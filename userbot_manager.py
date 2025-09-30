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
            await update_connection_status(False, "Pyrogram not installed")
            return False
        
        if self.is_initializing:
            logger.warning("⚠️ Userbot is already initializing")
            return False
        
        if not userbot_config.is_configured():
            logger.warning("⚠️ Userbot not configured")
            await update_connection_status(False, "Not configured")
            return False
        
        self.is_initializing = True
        
        try:
            logger.info("🔧 Initializing userbot...")
            
            api_id = userbot_config.api_id
            api_hash = userbot_config.api_hash
            
            if not api_id or not api_hash:
                logger.error("❌ Missing API credentials")
                await update_connection_status(False, "Missing API credentials")
                return False
            
            # Get session string from database
            session_string = get_session_string()
            
            # Create Pyrogram client
            self.client = Client(
                name="userbot_session",
                api_id=int(api_id),
                api_hash=api_hash,
                session_string=session_string,
                workdir="./userbot_data",
                in_memory=True
            )
            
            # Connect to Telegram
            await self.client.start()
            
            # Verify connection
            me = await self.client.get_me()
            logger.info(f"✅ Userbot connected as @{me.username or me.first_name} (ID: {me.id})")
            
            self.is_connected = True
            await update_connection_status(True, f"Connected as @{me.username or me.first_name}")
            
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
            await update_connection_status(False, "Session expired")
            return False
            
        except (UserDeactivated, UserDeactivatedBan):
            logger.error("❌ User account deactivated or banned")
            await update_connection_status(False, "Account deactivated")
            return False
            
        except ApiIdInvalid:
            logger.error("❌ Invalid API ID or Hash")
            await update_connection_status(False, "Invalid API credentials")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error initializing userbot: {e}", exc_info=True)
            await update_connection_status(False, f"Error: {str(e)[:100]}")
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
                await self.client.stop()
                logger.info("✅ Userbot disconnected")
            
            self.is_connected = False
            await update_connection_status(False, "Manually disconnected")
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
                    await update_connection_status(False, "Connection lost")
                    
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
            
            # Stop temporary client
            await self.client.stop()
            
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

# Global userbot manager instance
userbot_manager = UserbotManager()

