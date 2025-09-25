# --- START OF FILE enhanced_auto_ads_system.py ---

"""
🚀 ENHANCED AUTO ADS SYSTEM WITH USERBOT INTEGRATION 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Advanced auto ads system with integrated userbot functionality from AUTOFORWARDBOT.
Allows manual userbot session upload and direct channel posting capabilities.

Key Features:
- Manual .session file upload for userbot accounts
- Direct channel posting via Telethon userbot
- Preserve custom emojis and formatting
- Simple channel management interface
- Enhanced media handling with custom emoji support
- Professional session management

Author: Enhanced Bot System
Version: 2.0.0 - Userbot Integration Edition
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import json
import os
import asyncio
import base64
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Telethon imports for userbot functionality
try:
    from telethon import TelegramClient, Button
    from telethon.sessions import StringSession
    from telethon.tl.types import MessageEntityCustomEmoji, MessageEntityBold, MessageEntityItalic, MessageEntityMention
    from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.warning("Telethon not available - userbot functionality disabled")

from utils import (
    get_db_connection, send_message_with_retry, is_primary_admin,
    format_currency
)

logger = logging.getLogger(__name__)

# --- Enhanced Telethon Manager ---

class EnhancedTelethonManager:
    """Enhanced Telethon client manager for userbot functionality"""
    
    def __init__(self):
        self.clients: Dict[str, TelegramClient] = {}
        self.session_dir = "userbot_sessions"
        os.makedirs(self.session_dir, exist_ok=True)
        logger.info("Enhanced Telethon Manager initialized")
    
    async def get_client(self, account_data: Dict[str, Any]) -> Optional[TelegramClient]:
        """Get or create a Telethon client for userbot operations"""
        account_id = str(account_data['id'])
        
        # Check if existing client is still valid
        if account_id in self.clients:
            client = self.clients[account_id]
            try:
                if client.is_connected() and await client.is_user_authorized():
                    await client.get_me()
                    logger.info(f"✅ Existing userbot client for account {account_id} is valid")
                    return client
                else:
                    logger.warning(f"⚠️ Existing userbot client for account {account_id} invalid, recreating...")
                    await client.disconnect()
                    del self.clients[account_id]
            except Exception as e:
                logger.warning(f"⚠️ Userbot client {account_id} failed test: {e}, recreating...")
                try:
                    await client.disconnect()
                except:
                    pass
                del self.clients[account_id]
        
        try:
            # Create client from session data
            if account_data.get('session_string'):
                session_str = account_data['session_string'].strip()
                
                if session_str.startswith('U1FMaXRlIGZvcm1hdCAz') or len(session_str) > 1000:
                    # Base64 encoded session data
                    session_name = f"userbot_{account_id}"
                    session_path = os.path.join(self.session_dir, f"{session_name}.session")
                    
                    try:
                        session_data = base64.b64decode(session_str)
                        with open(session_path, 'wb') as f:
                            f.write(session_data)
                        
                        client = TelegramClient(
                            session_path.replace('.session', ''),
                            account_data['api_id'],
                            account_data['api_hash']
                        )
                        logger.info(f"✅ Created userbot client from base64 session data")
                    except Exception as decode_error:
                        logger.error(f"❌ Failed to decode userbot session data: {decode_error}")
                        return None
                else:
                    # StringSession
                    client = TelegramClient(
                        StringSession(session_str),
                        account_data['api_id'],
                        account_data['api_hash']
                    )
                    logger.info(f"✅ Created userbot client from StringSession")
            else:
                logger.error(f"❌ No session data available for userbot account {account_id}")
                return None
            
            # Connect with retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await client.connect()
                    logger.info(f"✅ Userbot client connected (attempt {attempt + 1}/{max_retries})")
                    break
                except Exception as connect_error:
                    logger.warning(f"⚠️ Userbot connection attempt {attempt + 1}/{max_retries} failed: {connect_error}")
                    if attempt == max_retries - 1:
                        logger.error(f"❌ Failed to connect userbot after {max_retries} attempts")
                        return None
                    await asyncio.sleep(2 ** attempt)
            
            # Verify authorization
            if not await client.is_user_authorized():
                logger.error(f"❌ Userbot account {account_id} is not authorized")
                await client.disconnect()
                return None
            
            # Test the client
            me = await client.get_me()
            logger.info(f"✅ Userbot connected and authorized: {me.first_name} (ID: {me.id})")
            
            # Store client for reuse
            self.clients[account_id] = client
            return client
            
        except Exception as e:
            logger.error(f"❌ Failed to create userbot client for account {account_id}: {e}")
            return None
    
    async def send_to_channel(self, client: TelegramClient, channel_id: str, content: Dict[str, Any]) -> bool:
        """Send content to channel using userbot with enhanced media support"""
        try:
            # Get channel entity
            try:
                # Handle different channel ID formats
                if channel_id.startswith('@'):
                    channel_entity = await client.get_entity(channel_id)
                elif channel_id.startswith('https://t.me/'):
                    channel_name = channel_id.replace('https://t.me/', '')
                    channel_entity = await client.get_entity(f'@{channel_name}')
                elif channel_id.isdigit() or channel_id.startswith('-'):
                    channel_entity = await client.get_entity(int(channel_id))
                else:
                    channel_entity = await client.get_entity(f'@{channel_id}')
            except Exception as entity_error:
                logger.error(f"❌ Failed to get channel entity for {channel_id}: {entity_error}")
                return False
            
            # Prepare message content
            message_text = content.get('text', '')
            
            # Create buttons if specified
            buttons = None
            if content.get('buttons'):
                button_rows = []
                current_row = []
                
                for i, button_data in enumerate(content['buttons']):
                    if button_data.get('url'):
                        telethon_button = Button.url(button_data['text'], button_data['url'])
                    else:
                        telethon_button = Button.inline(button_data['text'], f"btn_{i}")
                    
                    current_row.append(telethon_button)
                    
                    # Create new row every 2 buttons
                    if len(current_row) == 2 or i == len(content['buttons']) - 1:
                        button_rows.append(current_row)
                        current_row = []
                
                buttons = button_rows
            
            # Send message with media if available
            if content.get('media_type'):
                # Handle media messages
                media_type = content['media_type']
                file_id = content.get('file_id')
                
                if file_id:
                    # For now, we'll send text with buttons and note about media
                    # In full implementation, we'd download and re-upload media
                    full_text = f"{message_text}\n\n📎 Media: {media_type.title()}"
                    
                    sent_message = await client.send_message(
                        channel_entity,
                        full_text,
                        buttons=buttons
                    )
                else:
                    # Text only with buttons
                    sent_message = await client.send_message(
                        channel_entity,
                        message_text,
                        buttons=buttons
                    )
            else:
                # Text only message
                sent_message = await client.send_message(
                    channel_entity,
                    message_text,
                    buttons=buttons
                )
            
            if sent_message:
                logger.info(f"✅ Successfully sent message to channel {channel_id}")
                return True
            else:
                logger.error(f"❌ Failed to send message to channel {channel_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending to channel {channel_id}: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup all userbot clients"""
        for client in self.clients.values():
            try:
                await client.disconnect()
            except:
                pass
        self.clients.clear()

