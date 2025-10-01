"""
🚀 USERBOT DELIVERY VIA FORWARDING STRATEGY

This is the PROPER way to deliver media via secret chat:
1. Bot sends media to a private delivery channel
2. Userbot forwards from channel to buyer's secret chat
3. Clean up channel message after delivery

WHY THIS WORKS:
- No file encryption/decryption needed
- Media stays intact (no corruption)
- Telegram handles all the secret chat encryption internally
- Much simpler and more reliable than manual encryption
"""

import logging
from typing import List, Dict, Optional
from telethon import TelegramClient

logger = logging.getLogger(__name__)

class ForwardDeliverySystem:
    """Handles media delivery by forwarding from a private channel"""
    
    def __init__(self):
        self.delivery_channel_id: Optional[int] = None
        self.initialized = False
    
    async def initialize(self, bot, userbot_client: TelegramClient):
        """
        Initialize the delivery system
        
        Args:
            bot: The main PTB bot instance
            userbot_client: The Telethon userbot client
        """
        try:
            logger.info("🔄 Initializing forward delivery system...")
            
            # Get or create private delivery channel
            self.delivery_channel_id = await self._get_or_create_delivery_channel(
                bot, userbot_client
            )
            
            if self.delivery_channel_id:
                logger.info(f"✅ Delivery channel ready: {self.delivery_channel_id}")
                self.initialized = True
                return True
            else:
                logger.error("❌ Failed to set up delivery channel")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize forward delivery: {e}", exc_info=True)
            return False
    
    async def _get_or_create_delivery_channel(
        self, 
        bot, 
        userbot_client: TelegramClient
    ) -> Optional[int]:
        """
        Get existing delivery channel ID from DB or create new one
        
        Returns:
            Channel ID (as negative int) or None
        """
        try:
            from db import get_connection
            
            # Check if we have a delivery channel in system_settings
            with get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT setting_value 
                    FROM system_settings 
                    WHERE setting_key = 'delivery_channel_id'
                """)
                row = c.fetchone()
                
                if row and row[0]:
                    channel_id = int(row[0])
                    logger.info(f"📋 Found existing delivery channel: {channel_id}")
                    
                    # Verify channel exists and userbot has access
                    try:
                        channel = await userbot_client.get_entity(channel_id)
                        logger.info(f"✅ Delivery channel verified: {channel.title}")
                        return channel_id
                    except Exception as verify_err:
                        logger.warning(f"⚠️ Stored channel not accessible: {verify_err}")
                        # Will create new one below
                
                # Create new private delivery channel
                logger.info("📝 Creating new private delivery channel...")
                
                # Use userbot to create channel
                from telethon.tl.functions.channels import CreateChannelRequest
                
                result = await userbot_client(CreateChannelRequest(
                    title="🔐 Secret Delivery",
                    about="Private channel for secure product delivery",
                    megagroup=False  # Regular channel, not supergroup
                ))
                
                channel = result.chats[0]
                channel_id = -1 * int(f"100{channel.id}")  # Convert to negative ID
                
                logger.info(f"✅ Created delivery channel: {channel.title} (ID: {channel_id})")
                
                # Add bot to channel as admin
                bot_user = await bot.get_me()
                bot_username = bot_user.username
                
                from telethon.tl.functions.channels import InviteToChannelRequest
                await userbot_client(InviteToChannelRequest(
                    channel=channel,
                    users=[bot_username]
                ))
                
                logger.info(f"✅ Added bot @{bot_username} to delivery channel")
                
                # Save channel ID to DB
                c.execute("""
                    INSERT INTO system_settings (setting_key, setting_value)
                    VALUES ('delivery_channel_id', %s)
                    ON CONFLICT (setting_key) 
                    DO UPDATE SET setting_value = EXCLUDED.setting_value
                """, (str(channel_id),))
                conn.commit()
                
                logger.info(f"✅ Delivery channel saved to DB: {channel_id}")
                return channel_id
                
        except Exception as e:
            logger.error(f"❌ Failed to get/create delivery channel: {e}", exc_info=True)
            return None
    
    async def deliver_via_forward(
        self,
        bot,
        userbot_client: TelegramClient,
        buyer_user_id: int,
        buyer_username: Optional[str],
        media_items: List[Dict],
        product_name: str,
        product_description: str
    ) -> bool:
        """
        Deliver product by forwarding from delivery channel to secret chat
        
        Args:
            bot: Main PTB bot
            userbot_client: Telethon userbot
            buyer_user_id: Buyer's Telegram user ID
            buyer_username: Buyer's username (with @)
            media_items: List of media dicts with 'media_binary' and 'media_type'
            product_name: Product name for notification
            product_description: Product description
            
        Returns:
            True if delivery successful, False otherwise
        """
        if not self.initialized or not self.delivery_channel_id:
            logger.error("❌ Forward delivery system not initialized!")
            return False
        
        sent_message_ids = []
        
        try:
            logger.info(f"📦 Starting forward delivery to user {buyer_user_id} ({buyer_username})")
            
            # Step 1: Get or create secret chat
            from telethon_secret_chat import SecretChatManager
            secret_chat_manager = SecretChatManager(userbot_client)
            
            # Get user entity
            user_entity = await userbot_client.get_entity(buyer_username or buyer_user_id)
            logger.info(f"✅ Got user entity: {user_entity.id}")
            
            # Start secret chat
            secret_chat_obj = await secret_chat_manager.start_secret_chat(user_entity)
            logger.info(f"✅ Secret chat created/retrieved")
            
            # Send initial notification to secret chat
            await secret_chat_manager.send_secret_message(
                secret_chat_obj,
                f"🎁 **Your Purchase**\n\n"
                f"**Product:** {product_name}\n"
                f"**Description:** {product_description}\n\n"
                f"📦 Sending {len(media_items)} media file(s)..."
            )
            logger.info(f"✅ Sent notification to secret chat")
            
            # Step 2: Bot sends media to delivery channel
            logger.info(f"📤 Bot sending {len(media_items)} media items to delivery channel...")
            
            import tempfile
            import os
            
            for idx, media in enumerate(media_items, 1):
                media_binary = media.get('media_binary')
                media_type = media.get('media_type', 'photo')
                filename = media.get('filename', f'media_{idx}')
                
                if not media_binary:
                    logger.warning(f"⚠️ No binary data for media {idx}, skipping")
                    continue
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                    temp_file.write(media_binary)
                    temp_path = temp_file.name
                
                try:
                    # Bot sends to delivery channel
                    if media_type == 'photo':
                        msg = await bot.send_photo(
                            chat_id=self.delivery_channel_id,
                            photo=open(temp_path, 'rb')
                        )
                    elif media_type == 'video':
                        msg = await bot.send_video(
                            chat_id=self.delivery_channel_id,
                            video=open(temp_path, 'rb')
                        )
                    else:
                        msg = await bot.send_document(
                            chat_id=self.delivery_channel_id,
                            document=open(temp_path, 'rb')
                        )
                    
                    sent_message_ids.append(msg.message_id)
                    logger.info(f"✅ Bot sent media {idx} to channel (msg_id: {msg.message_id})")
                    
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
            
            if not sent_message_ids:
                logger.error("❌ No media was sent to delivery channel!")
                return False
            
            logger.info(f"✅ All {len(sent_message_ids)} media items sent to delivery channel")
            
            # Step 3: Userbot forwards from channel to secret chat
            logger.info(f"🔄 Userbot forwarding {len(sent_message_ids)} messages to secret chat...")
            
            # Get channel entity
            channel_entity = await userbot_client.get_entity(self.delivery_channel_id)
            
            # Forward each message to secret chat
            for msg_id in sent_message_ids:
                try:
                    # Get message from channel
                    message = await userbot_client.get_messages(channel_entity, ids=msg_id)
                    
                    if not message:
                        logger.warning(f"⚠️ Could not get message {msg_id} from channel")
                        continue
                    
                    # Send media to secret chat (Telethon will handle encryption)
                    if message.photo:
                        # Download and re-send (forwarding doesn't work in secret chats)
                        photo_bytes = await message.download_media(bytes)
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tf:
                            tf.write(photo_bytes)
                            tf_path = tf.name
                        
                        try:
                            await userbot_client.send_file(
                                secret_chat_obj,
                                tf_path
                            )
                            logger.info(f"✅ Forwarded photo {msg_id} to secret chat")
                        finally:
                            try:
                                os.unlink(tf_path)
                            except:
                                pass
                                
                    elif message.video or message.document:
                        # Download and re-send
                        file_bytes = await message.download_media(bytes)
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
                            tf.write(file_bytes)
                            tf_path = tf.name
                        
                        try:
                            await userbot_client.send_file(
                                secret_chat_obj,
                                tf_path
                            )
                            logger.info(f"✅ Forwarded video {msg_id} to secret chat")
                        finally:
                            try:
                                os.unlink(tf_path)
                            except:
                                pass
                    
                except Exception as forward_err:
                    logger.error(f"❌ Failed to forward message {msg_id}: {forward_err}", exc_info=True)
            
            # Step 4: Clean up delivery channel
            logger.info(f"🧹 Cleaning up delivery channel...")
            await userbot_client.delete_messages(channel_entity, sent_message_ids)
            logger.info(f"✅ Deleted {len(sent_message_ids)} messages from delivery channel")
            
            # Final notification
            await secret_chat_manager.send_secret_message(
                secret_chat_obj,
                f"✅ **Delivery Complete!**\n\n"
                f"All files have been securely delivered.\n"
                f"Thank you for your purchase!"
            )
            
            logger.info(f"✅ FORWARD DELIVERY SUCCESSFUL!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Forward delivery failed: {e}", exc_info=True)
            
            # Clean up any sent messages on failure
            if sent_message_ids and self.delivery_channel_id:
                try:
                    channel_entity = await userbot_client.get_entity(self.delivery_channel_id)
                    await userbot_client.delete_messages(channel_entity, sent_message_ids)
                    logger.info(f"🧹 Cleaned up {len(sent_message_ids)} failed delivery messages")
                except:
                    pass
            
            return False


# Global instance
forward_delivery_system = ForwardDeliverySystem()
