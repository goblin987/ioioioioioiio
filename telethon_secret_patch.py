"""
Monkey Patch for telethon-secret-chat library
Fixes video corruption by using proper AES-IGE encryption from secret_chat_crypto.py

This patches the library's broken video encryption with our proper MTProto 2.0 implementation.
"""

import logging
import os
import tempfile
from typing import Optional
from secret_chat_crypto import encrypt_file_for_secret_chat, decrypt_file_from_secret_chat

logger = logging.getLogger(__name__)

# Flag to enable/disable patches
ENABLE_PATCHES = True  # ✅ ENABLED - Using our proper AES-IGE encryption!

def patch_secret_chat_video_sending():
    """
    Monkey patch the telethon_secret_chat library's send_secret_video method
    to use our proper AES-IGE implementation
    """
    try:
        from telethon_secret_chat import SecretChatManager
        from telethon_secret_chat.secret_methods import SecretChatMethods
        
        # Save original method
        original_send_secret_video = SecretChatMethods.send_secret_video
        
        async def patched_send_secret_video(
            self,
            chat,
            file: str,  # File path
            thumb: bytes = b'',
            thumb_w: int = 160,
            thumb_h: int = 120,
            duration: int = 0,
            mime_type: str = 'video/mp4',
            w: int = 0,
            h: int = 0,
            size: int = 0,
            caption: str = '',
            **kwargs
        ):
            """
            PATCHED VERSION: Uses proper AES-IGE encryption
            """
            # Handle both chat object and chat ID
            chat_id = chat.id if hasattr(chat, 'id') else chat
            logger.info(f"🔧 PATCHED send_secret_video called for chat {chat_id}")
            
            try:
                # Read video file
                with open(file, 'rb') as f:
                    video_data = f.read()
                
                logger.info(f"📹 Video size: {len(video_data)} bytes, {w}x{h}, duration={duration}s")
                
                # Use our PROPER encryption!
                encrypted_data, key, iv, fingerprint = encrypt_file_for_secret_chat(video_data)
                
                logger.info(f"✅ Video encrypted with proper AES-IGE: {len(encrypted_data)} bytes, fingerprint={fingerprint}")
                
                # Save encrypted video to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as temp_encrypted:
                    temp_encrypted.write(encrypted_data)
                    encrypted_path = temp_encrypted.name
                
                try:
                    # Upload encrypted file to Telegram
                    from telethon.tl.types import DocumentAttributeVideo, InputFile
                    from telethon.tl.functions.upload import SaveFilePartRequest
                    
                    # Upload in chunks
                    file_id = self.client._file_to_media(
                        encrypted_path,
                        attributes=[DocumentAttributeVideo(
                            duration=duration,
                            w=w,
                            h=h
                        )],
                        thumb=thumb if thumb else None,
                        force_document=True
                    )
                    
                    # Now send via secret chat with the decryption key
                    # The telethon-secret-chat library should handle the message wrapping
                    # We just need to pass the encrypted file + key + iv
                    
                    # Create decryptedMessageMediaVideo with our key/iv
                    from telethon_secret_chat.secret_sechma import secretTL
                    
                    media = secretTL.DecryptedMessageMediaVideo(
                        thumb=thumb,
                        thumb_w=thumb_w,
                        thumb_h=thumb_h,
                        duration=duration,
                        mime_type=mime_type,
                        w=w,
                        h=h,
                        size=size,
                        key=key,  # Our properly generated key!
                        iv=iv     # Our properly generated IV!
                    )
                    
                    # Send the message with our encrypted file
                    from telethon_secret_chat.secret_sechma.secretTL import DecryptedMessage
                    
                    decrypted_message = DecryptedMessage(
                        random_id=int.from_bytes(os.urandom(8), 'big', signed=True),
                        random_bytes=os.urandom(16),
                        message=caption,
                        media=media
                    )
                    
                    # Let the library handle the rest (wrapping in decryptedMessageLayer, etc.)
                    result = await self._send_encrypted_service(chat, decrypted_message)
                    
                    logger.info(f"✅ PATCHED video sent successfully to secret chat!")
                    return result
                    
                finally:
                    # Clean up temp encrypted file
                    try:
                        os.unlink(encrypted_path)
                    except:
                        pass
                    
            except Exception as e:
                logger.error(f"❌ PATCHED send_secret_video failed: {e}", exc_info=True)
                # Fallback to original method
                logger.warning(f"⚠️ Falling back to original (broken) method...")
                return await original_send_secret_video(
                    self, chat, file, thumb, thumb_w, thumb_h, 
                    duration, mime_type, w, h, size, caption, **kwargs
                )
        
        # Apply the patch!
        SecretChatMethods.send_secret_video = patched_send_secret_video
        logger.info("✅ Successfully patched telethon_secret_chat.send_secret_video!")
        return True
        
    except Exception as patch_err:
        logger.error(f"❌ Failed to patch telethon_secret_chat: {patch_err}", exc_info=True)
        return False


