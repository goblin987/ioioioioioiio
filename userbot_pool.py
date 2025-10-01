"""
Userbot Pool Manager
Manages multiple Telethon userbots for secret chat delivery with load balancing
"""

import logging
import asyncio
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
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
            
            # 2. Create secret chat
            secret_chat_obj = None
            try:
                logger.info(f"🔐 Starting secret chat with user {user_entity.id} (@{buyer_username or 'N/A'})...")
                secret_chat_obj = await secret_chat_manager.start_secret_chat(user_entity)
                logger.info(f"✅ Secret chat started successfully!")
                # Wait for encryption handshake
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Failed to start secret chat: {e}")
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
                        media_file = io.BytesIO(media_binary)
                        media_file.name = filename
                        
                        logger.info(f"📤 Sending SECRET CHAT media {idx}/{len(media_binary_items)} ({len(media_binary)} bytes) type: {media_type}...")
                        
                        # Use Telethon's send_file method directly with the secret chat
                        # The secret_chat_obj should be the chat entity
                        try:
                            await client.send_file(
                                secret_chat_obj,
                                media_file,
                                caption=f"📦 Item {idx}/{len(media_binary_items)}",
                                force_document=(media_type not in ['photo', 'video'])
                            )
                            sent_media_count += 1
                            logger.info(f"✅ SECRET CHAT media {idx} sent successfully")
                        except Exception as send_err:
                            logger.error(f"❌ Failed to send media via Telethon send_file: {send_err}")
                            # Fallback: try sending as bytes directly
                            media_file.seek(0)
                            await secret_chat_manager.send_secret_message(secret_chat_obj, f"[Media {idx}: {filename}]")
                            logger.warning(f"⚠️ Sent placeholder text for media {idx} instead")
                        
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

