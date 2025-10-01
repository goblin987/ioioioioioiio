"""
Userbot Manager - Pyrogram Client Wrapper
Handles Telegram userbot connection, session management, and auto-reconnect
"""

import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone

try:
    from pyrogram import Client
    from pyrogram.errors import (
        SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired,
        PhoneNumberInvalid, ApiIdInvalid, AuthKeyUnregistered,
        UserDeactivated, UserDeactivatedBan, FloodWait
    )
    from pyrogram.types import User
    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error("❌ Pyrogram not installed. Install with: pip install pyrogram")

from userbot_config import userbot_config
from userbot_database import (
    save_session_string,
    get_session_string,
    update_connection_status,
    get_connection_status
)

logger = logging.getLogger(__name__)

class UserbotManager:
    """Manages Pyrogram userbot client and connections"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.is_connected: bool = False
        self.is_initializing: bool = False
        self.reconnect_task: Optional[asyncio.Task] = None
        self._setup_phone_code_hash: Optional[str] = None
        
    async def initialize(self) -> bool:
        """Initialize userbot client from database config"""
        if not PYROGRAM_AVAILABLE:
            logger.error("❌ Pyrogram not available")
            await asyncio.to_thread(update_connection_status, False, "Pyrogram not installed")
            return False
        
        if self.is_initializing:
            logger.warning("⚠️ Userbot is already initializing")
            return False
        
        if not userbot_config.is_configured():
            logger.warning("⚠️ Userbot not configured")
            await asyncio.to_thread(update_connection_status, False, "Not configured")
            return False
        
        self.is_initializing = True
        
        try:
            logger.info("🔧 Initializing userbot...")
            
            api_id = userbot_config.api_id
            api_hash = userbot_config.api_hash
            
            if not api_id or not api_hash:
                logger.error("❌ Missing API credentials")
                await asyncio.to_thread(update_connection_status, False, "Missing API credentials")
                return False
            
            # Get session string from database
            session_string = get_session_string()
            
            # Create Pyrogram client
            # 🚀 YOLO FIX: in_memory=False to persist peer cache across restarts!
            self.client = Client(
                name="userbot_session",
                api_id=int(api_id),
                api_hash=api_hash,
                session_string=session_string,
                workdir="./userbot_data",
                in_memory=False  # Must be False to save peers to disk!
            )
            
            # Connect to Telegram
            await self.client.start()
            
            # Verify connection
            me = await self.client.get_me()
            logger.info(f"✅ Userbot connected as @{me.username or me.first_name} (ID: {me.id})")
            
            self.is_connected = True
            await asyncio.to_thread(update_connection_status, True, f"Connected as @{me.username or me.first_name}")
            
            # Save session string for future use
            if not session_string:
                new_session = await self.client.export_session_string()
                save_session_string(new_session)
                logger.info("✅ Session string saved to database")
            
            # Start auto-reconnect monitor if enabled
            if userbot_config.auto_reconnect and not self.reconnect_task:
                self.reconnect_task = asyncio.create_task(self._monitor_connection())
            
            return True
            
        except AuthKeyUnregistered:
            logger.error("❌ Session expired - need to re-authenticate")
            await asyncio.to_thread(update_connection_status, False, "Session expired")
            return False
            
        except (UserDeactivated, UserDeactivatedBan):
            logger.error("❌ User account deactivated or banned")
            await asyncio.to_thread(update_connection_status, False, "Account deactivated")
            return False
            
        except ApiIdInvalid:
            logger.error("❌ Invalid API ID or Hash")
            await asyncio.to_thread(update_connection_status, False, "Invalid API credentials")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error initializing userbot: {e}", exc_info=True)
            await asyncio.to_thread(update_connection_status, False, f"Error: {str(e)[:100]}")
            return False
            
        finally:
            self.is_initializing = False
    
    async def disconnect(self) -> bool:
        """Disconnect userbot"""
        try:
            if self.reconnect_task:
                self.reconnect_task.cancel()
                self.reconnect_task = None
            
            if self.client:
                # Check if client is already disconnected to prevent "already terminated" error
                try:
                    if hasattr(self.client, 'is_connected') and self.client.is_connected:
                        await self.client.stop()
                        logger.info("✅ Userbot disconnected")
                    else:
                        logger.info("ℹ️ Client already disconnected, skipping stop()")
                except ConnectionError as e:
                    if "already terminated" in str(e).lower():
                        logger.info("ℹ️ Client already terminated, safe to ignore")
                    else:
                        raise
            
            self.is_connected = False
            await asyncio.to_thread(update_connection_status, False, "Manually disconnected")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error disconnecting userbot: {e}", exc_info=True)
            return False
    
    async def reconnect(self) -> bool:
        """Reconnect userbot"""
        logger.info("🔄 Reconnecting userbot...")
        await self.disconnect()
        await asyncio.sleep(2)
        return await self.initialize()
    
    async def _monitor_connection(self):
        """Monitor connection and auto-reconnect if needed"""
        logger.info("👁️ Connection monitor started")
        
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if not self.client or not self.is_connected:
                    continue
                
                # Check if still connected
                try:
                    await self.client.get_me()
                except Exception as e:
                    logger.warning(f"⚠️ Connection lost: {e}")
                    self.is_connected = False
                    await asyncio.to_thread(update_connection_status, False, "Connection lost")
                    
                    if userbot_config.auto_reconnect:
                        logger.info("🔄 Auto-reconnecting...")
                        await self.reconnect()
                
            except asyncio.CancelledError:
                logger.info("Connection monitor stopped")
                break
            except Exception as e:
                logger.error(f"❌ Error in connection monitor: {e}", exc_info=True)
    
    async def start_phone_auth(self, phone_number: str) -> dict:
        """Start phone authentication process"""
        if not PYROGRAM_AVAILABLE:
            return {'success': False, 'error': 'Pyrogram not installed'}
        
        try:
            api_id = userbot_config.api_id
            api_hash = userbot_config.api_hash
            
            if not api_id or not api_hash:
                return {'success': False, 'error': 'API credentials not set'}
            
            # Create temporary client for authentication
            temp_client = Client(
                name="temp_auth",
                api_id=int(api_id),
                api_hash=api_hash,
                phone_number=phone_number,
                workdir="./userbot_data",
                in_memory=True
            )
            
            # Connect and send code
            await temp_client.connect()
            sent_code = await temp_client.send_code(phone_number)
            
            self._setup_phone_code_hash = sent_code.phone_code_hash
            self.client = temp_client
            
            logger.info(f"✅ Verification code sent to {phone_number}")
            
            return {
                'success': True,
                'phone_code_hash': sent_code.phone_code_hash,
                'message': 'Verification code sent'
            }
            
        except PhoneNumberInvalid:
            return {'success': False, 'error': 'Invalid phone number'}
        except FloodWait as e:
            return {'success': False, 'error': f'Too many attempts. Wait {e.value} seconds'}
        except Exception as e:
            logger.error(f"❌ Error starting phone auth: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def verify_phone_code(self, phone_number: str, code: str) -> dict:
        """Verify phone code and complete authentication"""
        if not self.client or not self._setup_phone_code_hash:
            return {'success': False, 'error': 'Authentication not started'}
        
        try:
            # Sign in with code
            await self.client.sign_in(
                phone_number=phone_number,
                phone_code_hash=self._setup_phone_code_hash,
                phone_code=code
            )
            
            # Get user info
            me = await self.client.get_me()
            
            # Export and save session
            session_string = await self.client.export_session_string()
            save_session_string(session_string)
            
            logger.info(f"✅ Authentication successful: @{me.username or me.first_name}")
            
            # Stop temporary client safely
            try:
                if self.client and not self.client.is_connected:
                    # Client already disconnected, just clean up
                    pass
                else:
                    await self.client.stop()
            except Exception as e:
                logger.warning(f"⚠️ Error stopping temp client (safe to ignore): {e}")
            
            # Reset temp variables
            self.client = None
            self._setup_phone_code_hash = None
            
            return {
                'success': True,
                'username': me.username or me.first_name,
                'user_id': me.id
            }
            
        except PhoneCodeInvalid:
            return {'success': False, 'error': 'Invalid verification code'}
        except PhoneCodeExpired:
            return {'success': False, 'error': 'Verification code expired'}
        except SessionPasswordNeeded:
            return {'success': False, 'error': '2FA enabled. Please disable it first'}
        except Exception as e:
            logger.error(f"❌ Error verifying code: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def send_message(
        self,
        user_id: int,
        text: str,
        parse_mode: str = None,
        disable_web_page_preview: bool = True
    ) -> dict:
        """Send text message to user"""
        if not self.is_connected or not self.client:
            return {'success': False, 'error': 'Userbot not connected'}
        
        try:
            message = await self.client.send_message(
                chat_id=user_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
            
            logger.info(f"✅ Message sent to user {user_id}")
            return {'success': True, 'message_id': message.id}
            
        except FloodWait as e:
            logger.warning(f"⚠️ FloodWait: {e.value} seconds")
            return {'success': False, 'error': f'Rate limited. Wait {e.value}s'}
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def send_photo(
        self,
        user_id: int,
        photo_path: str,
        caption: str = None,
        ttl_seconds: int = None
    ) -> dict:
        """Send photo to user with optional TTL"""
        if not self.is_connected or not self.client:
            return {'success': False, 'error': 'Userbot not connected'}
        
        try:
            message = await self.client.send_photo(
                chat_id=user_id,
                photo=photo_path,
                caption=caption,
                ttl_seconds=ttl_seconds
            )
            
            logger.info(f"✅ Photo sent to user {user_id}")
            return {'success': True, 'message_id': message.id}
            
        except FloodWait as e:
            logger.warning(f"⚠️ FloodWait: {e.value} seconds")
            return {'success': False, 'error': f'Rate limited. Wait {e.value}s'}
        except Exception as e:
            logger.error(f"❌ Error sending photo: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def send_video(
        self,
        user_id: int,
        video_path: str,
        caption: str = None,
        ttl_seconds: int = None
    ) -> dict:
        """Send video to user with optional TTL"""
        if not self.is_connected or not self.client:
            return {'success': False, 'error': 'Userbot not connected'}
        
        try:
            message = await self.client.send_video(
                chat_id=user_id,
                video=video_path,
                caption=caption,
                ttl_seconds=ttl_seconds
            )
            
            logger.info(f"✅ Video sent to user {user_id}")
            return {'success': True, 'message_id': message.id}
            
        except FloodWait as e:
            logger.warning(f"⚠️ FloodWait: {e.value} seconds")
            return {'success': False, 'error': f'Rate limited. Wait {e.value}s'}
        except Exception as e:
            logger.error(f"❌ Error sending video: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def send_document(
        self,
        user_id: int,
        document_path: str,
        caption: str = None
    ) -> dict:
        """Send document to user"""
        if not self.is_connected or not self.client:
            return {'success': False, 'error': 'Userbot not connected'}
        
        try:
            message = await self.client.send_document(
                chat_id=user_id,
                document=document_path,
                caption=caption
            )
            
            logger.info(f"✅ Document sent to user {user_id}")
            return {'success': True, 'message_id': message.id}
            
        except FloodWait as e:
            logger.warning(f"⚠️ FloodWait: {e.value} seconds")
            return {'success': False, 'error': f'Rate limited. Wait {e.value}s'}
        except Exception as e:
            logger.error(f"❌ Error sending document: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def get_user_info(self, user_id: int) -> Optional[dict]:
        """Get user information"""
        if not self.is_connected or not self.client:
            return None
        
        try:
            user = await self.client.get_users(user_id)
            return {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_bot': user.is_bot
            }
        except Exception as e:
            logger.error(f"❌ Error getting user info: {e}", exc_info=True)
            return None
    
    async def deliver_product_via_secret_chat(
        self,
        buyer_user_id: int,
        product_data: dict,
        order_id: str,
        telegram_bot = None
    ) -> dict:
        """
        🚀 YOLO MODE: Deliver product using Saved Messages storage + Main Bot delivery
        
        This prevents media corruption and PEER_ID_INVALID by:
        1. Uploading media to userbot's Saved Messages (preserves quality, safe storage)
        2. Getting new file_ids from Saved Messages
        3. Using MAIN BOT to send to buyer (no PEER_ID_INVALID!)
        4. Cleaning up Saved Messages after 6 hours
        
        Args:
            buyer_user_id: Telegram user ID of buyer
            product_data: Dict with keys: product_id, product_name, size, city, district, price, media_items
            order_id: Unique order identifier
            telegram_bot: Main Telegram bot instance for sending messages
            
        Returns:
            dict: {'success': bool, 'error': str (if failed), 'media_file_ids': [list of new file_ids]}
        """
        if not self.is_connected or not self.client:
            logger.error("❌ Userbot not connected for secret chat delivery")
            return {'success': False, 'error': 'Userbot not connected'}
        
        try:
            product_id = product_data.get('product_id')
            product_name = product_data.get('product_name', 'Product')
            media_items = product_data.get('media_items', [])
            
            logger.info(f"🔐 Starting TRUE SECRET CHAT delivery for user {buyer_user_id}, product {product_id}")
            
            # PHASE 0: Request/Get Secret Chat with buyer
            # 🚀 YOLO: Userbots CAN initiate secret chats without prior interaction!
            secret_chat_id = None
            try:
                logger.info(f"🔐 Requesting secret chat with user {buyer_user_id}...")
                
                # Try to get existing secret chat from database first
                from userbot_database import get_secret_chat_id, save_secret_chat
                existing_chat_id = get_secret_chat_id(buyer_user_id)
                
                if existing_chat_id:
                    logger.info(f"✅ Found existing secret chat: {existing_chat_id}")
                    secret_chat_id = existing_chat_id
                else:
                    # 🚀 YOLO MODE: Use Pyrogram's built-in create_secret_chat() method!
                    # NO prior interaction needed - it just works!
                    logger.info(f"🔐 Creating secret chat with user {buyer_user_id}...")
                    
                    try:
                        # THIS IS THE CORRECT WAY - Pyrogram handles everything!
                        secret_chat = await self.client.create_secret_chat(buyer_user_id)
                        secret_chat_id = secret_chat.id
                        
                        # Save to database for future use
                        save_secret_chat(buyer_user_id, secret_chat_id)
                        logger.info(f"✅ Created secret chat {secret_chat_id} with user {buyer_user_id}")
                        
                        # Wait for encryption handshake
                        await asyncio.sleep(2)
                        
                    except Exception as sc_err:
                        logger.error(f"❌ Failed to create secret chat: {sc_err}")
                        return {
                            'success': False,
                            'error': f'Failed to create secret chat: {str(sc_err)}'
                        }
                    
            except Exception as e:
                logger.error(f"❌ Failed to create secret chat: {e}", exc_info=True)
                return {
                    'success': False,
                    'error': f'Failed to create secret chat: {str(e)}'
                }
            
            # PHASE 1: Upload media to Saved Messages using binary data from PostgreSQL
            # 🚀 YOLO STRATEGY: Upload to Saved Messages, then forward to secret chat
            saved_message_ids = []
            
            if media_items:
                logger.info(f"📤 Uploading {len(media_items)} media items to Saved Messages from PostgreSQL...")
                
                for idx, media_item in enumerate(media_items, 1):
                    media_binary = media_item.get('media_binary')
                    media_type = media_item.get('media_type')
                    
                    if not media_binary:
                        logger.warning(f"⚠️ No binary data for media item {idx}, skipping")
                        continue
                    
                    try:
                        # Create BytesIO object for upload
                        import io
                        media_file = io.BytesIO(media_binary)
                        
                        # Set filename based on media type
                        if media_type == 'photo':
                            media_file.name = f"product_{product_id}_{idx}.jpg"
                        elif media_type == 'video':
                            media_file.name = f"product_{product_id}_{idx}.mp4"
                        elif media_type == 'gif':
                            media_file.name = f"product_{product_id}_{idx}.mp4"
                        else:
                            logger.warning(f"⚠️ Unsupported media type: {media_type}")
                            continue
                        
                        logger.info(f"📤 Uploading media item {idx} ({len(media_binary)} bytes) to Saved Messages...")
                        
                        # Upload to Saved Messages ('me')
                        if media_type == 'photo':
                            saved_msg = await self.client.send_photo(
                                chat_id='me',  # Saved Messages
                                photo=media_file,
                                caption=f"📦 Order #{order_id} - Item {idx}/{len(media_items)}"
                            )
                        elif media_type == 'video':
                            saved_msg = await self.client.send_video(
                                chat_id='me',
                                video=media_file,
                                caption=f"📦 Order #{order_id} - Item {idx}/{len(media_items)}"
                            )
                        elif media_type == 'gif':
                            saved_msg = await self.client.send_animation(
                                chat_id='me',
                                animation=media_file,
                                caption=f"📦 Order #{order_id} - Item {idx}/{len(media_items)}"
                            )
                        
                        saved_message_ids.append(saved_msg.id)
                        
                        # 🚀 YOLO: Extract file_id from the saved message for main bot to use
                        if saved_msg.photo:
                            new_file_id = saved_msg.photo.file_id
                            new_file_ids.append(('photo', new_file_id))
                            logger.info(f"✅ Uploaded photo {idx} to Saved Messages (msg_id: {saved_msg.id}, file_id: {new_file_id[:20]}...)")
                        elif saved_msg.video:
                            new_file_id = saved_msg.video.file_id
                            new_file_ids.append(('video', new_file_id))
                            logger.info(f"✅ Uploaded video {idx} to Saved Messages (msg_id: {saved_msg.id}, file_id: {new_file_id[:20]}...)")
                        elif saved_msg.animation:
                            new_file_id = saved_msg.animation.file_id
                            new_file_ids.append(('animation', new_file_id))
                            logger.info(f"✅ Uploaded animation {idx} to Saved Messages (msg_id: {saved_msg.id}, file_id: {new_file_id[:20]}...)")
                        
                        # Rate limiting
                        await asyncio.sleep(1)
                        
                    except FloodWait as e:
                        logger.warning(f"⚠️ FloodWait for {e.value}s, waiting...")
                        await asyncio.sleep(e.value)
                        continue
                    except Exception as e:
                        logger.error(f"❌ Failed to upload media item {idx}: {e}", exc_info=True)
                        continue
                
                # Wait for Telegram to process
                logger.info("⏳ Waiting 3 seconds for Telegram to process...")
                await asyncio.sleep(3)
            
            # PHASE 2: Send initial notification to SECRET CHAT
            try:
                notification_text = f"""🔐 ENCRYPTED DELIVERY

