"""
Proper MTProto Secret Chat File Encryption
Implements AES-256-IGE encryption as per Telegram specification
Based on official MTProto 2.0 documentation with KDF (Key Derivation Function)
"""

import hashlib
import os
from typing import Tuple
from Crypto.Cipher import AES
import struct
import logging

logger = logging.getLogger(__name__)

def aes_ige_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """
    AES-256-IGE encryption (Infinite Garble Extension)
    This is Telegram's custom encryption mode
    """
    assert len(key) == 32  # 256-bit key
    assert len(iv) == 32   # 256-bit IV
    assert len(data) % 16 == 0  # Must be 16-byte aligned
    
    cipher = AES.new(key, AES.MODE_ECB)
    
    # Split IV into two halves for IGE mode
    iv1 = iv[:16]
    iv2 = iv[16:]
    
    encrypted = bytearray()
    
    # Process in 16-byte blocks
    for i in range(0, len(data), 16):
        block = data[i:i+16]
        
        # XOR with previous ciphertext (IGE mode)
        xored = bytes(a ^ b for a, b in zip(block, iv1))
        
        # Encrypt
        encrypted_block = cipher.encrypt(xored)
        
        # XOR with previous plaintext (IGE mode)
        result = bytes(a ^ b for a, b in zip(encrypted_block, iv2))
        
        encrypted.extend(result)
        
        # Update IVs for next block
        iv1 = result
        iv2 = block
    
    return bytes(encrypted)


def aes_ige_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """
    AES-256-IGE decryption (Infinite Garble Extension)
    """
    assert len(key) == 32  # 256-bit key
    assert len(iv) == 32   # 256-bit IV
    assert len(data) % 16 == 0  # Must be 16-byte aligned
    
    cipher = AES.new(key, AES.MODE_ECB)
    
    # Split IV into two halves for IGE mode
    iv1 = iv[:16]
    iv2 = iv[16:]
    
    decrypted = bytearray()
    
    # Process in 16-byte blocks
    for i in range(0, len(data), 16):
        block = data[i:i+16]
        
        # XOR with previous plaintext (IGE mode)
        xored = bytes(a ^ b for a, b in zip(block, iv2))
        
        # Decrypt
        decrypted_block = cipher.decrypt(xored)
        
        # XOR with previous ciphertext (IGE mode)
        result = bytes(a ^ b for a, b in zip(decrypted_block, iv1))
        
        decrypted.extend(result)
        
        # Update IVs for next block
        iv1 = block
        iv2 = result
    
    return bytes(decrypted)


def pad_to_16_bytes(data: bytes) -> bytes:
    """Pad data to 16-byte boundary with random bytes"""
    # Convert memoryview to bytes if needed
    if isinstance(data, memoryview):
        data = bytes(data)
    
    padding_needed = (16 - (len(data) % 16)) % 16
    if padding_needed > 0:
        padding = os.urandom(padding_needed)
        return data + padding
    return data


def derive_aes_key_iv_mtproto2(msg_key: bytes, auth_key: bytes, is_client: bool = True) -> Tuple[bytes, bytes]:
    """
    MTProto 2.0 Key Derivation Function (KDF)
    As shown in the official diagram
    
    Args:
        msg_key: 128-bit message key (from SHA-256 of plaintext)
        auth_key: 256-bit shared secret chat key
        is_client: True if encrypting from client, False if from server
    
    Returns:
        (aes_key, aes_iv): 256-bit AES key and 256-bit IV
    """
    x = 0 if is_client else 8  # Client uses x=0, server uses x=8
    
    # Multiple SHA-256 operations as per MTProto 2.0 spec
    sha256_a = hashlib.sha256(msg_key + auth_key[x:x+36]).digest()
    sha256_b = hashlib.sha256(auth_key[40+x:40+x+36] + msg_key).digest()
    
    # Derive AES key (256 bits)
    aes_key = sha256_a[:8] + sha256_b[8:24] + sha256_a[24:32]
    
    # Derive AES IV (256 bits)
    aes_iv = sha256_b[:8] + sha256_a[8:24] + sha256_b[24:32]
    
    return aes_key, aes_iv


def encrypt_file_for_secret_chat(file_data: bytes) -> Tuple[bytes, bytes, bytes, int]:
    """
    Encrypt a file for Telegram Secret Chat according to MTProto spec
    
    Returns:
        encrypted_data: The encrypted file bytes
        key: 256-bit AES key (to be sent in message)
        iv: 256-bit initialization vector (to be sent in message)
        fingerprint: Key fingerprint for verification
    """
    # Generate random 256-bit key and IV (as per spec)
    key = os.urandom(32)  # 256 bits
    iv = os.urandom(32)   # 256 bits
    
    # Pad file data to 16-byte boundary
    padded_data = pad_to_16_bytes(file_data)
    
    # Encrypt using AES-256-IGE
    encrypted_data = aes_ige_encrypt(padded_data, key, iv)
    
    # Compute key fingerprint as per spec:
    # digest = md5(key + iv)
    # fingerprint = substr(digest, 0, 4) XOR substr(digest, 4, 4)
    digest = hashlib.md5(key + iv).digest()
    fingerprint_bytes = bytes(a ^ b for a, b in zip(digest[:4], digest[4:8]))
    # Use signed int32 format (Telegram expects this)
    fingerprint = struct.unpack('<i', fingerprint_bytes)[0]
    
    return encrypted_data, key, iv, fingerprint


def decrypt_file_from_secret_chat(encrypted_data: bytes, key: bytes, iv: bytes, fingerprint: int) -> bytes:
    """
    Decrypt a file received from Telegram Secret Chat
    
    Args:
        encrypted_data: The encrypted file bytes
        key: 256-bit AES key (from message)
        iv: 256-bit initialization vector (from message)
        fingerprint: Key fingerprint for verification
    
    Returns:
        decrypted_data: The original file bytes
    """
    # Verify key fingerprint
    digest = hashlib.md5(key + iv).digest()
    fingerprint_bytes = bytes(a ^ b for a, b in zip(digest[:4], digest[4:8]))
    # Use signed int32 format (Telegram uses this)
    computed_fingerprint = struct.unpack('<i', fingerprint_bytes)[0]
    
    if computed_fingerprint != fingerprint:
        raise ValueError(f"Key fingerprint mismatch! Expected {fingerprint}, got {computed_fingerprint}")
    
    # Decrypt using AES-256-IGE
    decrypted_data = aes_ige_decrypt(encrypted_data, key, iv)
    
    return decrypted_data


# Test the implementation
if __name__ == "__main__":
    # Test data
    test_data = b"Hello, this is a test video file!" * 100
    
    print(f"Original size: {len(test_data)} bytes")
    
    # Encrypt
    encrypted, key, iv, fingerprint = encrypt_file_for_secret_chat(test_data)
    print(f"Encrypted size: {len(encrypted)} bytes")
    print(f"Key fingerprint: {fingerprint}")
    
    # Decrypt
    decrypted = decrypt_file_from_secret_chat(encrypted, key, iv, fingerprint)
    
    # Verify
    # Remove padding
    decrypted = decrypted[:len(test_data)]
    
    if decrypted == test_data:
        print("✅ Encryption/Decryption works correctly!")
    else:
        print("❌ Encryption/Decryption FAILED!")