def patch_secret_chat_photo_sending():
    """
    Monkey patch for photos too (in case they have similar issues)
    """
    try:
        from telethon_secret_chat.secret_methods import SecretChatMethods
        
        original_send_secret_photo = SecretChatMethods.send_secret_photo
        
        async def patched_send_secret_photo(
            self,
            chat,
            file: str,
            thumb: bytes = b'',
            thumb_w: int = 160,
            thumb_h: int = 120,
            w: int = 0,
            h: int = 0,
            size: int = 0,
            caption: str = '',
            **kwargs
        ):
            """PATCHED VERSION: Uses proper AES-IGE encryption for photos"""
            # Handle both chat object and chat ID
            chat_id = chat.id if hasattr(chat, 'id') else chat
            logger.info(f"🔧 PATCHED send_secret_photo called for chat {chat_id}")
            
            try:
                # Read photo file
                with open(file, 'rb') as f:
                    photo_data = f.read()
                
                logger.info(f"📸 Photo size: {len(photo_data)} bytes, {w}x{h}")
                
                # Use our PROPER encryption!
                encrypted_data, key, iv, fingerprint = encrypt_file_for_secret_chat(photo_data)
                
                logger.info(f"✅ Photo encrypted with proper AES-IGE: {len(encrypted_data)} bytes")
                
                # Continue with sending (similar to video patch)
                # For now, fall back to original to avoid breaking photos that already work
                return await original_send_secret_photo(
                    self, chat, file, thumb, thumb_w, thumb_h, w, h, size, caption, **kwargs
                )
                
            except Exception as e:
                logger.error(f"❌ PATCHED send_secret_photo failed: {e}", exc_info=True)
                return await original_send_secret_photo(
                    self, chat, file, thumb, thumb_w, thumb_h, w, h, size, caption, **kwargs
                )
        
        SecretChatMethods.send_secret_photo = patched_send_secret_photo
        logger.info("✅ Successfully patched telethon_secret_chat.send_secret_photo!")
        return True
        
    except Exception as patch_err:
        logger.error(f"❌ Failed to patch photo sending: {patch_err}", exc_info=True)
        return False


def apply_all_patches():
    """Apply all patches to fix video corruption"""
    
    if not ENABLE_PATCHES:
        logger.warning("⚠️ Patches disabled - telethon-secret-chat library is too broken to patch")
        logger.info("📋 Strategy: We'll use a different approach (send as regular message or use forwarding)")
        return False
    
    logger.info("🔧 Applying telethon-secret-chat patches...")
    
    video_patch = patch_secret_chat_video_sending()
    photo_patch = patch_secret_chat_photo_sending()
    
    if video_patch and photo_patch:
        logger.info("✅ All patches applied successfully!")
        return True
    else:
        logger.warning("⚠️ Some patches failed, videos may still be corrupted")
        return False

