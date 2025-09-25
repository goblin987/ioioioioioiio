"""
Testforwarder Integration - Exact copy from working repository
This file contains the exact functionality from https://github.com/goblin987/testforwarder
Integrated to work with the main bot's admin panel
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from config_testforwarder import Config
from database_testforwarder import Database
from bump_service_testforwarder import BumpService

# Configure professional logging
logger = logging.getLogger(__name__)

class TgcfBot:
    def escape_markdown(self, text):
        """Escape special Markdown characters"""
        if not text:
            return ""
        # Escape special characters that break Markdown
        text = str(text)
        text = text.replace("\\", "\\\\")  # Backslash first
        text = text.replace("*", "\\*")   # Asterisk
        text = text.replace("_", "\\_")   # Underscore
        text = text.replace("`", "\\`")   # Backtick
        text = text.replace("[", "\\[")   # Square brackets
        text = text.replace("]", "\\]")   # Square brackets
        text = text.replace("(", "\\(")   # Parentheses
        text = text.replace(")", "\\)")   # Parentheses
        text = text.replace("~", "\\~")   # Tilde
        text = text.replace(">", "\\>")   # Greater than
        text = text.replace("#", "\\#")   # Hash
        text = text.replace("+", "\\+")   # Plus
        text = text.replace("-", "\\-")   # Minus
        text = text.replace("=", "\\=")   # Equals
        text = text.replace("|", "\\|")   # Pipe
        text = text.replace("{", "\\{")   # Curly braces
        text = text.replace("}", "\\}")   # Curly braces
        text = text.replace(".", "\\.")   # Dot
        text = text.replace("!", "\\!")   # Exclamation
        return text

    def __init__(self):
        self.db = Database()
        self.bump_service = None  # Will be initialized after bot is created
        self.user_sessions = {}  # Store user session data
        
        # Initialize BumpService
        try:
            from bump_service_testforwarder import BumpService
            self.bump_service = BumpService(bot_instance=self)
            logger.info("BumpService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize BumpService: {e}")
            self.bump_service = None
    
    def validate_input(self, text: str, max_length: int = 1000, allowed_chars: str = None) -> tuple[bool, str]:
        """Validate user input with length and character restrictions"""
        import re  # Import at the top of the function
        
        if not text or not isinstance(text, str):
            return False, "Input cannot be empty"
        
        if len(text) > max_length:
            return False, f"Input too long (max {max_length} characters)"
        
        if allowed_chars:
            if not re.match(f"^[{re.escape(allowed_chars)}]+$", text):
                return False, f"Input contains invalid characters. Only {allowed_chars} allowed"
        
        # Check for potential SQL injection patterns
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
            r"(--|#|\/\*|\*\/)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+'.*'\s*=\s*'.*')",
            r"(\bUNION\s+SELECT\b)",
            r"(\bDROP\s+TABLE\b)",
            r"(\bINSERT\s+INTO\b)",
            r"(\bDELETE\s+FROM\b)"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "Input contains potentially malicious content"
        
        return True, ""

    def sanitize_text(self, text: str) -> str:
        """Sanitize text input"""
        if not text:
            return ""
        return text.strip()
    
    def get_main_menu_keyboard(self):
        """Get main menu keyboard markup"""
        keyboard = [
            [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
            [InlineKeyboardButton("📢 Bump Service", callback_data="bump_service")],
            [InlineKeyboardButton("📋 My Configurations", callback_data="my_configs")],
            [InlineKeyboardButton("➕ Add New Forwarding", callback_data="add_forwarding")],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("⬅️ Back to Main Bot", callback_data="admin_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def show_main_menu(self, query):
        """Show main menu with all core features"""
        reply_markup = self.get_main_menu_keyboard()
        
        try:
            await query.edit_message_text(
                "Choose an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as e:
            # If message is not modified, just answer the callback
            if "Message is not modified" in str(e):
                await query.answer()
            else:
                raise e
    
    async def show_manage_accounts(self, query):
        """Show manage accounts menu"""
        user_id = query.from_user.id
        
        # Get user's accounts from database
        accounts = self.db.get_user_accounts(user_id)
        
        msg = "👥 **Manage Accounts**\n\n"
        
        if accounts:
            msg += f"**📋 Your Accounts ({len(accounts)}):**\n\n"
            for account in accounts:
                status = "✅ Active" if account.get('is_active', True) else "❌ Inactive"
                msg += f"**{account['account_name']}**\n"
                msg += f"📱 Phone: {account.get('phone_number', 'Not set')}\n"
                msg += f"📊 Status: {status}\n\n"
        else:
            msg += "📭 **No accounts configured**\n\n"
            msg += "**🚀 Get Started:**\n"
            msg += "1. Add an account manually\n"
            msg += "2. Configure API credentials\n"
            msg += "3. Start creating campaigns!\n\n"
        
                keyboard = [
                    [InlineKeyboardButton("➕ Add Account Manually", callback_data="manual_setup")],
                    [InlineKeyboardButton("📁 Upload Session File", callback_data="upload_session")],
                ]
        
        if accounts:
            keyboard.extend([
                [InlineKeyboardButton("✏️ Edit Account", callback_data="edit_account")],
                [InlineKeyboardButton("🗑️ Delete Account", callback_data="delete_account")]
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")])
        
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_bump_service(self, query):
        """Show bump service menu"""
        msg = "📢 **Bump Service**\n\n"
        msg += "**🚀 Automated Campaign Management**\n\n"
        msg += "• Schedule campaigns to run automatically\n"
        msg += "• Multi-account broadcasting\n"
        msg += "• Performance tracking and analytics\n"
        msg += "• Smart retry mechanisms\n\n"
        msg += "**🎯 Features:**\n"
        msg += "• Campaign scheduling\n"
        msg += "• Target management\n"
        msg += "• Performance monitoring\n"
        msg += "• Error handling\n\n"
        msg += "**🎯 Ready to Start?**\n"
        msg += "Create campaigns and start sending automated ads!"
        
        keyboard = [
            [InlineKeyboardButton("➕ Create Campaign", callback_data="add_campaign")],
            [InlineKeyboardButton("📋 My Campaigns", callback_data="my_campaigns")],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_my_configs(self, query):
        """Show my configurations menu"""
        user_id = query.from_user.id
        
        # Get user's configurations from database
        configs = self.db.get_user_configs(user_id)
        
        msg = "📋 **My Configurations**\n\n"
        
        if configs:
            msg += f"**📋 Your Configurations ({len(configs)}):**\n\n"
            for config in configs:
                status = "✅ Active" if config.get('is_active', True) else "❌ Inactive"
                msg += f"**{config['name']}**\n"
                msg += f"📊 Status: {status}\n"
                msg += f"📅 Created: {config.get('created_at', 'Unknown')}\n\n"
        else:
            msg += "📭 **No configurations found**\n\n"
            msg += "**🚀 Get Started:**\n"
            msg += "1. Create a new forwarding configuration\n"
            msg += "2. Set up your target channels\n"
            msg += "3. Start forwarding messages!\n\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Add New Configuration", callback_data="add_forwarding")],
        ]
        
        if configs:
            keyboard.extend([
                [InlineKeyboardButton("✏️ Edit Configuration", callback_data="edit_config")],
                [InlineKeyboardButton("🗑️ Delete Configuration", callback_data="delete_config")]
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")])
        
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_help(self, query):
        """Show help menu"""
        msg = "❓ **Help & Support**\n\n"
        msg += "**🚀 Getting Started:**\n"
        msg += "1. **Add Accounts** - Set up your Telegram userbot accounts\n"
        msg += "2. **Create Configurations** - Set up forwarding rules\n"
        msg += "3. **Start Campaigns** - Begin automated messaging\n\n"
        msg += "**📋 Account Management:**\n"
        msg += "• Add accounts manually with API credentials\n"
        msg += "• Upload session files for quick setup\n"
        msg += "• Manage multiple accounts simultaneously\n\n"
        msg += "**⚙️ Configuration:**\n"
        msg += "• Set up forwarding rules\n"
        msg += "• Configure target channels\n"
        msg += "• Schedule automated campaigns\n\n"
        msg += "**🔧 Troubleshooting:**\n"
        msg += "• Check account status in Manage Accounts\n"
        msg += "• Verify API credentials are correct\n"
        msg += "• Ensure target channels are accessible\n\n"
        msg += "**📞 Support:**\n"
        msg += "For additional help, contact the administrator."
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def start_add_campaign(self, query):
        """Start campaign creation process"""
        user_id = query.from_user.id
        
        # Check if user has accounts
        accounts = self.db.get_user_accounts(user_id)
        if not accounts:
            await query.edit_message_text(
                "❌ **No Accounts Found**\n\nYou need to add at least one account before creating campaigns.\n\nPlease add an account first in Manage Accounts.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
                    [InlineKeyboardButton("⬅️ Back to Bump Service", callback_data="bump_service")]
                ])
            )
            return
        
        # Start campaign creation
        self.user_sessions[user_id] = {"step": "campaign_name", "campaign_data": {}}
        
        msg = "🚀 **Create New Campaign**\n\n"
        msg += "**Step 1/6: Campaign Name**\n\n"
        msg += "Please enter a name for this campaign (e.g., 'Product Launch', 'Weekly Promo', 'Holiday Sale')."
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="bump_service")]]
        
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_my_campaigns(self, query):
        """Show user's campaigns"""
        user_id = query.from_user.id
        
        # Get user's campaigns from database
        campaigns = self.db.get_user_campaigns(user_id)
        
        msg = "📋 **My Campaigns**\n\n"
        
        if campaigns:
            msg += f"**📋 Your Campaigns ({len(campaigns)}):**\n\n"
            for campaign in campaigns:
                status = "✅ Active" if campaign.get('is_active', True) else "❌ Inactive"
                msg += f"**{campaign['campaign_name']}**\n"
                msg += f"📊 Status: {status}\n"
                msg += f"📅 Schedule: {campaign.get('schedule_type', 'Once')}\n"
                msg += f"🎯 Targets: {len(campaign.get('target_chats', []))} chat(s)\n\n"
        else:
            msg += "📭 **No campaigns found**\n\n"
            msg += "**🚀 Get Started:**\n"
            msg += "1. Create your first campaign\n"
            msg += "2. Set up your target channels\n"
            msg += "3. Start sending automated ads!\n\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Create New Campaign", callback_data="add_campaign")],
        ]
        
        if campaigns:
            keyboard.extend([
                [InlineKeyboardButton("✏️ Edit Campaign", callback_data="edit_campaign")],
                [InlineKeyboardButton("🗑️ Delete Campaign", callback_data="delete_campaign")]
            ])
            
            # Add run buttons for each campaign
            for campaign in campaigns:
                if campaign.get('is_active', True):
                    keyboard.append([
                        InlineKeyboardButton(
                            f"🚀 Run {campaign['campaign_name']}",
                            callback_data=f"run_campaign_{campaign['id']}"
                        )
                    ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Bump Service", callback_data="bump_service")])
        
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def get_account_selection_keyboard(self, user_id: int, callback_prefix: str = "select_account"):
        """Get account selection keyboard for campaign creation or forwarding"""
        accounts = self.db.get_user_accounts(user_id)
        
        keyboard = []
        for account in accounts:
            keyboard.append([
                InlineKeyboardButton(
                    f"📱 {account['account_name']}",
                    callback_data=f"{callback_prefix}_{account['id']}"
                )
            ])
        
        if callback_prefix == "select_account":
            keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="bump_service")])
        else:
            keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="my_configs")])
        return InlineKeyboardMarkup(keyboard)
    
    async def handle_media_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle media content for campaigns"""
        try:
            media_data = {
                'type': 'media',
                'caption': update.message.caption or '',
                'entities': []
            }
            
            if update.message.photo:
                # Get the largest photo
                photo = max(update.message.photo, key=lambda x: x.file_size)
                media_data['media_type'] = 'photo'
                media_data['file_id'] = photo.file_id
                media_data['file_unique_id'] = photo.file_unique_id
                
            elif update.message.video:
                media_data['media_type'] = 'video'
                media_data['file_id'] = update.message.video.file_id
                media_data['file_unique_id'] = update.message.video.file_unique_id
                media_data['duration'] = update.message.video.duration
                media_data['width'] = update.message.video.width
                media_data['height'] = update.message.video.height
                
            elif update.message.document:
                media_data['media_type'] = 'document'
                media_data['file_id'] = update.message.document.file_id
                media_data['file_unique_id'] = update.message.document.file_unique_id
                media_data['file_name'] = update.message.document.file_name
                media_data['mime_type'] = update.message.document.mime_type
                
            # Handle entities if present
            if update.message.entities:
                media_data['entities'] = [
                    {
                        'type': entity.type,
                        'offset': entity.offset,
                        'length': entity.length,
                        'url': getattr(entity, 'url', None)
                    }
                    for entity in update.message.entities
                ]
            
            return media_data
            
        except Exception as e:
            logger.error(f"Error handling media content: {e}")
            return None
    
    def parse_button_input(self, text: str):
        """Parse button input text into button objects"""
        try:
            buttons = []
            lines = text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        button_text = parts[0].strip()
                        button_url = parts[1].strip()
                        
                        # Validate URL
                        if button_url.startswith(('http://', 'https://', 'tg://', 't.me/')):
                            buttons.append({
                                'text': button_text,
                                'url': button_url
                            })
            
            return buttons if buttons else None
            
        except Exception as e:
            logger.error(f"Error parsing button input: {e}")
            return None
    
    def validate_channel_link(self, link: str) -> bool:
        """Validate if a link is a valid Telegram channel link"""
        import re
        
        # Remove whitespace
        link = link.strip()
        
        # Check for @username format
        if re.match(r'^@[a-zA-Z0-9_]{5,32}$', link):
            return True
        
        # Check for t.me format
        if re.match(r'^https?://t\.me/[a-zA-Z0-9_]{5,32}$', link):
            return True
        
        # Check for telegram.me format
        if re.match(r'^https?://telegram\.me/[a-zA-Z0-9_]{5,32}$', link):
            return True
        
        # Check for channel ID format (negative number)
        if re.match(r'^-100\d+$', link):
            return True
        
        return False
    
    async def complete_campaign_creation(self, user_id: int, account_id: int):
        """Complete campaign creation and save to database"""
        session = self.user_sessions.get(user_id)
        if not session or 'campaign_data' not in session:
            return False
        
        campaign_data = session['campaign_data']
        
        try:
            # Convert ad_content to JSON string for database storage
            import json
            ad_content_json = json.dumps(campaign_data['ad_content'])
            
            # Add campaign to database
            campaign_id = self.db.add_campaign(
                user_id=user_id,
                account_id=account_id,
                campaign_name=campaign_data['campaign_name'],
                ad_content=ad_content_json,
                target_chats=campaign_data.get('target_chats', []),
                schedule_type=campaign_data['schedule_type'],
                schedule_time=campaign_data['schedule_time'],
                target_mode=campaign_data.get('target_mode', 'specific')
            )
            
            # Store buttons separately if they exist
            if campaign_data.get('buttons'):
                # Store buttons in campaign data or separate table
                # For now, we'll store them in the ad_content JSON
                pass
            
            # Clear session
            del self.user_sessions[user_id]
            
            return campaign_id
            
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            return False
    
    async def execute_campaign(self, campaign_id: int):
        """Execute a campaign using BumpService"""
        if not self.bump_service:
            logger.error("BumpService not available")
            return False
        
        try:
            # Get campaign data
            campaign = self.db.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return False
            
            # Execute campaign
            success = await self.bump_service.execute_campaign_async(campaign_id)
            return success
            
        except Exception as e:
            logger.error(f"Error executing campaign {campaign_id}: {e}")
            return False
    
    async def complete_forwarding_config(self, user_id: int, account_id: int):
        """Complete forwarding configuration and save to database"""
        session = self.user_sessions.get(user_id)
        if not session or 'forwarding_data' not in session:
            return False
        
        forwarding_data = session['forwarding_data']
        
        try:
            # Add forwarding configuration to database
            config_id = self.db.add_forwarding_config(
                user_id=user_id,
                account_id=account_id,
                source_chat_id=forwarding_data['source_channel'],
                destination_chat_id=forwarding_data['destination_channel'],
                config_name=forwarding_data['name'],
                config_data={}
            )
            
            # Clear session
            del self.user_sessions[user_id]
            
            return config_id
            
        except Exception as e:
            logger.error(f"Error creating forwarding config: {e}")
            return False
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads (session files)"""
        if not update.message or not update.message.document:
            return
        
        user_id = update.effective_user.id
        document = update.message.document
        
        # Check if it's a session file
        if document.file_name.endswith('.session'):
            await self.handle_session_file_upload(update, context)
        else:
            await update.message.reply_text(
                "❌ **Invalid file type**\n\nPlease upload a valid .session file.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_session_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle session file upload"""
        user_id = update.effective_user.id
        document = update.message.document
        
        try:
            # Download the session file
            file = await context.bot.get_file(document.file_id)
            file_path = f"temp_session_{user_id}_{document.file_name}"
            
            await file.download_to_drive(file_path)
            
            # Read and decode the session file
            with open(file_path, 'rb') as f:
                session_data = f.read()
            
            # Try to decode as base64
            import base64
            try:
                decoded_session = base64.b64decode(session_data).decode('utf-8')
            except:
                # If not base64, try as raw string
                decoded_session = session_data.decode('utf-8')
            
            # Start account setup with session
            self.user_sessions[user_id] = {
                "step": "session_account_name",
                "session_data": decoded_session,
                "account_data": {}
            }
            
            await update.message.reply_text(
                "✅ **Session file uploaded successfully!**\n\n**Step 1/2: Account Name**\n\nPlease enter a name for this account (e.g., 'My Account', 'Business Account').",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Clean up temp file
            import os
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            logger.error(f"Error handling session file upload: {e}")
            await update.message.reply_text(
                "❌ **Error processing session file**\n\nPlease make sure the file is a valid Telegram session file and try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def start_manual_setup(self, query):
        """Start manual account setup (5-step process)"""
        user_id = query.from_user.id
        self.user_sessions[user_id] = {"step": "account_name", "account_data": {}}
        
        text = """**Manual Account Setup**

**Step 1/5: Account Name**

Please send me a name for this work account (e.g., "Marketing Account", "Sales Account", "Support Account").

This name will help you identify the account when managing campaigns."""
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="manage_accounts")]]
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
                import re
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
                    "✅ **Phone number set!**\n\n**Step 3/5: API ID**\n\nPlease send me the API ID for this account (get it from https://my.telegram.org).",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'api_id':
                # Validate API ID (should be numeric)
                if not message_text.isdigit():
                    await update.message.reply_text(
                        "❌ **Invalid API ID**\n\nAPI ID should be a number. Please enter a valid API ID.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                session['account_data']['api_id'] = int(message_text)
                session['step'] = 'api_hash'
                
                await update.message.reply_text(
                    "✅ **API ID set!**\n\n**Step 4/5: API Hash**\n\nPlease send me the API Hash for this account (get it from https://my.telegram.org).",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'api_hash':
                # Validate API Hash (should be 32 characters)
                if len(message_text) != 32:
                    await update.message.reply_text(
                        "❌ **Invalid API Hash**\n\nAPI Hash should be 32 characters long. Please enter a valid API Hash.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                session['account_data']['api_hash'] = message_text
                session['step'] = 'login_code'
                
                # Start the login process
                await self.start_userbot_login(update, context)
        
        # Handle campaign creation
        elif 'campaign_data' in session:
            if session['step'] == 'campaign_name':
                logger.info(f"🔍 PROCESSING CAMPAIGN NAME: '{message_text}'")
                session['campaign_data']['campaign_name'] = message_text
                session['step'] = 'ad_content'
                
                await update.message.reply_text(
                    "✅ **Campaign name set!**\n\n**Step 2/6: Ad Content**\n\nPlease send me the message content for this campaign. You can include text, emojis, and formatting.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'ad_content':
                # Handle different types of content
                if update.message.photo or update.message.video or update.message.document:
                    # Media content
                    media_data = await self.handle_media_content(update, context)
                    if media_data:
                        session['campaign_data']['ad_content'] = media_data
                        session['step'] = 'target_selection'
                        
                        await update.message.reply_text(
                            "✅ **Media content set!**\n\n**Step 3/6: Target Selection**\n\nHow would you like to select target channels?\n\n• Send channel links (one per line)\n• Or type 'all' to target all your configured channels",
                            parse_mode=ParseMode.MARKDOWN
                        )
                else:
                    # Text content
                    session['campaign_data']['ad_content'] = {
                        'type': 'text',
                        'text': message_text,
                        'entities': []
                    }
                    session['step'] = 'button_choice'
                    
                    await update.message.reply_text(
                        "✅ **Text content set!**\n\n**Step 3/6: Add Buttons?**\n\nWould you like to add buttons to your message?\n\n• Type 'yes' to add buttons\n• Type 'no' to skip buttons",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif session['step'] == 'button_choice':
                if message_text.lower() == 'yes':
                    session['step'] = 'button_input'
                    await update.message.reply_text(
                        "✅ **Adding buttons!**\n\n**Step 4/6: Button Configuration**\n\nPlease send me the button configuration in this format:\n\n`Button Text | URL`\n\nExample:\n`Visit Website | https://example.com`\n`Contact Us | https://t.me/username`\n\nYou can add multiple buttons, one per line.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                elif message_text.lower() == 'no':
                    session['campaign_data']['buttons'] = []
                    session['step'] = 'target_selection'
                    await update.message.reply_text(
                        "✅ **No buttons added!**\n\n**Step 4/6: Target Selection**\n\nHow would you like to select target channels?\n\n• Send channel links (one per line)\n• Or type 'all' to target all your configured channels",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        "❌ **Invalid choice**\n\nPlease type 'yes' to add buttons or 'no' to skip.",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif session['step'] == 'button_input':
                buttons = self.parse_button_input(message_text)
                if buttons:
                    session['campaign_data']['buttons'] = buttons
                    session['step'] = 'target_selection'
                    await update.message.reply_text(
                        f"✅ **{len(buttons)} button(s) added!**\n\n**Step 5/6: Target Selection**\n\nHow would you like to select target channels?\n\n• Send channel links (one per line)\n• Or type 'all' to target all your configured channels",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        "❌ **Invalid button format**\n\nPlease use the format: `Button Text | URL`\n\nExample:\n`Visit Website | https://example.com`",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif session['step'] == 'target_selection':
                if message_text.lower() == 'all':
                    session['campaign_data']['target_mode'] = 'all'
                    session['campaign_data']['target_chats'] = []
                else:
                    # Parse and validate channel links
                    links = [link.strip() for link in message_text.split('\n') if link.strip()]
                    valid_links = []
                    invalid_links = []
                    
                    for link in links:
                        if self.validate_channel_link(link):
                            valid_links.append(link)
                        else:
                            invalid_links.append(link)
                    
                    if invalid_links:
                        await update.message.reply_text(
                            f"❌ **Invalid channel links detected:**\n\n" + 
                            "\n".join(invalid_links) + 
                            "\n\nPlease provide valid Telegram channel links (e.g., @channelname or https://t.me/channelname)",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        return
                    
                    session['campaign_data']['target_mode'] = 'specific'
                    session['campaign_data']['target_chats'] = valid_links
                
                session['step'] = 'schedule_type'
                
                await update.message.reply_text(
                    "✅ **Targets set!**\n\n**Step 4/6: Schedule Type**\n\nWhen should this campaign run?\n\n• Type 'once' - Send immediately\n• Type 'daily' - Send daily\n• Type 'weekly' - Send weekly\n• Type 'custom' - Custom schedule",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'schedule_type':
                schedule_type = message_text.lower()
                if schedule_type not in ['once', 'daily', 'weekly', 'custom']:
                    await update.message.reply_text(
                        "❌ **Invalid schedule type**\n\nPlease enter one of: once, daily, weekly, custom",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                session['campaign_data']['schedule_type'] = schedule_type
                
                if schedule_type == 'once':
                    session['campaign_data']['schedule_time'] = 'immediate'
                    session['step'] = 'account_selection'
                    
                    await update.message.reply_text(
                        "✅ **Schedule set to immediate!**\n\n**Step 5/6: Account Selection**\n\nWhich account should send this campaign?",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    session['step'] = 'schedule_time'
                    
                    await update.message.reply_text(
                        f"✅ **Schedule type set to {schedule_type}!**\n\n**Step 5/6: Schedule Time**\n\nWhat time should the campaign run? (Format: HH:MM, e.g., 14:30)",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif session['step'] == 'schedule_time':
                import re
                time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
                if not re.match(time_pattern, message_text):
                    await update.message.reply_text(
                        "❌ **Invalid time format**\n\nPlease enter time in HH:MM format (e.g., 14:30)",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                session['campaign_data']['schedule_time'] = message_text
                session['step'] = 'account_selection'
                
                await update.message.reply_text(
                    f"✅ **Schedule time set to {message_text}!**\n\n**Step 6/6: Account Selection**\n\nWhich account should send this campaign?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=await self.get_account_selection_keyboard(user_id)
                )
            
            elif session['step'] == 'account_selection':
                # This will be handled by account selection callback
                pass
        
        # Handle forwarding configuration
        elif 'forwarding_data' in session:
            if session['step'] == 'forwarding_name':
                session['forwarding_data']['name'] = message_text
                session['step'] = 'source_channel'
                
                await update.message.reply_text(
                    "✅ **Configuration name set!**\n\n**Step 2/4: Source Channel**\n\nPlease send me the source channel link (where messages will be forwarded from).\n\nExample: @sourcechannel or https://t.me/sourcechannel",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'source_channel':
                if self.validate_channel_link(message_text):
                    session['forwarding_data']['source_channel'] = message_text
                    session['step'] = 'destination_channel'
                    
                    await update.message.reply_text(
                        "✅ **Source channel set!**\n\n**Step 3/4: Destination Channel**\n\nPlease send me the destination channel link (where messages will be forwarded to).\n\nExample: @destinationchannel or https://t.me/destinationchannel",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        "❌ **Invalid channel link**\n\nPlease provide a valid Telegram channel link (e.g., @channelname or https://t.me/channelname)",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif session['step'] == 'destination_channel':
                if self.validate_channel_link(message_text):
                    session['forwarding_data']['destination_channel'] = message_text
                    session['step'] = 'account_selection_forwarding'
                    
                    await update.message.reply_text(
                        "✅ **Destination channel set!**\n\n**Step 4/4: Account Selection**\n\nWhich account should handle this forwarding?",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=await self.get_account_selection_keyboard(user_id, "select_forwarding_account")
                    )
                else:
                    await update.message.reply_text(
                        "❌ **Invalid channel link**\n\nPlease provide a valid Telegram channel link (e.g., @channelname or https://t.me/channelname)",
                        parse_mode=ParseMode.MARKDOWN
                    )
        
        # Handle session file account setup
        elif 'session_data' in session:
            if session['step'] == 'session_account_name':
                session['account_data']['account_name'] = message_text
                session['step'] = 'session_phone'
                
                await update.message.reply_text(
                    "✅ **Account name set!**\n\n**Step 2/2: Phone Number**\n\nPlease enter the phone number for this account (e.g., +1234567890).",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'session_phone':
                session['account_data']['phone_number'] = message_text
                
                # Complete account setup with session
                account_id = await self.complete_session_account_setup(user_id, session)
                
                if account_id:
                    await update.message.reply_text(
                        f"🎉 **Account Created Successfully!**\n\n**Account ID:** {account_id}\n\nYour account has been added and is ready to use!",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
                            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
                        ])
                    )
                else:
                    await update.message.reply_text(
                        "❌ **Error creating account**\n\nPlease try again or contact support.",
                        parse_mode=ParseMode.MARKDOWN
                    )
    
    async def complete_session_account_setup(self, user_id: int, session: dict):
        """Complete account setup with session file"""
        try:
            account_data = session['account_data']
            session_string = session['session_data']
            
            # Add account to database
            account_id = self.db.add_telegram_account(
                user_id=user_id,
                account_name=account_data['account_name'],
                phone_number=account_data['phone_number'],
                api_id="",  # Not needed for session files
                api_hash="",  # Not needed for session files
                session_string=session_string
            )
            
            # Clear session
            del self.user_sessions[user_id]
            
            return account_id
            
        except Exception as e:
            logger.error(f"Error completing session account setup: {e}")
            return False
    
    async def start_userbot_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the userbot login process"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        account_data = session['account_data']
        
        try:
            from telethon import TelegramClient
            from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError
            
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
                "✅ **API Hash set!**\n\n**Step 5/5: Login Code**\n\nI've sent a verification code to your phone. Please enter the code you received.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Store client in session for code verification
            session['temp_client'] = client
            session['step'] = 'verify_code'
            
        except Exception as e:
            logger.error(f"Error starting userbot login: {e}")
            await update.message.reply_text(
                f"❌ **Login Error**\n\nFailed to start login process: {str(e)}\n\nPlease try again.",
                parse_mode=ParseMode.MARKDOWN
            )
            # Clean up session
            del self.user_sessions[user_id]
    
    async def handle_login_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle login code verification"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        if user_id not in self.user_sessions:
            return
        
        session = self.user_sessions[user_id]
        
        if session.get('step') != 'verify_code':
            return
        
        try:
            from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError
            
            client = session['temp_client']
            
            # Verify the code
            await client.sign_in(phone=session['account_data']['phone_number'], code=message_text)
            
            # Get session string
            session_string = client.session.save()
            
            # Save account to database
            account_id = self.db.add_account(
                user_id=user_id,
                account_name=session['account_data']['account_name'],
                phone_number=session['account_data']['phone_number'],
                api_id=session['account_data']['api_id'],
                api_hash=session['account_data']['api_hash'],
                session_string=session_string
            )
            
            await update.message.reply_text(
                f"🎉 **Account Setup Complete!**\n\n✅ Account '{session['account_data']['account_name']}' has been successfully added!\n\nYou can now use this account for campaigns.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Clean up
            await client.disconnect()
            del self.user_sessions[user_id]
            
        except PhoneCodeInvalidError:
            await update.message.reply_text(
                "❌ **Invalid Code**\n\nThe verification code you entered is incorrect. Please try again.",
                parse_mode=ParseMode.MARKDOWN
            )
        except SessionPasswordNeededError:
            await update.message.reply_text(
                "🔐 **2FA Required**\n\nThis account has 2FA enabled. Please enter your 2FA password.",
                parse_mode=ParseMode.MARKDOWN
            )
            session['step'] = '2fa_password'
        except FloodWaitError as e:
            await update.message.reply_text(
                f"⏳ **Rate Limited**\n\nPlease wait {e.seconds} seconds before trying again.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error verifying login code: {e}")
            await update.message.reply_text(
                f"❌ **Verification Error**\n\nFailed to verify code: {str(e)}\n\nPlease try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_2fa_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 2FA password"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        if user_id not in self.user_sessions:
            return
        
        session = self.user_sessions[user_id]
        
        if session.get('step') != '2fa_password':
            return
        
        try:
            client = session['temp_client']
            
            # Sign in with 2FA password
            await client.sign_in(password=message_text)
            
            # Get session string
            session_string = client.session.save()
            
            # Save account to database
            account_id = self.db.add_account(
                user_id=user_id,
                account_name=session['account_data']['account_name'],
                phone_number=session['account_data']['phone_number'],
                api_id=session['account_data']['api_id'],
                api_hash=session['account_data']['api_hash'],
                session_string=session_string
            )
            
            await update.message.reply_text(
                f"🎉 **Account Setup Complete!**\n\n✅ Account '{session['account_data']['account_name']}' has been successfully added!\n\nYou can now use this account for campaigns.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Clean up
            await client.disconnect()
            del self.user_sessions[user_id]
            
        except Exception as e:
            logger.error(f"Error with 2FA password: {e}")
            await update.message.reply_text(
                f"❌ **2FA Error**\n\nFailed to verify 2FA password: {str(e)}\n\nPlease try again.",
                parse_mode=ParseMode.MARKDOWN
            )

# Global bot instance to maintain user sessions
_global_bot = None

def get_testforwarder_bot():
    """Get or create the global bot instance"""
    global _global_bot
    if _global_bot is None:
        _global_bot = TgcfBot()
    return _global_bot

# Integration functions for existing bot system
async def handle_testforwarder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main entry point for testforwarder system - shows its main menu"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.show_main_menu(query)

async def handle_testforwarder_manual_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle manual setup callback for testforwarder"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.start_manual_setup(query)

async def handle_testforwarder_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages for testforwarder configuration setup"""
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

async def handle_testforwarder_bump_service(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle bump service callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.show_bump_service(query)

async def handle_testforwarder_my_configs(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle my configs callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.show_my_configs(query)

async def handle_testforwarder_add_forwarding(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle add forwarding callback"""
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id
    bot = get_testforwarder_bot()
    
    # Start forwarding configuration
    bot.user_sessions[user_id] = {"step": "forwarding_name", "forwarding_data": {}}
    
    await query.edit_message_text(
        "➕ **Add New Forwarding Configuration**\n\n**Step 1/4: Configuration Name**\n\nPlease enter a name for this forwarding configuration (e.g., 'News Forwarding', 'Product Updates').",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_testforwarder_help(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle help callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.show_help(query)

async def handle_testforwarder_manage_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle manage accounts callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.show_manage_accounts(query)

async def handle_testforwarder_upload_session(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle upload session callback"""
    query = update.callback_query
    if not query:
        return
    
    await query.edit_message_text(
        "📁 **Upload Session File**\n\nPlease upload your Telegram session file (.session).\n\n**Instructions:**\n1. Export your session from your Telegram client\n2. Upload the .session file here\n3. Enter account name and phone number\n\n**Note:** Session files contain your login credentials. Make sure you trust this bot before uploading.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to Manage Accounts", callback_data="manage_accounts")]
        ])
    )

async def handle_testforwarder_edit_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit account callback"""
    query = update.callback_query
    if not query:
        return
    await query.edit_message_text("✏️ **Edit Account**\n\nThis feature is coming soon!", parse_mode=ParseMode.MARKDOWN)

async def handle_testforwarder_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle delete account callback"""
    query = update.callback_query
    if not query:
        return
    await query.edit_message_text("🗑️ **Delete Account**\n\nThis feature is coming soon!", parse_mode=ParseMode.MARKDOWN)

async def handle_testforwarder_edit_config(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit config callback"""
    query = update.callback_query
    if not query:
        return
    await query.edit_message_text("✏️ **Edit Configuration**\n\nThis feature is coming soon!", parse_mode=ParseMode.MARKDOWN)

async def handle_testforwarder_delete_config(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle delete config callback"""
    query = update.callback_query
    if not query:
        return
    await query.edit_message_text("🗑️ **Delete Configuration**\n\nThis feature is coming soon!", parse_mode=ParseMode.MARKDOWN)

async def handle_testforwarder_add_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle add campaign callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.start_add_campaign(query)

async def handle_testforwarder_my_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle my campaigns callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_testforwarder_bot()
    await bot.show_my_campaigns(query)

async def handle_testforwarder_edit_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit campaign callback"""
    query = update.callback_query
    if not query:
        return
    await query.edit_message_text("✏️ **Edit Campaign**\n\nThis feature is coming soon!", parse_mode=ParseMode.MARKDOWN)

async def handle_testforwarder_delete_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle delete campaign callback"""
    query = update.callback_query
    if not query:
        return
    await query.edit_message_text("🗑️ **Delete Campaign**\n\nThis feature is coming soon!", parse_mode=ParseMode.MARKDOWN)

async def handle_testforwarder_run_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle run campaign callback"""
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id
    campaign_id = int(params['campaign_id'])
    
    bot = get_testforwarder_bot()
    
    # Show loading message
    await query.edit_message_text(
        "🚀 **Executing Campaign...**\n\nPlease wait while we send your campaign to all target channels.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Execute campaign
    success = await bot.execute_campaign(campaign_id)
    
    if success:
        await query.edit_message_text(
            f"✅ **Campaign Executed Successfully!**\n\nCampaign ID: {campaign_id}\n\nYour messages have been sent to all target channels.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View My Campaigns", callback_data="my_campaigns")],
                [InlineKeyboardButton("⬅️ Back to Bump Service", callback_data="bump_service")]
            ])
        )
    else:
        await query.edit_message_text(
            f"❌ **Campaign Execution Failed**\n\nCampaign ID: {campaign_id}\n\nPlease check your account settings and try again.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View My Campaigns", callback_data="my_campaigns")],
                [InlineKeyboardButton("⬅️ Back to Bump Service", callback_data="bump_service")]
            ])
        )

async def handle_testforwarder_select_forwarding_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle account selection for forwarding configuration"""
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id
    account_id = int(params['account_id'])
    
    bot = get_testforwarder_bot()
    config_id = await bot.complete_forwarding_config(user_id, account_id)
    
    if config_id:
        await query.edit_message_text(
            f"🎉 **Forwarding Configuration Created!**\n\n**Config ID:** {config_id}\n\nYour forwarding configuration has been saved and is ready to use!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View My Configurations", callback_data="my_configs")],
                [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
            ])
        )
    else:
        await query.edit_message_text(
            "❌ **Error creating forwarding configuration**\n\nPlease try again or contact support.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
            ])
        )

async def handle_testforwarder_select_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle account selection for campaign creation"""
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id
    account_id = int(params['account_id'])
    
    bot = get_testforwarder_bot()
    campaign_id = await bot.complete_campaign_creation(user_id, account_id)
    
    if campaign_id:
        await query.edit_message_text(
            f"🎉 **Campaign Created Successfully!**\n\n**Campaign ID:** {campaign_id}\n\nYour campaign has been saved and is ready to run!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View My Campaigns", callback_data="my_campaigns")],
                [InlineKeyboardButton("⬅️ Back to Bump Service", callback_data="bump_service")]
            ])
        )
    else:
        await query.edit_message_text(
            "❌ **Error creating campaign**\n\nPlease try again or contact support.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Bump Service", callback_data="bump_service")]
            ])
        )