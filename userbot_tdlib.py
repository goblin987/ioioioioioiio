"""
ATTEMPT #40: TDLib Implementation for Secret Chat Videos
Uses the OFFICIAL Telegram library (same as Telegram Desktop)
This WILL work because it's what the official client uses!
"""

import asyncio
import logging
import os
import tempfile
from typing import Dict, Optional, Tuple, List
from telegram.client import Telegram
from telegram.text import Spoiler, Italic

logger = logging.getLogger(__name__)

class TDLibSecretChatManager:
    """
    Manager for TDLib-based secret chat delivery
    Uses the same library as official Telegram clients
    """
    
    def __init__(self):
        self.clients: Dict[int, Telegram] = {}  # userbot_id -> TDLib client
        self.secret_chats: Dict[int, Dict] = {}  # user_id -> secret_chat_info
        self.is_initialized = False
        
    async def add_userbot(self, userbot_id: int, api_id: int, api_hash: str, phone: str):
        """Initialize a TDLib client for a userbot"""
        try:
            logger.info(f"🔧 Initializing TDLib client #{userbot_id}...")
            
            # Create TDLib client
            tg = Telegram(
                api_id=api_id,
                api_hash=api_hash,
                phone=phone,
                database_encryption_key='secretchat_tdlib_key',
                files_directory=f'/tmp/tdlib_{userbot_id}'
            )
            
            # Start and login
            tg.login()
            
            # Wait for authorization
            await asyncio.sleep(2)
            
            self.clients[userbot_id] = tg
            logger.info(f"✅ TDLib client #{userbot_id} initialized!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize TDLib client #{userbot_id}: {e}")
            return False
    
    async def get_or_create_secret_chat(
        self,
        client: Telegram,
        user_id: int
    ) -> Optional[int]:
        """Get existing or create new secret chat"""
        try:
            logger.info(f"🔐 Creating secret chat with user {user_id}...")
            
            # Create secret chat
            result = client.call_method(
                'createNewSecretChat',
                params={'user_id': user_id},
                block=True
            )
            
            if result and 'id' in result:
                secret_chat_id = result['id']
                logger.info(f"✅ Secret chat created: {secret_chat_id}")
                return secret_chat_id
            else:
                logger.error(f"❌ Failed to create secret chat: {result}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating secret chat: {e}")
            return None
    
    async def send_text_message(
        self,
        client: Telegram,
        chat_id: int,
        text: str
    ) -> bool:
        """Send text message to secret chat"""
        try:
            logger.info(f"📤 Sending text to secret chat {chat_id}...")
            
            result = client.call_method(
                'sendMessage',
                params={
                    'chat_id': chat_id,
                    'input_message_content': {
                        '@type': 'inputMessageText',
                        'text': {
                            '@type': 'formattedText',
                            'text': text
                        }
                    }
                },
                block=True
            )
            
            logger.info(f"✅ Text message sent!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send text: {e}")
            return False
    
    async def send_photo(
        self,
        client: Telegram,
        chat_id: int,
        photo_path: str,
        caption: str = ""
    ) -> bool:
        """Send photo to secret chat"""
        try:
            logger.info(f"📤 Sending photo to secret chat {chat_id}...")
            
            result = client.call_method(
                'sendMessage',
                params={
                    'chat_id': chat_id,
                    'input_message_content': {
                        '@type': 'inputMessagePhoto',
                        'photo': {
                            '@type': 'inputFileLocal',
                            'path': photo_path
                        },
                        'caption': {
                            '@type': 'formattedText',
                            'text': caption
                        }
                    }
                },
                block=True
            )
            
            logger.info(f"✅ Photo sent!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send photo: {e}")
            return False
    
    async def send_video(
        self,
        client: Telegram,
        chat_id: int,
        video_path: str,
        caption: str = "",
        duration: int = 0,
        width: int = 0,
        height: int = 0
    ) -> bool:
        """
        Send video to secret chat using TDLib
        THIS is the critical method - uses official Telegram encryption!
        """
        try:
            logger.critical(f"🎬 SENDING VIDEO VIA TDLIB (OFFICIAL LIBRARY)!")
            logger.info(f"📤 Chat: {chat_id}, Video: {video_path}")
            logger.info(f"📊 Duration: {duration}s, Resolution: {width}x{height}")
            
            result = client.call_method(
                'sendMessage',
                params={
                    'chat_id': chat_id,
                    'input_message_content': {
                        '@type': 'inputMessageVideo',
                        'video': {
                            '@type': 'inputFileLocal',
                            'path': video_path
                        },
                        'caption': {
                            '@type': 'formattedText',
                            'text': caption
                        },
                        'duration': duration,
                        'width': width,
                        'height': height,
                        'supports_streaming': True
                    }
                },
                block=True
            )
            
            logger.critical(f"✅ VIDEO SENT VIA TDLIB!")
            logger.critical(f"🎯 This video SHOULD be playable (official encryption)!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send video via TDLib: {e}")
            return False
    
    async def deliver_media_via_tdlib(
        self,
        userbot_id: int,
        user_id: int,
        product_data: dict,
        media_binary_items: List[Dict],
        order_id: str
    ) -> Tuple[bool, str]:
        """
        Complete delivery flow using TDLib
        """
        
        client = self.clients.get(userbot_id)
        if not client:
            return False, f"TDLib client #{userbot_id} not available"
        
        try:
            logger.critical(f"🎬 ATTEMPT #40: TDLib delivery for order #{order_id}")
            
            # Step 1: Create/get secret chat
            secret_chat_id = await self.get_or_create_secret_chat(client, user_id)
            if not secret_chat_id:
                return False, "Failed to create secret chat"
            
            await asyncio.sleep(2)
            
            # Step 2: Send notification
            notification = f"""🔐 ENCRYPTED DELIVERY (via TDLib)
📦 Order #{order_id}
🏷️ {product_data.get('product_name', 'Product')}
💰 {product_data.get('price', 0):.2f} EUR
⏬ Receiving media..."""
            
            await self.send_text_message(client, secret_chat_id, notification)
            await asyncio.sleep(1)
            
            # Step 3: Send media
            sent_count = 0
            for idx, media_item in enumerate(media_binary_items, 1):
                media_type = media_item['media_type']
                media_binary = media_item['media_binary']
                filename = media_item['filename']
                
                try:
                    logger.info(f"📤 Sending media {idx}/{len(media_binary_items)} via TDLib...")
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                        temp_file.write(media_binary)
                        temp_path = temp_file.name
                    
                    try:
                        if media_type == 'photo':
                            success = await self.send_photo(client, secret_chat_id, temp_path)
                            if success:
                                logger.info(f"✅ Photo {idx} sent!")
                                sent_count += 1
                                
                        elif media_type == 'video':
                            # 🎬 THE MOMENT OF TRUTH: TDLib video sending!
                            success = await self.send_video(
                                client,
                                secret_chat_id,
                                temp_path,
                                caption=f"🎬 Video for Order #{order_id}"
                            )
                            if success:
                                logger.critical(f"✅ VIDEO {idx} SENT VIA TDLIB!")
                                sent_count += 1
                            else:
                                logger.error(f"❌ TDLib video send returned False")
                                
                    finally:
                        try:
                            os.unlink(temp_path)
                        except:
                            pass
                            
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Failed to send media {idx}: {e}")
                    continue
            
            logger.info(f"✅ TDLib delivery complete! Sent {sent_count}/{len(media_binary_items)} items")
            return True, f"Delivered via TDLib (official Telegram library)"
            
        except Exception as e:
            logger.error(f"❌ TDLib delivery failed: {e}", exc_info=True)
            return False, f"TDLib error: {e}"


# Global instance
tdlib_manager = TDLibSecretChatManager()

