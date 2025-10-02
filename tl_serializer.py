#!/usr/bin/env python3
"""
TL (Type Language) Serialization for MTProto Secret Chats
Implements proper serialization for DecryptedMessage structures
"""
import os
import struct
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def serialize_bytes(data: bytes) -> bytes:
    """
    Serialize bytes with TL padding.
    Format: length (1 byte if < 254, else 254 + 3 bytes) + data + padding to 4-byte boundary
    """
    length = len(data)
    
    if length < 254:
        result = struct.pack('<B', length) + data
    else:
        result = struct.pack('<B', 254) + struct.pack('<I', length)[:3] + data
    
    # Pad to 4-byte boundary
    padding_needed = (4 - len(result) % 4) % 4
    result += b'\x00' * padding_needed
    
    return result


def serialize_string(text: str) -> bytes:
    """Serialize a string (UTF-8 encoded)"""
    return serialize_bytes(text.encode('utf-8'))


def serialize_int(value: int) -> bytes:
    """Serialize a 32-bit integer"""
    return struct.pack('<i', value)


def serialize_long(value: int) -> bytes:
    """Serialize a 64-bit integer"""
    return struct.pack('<q', value)


class DocumentAttributeVideo:
    """
    DocumentAttributeVideo for secret chats
    
    documentAttributeVideo#0ef02ce6 
        flags:# 
        round_message:flags.0?true 
        supports_streaming:flags.1?true 
        duration:int 
        w:int 
        h:int 
        = DocumentAttribute;
    """
    CONSTRUCTOR_ID = 0x0ef02ce6
    
    def __init__(self, duration: int, w: int, h: int, round_message: bool = False, supports_streaming: bool = True):
        self.duration = duration
        self.w = w
        self.h = h
        self.round_message = round_message
        self.supports_streaming = supports_streaming
    
    def serialize(self) -> bytes:
        flags = 0
        if self.round_message:
            flags |= (1 << 0)
        if self.supports_streaming:
            flags |= (1 << 1)
        
        data = struct.pack('<I', self.CONSTRUCTOR_ID)
        data += serialize_int(flags)
        data += serialize_int(self.duration)
        data += serialize_int(self.w)
        data += serialize_int(self.h)
        return data


class DecryptedMessageMediaDocument:
    """
    DecryptedMessageMediaDocument structure for secret chats
    
    decryptedMessageMediaDocument#7afe8ae2 
        thumb:bytes 
        thumb_w:int 
        thumb_h:int 
        mime_type:string 
        size:int 
        key:bytes 
        iv:bytes 
        attributes:Vector<DocumentAttribute> 
        caption:string 
        = DecryptedMessageMedia;
    """
    CONSTRUCTOR_ID = 0x7afe8ae2
    
    def __init__(
        self,
        thumb: bytes,
        thumb_w: int,
        thumb_h: int,
        mime_type: str,
        size: int,
        key: bytes,
        iv: bytes,
        attributes: list,
        caption: str
    ):
        self.thumb = thumb
        self.thumb_w = thumb_w
        self.thumb_h = thumb_h
        self.mime_type = mime_type
        self.size = size
        self.key = key
        self.iv = iv
        self.attributes = attributes
        self.caption = caption
    
    def serialize(self) -> bytes:
        """Serialize to bytes"""
        data = struct.pack('<I', self.CONSTRUCTOR_ID)
        data += serialize_bytes(self.thumb)
        data += serialize_int(self.thumb_w)
        data += serialize_int(self.thumb_h)
        data += serialize_string(self.mime_type)
        data += serialize_int(self.size)
        data += serialize_bytes(self.key)
        data += serialize_bytes(self.iv)
        
        # Serialize attributes vector
        data += serialize_int(0x1cb5c415)  # Vector constructor
        data += serialize_int(len(self.attributes))
        for attr in self.attributes:
            if hasattr(attr, 'serialize'):
                data += attr.serialize()
        
        data += serialize_string(self.caption)
        
        return data


