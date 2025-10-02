#!/usr/bin/env python3
"""
Manual MTProto 2.0 implementation for sending files in secret chats.
Bypasses the broken telethon-secret-chat library.
"""
import os
import logging
import struct
from typing import Tuple, Optional
from telethon import TelegramClient
from telethon.tl.functions.upload import SaveFilePartRequest
from telethon.tl.functions.messages import SendEncryptedFileRequest
from telethon.tl.types import InputFile, InputEncryptedChat, InputEncryptedFileUploaded
from secret_chat_crypto import encrypt_file_for_secret_chat

logger = logging.getLogger(__name__)


async def upload_encrypted_file(
    client: TelegramClient,
    encrypted_data: bytes,
    file_id: int
) -> InputFile:
    """
    Upload encrypted file to Telegram servers in chunks.
    Returns InputFile that can be used in sendEncryptedFile.
    """
    CHUNK_SIZE = 512 * 1024  # 512 KB chunks (Telegram standard)
    total_size = len(encrypted_data)
    total_parts = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    logger.info(f"📤 Uploading {total_size} bytes in {total_parts} chunks...")
    
    for part_index in range(total_parts):
        start = part_index * CHUNK_SIZE
        end = min(start + CHUNK_SIZE, total_size)
        chunk = encrypted_data[start:end]
        
        # Upload chunk using upload.saveFilePart
        result = await client(SaveFilePartRequest(
            file_id=file_id,
            file_part=part_index,
            bytes=chunk
        ))
        
        if not result:
            raise Exception(f"Failed to upload part {part_index}")
        
        if (part_index + 1) % 10 == 0:
            logger.info(f"📦 Uploaded {part_index + 1}/{total_parts} chunks")
    
    logger.info(f"✅ All {total_parts} chunks uploaded successfully!")
    
    # Return InputFile
    return InputFile(
        id=file_id,
        parts=total_parts,
        name="encrypted_file.bin",
        md5_checksum=""
    )


def create_decrypted_message_media_photo(
    thumb: bytes,
    thumb_w: int,
    thumb_h: int,
    w: int,
    h: int,
    size: int,
    key: bytes,
    iv: bytes
) -> bytes:
    """
    Manually construct DecryptedMessageMediaPhoto TL object.
    This is what goes INSIDE the encrypted message.
    """
    # DecryptedMessageMediaPhoto#f1fa8d78
    constructor_id = 0xf1fa8d78
    
    # Build TL structure (simplified - may need adjustments)
    data = struct.pack('<I', constructor_id)  # constructor ID
    data += struct.pack('<I', len(thumb)) + thumb  # thumb bytes
    data += struct.pack('<I', thumb_w)  # thumb width
    data += struct.pack('<I', thumb_h)  # thumb height
    data += struct.pack('<I', w)  # width
    data += struct.pack('<I', h)  # height
    data += struct.pack('<I', size)  # file size
    data += key  # encryption key (32 bytes)
    data += iv  # IV (32 bytes)
    
    return data


async def send_encrypted_photo_manual(
    client: TelegramClient,
    secret_chat_id: int,
    photo_data: bytes,
    w: int = 960,
    h: int = 1280,
    thumb: bytes = b'',
    thumb_w: int = 100,
    thumb_h: int = 100
) -> bool:
    """
    Send a photo to a secret chat using manual MTProto 2.0 encryption.
    
    Args:
        client: Telethon client
        secret_chat_id: Secret chat ID (negative number)
        photo_data: Raw photo bytes
        w, h: Photo dimensions
        thumb, thumb_w, thumb_h: Thumbnail data
    
    Returns:
        True if successful
    """
    try:
        logger.info(f"🔐 Manually encrypting photo with MTProto 2.0...")
        
        # Step 1: Encrypt the file with our AES-256-IGE implementation
        encrypted_data, key, iv, fingerprint = encrypt_file_for_secret_chat(photo_data)
        logger.info(f"✅ Photo encrypted: {len(encrypted_data)} bytes, fingerprint={fingerprint}")
        
        # Step 2: Upload encrypted file to Telegram
        file_id = int.from_bytes(os.urandom(8), 'big')  # Random file ID
        input_file = await upload_encrypted_file(client, encrypted_data, file_id)
        
        # Step 3: Create InputEncryptedFileUploaded
        input_encrypted_file = InputEncryptedFileUploaded(
            id=file_id,
            parts=input_file.parts,
            md5_checksum="",
            key_fingerprint=fingerprint
        )
        
        # Step 4: Create the decrypted message media
        # This contains the DECRYPTION key/iv that the recipient needs
        media_data = create_decrypted_message_media_photo(
            thumb=thumb,
            thumb_w=thumb_w,
            thumb_h=thumb_h,
            w=w,
            h=h,
            size=len(photo_data),
            key=key,
            iv=iv
        )
        
        # Step 5: Use telethon-secret-chat to send the message part
        # The library will encrypt the message (containing key+IV) with secret chat key
        # But we provide the ALREADY ENCRYPTED file!
        
        # Get secret chat manager
        from telethon_secret_chat import SecretChatManager
        secret_manager = SecretChatManager(client)
        
        # Get the secret chat object
        secret_chat = secret_manager.get_secret_chat(secret_chat_id)
        
        if not secret_chat:
            raise Exception(f"Secret chat {secret_chat_id} not found")
        
        # Build the raw TL object for DecryptedMessageMediaPhoto
        from telethon_secret_chat.secret_sechma import secretTL
        
        media = secretTL.DecryptedMessageMediaPhoto(
            thumb=thumb if thumb else b'',
            thumb_w=thumb_w,
            thumb_h=thumb_h,
            w=w,
            h=h,
            size=len(photo_data),
            key=key,  # Our encryption key!
            iv=iv     # Our IV!
        )
        
        # Send via messages.sendEncryptedFile with OUR encrypted file
        from telethon.tl.functions.messages import SendEncryptedFileRequest
        from telethon.tl.types import InputEncryptedChat
        
        # Create message with media
        message = secretTL.DecryptedMessage(
            random_id=int.from_bytes(os.urandom(8), 'big'),
            random_bytes=os.urandom(15),
            message="",  # No text, just media
            media=media
        )
        
        # Let secret_manager encrypt the MESSAGE (not the file - we already did that!)
        encrypted_message = await secret_manager.encrypt_secret_message(
            secret_chat,
            message
        )
        
        # Send the encrypted message with our encrypted file
        await client(SendEncryptedFileRequest(
            peer=InputEncryptedChat(
                chat_id=abs(secret_chat_id),
                access_hash=secret_chat.access_hash
            ),
            random_id=message.random_id,
            data=encrypted_message,
            file=input_encrypted_file  # Our pre-encrypted file!
        ))
        
        logger.info(f"✅ Photo sent via manual MTProto 2.0!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Manual photo send failed: {e}", exc_info=True)
        return False


