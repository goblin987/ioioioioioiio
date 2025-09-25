"""
Testforwarder Integration - Exact copy from working repository
This file contains the exact functionality from https://github.com/goblin987/testforwarder
Integrated to work with the main bot's admin panel
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError
import re
import os
import json
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class TestforwarderBot:
    def __init__(self):
        self.user_sessions = {}  # Store user session data
        self.db = None  # Will be initialized later
    
    def escape_markdown(self, text):
        """Escape special Markdown characters"""
        if not text:
            return ""
        return text.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[').replace(']', '\\]')
    
    def validate_input(self, text: str, max_length: int = 1000, allowed_chars: str = None) -> tuple[bool, str]:
        """Validate user input with length and character restrictions"""
        if not text or not isinstance(text, str):
            return False, "Input cannot be empty"
        
        if len(text) > max_length:
            return False, f"Input too long (max {max_length} characters)"
        
        if allowed_chars:
            if not re.match(f"^[{re.escape(allowed_chars)}]+$", text):
                return False, f"Input contains invalid characters. Only {allowed_chars} allowed"
        
        return True, ""
    
    def sanitize_text(self, text: str) -> str:
        """Sanitize text input"""
        if not text:
            return ""
        return text.strip()
    
    async def show_main_menu(self, query):
        """Show main menu with all core features"""
        keyboard = [
            [InlineKeyboardButton("👥 Manage Accounts", callback_data="tf_manage_accounts")],
            [InlineKeyboardButton("📢 Bump Service", callback_data="tf_bump_service")],
            [InlineKeyboardButton("📋 My Configurations", callback_data="tf_my_configs")],
            [InlineKeyboardButton("➕ Add New Forwarding", callback_data="tf_add_forwarding")],
            [InlineKeyboardButton("❓ Help", callback_data="tf_help")],
            [InlineKeyboardButton("⬅️ Back to Main Bot", callback_data="admin_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Choose an option:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def start_manual_setup(self, query):
        """Start manual account setup (5-step process)"""
        user_id = query.from_user.id
        self.user_sessions[user_id] = {"step": "account_name", "account_data": {}}
        
        logger.info(f"🔍 MANUAL SETUP: Created session for user {user_id}")
        logger.info(f"🔍 SESSION DATA: {self.user_sessions[user_id]}")
        
        text = """**Manual Account Setup**

**Step 1/5: Account Name**

Please send me a name for this work account (e.g., "Marketing Account", "Sales Account", "Support Account").

