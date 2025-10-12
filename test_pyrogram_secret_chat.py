"""
Test if Pyrogram's secret chat video sending works better than Telethon
This is Solution #2 from the guide - the easiest path forward
"""

import asyncio
import logging
import os
from pyrogram import Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# You'll need to fill these in from your environment variables
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_STRING = os.getenv("USERBOT_SESSION_STRING_1", "")

async def test_pyrogram_secret_chat():
    """
    Test if Pyrogram can send working videos to secret chats
    """
    
    if not API_ID or not API_HASH:
        print("❌ Need TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables")
        return
    
    app = Client(
        "test_pyrogram",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING if SESSION_STRING else None
    )
    
    async with app:
        logger.info("✅ Pyrogram client connected!")
        
        # Test: Can Pyrogram create secret chats?
        try:
            # Get your own user to test
            me = await app.get_me()
            logger.info(f"👤 Logged in as: {me.first_name} (@{me.username})")
            
            # Check if Pyrogram supports secret chats
            if hasattr(app, 'create_secret_chat'):
                logger.info("✅ Pyrogram DOES support secret chats!")
                logger.info("📝 To test: Call create_secret_chat(user_id) and send_video()")
            else:
                logger.error("❌ Pyrogram does NOT support secret chats natively")
                logger.info("   This means we need Solution #1 (fix tgcrypto) or Solution #3 (proxy)")
            
        except Exception as e:
            logger.error(f"❌ Error testing Pyrogram: {e}")

if __name__ == "__main__":
    asyncio.run(test_pyrogram_secret_chat())

