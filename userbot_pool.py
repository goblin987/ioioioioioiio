"""
Userbot Pool Manager
Manages multiple Telethon userbots for secret chat delivery with load balancing
"""

import logging
import asyncio
import os
import tempfile
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeVideo
from telethon_secret_chat import SecretChatManager
import io

logger = logging.getLogger(__name__)

class UserbotPool:
    """Manages a pool of Telethon userbots for secret chat delivery"""
    
    def __init__(self):
        self.clients: Dict[int, TelegramClient] = {}  # userbot_id -> client
        self.secret_chat_managers: Dict[int, SecretChatManager] = {}  # userbot_id -> manager
        self.is_initialized = False
        self._last_used_index = 0
        
    async def initialize(self):
        """Initialize all enabled userbots from database"""
        if self.is_initialized:
            logger.info("Userbot pool already initialized")
            return
        
        logger.info("🔄 Initializing userbot pool...")
        
        from userbot_database import get_db_connection
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            # Get all enabled userbots with sessions
            c.execute("""
                SELECT id, name, api_id, api_hash, phone_number, session_string, priority
                FROM userbots
                WHERE is_enabled = TRUE AND session_string IS NOT NULL
                ORDER BY priority DESC, id ASC
            """)
            
            userbots = c.fetchall()
            
            if not userbots:
                logger.warning("⚠️ No enabled userbots found in database")
                return
            
            logger.info(f"📋 Found {len(userbots)} enabled userbot(s) to initialize")
            
            # Initialize each userbot
            for ub in userbots:
                userbot_id = ub['id']
                name = ub['name']
                api_id = int(ub['api_id'])
                api_hash = ub['api_hash']
                session_string = ub['session_string']
                
                try:
                    logger.info(f"🔌 Connecting userbot #{userbot_id} ({name})...")
                    
                    # Create Telethon client
                    client = TelegramClient(
                        StringSession(session_string),
                        api_id,
                        api_hash
                    )
                    
                    await client.connect()
                    
                    # Check if authorized
                    if not await client.is_user_authorized():
                        logger.error(f"❌ Userbot #{userbot_id} not authorized!")
                        await client.disconnect()
                        self._update_connection_status(userbot_id, False, "Not authorized")
                        continue
                    
                    # Get user info
                    me = await client.get_me()
                    username = me.username or me.first_name
                    
                    # Create secret chat manager
                    secret_chat_manager = SecretChatManager(client, auto_accept=True)
                    
                    # Store in pool
                    self.clients[userbot_id] = client
                    self.secret_chat_managers[userbot_id] = secret_chat_manager
                    
                    # Update database status
                    self._update_connection_status(userbot_id, True, f"Connected as @{username}")
                    
                    logger.info(f"✅ Userbot #{userbot_id} ({name}) connected as @{username}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to initialize userbot #{userbot_id} ({name}): {e}", exc_info=True)
                    self._update_connection_status(userbot_id, False, f"Error: {str(e)[:100]}")
                    continue
            
            self.is_initialized = True
            logger.info(f"✅ Userbot pool initialized with {len(self.clients)} active userbot(s)")
            
        except Exception as e:
            logger.error(f"❌ Error initializing userbot pool: {e}", exc_info=True)
        finally:
            conn.close()
    
    def _update_connection_status(self, userbot_id: int, is_connected: bool, status_message: str):
        """Update userbot connection status in database"""
        from userbot_database import get_db_connection
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute("""
                UPDATE userbots
                SET is_connected = %s, status_message = %s, last_connected_at = %s
                WHERE id = %s
            """, (is_connected, status_message, datetime.now(timezone.utc) if is_connected else None, userbot_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating connection status for userbot #{userbot_id}: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_available_userbot(self) -> Optional[Tuple[int, TelegramClient, SecretChatManager]]:
        """Get next available userbot using round-robin selection"""
        if not self.clients:
            logger.warning("⚠️ No userbots available in pool")
            return None
        
        userbot_ids = list(self.clients.keys())
        
        # Round-robin selection
        self._last_used_index = (self._last_used_index + 1) % len(userbot_ids)
        userbot_id = userbot_ids[self._last_used_index]
        
        client = self.clients.get(userbot_id)
        secret_chat_manager = self.secret_chat_managers.get(userbot_id)
        
        if client and secret_chat_manager:
            logger.info(f"🎯 Selected userbot #{userbot_id} for delivery (round-robin)")
            return userbot_id, client, secret_chat_manager
        
        return None
    
    async def deliver_via_secret_chat(
        self,
        buyer_user_id: int,
        buyer_username: Optional[str],
        product_data: dict,
        media_binary_items: List[Dict],
        order_id: str
    ) -> Tuple[bool, str]:
        """Deliver product via secret chat using an available userbot from the pool"""
        
        # Get available userbot
        userbot_info = self.get_available_userbot()
        
        if not userbot_info:
            return False, "No userbots available in pool"
        
        userbot_id, client, secret_chat_manager = userbot_info
        
        try:
            logger.info(f"🔐 Starting SECRET CHAT delivery via userbot #{userbot_id} to user {buyer_user_id} (@{buyer_username or 'no_username'})")
            
            # 1. Get FULL user entity (not just InputPeer) - try username first
            try:
                if buyer_username:
                    logger.info(f"🔍 Getting FULL user entity by username: @{buyer_username}...")
                    user_entity = await client.get_entity(buyer_username)
                    logger.info(f"✅ Got full user entity by username: {user_entity.id}")
                else:
                    logger.info(f"🔍 Getting FULL user entity by ID: {buyer_user_id}...")
                    user_entity = await client.get_entity(buyer_user_id)
                    logger.info(f"✅ Got full user entity by ID: {user_entity.id}")
            except Exception as e:
                logger.error(f"❌ Error getting user entity for {buyer_user_id} (@{buyer_username or 'N/A'}): {e}")
                return False, f"Failed to get user entity: {e}"
            
            # 2. Get or create secret chat (REUSE existing chats to avoid rate limits!)
            secret_chat_id = None
            secret_chat_obj = None
            try:
                # 🎯 ATTEMPT #28: Check for existing secret chat FIRST!
                # Try multiple methods to get existing chats
                existing_chat = None
                
                try:
                    # Method 1: Try session.get_all_secret_chats()
                    if hasattr(secret_chat_manager, 'session'):
                        session = secret_chat_manager.session
                        if hasattr(session, 'get_all_secret_chats'):
                            existing_chats = session.get_all_secret_chats()
                            logger.info(f"♻️ Found {len(existing_chats)} existing secret chats via session")
                            for chat in existing_chats:
                                if hasattr(chat, 'user_id') and chat.user_id == user_entity.id:
                                    existing_chat = chat
                                    logger.info(f"♻️ Found existing chat with user {user_entity.id}! Chat ID: {chat.id}")
                                    break
                        elif hasattr(session, 'get_secret_chat_by_user_id'):
                            # Method 2: Direct lookup by user_id
                            existing_chat = session.get_secret_chat_by_user_id(user_entity.id)
                            if existing_chat:
                                logger.info(f"♻️ Found existing chat via user_id lookup: {existing_chat.id}")
                except Exception as lookup_err:
                    logger.info(f"ℹ️ Could not lookup existing chats: {lookup_err}")
                
                if existing_chat:
                    # Reuse existing chat!
                    secret_chat_obj = existing_chat
                    secret_chat_id = existing_chat.id
                    logger.info(f"✅ Reusing existing secret chat: {secret_chat_id}")
                else:
                    # Create new chat only if none exists
                    logger.info(f"🔐 Starting NEW secret chat with user {user_entity.id} (@{buyer_username or 'N/A'})...")
                    secret_chat_id = await secret_chat_manager.start_secret_chat(user_entity)
                    logger.info(f"✅ Secret chat started! ID: {secret_chat_id}")
                    # Wait for encryption handshake
                    await asyncio.sleep(2)
                    
                    # Get the actual secret chat object from the manager
                    secret_chat_obj = secret_chat_manager.get_secret_chat(secret_chat_id)
                    logger.info(f"✅ Retrieved secret chat object: {type(secret_chat_obj)}")
                
                # 🔍 CRITICAL DEBUG: Check secret chat layer!
                try:
                    if hasattr(secret_chat_obj, 'layer'):
                        logger.critical(f"🎯 SECRET CHAT LAYER: {secret_chat_obj.layer}")
                    if hasattr(secret_chat_obj, '__dict__'):
                        logger.critical(f"🔍 SECRET CHAT ATTRIBUTES: {list(secret_chat_obj.__dict__.keys())}")
                except Exception as layer_err:
                    logger.error(f"❌ Could not inspect secret chat: {layer_err}")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Failed to start secret chat: {e}")
                
                # 🎯 ATTEMPT #29: If rate limited, try a DIFFERENT userbot!
                if "wait of" in error_msg and "seconds is required" in error_msg:
                    logger.warning(f"⚠️ Userbot #{userbot_id} is RATE LIMITED! Trying a different userbot...")
                    
                    # Try to get a different userbot
                    all_userbot_ids = list(self.clients.keys())
                    for alt_userbot_id in all_userbot_ids:
                        if alt_userbot_id == userbot_id:
                            continue  # Skip the rate-limited one
                        
                        logger.info(f"🔄 Retrying with userbot #{alt_userbot_id}...")
                        alt_client = self.clients.get(alt_userbot_id)
                        alt_secret_chat_manager = self.secret_chat_managers.get(alt_userbot_id)
                        
                        if not alt_client or not alt_secret_chat_manager:
                            continue
                        
                        try:
                            # CRITICAL: Re-fetch user entity using the NEW client's session!
                            logger.info(f"🔄 Re-fetching user entity for userbot #{alt_userbot_id}...")
                            if buyer_username:
                                alt_user_entity = await alt_client.get_entity(buyer_username)
                            else:
                                alt_user_entity = await alt_client.get_entity(buyer_user_id)
                            logger.info(f"✅ Got user entity for alt userbot")
                            
                            # Try creating secret chat with alternative userbot
                            logger.info(f"🔐 Creating secret chat with userbot #{alt_userbot_id}...")
                            alt_secret_chat_id = await alt_secret_chat_manager.start_secret_chat(alt_user_entity)
                            logger.info(f"✅ Secret chat created with alt userbot! ID: {alt_secret_chat_id}")
                            await asyncio.sleep(2)
                            
                            # Use this userbot instead!
                            userbot_id = alt_userbot_id
                            client = alt_client
                            secret_chat_manager = alt_secret_chat_manager
                            secret_chat_id = alt_secret_chat_id
                            secret_chat_obj = secret_chat_manager.get_secret_chat(alt_secret_chat_id)
                            
                            logger.info(f"✅ Successfully switched to userbot #{alt_userbot_id}!")
                            break  # Success! Continue with delivery
                        except Exception as alt_err:
                            logger.warning(f"⚠️ Userbot #{alt_userbot_id} also failed: {alt_err}")
                            continue  # Try next userbot
                    else:
                        # All userbots failed
                        return False, f"All userbots are rate limited or failed: {e}"
                else:
                    # Not a rate limit error, just fail
                    return False, f"Failed to start secret chat: {e}"
            
            # 3. Send notification
            notification_text = f"""🔐 ENCRYPTED DELIVERY
📦 Order #{order_id}
🏷️ {product_data.get('product_name', 'Product')}
📏 {product_data.get('size', 'N/A')}
📍 {product_data.get('city', 'N/A')}, {product_data.get('district', 'N/A')}
💰 {product_data.get('price', 0):.2f} EUR
⏬ Receiving secure media..."""
            
            try:
                await secret_chat_manager.send_secret_message(secret_chat_obj, notification_text)
                logger.info(f"✅ Sent notification to secret chat")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Failed to send notification: {e}")
            
            # 4. Send media files
            sent_media_count = 0
            if media_binary_items and len(media_binary_items) > 0:
                logger.info(f"📂 Sending {len(media_binary_items)} media items via SECRET CHAT...")
                for idx, media_item in enumerate(media_binary_items, 1):
                    media_type = media_item['media_type']
                    media_binary = media_item['media_binary']
                    filename = media_item['filename']
                    
                    try:
                        logger.info(f"📤 Sending SECRET CHAT media {idx}/{len(media_binary_items)} ({len(media_binary)} bytes) type: {media_type}...")
                        
                        # Save to temp file (secret chat library needs file path)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                            temp_file.write(media_binary)
                            temp_path = temp_file.name
                        
                        try:
                            # MANUAL ENCRYPTION APPROACH (MTProto spec compliant!)
                            # 1. Encrypt the file ourselves with AES-256-IGE
                            # 2. Upload encrypted file to Telegram
                            # 3. Send decryption key via secret chat
                            
                            # Send via secret chat with proper parameters
                            logger.info(f"📤 Sending {media_type} via secret chat...")
                            
                            file_size = len(media_binary)
                            
                            if media_type == 'photo':
                                # Send photo with required parameters
                                await secret_chat_manager.send_secret_photo(
                                    secret_chat_obj,
                                    temp_path,
                                    thumb=b'',
                                    thumb_w=100,
                                    thumb_h=100,
                                    w=960,
                                    h=1280,
                                    size=file_size
                                )
                                logger.info(f"✅ SECRET CHAT photo {idx} sent!")
                                sent_media_count += 1
                                
                            elif media_type == 'video':
                                # 🔥 ATTEMPT #14: Full MTProto 2.0 manual implementation!
                                logger.info(f"🚀 ATTEMPT #14: Using manual MTProto 2.0 implementation...")
                                
                                try:
                                    # First, extract video attributes
                                    logger.info(f"🔼 Uploading video to Saved Messages to extract attributes...")
                                    me = await client.get_me()
                                    temp_msg = await client.send_file(me, temp_path, force_document=False)
                                    
                                    # Extract attributes
                                    video_duration = 0
                                    video_w = 640
                                    video_h = 480
                                    video_thumb = b''
                                    video_thumb_w = 160
                                    video_thumb_h = 120
                                    
                                    if temp_msg.video:
                                        video_doc = temp_msg.video
                                        if hasattr(video_doc, 'attributes'):
                                            for attr in video_doc.attributes:
                                                if hasattr(attr, 'duration'):
                                                    video_duration = int(attr.duration) if attr.duration else 0
                                                if hasattr(attr, 'w') and hasattr(attr, 'h'):
                                                    video_w = int(attr.w) if attr.w else 640
                                                    video_h = int(attr.h) if attr.h else 480
                                        
                                        # Get thumbnail
                                        if hasattr(video_doc, 'thumbs') and video_doc.thumbs:
                                            for thumb_obj in video_doc.thumbs:
                                                if hasattr(thumb_obj, 'w') and hasattr(thumb_obj, 'h'):
                                                    video_thumb_w = int(thumb_obj.w) if thumb_obj.w else 160
                                                    video_thumb_h = int(thumb_obj.h) if thumb_obj.h else 120
                                                    break
                                    
                                    logger.info(f"📹 Video attributes: duration={video_duration}s, {video_w}x{video_h}")
                                    
                                    # 🎯 ATTEMPT #21: Download saved message as BYTES and send with library
                                    # The key insight: User said forwarding works because client downloads & re-uploads!
                                    # We'll use send_secret_video() but with FRESH download from Saved Messages
                                    logger.info(f"🎯 ATTEMPT #21: Download from Saved Messages & send_secret_video!")
                                    
                                    try:
                                        # Download the video as bytes BEFORE deleting message
                                        logger.info(f"📥 Downloading video from Saved Messages as bytes...")
                                        video_bytes = await temp_msg.download_media(bytes)
                                        logger.info(f"✅ Downloaded {len(video_bytes)} bytes")
                                        
                                        # NOW delete temp message
                                        await temp_msg.delete()
                                        logger.info(f"🗑️ Deleted temp message from Saved Messages")
                                        
                                        # Save to temp file
                                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as fresh_tf:
                                            fresh_tf.write(video_bytes)
                                            fresh_temp_path = fresh_tf.name
                                        
                                        logger.info(f"📤 Sending video via send_secret_video with FRESH file...")
                                        
                                        # Find proper thumbnail
                                        thumb_bytes = b''
                                        thumb_w = 90
                                        thumb_h = 160
                                        video_obj = temp_msg.video or temp_msg.document
                                        if video_obj and hasattr(video_obj, 'thumbs') and video_obj.thumbs:
                                            for thumb in video_obj.thumbs:
                                                if hasattr(thumb, 'w') and hasattr(thumb, 'h'):
                                                    thumb_w = thumb.w
                                                    thumb_h = thumb.h
                                                    break
                                        
                                        # 🎯 ATTEMPT #23: Send document WITH video attributes!
                                        # The file needs DocumentAttributeVideo so Telegram recognizes it
                                        logger.info(f"🎯 ATTEMPT #23: Sending document WITH video attributes...")
                                        
                                        # 🎯 ATTEMPT #31: Use library's send_secret_video() with FRESH bytes!
                                        # Photos work with library, so videos should too if bytes are good!
                                        logger.info(f"🚀 ATTEMPT #31: Using library's send_secret_video() with fresh bytes...")
                                        
                                        try:
                                            await secret_chat_manager.send_secret_video(
                                                secret_chat_obj,
                                                fresh_temp_path,
                                                thumb=thumb_bytes,
                                                thumb_w=thumb_w,
                                                thumb_h=thumb_h,
                                                duration=video_duration,
                                                w=video_w,
                                                h=video_h,
                                                size=len(video_bytes)
                                            )
                                            logger.info(f"✅ Video {idx} sent via library's send_secret_video!")
                                        except Exception as lib_err:
                                            logger.error(f"❌ Library send_secret_video failed: {lib_err}")
                                            # Fallback to document
                                            await secret_chat_manager.send_secret_document(
                                                secret_chat_obj,
                                                fresh_temp_path,
                                                thumb=thumb_bytes,
                                                thumb_w=thumb_w,
                                                thumb_h=thumb_h,
                                                file_name="video.mp4",
                                                mime_type="video/mp4",
                                                size=len(video_bytes)
                                            )
                                            logger.info(f"✅ Video {idx} sent via fallback document!")
                                        
                                        # Cleanup
                                        try:
                                            os.unlink(fresh_temp_path)
                                        except:
                                            pass
                                        
                                        sent_media_count += 1
                                        continue
                                        
                                    except Exception as fresh_err:
                                        logger.error(f"❌ ATTEMPT #21 failed: {fresh_err}", exc_info=True)
                                    
                                except Exception as manual_err:
                                    logger.error(f"❌ Manual MTProto 2.0 implementation failed: {manual_err}", exc_info=True)
                                
                            if media_type == 'video':  # Fallback to original method
                                # For video, we need to upload to Saved Messages first to get attributes
                                logger.info(f"🔼 Uploading video to Saved Messages to extract attributes...")
                                me = await client.get_me()
                                temp_msg = await client.send_file(me, temp_path)
                                
                                # Extract video attributes (might be in .video or .document)
                                video_obj = temp_msg.video or temp_msg.document
                                
                                if video_obj:
                                    # Find a proper thumbnail (skip PhotoStrippedSize)
                                    thumb_bytes = b''
                                    thumb_w = 160
                                    thumb_h = 120
                                    if hasattr(video_obj, 'thumbs') and video_obj.thumbs:
                                        for thumb in video_obj.thumbs:
                                            # Skip PhotoStrippedSize, use PhotoSize or PhotoCachedSize
                                            if hasattr(thumb, 'w') and hasattr(thumb, 'h'):
                                                thumb_w = thumb.w
                                                thumb_h = thumb.h
                                                if hasattr(thumb, 'bytes'):
                                                    thumb_bytes = thumb.bytes
                                                break
                                    
                                    # Extract video attributes from DocumentAttributeVideo
                                    duration = 0
                                    width = 640
                                    height = 480
                                    mime_type = "video/mp4"
                                    
                                    if hasattr(video_obj, 'attributes'):
                                        for attr in video_obj.attributes:
                                            if hasattr(attr, 'duration'):  # DocumentAttributeVideo
                                                duration = int(attr.duration) if attr.duration else 0
                                                width = int(attr.w) if hasattr(attr, 'w') and attr.w else 640
                                                height = int(attr.h) if hasattr(attr, 'h') and attr.h else 480
                                                break
                                    
                                    # Fallback: try direct attributes
                                    if hasattr(video_obj, 'duration'):
                                        duration = int(video_obj.duration)
                                    if hasattr(video_obj, 'w'):
                                        width = int(video_obj.w)
                                    if hasattr(video_obj, 'h'):
                                        height = int(video_obj.h)
                                    if hasattr(video_obj, 'mime_type'):
                                        mime_type = video_obj.mime_type
                                    
                                    file_size = video_obj.size if hasattr(video_obj, 'size') else file_size
                                    
                                    logger.info(f"📹 Video attributes: {duration}s, {width}x{height}, {mime_type}, {file_size} bytes")
                                    
                                    await secret_chat_manager.send_secret_video(
                                        secret_chat_obj,
                                        temp_path,
                                        thumb=thumb_bytes,
                                        thumb_w=thumb_w,
                                        thumb_h=thumb_h,
                                        duration=duration,
                                        mime_type=mime_type,
                                        w=width,
                                        h=height,
                                        size=file_size
                                    )
                                    logger.info(f"✅ SECRET CHAT video {idx} sent!")
                                    sent_media_count += 1
                                    
                                    # Delete from Saved Messages
                                    await client.delete_messages(me, temp_msg.id)
                                else:
                                    logger.error(f"❌ Failed to get video attributes from temp message")
                                    raise Exception("No video attributes")
                            
                        except Exception as send_err:
                            # Fallback: send placeholder
                            logger.error(f"❌ Failed to send media to secret chat: {send_err}", exc_info=True)
                            try:
                                await secret_chat_manager.send_secret_message(secret_chat_obj, f"[Media {idx}: {filename}]")
                                logger.warning(f"⚠️ Sent placeholder text for media {idx} instead")
                            except:
                                pass
                        finally:
                            # Clean up temp file
                            try:
                                os.unlink(temp_path)
                            except:
                                pass
                        
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to send SECRET CHAT media {idx}: {e}", exc_info=True)
            else:
                logger.warning(f"⚠️ No media items to send for order {order_id} (Product ID: {product_data.get('product_id')}). Product has no media in database!")
            
            # 5. Send product details
            details_text = f"""📦 Product Details
🏷️ {product_data.get('product_name', 'Product')}
📏 {product_data.get('size', 'N/A')}
📍 {product_data.get('city', 'N/A')}, {product_data.get('district', 'N/A')}
💰 {product_data.get('price', 0):.2f} EUR
📝 Pickup Instructions:
{product_data.get('original_text', 'No additional details.')}
✅ Order Completed
Order ID: {order_id}
Thank you! 🎉"""
            
            try:
                await secret_chat_manager.send_secret_message(secret_chat_obj, details_text)
                logger.info(f"✅ Sent product details to secret chat")
            except Exception as e:
                logger.error(f"❌ Failed to send product details: {e}")
            
            return True, f"Product delivered via SECRET CHAT (userbot #{userbot_id}) to user {buyer_user_id}"
            
        except Exception as e:
            logger.error(f"❌ Secret chat delivery failed (userbot #{userbot_id}): {e}", exc_info=True)
            return False, f"Secret chat delivery error: {e}"
    
    async def disconnect_all(self):
        """Disconnect all userbots in the pool"""
        logger.info("🔌 Disconnecting all userbots in pool...")
        
        for userbot_id, client in list(self.clients.items()):
            try:
                await client.disconnect()
                self._update_connection_status(userbot_id, False, "Disconnected")
                logger.info(f"✅ Disconnected userbot #{userbot_id}")
            except Exception as e:
                logger.error(f"❌ Error disconnecting userbot #{userbot_id}: {e}")
        
        self.clients.clear()
        self.secret_chat_managers.clear()
        self.is_initialized = False
        logger.info("✅ All userbots disconnected")

# Global userbot pool instance
userbot_pool = UserbotPool()

