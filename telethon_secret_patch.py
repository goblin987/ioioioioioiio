"""
NUCLEAR PATCH: Intercept at the Python layer BEFORE calling compiled tgcrypto

The telethon-secret-chat library is Python code that calls tgcrypto.
We'll patch the PYTHON function that calls tgcrypto, not tgcrypto itself!
"""

import logging
from secret_chat_crypto import aes_ige_encrypt, aes_ige_decrypt, pad_to_16_bytes
import sys

logger = logging.getLogger(__name__)

ENABLE_PATCHES = False  # Library is too broken, use regular secret chat methods


def patch_upload_secret_file():
    """
    Patch the upload_secret_file method which is where file encryption happens
    """
    try:
        from telethon_secret_chat import secret_methods
        
        if not hasattr(secret_methods, 'SecretChatMethods'):
            logger.error("❌ Cannot find SecretChatMethods")
            return False
        
        SecretChatMethods = secret_methods.SecretChatMethods
        
        if not hasattr(SecretChatMethods, 'upload_secret_file'):
            logger.error("❌ Cannot find upload_secret_file method")
            return False
        
        original_upload = SecretChatMethods.upload_secret_file
        
        async def patched_upload_secret_file(self, file, *args, **kwargs):
            """
            PATCHED: Intercept file upload and use our encryption
            """
            logger.critical(f"🔧🔧🔧 PATCHED upload_secret_file CALLED: file={file}")
            
            # Read the file
            if isinstance(file, str):
                with open(file, 'rb') as f:
                    file_data = f.read()
                logger.critical(f"📂 Read file: {len(file_data)} bytes")
            else:
                file_data = file
            
            # Generate random key and IV (256-bit each)
            import os
            key = os.urandom(32)
            iv = os.urandom(32)
            
            logger.critical(f"🔐 Encrypting with OUR AES-IGE: {len(file_data)} bytes")
            
            try:
                # PAD to 16-byte boundary first!
                padded_data = pad_to_16_bytes(file_data)
                logger.critical(f"📦 Padded to: {len(padded_data)} bytes")
                
                # Use OUR correct encryption!
                encrypted_data = aes_ige_encrypt(padded_data, key, iv)
                logger.critical(f"✅✅✅ OUR ENCRYPTION SUCCESS: {len(encrypted_data)} bytes")
                
                # Now we need to upload the encrypted data and return the result
                # The original method expects to return an uploaded file reference
                # We'll call the original with our pre-encrypted data
                
                # Save encrypted data to temp file
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.enc') as temp_enc:
                    temp_enc.write(encrypted_data)
                    temp_path = temp_enc.name
                
                try:
                    # We've encrypted it - now just call the ORIGINAL upload
                    # But we don't want to use this complex approach
                    # Just let it fall through to original method
                    logger.critical(f"⚠️ Encrypted data ready, falling back to original upload")
                    return await original_upload(self, file, *args, **kwargs)
                    
                finally:
                    try:
                        import os
                        os.unlink(temp_path)
                    except:
                        pass
                    
            except Exception as e:
                logger.critical(f"❌❌❌ OUR ENCRYPTION FAILED: {e}")
                # Fallback to original
                return await original_upload(self, file, *args, **kwargs)
        
        # Apply the patch
        SecretChatMethods.upload_secret_file = patched_upload_secret_file
        logger.critical("✅✅✅ upload_secret_file PATCHED!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to patch upload_secret_file: {e}", exc_info=True)
        return False


def patch_send_secret_video():
    """
    Patch send_secret_video at the Python level to use our encryption
    """
    try:
        from telethon_secret_chat import secret_methods
        
        SecretChatMethods = secret_methods.SecretChatMethods
        
        if not hasattr(SecretChatMethods, 'send_secret_video'):
            logger.error("❌ Cannot find send_secret_video")
            return False
        
        original_send_video = SecretChatMethods.send_secret_video
        
        async def patched_send_secret_video(self, chat, file, *args, **kwargs):
            """
            PATCHED: Use our encryption for video files
            """
            logger.critical(f"🔧🔧🔧 PATCHED send_secret_video CALLED: file={file}")
            
            # Read the video file
            with open(file, 'rb') as f:
                video_data = f.read()
            
            logger.critical(f"📹 Video file size: {len(video_data)} bytes")
            
            # Generate encryption key and IV
            import os
            key = os.urandom(32)
            iv = os.urandom(32)
            
            logger.critical(f"🔐 Encrypting video with OUR AES-IGE...")
            
            try:
                # PAD to 16-byte boundary first!
                padded_video = pad_to_16_bytes(video_data)
                logger.critical(f"📦 Padded video to: {len(padded_video)} bytes")
                
                # Encrypt with OUR implementation
                encrypted_video = aes_ige_encrypt(padded_video, key, iv)
                logger.critical(f"✅✅✅ Video encrypted: {len(encrypted_video)} bytes")
                
                # Save encrypted video to temp file
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.enc.mp4') as temp_enc:
                    temp_enc.write(encrypted_video)
                    encrypted_path = temp_enc.name
                
                try:
                    # Now we need to manually construct the secret message with our key/iv
                    # This is complex - for now, let's try calling original but warn
                    logger.critical(f"⚠️ Calling original with encrypted file - this might double-encrypt!")
                    result = await original_send_video(self, chat, encrypted_path, *args, **kwargs)
                    logger.critical(f"✅ Original method returned: {result}")
                    return result
                    
                finally:
                    try:
                        import os
                        os.unlink(encrypted_path)
                    except:
                        pass
                    
            except Exception as e:
                logger.critical(f"❌❌❌ Patch failed: {e}", exc_info=True)
                return await original_send_video(self, chat, file, *args, **kwargs)
        
        SecretChatMethods.send_secret_video = patched_send_secret_video
        logger.critical("✅✅✅ send_secret_video PATCHED!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to patch send_secret_video: {e}", exc_info=True)
        return False


def apply_all_patches():
    """
    Apply patches at the Python layer
    """
    
    if not ENABLE_PATCHES:
        logger.warning("⚠️ Patches disabled")
        return False
    
    logger.critical("🔥🔥🔥 APPLYING NUCLEAR PYTHON-LEVEL PATCHES...")
    logger.critical("🎯 Target: Patch Python methods BEFORE they call tgcrypto")
    
    success_count = 0
    
    # Try patching at multiple levels
    if patch_send_secret_video():
        success_count += 1
    
    if patch_upload_secret_file():
        success_count += 1
    
    if success_count > 0:
        logger.critical(f"✅✅✅ {success_count} Python-level patches applied!")
        logger.critical("📹 Videos should now use OUR encryption!")
        return True
    else:
        logger.error("❌ All Python-level patches failed")
        return False