async def send_encrypted_video_manual(
    client: TelegramClient,
    secret_chat_id: int,
    video_data: bytes,
    duration: int,
    w: int,
    h: int,
    mime_type: str = "video/mp4",
    thumb: bytes = b'',
    thumb_w: int = 160,
    thumb_h: int = 120
) -> bool:
    """
    Send a video to a secret chat using manual MTProto 2.0 encryption.
    """
    try:
        logger.info(f"🔐 Manually encrypting video with MTProto 2.0...")
        
        # Step 1: Encrypt the file
        encrypted_data, key, iv, fingerprint = encrypt_file_for_secret_chat(video_data)
        logger.info(f"✅ Video encrypted: {len(encrypted_data)} bytes, fingerprint={fingerprint}")
        
        # Step 2: Upload encrypted file
        file_id = int.from_bytes(os.urandom(8), 'big')
        input_file = await upload_encrypted_file(client, encrypted_data, file_id)
        
        # Step 3: Create InputEncryptedFileUploaded
        from telethon.tl.types import InputEncryptedFileUploaded
        input_encrypted_file = InputEncryptedFileUploaded(
            id=file_id,
            parts=input_file.parts,
            md5_checksum="",
            key_fingerprint=fingerprint
        )
        
        # Step 4: Get secret chat manager and secret chat
        from telethon_secret_chat import SecretChatManager
        secret_manager = SecretChatManager(client)
        secret_chat = secret_manager.get_secret_chat(secret_chat_id)
        
        if not secret_chat:
            raise Exception(f"Secret chat {secret_chat_id} not found")
        
        # Step 5: Build DecryptedMessageMediaVideo with OUR keys
        from telethon_secret_chat.secret_sechma import secretTL
        
        media = secretTL.DecryptedMessageMediaVideo(
            thumb=thumb if thumb else b'',
            thumb_w=thumb_w,
            thumb_h=thumb_h,
            duration=duration,
            mime_type=mime_type,
            w=w,
            h=h,
            size=len(video_data),
            key=key,  # Our encryption key!
            iv=iv,    # Our IV!
            caption=""
        )
        
        # Step 6: Create message with media
        message = secretTL.DecryptedMessage(
            random_id=int.from_bytes(os.urandom(8), 'big'),
            random_bytes=os.urandom(15),
            message="",  # No text, just media
            media=media
        )
        
        # Step 7: Let secret_manager encrypt the MESSAGE (containing key+IV)
        encrypted_message = await secret_manager.encrypt_secret_message(
            secret_chat,
            message
        )
        
        # Step 8: Send via messages.sendEncryptedFile
        from telethon.tl.functions.messages import SendEncryptedFileRequest
        from telethon.tl.types import InputEncryptedChat
        
        await client(SendEncryptedFileRequest(
            peer=InputEncryptedChat(
                chat_id=abs(secret_chat_id),
                access_hash=secret_chat.access_hash
            ),
            random_id=message.random_id,
            data=encrypted_message,
            file=input_encrypted_file  # Our pre-encrypted file!
        ))
        
        logger.info(f"✅ Video sent via manual MTProto 2.0!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Manual video send failed: {e}", exc_info=True)
        return False