class DecryptedMessage:
    """
    DecryptedMessage structure for secret chats (Layer 73+)
    
    decryptedMessage#204d3878 
        flags:# 
        ttl:flags.2?int 
        message:string 
        media:flags.9?DecryptedMessageMedia 
        entities:flags.7?Vector<MessageEntity> 
        via_bot_name:flags.11?string 
        reply_to_random_id:flags.3?long 
        random_id:long 
        = DecryptedMessage;
    """
    CONSTRUCTOR_ID = 0x204d3878
    
    def __init__(
        self,
        random_id: int,
        message: str = "",
        media: Optional[DecryptedMessageMediaDocument] = None,
        ttl: Optional[int] = None,
        entities: Optional[list] = None,
        via_bot_name: Optional[str] = None,
        reply_to_random_id: Optional[int] = None
    ):
        self.random_id = random_id
        self.message = message
        self.media = media
        self.ttl = ttl
        self.entities = entities
        self.via_bot_name = via_bot_name
        self.reply_to_random_id = reply_to_random_id
    
    def serialize(self) -> bytes:
        """Serialize to bytes"""
        # Calculate flags
        flags = 0
        if self.ttl is not None:
            flags |= (1 << 2)
        if self.reply_to_random_id is not None:
            flags |= (1 << 3)
        if self.entities is not None:
            flags |= (1 << 7)
        if self.media is not None:
            flags |= (1 << 9)
        if self.via_bot_name is not None:
            flags |= (1 << 11)
        
        data = struct.pack('<I', self.CONSTRUCTOR_ID)
        data += serialize_int(flags)
        
        if self.ttl is not None:
            data += serialize_int(self.ttl)
        
        data += serialize_string(self.message)
        
        if self.media is not None:
            data += self.media.serialize()
        
        if self.entities is not None:
            data += serialize_int(0x1cb5c415)  # Vector constructor
            data += serialize_int(len(self.entities))
            for entity in self.entities:
                if hasattr(entity, 'serialize'):
                    data += entity.serialize()
        
        if self.via_bot_name is not None:
            data += serialize_string(self.via_bot_name)
        
        if self.reply_to_random_id is not None:
            data += serialize_long(self.reply_to_random_id)
        
        data += serialize_long(self.random_id)
        
        return data


def encrypt_message_for_secret_chat(message_data: bytes, secret_key: bytes, is_sender: bool = True) -> tuple:
    """
    Encrypt a message for secret chat using MTProto 2.0
    
    Args:
        message_data: Serialized DecryptedMessage bytes
        secret_key: 256-bit shared secret key (from DH exchange)
        is_sender: True if we're the sender, False if recipient
    
    Returns:
        (encrypted_data, msg_key)
    """
    import hashlib
    import random
    from secret_chat_crypto import aes_ige_encrypt, pad_to_16_bytes
    
    # Add random padding (12-1024 bytes, multiple of 16)
    padding_length = random.randint(12, 1024)
    padding_length = ((padding_length + 15) // 16) * 16
    padding = os.urandom(padding_length)
    
    plaintext = message_data + padding
    
    # Determine x value (0 for sender, 8 for recipient)
    x = 0 if is_sender else 8
    
    # Calculate msg_key_large = SHA256(substr(secret_key, 88+x, 32) + plaintext + padding)
    key_part = secret_key[88+x:88+x+32]
    msg_key_large = hashlib.sha256(key_part + plaintext).digest()
    msg_key = msg_key_large[8:24]  # 16 bytes
    
    # Derive AES key and IV
    sha256_a = hashlib.sha256(msg_key + secret_key[x:x+36]).digest()
    sha256_b = hashlib.sha256(secret_key[40+x:40+x+36] + msg_key).digest()
    
    aes_key = sha256_a[0:8] + sha256_b[8:24] + sha256_a[24:32]
    aes_iv = sha256_b[0:8] + sha256_a[8:24] + sha256_b[24:32]
    
    # Encrypt with AES-256-IGE
    plaintext_padded = pad_to_16_bytes(plaintext)
    encrypted = aes_ige_encrypt(plaintext_padded, aes_key, aes_iv)
    
    return encrypted, msg_key


if __name__ == "__main__":
    # Test serialization
    logging.basicConfig(level=logging.INFO)
    
    # Test DecryptedMessageMediaDocument
    media = DecryptedMessageMediaDocument(
        thumb=b'',
        thumb_w=90,
        thumb_h=160,
        mime_type="video/mp4",
        size=1000000,
        key=os.urandom(32),
        iv=os.urandom(32),
        attributes=[],
        caption="Test video"
    )
    
    msg = DecryptedMessage(
        random_id=12345678901234,
        message="",
        media=media
    )
    
    serialized = msg.serialize()
    logger.info(f"✅ Serialized message: {len(serialized)} bytes")
    logger.info(f"First 32 bytes (hex): {serialized[:32].hex()}")

