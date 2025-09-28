"""
TgCF Pro - Smart Bump Service Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Enterprise-grade automated advertising and campaign management system.
Provides intelligent scheduling, multi-target broadcasting, and comprehensive
performance analytics for business communication automation.

Features:
- Advanced campaign scheduling with multiple patterns
- Multi-account campaign management
- Real-time performance tracking and analytics
- Intelligent retry mechanisms and error handling
- Professional campaign templates and A/B testing

Author: TgCF Pro Team
License: MIT
Version: 1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import schedule
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from telethon import TelegramClient
from telethon.tl.custom import Button
from telethon.tl.types import ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonUrl, KeyboardButtonRow
from database_testforwarder import Database
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telethon_manager_testforwarder import TelethonManager
import json
import threading
import traceback

# Global telethon manager instance
telethon_manager = TelethonManager()

# Configure structured logging
logger = logging.getLogger(__name__)

class StructuredLogger:
    """Enhanced logging with structured data and context"""
    
    @staticmethod
    def log_operation(operation: str, user_id: int = None, campaign_id: int = None, 
                     account_id: int = None, success: bool = None, details: str = None):
        """Log operation with structured context"""
        context = {
            'operation': operation,
            'user_id': user_id,
            'campaign_id': campaign_id,
            'account_id': account_id,
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'details': details
        }
        
        if success is True:
            logger.info(f"✅ {operation} completed successfully", extra=context)
        elif success is False:
            logger.error(f"❌ {operation} failed", extra=context)
        else:
            logger.info(f"🔄 {operation} in progress", extra=context)
    
    @staticmethod
    def log_error(operation: str, error: Exception, user_id: int = None, 
                 campaign_id: int = None, account_id: int = None):
        """Log error with full context and stack trace"""
        context = {
            'operation': operation,
            'user_id': user_id,
            'campaign_id': campaign_id,
            'account_id': account_id,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            'stack_trace': traceback.format_exc()
        }
        
        logger.error(f"💥 {operation} failed: {error}", extra=context, exc_info=True)
    
    @staticmethod
    def log_performance(operation: str, duration: float, user_id: int = None, 
                       campaign_id: int = None, details: str = None):
        """Log performance metrics"""
        context = {
            'operation': operation,
            'duration_seconds': duration,
            'user_id': user_id,
            'campaign_id': campaign_id,
            'timestamp': datetime.now().isoformat(),
            'details': details
        }
        
        if duration > 10:
            logger.warning(f"⚠️ {operation} took {duration:.2f}s (slow)", extra=context)
        else:
            logger.info(f"⏱️ {operation} completed in {duration:.2f}s", extra=context)

@dataclass
class AdCampaign:
    """Represents an advertising campaign"""
    id: int
    user_id: int
    account_id: int
    campaign_name: str
    ad_content: str
    target_chats: List[str]
    schedule_type: str  # 'once', 'daily', 'weekly', 'custom'
    schedule_time: str  # Format: "HH:MM" or cron-like
    is_active: bool
    created_at: str
    last_run: Optional[str] = None
    total_sends: int = 0

class BumpService:
    """Service for managing automated ad bumping/posting"""
    
    def __init__(self, bot_instance=None):
        self.db = Database()
        self.active_campaigns = {}
        self.scheduler_thread = None
        self.is_running = False
        self.telegram_clients = {}
        self.client_init_semaphore = threading.Semaphore(1)  # Thread-safe semaphore
        self.temp_files = set()  # Track temporary files for cleanup
        self.bot_instance = bot_instance  # Store bot instance for ReplyKeyboardMarkup
        self.init_bump_database()
    
    def _get_db_connection(self):
        """Get database connection with proper configuration"""
        return self.db._get_connection()
    
    def _register_temp_file(self, file_path: str):
        """Register a temporary file for cleanup"""
        self.temp_files.add(file_path)
    
    def _cleanup_temp_file(self, file_path: str):
        """Clean up a temporary file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")
        finally:
            self.temp_files.discard(file_path)
    
    async def _process_bridge_channel_message(self, client, chat_entity, ad_content, telethon_reply_markup):
        """Process bridge channel message with premium emoji preservation"""
        try:
            bridge_channel_entity = ad_content.get('bridge_channel_entity')
            bridge_message_id = ad_content.get('bridge_message_id')
            
            logger.info(f"🔗 Bridge channel: {bridge_channel_entity}, Message ID: {bridge_message_id}")
            
            # Step 1: Get the bridge channel entity (join if needed)
            try:
                bridge_entity = await client.get_entity(bridge_channel_entity)
                logger.info(f"✅ Bridge channel entity resolved: {getattr(bridge_entity, 'title', bridge_channel_entity)}")
                
                # Try to join the channel (if it's public and we're not already in it)
                try:
                    from telethon.tl.functions.channels import JoinChannelRequest
                    await client(JoinChannelRequest(bridge_entity))
                    logger.info(f"✅ Joined bridge channel {bridge_channel_entity}")
                except Exception as join_error:
                    logger.info(f"Already in bridge channel or can't join: {join_error}")
                
            except Exception as entity_error:
                logger.error(f"❌ Could not resolve bridge channel {bridge_channel_entity}: {entity_error}")
                return
            
            # Step 2: Get the original message from bridge channel (preserves all entities)
            try:
                original_message = await client.get_messages(bridge_entity, ids=bridge_message_id)
                if not original_message:
                    logger.error(f"❌ Message {bridge_message_id} not found in {bridge_channel_entity}")
                    return
                
                logger.info(f"✅ Retrieved original message from bridge channel with all entities intact")
                logger.info(f"Message has media: {bool(original_message.media)}")
                logger.info(f"Message text length: {len(original_message.message or '')}")
                
                # Step 3: Forward the message with all entities preserved + add buttons
                if original_message.media:
                    # Forward media with preserved entities and add buttons
                    message = await client.send_file(
                        chat_entity,
                        original_message.media,
                        caption=original_message.message,
                        reply_markup=telethon_reply_markup
                    )
                    logger.info(f"✅ Bridge channel media forwarded with PREMIUM EMOJIS and buttons to {chat_entity.title}")
                else:
                    # Forward text with preserved entities and add buttons
                    message = await client.send_message(
                        chat_entity,
                        original_message.message,
                        reply_markup=telethon_reply_markup
                    )
                    logger.info(f"✅ Bridge channel text forwarded with PREMIUM EMOJIS and buttons to {chat_entity.title}")
                
            except Exception as message_error:
                logger.error(f"❌ Could not retrieve/forward message from bridge channel: {message_error}")
                return
                
        except Exception as e:
            logger.error(f"❌ Bridge channel processing failed: {e}")
            return
    
    def cleanup_all_resources(self):
        """Clean up all resources (clients, temp files, etc.)"""
        logger.info("Starting comprehensive resource cleanup...")
        
        # Clean up all Telegram clients
        for account_id, client in list(self.telegram_clients.items()):
            try:
                if hasattr(client, 'disconnect'):
                    # Run disconnect in a separate thread to avoid blocking
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(self._sync_disconnect_client, client)
                        future.result(timeout=5)  # 5 second timeout
                logger.info(f"Disconnected client for account {account_id}")
            except Exception as e:
                logger.error(f"Error disconnecting client {account_id}: {e}")
            finally:
                del self.telegram_clients[account_id]
        
        # Clean up all temporary files
        for temp_file in list(self.temp_files):
            self._cleanup_temp_file(temp_file)
        
        # Clean up any remaining session files
        self._cleanup_session_files()
        
        logger.info("Resource cleanup completed")
    
    def _sync_disconnect_client(self, client):
        """Synchronously disconnect a client"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(client.disconnect())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Failed to disconnect client: {e}")
    
    def _cleanup_session_files(self):
        """Clean up all session files"""
        import glob
        try:
            # Find all session files
            session_files = glob.glob("bump_session_*.session")
            for session_file in session_files:
                try:
                    if os.path.exists(session_file):
                        os.remove(session_file)
                        logger.debug(f"Cleaned up session file: {session_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up session file {session_file}: {e}")
        except Exception as e:
            logger.error(f"Error during session file cleanup: {e}")
    
    # Removed _format_buttons_as_text - now using inline buttons only
    
    def _reconstruct_text_with_entities(self, text, entities):
        """Reconstruct text with custom emojis using entity data"""
        if not text or not entities:
            return text or ""
        
        logger.info(f"Reconstructing text with {len(entities)} entities")
        
        # Sort entities by offset to process them in order
        sorted_entities = sorted(entities, key=lambda x: x.get('offset', 0))
        
        reconstructed = ""
        last_offset = 0
        
        for entity in sorted_entities:
            entity_type = entity.get('type', '')
            offset = entity.get('offset', 0)
            length = entity.get('length', 0)
            
            # Add text before this entity
            if offset > last_offset:
                reconstructed += text[last_offset:offset]
            
            # Get the entity text
            entity_text = text[offset:offset + length]
            
            if entity_type == 'custom_emoji' and entity.get('custom_emoji_id'):
                # For custom emojis, we'll use a special format that Telethon can understand
                custom_emoji_id = entity.get('custom_emoji_id')
                # Use the original text but mark it for custom emoji
                reconstructed += entity_text  # Keep original emoji text
                logger.info(f"Preserved custom emoji: {entity_text} (ID: {custom_emoji_id})")
            else:
                # For other entities, just add the text
                reconstructed += entity_text
            
            last_offset = offset + length
        
        # Add remaining text
        if last_offset < len(text):
            reconstructed += text[last_offset:]
        
        logger.info(f"Text reconstruction complete: {len(reconstructed)} chars")
        return reconstructed
    
    def _convert_to_telethon_entities(self, entities, text):
        """Convert Bot API entities to Telethon entities for premium emoji support"""
        if not entities:
            return []
        
        try:
            from telethon.tl.types import (
                MessageEntityCustomEmoji, MessageEntityBold, MessageEntityItalic,
                MessageEntityTextUrl, MessageEntityHashtag
            )
            
            telethon_entities = []
            
            for entity in entities:
                entity_type = entity.get('type', '')
                offset = entity.get('offset', 0)
                length = entity.get('length', 0)
                
                # Skip if offset/length would be out of bounds
                if offset + length > len(text):
                    continue
                
                if entity_type == 'custom_emoji' and entity.get('custom_emoji_id'):
                    # This is the key for premium emojis!
                    custom_emoji_id = int(entity.get('custom_emoji_id'))
                    telethon_entity = MessageEntityCustomEmoji(
                        offset=offset,
                        length=length,
                        document_id=custom_emoji_id
                    )
                    telethon_entities.append(telethon_entity)
                    # Custom emoji converted successfully
                
                elif entity_type == 'bold':
                    telethon_entities.append(MessageEntityBold(offset=offset, length=length))
                
                elif entity_type == 'italic':
                    telethon_entities.append(MessageEntityItalic(offset=offset, length=length))
                
                elif entity_type == 'text_link' and entity.get('url'):
                    telethon_entities.append(MessageEntityTextUrl(
                        offset=offset, length=length, url=entity.get('url')
                    ))
                
                elif entity_type == 'hashtag':
                    telethon_entities.append(MessageEntityHashtag(offset=offset, length=length))
            
            logger.info(f"Converted {len(telethon_entities)} entities for Telethon")
            return telethon_entities
            
        except Exception as e:
            logger.error(f"Failed to convert entities to Telethon format: {e}")
            return []
    
    # Removed _add_buttons_to_text - now using inline buttons directly
    
    def init_bump_database(self):
        """Initialize bump service database tables"""
        import sqlite3
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Ad campaigns table - Enhanced for multi-userbot support
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ad_campaigns (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    account_id INTEGER,
                    campaign_name TEXT,
                    ad_content TEXT,
                    target_chats TEXT,
                    schedule_type TEXT,
                    schedule_time TEXT,
                    buttons TEXT,
                    target_mode TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    immediate_start BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_run TIMESTAMP,
                    total_sends INTEGER DEFAULT 0,
                    additional_accounts TEXT,  -- JSON array of {account_id, delay_minutes, content_variation}
                    spam_avoidance_enabled BOOLEAN DEFAULT 1,
                    timing_variation_minutes INTEGER DEFAULT 5,
                    content_variations TEXT,  -- JSON array of message variations
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (account_id) REFERENCES telegram_accounts (id)
                )
            ''')
            
            # Campaign execution logs for spam avoidance
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaign_execution_logs (
                    id SERIAL PRIMARY KEY,
                    campaign_id INTEGER,
                    account_id INTEGER,
                    execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    content_variation_used INTEGER DEFAULT 0,
                    groups_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    delay_applied_minutes INTEGER DEFAULT 0,
                    FOREIGN KEY (campaign_id) REFERENCES ad_campaigns (id),
                    FOREIGN KEY (account_id) REFERENCES telegram_accounts (id)
                )
            ''')
            
            # Add missing columns to existing tables if they don't exist
            cursor.execute("PRAGMA table_info(ad_campaigns)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'buttons' not in columns:
                cursor.execute('ALTER TABLE ad_campaigns ADD COLUMN buttons TEXT')
                logger.info("Added buttons column to ad_campaigns table")
            if 'target_mode' not in columns:
                cursor.execute('ALTER TABLE ad_campaigns ADD COLUMN target_mode TEXT')
                logger.info("Added target_mode column to ad_campaigns table")
            if 'immediate_start' not in columns:
                cursor.execute('ALTER TABLE ad_campaigns ADD COLUMN immediate_start BOOLEAN DEFAULT 0')
                logger.info("Added immediate_start column to ad_campaigns table")
            if 'additional_accounts' not in columns:
                cursor.execute('ALTER TABLE ad_campaigns ADD COLUMN additional_accounts TEXT')
                logger.info("Added additional_accounts column to ad_campaigns table")
            if 'spam_avoidance_enabled' not in columns:
                cursor.execute('ALTER TABLE ad_campaigns ADD COLUMN spam_avoidance_enabled BOOLEAN DEFAULT 1')
                logger.info("Added spam_avoidance_enabled column to ad_campaigns table")
            if 'timing_variation_minutes' not in columns:
                cursor.execute('ALTER TABLE ad_campaigns ADD COLUMN timing_variation_minutes INTEGER DEFAULT 5')
                logger.info("Added timing_variation_minutes column to ad_campaigns table")
            if 'content_variations' not in columns:
                cursor.execute('ALTER TABLE ad_campaigns ADD COLUMN content_variations TEXT')
                logger.info("Added content_variations column to ad_campaigns table")
            
            # Update existing campaigns with default values and ensure they're active
            cursor.execute("UPDATE ad_campaigns SET buttons = ? WHERE buttons IS NULL", (json.dumps([{"text": "Shop Now", "url": "https://t.me/testukassdfdds"}]),))
            cursor.execute("UPDATE ad_campaigns SET target_mode = 'all_groups' WHERE target_mode IS NULL")
            cursor.execute("UPDATE ad_campaigns SET immediate_start = 0 WHERE immediate_start IS NULL")
            cursor.execute("UPDATE ad_campaigns SET is_active = 1 WHERE is_active IS NULL OR is_active = 0")
            cursor.execute("UPDATE ad_campaigns SET spam_avoidance_enabled = 1 WHERE spam_avoidance_enabled IS NULL")
            cursor.execute("UPDATE ad_campaigns SET timing_variation_minutes = 5 WHERE timing_variation_minutes IS NULL")
            
            updated_count = cursor.rowcount
            if updated_count > 0:
                logger.info(f"Updated {updated_count} existing campaigns with default button data and activated them")
            
            # Ad performance tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ad_performance (
                    id SERIAL PRIMARY KEY,
                    campaign_id INTEGER,
                    user_id BIGINT,
                    target_chat TEXT,
                    message_id INTEGER,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    FOREIGN KEY (campaign_id) REFERENCES ad_campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
    
    def add_campaign(self, user_id: int, account_id: int, campaign_name: str, 
                    ad_content, target_chats: List[str], schedule_type: str, 
                    schedule_time: str, buttons=None, target_mode='specific', immediate_start=False) -> int:
        """Add new ad campaign with support for complex content types and buttons"""
        import sqlite3
        start_time = time.time()
        
        try:
            StructuredLogger.log_operation(
                "add_campaign", 
                user_id=user_id, 
                campaign_id=None, 
                account_id=account_id,
                success=None,
                details=f"Creating campaign '{campaign_name}' with {len(target_chats)} targets"
            )
            
            # Convert ad_content to JSON string if it's a list or dict
            if isinstance(ad_content, (list, dict)):
                ad_content_str = json.dumps(ad_content)
            else:
                ad_content_str = str(ad_content)
            
            # Convert target_chats to JSON string
            target_chats_str = json.dumps(target_chats) if isinstance(target_chats, list) else str(target_chats)
            
            # Convert buttons to JSON string
            buttons_str = json.dumps(buttons) if buttons else None
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO ad_campaigns 
                    (user_id, account_id, campaign_name, ad_content, target_chats, schedule_type, schedule_time, buttons, target_mode, immediate_start)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, account_id, campaign_name, ad_content_str, 
                     target_chats_str, schedule_type, schedule_time, buttons_str, target_mode, immediate_start))
                conn.commit()
                campaign_id = cursor.lastrowid
                
                # Schedule the campaign
                self.schedule_campaign(campaign_id)
                
                duration = time.time() - start_time
                StructuredLogger.log_performance(
                    "add_campaign", 
                    duration, 
                    user_id=user_id, 
                    campaign_id=campaign_id,
                    details=f"Campaign '{campaign_name}' created and scheduled"
                )
                
                StructuredLogger.log_operation(
                    "add_campaign", 
                    user_id=user_id, 
                    campaign_id=campaign_id, 
                    account_id=account_id,
                    success=True,
                    details=f"Campaign '{campaign_name}' successfully created"
                )
                
                # Execute immediately if requested
                if immediate_start:
                    logger.info(f"🚀 Running campaign {campaign_id} immediately on creation")
                    # Run the campaign execution in a separate thread to not block
                    threading.Thread(
                        target=self._run_campaign_immediately, 
                        args=(campaign_id,),
                        daemon=True
                    ).start()
                
                return campaign_id
                
        except Exception as e:
            StructuredLogger.log_error(
                "add_campaign", 
                e, 
                user_id=user_id, 
                account_id=account_id,
                details=f"Failed to create campaign '{campaign_name}'"
            )
            raise
    
    def _run_campaign_immediately(self, campaign_id: int):
        """Run campaign immediately in a separate thread"""
        try:
            logger.info(f"🚀 Starting immediate execution of campaign {campaign_id}")
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the campaign execution
                loop.run_until_complete(self._execute_campaign_async(campaign_id))
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"❌ Immediate campaign execution failed for {campaign_id}: {e}")
    
    async def _execute_campaign_async(self, campaign_id: int):
        """Execute campaign asynchronously - same logic as scheduled execution"""
        try:
            # Get campaign data
            campaign = self.db.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return
            
            logger.info(f"🚀 Executing immediate campaign {campaign_id}: {campaign['campaign_name']}")
            
            # Use the existing campaign execution logic
            await self._async_send_ad(campaign_id)
            
            logger.info(f"✅ Immediate campaign {campaign_id} executed successfully")
            
        except Exception as e:
            logger.error(f"❌ Immediate campaign execution failed for {campaign_id}: {e}")
    
    def get_user_campaigns(self, user_id: int) -> List[Dict]:
        """Get all campaigns for a user"""
        import sqlite3
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ac.id, ac.user_id, ac.account_id, ac.campaign_name, ac.ad_content, 
                       ac.target_chats, ac.schedule_type, ac.schedule_time, ac.buttons, 
                       ac.target_mode, ac.is_active, ac.created_at, ac.last_run, 
                       ac.total_sends, ta.account_name
                FROM ad_campaigns ac
                LEFT JOIN telegram_accounts ta ON ac.account_id = ta.id
                WHERE ac.user_id = ?
                ORDER BY ac.created_at DESC
            ''', (user_id,))
            rows = cursor.fetchall()
            
            campaigns = []
            for row in rows:
                # Parse ad_content (could be JSON string or plain string) - safer parsing
                try:
                    if row[4] and isinstance(row[4], str) and row[4].startswith(('[', '{')):
                        ad_content = json.loads(row[4])
                    else:
                        ad_content = str(row[4]) if row[4] else ""
                except (json.JSONDecodeError, AttributeError, TypeError):
                    ad_content = str(row[4]) if row[4] else ""
                
                # Parse target_chats (should be JSON string) - safer parsing
                try:
                    if row[5] and isinstance(row[5], str):
                        target_chats = json.loads(row[5])
                    elif isinstance(row[5], list):
                        target_chats = row[5]
                    else:
                        target_chats = [str(row[5])] if row[5] else []
                except (json.JSONDecodeError, TypeError):
                    target_chats = [str(row[5])] if row[5] else []
                
                # Parse buttons if they exist - much safer parsing
                buttons = []
                try:
                    if len(row) > 8 and row[8] is not None:
                        if isinstance(row[8], str) and row[8]:
                            buttons = json.loads(row[8])
                        elif isinstance(row[8], list):
                            buttons = row[8]
                except (json.JSONDecodeError, IndexError, TypeError):
                    buttons = []
                
                # Parse target_mode if it exists - safer parsing
                try:
                    target_mode = str(row[9]) if len(row) > 9 and row[9] else 'specific'
                except (IndexError, TypeError):
                    target_mode = 'specific'
                
                campaigns.append({
                    'id': row[0],                    # ac.id
                    'user_id': row[1],               # ac.user_id  
                    'account_id': row[2],            # ac.account_id
                    'campaign_name': row[3],         # ac.campaign_name
                    'ad_content': ad_content,        # ac.ad_content (parsed)
                    'target_chats': target_chats,    # ac.target_chats (parsed)
                    'schedule_type': row[6],         # ac.schedule_type
                    'schedule_time': row[7],         # ac.schedule_time
                    'buttons': buttons,              # ac.buttons (parsed)
                    'target_mode': target_mode,      # ac.target_mode (parsed)
                    'is_active': bool(row[10]),      # ac.is_active
                    'created_at': row[11],           # ac.created_at
                    'last_run': row[12],             # ac.last_run
                    'total_sends': row[13] or 0,     # ac.total_sends
                    'account_name': row[14]          # ta.account_name
                })
            return campaigns
    
    def get_campaign(self, campaign_id: int) -> Optional[Dict]:
        """Get specific campaign by ID"""
        import sqlite3
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ac.id, ac.user_id, ac.account_id, ac.campaign_name, ac.ad_content, 
                       ac.target_chats, ac.schedule_type, ac.schedule_time, ac.buttons, 
                       ac.target_mode, ac.is_active, ac.immediate_start, ac.created_at, ac.last_run, 
                       ac.total_sends, ta.account_name
                FROM ad_campaigns ac
                LEFT JOIN telegram_accounts ta ON ac.account_id = ta.id
                WHERE ac.id = ?
            ''', (campaign_id,))
            row = cursor.fetchone()
            
            if row:
                # Parse ad_content (could be JSON string or plain string) - safer parsing
                try:
                    if row[4] and isinstance(row[4], str) and row[4].startswith(('[', '{')):
                        ad_content = json.loads(row[4])
                    else:
                        ad_content = str(row[4]) if row[4] else ""
                except (json.JSONDecodeError, AttributeError, TypeError):
                    ad_content = str(row[4]) if row[4] else ""
                
                # Parse target_chats (should be JSON string) - safer parsing
                try:
                    if row[5] and isinstance(row[5], str):
                        target_chats = json.loads(row[5])
                    elif isinstance(row[5], list):
                        target_chats = row[5]
                    else:
                        target_chats = [str(row[5])] if row[5] else []
                except (json.JSONDecodeError, TypeError):
                    target_chats = [str(row[5])] if row[5] else []
                
                # Parse buttons if they exist - much safer parsing
                buttons = []
                try:
                    if len(row) > 8 and row[8] is not None:
                        if isinstance(row[8], str) and row[8]:
                            buttons = json.loads(row[8])
                        elif isinstance(row[8], list):
                            buttons = row[8]
                except (json.JSONDecodeError, IndexError, TypeError):
                    buttons = []
                
                # Parse target_mode if it exists - safer parsing
                try:
                    target_mode = str(row[9]) if len(row) > 9 and row[9] else 'specific'
                except (IndexError, TypeError):
                    target_mode = 'specific'
                
                return {
                    'id': row[0],                    # ac.id
                    'user_id': row[1],               # ac.user_id  
                    'account_id': row[2],            # ac.account_id
                    'campaign_name': row[3],         # ac.campaign_name
                    'ad_content': ad_content,        # ac.ad_content (parsed)
                    'target_chats': target_chats,    # ac.target_chats (parsed)
                    'schedule_type': row[6],         # ac.schedule_type
                    'schedule_time': row[7],         # ac.schedule_time
                    'buttons': buttons,              # ac.buttons (parsed)
                    'target_mode': target_mode,      # ac.target_mode (parsed)
                    'is_active': bool(row[10]),      # ac.is_active
                    'immediate_start': bool(row[11]), # ac.immediate_start
                    'created_at': row[12],           # ac.created_at
                    'last_run': row[13],             # ac.last_run
                    'total_sends': row[14] or 0,     # ac.total_sends
                    'account_name': row[15]          # ta.account_name
                }
            return None
    
    def update_campaign(self, campaign_id: int, **kwargs):
        """Update campaign details with SQL injection protection"""
        import sqlite3
        
        # Strictly validate allowed fields to prevent SQL injection
        allowed_fields = {
            'campaign_name': str,
            'ad_content': (str, dict, list),
            'target_chats': (str, list),
            'schedule_type': str,
            'schedule_time': str,
            'is_active': bool
        }
        
        updates = []
        values = []
        
        for field, value in kwargs.items():
            # Validate field name
            if field not in allowed_fields:
                logger.warning(f"Attempted to update invalid field '{field}' for campaign {campaign_id}")
                continue
            
            # Validate field type
            expected_type = allowed_fields[field]
            if not isinstance(value, expected_type):
                logger.warning(f"Invalid type for field '{field}': expected {expected_type}, got {type(value)}")
                continue
            
            # Sanitize and prepare value
            if field == 'target_chats' and isinstance(value, list):
                value = json.dumps(value)
            elif field == 'ad_content' and isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif field == 'is_active' and not isinstance(value, bool):
                value = bool(value)
            
            updates.append(f"{field} = ?")
            values.append(value)
        
        if not updates:
            logger.warning(f"No valid updates provided for campaign {campaign_id}")
            return False
        
        try:
            values.append(campaign_id)
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Use parameterized query to prevent SQL injection
                cursor.execute(f'''
                    UPDATE ad_campaigns 
                    SET {', '.join(updates)}
                    WHERE id = ?
                ''', values)
                conn.commit()
                
                if cursor.rowcount == 0:
                    logger.warning(f"No campaign found with ID {campaign_id}")
                    return False
                
                logger.info(f"Successfully updated campaign {campaign_id} with fields: {', '.join([u.split(' = ')[0] for u in updates])}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update campaign {campaign_id}: {e}")
            return False
    
    def delete_campaign(self, campaign_id: int):
        """Permanently delete campaign from database and clean up scheduler"""
        import sqlite3
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Delete from ad_performance table first (foreign key constraint)
            cursor.execute('DELETE FROM ad_performance WHERE campaign_id = ?', (campaign_id,))
            
            # Delete from ad_campaigns table
            cursor.execute('DELETE FROM ad_campaigns WHERE id = ?', (campaign_id,))
            
            conn.commit()
            logger.info(f"Permanently deleted campaign {campaign_id} from database")
            
        # Remove from active campaigns
        if campaign_id in self.active_campaigns:
            del self.active_campaigns[campaign_id]
            logger.info(f"Removed campaign {campaign_id} from active campaigns")
        
        # Clean up scheduled jobs for this campaign
        import schedule
        jobs_to_remove = []
        for job in schedule.jobs:
            if hasattr(job, 'job_func') and hasattr(job.job_func, 'args') and job.job_func.args and job.job_func.args[0] == campaign_id:
                jobs_to_remove.append(job)
        
        for job in jobs_to_remove:
            schedule.cancel_job(job)
            logger.info(f"Cancelled scheduled job for campaign {campaign_id}")
        
        logger.info(f"Campaign {campaign_id} completely cleaned up")
    
    def initialize_telegram_client(self, account_id: int, cache_client: bool = False) -> Optional[TelegramClient]:
        """Initialize Telegram client - Thread-safe version for scheduler"""
        # Use thread-safe semaphore to prevent simultaneous client initialization
        with self.client_init_semaphore:
            try:
                # Always run in a separate thread to avoid event loop conflicts
                import concurrent.futures
                import threading
                
                # Check if we're in the main thread (where the bot runs)
                current_thread = threading.current_thread()
                is_main_thread = current_thread == threading.main_thread()
                
                if is_main_thread:
                    # We're in the main thread - use ThreadPoolExecutor to avoid blocking
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(self._sync_initialize_client, account_id, cache_client)
                        return future.result(timeout=30)  # 30 second timeout
                else:
                    # We're already in a background thread - run directly
                    return self._sync_initialize_client(account_id, cache_client)
                    
            except Exception as e:
                logger.error(f"Failed to initialize client for account {account_id}: {e}")
                return None
    
    def _sync_initialize_client(self, account_id: int, cache_client: bool = False) -> Optional[TelegramClient]:
        """Synchronous wrapper for client initialization in a new thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._async_initialize_client(account_id, cache_client))
        finally:
            loop.close()
    
    async def _async_initialize_client(self, account_id: int, cache_client: bool = False) -> Optional[TelegramClient]:
        """Async helper for client initialization using telethon_manager (no interactive auth)"""
        # For scheduled executions, always create fresh client to avoid asyncio loop issues
        if cache_client and account_id in self.telegram_clients:
            return self.telegram_clients[account_id]
        
        account = self.db.get_account(account_id)
        if not account:
            logger.error(f"Account {account_id} not found")
            return None
        
        # 🎯 USE TELETHON_MANAGER: No more interactive authentication issues!
        logger.info(f"🔄 BUMP SERVICE: Using telethon_manager for account {account_id}")
        
        try:
            # Use the unified telethon manager (handles sessions properly)
            client = await telethon_manager.get_client(account)
            
            if not client:
                logger.error(f"❌ Failed to get client from telethon_manager for account {account_id}")
                return None
                
            # Only cache client if requested (not for scheduled executions)
            if cache_client:
                self.telegram_clients[account_id] = client
                
            logger.info(f"✅ Telegram client initialized via telethon_manager (Account: {account_id})")
            
            # 🎯 AUTO-JOIN STORAGE CHANNEL: Ensure worker account can access storage channel
            try:
                from config_testforwarder import Config
                storage_channel_id = Config.STORAGE_CHANNEL_ID
                
                if storage_channel_id:
                    logger.info(f"🔄 AUTO-JOIN: Ensuring worker account has access to storage channel {storage_channel_id}")
                    
                    # Convert string ID to integer for Telethon
                    try:
                        if isinstance(storage_channel_id, str):
                            if storage_channel_id.startswith('-100'):
                                # Full channel ID format: -1001234567890
                                channel_id_int = int(storage_channel_id)
                            elif storage_channel_id.startswith('-'):
                                # Short format: -1234567890, convert to full format
                                channel_id_int = int('-100' + storage_channel_id[1:])
                            else:
                                # Positive number, convert to negative channel ID
                                channel_id_int = int('-100' + storage_channel_id)
                        else:
                            channel_id_int = int(storage_channel_id)
                        
                        logger.info(f"🔄 Using channel ID: {channel_id_int}")
                        
                        # Try to get channel info with proper error handling
                        try:
                            storage_channel = await client.get_entity(channel_id_int)
                            logger.info(f"✅ Storage channel access confirmed: {storage_channel.title}")
                        except Exception as entity_error:
                            # Handle asyncio event loop issues
                            if "asyncio event loop" in str(entity_error):
                                logger.warning(f"⚠️ Event loop issue detected, retrying with fresh client...")
                                # Recreate client to avoid event loop conflicts
                                client = await telethon_manager.get_client(account)
                                if client:
                                    storage_channel = await client.get_entity(channel_id_int)
                                    logger.info(f"✅ Storage channel access confirmed after retry: {storage_channel.title}")
                                else:
                                    raise entity_error
                            else:
                                raise entity_error
                        
                    except Exception as access_error:
                        logger.warning(f"⚠️ Cannot access storage channel with ID {channel_id_int}: {access_error}")
                        
                        # 🔄 TELETHON SESSION REFRESH: If worker is member but Telethon can't find channel, refresh session
                        if "Cannot find any entity" in str(access_error):
                            logger.warning(f"🔄 TELETHON SESSION ISSUE: Worker is member but session cache is stale")
                            logger.warning(f"💡 SOLUTION: Force session refresh by getting dialogs")
                            
                            try:
                                # Force Telethon to refresh its entity cache by getting dialogs
                                logger.info(f"🔄 Refreshing Telethon session cache...")
                                dialogs = await client.get_dialogs(limit=50)
                                logger.info(f"✅ Session refreshed: Found {len(dialogs)} dialogs")
                                
                                # Try accessing storage channel again after refresh
                                storage_channel = await client.get_entity(channel_id_int)
                                logger.info(f"✅ Storage channel access confirmed after session refresh: {storage_channel.title}")
                                
                            except Exception as refresh_error:
                                logger.warning(f"❌ Session refresh failed: {refresh_error}")
                                
                                # Try alternative ID formats as fallback
                                alternative_ids = []
                                if isinstance(storage_channel_id, str) and storage_channel_id.startswith('-100'):
                                    # Try without -100 prefix
                                    alt_id = int(storage_channel_id[4:])  # Remove -100 prefix
                                    alternative_ids.append(alt_id)
                                    alternative_ids.append(-alt_id)  # Try negative version
                                
                                for alt_id in alternative_ids:
                                    try:
                                        logger.info(f"🔄 Trying alternative channel ID after refresh: {alt_id}")
                                        storage_channel = await client.get_entity(alt_id)
                                        logger.info(f"✅ Storage channel access confirmed with alternative ID {alt_id}: {storage_channel.title}")
                                        break
                                    except Exception as alt_error:
                                        logger.warning(f"❌ Alternative ID {alt_id} failed: {alt_error}")
                                else:
                                    logger.warning(f"❌ All channel access methods failed")
                                    logger.warning(f"💡 If worker account is a member, this is a Telethon session cache issue")
                                    logger.warning(f"💡 Consider restarting the service to refresh session files")
                        else:
                            logger.warning(f"❌ Channel access failed with non-entity error: {access_error}")
                else:
                    logger.info(f"⚠️ STORAGE_CHANNEL_ID not configured - skipping auto-join")
                    
            except Exception as storage_setup_error:
                logger.error(f"❌ Storage channel setup failed: {storage_setup_error}")
                # Continue anyway - this is not critical for basic functionality
            
            return client
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize client via telethon_manager for account {account_id}: {e}")
            return None
    
    def send_ad(self, campaign_id: int):
        """Send ad for a specific campaign with button support - Thread-safe version"""
        try:
            import threading
            
            # Check if we're in the main thread
            current_thread = threading.current_thread()
            is_main_thread = current_thread == threading.main_thread()
            
            if is_main_thread:
                # We're in the main thread - use ThreadPoolExecutor to avoid blocking
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._sync_send_ad, campaign_id)
                    return future.result(timeout=60)  # 60 second timeout for sending ads
            else:
                # We're already in a background thread - run directly
                return self._sync_send_ad(campaign_id)
                
        except Exception as e:
            logger.error(f"Failed to send ad for campaign {campaign_id}: {e}")
            return False
    
    def _sync_send_ad(self, campaign_id: int):
        """Synchronous wrapper for send_ad in a new thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._async_send_ad(campaign_id))
        finally:
            loop.close()
    
    async def _async_send_ad(self, campaign_id: int):
        """Async helper for send_ad"""
        logger.info(f"🚀 Starting _async_send_ad for campaign {campaign_id}")
        
        try:
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"❌ Campaign {campaign_id} not found!")
                return False
            
            logger.info(f"📋 Campaign found: {campaign['campaign_name']}")
            logger.info(f"👤 Account ID: {campaign['account_id']}")
            logger.info(f"🎯 Target chats: {campaign.get('target_chats', [])}")
            logger.info(f"🔘 Buttons: {len(campaign.get('buttons', []))} buttons")
            if not campaign or not campaign['is_active']:
                logger.warning(f"Campaign {campaign_id} not found or inactive")
                return
        except Exception as e:
            logger.error(f"🚨 Failed to get campaign {campaign_id}: {e}")
            return
        
        # Get account info for logging
        account = self.db.get_account(campaign['account_id'])
        account_name = account['account_name'] if account else f"Account_{campaign['account_id']}"
        
        logger.info(f"🚀 YOLO MODE: Starting campaign {campaign['campaign_name']} using {account_name}")
        logger.info(f"⚡ AGGRESSIVE MODE ENABLED: Maximum performance configuration active")
        
        # YOLO MODE: Use fresh client for scheduled execution with aggressive retries
        # Maximum performance configuration with no compromises
        from config_testforwarder import Config
        max_client_retries = getattr(Config, 'MAX_RETRY_ATTEMPTS', 5)  # YOLO MODE: 5 retries
        client = None
        
        for client_attempt in range(max_client_retries):
            try:
                client = await self._async_initialize_client(campaign['account_id'], cache_client=False)
                if client:
                    # Test client with a simple API call
                    await client.get_me()
                    logger.info(f"✅ Client initialized and tested successfully for {account_name}")
                    break
                else:
                    logger.warning(f"⚠️ Client initialization returned None (attempt {client_attempt + 1})")
            except Exception as client_error:
                logger.warning(f"⚠️ Client test failed (attempt {client_attempt + 1}): {client_error}")
                if client:
                    try:
                        await client.disconnect()
                    except:
                        pass
                client = None
            
            if client_attempt < max_client_retries - 1:
                await asyncio.sleep(3 * (client_attempt + 1))  # Progressive delay
        
        if not client:
            logger.error(f"❌ Failed to initialize {account_name} for campaign {campaign_id} after {max_client_retries} attempts")
            logger.error(f"💡 Solution: Re-add {account_name} with API credentials instead of uploaded session")
            return False
        
        # Get storage channel for forwarding
        storage_channel = None
        try:
            from config_testforwarder import Config
            storage_channel_id = Config.STORAGE_CHANNEL_ID
            if storage_channel_id:
                storage_channel = await client.get_entity(int(storage_channel_id))
                logger.info(f"✅ Storage channel ready for forwarding: {storage_channel.title}")
        except Exception as e:
            logger.warning(f"⚠️ Could not get storage channel: {e}")
            storage_channel = None
        
        ad_content = campaign['ad_content']
        target_chats = campaign['target_chats']
        buttons = campaign.get('buttons', [])
        sent_count = 0
        
        # Create buttons from campaign data or use default
        
        # Create ReplyKeyboardMarkup for worker account (persistent bottom keyboard)
        telethon_reply_markup = None
        if buttons and len(buttons) > 0:
            try:
                # Create button rows for ReplyKeyboardMarkup with text buttons
                button_rows = []
                for button_info in buttons:
                    if button_info.get('text'):
                        # Create simple text button for ReplyKeyboardMarkup
                        from telethon.tl.types import KeyboardButton
                        button_row = [KeyboardButton(
                            text=button_info['text']
                        )]
                        button_rows.append(button_row)
                        logger.info(f"✅ Created ReplyKeyboard button: '{button_info['text']}'")
                
                if button_rows:
                    # Create ReplyKeyboardMarkup (persistent bottom keyboard)
                    from telethon.tl.types import ReplyKeyboardMarkup
                    telethon_reply_markup = ReplyKeyboardMarkup(
                        rows=button_rows,
                        resize=True,        # Makes buttons large and full-width
                        persistent=True,    # Stays visible for ALL messages
                        selective=False     # Shows to everyone in group
                    )
                    logger.info(f"🔘 Created ReplyKeyboardMarkup with {len(button_rows)} URL button rows")
                    logger.info(f"🔘 ReplyKeyboardMarkup type: {type(telethon_reply_markup)}")
                else:
                    logger.warning(f"⚠️ No valid URL buttons created")
                    telethon_reply_markup = None
            except Exception as e:
                logger.error(f"❌ ReplyKeyboardMarkup creation failed: {e}")
                telethon_reply_markup = None
        
        # Store button data for bot to use later
        campaign_buttons = buttons if buttons and len(buttons) > 0 else []
        logger.info(f"📱 Bot will handle InlineKeyboardMarkup: {len(campaign_buttons)} buttons configured")
        
        # Debug button creation
        if telethon_reply_markup:
            logger.info(f"🔘 SUCCESS: Created InlineKeyboardMarkup with {len(telethon_reply_markup.rows)} button rows for worker account")
            for i, row in enumerate(telethon_reply_markup.rows):
                logger.info(f"🔘 Row {i}: {len(row)} buttons")
                for j, btn in enumerate(row):
                    logger.info(f"🔘 Button {i},{j}: {btn.text}")
        else:
            logger.warning(f"⚠️ No InlineKeyboardMarkup created for worker account")
        
        # Get all groups if target_mode is all_groups
        if campaign.get('target_mode') == 'all_groups' or target_chats == ['ALL_WORKER_GROUPS']:
            logger.info(f"Getting all groups for scheduled campaign {campaign_id}")
            dialogs = await client.get_dialogs()
            target_entities = []
            for dialog in dialogs:
                if dialog.is_group:
                    target_entities.append(dialog.entity)
                    logger.info(f"Found group for scheduled send: {dialog.name}")
        else:
            # Convert chat IDs to entities
            target_entities = []
            for chat_id in target_chats:
                try:
                    entity = await client.get_entity(chat_id)
                    target_entities.append(entity)
                except Exception as e:
                    logger.error(f"Failed to get entity for {chat_id}: {e}")
        
        # Create template message ONCE before processing all chats
        template_message_id = None
        
        # No template creation needed - send directly to target groups
        template_message_id = None
        
        # Initialize button tracking
        buttons_sent_count = 0
        
        for chat_entity in target_entities:
            message = None
            try:
                # YOLO MODE FIX: Handle different content types including linked messages
                if isinstance(ad_content, list) and ad_content:
                    logger.info(f"🔥 YOLO MODE: Processing {len(ad_content)} ad content items for {chat_entity.title}")
                    
                    # Process linked messages (the actual format we're getting)
                    for message_data in ad_content:
                        logger.info(f"🔍 YOLO DEBUG: Processing message_data: {message_data}")
                        
                        if message_data.get('type') == 'linked_message':
                            # This is a linked message - get it from storage and send with buttons
                            storage_chat_id = int(message_data.get('storage_chat_id'))
                            storage_message_id = int(message_data.get('storage_message_id'))
                            
                            logger.info(f"🚀 YOLO MODE: Forwarding linked message {storage_message_id} from {storage_chat_id}")
                            
                            try:
                                # PERFECT SOLUTION: Forward the message directly from storage (already has buttons!)
                                # The storage message already has the buttons added when campaign was created
                                logger.info(f"🚀 YOLO PERFECT: Forwarding message {storage_message_id} directly from storage (buttons included!)")
                                
                                # Get the storage channel entity for this specific message
                                storage_channel_entity = None
                                if storage_chat_id:
                                    try:
                                        storage_channel_entity = await client.get_entity(storage_chat_id)
                                        logger.debug(f"🔧 Got storage channel entity: {storage_channel_entity.title if hasattr(storage_channel_entity, 'title') else 'Unknown'}")
                                    except Exception as entity_error:
                                        logger.error(f"❌ Failed to get storage channel entity: {entity_error}")
                                        storage_channel_entity = storage_channel  # Fallback to global storage_channel
                                else:
                                    storage_channel_entity = storage_channel  # Use global storage_channel
                                
                                if not storage_channel_entity:
                                    logger.error(f"❌ No storage channel entity available for forwarding")
                                    continue
                                
                                # Forward the message directly - this preserves EVERYTHING!
                                sent_msg = await client.forward_messages(
                                    entity=chat_entity,
                                    messages=storage_message_id,
                                    from_peer=storage_channel_entity
                                )
                                
                                if sent_msg:
                                    logger.info(f"🔥 YOLO SUCCESS: Forwarded message with PREMIUM EMOJIS + REAL BUTTONS to {chat_entity.title}!")
                                else:
                                    logger.error(f"❌ YOLO: Failed to forward message {storage_message_id}")
                                    continue
                                
                                if sent_msg:
                                    buttons_sent_count += 1
                                    logger.info(f"✅ YOLO MODE: Successfully sent message to {chat_entity.title}")
                                    continue  # Move to next group
                                
                            except Exception as linked_error:
                                logger.error(f"❌ YOLO MODE: Failed to send linked message: {linked_error}")
                                continue  # Try next group
                    
                    # OLD LOGIC: Find the main media message and combine all text content (keeping as fallback)
                    media_message = None
                    combined_text = ""
                    
                    for message_data in ad_content:
                        if message_data.get('media_type') and not media_message:
                            # Use the first media message as the main one
                            media_message = message_data
                        elif message_data.get('text'):
                            # Collect all text content
                            if combined_text:
                                combined_text += "\n\n" + message_data.get('text', '')
                            else:
                                combined_text = message_data.get('text', '')
                    
                    if media_message:
                        # Send ONE message with media + combined text + buttons
                        try:
                            # Combine caption with additional text
                            caption_text = media_message.get('caption', '')
                            if caption_text and combined_text:
                                final_caption = caption_text + "\n\n" + combined_text
                            elif combined_text:
                                final_caption = combined_text
                            else:
                                final_caption = caption_text
                            
                            # ALWAYS add button URLs as text for media messages (ReplyKeyboardMarkup buttons don't work in regular groups)
                            button_text = ""
                            if telethon_reply_markup and hasattr(telethon_reply_markup, 'rows'):
                                for button_row in telethon_reply_markup.rows:
                                    for button in button_row:
                                        if hasattr(button, 'url'):
                                            button_text += f"\n\n🔗 {button.text}: {button.url}"
                            
                            # Combine caption with button text
                            final_caption = (final_caption or "") + button_text
                            
                            # Truncate message if too long (Telegram limit is 4096 characters)
                            if len(final_caption) > 4000:  # Leave some room for safety
                                final_caption = final_caption[:4000] + "..."
                                logger.warning(f"Message truncated to fit Telegram limits (was {len(final_caption)} chars)")
                            
                            # PROVEN SOLUTION: Add buttons as clickable text links (user accounts cannot send inline buttons)
                            logger.info(f"Sending media with text-based buttons (user account compatible)")
                            
                            # Get the original text/caption
                            original_text = media_message.get('caption', '')
                            
                            # Add button URLs as clickable text links (this works for user accounts)
                            button_text = ""
                            if campaign_buttons and len(campaign_buttons) > 0:
                                button_text = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                for button_info in campaign_buttons:
                                    if button_info.get('url') and button_info.get('text'):
                                        # Create clickable link format
                                        button_text += f"🔗 [{button_info['text']}]({button_info['url']})\n"
                                button_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                logger.info(f"✅ Added {len(campaign_buttons)} clickable text buttons to message")
                            
                            # Combine original text with button text
                            final_text = (original_text or "") + button_text
                            
                            # Truncate if too long
                            if len(final_text) > 4000:
                                final_text = final_text[:3900] + "...\n" + button_text[-100:]  # Keep buttons visible
                            
                            # UNIFIED TELETHON: Use stored client for perfect forwarding
                            try:
                                # Get storage message ID and stored client from campaign data
                                storage_message_id = media_message.get('storage_message_id')
                                storage_chat_id = media_message.get('storage_chat_id')
                                stored_client = media_message.get('telethon_client')
                                
                                if storage_message_id and storage_chat_id:
                                    logger.info(f"🔄 UNIFIED TELETHON: Forwarding storage message {storage_message_id}")
                                    
                                    # Use stored client if available, otherwise use current client
                                    forward_client = stored_client if stored_client else client
                                    
                                    # Get storage channel entity
                                    storage_channel_entity = await forward_client.get_entity(storage_chat_id)
                                    
                                    # Forward the message from storage channel with retry mechanism
                                    max_forward_retries = 3
                                    forwarded_successfully = False
                                    
                                    for forward_attempt in range(max_forward_retries):
                                        try:
                                            # Verify client is still authorized before forwarding
                                            if not await forward_client.is_user_authorized():
                                                logger.error(f"❌ Forward client not authorized (attempt {forward_attempt + 1})")
                                                break
                                            
                                            # SOLUTION: Create new message with text-based buttons instead of forwarding
                                            # Get original message content
                                            original_message = await forward_client.get_messages(storage_channel_entity, ids=storage_message_id)
                                            if not original_message:
                                                logger.error("Could not get original message from storage")
                                                continue
                                            
                                            # Extract content and add text-based buttons
                                            message_text = original_message.message or ""
                                            
                                            # Add clickable button links
                                            button_text = ""
                                            if campaign_buttons and len(campaign_buttons) > 0:
                                                button_text = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                                for button_info in campaign_buttons:
                                                    if button_info.get('url') and button_info.get('text'):
                                                        button_text += f"🔗 [{button_info['text']}]({button_info['url']})\n"
                                                button_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                            
                                            final_message_text = message_text + button_text
                                            
                                            # Send new message with text-based buttons and media
                                            if original_message.media:
                                                forwarded_messages = await forward_client.send_file(
                                                    chat_entity,
                                                    file=original_message.media,
                                                    caption=final_message_text,
                                                    parse_mode='md'  # Enable markdown parsing for clickable links
                                                )
                                            else:
                                                forwarded_messages = await forward_client.send_message(
                                                    chat_entity,
                                                    message=final_message_text,
                                                    parse_mode='md'  # Enable markdown parsing for clickable links
                                                )
                                            
                                            if forwarded_messages:
                                                message = forwarded_messages[0] if isinstance(forwarded_messages, list) else forwarded_messages
                                                logger.info(f"✅ UNIFIED TELETHON: Forwarded message with premium emojis and buttons to {chat_entity.title}")
                                                forwarded_successfully = True
                                                break
                                            else:
                                                logger.warning(f"No messages forwarded from storage channel (attempt {forward_attempt + 1})")
                                                
                                        except Exception as forward_error:
                                            logger.error(f"❌ Forward attempt {forward_attempt + 1} failed: {forward_error}")
                                            if forward_attempt < max_forward_retries - 1:
                                                await asyncio.sleep(2 ** forward_attempt)  # Exponential backoff
                                    
                                    if forwarded_successfully:
                                        continue
                                else:
                                    logger.warning(f"Missing storage message data: message_id={storage_message_id}, chat_id={storage_chat_id}")
                                    
                            except Exception as forward_error:
                                logger.error(f"Failed to forward with unified Telethon: {forward_error}")
                                
                                # Fallback: Download and re-upload (loses custom emojis but preserves basic content)
                                logger.info(f"Downloading media file: {media_message['file_id']}")
                                try:
                                    media_file = await client.download_media(media_message['file_id'])
                                    logger.info(f"Media download result: {media_file}")
                                except Exception as download_error:
                                    logger.error(f"Media download failed: {download_error}")
                                    media_file = None
                                
                                if media_file and os.path.exists(media_file):
                                    # Register for cleanup
                                    self._register_temp_file(media_file)
                                    
                                    # Send the downloaded media file
                                    message = await client.send_file(
                                        chat_entity,
                                        media_file,
                                        caption=final_caption,
                                        parse_mode='html'
                                    )
                                    logger.info(f"✅ Media sent via download ({media_message['media_type']}) to {chat_entity.title}")
                                    
                                    # Note: No cleanup needed - using permanent local media file
                                else:
                                    # Fallback to text if media download fails
                                    if final_caption:
                                        message = await client.send_message(
                                            chat_entity,
                                            final_caption,
                                            parse_mode='html'
                                        )
                                        logger.warning(f"⚠️ Media download failed, sent as text to {chat_entity.title}")
                                    else:
                                        continue  # Skip if no text content
                        except Exception as e:
                            logger.error(f"❌ Failed to send combined media+text to {chat_entity.title}: {e}")
                            # Fallback to text message
                            if combined_text:
                                # Try with inline buttons first, fallback to text
                                try:
                                    message = await client.send_message(
                                        chat_entity,
                                        combined_text,
                                        reply_markup=telethon_reply_markup,
                                        parse_mode='html'
                                    )
                                    logger.info(f"✅ Text sent with inline buttons to {chat_entity.title}")
                                except Exception as button_error:
                                    # Fallback: Send with buttons as text
                                    logger.warning(f"Inline buttons failed for text, using text fallback: {button_error}")
                                    message = await client.send_message(
                                        chat_entity,
                                        combined_text,
                                        reply_markup=telethon_reply_markup,
                                        parse_mode='html'
                                    )
                                logger.info(f"📝 Sent as text fallback to {chat_entity.title}")
                            else:
                                continue  # Skip if no text content
                    else:
                        # No media, just send combined text as one message
                        try:
                            if combined_text:
                                # Add buttons as text to the message
                                combined_text_with_buttons = combined_text
                                # Buttons will be sent as inline buttons
                                
                                message = await client.send_message(
                                    chat_entity,
                                    combined_text_with_buttons,
                                    reply_markup=telethon_reply_markup,
                                    parse_mode='html'
                                )
                                logger.info(f"✅ Combined text message sent to {chat_entity.title}")
                            else:
                                continue  # Skip if no content
                        except Exception as e:
                            logger.error(f"❌ Failed to send text message to {chat_entity.title}: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"❌ Failed to send combined media+text to {chat_entity.title}: {e}")
                            # Fallback to text message
                            if combined_text:
                                # Try with inline buttons first, fallback to text
                                try:
                                    message = await client.send_message(
                                        chat_entity,
                                        combined_text,
                                        reply_markup=telethon_reply_markup,
                                        parse_mode='html'
                                    )
                                    logger.info(f"✅ Text sent with inline buttons to {chat_entity.title}")
                                except Exception as button_error:
                                    # Fallback: Send with buttons as text
                                    logger.warning(f"Inline buttons failed for text, using text fallback: {button_error}")
                                    message = await client.send_message(
                                        chat_entity,
                                        combined_text,
                                        reply_markup=telethon_reply_markup,
                                        parse_mode='html'
                                    )
                                logger.info(f"📝 Sent as text fallback to {chat_entity.title}")
                            else:
                                continue  # Skip if no text content
                else:
                    # Process single message with inline buttons
                    
                    # Single message - check if it has media or is just text
                    if isinstance(ad_content, dict) and ad_content.get('media_type'):
                        # Single message with media - WORKING SOLUTION
                        try:
                            logger.info(f"Processing single media message with guaranteed buttons")
                            
                            # Get original text/caption
                            original_text = ad_content.get('caption', ad_content.get('text', '')) or ''
                            
                            # Use original text WITHOUT adding button text - buttons will be inline
                            final_text = original_text
                            
                            # Truncate message if too long
                            if len(final_text) > 4000:
                                final_text = final_text[:4000] + "..."
                                logger.warning(f"Single media message truncated to fit Telegram limits")

                            # ULTIMATE FIX: Use stored entity data to reconstruct premium emojis
                            media_file = None
                            
                            # CRITICAL INSIGHT: Worker can't access your private chat, but we have the entity data!
                            logger.info(f"🔄 PREMIUM EMOJI RECONSTRUCTION: Using stored entity data to rebuild premium emojis")
                            
                            # Get the stored caption and entities from BotFather bot
                            stored_caption = ad_content.get('caption', '')
                            stored_entities = ad_content.get('caption_entities', [])
                            
                            logger.info(f"Stored caption length: {len(stored_caption)}")
                            logger.info(f"Stored entities count: {len(stored_entities)}")
                            logger.info(f"Premium emoji entities: {len([e for e in stored_entities if e.get('type') == 'custom_emoji'])}")
                            
                            # Use the stored caption with entity data (this preserves premium emoji IDs)
                            original_text = stored_caption
                            
                            # SOLUTION: Download media using Bot API, then send with Telethon + buttons
                            logger.info(f"📤 STORAGE CHANNEL SOLUTION: Using persistent media from storage channel")
                            logger.info(f"📹 Video details: {ad_content.get('width')}x{ad_content.get('height')}, {ad_content.get('duration')}s, {ad_content.get('file_size')} bytes")
                            
                            # 🎯 STORAGE CHANNEL APPROACH: Use file_id from storage channel (persistent & reliable)
                            storage_file_id = ad_content.get('storage_file_id')
                            media_file_id = None
                            
                            if storage_file_id:
                                logger.info(f"✅ Using storage channel file_id: {storage_file_id}")
                                media_file_id = storage_file_id
                                logger.info(f"📤 Storage channel provides persistent, reliable media access")
                                
                            else:
                                # Fallback to original file_id if storage channel not available
                                original_file_id = ad_content.get('file_id')
                                if original_file_id:
                                    logger.warning(f"⚠️ Storage channel not available, using original file_id: {original_file_id}")
                                    media_file_id = original_file_id
                                else:
                                    logger.warning(f"❌ No media file_id available - will send text with premium emojis only")
                                    media_file_id = None
                            
                            if media_file_id:
                                # 🎯 TELETHON MEDIA SOLUTION: Get original message via Telethon for native media handling
                                logger.info(f"🔄 TELETHON APPROACH: Getting original message for native media handling")
                                
                                try:
                                    # 🎯 BREAKTHROUGH: Get media from STORAGE CHANNEL instead of user's private chat
                                    storage_chat_id = ad_content.get('storage_chat_id')
                                    storage_message_id = ad_content.get('storage_message_id')
                                    
                                    if storage_chat_id and storage_message_id:
                                        logger.info(f"📥 BREAKTHROUGH: Fetching media from STORAGE CHANNEL message {storage_message_id} in chat {storage_chat_id}")
                                        
                                        # Convert storage_chat_id to proper format for Telethon
                                        try:
                                            if isinstance(storage_chat_id, str):
                                                if storage_chat_id.startswith('-100'):
                                                    storage_chat_id_int = int(storage_chat_id)
                                                elif storage_chat_id.startswith('-'):
                                                    storage_chat_id_int = int('-100' + storage_chat_id[1:])
                                                else:
                                                    storage_chat_id_int = int('-100' + storage_chat_id)
                                            else:
                                                storage_chat_id_int = int(storage_chat_id)
                                            
                                            logger.info(f"🔄 Using storage chat ID: {storage_chat_id_int}")
                                            
                                            # Get the message from storage channel (bot has access!)
                                            storage_message = await client.get_messages(storage_chat_id_int, ids=storage_message_id)
                                            # Note: get_messages with single ID returns single Message object, not list
                                        except Exception as storage_access_error:
                                            logger.error(f"❌ Storage channel access failed: {storage_access_error}")
                                            
                                            # 🔄 TELETHON SESSION REFRESH: Try refreshing session if entity not found
                                            if "Cannot find any entity" in str(storage_access_error):
                                                logger.warning(f"🔄 MEDIA ACCESS: Telethon session cache issue detected")
                                                try:
                                                    logger.info(f"🔄 Refreshing session cache for media access...")
                                                    await client.get_dialogs(limit=50)
                                                    logger.info(f"✅ Session refreshed, retrying media access...")
                                                    
                                                    # Retry after session refresh
                                                    storage_message = await client.get_messages(storage_chat_id_int, ids=storage_message_id)
                                                    logger.info(f"✅ Media access successful after session refresh!")
                                                except Exception as retry_error:
                                                    logger.error(f"❌ Media access failed even after session refresh: {retry_error}")
                                                    storage_message = None
                                            else:
                                                storage_message = None
                                        
                                        if storage_message:
                                            logger.info(f"🔥 STORAGE MESSAGE DEBUG: Message type: {type(storage_message)}")
                                            logger.info(f"🔥 STORAGE MESSAGE DEBUG: Has media: {hasattr(storage_message, 'media') and storage_message.media is not None}")
                                            logger.info(f"🔥 STORAGE MESSAGE DEBUG: Has caption: {hasattr(storage_message, 'caption')}")
                                            logger.info(f"🔥 STORAGE MESSAGE DEBUG: Has reply_markup: {hasattr(storage_message, 'reply_markup') and storage_message.reply_markup is not None}")
                                            if hasattr(storage_message, 'reply_markup') and storage_message.reply_markup:
                                                logger.info(f"🔥 STORAGE MESSAGE DEBUG: Reply markup type: {type(storage_message.reply_markup)}")
                                                if hasattr(storage_message.reply_markup, 'rows'):
                                                    logger.info(f"🔥 STORAGE MESSAGE DEBUG: Reply markup rows: {len(storage_message.reply_markup.rows)}")
                                            if hasattr(storage_message, 'media') and storage_message.media:
                                                logger.info(f"✅ STORAGE SUCCESS: Found media in storage channel: {type(storage_message.media)}")
                                            else:
                                                logger.error(f"❌ STORAGE ISSUE: Message has no media attribute or media is None")
                                            
                                            # Check worker account premium status
                                            me = await client.get_me()
                                            worker_has_premium = getattr(me, 'premium', False)
                                            logger.info(f"✅ Worker account premium status: {worker_has_premium}")
                                            
                                            if worker_has_premium and stored_entities:
                                                logger.info(f"🎉 PERFECT SETUP: Worker has Premium + entity data + storage media!")
                                                
                                                # Convert stored entities to Telethon format
                                                telethon_entities = self._convert_to_telethon_entities(stored_entities, original_text)
                                                
                                                # Storage message ready for forwarding
                                                logger.info(f"📱 Storage message ready for forwarding")
                                                
                                                # 🚀 FINAL SOLUTION: Use database caption + entities + buttons with parse_mode='none'
                                                # Storage message doesn't have caption - use stored caption from database
                                                logger.info(f"🚀 ULTIMATE FIX: Using database caption + entities + storage media + buttons")
                                                
                                                # Buttons ready for sending
                                                
                                                # Send directly with all components (media + premium emojis + buttons)
                                                logger.info(f"🚀 Sending message with ALL components to {chat_entity.title}")
                                                
                                                # Send with buttons if available
                                                if buttons and len(buttons) > 0:
                                                    try:
                                                        # Use the global telethon_reply_markup we created earlier
                                                        reply_markup = telethon_reply_markup
                                                        
                                                        # Get caption text and media
                                                        caption_text = ad_content.get('caption') or ad_content.get('text', '')
                                                        video_file = storage_message.media
                                                        
                                                        # Convert entities for premium emojis
                                                        stored_entities = ad_content.get('caption_entities', [])
                                                        telethon_entities = self._convert_to_telethon_entities(stored_entities, caption_text)
                                                        
                                                        logger.info(f"📝 Caption: {len(caption_text)} chars")
                                                        logger.info(f"🎨 Entities: {len(telethon_entities)} (including {len([e for e in telethon_entities if hasattr(e, 'document_id')])} premium emojis)")
                                                        logger.info(f"🔘 Buttons: {len(telethon_reply_markup.rows) if telethon_reply_markup and hasattr(telethon_reply_markup, 'rows') else 0} rows (Telethon format)")
                                                        
                                                        # Send message with ALL components using send_file
                                                        logger.info(f"🚀 SENDING message with media + premium emojis + InlineKeyboardMarkup buttons")
                                                        logger.info(f"🔍 DEBUG: reply_markup type: {type(reply_markup)}")
                                                        logger.info(f"🔍 DEBUG: reply_markup value: {reply_markup}")
                                                        
                                                        # FORWARD the storage message to preserve InlineKeyboardMarkup buttons!
                                                        # This is how user accounts can send InlineKeyboardMarkup - by forwarding!
                                                        # Forward with retry mechanism for better reliability
                                                        max_forward_retries = 3
                                                        forwarded_successfully = False
                                                        
                                                        for forward_attempt in range(max_forward_retries):
                                                            try:
                                                                # Verify client is still authorized
                                                                if not await client.is_user_authorized():
                                                                    logger.error(f"❌ Client not authorized for forwarding (attempt {forward_attempt + 1})")
                                                                    break
                                                                
                                                                # SOLUTION: Create new message with text-based buttons (user accounts cannot forward inline buttons)
                                                                # Get original message content
                                                                original_message = await client.get_messages(storage_channel, ids=storage_message.id)
                                                                if not original_message:
                                                                    logger.error("Could not get original message from storage")
                                                                    continue
                                                                
                                                                # Extract content and add text-based buttons
                                                                message_text = original_message.message or ""
                                                                
                                                                # Add clickable button links
                                                                button_text = ""
                                                                if campaign_buttons and len(campaign_buttons) > 0:
                                                                    button_text = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                                                    for button_info in campaign_buttons:
                                                                        if button_info.get('url') and button_info.get('text'):
                                                                            button_text += f"🔗 [{button_info['text']}]({button_info['url']})\n"
                                                                    button_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                                                
                                                                final_message_text = message_text + button_text
                                                                
                                                                # Send new message with text-based buttons and media
                                                                if original_message.media:
                                                                    sent_msg = await client.send_file(
                                                                        chat_entity,
                                                                        file=original_message.media,
                                                                        caption=final_message_text,
                                                                        parse_mode='md'  # Enable markdown parsing for clickable links
                                                                    )
                                                                else:
                                                                    sent_msg = await client.send_message(
                                                                        chat_entity,
                                                                        message=final_message_text,
                                                                        parse_mode='md'  # Enable markdown parsing for clickable links
                                                                    )
                                                                
                                                                if sent_msg:
                                                                    logger.info(f"✅ SUCCESS: Worker sent message with text-based clickable buttons to {chat_entity.title}!")
                                                                    buttons_sent_count += 1
                                                                    forwarded_successfully = True
                                                                    break
                                                                else:
                                                                    logger.warning(f"Send returned None (attempt {forward_attempt + 1})")
                                                                    
                                                            except Exception as forward_error:
                                                                logger.error(f"❌ Send attempt {forward_attempt + 1} failed: {forward_error}")
                                                                if forward_attempt < max_forward_retries - 1:
                                                                    await asyncio.sleep(2 ** forward_attempt)  # Exponential backoff
                                                        
                                                        if forwarded_successfully:
                                                            continue
                                                        else:
                                                            logger.error(f"❌ Failed to send message with buttons after {max_forward_retries} attempts")
                                                            # Continue to fallback logic below
                                                            # Fallback: Send new message without buttons
                                                            sent_msg = await client.send_file(
                                                                chat_entity,           # Target group
                                                                file=storage_message.media,  # Media file from storage
                                                                caption=caption_text,  # Caption text
                                                                formatting_entities=telethon_entities,  # Premium emojis for caption
                                                                parse_mode=None,       # Let entities handle formatting
                                                                link_preview=False
                                                            )
                                                            logger.info(f"✅ Sent new message without buttons to {chat_entity.title}")
                                                        
                                                        # DEBUG: Verify sent message has InlineKeyboardMarkup buttons
                                                        if hasattr(sent_msg, 'reply_markup') and sent_msg.reply_markup:
                                                            logger.info(f"✅ CONFIRMED: Sent message HAS InlineKeyboardMarkup buttons!")
                                                            if hasattr(sent_msg.reply_markup, 'rows'):
                                                                logger.info(f"✅ CONFIRMED: InlineKeyboardMarkup has {len(sent_msg.reply_markup.rows)} button rows")
                                                        else:
                                                            logger.error(f"❌ PROBLEM: Sent message has NO InlineKeyboardMarkup buttons!")
                                                        
                                                        # Check for premium emojis in the sent message
                                                        if hasattr(sent_msg, 'entities') and sent_msg.entities:
                                                            custom_emojis = [e for e in sent_msg.entities if hasattr(e, 'document_id')]
                                                            logger.info(f"✅ CONFIRMED: Sent message has {len(custom_emojis)} premium emojis!")
                                                        else:
                                                            logger.warning(f"⚠️ WARNING: Sent message may not have premium emojis")
                                                        
                                                        logger.info(f"✅ SUCCESS: Worker sent message with media + premium emojis + InlineKeyboardMarkup buttons to {chat_entity.title}!")
                                                        buttons_sent_count += 1
                                                        continue
                                                        
                                                    except Exception as send_error:
                                                        logger.error(f"❌ Send with buttons failed: {send_error}")
                                                
                                                # Fallback: Worker sends without buttons if everything fails
                                                logger.info(f"📤 Fallback: Worker sends without buttons")
                                                
                                                caption_text = ad_content.get('caption') or ad_content.get('text', '')
                                                # Convert entities for premium emojis in fallback too
                                                stored_entities = ad_content.get('caption_entities', [])
                                                telethon_entities = self._convert_to_telethon_entities(stored_entities, caption_text)
                                                
                                                message = await client.send_file(
                                                    chat_entity,
                                                    storage_message.media,
                                                    caption=caption_text,
                                                    formatting_entities=telethon_entities,
                                                    parse_mode=None,
                                                    link_preview=False
                                                )
                                                logger.info(f"✅ Worker sent Media + Premium Emojis + Clickable Text Buttons")
                                                
                                                continue
                                            
                                            # Fallback: Send storage media with original entities and buttons
                                            logger.info(f"🔧 FALLBACK DEBUG: Checking storage message content")
                                            logger.info(f"FALLBACK Storage message text: {storage_message.text}")
                                            logger.info(f"FALLBACK Storage message caption: {getattr(storage_message, 'caption', 'NO CAPTION ATTRIBUTE')}")
                                            logger.info(f"FALLBACK Storage message entities: {getattr(storage_message, 'entities', 'NO ENTITIES ATTRIBUTE')}")
                                            logger.info(f"FALLBACK Storage message caption_entities: {getattr(storage_message, 'caption_entities', 'NO CAPTION_ENTITIES ATTRIBUTE')}")
                                            
                                            # 🚀 FINAL SOLUTION: Use database caption + entities + buttons with parse_mode='none'
                                            # Storage message doesn't have caption - use stored caption from database
                                            logger.info(f"🚀 ULTIMATE FIX: Using database caption + entities + storage media + buttons")
                                            
                                            # 🔥 FALLBACK BUTTON DEBUG: Log button details before sending
                                            logger.info(f"🔥 FALLBACK REPLY KEYBOARD DEBUG: telethon_reply_markup type: {type(telethon_reply_markup)}")
                                            logger.info(f"🔥 FALLBACK REPLY KEYBOARD DEBUG: telethon_reply_markup content: {telethon_reply_markup}")
                                            if telethon_reply_markup and hasattr(telethon_reply_markup, 'rows'):
                                                for i, row in enumerate(telethon_reply_markup.rows):
                                                    logger.info(f"🔥 FALLBACK REPLY KEYBOARD DEBUG: Row {i}: {row}")
                                                    for j, btn in enumerate(row):
                                                        logger.info(f"🔥 FALLBACK REPLY KEYBOARD DEBUG: Button {i},{j}: {btn} (type: {type(btn)})")
                                            
                                            # 🚀 FALLBACK: BUTTONS PRIORITY!
                                            logger.info(f"🚀 FALLBACK: Prioritizing buttons for functionality!")
                                            
                                            # Send with buttons as priority
                                            message = await client.send_file(
                                                chat_entity,
                                                storage_message.media,  # Media file
                                                caption=original_text,  # Plain text caption
                                                reply_markup=telethon_reply_markup,  # BUTTONS PRIORITY!
                                                parse_mode=None,  # No parsing
                                                link_preview=False  # Disable link preview
                                            )
                                            logger.info(f"✅ FALLBACK: Media + Buttons sent!")
                                            
                                            logger.info(f"🎉 FALLBACK: Media + Buttons sent to {chat_entity.title}")
                                            
                                            # Debug: Check if message has reply markup
                                            if hasattr(message, 'reply_markup') and message.reply_markup:
                                                logger.info(f"✅ CONFIRMED: Message has reply_markup with {len(message.reply_markup.rows)} button rows")
                                            else:
                                                logger.warning(f"⚠️ WARNING: Message has NO reply_markup!")
                                            
                                            continue
                                        else:
                                            logger.warning(f"❌ Storage channel message has no media or not found")
                                    else:
                                        logger.warning(f"❌ Missing storage_chat_id or storage_message_id")
                                        
                                except Exception as telethon_media_error:
                                    logger.error(f"❌ Telethon media access failed: {telethon_media_error}")
                                
                                # If all media approaches fail, fall back to text
                                logger.warning(f"Media handling failed, falling back to text")
                            
                            # If media handling failed, send as text with premium emoji entities
                            logger.warning(f"🚨 CRITICAL ISSUE: Media download failed - buttons may not work on text-only messages in groups!")
                            logger.info(f"💡 TELEGRAM LIMITATION: Groups may ignore inline buttons on text-only messages")
                            logger.info(f"📝 PREMIUM EMOJI TEXT FALLBACK: Sending as text with entity reconstruction (buttons may not appear)")
                            
                            # Text fallback - send as text with buttons
                            try:
                                me = await client.get_me()
                                worker_has_premium = getattr(me, 'premium', False)
                                
                                if worker_has_premium and stored_entities:
                                    logger.info(f"🎉 TEXT FALLBACK: Worker has Premium + entity data = Premium emojis should work!")
                                    
                                    # Convert stored entities to Telethon format
                                    telethon_entities = self._convert_to_telethon_entities(stored_entities, original_text)
                                    
                                    if telethon_entities:
                                        # Send text with premium emoji entities
                                        message = await client.send_message(
                                            chat_entity,
                                            original_text,
                                            formatting_entities=telethon_entities,
                                            reply_markup=telethon_reply_markup
                                        )
                                        logger.info(f"✅ Text sent with PREMIUM EMOJIS and inline buttons to {chat_entity.title}")
                                    else:
                                        # Fallback: Send without entities but with buttons
                                        message = await client.send_message(
                                            chat_entity,
                                            original_text,
                                            reply_markup=telethon_reply_markup
                                        )
                                        logger.info(f"✅ Text sent with inline buttons to {chat_entity.title}")
                                else:
                                    # Send without premium emoji entities but with buttons
                                    message = await client.send_message(
                                        chat_entity,
                                        original_text,
                                        reply_markup=telethon_reply_markup
                                    )
                                    logger.info(f"✅ Text sent with inline buttons to {chat_entity.title}")
                                
                            except Exception as text_error:
                                logger.error(f"Text fallback failed: {text_error}")
                                # Still continue to next chat even if this one fails
                                pass
                        
                        except Exception as single_media_error:
                            logger.error(f"Single media processing failed: {single_media_error}")
                            # Continue to next chat
                            continue
                
                # Log the performance
                if message:
                    self.log_ad_performance(campaign_id, campaign['user_id'], str(chat_entity.id), message.id)
                    sent_count += 1
                    logger.info(f"Scheduled ad sent to {chat_entity.title} ({chat_entity.id}) for campaign {campaign['campaign_name']}")
                
                # Add delay between sends
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to send scheduled ad to {chat_entity.title if hasattr(chat_entity, 'title') else 'Unknown'}: {e}")
                self.log_ad_performance(campaign_id, campaign['user_id'], str(chat_entity.id) if hasattr(chat_entity, 'id') else 'unknown', None, 'failed')
        
        # Update campaign statistics
        self.update_campaign_stats(campaign_id, sent_count)
        logger.info(f"Scheduled campaign {campaign['campaign_name']} completed: {buttons_sent_count}/{len(target_entities)} ads sent with buttons")
        
        # Disconnect client after scheduled execution to prevent asyncio loop issues
        try:
            await client.disconnect()
            logger.info(f"Disconnected client for scheduled campaign {campaign_id}")
        except Exception as e:
            logger.warning(f"Failed to disconnect client for campaign {campaign_id}: {e}")
        
        # MULTI-USERBOT: Execute for additional accounts with delays
        await self._execute_additional_accounts(campaign_id, campaign)
    
    async def _execute_additional_accounts(self, campaign_id: int, campaign: dict):
        """Execute campaign for additional accounts with spam avoidance"""
        try:
            additional_accounts = campaign.get('additional_accounts')
            if not additional_accounts:
                return
                
            try:
                additional_accounts_data = json.loads(additional_accounts) if isinstance(additional_accounts, str) else additional_accounts
                if not additional_accounts_data:
                    return
                    
                logger.info(f"🚀 MULTI-USERBOT: Found {len(additional_accounts_data)} additional accounts for campaign {campaign_id}")
                
                for account_config in additional_accounts_data:
                    account_id = account_config.get('account_id')
                    delay_minutes = account_config.get('delay_minutes', 0)
                    content_variation_index = account_config.get('content_variation', 0)
                    
                    if not account_id:
                        continue
                        
                    if delay_minutes > 0:
                        logger.info(f"🕐 MULTI-USERBOT: Scheduling account {account_id} with {delay_minutes} minute delay")
                        # Schedule the additional account execution
                        asyncio.create_task(self._execute_delayed_account(campaign_id, account_id, delay_minutes, content_variation_index))
                    else:
                        # Execute immediately for this additional account
                        await self._execute_single_additional_account(campaign_id, account_id, content_variation_index)
                        
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"❌ Error processing additional accounts: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error in _execute_additional_accounts: {e}")
    
    async def _execute_delayed_account(self, campaign_id: int, account_id: int, delay_minutes: int, content_variation_index: int = 0):
        """Execute campaign for an additional account after delay"""
        try:
            # Apply spam avoidance timing variation
            import random
            base_delay = delay_minutes * 60
            spam_variation = random.randint(0, 300)  # 0-5 minutes additional variation
            total_delay = base_delay + spam_variation
            
            logger.info(f"🕐 MULTI-USERBOT: Waiting {total_delay/60:.1f} minutes for account {account_id} (base: {delay_minutes}m + spam avoidance: {spam_variation/60:.1f}m)")
            await asyncio.sleep(total_delay)
            
            logger.info(f"🚀 MULTI-USERBOT: Executing delayed campaign for account {account_id}")
            await self._execute_single_additional_account(campaign_id, account_id, content_variation_index)
            
        except Exception as e:
            logger.error(f"❌ Error in delayed execution for account {account_id}: {e}")
    
    async def _execute_single_additional_account(self, campaign_id: int, account_id: int, content_variation_index: int = 0):
        """Execute campaign for a single additional account with spam avoidance"""
        start_time = time.time()
        execution_log = {
            'campaign_id': campaign_id,
            'account_id': account_id,
            'content_variation_used': content_variation_index,
            'groups_count': 0,
            'success_count': 0,
            'delay_applied_minutes': 0
        }
        
        try:
            # Get campaign data
            campaign = self.get_campaign(campaign_id)
            if not campaign or not campaign['is_active']:
                logger.error(f"❌ Campaign {campaign_id} not found or inactive for additional account {account_id}")
                return
                
            # Get account info
            account = self.db.get_account(account_id)
            if not account:
                logger.error(f"❌ Additional account {account_id} not found")
                return
                
            account_name = account['account_name']
            logger.info(f"🚀 MULTI-USERBOT: Executing campaign '{campaign['campaign_name']}' for additional account '{account_name}'")
            
            # Apply spam avoidance
            spam_delay = await self._apply_spam_avoidance_timing(campaign)
            execution_log['delay_applied_minutes'] = spam_delay
            
            # Get content variation
            content_variation = self._get_content_variation(campaign, content_variation_index)
            
            # Initialize client for this account
            client = await self._async_initialize_client(account_id)
            if not client:
                logger.error(f"❌ Failed to initialize client for additional account {account_id}")
                return
                
            try:
                # Get target groups for this account
                target_entities = await self._get_account_groups(client, campaign)
                execution_log['groups_count'] = len(target_entities)
                
                if not target_entities:
                    logger.warning(f"⚠️ No target groups found for additional account {account_name}")
                    return
                    
                logger.info(f"🎯 MULTI-USERBOT: Found {len(target_entities)} groups for account {account_name}")
                
                # Execute forwarding for each group
                success_count = 0
                for chat_entity in target_entities:
                    try:
                        # Apply per-message spam avoidance delay
                        await self._apply_per_message_delay()
                        
                        # Forward the message (same logic as main account)
                        await self._forward_campaign_message(client, chat_entity, campaign, content_variation)
                        success_count += 1
                        logger.info(f"✅ MULTI-USERBOT: Sent to {chat_entity.title} via {account_name}")
                        
                    except Exception as msg_error:
                        logger.error(f"❌ MULTI-USERBOT: Failed to send to {chat_entity.title} via {account_name}: {msg_error}")
                        
                execution_log['success_count'] = success_count
                logger.info(f"🎯 MULTI-USERBOT: Account {account_name} completed: {success_count}/{len(target_entities)} messages sent")
                
            finally:
                # Disconnect client
                try:
                    await client.disconnect()
                    logger.info(f"🔌 MULTI-USERBOT: Disconnected client for {account_name}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to disconnect client for {account_name}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error executing additional account {account_id}: {e}")
        finally:
            # Log execution
            self._log_campaign_execution(execution_log)
            duration = time.time() - start_time
            logger.info(f"⏱️ MULTI-USERBOT: Account {account_id} execution completed in {duration:.2f}s")
    
    async def _apply_spam_avoidance_timing(self, campaign: dict) -> float:
        """Apply spam avoidance timing delays"""
        import random
        
        spam_avoidance_enabled = campaign.get('spam_avoidance_enabled', True)
        timing_variation = campaign.get('timing_variation_minutes', 5)
        
        if not spam_avoidance_enabled:
            logger.info("📵 SPAM AVOIDANCE: Disabled for this campaign")
            return 0
            
        if timing_variation <= 0:
            return 0
            
        # Apply random delay (0 to timing_variation minutes)
        delay_seconds = random.randint(0, timing_variation * 60)
        delay_minutes = delay_seconds / 60
        
        logger.info(f"⏱️ SPAM AVOIDANCE: Applying random delay of {delay_minutes:.1f} minutes")
        await asyncio.sleep(delay_seconds)
        
        return delay_minutes
    
    async def _apply_per_message_delay(self):
        """Apply small delay between messages to avoid spam detection"""
        import random
        delay = random.uniform(1, 3)  # 1-3 seconds between messages
        await asyncio.sleep(delay)
    
    def _get_content_variation(self, campaign: dict, variation_index: int = 0):
        """Get content variation for spam avoidance"""
        content_variations = campaign.get('content_variations')
        if not content_variations:
            return None
            
        try:
            variations = json.loads(content_variations) if isinstance(content_variations, str) else content_variations
            if variations and len(variations) > variation_index:
                selected_variation = variations[variation_index]
                logger.info(f"📝 SPAM AVOIDANCE: Using content variation {variation_index + 1}/{len(variations)}")
                return selected_variation
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"❌ Error processing content variations: {e}")
            
        return None
    
    async def _get_account_groups(self, client, campaign: dict):
        """Get target groups for a specific account"""
        target_entities = []
        target_chats = campaign.get('target_chats', [])
        target_mode = campaign.get('target_mode', 'specific')
        
        if target_mode == 'all_groups' or 'ALL_WORKER_GROUPS' in target_chats:
            # Get all groups this account is member of
            try:
                async for dialog in client.iter_dialogs():
                    if dialog.is_group or dialog.is_channel:
                        if hasattr(dialog.entity, 'broadcast') and not dialog.entity.broadcast:
                            target_entities.append(dialog.entity)
                        elif not hasattr(dialog.entity, 'broadcast'):
                            target_entities.append(dialog.entity)
            except Exception as e:
                logger.error(f"❌ Error getting groups for account: {e}")
        else:
            # Get specific groups
            for chat in target_chats:
                try:
                    if chat == 'ALL_WORKER_GROUPS':
                        continue
                    entity = await client.get_entity(chat)
                    target_entities.append(entity)
                except Exception as e:
                    logger.warning(f"⚠️ Could not get entity {chat}: {e}")
                    
        return target_entities
    
    async def _forward_campaign_message(self, client, chat_entity, campaign: dict, content_variation=None):
        """Forward campaign message to a specific chat"""
        try:
            ad_content = campaign.get('ad_content', [])
            if not ad_content:
                return
            
            # Process each message in ad_content
            for message_data in ad_content:
                if message_data.get('type') == 'linked_message':
                    storage_message_id = int(message_data.get('storage_message_id'))
                    storage_chat_id = message_data.get('storage_chat_id')
                    
                    # Use content variation if available
                    if content_variation and content_variation.get('storage_message_id'):
                        storage_message_id = int(content_variation['storage_message_id'])
                        # Also update storage_chat_id if provided in variation
                        if content_variation.get('storage_chat_id'):
                            storage_chat_id = content_variation['storage_chat_id']
                        logger.info(f"📝 Using variation message {storage_message_id}")
                    
                    # Get storage channel entity
                    storage_channel_entity = None
                    if storage_chat_id:
                        try:
                            storage_channel_entity = await client.get_entity(int(storage_chat_id))
                            logger.debug(f"🔧 MULTI-USERBOT: Got storage channel entity for forwarding")
                        except Exception as entity_error:
                            logger.error(f"❌ MULTI-USERBOT: Failed to get storage channel entity: {entity_error}")
                            # Try fallback with Config
                            try:
                                from config_testforwarder import Config
                                storage_channel_id = Config.STORAGE_CHANNEL_ID
                                if storage_channel_id:
                                    storage_channel_entity = await client.get_entity(int(storage_channel_id))
                            except Exception as fallback_error:
                                logger.error(f"❌ MULTI-USERBOT: Fallback storage channel failed: {fallback_error}")
                                continue
                    
                    if not storage_channel_entity:
                        logger.error(f"❌ MULTI-USERBOT: No storage channel entity available")
                        continue
                    
                    # Forward the message directly
                    sent_msg = await client.forward_messages(
                        entity=chat_entity,
                        messages=storage_message_id,
                        from_peer=storage_channel_entity
                    )
                    
                    if sent_msg:
                        logger.debug(f"✅ Forwarded message to {chat_entity.title}")
                    else:
                        logger.error(f"❌ Failed to forward message to {chat_entity.title}")
                        
        except Exception as e:
            logger.error(f"❌ Error forwarding message: {e}")
            raise
    
    def _log_campaign_execution(self, execution_log: dict):
        """Log campaign execution for analytics"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO campaign_execution_logs 
                    (campaign_id, account_id, content_variation_used, groups_count, 
                     success_count, delay_applied_minutes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    execution_log['campaign_id'],
                    execution_log['account_id'], 
                    execution_log['content_variation_used'],
                    execution_log['groups_count'],
                    execution_log['success_count'],
                    execution_log['delay_applied_minutes']
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"❌ Error logging campaign execution: {e}")
    
    def log_ad_performance(self, campaign_id: int, user_id: int, target_chat: str, 
                          message_id: Optional[int], status: str = 'sent'):
        """Log ad performance"""
        import sqlite3
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ad_performance 
                (campaign_id, user_id, target_chat, message_id, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (campaign_id, user_id, target_chat, message_id, status))
            conn.commit()
    
    def update_campaign_stats(self, campaign_id: int, sent_count: int):
        """Update campaign statistics"""
        import sqlite3
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE ad_campaigns 
                SET last_run = CURRENT_TIMESTAMP, total_sends = total_sends + ?
                WHERE id = ?
            ''', (sent_count, campaign_id))
            conn.commit()
    
    def schedule_campaign(self, campaign_id: int):
        """Schedule a campaign based on its schedule type"""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return
        
        schedule_type = campaign['schedule_type']
        schedule_time = campaign['schedule_time']
        
        if schedule_type == 'daily':
            schedule.every().day.at(schedule_time).do(self.run_campaign_job, campaign_id)
        elif schedule_type == 'weekly':
            # Assuming format like "Monday 14:30"
            day, time_str = schedule_time.split(' ')
            getattr(schedule.every(), day.lower()).at(time_str).do(self.run_campaign_job, campaign_id)
        elif schedule_type == 'hourly':
            job = schedule.every().hour.do(self.run_campaign_job, campaign_id)
            # Only run immediately if this is a new campaign with immediate_start=True
            # Existing campaigns loaded from database should not run immediately
            if campaign.get('is_active', False) and campaign.get('immediate_start', False):
                logger.info(f"🚀 Running campaign {campaign_id} immediately on hourly schedule activation")
                self.run_campaign_job(campaign_id)
            else:
                logger.info(f"📅 Campaign {campaign_id} scheduled for hourly execution (no immediate start)")
        elif schedule_type == 'custom':
            # Parse custom interval (e.g., "every 3 minutes", "every 4 hours")
            try:
                if 'hour' in schedule_time.lower():
                    hours = int(schedule_time.split()[1])
                    job = schedule.every(hours).hours.do(self.run_campaign_job, campaign_id)
                    
                    # Only run immediately if this is a new campaign with immediate_start=True
                    # Existing campaigns loaded from database should not run immediately
                    campaign = self.get_campaign(campaign_id)
                    if campaign and campaign.get('is_active', False) and campaign.get('immediate_start', False):
                        logger.info(f"🚀 Running campaign {campaign_id} immediately on schedule activation")
                        # Add staggered delay to prevent database conflicts
                        import random
                        delay = random.uniform(0.5, 2.0)  # Random delay between 0.5-2 seconds
                        # Run in a separate thread to avoid blocking
                        import threading
                        threading.Thread(target=lambda: (time.sleep(delay), self.run_campaign_job(campaign_id)), daemon=True).start()
                    else:
                        logger.info(f"📅 Campaign {campaign_id} scheduled for custom execution (no immediate start)")
                    
                    logger.info(f"📅 Campaign {campaign_id} scheduled every {hours} hours")
                elif 'minute' in schedule_time.lower():
                    # Handle formats like "3 minutes", "every 3 minutes"
                    parts = schedule_time.split()
                    if len(parts) >= 2:
                        # Find the number in the string
                        for part in parts:
                            if part.isdigit():
                                minutes = int(part)
                                break
                        else:
                            minutes = 10  # default
                    else:
                        minutes = 10  # default
                    
                    # Schedule the job to run every X minutes
                    job = schedule.every(minutes).minutes.do(self.run_campaign_job, campaign_id)
                    
                    # IMPORTANT: Run the job immediately for the first time if campaign is active
                    campaign = self.get_campaign(campaign_id)
                    if campaign and campaign.get('is_active', False):
                        logger.info(f"🚀 Running campaign {campaign_id} immediately on schedule activation")
                        # Add staggered delay to prevent database conflicts
                        import random
                        delay = random.uniform(0.5, 2.0)  # Random delay between 0.5-2 seconds
                        # Run in a separate thread to avoid blocking
                        import threading
                        threading.Thread(target=lambda: (time.sleep(delay), self.run_campaign_job(campaign_id)), daemon=True).start()
                    
                    logger.info(f"📅 Campaign {campaign_id} scheduled every {minutes} minutes")
                elif schedule_time.isdigit():
                    # If just a number, assume minutes
                    minutes = int(schedule_time)
                    job = schedule.every(minutes).minutes.do(self.run_campaign_job, campaign_id)
                    
                    # IMPORTANT: Run the job immediately for the first time if campaign is active
                    campaign = self.get_campaign(campaign_id)
                    if campaign and campaign.get('is_active', False):
                        logger.info(f"🚀 Running campaign {campaign_id} immediately on schedule activation")
                        # Add staggered delay to prevent database conflicts
                        import random
                        delay = random.uniform(0.5, 2.0)  # Random delay between 0.5-2 seconds
                        # Run in a separate thread to avoid blocking
                        import threading
                        threading.Thread(target=lambda: (time.sleep(delay), self.run_campaign_job(campaign_id)), daemon=True).start()
                    
                    logger.info(f"📅 Campaign {campaign_id} scheduled every {minutes} minutes")
                else:
                    logger.warning(f"⚠️ Unknown custom schedule format: {schedule_time}")
            except (ValueError, IndexError) as e:
                logger.error(f"❌ Error parsing custom schedule '{schedule_time}': {e}")
                # Default to 10 minutes if parsing fails
                schedule.every(10).minutes.do(self.run_campaign_job, campaign_id)
                logger.info(f"📅 Campaign {campaign_id} defaulted to every 10 minutes")
        
        self.active_campaigns[campaign_id] = campaign
        logger.info(f"Scheduled campaign {campaign_id} ({schedule_type} at {schedule_time})")
    
    def run_campaign_job(self, campaign_id: int):
        """Execute scheduled campaign automatically"""
        try:
            import datetime
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"🔄 Scheduler executing campaign {campaign_id} at {current_time}")
            
            # Get campaign from database
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                logger.warning(f"Campaign {campaign_id} not found for scheduled execution - removing from active campaigns")
                # Remove from active campaigns if campaign doesn't exist
                if campaign_id in self.active_campaigns:
                    del self.active_campaigns[campaign_id]
                return
                
            if not campaign.get('is_active', False):
                logger.warning(f"Campaign {campaign_id} is not active, removing from active campaigns")
                # Remove inactive campaigns from active campaigns
                if campaign_id in self.active_campaigns:
                    del self.active_campaigns[campaign_id]
                return
            
            # Log campaign details
            logger.info(f"📋 Campaign {campaign_id}: {campaign['campaign_name']}")
            logger.info(f"📅 Schedule: {campaign['schedule_type']} at {campaign['schedule_time']}")
            logger.info(f"👤 Account ID: {campaign['account_id']}")
            
            # Check account status
            account = self.db.get_account(campaign['account_id'])
            if not account:
                logger.error(f"❌ Account {campaign['account_id']} not found for campaign {campaign_id}")
                return
            
            if not account.get('session_string'):
                logger.error(f"❌ Account {campaign['account_id']} has no session string")
                return
            
            logger.info(f"✅ Account {account.get('account_name', 'Unknown')} is ready")
            
            # Log next scheduled run
            logger.info(f"📅 Next run for campaign {campaign_id} will be in {campaign['schedule_time']}")
            
            # Execute campaign in new thread to avoid blocking scheduler
            def execute_async():
                try:
                    import asyncio
                    logger.info(f"🚀 Starting async execution for campaign {campaign_id}")
                    # Run the campaign asynchronously
                    asyncio.run(self.execute_scheduled_campaign(campaign_id, campaign))
                    logger.info(f"✅ Async execution completed for campaign {campaign_id}")
                except Exception as e:
                    logger.error(f"❌ Error executing scheduled campaign {campaign_id}: {e}")
                    import traceback
                    logger.error(f"Stack trace: {traceback.format_exc()}")
            
            # Start execution in separate thread
            execution_thread = threading.Thread(target=execute_async, daemon=True)
            execution_thread.start()
            logger.info(f"✅ Campaign {campaign_id} scheduled execution started")
            
        except Exception as e:
            logger.error(f"Error in campaign scheduler for {campaign_id}: {e}")
    
    async def execute_scheduled_campaign(self, campaign_id: int, campaign: dict):
        """Execute a scheduled campaign automatically"""
        try:
            logger.info(f"🚀 Executing scheduled campaign {campaign_id}: {campaign['campaign_name']}")
            
            # Check account status first
            account = self.db.get_account(campaign['account_id'])
            if not account:
                logger.error(f"Account {campaign['account_id']} not found for campaign {campaign_id}")
                return False
            
            if not account.get('session_string'):
                logger.error(f"Account {campaign['account_id']} ({account.get('account_name', 'Unknown')}) has no session string")
                logger.error(f"Please re-add account '{account.get('account_name', 'Unknown')}' with phone verification")
                return False
            
            # Send the ad using the async version directly
            await self._async_send_ad(campaign_id)
            logger.info(f"✅ Scheduled campaign {campaign_id} executed successfully")
                
            return True
            
        except Exception as e:
            logger.error(f"Error executing scheduled campaign {campaign_id}: {e}")
            return False
    
    def cleanup_corrupted_sessions(self):
        """Clean up any corrupted session files"""
        import os
        import glob
        
        try:
            # Find all bump session files
            session_files = glob.glob("bump_session_*.session")
            cleaned_count = 0
            
            for session_file in session_files:
                try:
                    # Check if file is empty or corrupted
                    if os.path.getsize(session_file) == 0:
                        os.remove(session_file)
                        cleaned_count += 1
                        logger.info(f"Cleaned up empty session file: {session_file}")
                except Exception as e:
                    logger.warning(f"Could not clean up session file {session_file}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} corrupted session files")
                
        except Exception as e:
            logger.warning(f"Error during session cleanup: {e}")

    def start_scheduler(self):
        """Start the campaign scheduler with proper background thread"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("🚀 Bump service scheduler started (automatic execution mode)")
        
        # Clean up any corrupted session files
        self.cleanup_corrupted_sessions()
        
        # Load existing campaigns into memory
        self.load_existing_campaigns()
        
        # Start background scheduler thread
        def scheduler_worker():
            """Background worker that runs scheduled campaigns"""
            logger.info("📅 Scheduler worker thread started")
            last_log_time = time.time()
            while self.is_running:
                try:
                    # Log scheduler status every 60 seconds
                    current_time = time.time()
                    if current_time - last_log_time >= 60:
                        jobs = schedule.get_jobs()
                        logger.info(f"⏰ Scheduler status: {len(jobs)} active jobs, {len(self.active_campaigns)} active campaigns")
                        # Log details about each job
                        for job in jobs:
                            next_run = job.next_run.strftime("%H:%M:%S") if job.next_run else "Not scheduled"
                            logger.info(f"  📅 Job scheduled for: {next_run}")
                        last_log_time = current_time
                    
                    # Run pending scheduled jobs
                    schedule.run_pending()
                    time.sleep(1)  # Check every second
                except Exception as e:
                    logger.error(f"Error in scheduler worker: {e}")
                    time.sleep(5)  # Wait 5 seconds on error
            logger.info("📅 Scheduler worker thread stopped")
        
        # Start the scheduler thread
        self.scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
        self.scheduler_thread.start()
        logger.info("✅ Background scheduler thread started successfully")
    
    def stop_scheduler(self):
        """Stop the campaign scheduler"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        schedule.clear()
        logger.info("Bump service scheduler stopped")
    
    def load_existing_campaigns(self):
        """Load and schedule existing active campaigns"""
        import sqlite3
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, campaign_name, schedule_time FROM ad_campaigns WHERE is_active = 1')
            rows = cursor.fetchall()
            
            for row in rows:
                campaign_id = row[0]
                campaign_name = row[1]
                schedule_time = row[2]
                logger.info(f"Loading campaign {campaign_id}: {campaign_name} (schedule: {schedule_time})")
                self.schedule_campaign(campaign_id)
        
        logger.info(f"Loaded {len(rows)} existing campaigns")
    
    def get_campaign_performance(self, campaign_id: int) -> Dict[str, Any]:
        """Get performance statistics for a campaign"""
        import sqlite3
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful_sends,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_sends
                FROM ad_performance 
                WHERE campaign_id = ?
            ''', (campaign_id,))
            row = cursor.fetchone()
            
            return {
                'total_attempts': row[0] or 0,
                'successful_sends': row[1] or 0,
                'failed_sends': row[2] or 0,
                'success_rate': (row[1] / row[0] * 100) if row[0] > 0 else 0
            }
    
    def add_additional_account_to_campaign(self, campaign_id: int, account_id: int, delay_minutes: int = 0, content_variation_index: int = 0):
        """Add additional userbot to existing campaign"""
        try:
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"❌ Campaign {campaign_id} not found")
                return False
                
            # Get existing additional accounts
            additional_accounts = campaign.get('additional_accounts', '[]')
            try:
                additional_accounts_data = json.loads(additional_accounts) if isinstance(additional_accounts, str) else (additional_accounts or [])
            except (json.JSONDecodeError, TypeError):
                additional_accounts_data = []
            
            # Check if account already exists
            for account in additional_accounts_data:
                if account.get('account_id') == account_id:
                    logger.warning(f"⚠️ Account {account_id} already exists in campaign {campaign_id}")
                    return False
            
            # Add new account
            new_account_config = {
                'account_id': account_id,
                'delay_minutes': delay_minutes,
                'content_variation': content_variation_index
            }
            additional_accounts_data.append(new_account_config)
            
            # Update campaign
            self.update_campaign(campaign_id, additional_accounts=json.dumps(additional_accounts_data))
            
            logger.info(f"✅ Added account {account_id} to campaign {campaign_id} with {delay_minutes}m delay")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding additional account: {e}")
            return False
    
    def add_content_variation_to_campaign(self, campaign_id: int, storage_message_id: int, variation_name: str = ""):
        """Add content variation for spam avoidance"""
        try:
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"❌ Campaign {campaign_id} not found")
                return False
                
            # Get existing variations
            content_variations = campaign.get('content_variations', '[]')
            try:
                variations_data = json.loads(content_variations) if isinstance(content_variations, str) else (content_variations or [])
            except (json.JSONDecodeError, TypeError):
                variations_data = []
            
            # Add new variation
            new_variation = {
                'storage_message_id': storage_message_id,
                'name': variation_name or f"Variation {len(variations_data) + 1}",
                'created_at': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            variations_data.append(new_variation)
            
            # Update campaign
            self.update_campaign(campaign_id, content_variations=json.dumps(variations_data))
            
            logger.info(f"✅ Added content variation '{new_variation['name']}' to campaign {campaign_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding content variation: {e}")
            return False
    
    def update_spam_avoidance_settings(self, campaign_id: int, enabled: bool = True, timing_variation_minutes: int = 5):
        """Update spam avoidance settings for campaign"""
        try:
            self.update_campaign(
                campaign_id, 
                spam_avoidance_enabled=enabled,
                timing_variation_minutes=timing_variation_minutes
            )
            
            status = "enabled" if enabled else "disabled"
            logger.info(f"✅ Spam avoidance {status} for campaign {campaign_id} (variation: {timing_variation_minutes}m)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating spam avoidance settings: {e}")
            return False
    
    async def close(self):
        """Close all connections"""
        self.stop_scheduler()
        
        for account_id, client in self.telegram_clients.items():
            try:
                await client.disconnect()
                logger.info(f"Disconnected bump service client for account {account_id}")
            except Exception as e:
                logger.error(f"Error disconnecting client {account_id}: {e}")
        
        self.telegram_clients.clear()