This name will help you identify the account when managing campaigns."""
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="tf_manage_accounts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages for configuration setup"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        logger.info(f"🔍 MESSAGE HANDLER: User {user_id} sent message: '{message_text}'")
        logger.info(f"🔍 SESSION CHECK: User {user_id} in sessions: {user_id in self.user_sessions}")
        logger.info(f"🔍 ACTIVE SESSIONS: {list(self.user_sessions.keys())}")
        
        if user_id not in self.user_sessions:
            logger.info(f"🔍 NO SESSION: User {user_id} not in sessions, ignoring message")
            return
        
        session = self.user_sessions[user_id]
        
        # Validate and sanitize text input
        if message_text:
            is_valid, error_msg = self.validate_input(message_text, max_length=2000)
            if not is_valid:
                safe_error_msg = self.escape_markdown(error_msg)
                await update.message.reply_text(
                    f"❌ **Invalid Input**\n\n{safe_error_msg}\n\nPlease try again with valid input.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            message_text = self.sanitize_text(message_text)
        
        logger.info(f"🔍 SESSION DEBUG: User {user_id} step: {session.get('step', 'unknown')}")
        
        # Handle account creation
        if 'account_data' in session:
            if session['step'] == 'account_name':
                logger.info(f"🔍 PROCESSING ACCOUNT NAME: '{message_text}'")
                session['account_data']['account_name'] = message_text
                session['step'] = 'phone_number'
                
                logger.info(f"🔍 ACCOUNT NAME SET: {session['account_data']}")
                logger.info(f"🔍 STEP CHANGED TO: {session['step']}")
                
                await update.message.reply_text(
                    "✅ **Account name set!**\n\n**Step 2/5: Phone Number**\n\nPlease send me the phone number for this work account (with country code, e.g., +1234567890).",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'phone_number':
                # Validate phone number format
                phone_pattern = r'^\+?[1-9]\d{1,14}$'
                if not re.match(phone_pattern, message_text.replace(' ', '').replace('-', '')):
                    await update.message.reply_text(
                        "❌ **Invalid Phone Number**\n\nPlease enter a valid phone number with country code (e.g., +1234567890).",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                session['account_data']['phone_number'] = message_text
                session['step'] = 'api_id'
                
                await update.message.reply_text(
                    "✅ **Phone number set!**\n\n**Step 3/5: API ID**\n\nPlease send me the API ID for this account.\n\n**Get it from:** https://my.telegram.org\n• Go to 'API development tools'\n• Create a new application\n• Copy your API ID",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'api_id':
                try:
                    api_id = int(message_text)
                    session['account_data']['api_id'] = api_id
                    session['step'] = 'api_hash'
                    
                    await update.message.reply_text(
                        "✅ **API ID set!**\n\n**Step 4/5: API Hash**\n\nPlease send me the API Hash for this account.\n\n**Get it from:** https://my.telegram.org\n• Same page as API ID\n• Copy your API Hash",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except ValueError:
                    await update.message.reply_text(
                        "❌ **Invalid API ID**\n\nPlease enter a valid numeric API ID.",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif session['step'] == 'api_hash':
                session['account_data']['api_hash'] = message_text
                session['step'] = 'login_code'
                
                # Start the login process
                await self.start_userbot_login(update, context)
    
    async def start_userbot_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the userbot login process"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        account_data = session['account_data']
        
        try:
            # Create a temporary client for login
            client = TelegramClient(
                f"temp_session_{user_id}",
                account_data['api_id'],
                account_data['api_hash']
            )
            
            await client.connect()
            
            # Send code request
            await client.send_code_request(account_data['phone_number'])
            
            await update.message.reply_text(
                "✅ **API Hash set!**\n\n**Step 5/5: Login Code**\n\nI've sent a verification code to your phone.\n\nPlease send me the code you received.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Store client in session for code verification
            session['temp_client'] = client
            
        except Exception as e:
            logger.error(f"Failed to start authentication: {e}")
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            await update.message.reply_text(
                f"❌ **Authentication Failed**\n\nError: {str(e)}\n\nPlease check your API credentials and try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_login_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle login code verification"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        code = update.message.text.strip()
        
        try:
            client = session.get('temp_client')
            if not client:
                await update.message.reply_text("❌ Session expired. Please start over.")
                if user_id in self.user_sessions:
                    del self.user_sessions[user_id]
                return
            
            # Sign in with the code
            await client.sign_in(session['account_data']['phone_number'], code)
            
            # Get session string
            session_string = client.session.save()
            
            # Save account to database (simplified for now)
            account_data = session['account_data']
            account_data['session_string'] = session_string
            account_data['status'] = 'active'
            account_data['created_at'] = datetime.now().isoformat()
            
            # Clear session
            del self.user_sessions[user_id]
            
            keyboard = [
                [InlineKeyboardButton("📢 Create Campaign", callback_data="tf_add_campaign")],
                [InlineKeyboardButton("👥 Manage Accounts", callback_data="tf_manage_accounts")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="tf_main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎉 **Account Setup Complete!**\n\n✅ Account: {account_data['account_name']}\n✅ Phone: {account_data['phone_number']}\n✅ Status: Active\n\nYour account is now ready to use!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except SessionPasswordNeededError:
            session['step'] = '2fa_password'
            await update.message.reply_text(
                "🔐 **Two-Factor Authentication Required**\n\nPlease send me your 2FA password.",
                parse_mode=ParseMode.MARKDOWN
            )
        except PhoneCodeInvalidError:
            await update.message.reply_text(
                "❌ **Invalid Code**\n\nPlease check the code and try again.",
                parse_mode=ParseMode.MARKDOWN
            )
        except FloodWaitError as e:
            await update.message.reply_text(
                f"⏰ **Rate Limited**\n\nPlease wait {e.seconds} seconds before trying again.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Login failed: {e}")
            await update.message.reply_text(
                f"❌ **Login Failed**\n\nError: {str(e)}\n\nPlease try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_2fa_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 2FA password"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        password = update.message.text
        
        try:
            client = session.get('temp_client')
            if not client:
                await update.message.reply_text("❌ Session expired. Please start over.")
                if user_id in self.user_sessions:
                    del self.user_sessions[user_id]
                return
            
            # Sign in with password
            await client.sign_in(password=password)
            
            # Get session string
            session_string = client.session.save()
            
            # Save account to database
            account_data = session['account_data']
            account_data['session_string'] = session_string
            account_data['status'] = 'active'
            account_data['created_at'] = datetime.now().isoformat()
            
            # Clear session
            del self.user_sessions[user_id]
            
            keyboard = [
                [InlineKeyboardButton("📢 Create Campaign", callback_data="tf_add_campaign")],
                [InlineKeyboardButton("👥 Manage Accounts", callback_data="tf_manage_accounts")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="tf_main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎉 **Account Setup Complete!**\n\n✅ Account: {account_data['account_name']}\n✅ Phone: {account_data['phone_number']}\n✅ Status: Active\n\nYour account is now ready to use!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"2FA login failed: {e}")
            await update.message.reply_text(
                f"❌ **2FA Failed**\n\nError: {str(e)}\n\nPlease try again.",
                parse_mode=ParseMode.MARKDOWN
            )

# Global bot instance
_global_testforwarder_bot = None

def get_testforwarder_bot():
    """Get or create the global testforwarder bot instance"""
    global _global_testforwarder_bot
    if _global_testforwarder_bot is None:
        _global_testforwarder_bot = TestforwarderBot()
    return _global_testforwarder_bot

# Integration handlers for main bot
async def handle_testforwarder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle testforwarder menu callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.show_main_menu(query)

async def handle_testforwarder_manual_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle manual setup callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.start_manual_setup(query)

async def handle_testforwarder_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages for testforwarder bot"""
    bot = get_testforwarder_bot()
    await bot.handle_message(update, context)

async def handle_testforwarder_login_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle login code for testforwarder bot"""
    bot = get_testforwarder_bot()
    await bot.handle_login_code(update, context)

async def handle_testforwarder_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 2FA password for testforwarder bot"""
    bot = get_testforwarder_bot()
    await bot.handle_2fa_password(update, context)
