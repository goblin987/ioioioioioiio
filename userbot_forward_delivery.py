"""
Forward-Based Secret Chat Delivery
Strategy: Bot sends media to private channel → Userbot forwards to secret chat
This preserves video quality without re-encoding!
"""

import logging
import asyncio
import os
import tempfile
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.tl.types import InputChannel
from telethon_secret_chat import SecretChatManager

logger = logging.getLogger(__name__)

# Delivery channel ID (will be set in admin panel)
DELIVERY_CHANNEL_ID = None  # Admin will create and set this

async def setup_delivery_channel(client: TelegramClient, bot_username: str) -> int:
    """
    Create a private delivery channel and add bot + userbot
    Returns: channel_id
    """
    try:
        # Create private channel
        result = await client(functions.channels.CreateChannelRequest(
            title=f"🔐 Secret Delivery Channel",
            about="Private channel for forwarding media to secret chats",
            megagroup=False  # Regular channel, not supergroup
        ))
        
        channel = result.chats[0]
        channel_id = channel.id
        logger.info(f"✅ Created delivery channel: {channel_id}")
        
        # Add bot to channel as admin
        await client(functions.channels.InviteToChannelRequest(
            channel=channel,
            users=[bot_username]
        ))
        
        # Make bot admin so it can post
        await client(functions.channels.EditAdminRequest(
            channel=channel,
            user_id=bot_username,
            admin_rights=types.ChatAdminRights(
                post_messages=True,
                edit_messages=True,
                delete_messages=True
            ),
            rank="Delivery Bot"
        ))
        
        logger.info(f"✅ Added {bot_username} as admin to channel {channel_id}")
        return channel_id
        
    except Exception as e:
        logger.error(f"❌ Failed to setup delivery channel: {e}")
        raise


async def forward_to_secret_chat(
    client: TelegramClient,
    secret_chat_manager: SecretChatManager,
    secret_chat_obj,
    channel_id: int,
    message_ids: List[int],
    buyer_username: str
) -> bool:
    """
    Forward messages from delivery channel to secret chat
    This preserves video quality!
    """
    try:
        logger.info(f"📤 Forwarding {len(message_ids)} messages from channel to secret chat...")
        
        # Get channel entity
        channel = await client.get_entity(channel_id)
        
        # Get messages from channel
        messages = await client.get_messages(channel, ids=message_ids)
        
        # Forward each message to secret chat
        for idx, msg in enumerate(messages, 1):
            try:
                if msg.photo:
                    logger.info(f"📸 Forwarding photo {idx} to secret chat...")
                    # Download from channel
                    photo_bytes = await client.download_media(msg.photo, file=bytes)
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                        temp_file.write(photo_bytes)
                        temp_path = temp_file.name
                    
                    try:
                        # Send to secret chat
                        await secret_chat_manager.send_secret_photo(
                            secret_chat_obj,
                            temp_path,
                            thumb=b'',
                            thumb_w=160,
                            thumb_h=120,
                            w=1280,
                            h=720,
                            size=len(photo_bytes)
                        )
                        logger.info(f"✅ Photo {idx} forwarded to secret chat")
                    finally:
                        os.unlink(temp_path)
                        
                elif msg.video or msg.document:
                    logger.info(f"🎥 Forwarding video {idx} to secret chat...")
                    # Download from channel (this is the ORIGINAL video, not re-encoded!)
                    video_bytes = await client.download_media(msg, file=bytes)
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                        temp_file.write(video_bytes)
                        temp_path = temp_file.name
                    
                    try:
                        # Get video attributes
                        video_doc = msg.video or msg.document
                        from telethon.tl.types import DocumentAttributeVideo
                        
                        duration = 0
                        w = 0
                        h = 0
                        if hasattr(video_doc, 'attributes'):
                            for attr in video_doc.attributes:
                                if isinstance(attr, DocumentAttributeVideo):
                                    duration = int(attr.duration) if attr.duration else 0
                                    w = int(attr.w) if attr.w else 0
                                    h = int(attr.h) if attr.h else 0
                                    break
                        
                        # Send to secret chat - THIS SHOULD WORK WITHOUT CORRUPTION!
                        await secret_chat_manager.send_secret_video(
                            secret_chat_obj,
                            temp_path,
                            thumb=b'',
                            thumb_w=160,
                            thumb_h=120,
                            duration=duration,
                            mime_type='video/mp4',
                            w=w,
                            h=h,
                            size=len(video_bytes)
                        )
                        logger.info(f"✅ Video {idx} forwarded to secret chat")
                    finally:
                        os.unlink(temp_path)
                        
                elif msg.text:
                    logger.info(f"💬 Forwarding text {idx} to secret chat...")
                    await secret_chat_manager.send_secret_message(secret_chat_obj, msg.text)
                    logger.info(f"✅ Text {idx} forwarded to secret chat")
                
                await asyncio.sleep(0.5)
                
            except Exception as msg_err:
                logger.error(f"❌ Failed to forward message {idx}: {msg_err}")
                continue
        
        logger.info(f"✅ Forwarded {len(messages)} messages to secret chat")
        
        # Clean up channel messages
        try:
            await client.delete_messages(channel, message_ids)
            logger.info(f"🗑️ Cleaned up {len(message_ids)} messages from delivery channel")
        except Exception as del_err:
            logger.warning(f"⚠️ Could not delete channel messages: {del_err}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Forward to secret chat failed: {e}", exc_info=True)
        return False