📦 Order #{order_id}
🏷️ {product_name}
📏 {product_data.get('size', 'N/A')}
📍 {product_data.get('city', 'N/A')}, {product_data.get('district', 'N/A')}
💰 {product_data.get('price', 0):.2f} EUR

⏬ Receiving secure media..."""
                
                # 🚀 YOLO: Send to SECRET CHAT (no HTML parsing in secret chats!)
                await self.client.send_message(
                    chat_id=secret_chat_id,
                    text=notification_text
                )
                logger.info(f"✅ Sent notification to secret chat {secret_chat_id}")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Failed to send notification to secret chat: {e}")
                # Continue anyway
            
            # PHASE 3: Forward saved messages to SECRET CHAT
            forwarded_count = 0
            
            if saved_message_ids:
                logger.info(f"🔐 Forwarding {len(saved_message_ids)} messages to SECRET CHAT {secret_chat_id}...")
                
                for msg_id in saved_message_ids:
                    try:
                        # 🚀 YOLO: Forward to SECRET CHAT
                        await self.client.forward_messages(
                            chat_id=secret_chat_id,
                            from_chat_id='me',  # From Saved Messages
                            message_ids=msg_id
                        )
                        forwarded_count += 1
                        logger.info(f"✅ Forwarded message {msg_id} to secret chat {secret_chat_id}")
                        
                        # Rate limiting between forwards
                        await asyncio.sleep(2)
                        
                    except FloodWait as e:
                        logger.warning(f"⚠️ FloodWait for {e.value}s, waiting...")
                        await asyncio.sleep(e.value)
                        continue
                    except Exception as e:
                        logger.error(f"❌ Failed to forward message {msg_id} to secret chat: {e}")
                        continue
            
            # PHASE 4: Send product details to SECRET CHAT
            try:
                details_text = f"""📦 Product Details

