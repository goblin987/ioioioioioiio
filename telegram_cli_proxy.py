"""
ATTEMPT #40: Proxy through official Telegram CLI
The official Telegram client CAN send working videos to secret chats
We'll use telegram-cli or tg (Telegram CLI) to do the actual sending
"""

import asyncio
import logging
import os
import tempfile
import json
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class TelegramCLIProxy:
    """
    Proxy that uses official Telegram CLI to send videos to secret chats
    This works because the official client has working video encryption
    """
    
    def __init__(self, cli_path: str = "/usr/local/bin/telegram-cli"):
        self.cli_path = cli_path
        self.is_available = False
        
    async def check_availability(self) -> bool:
        """Check if telegram-cli is installed and working"""
        try:
            process = await asyncio.create_subprocess_exec(
                self.cli_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.is_available = True
                logger.info(f"✅ Telegram CLI available: {stdout.decode().strip()}")
                return True
            else:
                logger.warning(f"⚠️ Telegram CLI not available: {stderr.decode()}")
                return False
                
        except FileNotFoundError:
            logger.warning(f"⚠️ Telegram CLI not found at {self.cli_path}")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking Telegram CLI: {e}")
            return False
    
    async def send_video_to_secret_chat(
        self,
        phone_number: str,
        user_identifier: str,  # username or phone
        video_path: str,
        caption: str = ""
    ) -> Tuple[bool, str]:
        """
        Send video to secret chat using Telegram CLI
        
        Args:
            phone_number: Your phone number (for authentication)
            user_identifier: Target user's username or phone
            video_path: Path to video file
            caption: Video caption
            
        Returns:
            (success, message)
        """
        
        if not self.is_available:
            return False, "Telegram CLI not available"
        
        try:
            logger.info(f"🔐 Sending video via Telegram CLI to {user_identifier}...")
            
            # Create command script
            commands = [
                f"secret_chat {user_identifier}",
                "sleep 2",
                f"send_video @{user_identifier} {video_path}",
                "quit"
            ]
            
            # Write commands to temp file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write('\n'.join(commands))
                script_path = f.name
            
            try:
                # Run telegram-cli with script
                process = await asyncio.create_subprocess_exec(
                    self.cli_path,
                    "-k", "server.pub",  # Server public key
                    "-W",  # Wait for link
                    "-s", script_path,  # Script file
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=60.0
                )
                
                output = stdout.decode()
                error = stderr.decode()
                
                if "success" in output.lower() or process.returncode == 0:
                    logger.info(f"✅ Video sent via Telegram CLI!")
                    return True, "Sent via Telegram CLI"
                else:
                    logger.error(f"❌ Telegram CLI failed: {error}")
                    return False, f"CLI error: {error[:100]}"
                    
            finally:
                try:
                    os.unlink(script_path)
                except:
                    pass
                    
        except asyncio.TimeoutError:
            logger.error(f"❌ Telegram CLI timed out")
            return False, "CLI timeout"
        except Exception as e:
            logger.error(f"❌ Telegram CLI error: {e}")
            return False, f"CLI error: {e}"


# Alternative: Use tdlib (Telegram Database Library) - Python bindings
class TDLibProxy:
    """
    Alternative: Use TDLib (official Telegram library)
    This is MORE reliable than telegram-cli
    """
    
    def __init__(self):
        self.is_available = False
        self.client = None
        
    async def initialize(self, api_id: int, api_hash: str, phone: str):
        """Initialize TDLib client"""
        try:
            from telegram.client import Telegram
            
            self.client = Telegram(
                api_id=api_id,
                api_hash=api_hash,
                phone=phone,
                database_encryption_key='changeme1234',
                files_directory='/tmp/tdlib'
            )
            
            self.client.login()
            self.is_available = True
            logger.info("✅ TDLib client initialized!")
            return True
            
        except ImportError:
            logger.warning("⚠️ python-telegram package not installed")
            logger.info("   Install with: pip install python-telegram")
            return False
        except Exception as e:
            logger.error(f"❌ TDLib initialization failed: {e}")
            return False
    
    async def send_video_to_secret_chat(
        self,
        user_id: int,
        video_path: str,
        caption: str = ""
    ) -> Tuple[bool, str]:
        """Send video using TDLib (official Telegram library)"""
        
        if not self.is_available or not self.client:
            return False, "TDLib not available"
        
        try:
            logger.info(f"🔐 Creating secret chat via TDLib...")
            
            # Create secret chat
            result = self.client.call_method(
                'createNewSecretChat',
                params={'user_id': user_id}
            )
            
            secret_chat_id = result['id']
            logger.info(f"✅ Secret chat created: {secret_chat_id}")
            
            # Send video
            logger.info(f"📤 Sending video via TDLib...")
            result = self.client.call_method(
                'sendMessage',
                params={
                    'chat_id': secret_chat_id,
                    'input_message_content': {
                        '@type': 'inputMessageVideo',
                        'video': {'@type': 'inputFileLocal', 'path': video_path},
                        'caption': {'@type': 'formattedText', 'text': caption}
                    }
                }
            )
            
            logger.info(f"✅ Video sent via TDLib!")
            return True, "Sent via TDLib (official library)"
            
        except Exception as e:
            logger.error(f"❌ TDLib error: {e}")
            return False, f"TDLib error: {e}"


# Global instances
cli_proxy = TelegramCLIProxy()
tdlib_proxy = TDLibProxy()

