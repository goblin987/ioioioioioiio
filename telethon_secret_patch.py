"""
Deep Runtime Patch for telethon-secret-chat library
STRATEGY: Find and replace the IGE encryption function at runtime

The library must use SOME AES-IGE implementation - we'll find it and replace it!
"""

import logging
from secret_chat_crypto import aes_ige_encrypt, aes_ige_decrypt
import sys

logger = logging.getLogger(__name__)

ENABLE_PATCHES = True


def discover_and_patch_ige():
    """
    Discover which IGE implementation the library uses and patch it
    """
    try:
        from telethon_secret_chat import secret_methods
        
        logger.info("🔍 Searching for IGE encryption implementation...")
        
        # Check what the library actually has
        if hasattr(secret_methods, 'SecretChatMethods'):
            methods_class = secret_methods.SecretChatMethods
            logger.info(f"📋 SecretChatMethods attributes: {dir(methods_class)}")
            
            # Look for any method with 'crypt' or 'ige' in the name
            for attr_name in dir(methods_class):
                if 'crypt' in attr_name.lower() or 'ige' in attr_name.lower():
                    logger.info(f"🔍 Found potential crypto method: {attr_name}")
        
        # Try to patch the telethon_secret_chat.ige module if it exists
        try:
            from telethon_secret_chat import ige as ige_module
            logger.info(f"📦 Found IGE module: {ige_module}")
            logger.info(f"📋 IGE module contents: {dir(ige_module)}")
            
            # Patch the encrypt/decrypt functions in the IGE module
            if hasattr(ige_module, 'encrypt'):
                original_encrypt = ige_module.encrypt
                
                def patched_ige_encrypt(data, key, iv):
                    logger.info(f"🔧 PATCHED IGE encrypt called: {len(data)} bytes")
                    result = aes_ige_encrypt(data, key, iv)
                    logger.info(f"✅ PATCHED IGE encrypt done: {len(result)} bytes")
                    return result
                
                ige_module.encrypt = patched_ige_encrypt
                logger.info("✅ Patched telethon_secret_chat.ige.encrypt!")
                return True
            
            if hasattr(ige_module, 'ige_encrypt'):
                original_ige_encrypt = ige_module.ige_encrypt
                
                def patched_ige_encrypt(data, key, iv):
                    logger.info(f"🔧 PATCHED ige_encrypt called: {len(data)} bytes")
                    result = aes_ige_encrypt(data, key, iv)
                    logger.info(f"✅ PATCHED ige_encrypt done: {len(result)} bytes")
                    return result
                
                ige_module.ige_encrypt = patched_ige_encrypt
                logger.info("✅ Patched telethon_secret_chat.ige.ige_encrypt!")
                return True
                
        except ImportError:
            logger.warning("⚠️ No ige module found in telethon_secret_chat")
        
        # Try to find and patch the AES implementation the library uses
        # Check if the library uses tgcrypto
        try:
            import tgcrypto
            logger.info(f"📦 Found tgcrypto: {tgcrypto}")
            logger.info(f"📋 tgcrypto contents: {dir(tgcrypto)}")
            
            if hasattr(tgcrypto, 'ige256_encrypt'):
                original_ige256_encrypt = tgcrypto.ige256_encrypt
                
                def patched_ige256_encrypt(data, key, iv):
                    logger.info(f"🔧 PATCHED tgcrypto.ige256_encrypt called: {len(data)} bytes")
                    result = aes_ige_encrypt(data, key, iv)
                    logger.info(f"✅ PATCHED tgcrypto.ige256_encrypt done: {len(result)} bytes")
                    return result
                
                tgcrypto.ige256_encrypt = patched_ige256_encrypt
                logger.info("✅ Patched tgcrypto.ige256_encrypt!")
                return True
                
        except ImportError:
            logger.info("📋 tgcrypto not found")
        
        logger.error("❌ Could not find IGE encryption implementation to patch!")
        return False
        
    except Exception as e:
        logger.error(f"❌ Failed to discover and patch IGE: {e}", exc_info=True)
        return False


def apply_all_patches():
    """
    Apply patches to fix video corruption
    
    This will discover and replace whatever IGE implementation the library uses
    """
    
    if not ENABLE_PATCHES:
        logger.warning("⚠️ Patches disabled")
        return False
    
    logger.info("🔧 Applying DEEP telethon-secret-chat patches...")
    logger.info("🎯 Target: Discover and replace the library's IGE encryption")
    
    if discover_and_patch_ige():
        logger.info("✅ 🎉 IGE encryption patched successfully!")
        logger.info("📹 Videos should now encrypt/decrypt correctly!")
        return True
    else:
        logger.error("❌ Failed to patch IGE - videos will still be corrupted")
        return False