🏷️ {product_name}
📏 {product_data.get('size', 'N/A')}
📍 {product_data.get('city', 'N/A')}, {product_data.get('district', 'N/A')}
💰 {product_data.get('price', 0):.2f} EUR

📝 Pickup Details:
{product_data.get('original_text', 'No additional details provided.')}

✅ Order Completed
Order ID: {order_id}

Thank you! 🎉"""
                
                # 🚀 YOLO: Send to SECRET CHAT (no HTML parsing!)
                await self.client.send_message(
                    chat_id=secret_chat_id,
                    text=details_text
                )
                logger.info(f"✅ Sent product details to secret chat {secret_chat_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to send product details to secret chat: {e}")
            
            # PHASE 5: Schedule cleanup of Saved Messages after 6 hours
            if saved_message_ids:
                asyncio.create_task(
                    self._cleanup_saved_messages_later(saved_message_ids, delay_hours=6)
                )
                logger.info(f"🗑️ Scheduled cleanup of {len(saved_message_ids)} Saved Messages in 6 hours")
            
            # Success!
            success_msg = f"✅ Delivered {forwarded_count} media items to user {buyer_user_id}"
            logger.info(success_msg)
            
            return {
                'success': True,
                'media_count': forwarded_count,
                'message': success_msg
            }
            
        except Exception as e:
            logger.error(f"❌ Secret chat delivery failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _cleanup_saved_messages_later(self, message_ids: list, delay_hours: int = 6):
        """Cleanup Saved Messages after specified delay"""
        await asyncio.sleep(delay_hours * 3600)
        
        try:
            if self.is_connected and self.client:
                await self.client.delete_messages(
                    chat_id='me',  # Saved Messages
                    message_ids=message_ids
                )
                logger.info(f"🗑️ Cleaned up {len(message_ids)} messages from Saved Messages")
        except Exception as e:
            logger.error(f"❌ Failed to cleanup saved messages: {e}")

# Global userbot manager instance
userbot_manager = UserbotManager()