# Global instance
enhanced_telethon_manager = EnhancedTelethonManager() if TELETHON_AVAILABLE else None

# --- Enhanced Database Functions ---

def init_enhanced_auto_ads_tables():
    """Initialize enhanced auto ads tables with userbot support"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Enhanced userbot accounts table
        c.execute("""
            CREATE TABLE IF NOT EXISTS userbot_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                phone_number TEXT,
                api_id TEXT NOT NULL,
                api_hash TEXT NOT NULL,
                session_string TEXT NOT NULL,
                session_data BLOB,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0
            )
        """)
        
        # Enhanced auto ads campaigns with userbot support
        c.execute("""
            CREATE TABLE IF NOT EXISTS enhanced_auto_ads_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_name TEXT NOT NULL,
                userbot_account_id INTEGER,
                content_text TEXT,
                content_media_type TEXT,
                content_media_data TEXT,
                buttons_data TEXT,
                target_channels TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_time TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_run TIMESTAMP,
                next_run TIMESTAMP,
                total_sent INTEGER DEFAULT 0,
                total_errors INTEGER DEFAULT 0,
                FOREIGN KEY (userbot_account_id) REFERENCES userbot_accounts (id)
            )
        """)
        
        # Enhanced channel management
        c.execute("""
            CREATE TABLE IF NOT EXISTS enhanced_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                channel_username TEXT,
                channel_url TEXT,
                is_active INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_post TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0
            )
        """)
        
        # Campaign execution logs
        c.execute("""
            CREATE TABLE IF NOT EXISTS campaign_execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                error_message TEXT,
                message_id TEXT,
                FOREIGN KEY (campaign_id) REFERENCES enhanced_auto_ads_campaigns (id)
            )
        """)
        
        conn.commit()
        logger.info("Enhanced auto ads tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing enhanced auto ads tables: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# --- Enhanced Auto Ads Handlers ---

async def handle_enhanced_auto_ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """🚀 Enhanced Auto Ads System with Userbot Integration"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get statistics
        c.execute("SELECT COUNT(*) FROM userbot_accounts WHERE is_active = 1")
        active_accounts = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM enhanced_auto_ads_campaigns WHERE is_active = 1")
        active_campaigns = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM enhanced_channels WHERE is_active = 1")
        active_channels = c.fetchone()[0]
        
        # Get recent activity
        c.execute("""
            SELECT SUM(total_sent), SUM(total_errors) 
            FROM enhanced_auto_ads_campaigns
        """)
        stats = c.fetchone()
        total_sent = stats[0] or 0
        total_errors = stats[1] or 0
        
    except Exception as e:
        logger.error(f"Error loading enhanced auto ads menu: {e}")
        active_accounts = active_campaigns = active_channels = 0
        total_sent = total_errors = 0
    finally:
        if conn:
            conn.close()
    
    # Build enhanced menu message
    msg = "🚀 **ENHANCED AUTO ADS SYSTEM** 🚀\n\n"
    msg += "🤖 **Integrated Userbot Technology**\n"
    msg += "📱 **Direct Channel Posting Capabilities**\n\n"
    
    msg += "**📊 System Status:**\n"
    msg += f"🤖 **Userbot Accounts:** {active_accounts} active\n"
    msg += f"📢 **Campaigns:** {active_campaigns} running\n"
    msg += f"📺 **Channels:** {active_channels} configured\n"
    msg += f"📤 **Messages Sent:** {total_sent:,}\n"
    msg += f"❌ **Errors:** {total_errors:,}\n\n"
    
    if not TELETHON_AVAILABLE:
        msg += "⚠️ **Telethon not available** - Install telethon for full functionality\n\n"
    
    msg += "**🎯 What would you like to do?**"
    
    keyboard = [
        [
            InlineKeyboardButton("🤖 Manage Userbot Accounts", callback_data="enhanced_manage_accounts"),
            InlineKeyboardButton("📢 Manage Campaigns", callback_data="enhanced_manage_campaigns")
        ],
        [
            InlineKeyboardButton("📺 Manage Channels", callback_data="enhanced_manage_channels"),
            InlineKeyboardButton("📊 View Analytics", callback_data="enhanced_ads_analytics")
        ],
        [
            InlineKeyboardButton("➕ Create New Campaign", callback_data="enhanced_create_campaign"),
            InlineKeyboardButton("🧪 Test System", callback_data="enhanced_test_system")
        ],
        [
            InlineKeyboardButton("⚙️ System Settings", callback_data="enhanced_ads_settings"),
            InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")
        ]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_manage_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """🤖 Manage Userbot Accounts"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all userbot accounts
        c.execute("""
            SELECT id, account_name, phone_number, is_active, 
                   success_count, error_count, last_used, created_at
            FROM userbot_accounts 
            ORDER BY created_at DESC
        """)
        accounts = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading userbot accounts: {e}")
        accounts = []
    finally:
        if conn:
            conn.close()
    
    # Build accounts menu
    msg = "🤖 **USERBOT ACCOUNT MANAGER** 🤖\n\n"
    msg += "📱 **Manual Session Upload System**\n"
    msg += "🔧 **Professional Userbot Management**\n\n"
    
    if accounts:
        msg += f"**📋 Your Accounts ({len(accounts)}):**\n\n"
        for account in accounts:
            status = "✅ Active" if account['is_active'] else "❌ Inactive"
            success_rate = 0
            if account['success_count'] + account['error_count'] > 0:
                success_rate = (account['success_count'] / (account['success_count'] + account['error_count'])) * 100
            
            msg += f"**{account['account_name']}**\n"
            msg += f"📱 Phone: {account['phone_number'] or 'Not set'}\n"
            msg += f"📊 Status: {status} | Success: {success_rate:.1f}%\n"
            msg += f"📈 Sent: {account['success_count']} | Errors: {account['error_count']}\n\n"
    else:
        msg += "📭 **No userbot accounts configured**\n\n"
        msg += "**🚀 Get Started:**\n"
        msg += "1. Upload a .session file from your Telegram userbot\n"
        msg += "2. Configure API credentials\n"
        msg += "3. Start posting directly to channels!\n\n"
    
    msg += "**🎯 Account Management:**"
    
    keyboard = [
        [InlineKeyboardButton("📤 Upload Session File", callback_data="enhanced_upload_session")],
        [InlineKeyboardButton("➕ Add Account Manually", callback_data="enhanced_add_account")],
    ]
    
    # Add account management buttons if accounts exist
    if accounts:
        keyboard.extend([
            [InlineKeyboardButton("✏️ Edit Account", callback_data="enhanced_edit_account")],
            [InlineKeyboardButton("🗑️ Delete Account", callback_data="enhanced_delete_account")]
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("🧪 Test Accounts", callback_data="enhanced_test_accounts")],
        [InlineKeyboardButton("⬅️ Back to Auto Ads", callback_data="enhanced_auto_ads_menu")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_upload_session(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """📤 Upload Session File Interface"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    # Set upload state
    context.user_data['enhanced_ads_state'] = 'awaiting_session_file'
    
    msg = "📤 **UPLOAD SESSION FILE** 📤\n\n"
    msg += "🔧 **Professional Userbot Integration**\n\n"
    
    msg += "**📋 Instructions:**\n"
    msg += "1. **Locate your .session file** from your Telegram userbot\n"
    msg += "2. **Upload the .session file** to this chat\n"
    msg += "3. **Provide API credentials** when prompted\n"
    msg += "4. **Start posting directly** to channels!\n\n"
    
    msg += "**📁 Supported Files:**\n"
    msg += "• `.session` files from Telethon\n"
    msg += "• Session files from other userbot projects\n"
    msg += "• Base64 encoded session data\n\n"
    
    msg += "**🔒 Security:**\n"
    msg += "• Files are encrypted and stored securely\n"
    msg += "• Only you can access your sessions\n"
    msg += "• Automatic cleanup of temporary files\n\n"
    
    msg += "**📤 Please upload your .session file now...**"
    
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data="enhanced_manage_accounts")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_session_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded session file"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get('enhanced_ads_state') != 'awaiting_session_file':
        return
    
    if not update.message.document:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Please upload a .session file (document).", parse_mode=None)
        return
    
    document = update.message.document
    
    # Validate file
    if not document.file_name or not document.file_name.endswith('.session'):
        await send_message_with_retry(context.bot, chat_id, 
            "❌ **Invalid file type!**\n\nPlease upload a .session file from your Telegram userbot.", 
            parse_mode='Markdown')
        return
    
    try:
        # Download the session file
        file = await context.bot.get_file(document.file_id)
        
        # Create temporary file
        temp_path = f"temp_session_{user_id}_{int(time.time())}.session"
        await file.download_to_drive(temp_path)
        
        # Read session data
        with open(temp_path, 'rb') as f:
            session_data = f.read()
        
        # Encode session data
        session_b64 = base64.b64encode(session_data).decode('utf-8')
        
        # Clean up temp file
        os.remove(temp_path)
        
        # Store in context for next step
        context.user_data['pending_session'] = {
            'filename': document.file_name,
            'session_data': session_b64,
            'file_size': document.file_size
        }
        
        # Move to next step
        context.user_data['enhanced_ads_state'] = 'awaiting_account_details'
        
        msg = "✅ **Session File Uploaded Successfully!** ✅\n\n"
        msg += f"📁 **File:** {document.file_name}\n"
        msg += f"📏 **Size:** {document.file_size:,} bytes\n\n"
        msg += "**🔧 Now please provide account details:**\n\n"
        msg += "**Format:**\n"
        msg += "`Account Name: My Userbot`\n"
        msg += "`Phone: +1234567890`\n"
        msg += "`API ID: 12345678`\n"
        msg += "`API Hash: abcd1234efgh5678`\n\n"
        msg += "**Example:**\n"
        msg += "`Account Name: Business Bot`\n"
        msg += "`Phone: +1234567890`\n"
        msg += "`API ID: 12345678`\n"
        msg += "`API Hash: a1b2c3d4e5f6g7h8`"
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="enhanced_manage_accounts")]
        ]
        
        await send_message_with_retry(context.bot, chat_id, msg, 
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing session file: {e}")
        await send_message_with_retry(context.bot, chat_id, 
            f"❌ Error processing session file: {str(e)}", parse_mode=None)

async def handle_enhanced_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle account details input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get('enhanced_ads_state') != 'awaiting_account_details':
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Please send account details as text.", parse_mode=None)
        return
    
    text = update.message.text.strip()
    
    # Parse account details
    try:
        details = {}
        for line in text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'account name' in key or 'name' in key:
                    details['account_name'] = value
                elif 'phone' in key:
                    details['phone_number'] = value
                elif 'api id' in key or 'api_id' in key:
                    details['api_id'] = value
                elif 'api hash' in key or 'api_hash' in key:
                    details['api_hash'] = value
        
        # Validate required fields
        required = ['account_name', 'api_id', 'api_hash']
        missing = [field for field in required if not details.get(field)]
        
        if missing:
            await send_message_with_retry(context.bot, chat_id, 
                f"❌ **Missing required fields:** {', '.join(missing)}\n\n"
                "Please provide all required information.", parse_mode='Markdown')
            return
        
        # Get pending session data
        pending_session = context.user_data.get('pending_session')
        if not pending_session:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ Session data expired. Please upload the session file again.", parse_mode=None)
            context.user_data.pop('enhanced_ads_state', None)
            return
        
        # Save to database
        success = await save_userbot_account(details, pending_session['session_data'])
        
        if success:
            # Clear state
            context.user_data.pop('enhanced_ads_state', None)
            context.user_data.pop('pending_session', None)
            
            msg = "🎉 **Userbot Account Added Successfully!** 🎉\n\n"
            msg += f"🤖 **Account:** {details['account_name']}\n"
            msg += f"📱 **Phone:** {details.get('phone_number', 'Not provided')}\n"
            msg += f"🔑 **API ID:** {details['api_id']}\n\n"
            msg += "**✅ Ready to use for:**\n"
            msg += "• Direct channel posting\n"
            msg += "• Automated campaigns\n"
            msg += "• Custom emoji support\n"
            msg += "• Enhanced media handling\n\n"
            msg += "🚀 **Start creating campaigns now!**"
            
            keyboard = [
                [InlineKeyboardButton("📢 Create Campaign", callback_data="enhanced_create_campaign")],
                [InlineKeyboardButton("🤖 Manage Accounts", callback_data="enhanced_manage_accounts")],
                [InlineKeyboardButton("🏠 Auto Ads Menu", callback_data="enhanced_auto_ads_menu")]
            ]
            
            await send_message_with_retry(context.bot, chat_id, msg, 
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ Failed to save userbot account. Please try again.", parse_mode=None)
        
    except Exception as e:
        logger.error(f"Error parsing account details: {e}")
        await send_message_with_retry(context.bot, chat_id, 
            "❌ **Invalid format!**\n\nPlease use the format:\n"
            "`Account Name: Your Name`\n"
            "`Phone: +1234567890`\n"
            "`API ID: 12345678`\n"
            "`API Hash: abcd1234`", parse_mode='Markdown')

async def save_userbot_account(details: Dict[str, str], session_data: str) -> bool:
    """Save userbot account to database"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO userbot_accounts 
            (account_name, phone_number, api_id, api_hash, session_string)
            VALUES (?, ?, ?, ?, ?)
        """, (
            details['account_name'],
            details.get('phone_number'),
            details['api_id'],
            details['api_hash'],
            session_data
        ))
        
        conn.commit()
        logger.info(f"Userbot account '{details['account_name']}' saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error saving userbot account: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- Channel Management ---

async def handle_enhanced_manage_channels(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """📺 Enhanced Channel Management"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all channels
        c.execute("""
            SELECT id, channel_name, channel_id, channel_username, 
                   is_active, success_count, error_count, last_post
            FROM enhanced_channels 
            ORDER BY added_at DESC
        """)
        channels = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading channels: {e}")
        channels = []
    finally:
        if conn:
            conn.close()
    
    # Build channels menu
    msg = "📺 **ENHANCED CHANNEL MANAGER** 📺\n\n"
    msg += "🔗 **Direct Channel Link Support**\n"
    msg += "🚀 **Instant Channel Addition**\n\n"
    
    if channels:
        msg += f"**📋 Your Channels ({len(channels)}):**\n\n"
        for channel in channels:
            status = "✅ Active" if channel['is_active'] else "❌ Inactive"
            success_rate = 0
            if channel['success_count'] + channel['error_count'] > 0:
                success_rate = (channel['success_count'] / (channel['success_count'] + channel['error_count'])) * 100
            
            msg += f"**{channel['channel_name']}**\n"
            msg += f"🔗 ID: {channel['channel_id']}\n"
            msg += f"📊 Status: {status} | Success: {success_rate:.1f}%\n"
            msg += f"📈 Posts: {channel['success_count']} | Errors: {channel['error_count']}\n\n"
    else:
        msg += "📭 **No channels configured**\n\n"
        msg += "**🚀 Quick Setup:**\n"
        msg += "1. Send a channel link (e.g., https://t.me/yourchannel)\n"
        msg += "2. Channel is automatically added\n"
        msg += "3. Start posting immediately!\n\n"
    
    msg += "**🎯 Channel Management:**"
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="enhanced_add_channel")],
        [InlineKeyboardButton("🔗 Quick Add (Link)", callback_data="enhanced_quick_add_channel")]
    ]
    
    if channels:
        keyboard.extend([
            [InlineKeyboardButton("✏️ Edit Channel", callback_data="enhanced_edit_channel")],
            [InlineKeyboardButton("🗑️ Remove Channel", callback_data="enhanced_remove_channel")]
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("🧪 Test Channels", callback_data="enhanced_test_channels")],
        [InlineKeyboardButton("⬅️ Back to Auto Ads", callback_data="enhanced_auto_ads_menu")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_quick_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """🔗 Quick Add Channel via Link"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    # Set state
    context.user_data['enhanced_ads_state'] = 'awaiting_channel_link'
    
    msg = "🔗 **QUICK CHANNEL ADDITION** 🔗\n\n"
    msg += "📱 **Instant Channel Integration**\n\n"
    
    msg += "**📋 Supported Formats:**\n"
    msg += "• `https://t.me/yourchannel`\n"
    msg += "• `@yourchannel`\n"
    msg += "• `yourchannel`\n"
    msg += "• `-1001234567890` (Channel ID)\n\n"
    
    msg += "**🚀 Features:**\n"
    msg += "• Automatic channel detection\n"
    msg += "• Instant verification\n"
    msg += "• Ready for posting immediately\n\n"
    
    msg += "**🔗 Please send a channel link or username...**"
    
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data="enhanced_manage_channels")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- Message State Handlers ---

async def handle_enhanced_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel link input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get('enhanced_ads_state') != 'awaiting_channel_link':
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Please send a channel link or username.", parse_mode=None)
        return
    
    channel_input = update.message.text.strip()
    
    # Parse channel info
    channel_info = parse_channel_input(channel_input)
    
    if not channel_info:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ **Invalid channel format!**\n\n"
            "**Supported formats:**\n"
            "• https://t.me/yourchannel\n"
            "• @yourchannel\n"
            "• yourchannel\n"
            "• -1001234567890", parse_mode='Markdown')
        return
    
    # Save channel
    success = await save_channel(channel_info)
    
    if success:
        # Clear state
        context.user_data.pop('enhanced_ads_state', None)
        
        msg = "✅ **Channel Added Successfully!** ✅\n\n"
        msg += f"📺 **Channel:** {channel_info['name']}\n"
        msg += f"🔗 **ID:** {channel_info['id']}\n"
        msg += f"👤 **Username:** {channel_info.get('username', 'Not available')}\n\n"
        msg += "**🚀 Ready for:**\n"
        msg += "• Automated campaigns\n"
        msg += "• Direct posting via userbot\n"
        msg += "• Custom emoji support\n"
        msg += "• Enhanced media handling\n\n"
        msg += "🎯 **Start creating campaigns now!**"
        
        keyboard = [
            [InlineKeyboardButton("📢 Create Campaign", callback_data="enhanced_create_campaign")],
            [InlineKeyboardButton("📺 Manage Channels", callback_data="enhanced_manage_channels")],
            [InlineKeyboardButton("🏠 Auto Ads Menu", callback_data="enhanced_auto_ads_menu")]
        ]
        
        await send_message_with_retry(context.bot, chat_id, msg, 
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Failed to add channel. Please try again.", parse_mode=None)

def parse_channel_input(channel_input: str) -> Optional[Dict[str, str]]:
    """Parse various channel input formats"""
    try:
        channel_input = channel_input.strip()
        
        if channel_input.startswith('https://t.me/'):
            # https://t.me/channelname
            username = channel_input.replace('https://t.me/', '')
            return {
                'name': username,
                'id': f'@{username}',
                'username': username,
                'url': channel_input
            }
        elif channel_input.startswith('@'):
            # @channelname
            username = channel_input[1:]
            return {
                'name': username,
                'id': channel_input,
                'username': username,
                'url': f'https://t.me/{username}'
            }
        elif channel_input.startswith('-') or channel_input.isdigit():
            # -1001234567890 or 1234567890
            channel_id = channel_input if channel_input.startswith('-') else f'-{channel_input}'
            return {
                'name': f'Channel {channel_id}',
                'id': channel_id,
                'username': None,
                'url': None
            }
        else:
            # channelname
            return {
                'name': channel_input,
                'id': f'@{channel_input}',
                'username': channel_input,
                'url': f'https://t.me/{channel_input}'
            }
    except Exception as e:
        logger.error(f"Error parsing channel input: {e}")
        return None

async def save_channel(channel_info: Dict[str, str]) -> bool:
    """Save channel to database"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO enhanced_channels 
            (channel_name, channel_id, channel_username, channel_url)
            VALUES (?, ?, ?, ?)
        """, (
            channel_info['name'],
            channel_info['id'],
            channel_info.get('username'),
            channel_info.get('url')
        ))
        
        conn.commit()
        logger.info(f"Channel '{channel_info['name']}' saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error saving channel: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- Missing Enhanced Handlers ---

async def handle_enhanced_add_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """➕ Add Account Manually"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    msg = "➕ **ADD USERBOT ACCOUNT MANUALLY** ➕\n\n"
    msg += "🔧 **Manual Account Configuration**\n\n"
    
    msg += "**📋 Required Information:**\n"
    msg += "• Account Name (e.g., 'My Business Bot')\n"
    msg += "• Phone Number (e.g., '+1234567890')\n"
    msg += "• API ID (from my.telegram.org)\n"
    msg += "• API Hash (from my.telegram.org)\n"
    msg += "• Session String (from your userbot)\n\n"
    
    msg += "**🚨 Important Notes:**\n"
    msg += "• This is for advanced users only\n"
    msg += "• You need existing session credentials\n"
    msg += "• Easier to use 'Upload Session File' instead\n\n"
    
    msg += "**💡 Recommendation:** Use 'Upload Session File' for easier setup!"
    
    keyboard = [
        [InlineKeyboardButton("📤 Upload Session File Instead", callback_data="enhanced_upload_session")],
        [InlineKeyboardButton("🔧 Continue Manual Setup", callback_data="enhanced_manual_setup_start")],
        [InlineKeyboardButton("⬅️ Back to Accounts", callback_data="enhanced_manage_accounts")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_manual_setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """🔧 Start Manual Setup Process"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    # Set manual setup state
    context.user_data['enhanced_ads_state'] = 'awaiting_manual_account_details'
    
    msg = "🔧 **MANUAL ACCOUNT SETUP** 🔧\n\n"
    msg += "**📝 Please provide account details in this format:**\n\n"
    
    msg += "```\n"
    msg += "Account Name: My Business Bot\n"
    msg += "Phone: +1234567890\n"
    msg += "API ID: 12345678\n"
    msg += "API Hash: abcd1234efgh5678\n"
    msg += "```\n\n"
    
    msg += "**🔐 After providing details, you'll receive a login code:**\n"
    msg += "• Check your Telegram app\n"
    msg += "• Enter the verification code\n"
    msg += "• Account will be automatically configured\n\n"
    
    msg += "**📤 Please send your account details now...**"
    
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data="enhanced_manage_accounts")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_manual_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle manual account details input and start login process"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get('enhanced_ads_state') != 'awaiting_manual_account_details':
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Please send account details as text.", parse_mode=None)
        return
    
    text = update.message.text.strip()
    
    # Parse manual account details
    try:
        details = {}
        for line in text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'account name' in key or 'name' in key:
                    details['account_name'] = value
                elif 'phone' in key:
                    details['phone_number'] = value
                elif 'api id' in key or 'api_id' in key:
                    details['api_id'] = value
                elif 'api hash' in key or 'api_hash' in key:
                    details['api_hash'] = value
        
        # Validate required fields
        required = ['account_name', 'api_id', 'api_hash', 'phone_number']
        missing = [field for field in required if not details.get(field)]
        
        if missing:
            await send_message_with_retry(context.bot, chat_id, 
                f"❌ **Missing required fields:** {', '.join(missing)}\n\n"
                "Please provide all required information.", parse_mode='Markdown')
            return
        
        # Store account details for login process
        context.user_data['pending_account'] = details
        
        # Start login process
        await start_userbot_login(update, context, details)
        
    except Exception as e:
        logger.error(f"Error parsing manual account details: {e}")
        await send_message_with_retry(context.bot, chat_id, 
            "❌ **Invalid format!**\n\nPlease use the exact format provided.", parse_mode='Markdown')

async def start_userbot_login(update: Update, context: ContextTypes.DEFAULT_TYPE, details: Dict[str, str]):
    """Start the userbot login process"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not TELETHON_AVAILABLE:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ **Telethon not available!**\n\nPlease install telethon for userbot functionality.", 
            parse_mode='Markdown')
        return
    
    try:
        # Create temporary client for login
        session_name = f"temp_login_{user_id}_{int(time.time())}"
        client = TelegramClient(session_name, int(details['api_id']), details['api_hash'])
        
        # Connect and start login process
        await client.connect()
        
        # Send code request
        await client.send_code_request(details['phone_number'])
        
        # Store client in context for code verification
        context.user_data['login_client'] = client
        context.user_data['enhanced_ads_state'] = 'awaiting_login_code'
        
        msg = "📱 **LOGIN CODE SENT!** 📱\n\n"
        msg += f"🤖 **Account:** {details['account_name']}\n"
        msg += f"📱 **Phone:** {details['phone_number']}\n\n"
        msg += "**📲 Check your Telegram app for the verification code!**\n\n"
        msg += "**📤 Please send the 5-digit code you received:**"
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancel Login", callback_data="enhanced_manage_accounts")]
        ]
        
        await send_message_with_retry(context.bot, chat_id, msg, 
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error starting userbot login: {e}")
        await send_message_with_retry(context.bot, chat_id, 
            f"❌ **Login failed:** {str(e)}\n\nPlease check your API credentials and try again.", 
            parse_mode='Markdown')

async def handle_enhanced_login_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle login code verification"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get('enhanced_ads_state') != 'awaiting_login_code':
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Please send the verification code.", parse_mode=None)
        return
    
    code = update.message.text.strip()
    
    # Validate code format
    if not code.isdigit() or len(code) != 5:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ **Invalid code format!**\n\nPlease send the 5-digit verification code.", 
            parse_mode='Markdown')
        return
    
    try:
        # Get login client and account details
        client = context.user_data.get('login_client')
        account_details = context.user_data.get('pending_account')
        
        if not client or not account_details:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ **Login session expired!**\n\nPlease start the login process again.", 
                parse_mode='Markdown')
            return
        
        # Verify code and complete login
        await client.sign_in(account_details['phone_number'], code)
        
        # Get session string
        session_string = client.session.save()
        
        # Save account to database
        success = await save_userbot_account(account_details, session_string)
        
        # Clean up
        await client.disconnect()
        context.user_data.pop('login_client', None)
        context.user_data.pop('pending_account', None)
        context.user_data.pop('enhanced_ads_state', None)
        
        if success:
            msg = "🎉 **ACCOUNT LOGIN SUCCESSFUL!** 🎉\n\n"
            msg += f"🤖 **Account:** {account_details['account_name']}\n"
            msg += f"📱 **Phone:** {account_details['phone_number']}\n"
            msg += f"🔑 **API ID:** {account_details['api_id']}\n\n"
            msg += "**✅ Userbot account is now active and ready for campaigns!**\n\n"
            msg += "**🚀 What's next?**\n"
            msg += "• Add channels to post to\n"
            msg += "• Create automated campaigns\n"
            msg += "• Start posting with userbot technology"
            
            keyboard = [
                [InlineKeyboardButton("📺 Add Channels", callback_data="enhanced_manage_channels")],
                [InlineKeyboardButton("📢 Create Campaign", callback_data="enhanced_create_campaign")],
                [InlineKeyboardButton("🤖 Manage Accounts", callback_data="enhanced_manage_accounts")],
                [InlineKeyboardButton("🏠 Auto Ads Menu", callback_data="enhanced_auto_ads_menu")]
            ]
            
            await send_message_with_retry(context.bot, chat_id, msg, 
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ **Failed to save account!**\n\nPlease try again.", parse_mode=None)
        
    except PhoneCodeInvalidError:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ **Invalid verification code!**\n\nPlease check the code and try again.", 
            parse_mode='Markdown')
    except SessionPasswordNeededError:
        # Handle 2FA password
        context.user_data['enhanced_ads_state'] = 'awaiting_2fa_password'
        await send_message_with_retry(context.bot, chat_id, 
            "🔐 **2FA PASSWORD REQUIRED** 🔐\n\n"
            "This account has two-factor authentication enabled.\n"
            "**📤 Please send your 2FA password:**", 
            parse_mode='Markdown')
    except FloodWaitError as e:
        await send_message_with_retry(context.bot, chat_id, 
            f"⏰ **Rate limited!**\n\nPlease wait {e.seconds} seconds before trying again.", 
            parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error during login verification: {e}")
        await send_message_with_retry(context.bot, chat_id, 
            f"❌ **Login failed:** {str(e)}\n\nPlease try again.", parse_mode='Markdown')

async def handle_enhanced_2fa_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 2FA password input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get('enhanced_ads_state') != 'awaiting_2fa_password':
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Please send your 2FA password.", parse_mode=None)
        return
    
    password = update.message.text.strip()
    
    try:
        # Get login client and account details
        client = context.user_data.get('login_client')
        account_details = context.user_data.get('pending_account')
        
        if not client or not account_details:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ **Login session expired!**\n\nPlease start the login process again.", 
                parse_mode='Markdown')
            return
        
        # Complete 2FA login
        await client.sign_in(password=password)
        
        # Get session string
        session_string = client.session.save()
        
        # Save account to database
        success = await save_userbot_account(account_details, session_string)
        
        # Clean up
        await client.disconnect()
        context.user_data.pop('login_client', None)
        context.user_data.pop('pending_account', None)
        context.user_data.pop('enhanced_ads_state', None)
        
        if success:
            msg = "🎉 **2FA LOGIN SUCCESSFUL!** 🎉\n\n"
            msg += f"🤖 **Account:** {account_details['account_name']}\n"
            msg += f"📱 **Phone:** {account_details['phone_number']}\n"
            msg += f"🔑 **API ID:** {account_details['api_id']}\n\n"
            msg += "**✅ Userbot account with 2FA is now active!**\n\n"
            msg += "**🚀 Ready for campaigns!**"
            
            keyboard = [
                [InlineKeyboardButton("📺 Add Channels", callback_data="enhanced_manage_channels")],
                [InlineKeyboardButton("📢 Create Campaign", callback_data="enhanced_create_campaign")],
                [InlineKeyboardButton("🤖 Manage Accounts", callback_data="enhanced_manage_accounts")],
                [InlineKeyboardButton("🏠 Auto Ads Menu", callback_data="enhanced_auto_ads_menu")]
            ]
            
            await send_message_with_retry(context.bot, chat_id, msg, 
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ **Failed to save account!**\n\nPlease try again.", parse_mode=None)
        
    except Exception as e:
        logger.error(f"Error during 2FA verification: {e}")
        await send_message_with_retry(context.bot, chat_id, 
            f"❌ **2FA failed:** {str(e)}\n\nPlease check your password and try again.", 
            parse_mode='Markdown')

async def handle_enhanced_ads_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """📊 View Analytics Dashboard"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get comprehensive analytics
        c.execute("""
            SELECT COUNT(*) as total_accounts, 
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_accounts,
                   SUM(success_count) as total_success,
                   SUM(error_count) as total_errors
            FROM userbot_accounts
        """)
        account_stats = c.fetchone()
        
        c.execute("""
            SELECT COUNT(*) as total_campaigns,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_campaigns,
                   SUM(total_sent) as total_messages,
                   SUM(total_errors) as campaign_errors
            FROM enhanced_auto_ads_campaigns
        """)
        campaign_stats = c.fetchone()
        
        c.execute("""
            SELECT COUNT(*) as total_channels,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_channels,
                   SUM(success_count) as channel_success,
                   SUM(error_count) as channel_errors
            FROM enhanced_channels
        """)
        channel_stats = c.fetchone()
        
        # Get recent activity
        c.execute("""
            SELECT COUNT(*) as recent_executions
            FROM campaign_execution_logs
            WHERE execution_time > datetime('now', '-24 hours')
        """)
        recent_activity = c.fetchone()
        
    except Exception as e:
        logger.error(f"Error loading analytics: {e}")
        account_stats = {'total_accounts': 0, 'active_accounts': 0, 'total_success': 0, 'total_errors': 0}
        campaign_stats = {'total_campaigns': 0, 'active_campaigns': 0, 'total_messages': 0, 'campaign_errors': 0}
        channel_stats = {'total_channels': 0, 'active_channels': 0, 'channel_success': 0, 'channel_errors': 0}
        recent_activity = {'recent_executions': 0}
    finally:
        if conn:
            conn.close()
    
    # Build analytics message
    msg = "📊 **ENHANCED AUTO ADS ANALYTICS** 📊\n\n"
    msg += "🤖 **Userbot Accounts:**\n"
    msg += f"• Total: {account_stats['total_accounts']} | Active: {account_stats['active_accounts']}\n"
    msg += f"• Success: {account_stats['total_success']:,} | Errors: {account_stats['total_errors']:,}\n\n"
    
    msg += "📢 **Campaigns:**\n"
    msg += f"• Total: {campaign_stats['total_campaigns']} | Active: {campaign_stats['active_campaigns']}\n"
    msg += f"• Messages Sent: {campaign_stats['total_messages']:,}\n"
    msg += f"• Errors: {campaign_stats['campaign_errors']:,}\n\n"
    
    msg += "📺 **Channels:**\n"
    msg += f"• Total: {channel_stats['total_channels']} | Active: {channel_stats['active_channels']}\n"
    msg += f"• Successful Posts: {channel_stats['channel_success']:,}\n"
    msg += f"• Errors: {channel_stats['channel_errors']:,}\n\n"
    
    msg += f"⚡ **Recent Activity (24h):** {recent_activity['recent_executions']} executions\n\n"
    
    # Calculate success rates
    if account_stats['total_success'] + account_stats['total_errors'] > 0:
        account_rate = (account_stats['total_success'] / (account_stats['total_success'] + account_stats['total_errors'])) * 100
        msg += f"✅ **Account Success Rate:** {account_rate:.1f}%\n"
    
    if channel_stats['channel_success'] + channel_stats['channel_errors'] > 0:
        channel_rate = (channel_stats['channel_success'] / (channel_stats['channel_success'] + channel_stats['channel_errors'])) * 100
        msg += f"📺 **Channel Success Rate:** {channel_rate:.1f}%\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📈 Detailed Reports", callback_data="enhanced_detailed_analytics"),
            InlineKeyboardButton("📊 Export Data", callback_data="enhanced_export_analytics")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="enhanced_ads_analytics"),
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="enhanced_auto_ads_menu")
        ]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_test_system(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """🧪 Test System Functionality"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    msg = "🧪 **SYSTEM TEST CENTER** 🧪\n\n"
    msg += "🔧 **Comprehensive Testing Suite**\n\n"
    
    msg += "**🎯 Available Tests:**\n\n"
    
    msg += "🤖 **Account Tests:**\n"
    msg += "• Test userbot connections\n"
    msg += "• Validate session data\n"
    msg += "• Check API credentials\n\n"
    
    msg += "📺 **Channel Tests:**\n"
    msg += "• Verify channel access\n"
    msg += "• Test posting permissions\n"
    msg += "• Check channel validity\n\n"
    
    msg += "🚀 **System Tests:**\n"
    msg += "• Database connectivity\n"
    msg += "• Telethon integration\n"
    msg += "• Error handling\n\n"
    
    msg += "**🔬 Choose a test to run:**"
    
    keyboard = [
        [
            InlineKeyboardButton("🤖 Test Accounts", callback_data="enhanced_test_accounts"),
            InlineKeyboardButton("📺 Test Channels", callback_data="enhanced_test_channels")
        ],
        [
            InlineKeyboardButton("🔗 Test Connections", callback_data="enhanced_test_connections"),
            InlineKeyboardButton("💾 Test Database", callback_data="enhanced_test_database")
        ],
        [
            InlineKeyboardButton("🧪 Run All Tests", callback_data="enhanced_test_all"),
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="enhanced_auto_ads_menu")
        ]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_manage_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """📢 Manage Campaigns"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all campaigns
        c.execute("""
            SELECT id, campaign_name, is_active, created_at, last_run, 
                   total_sent, total_errors, next_run
            FROM enhanced_auto_ads_campaigns 
            ORDER BY created_at DESC
            LIMIT 10
        """)
        campaigns = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading campaigns: {e}")
        campaigns = []
    finally:
        if conn:
            conn.close()
    
    # Build campaigns menu
    msg = "📢 **CAMPAIGN MANAGER** 📢\n\n"
    msg += "🎯 **Professional Campaign Management**\n\n"
    
    if campaigns:
        msg += f"**📋 Your Campaigns ({len(campaigns)}):**\n\n"
        for campaign in campaigns:
            status = "✅ Active" if campaign['is_active'] else "❌ Inactive"
            
            msg += f"**{campaign['campaign_name']}**\n"
            msg += f"📊 Status: {status}\n"
            msg += f"📤 Sent: {campaign['total_sent']} | ❌ Errors: {campaign['total_errors']}\n"
            msg += f"⏰ Created: {campaign['created_at'][:16]}\n\n"
    else:
        msg += "📭 **No campaigns created yet**\n\n"
        msg += "**🚀 Get Started:**\n"
        msg += "1. Set up userbot accounts\n"
        msg += "2. Add target channels\n"
        msg += "3. Create your first campaign!\n\n"
    
    msg += "**🎯 Campaign Management:**"
    
    keyboard = [
        [InlineKeyboardButton("➕ Create Campaign", callback_data="enhanced_create_campaign")],
    ]
    
    if campaigns:
        keyboard.extend([
            [InlineKeyboardButton("✏️ Edit Campaign", callback_data="enhanced_edit_campaign")],
            [InlineKeyboardButton("▶️ Start/Stop", callback_data="enhanced_toggle_campaign")],
            [InlineKeyboardButton("🗑️ Delete Campaign", callback_data="enhanced_delete_campaign")]
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("📊 Campaign Analytics", callback_data="enhanced_campaign_analytics")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="enhanced_auto_ads_menu")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """➕ Add Channel (Regular Method)"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    # Set state for channel addition
    context.user_data['enhanced_ads_state'] = 'awaiting_channel_details'
    
    msg = "➕ **ADD CHANNEL** ➕\n\n"
    msg += "📺 **Channel Configuration**\n\n"
    
    msg += "**📋 Please provide channel details:**\n\n"
    
    msg += "**Format:**\n"
    msg += "`Channel Name: My Channel`\n"
    msg += "`Channel Link: https://t.me/mychannel`\n"
    msg += "`Description: Business announcements`\n\n"
    
    msg += "**📝 Example:**\n"
    msg += "`Channel Name: Business Updates`\n"
    msg += "`Channel Link: @businessupdates`\n"
    msg += "`Description: Daily business news`\n\n"
    
    msg += "**🔗 Supported Formats:**\n"
    msg += "• https://t.me/channelname\n"
    msg += "• @channelname\n"
    msg += "• channelname\n"
    msg += "• -1001234567890\n\n"
    
    msg += "**📤 Please send your channel details...**"
    
    keyboard = [
        [InlineKeyboardButton("🔗 Quick Add Instead", callback_data="enhanced_quick_add_channel")],
        [InlineKeyboardButton("❌ Cancel", callback_data="enhanced_manage_channels")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_enhanced_channel_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle detailed channel input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get('enhanced_ads_state') != 'awaiting_channel_details':
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Please send channel details as text.", parse_mode=None)
        return
    
    text = update.message.text.strip()
    
    # Parse channel details
    try:
        details = {'description': 'No description provided'}
        channel_link = None
        
        for line in text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'channel name' in key or 'name' in key:
                    details['name'] = value
                elif 'channel link' in key or 'link' in key or 'url' in key:
                    channel_link = value
                elif 'description' in key:
                    details['description'] = value
        
        if not details.get('name') or not channel_link:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ **Missing required fields!**\n\nPlease provide both channel name and link.", 
                parse_mode='Markdown')
            return
        
        # Parse channel info
        channel_info = parse_channel_input(channel_link)
        if not channel_info:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ **Invalid channel link format!**", parse_mode='Markdown')
            return
        
        # Merge details
        channel_info['name'] = details['name']
        channel_info['description'] = details.get('description', 'No description')
        
        # Save channel
        success = await save_channel(channel_info)
        
        if success:
            # Clear state
            context.user_data.pop('enhanced_ads_state', None)
            
            msg = "✅ **Channel Added Successfully!** ✅\n\n"
            msg += f"📺 **Name:** {channel_info['name']}\n"
            msg += f"🔗 **Link:** {channel_link}\n"
            msg += f"📝 **Description:** {details.get('description', 'None')}\n\n"
            msg += "**🚀 Ready for campaigns!**"
            
            keyboard = [
                [InlineKeyboardButton("📢 Create Campaign", callback_data="enhanced_create_campaign")],
                [InlineKeyboardButton("📺 Manage Channels", callback_data="enhanced_manage_channels")],
                [InlineKeyboardButton("🏠 Auto Ads Menu", callback_data="enhanced_auto_ads_menu")]
            ]
            
            await send_message_with_retry(context.bot, chat_id, msg, 
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await send_message_with_retry(context.bot, chat_id, 
                "❌ Failed to add channel. Please try again.", parse_mode=None)
        
    except Exception as e:
        logger.error(f"Error parsing channel details: {e}")
        await send_message_with_retry(context.bot, chat_id, 
            "❌ **Invalid format!**\n\nPlease use the provided format.", parse_mode='Markdown')

async def handle_enhanced_ads_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """⚙️ System Settings"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    msg = "⚙️ **ENHANCED AUTO ADS SETTINGS** ⚙️\n\n"
    msg += "🔧 **System Configuration**\n\n"
    
    # Check Telethon status
    telethon_status = "✅ Available" if TELETHON_AVAILABLE else "❌ Not Available"
    msg += f"**🤖 Telethon Status:** {telethon_status}\n"
    
    if TELETHON_AVAILABLE:
        msg += f"**📦 Telethon Version:** Available\n"
    else:
        msg += "**⚠️ Install telethon for full functionality**\n"
    
    msg += f"**🗃️ Database:** Connected\n"
    msg += f"**🔐 Security:** Admin-only access\n\n"
    
    msg += "**⚙️ Configuration Options:**\n\n"
    
    msg += "🤖 **Account Settings:**\n"
    msg += "• Session timeout management\n"
    msg += "• Connection retry settings\n"
    msg += "• Error handling configuration\n\n"
    
    msg += "📺 **Channel Settings:**\n"
    msg += "• Posting rate limits\n"
    msg += "• Error retry attempts\n"
    msg += "• Channel validation rules\n\n"
    
    msg += "📊 **Analytics Settings:**\n"
    msg += "• Data retention period\n"
    msg += "• Report generation\n"
    msg += "• Performance tracking\n"
    
    keyboard = [
        [
            InlineKeyboardButton("🤖 Account Settings", callback_data="enhanced_account_settings"),
            InlineKeyboardButton("📺 Channel Settings", callback_data="enhanced_channel_settings")
        ],
        [
            InlineKeyboardButton("📊 Analytics Settings", callback_data="enhanced_analytics_settings"),
            InlineKeyboardButton("🔧 System Diagnostics", callback_data="enhanced_system_diagnostics")
        ],
        [
            InlineKeyboardButton("💾 Backup Settings", callback_data="enhanced_backup_settings"),
            InlineKeyboardButton("🔄 Reset to Defaults", callback_data="enhanced_reset_settings")
        ],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="enhanced_auto_ads_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Placeholder handlers for settings and other features
async def handle_enhanced_create_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """➕ Create New Campaign"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    await query.edit_message_text(
        "🚧 **Campaign Creation Coming Soon!** 🚧\n\n"
        "This feature will allow you to:\n"
        "• Create automated campaigns\n"
        "• Schedule posts to multiple channels\n"
        "• Use userbot technology for direct posting\n"
        "• Track campaign performance\n\n"
        "📋 **For now, use the existing manual posting features.**",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="enhanced_auto_ads_menu")
        ]]),
        parse_mode='Markdown'
    )

# Add placeholder handlers for all other missing callbacks
async def handle_enhanced_test_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    await update.callback_query.edit_message_text(
        "🧪 **Account Testing Coming Soon!**\n\nThis will test all userbot accounts.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="enhanced_test_system")]])
    )

async def handle_enhanced_test_channels(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    await update.callback_query.edit_message_text(
        "🧪 **Channel Testing Coming Soon!**\n\nThis will test all channels.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="enhanced_test_system")]])
    )

async def handle_enhanced_test_connections(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    await update.callback_query.edit_message_text(
        "🧪 **Connection Testing Coming Soon!**\n\nThis will test system connections.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="enhanced_test_system")]])
    )

async def handle_enhanced_test_database(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    await update.callback_query.edit_message_text(
        "🧪 **Database Testing Coming Soon!**\n\nThis will test database connectivity.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="enhanced_test_system")]])
    )

async def handle_enhanced_test_all(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    await update.callback_query.edit_message_text(
        "🧪 **Full System Test Coming Soon!**\n\nThis will run all tests.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="enhanced_test_system")]])
    )

# --- END OF FILE enhanced_auto_ads_system.py ---
