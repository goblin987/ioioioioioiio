"""
Pyrogram-based Secret Chat Implementation
Testing if tg-secret library works better than telethon-secret-chat
"""

import asyncio
import logging
import os
import tempfile
from typing import Dict, List, Optional, Tuple
from pyrogram import Client
from tg_secret import TelegramSecretClient
from tg_secret.client_adapters.pyrogram_adapter import PyrogramClientAdapter

logger = logging.getLogger(__name__)

class PyrogramUserbotPool:
    """
    Pyrogram-based userbot pool for secret chat delivery
    Uses tg-secret library which might have better video support
    """
    
    def __init__(self):
        self.pyrogram_clients: Dict[int, Client] = {}
        self.secret_clients: Dict[int, TelegramSecretClient] = {}
        self.current_userbot_index = 0
        
    async def add_userbot(self, userbot_id: int, api_id: int, api_hash: str, session_string: str):
        """Add a Pyrogram userbot to the pool"""
        try:
            logger.info(f"🔧 Adding Pyrogram userbot #{userbot_id}...")
            
            # Create Pyrogram client
            client = Client(
                f"pyrogram_userbot_{userbot_id}",
                api_id=api_id,
                api_hash=api_hash,
                session_string=session_string
            )
            
            # Start the client
            await client.start()
            logger.info(f"✅ Pyrogram userbot #{userbot_id} started")
            
            # Create secret chat client
            secret_client = TelegramSecretClient(PyrogramClientAdapter(client))
            
            self.pyrogram_clients[userbot_id] = client
            self.secret_clients[userbot_id] = secret_client
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add Pyrogram userbot #{userbot_id}: {e}")
            return False
    
    async def deliver_via_pyrogram_secret_chat(
        self,
        buyer_user_id: int,
        buyer_username: Optional[str],
        product_data: dict,
        media_binary_items: List[Dict],
        order_id: str
    ) -> Tuple[bool, str]:
        """
        Deliver media via Pyrogram + tg-secret
        """
        
        if not self.secret_clients:
            return False, "No Pyrogram userbots available"
        
        # Get next available userbot
        userbot_id = list(self.secret_clients.keys())[self.current_userbot_index % len(self.secret_clients)]
        self.current_userbot_index += 1
        
        client = self.pyrogram_clients[userbot_id]
        secret_client = self.secret_clients[userbot_id]
        
        try:
            logger.info(f"🔐 Starting PYROGRAM secret chat delivery to user {buyer_user_id}")
            
            # Step 1: Request encryption (create secret chat)
            logger.info(f"🔐 Requesting encryption with user {buyer_user_id}...")
            encryption_response = await secret_client.request_encryption(buyer_user_id)
            
            if not encryption_response:
                return False, "Failed to create secret chat with Pyrogram"
            
            secret_chat_id = encryption_response.id
            logger.info(f"✅ Pyrogram secret chat created! ID: {secret_chat_id}")
            
            await asyncio.sleep(2)
            
            # Step 2: Send notification
            notification_text = f"""🔐 ENCRYPTED DELIVERY (via Pyrogram)
📦 Order #{order_id}
🏷️ {product_data.get('product_name', 'Product')}
💰 {product_data.get('price', 0):.2f} EUR
⏬ Receiving media..."""
            
            try:
                await secret_client.send_message(
                    chat_id=secret_chat_id,
                    text=notification_text
                )
                logger.info(f"✅ Sent notification via Pyrogram")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Failed to send notification: {e}")
            
            # Step 3: Send media
            sent_media_count = 0
            if media_binary_items and len(media_binary_items) > 0:
                logger.info(f"📂 Sending {len(media_binary_items)} media items via PYROGRAM SECRET CHAT...")
                
                for idx, media_item in enumerate(media_binary_items, 1):
                    media_type = media_item['media_type']
                    media_binary = media_item['media_binary']
                    filename = media_item['filename']
                    
                    try:
                        logger.info(f"📤 Sending media {idx}/{len(media_binary_items)} ({len(media_binary)} bytes) type: {media_type}...")
                        
                        # Save to temp file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                            temp_file.write(media_binary)
                            temp_path = temp_file.name
                        
                        try:
                            if media_type == 'photo':
                                # Send photo
                                await secret_client.send_photo(
                                    chat_id=secret_chat_id,
                                    file_path=temp_path
                                )
                                logger.info(f"✅ PYROGRAM photo {idx} sent!")
                                sent_media_count += 1
                                
                            elif media_type == 'video':
                                # 🎬 THE CRITICAL TEST: Send video via Pyrogram tg-secret
                                logger.critical(f"🎬 PYROGRAM TEST: Sending video via tg-secret...")
                                
                                await secret_client.send_document(
                                    chat_id=secret_chat_id,
                                    file_path=temp_path,
                                    caption="🎬 Video for your order"
                                )
                                logger.info(f"✅ PYROGRAM video {idx} sent!")
                                logger.critical(f"🎯 CRITICAL: Check if video is PLAYABLE (not corrupted)!")
                                sent_media_count += 1
                                
                        finally:
                            try:
                                os.unlink(temp_path)
                            except:
                                pass
                                
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to send media {idx}: {e}")
                        continue
            
            logger.info(f"✅ Pyrogram delivery complete! Sent {sent_media_count}/{len(media_binary_items)} items")
            return True, f"Delivered via Pyrogram secret chat"
            
        except Exception as e:
            logger.error(f"❌ Pyrogram secret chat delivery failed: {e}", exc_info=True)
            return False, f"Pyrogram delivery error: {e}"
    
    async def stop_all(self):
        """Stop all Pyrogram clients"""
        for userbot_id, client in self.pyrogram_clients.items():
            try:
                await client.stop()
                logger.info(f"✅ Pyrogram userbot #{userbot_id} stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping Pyrogram userbot #{userbot_id}: {e}")


# Global instance
pyrogram_pool = PyrogramUserbotPool()

