"""
Deep Patch for telethon-secret-chat library
STRATEGY: Patch at the pyaes level (the library it uses for encryption)

The library uses pyaes for AES-IGE encryption, which is BROKEN for large files.
We'll replace pyaes.AESModeOfOperationIGE with our implementation.
"""

import logging
from secret_chat_crypto import aes_ige_encrypt, aes_ige_decrypt
import os

logger = logging.getLogger(__name__)

ENABLE_PATCHES = True


def patch_pyaes_ige():
    """
    Patch the pyaes library's IGE mode with our proper implementation
    This is the ROOT CAUSE - pyaes.AESModeOfOperationIGE is broken!
    """
    try:
        import pyaes
        
        logger.info("🔧 Patching pyaes.AESModeOfOperationIGE...")
        
        # Save original
        original_ige_class = pyaes.AESModeOfOperationIGE
        
        class PatchedAESModeOfOperationIGE:
            """
            Replacement for pyaes.AESModeOfOperationIGE using our correct implementation
            """
            def __init__(self, key, iv=None):
                self.key = key
                self.iv = iv if iv else b'\x00' * 32
                logger.info(f"🔧 PatchedAESModeOfOperationIGE initialized: key={len(key)} bytes, iv={len(iv) if iv else 0} bytes")
            
            def encrypt(self, plaintext):
                """Use our proper AES-IGE encryption"""
                logger.info(f"🔐 PATCHED IGE encrypt called: {len(plaintext)} bytes")
                result = aes_ige_encrypt(plaintext, self.key, self.iv)
                logger.info(f"✅ PATCHED IGE encrypt done: {len(result)} bytes")
                return result
            
            def decrypt(self, ciphertext):
                """Use our proper AES-IGE decryption"""
                logger.info(f"🔐 PATCHED IGE decrypt called: {len(ciphertext)} bytes")
                result = aes_ige_decrypt(ciphertext, self.key, self.iv)
                logger.info(f"✅ PATCHED IGE decrypt done: {len(result)} bytes")
                return result
        
        # REPLACE the broken class with our working one!
        pyaes.AESModeOfOperationIGE = PatchedAESModeOfOperationIGE
        
        logger.info("✅ Successfully replaced pyaes.AESModeOfOperationIGE with our implementation!")
        return True
        
    except ImportError:
        logger.warning("⚠️ pyaes not found - library might use different crypto backend")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to patch pyaes: {e}", exc_info=True)
        return False


def patch_pycryptodome_ige():
    """
    Alternative: Patch pycryptodome if the library uses that
    """
    try:
        from Crypto.Cipher import AES
        
        logger.info("🔧 Attempting to patch Crypto.Cipher.AES...")
        
        # This is trickier because pycryptodome doesn't have native IGE mode
        # If the library uses it, they must have implemented a wrapper
        
        # For now, just log that we detected pycryptodome
        logger.info("✅ pycryptodome detected, but no patching needed (library uses pyaes for IGE)")
        return True
        
    except ImportError:
        logger.info("📋 pycryptodome not found")
        return False


def apply_all_patches():
    """
    Apply all patches to fix video corruption
    
    THIS IS THE NUCLEAR OPTION: We replace the entire AES-IGE implementation
    """
    
    if not ENABLE_PATCHES:
        logger.warning("⚠️ Patches disabled")
        return False
    
    logger.info("🔧 Applying DEEP telethon-secret-chat patches...")
    logger.info("🎯 Target: Replace pyaes.AESModeOfOperationIGE with our correct implementation")
    
    # This is the MAIN patch
    if patch_pyaes_ige():
        logger.info("✅ 🎉 CRITICAL PATCH APPLIED - pyaes IGE encryption replaced!")
        logger.info("📹 Videos should now encrypt/decrypt correctly!")
        return True
    else:
        logger.error("❌ Failed to patch pyaes - videos will still be corrupted")
        # Try alternative
        patch_pycryptodome_ige()
        return False
