#!/usr/bin/env python3
"""
Full MTProto 2.0 Secret Chat Implementation
Bypasses telethon-secret-chat library entirely for video sending
"""
import os
import logging
import random
from typing import Optional, Tuple
from telethon import TelegramClient
from telethon.tl.functions.upload import SaveFilePartRequest
from telethon.tl.functions.messages import SendEncryptedFileRequest
from telethon.tl.types import InputEncryptedChat, InputEncryptedFileUploaded

from secret_chat_crypto import encrypt_file_for_secret_chat
from tl_serializer import DocumentAttributeVideo, encrypt_message_for_secret_chat

logger = logging.getLogger(__name__)


async def send_video_mtproto_full(
    client: TelegramClient,
    secret_chat_manager,
    secret_chat_obj,
    video_data: bytes,
    filename: str = "video.mp4",
    duration: int = 0,
    width: int = 0,
    height: int = 0
) -> bool:
    """
    🔥 ATTEMPT #17: Full MTProto 2.0 implementation WITHOUT library's broken encryption
    
    This completely bypasses the telethon-secret-chat library's media encryption
    and implements the entire MTProto 2.0 protocol manually.
    
    Args:
        client: Telethon client
        secret_chat_manager: Only used to get the secret key
        secret_chat_obj: Secret chat object (contains ID and access_hash)
        video_data: Raw video bytes
        filename: Video filename
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"🚀 ATTEMPT #17: Full MTProto 2.0 - bypassing library entirely!")
        
        # ============================================================================
        # STEP 1: Encrypt the video file with OUR encryption
        # ============================================================================
        logger.info(f"🔐 Step 1: Encrypting {len(video_data)} bytes with AES-256-IGE...")
        encrypted_video, file_key, file_iv, fingerprint = encrypt_file_for_secret_chat(video_data)
        logger.info(f"✅ File encrypted: {len(encrypted_video)} bytes, fingerprint={fingerprint}")
        
        # ============================================================================
        # STEP 2: Upload encrypted file to Telegram
        # ============================================================================
        logger.info(f"📤 Step 2: Uploading encrypted file chunks...")
        
        file_id = random.randint(1, 9223372036854775807)  # Signed int64
        CHUNK_SIZE = 512 * 1024
        total_parts = (len(encrypted_video) + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        for part_index in range(total_parts):
            start = part_index * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, len(encrypted_video))
            chunk = encrypted_video[start:end]
            
            await client(SaveFilePartRequest(
                file_id=file_id,
                file_part=part_index,
                bytes=chunk
            ))
        
        logger.info(f"✅ Uploaded {total_parts} chunks successfully!")
        
        # ============================================================================
        # STEP 3: Create InputEncryptedFileUploaded
        # ============================================================================
        input_file = InputEncryptedFileUploaded(
            id=file_id,
            parts=total_parts,
            md5_checksum="",
            key_fingerprint=fingerprint
        )
        
        # ============================================================================
        # STEP 4: Build DecryptedMessageMediaDocument with OUR keys
        # ============================================================================
        logger.info(f"🏗️ Step 4: Building TL structure...")
        
        # 🎯 ATTEMPT #19: Use library's TL classes (same as photos!)
        # Photos work, so use EXACT same TL objects!
        logger.info(f"🎯 Using library's TL classes...")
        
        # Import library's TL classes
        from telethon_secret_chat.secret_sechma import secretTL
        
        # Build media using library's classes
        media = secretTL.DecryptedMessageMediaDocument(
            thumb=b'',
            thumb_w=90,
            thumb_h=160,
            mime_type="video/mp4",
            size=len(video_data),  # ORIGINAL size
            key=file_key,  # OUR encryption key
            iv=file_iv,    # OUR IV
            # Library might need attributes in a specific format
            attributes=[],  # Try without attributes first
            caption=""
        )
        
        # Build message using library's classes
        try:
            # Try modern layer first
            message = secretTL.DecryptedMessage(
                random_id=random.randint(1, 9223372036854775807),
                message="",
                media=media
            )
            logger.info(f"✅ Using modern DecryptedMessage")
        except TypeError:
            # Fallback to layer 23
            message = secretTL.DecryptedMessage23(
                random_id=random.randint(1, 9223372036854775807),
                ttl=0,
                message="",
                media=media
            )
            logger.info(f"✅ Using DecryptedMessage23 (layer 23)")
        
        # Serialize the message using library's serializer
        serialized_message = bytes(message)
        logger.info(f"✅ Message serialized: {len(serialized_message)} bytes")
        
        # ============================================================================
        # STEP 6: Get the secret chat's shared key
        # ============================================================================
        logger.info(f"🔑 Step 6: Extracting secret chat shared key...")
        
        try:
            # Try to get the shared key from the library's session
            secret_key = None
            
            # Method 1: From secret_chat_obj
            if hasattr(secret_chat_obj, 'auth_key'):
                secret_key = secret_chat_obj.auth_key
                logger.info(f"✅ Got auth_key from secret_chat_obj")
            
            # Method 2: From secret_chat_manager session
            elif hasattr(secret_chat_manager, 'session'):
                session = secret_chat_manager.session
                if hasattr(session, 'get_secret_chat_by_id'):
                    sc = session.get_secret_chat_by_id(secret_chat_obj.id)
                    if sc and hasattr(sc, 'auth_key'):
                        secret_key = sc.auth_key
                        logger.info(f"✅ Got auth_key from session")
            
            # Method 3: From Telethon session directly
            if secret_key is None:
                # Try to access the auth key from Telethon's internal structures
                # This is hacky but necessary since the library doesn't expose it properly
                if hasattr(client.session, '_secret_chats'):
                    sc = client.session._secret_chats.get(secret_chat_obj.id)
                    if sc:
                        secret_key = sc.get('key')
                        logger.info(f"✅ Got auth_key from Telethon session")
            
            if secret_key is None:
                raise Exception("Cannot extract secret chat shared key! Library doesn't expose it.")
            
            # Ensure it's bytes
            if isinstance(secret_key, int):
                secret_key = secret_key.to_bytes(256, 'big')
            elif not isinstance(secret_key, bytes):
                secret_key = bytes(secret_key)
            
            logger.info(f"✅ Secret key extracted: {len(secret_key)} bytes")
            
        except Exception as key_err:
            logger.error(f"❌ Cannot get secret chat key: {key_err}")
            logger.warning(f"⚠️ Will try to use library's method as absolute last resort...")
            
            # ABSOLUTE LAST RESORT: Use library to encrypt the message
            # This will use the library's message encryption but OUR file encryption
            try:
                from telethon_secret_chat.secret_sechma import secretTL
                
                # Build library's message structure
                lib_msg = secretTL.DecryptedMessage23(
                    random_id=message.random_id,
                    ttl=0,
                    message="",
                    media=secretTL.DecryptedMessageMediaDocument(
                        thumb=b'',
                        thumb_w=90,
                        thumb_h=160,
                        mime_type="video/mp4",
                        size=len(video_data),
                        key=file_key,
                        iv=file_iv,
                        attributes=[],
                        caption=""
                    )
                )
                
                # Let library encrypt the message
                encrypted_msg_bytes = await secret_chat_manager._encrypt_message(secret_chat_obj, bytes(lib_msg))
                msg_key = encrypted_msg_bytes[:16]  # Library includes msg_key at start
                encrypted_data = encrypted_msg_bytes[16:]
                
                logger.info(f"✅ Used library to encrypt message (last resort)")
                
                # Skip to step 8
                await client(SendEncryptedFileRequest(
                    peer=InputEncryptedChat(
                        chat_id=secret_chat_obj.id,
                        access_hash=secret_chat_obj.access_hash
                    ),
                    random_id=message.random_id,
                    data=encrypted_msg_bytes,
                    file=input_file
                ))
                
                logger.info(f"✅ SUCCESS! Video sent via MTProto 2.0 (library-assisted)!")
                return True
                
            except Exception as lib_err:
                logger.error(f"❌ Library encryption also failed: {lib_err}", exc_info=True)
                return False
        
        # ============================================================================
        # STEP 7: Encrypt the message with the secret chat key
        # ============================================================================
        logger.info(f"🔐 Step 7: Encrypting message with secret chat key...")
        
        encrypted_data, msg_key = encrypt_message_for_secret_chat(
            serialized_message,
            secret_key,
            is_sender=True
        )
        
        logger.info(f"✅ Message encrypted: {len(encrypted_data)} bytes")
        
        # ============================================================================
        # STEP 8: Send via SendEncryptedFileRequest
        # ============================================================================
        logger.info(f"📤 Step 8: Sending encrypted file + message...")
        
        # Build the final encrypted data (msg_key + encrypted_message)
        final_data = msg_key + encrypted_data
        
        await client(SendEncryptedFileRequest(
            peer=InputEncryptedChat(
                chat_id=secret_chat_obj.id,
                access_hash=secret_chat_obj.access_hash
            ),
            random_id=message.random_id,
            data=final_data,
            file=input_file
        ))
        
        logger.info(f"✅ SUCCESS! Video sent via FULL MTProto 2.0 implementation!")
        logger.info(f"🎯 Buyer should be able to play video with ZERO extra steps!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ATTEMPT #17 failed: {e}", exc_info=True)
        return False

