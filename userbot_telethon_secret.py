#!/usr/bin/env python3
"""
🔐 TELETHON SECRET CHAT WRAPPER
Integrates Telethon secret chat with existing Pyrogram userbot setup
"""

import logging
import asyncio
import os
from typing import Optional, List, Tuple
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

logger = logging.getLogger(__name__)

class TelethonSecretChat:
    """Wrapper for Telethon secret chat functionality"""
    
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.secret_chat_manager = None
    
    async def initialize(self, api_id: int, api_hash: str, phone_number: str = None) -> bool:
        """Initialize Telethon client - will create its own session"""
        try:
            logger.info("🔐 TELETHON: Initializing for secret chat...")
            
            # 🚀 YOLO: Try to load existing Telethon session from PostgreSQL first
            from userbot_database import get_db_connection
            conn = get_db_connection()
            c = conn.cursor()
            
            telethon_session_string = None
            try:
                c.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'telethon_session_string'")
                result = c.fetchone()
                if result:
                    telethon_session_string = result['setting_value']
                    logger.info("✅ TELETHON: Found existing session string in database")
            except Exception as e:
                logger.info(f"ℹ️ TELETHON: No existing session found: {e}")
            finally:
                conn.close()
            
            # Create Telethon client with session string (or empty for new session)
            self.client = TelegramClient(
                StringSession(telethon_session_string) if telethon_session_string else StringSession(), 
                api_id, 
                api_hash
            )
            
            await self.client.connect()
            
            # Check if we need to authorize
            if not await self.client.is_user_authorized():
                logger.warning("⚠️ TELETHON: Not authorized, needs phone auth")
                
                # If we have a Pyrogram session but no Telethon session,
                # user is already logged in via Pyrogram, so we can use same credentials
                # But Telethon needs its own login flow
                
                # 🚀 YOLO: For now, we'll use the existing Pyrogram connection
                # and just skip Telethon secret chat (fall back to regular delivery)
                logger.warning("⚠️ TELETHON: Using fallback - will deliver via regular Pyrogram")
                return False
            
            # Initialize secret chat manager
            try:
                from telethon_secret_chat import SecretChatManager
                self.secret_chat_manager = SecretChatManager(self.client, auto_accept=True)
                logger.info("✅ TELETHON: Secret chat manager initialized")
            except ImportError:
                logger.error("❌ TELETHON: telethon-secret-chat library not installed!")
                return False
            
            me = await self.client.get_me()
            self.is_connected = True
            
            # 🚀 YOLO: Save Telethon session string to PostgreSQL for future use
            try:
                new_session_string = self.client.session.save()
                if new_session_string and not telethon_session_string:
                    # Save new session
                    conn = get_db_connection()
                    c = conn.cursor()
                    try:
                        c.execute("""
                            INSERT INTO system_settings (setting_key, setting_value)
                            VALUES ('telethon_session_string', %s)
                            ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value
                        """, (new_session_string,))
                        conn.commit()
                        logger.info("✅ TELETHON: Session string saved to database")
                    except Exception as save_err:
                        logger.warning(f"⚠️ TELETHON: Could not save session: {save_err}")
                        conn.rollback()
                    finally:
                        conn.close()
            except Exception as session_err:
                logger.warning(f"⚠️ TELETHON: Could not extract session string: {session_err}")
            
            logger.info(f"✅ TELETHON: Connected as @{me.username or me.first_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ TELETHON: Initialization failed: {e}", exc_info=True)
            return False
    
    async def disconnect(self):
        """Disconnect Telethon client"""
        try:
            if self.client:
                await self.client.disconnect()
                self.client = None
            self.is_connected = False
            logger.info("✅ TELETHON: Disconnected")
        except Exception as e:
            logger.error(f"❌ TELETHON: Error disconnecting: {e}")
    
    async def deliver_via_secret_chat(
        self, 
        buyer_user_id: int, 
        product_data: dict,
        media_binary_items: List[dict],  # [{'type': 'photo/video', 'binary': bytes, 'filename': str}]
        order_id: str
    ) -> Tuple[bool, str]:
        """
        🔐 Deliver product via Telethon secret chat
        
        Args:
            buyer_user_id: Telegram user ID
            product_data: Product details dict
            media_binary_items: List of media items with binary data
            order_id: Order identifier
        
        Returns:
            (success: bool, message: str)
        """
        if not self.is_connected or not self.secret_chat_manager:
            return False, "Telethon not connected"
        
        try:
            logger.info(f"🔐 TELETHON SECRET CHAT: Starting delivery to user {buyer_user_id}")
            
            # Get user entity
            try:
                user_entity = await self.client.get_entity(buyer_user_id)
                logger.info(f"✅ TELETHON: Found user entity for {buyer_user_id}")
            except Exception as e:
                logger.error(f"❌ TELETHON: Failed to get user entity: {e}")
                return False, f"Failed to find user: {e}"
            
            # Create or reuse secret chat
            secret_chat_id = None
            
            try:
                # Check for existing secret chats
                existing_chats = []
                try:
                    if hasattr(self.secret_chat_manager, 'get_all_secret_chats'):
                        existing_chats = self.secret_chat_manager.get_all_secret_chats()
                        logger.info(f"🔍 TELETHON: Found {len(existing_chats)} existing secret chats")
                except Exception as check_error:
                    logger.info(f"ℹ️ TELETHON: Could not check existing chats: {check_error}")
                
                # Try to reuse existing secret chat
                for chat in existing_chats:
                    try:
                        if hasattr(chat, 'user_id') and chat.user_id == user_entity.id:
                            secret_chat_id = chat.id
                            logger.info(f"✅ TELETHON: Reusing existing secret chat {secret_chat_id}")
                            break
                    except:
                        continue
                
                # Create new secret chat if none exists
                if not secret_chat_id:
                    logger.info(f"🔐 TELETHON: Creating NEW secret chat with user {buyer_user_id}")
                    secret_chat_id = await self.secret_chat_manager.start_secret_chat(user_entity)
                    logger.info(f"✅ TELETHON: NEW secret chat created, ID: {secret_chat_id}")
                    
                    # Wait for encryption handshake
                    await asyncio.sleep(3)
                
            except Exception as sc_error:
                logger.error(f"❌ TELETHON: Failed to create secret chat: {sc_error}")
                return False, f"Secret chat creation failed: {sc_error}"
            
            # Send product details message with retries
            message = f"""🔐 ENCRYPTED DELIVERY

📦 Order #{order_id}
🏷️ {product_data.get('product_name', 'Product')}
📏 {product_data.get('size', 'N/A')}
📍 {product_data.get('city', 'N/A')}, {product_data.get('district', 'N/A')}
💰 {product_data.get('price', 0):.2f} EUR

⏬ Receiving secure media..."""
            
            message_sent = False
            for attempt in range(1, 4):
                try:
                    wait_time = attempt * 2
                    logger.info(f"🔄 TELETHON: Attempt {attempt}/3 - waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    
                    secret_chat_obj = self.secret_chat_manager.get_secret_chat(secret_chat_id)
                    target = secret_chat_obj if secret_chat_obj else secret_chat_id
                    
                    await self.secret_chat_manager.send_secret_message(target, message)
                    logger.info(f"✅ TELETHON: Message sent on attempt {attempt}")
                    message_sent = True
                    break
                    
                except Exception as send_error:
                    logger.warning(f"⚠️ TELETHON: Attempt {attempt} failed: {send_error}")
                    if attempt == 3:
                        logger.error(f"❌ TELETHON: All message attempts failed!")
            
            if not message_sent:
                return False, "Failed to send message after 3 attempts"
            
            # Send media files
            if media_binary_items:
                logger.info(f"📂 TELETHON: Sending {len(media_binary_items)} media items")
                
                import tempfile
                temp_files = []
                
                try:
                    for i, media_item in enumerate(media_binary_items, 1):
                        media_type = media_item.get('media_type')
                        media_binary = media_item.get('media_binary')
                        filename = media_item.get('filename', f'media_{i}')
                        
                        if not media_binary:
                            logger.warning(f"⚠️ TELETHON: No binary data for item {i}")
                            continue
                        
                        # Write to temp file
                        suffix = '.jpg' if media_type == 'photo' else '.mp4'
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        temp_file.write(media_binary)
                        temp_file.close()
                        temp_files.append(temp_file.name)
                        
                        logger.info(f"📁 TELETHON: Created temp file for item {i}: {temp_file.name}")
                        
                        # Send to secret chat with retries
                        for attempt in range(1, 3):
                            try:
                                await asyncio.sleep(2)
                                
                                secret_chat_obj = self.secret_chat_manager.get_secret_chat(secret_chat_id)
                                target = secret_chat_obj if secret_chat_obj else secret_chat_id
                                
                                file_size = os.path.getsize(temp_file.name)
                                
                                if media_type == 'photo':
                                    await self.secret_chat_manager.send_secret_photo(
                                        target, 
                                        temp_file.name,
                                        thumb=b'', 
                                        thumb_w=100, 
                                        thumb_h=100, 
                                        w=800, 
                                        h=600, 
                                        size=file_size
                                    )
                                    logger.info(f"✅ TELETHON: Photo {i} sent")
                                    
                                elif media_type == 'video':
                                    # First upload to Saved Messages to get attributes
                                    me = await self.client.get_me()
                                    temp_msg = await self.client.send_file(me, temp_file.name)
                                    
                                    if temp_msg.video:
                                        video = temp_msg.video
                                        await self.secret_chat_manager.send_secret_video(
                                            target,
                                            temp_file.name,
                                            thumb=video.thumbs[0].bytes if video.thumbs else b'',
                                            thumb_w=video.thumbs[0].w if video.thumbs else 160,
                                            thumb_h=video.thumbs[0].h if video.thumbs else 120,
                                            duration=video.duration,
                                            mime_type=video.mime_type,
                                            w=video.w,
                                            h=video.h,
                                            size=video.size
                                        )
                                        logger.info(f"✅ TELETHON: Video {i} sent")
                                        
                                        # Cleanup temp message
                                        try:
                                            await temp_msg.delete()
                                        except:
                                            pass
                                    else:
                                        # Fallback to document
                                        await self.secret_chat_manager.send_secret_document(
                                            target,
                                            temp_file.name,
                                            thumb=b'',
                                            thumb_w=0,
                                            thumb_h=0,
                                            file_name=filename,
                                            mime_type='video/mp4',
                                            size=file_size
                                        )
                                        logger.info(f"✅ TELETHON: Video {i} sent as document")
                                
                                break  # Success
                                
                            except Exception as media_error:
                                logger.warning(f"⚠️ TELETHON: Attempt {attempt} failed for media {i}: {media_error}")
                                if attempt == 2:
                                    logger.error(f"❌ TELETHON: Failed to send media {i}")
                
                finally:
                    # Cleanup temp files
                    for temp_file in temp_files:
                        try:
                            os.unlink(temp_file)
                        except:
                            pass
                    logger.info(f"🗑️ TELETHON: Cleaned up {len(temp_files)} temp files")
            
            # Send final details
            details_text = f"""📦 Product Details

🏷️ {product_data.get('product_name', 'Product')}
📏 {product_data.get('size', 'N/A')}
📍 {product_data.get('city', 'N/A')}, {product_data.get('district', 'N/A')}
💰 {product_data.get('price', 0):.2f} EUR

📝 Pickup Details:
{product_data.get('original_text', 'No additional details.')}

✅ Order Completed
Order ID: {order_id}

Thank you! 🎉"""
            
            try:
                await asyncio.sleep(2)
                secret_chat_obj = self.secret_chat_manager.get_secret_chat(secret_chat_id)
                target = secret_chat_obj if secret_chat_obj else secret_chat_id
                await self.secret_chat_manager.send_secret_message(target, details_text)
                logger.info(f"✅ TELETHON: Product details sent")
            except Exception as details_error:
                logger.warning(f"⚠️ TELETHON: Failed to send details: {details_error}")
            
            logger.info(f"🎉 TELETHON: Secret chat delivery completed for user {buyer_user_id}")
            return True, f"Delivered via SECRET CHAT (chat_id: {secret_chat_id})"
            
        except Exception as e:
            logger.error(f"❌ TELETHON: Delivery failed: {e}", exc_info=True)
            return False, f"Secret chat delivery error: {str(e)}"

# Global instance
telethon_secret_chat = TelethonSecretChat()

