"""
Auto Ads System - Simplified UI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Professional auto ads campaign management system with simplified 6-button interface.
Integrates with botshop while keeping auto ads accounts separate from userbots.

Author: TgCF Pro Team (Adapted for Botshop)
License: MIT
Version: 2.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from auto_ads_database import AutoAdsDatabase
from auto_ads_bump_service import AutoAdsBumpService
from auto_ads_telethon_manager import auto_ads_telethon_manager

logger = logging.getLogger(__name__)

# Global instances
db = AutoAdsDatabase()
bump_service = None  # Will be initialized when needed

# Initialize database tables on import
try:
    db.init_tables()
    logger.info("✅ Auto ads database initialized")
except Exception as e:
    logger.error(f"⚠️ Failed to initialize auto ads database: {e}")

def get_bump_service(bot_instance=None):
    """Get or create bump service instance with bot instance for button support"""
    global bump_service
    if bump_service is None:
        bump_service = AutoAdsBumpService(bot_instance=bot_instance)
    elif bot_instance and not bump_service.bot_instance:
        # Update bot instance if it wasn't set before
        bump_service.bot_instance = bot_instance
    return bump_service

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📋 MAIN MENU - Simplified 6-Button Interface
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_enhanced_auto_ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main auto ads menu with simplified 6-button interface"""
    query = update.callback_query
    if query:
        await query.answer()
    
    text = """
🚀 **Auto Ads System**

Automate your advertising campaigns across multiple Telegram accounts.

**Quick Start:**
1️⃣ Add Account - Upload your Telegram session
2️⃣ Create Campaign - Choose what and where to post
3️⃣ Start Campaign - Watch it run automatically

Select an option below:
    """
    
    keyboard = [
        [InlineKeyboardButton("📢 My Campaigns", callback_data="aa_my_campaigns"),
         InlineKeyboardButton("➕ Create Campaign", callback_data="aa_add_campaign")],
        [InlineKeyboardButton("👥 Manage Accounts", callback_data="aa_manage_accounts"),
         InlineKeyboardButton("➕ Add Account", callback_data="aa_add_account")],
        [InlineKeyboardButton("❓ Help", callback_data="aa_help"),
         InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👥 ACCOUNT MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_auto_ads_manage_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show list of accounts"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        text = """
👥 **Manage Accounts**

No accounts found.

To get started, you need to add at least one Telegram account for posting campaigns.

Click "Add Account" below to get started!
        """
        keyboard = [
            [InlineKeyboardButton("➕ Add Account", callback_data="aa_add_account")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="auto_ads_menu")]
        ]
    else:
        text = f"👥 **Manage Accounts**\n\nYou have {len(accounts)} account(s) configured:\n\n"
        keyboard = []
        
        for account in accounts:
            status = "✅" if account['is_active'] else "⏸️"
            text += f"{status} **{account['account_name']}**\n"
            text += f"   📱 {account['phone_number']}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"🗑️ Delete {account['account_name']}", 
                                   callback_data=f"aa_delete_account_{account['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add Account", callback_data="aa_add_account")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="auto_ads_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_add_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Start add account wizard"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    text = """
➕ **Add Account**

**Two Ways to Add:**

1️⃣ **Upload Session File** (Recommended)
   - Fast and easy
   - No API credentials needed
   - Upload your .session file

2️⃣ **Manual Setup**
   - Requires API ID and API Hash
   - 5-step process
   - For advanced users

Choose your method:
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 Upload Session File", callback_data="aa_upload_session")],
        [InlineKeyboardButton("⚙️ Manual Setup", callback_data="aa_manual_setup")],
        [InlineKeyboardButton("❌ Cancel", callback_data="aa_manage_accounts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_upload_session(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Start session upload wizard"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    context.user_data['aa_session'] = {
        'step': 'upload_file',
        'type': 'upload',
        'data': {}
    }
    
    text = """
📤 **Upload Session File**

**Step 1/3: Upload File**

Send me your Telegram .session file as a document.

**Requirements:**
• File must have .session extension
• File size should be less than 50KB
• Session must be valid and active

**Where to get it:**
If you used Telethon before, the file is in your script directory (e.g., `my_account.session`)

Send the file now, or click Cancel to go back.
    """
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="aa_add_account")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_manual_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Start manual setup wizard"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    context.user_data['aa_session'] = {
        'step': 'account_name',
        'type': 'manual',
        'data': {}
    }
    
    text = """
⚙️ **Manual Account Setup**

**Step 1/5: Account Name**

Please send me a name for this account (e.g., "Marketing Bot", "Promo Account").

This name will help you identify the account when managing campaigns.
    """
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="aa_add_account")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Delete account with confirmation"""
    query = update.callback_query
    await query.answer()
    
    # Extract account_id from callback_data
    callback_data = query.data
    account_id = int(callback_data.split('_')[-1])
    
    account = db.get_account(account_id)
    if not account:
        await query.answer("Account not found!", show_alert=True)
        return
    
    text = f"""
🗑️ **Delete Account**

Are you sure you want to delete this account?

**Account:** {account['account_name']}
**Phone:** {account['phone_number']}

**Warning:** This will also delete all campaigns using this account!

This action cannot be undone.
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"aa_confirm_delete_account_{account_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="aa_manage_accounts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_confirm_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Confirm and delete account"""
    query = update.callback_query
    await query.answer()
    
    # Extract account_id from callback_data
    callback_data = query.data
    account_id = int(callback_data.split('_')[-1])
    
    try:
        db.delete_account(account_id)
        await query.answer("✅ Account deleted successfully!", show_alert=True)
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        await query.answer("❌ Error deleting account. Please try again.", show_alert=True)
    
    # Show accounts list
    await handle_auto_ads_manage_accounts(update, context, params)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📢 CAMPAIGN MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_auto_ads_my_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show list of campaigns"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    service = get_bump_service(bot_instance=context.bot)
    campaigns = service.get_user_campaigns(user_id)
    
    if not campaigns:
        text = """
📢 **My Campaigns**

No campaigns found.

To get started:
1. Make sure you have at least one account added
2. Click "Create Campaign" below
3. Follow the simple 6-step wizard

Your campaigns will appear here once created!
        """
        keyboard = [
            [InlineKeyboardButton("➕ Create Campaign", callback_data="aa_add_campaign")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="auto_ads_menu")]
        ]
    else:
        text = f"📢 **My Campaigns**\n\nYou have {len(campaigns)} campaign(s):\n\n"
        keyboard = []
        
        for campaign in campaigns:
            status_icon = "▶️" if campaign['is_active'] else "⏸️"
            toggle_text = "Pause" if campaign['is_active'] else "Start"
            
            # Calculate target count correctly
            target_chats = campaign.get('target_chats', [])
            if target_chats == ['all'] or target_chats == 'all':
                target_display = "All groups"
            else:
                target_display = f"{len(target_chats)} chat(s)"
            
            text += f"{status_icon} **{campaign['campaign_name']}**\n"
            text += f"   📱 Account: {campaign.get('account_name', 'Unknown')}\n"
            text += f"   🎯 Targets: {target_display}\n"
            text += f"   📊 Sent: {campaign.get('sent_count', 0)} times\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"▶️ Start", callback_data=f"aa_start_campaign_{campaign['id']}"),
                InlineKeyboardButton(f"⏸️/{toggle_text}", callback_data=f"aa_toggle_campaign_{campaign['id']}"),
                InlineKeyboardButton("🗑️", callback_data=f"aa_delete_campaign_{campaign['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Create Campaign", callback_data="aa_add_campaign")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="auto_ads_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_add_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Start campaign creation wizard"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Check if user has accounts
    accounts = db.get_user_accounts(user_id)
    if not accounts:
        text = """
❌ **No Accounts Found**

You need to add at least one Telegram account before creating campaigns.

Click "Add Account" below to get started!
        """
        keyboard = [
            [InlineKeyboardButton("➕ Add Account", callback_data="aa_add_account")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="auto_ads_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return
    
    # Initialize campaign creation session
    context.user_data['aa_session'] = {
        'step': 'campaign_name',
        'type': 'campaign',
        'data': {}
    }
    
    text = """
➕ **Create Campaign**

**Step 1/6: Campaign Name**

Please send me a name for this campaign (e.g., "Daily Product Promo", "Weekend Sale").

This name will help you identify the campaign in your dashboard.
    """
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_start_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Execute campaign immediately"""
    query = update.callback_query
    
    # Extract campaign_id from callback_data
    callback_data = query.data
    campaign_id = int(callback_data.split('_')[-1])
    
    await query.answer("⏳ Starting campaign... This may take a moment.", show_alert=False)
    
    # Get campaign details for the confirmation message
    try:
        # Pass bot instance for inline button support
        service = get_bump_service(bot_instance=context.bot)
        campaign = service.get_campaign(campaign_id)
        
        if not campaign:
            await query.message.reply_text("❌ Campaign not found.", parse_mode=ParseMode.MARKDOWN)
            return
        
        # Execute the campaign silently (no messages)
        results = await service.execute_campaign(campaign_id)
        
        # Only show error if campaign actually failed
        if not results['success']:
            await query.message.reply_text(
                f"❌ **Campaign Failed**\n\n{results.get('message', 'Unknown error')}",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Error executing campaign: {e}")
        await query.message.reply_text(
            f"❌ Error executing campaign: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Refresh campaign list (handle callback query timeout)
    try:
        # Create a fresh update object to avoid "query too old" error
        await query.message.reply_text(
            "✅ Campaign execution complete. Use the button below to view campaigns.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 My Campaigns", callback_data="aa_my_campaigns"),
                InlineKeyboardButton("🚀 Auto Ads Menu", callback_data="auto_ads_menu")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error sending completion message: {e}")

async def handle_auto_ads_toggle_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Toggle campaign active status"""
    query = update.callback_query
    
    # Extract campaign_id from callback_data
    callback_data = query.data
    campaign_id = int(callback_data.split('_')[-1])
    
    try:
        service = get_bump_service(bot_instance=context.bot)
        success = service.toggle_campaign(campaign_id)
        
        if success:
            await query.answer("✅ Campaign status updated!", show_alert=False)
        else:
            await query.answer("❌ Failed to update campaign status", show_alert=True)
    except Exception as e:
        logger.error(f"Error toggling campaign: {e}")
        await query.answer("❌ Error updating campaign", show_alert=True)
    
    # Refresh campaign list
    await handle_auto_ads_my_campaigns(update, context, params)

async def handle_auto_ads_delete_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Delete campaign with confirmation"""
    query = update.callback_query
    await query.answer()
    
    # Extract campaign_id from callback_data
    callback_data = query.data
    campaign_id = int(callback_data.split('_')[-1])
    
    service = get_bump_service(bot_instance=context.bot)
    campaign = service.get_campaign(campaign_id)
    
    if not campaign:
        await query.answer("Campaign not found!", show_alert=True)
        return
    
    text = f"""
🗑️ **Delete Campaign**

Are you sure you want to delete this campaign?

**Campaign:** {campaign['campaign_name']}
**Account:** {campaign.get('account_name', 'Unknown')}
**Targets:** {len(campaign.get('target_chats', []))} chat(s)

This action cannot be undone.
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"aa_confirm_delete_campaign_{campaign_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_confirm_delete_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Confirm and delete campaign"""
    query = update.callback_query
    await query.answer()
    
    # Extract campaign_id from callback_data
    callback_data = query.data
    campaign_id = int(callback_data.split('_')[-1])
    
    try:
        service = get_bump_service(bot_instance=context.bot)
        service.delete_campaign(campaign_id)
        await query.answer("✅ Campaign deleted successfully!", show_alert=True)
    except Exception as e:
        logger.error(f"Error deleting campaign: {e}")
        await query.answer("❌ Error deleting campaign. Please try again.", show_alert=True)
    
    # Show campaigns list
    await handle_auto_ads_my_campaigns(update, context, params)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❓ HELP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_auto_ads_help(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show help information"""
    query = update.callback_query
    await query.answer()
    
    text = """
❓ **Auto Ads Help**

**Getting Started:**

1️⃣ **Setup Bridge Channel (REQUIRED)**
   • Create a private Telegram channel
   • Add your bot to the channel as admin
   • Add all userbots to the channel
   • Post your ad in that channel (text/photo/video)
   • Copy the message link and paste in bot when creating campaign
   • Bot will add buttons during campaign (if you specify them)

2️⃣ **Add Account**
   • Upload Telegram session file (.session)
   • Or enter API credentials manually
   • Wait for green status indicator

3️⃣ **Create Campaign**  
   • Choose account to use
   • Paste bridge channel message link
   • Select target groups (all or specific)
   • Set schedule (once/daily)

4️⃣ **Start Campaign**
   • Ads post automatically with anti-ban delays
   • 2-5 minute random delays between messages
   • Check progress in "My Campaigns"

**Why Bridge Channel?**
✅ Preserves premium emojis and formatting
✅ Supports photos, videos, animations
✅ Keeps message styling intact
✅ Can update ad content in one place

**Campaign Content Types:**
• Text messages (typed directly)
• Forwarded messages (from bridge channel)
• Bridge links (preserves premium content)

**Anti-Ban Protection:**
• Random delays: 2-5 minutes
• Night breaks: 3-6 AM (simulates sleep)
• Daily limits: 20/60/unlimited
• Account age consideration

Need more help? Contact support.
    """
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="auto_ads_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 MESSAGE HANDLERS (Multi-Step Wizards)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_auto_ads_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages during multi-step wizards"""
    if 'aa_session' not in context.user_data:
        return
    
    session = context.user_data['aa_session']
    step = session.get('step')
    session_type = session.get('type')
    
    if session_type == 'manual':
        await handle_manual_setup_message(update, context, session, step)
    elif session_type == 'upload':
        # Check if waiting for account name after upload
        if step == 'account_name':
            await handle_session_upload_name(update, context)
        elif step == 'phone_api':
            await handle_session_upload_api(update, context)
    elif session_type == 'campaign':
        # Route campaign wizard messages
        if step == 'ad_content':
            await handle_auto_ads_ad_content_received(update, context)
        elif step == 'button_input':
            await handle_button_input(update, context)
        elif step == 'target_chats_input':
            await handle_target_chats_input(update, context)
        elif step == 'schedule_time':
            await handle_schedule_time_input(update, context)
        else:
            await handle_campaign_message(update, context, session, step)

async def handle_manual_setup_message(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict, step: str):
    """Handle manual account setup messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if step == 'account_name':
        session['data']['account_name'] = text
        session['step'] = 'phone_number'
        
        await update.message.reply_text(
            "⚙️ **Step 2/5: Phone Number**\n\nPlease send me the phone number of this Telegram account (with country code, e.g., +1234567890):",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif step == 'phone_number':
        session['data']['phone_number'] = text
        session['step'] = 'api_id'
        
        await update.message.reply_text(
            "⚙️ **Step 3/5: API ID**\n\nPlease send me the API ID from my.telegram.org:",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif step == 'api_id':
        session['data']['api_id'] = text
        session['step'] = 'api_hash'
        
        await update.message.reply_text(
            "⚙️ **Step 4/5: API Hash**\n\nPlease send me the API Hash from my.telegram.org:",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif step == 'api_hash':
        session['data']['api_hash'] = text
        session['step'] = 'login_code'
        
        # Create Telethon client and send code request
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            api_id = int(session['data']['api_id'])
            api_hash = session['data']['api_hash']
            phone = session['data']['phone_number']
            
            # Create temp client to send code
            temp_client = TelegramClient(
                StringSession(),
                api_id,
                api_hash
            )
            
            await temp_client.connect()
            
            # Send code request
            await temp_client.send_code_request(phone)
            
            # Store client in session for later use
            session['temp_client'] = temp_client
            context.user_data['aa_session'] = session
            
            await update.message.reply_text(
                "⚙️ **Step 5/5: Login Code**\n\n"
                "📱 A login code has been sent to your Telegram account.\n\n"
                "Please check your Telegram app and send me the code here (e.g., 12345):",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error sending login code: {e}")
            await update.message.reply_text(
                f"❌ **Error Sending Login Code**\n\n{str(e)}\n\n"
                "Please verify:\n"
                "• Phone number is correct (with country code)\n"
                "• API ID and API Hash are valid\n"
                "• Account exists and is not banned",
                parse_mode=ParseMode.MARKDOWN
            )
            # Clear session on error
            if 'aa_session' in context.user_data:
                del context.user_data['aa_session']
    
    elif step == 'login_code':
        # User provided login code
        code = text.replace(' ', '').replace('-', '')  # Clean code
        
        try:
            temp_client = session.get('temp_client')
            if not temp_client:
                raise Exception("Session expired. Please start again.")
            
            phone = session['data']['phone_number']
            
            # Try to login with code
            try:
                await temp_client.sign_in(phone, code)
            except SessionPasswordNeededError:
                # 2FA enabled - ask for password
                session['step'] = '2fa_password'
                context.user_data['aa_session'] = session
                
                await update.message.reply_text(
                    "🔐 **Two-Factor Authentication**\n\n"
                    "Your account has 2FA enabled. Please send me your 2FA password:",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Get session string
            session_string = temp_client.session.save()
            
            # Disconnect temp client
            await temp_client.disconnect()
            
            # Save account to database
            account_id = db.add_telegram_account(
                user_id=user_id,
                account_name=session['data']['account_name'],
                phone_number=phone,
                api_id=session['data']['api_id'],
                api_hash=session['data']['api_hash'],
                session_string=session_string
            )
            
            keyboard = [[InlineKeyboardButton("🚀 Go to Auto Ads System", callback_data="auto_ads_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ **Account Added Successfully!**\n\n"
                f"Account Name: {session['data']['account_name']}\n"
                f"Phone: {phone}\n\n"
                "You can now create campaigns using this account!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            # Clear session
            del context.user_data['aa_session']
            
        except Exception as e:
            logger.error(f"Error logging in: {e}")
            error_msg = str(e)
            
            if "PHONE_CODE_INVALID" in error_msg:
                await update.message.reply_text(
                    "❌ **Invalid Code**\n\n"
                    "The code you provided is incorrect. Please try again or restart the setup.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"❌ **Login Error**\n\n{error_msg}\n\n"
                    "Please try again or contact support.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Clear session on error
            if 'aa_session' in context.user_data:
                del context.user_data['aa_session']
    
    elif step == '2fa_password':
        # User provided 2FA password
        password = text
        
        try:
            temp_client = session.get('temp_client')
            if not temp_client:
                raise Exception("Session expired. Please start again.")
            
            # Login with 2FA password
            await temp_client.sign_in(password=password)
            
            # Get session string
            session_string = temp_client.session.save()
            
            # Disconnect temp client
            await temp_client.disconnect()
            
            phone = session['data']['phone_number']
            
            # Save account to database
            account_id = db.add_telegram_account(
                user_id=user_id,
                account_name=session['data']['account_name'],
                phone_number=phone,
                api_id=session['data']['api_id'],
                api_hash=session['data']['api_hash'],
                session_string=session_string
            )
            
            keyboard = [[InlineKeyboardButton("🚀 Go to Auto Ads System", callback_data="auto_ads_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ **Account Added Successfully!**\n\n"
                f"Account Name: {session['data']['account_name']}\n"
                f"Phone: {phone}\n\n"
                "You can now create campaigns using this account!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            # Clear session
            del context.user_data['aa_session']
            
        except Exception as e:
            logger.error(f"Error with 2FA: {e}")
            await update.message.reply_text(
                f"❌ **2FA Error**\n\n{str(e)}\n\n"
                "Password may be incorrect. Please try the setup again.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Clear session on error
            if 'aa_session' in context.user_data:
                del context.user_data['aa_session']

async def handle_campaign_message(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict, step: str):
    """Handle campaign creation messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if step == 'campaign_name':
        session['data']['campaign_name'] = text
        session['step'] = 'select_account'
        
        # Show account selection
        accounts = db.get_user_accounts(user_id)
        keyboard = []
        for account in accounts:
            keyboard.append([InlineKeyboardButton(
                f"📱 {account['account_name']} ({account['phone_number']})",
                callback_data=f"aa_select_account_{account['id']}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "➕ **Step 2/6: Select Account**\n\nWhich account should post this campaign?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

async def handle_auto_ads_select_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle account selection for campaign"""
    query = update.callback_query
    await query.answer()
    
    # Extract account_id from callback_data
    callback_data = query.data
    account_id = int(callback_data.split('_')[-1])
    
    session = context.user_data.get('aa_session', {})
    session['data']['account_id'] = account_id
    session['step'] = 'ad_content'
    context.user_data['aa_session'] = session
    
    text = """
➕ **Step 3/6: Ad Content**

What would you like to post?

**Option 1:** Type your ad text directly

**Option 2:** Paste a bridge channel link (RECOMMENDED)
   • Right-click message in channel → Copy Link
   • Format: t.me/yourchannel/123
   • Preserves premium emojis, photos, videos

**Option 3:** Forward a message from bridge channel

Send your content now:
    """
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_ad_content_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad content received"""
    session = context.user_data.get('aa_session', {})
    
    # Store ad content
    if hasattr(update.message, 'forward_date') and update.message.forward_date:
        # Forwarded message
        session['data']['ad_content'] = {
            'type': 'forward',
            'text': update.message.text or update.message.caption or '[Media]',
            'forwarded_message': True
        }
    elif update.message.text and ('t.me/' in update.message.text or 'telegram.me/' in update.message.text):
        # Bridge channel link - parse to extract channel ID and message ID
        import re
        bridge_text = update.message.text.strip()
        
        # Try to parse: https://t.me/c/1234567890/123 or https://t.me/channelname/123
        match = re.search(r't\.me/c/(\d+)/(\d+)', bridge_text)
        if match:
            # Private channel: https://t.me/c/1234567890/123
            channel_id = int('-100' + match.group(1))  # Convert to full channel ID
            message_id = int(match.group(2))
            session['data']['ad_content'] = {
                'type': 'bridge',
                'text': bridge_text,
                'bridge_channel': True,
                'bridge_channel_entity': channel_id,
                'bridge_message_id': message_id
            }
        else:
            # Try public channel: https://t.me/channelname/123
            match = re.search(r't\.me/([a-zA-Z0-9_]+)/(\d+)', bridge_text)
            if match:
                channel_username = '@' + match.group(1)
                message_id = int(match.group(2))
                session['data']['ad_content'] = {
                    'type': 'bridge',
                    'text': bridge_text,
                    'bridge_channel': True,
                    'bridge_channel_entity': channel_username,
                    'bridge_message_id': message_id
                }
            else:
                # Couldn't parse - store as-is (will fail later with better error)
                session['data']['ad_content'] = {
                    'type': 'bridge',
                    'text': bridge_text,
                    'bridge_channel': True,
                    'error': 'Could not parse message link - please use format: https://t.me/c/channelid/messageid'
                }
    else:
        # Regular text
        session['data']['ad_content'] = {
            'type': 'text',
            'text': update.message.text or update.message.caption or '[Media]'
        }
    
    session['step'] = 'button_choice'
    context.user_data['aa_session'] = session
    
    # Ask about buttons
    text = """
➕ **Step 4/6: Add Buttons**

Would you like to add clickable buttons under your ad?

**The bot will add these buttons automatically when sending your ad!**

**Example buttons:**
• Shop Now → https://example.com
• Contact Us → https://t.me/support  
• Visit Website → https://mysite.com

Choose an option:
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Add Buttons", callback_data="aa_add_buttons_yes")],
        [InlineKeyboardButton("❌ No Buttons", callback_data="aa_add_buttons_no")],
        [InlineKeyboardButton("🔙 Cancel", callback_data="aa_my_campaigns")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_add_buttons_yes(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle user choosing to add buttons"""
    query = update.callback_query
    await query.answer()
    
    session = context.user_data.get('aa_session', {})
    session['step'] = 'button_input'
    context.user_data['aa_session'] = session
    
    text = """
➕ **Add Buttons to Your Ad**

**Format:** `[Button Text] - [URL]`

**Examples:**
```
Shop Now - https://example.com/shop
Visit Website - https://mysite.com
Contact Us - https://t.me/support
```

**Instructions:**
• Send one button per message
• Or send multiple buttons separated by new lines
• When finished, type `done` or `finish`

**The bot will automatically add these buttons when sending your ad!**

Send your first button now:
    """
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_auto_ads_add_buttons_no(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle user choosing to skip buttons"""
    query = update.callback_query
    await query.answer()
    
    session = context.user_data.get('aa_session', {})
    session['data']['buttons'] = []  # No buttons
    session['step'] = 'target_chats'
    context.user_data['aa_session'] = session
    
    # Show target selection
    text = """
➕ **Step 5/6: Target Chats**

Where should this be posted?

**Option 1:** All groups the account is in
**Option 2:** Specific chats (you'll provide chat IDs/usernames)

Choose an option:
    """
    
    keyboard = [
        [InlineKeyboardButton("📢 All Groups", callback_data="aa_target_all_groups")],
        [InlineKeyboardButton("🎯 Specific Chats", callback_data="aa_target_specific_chats")],
        [InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_target_all_groups(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle target all groups selection"""
    query = update.callback_query
    await query.answer()
    
    session = context.user_data.get('aa_session', {})
    session['data']['target_chats'] = ['all']
    session['step'] = 'schedule'
    context.user_data['aa_session'] = session
    
    text = """
➕ **Step 5/6: Schedule**

When should this campaign run?

Choose a schedule type:
    """
    
    keyboard = [
        [InlineKeyboardButton("▶️ Once (Now)", callback_data="aa_schedule_once")],
        [InlineKeyboardButton("📅 Daily", callback_data="aa_schedule_daily")],
        [InlineKeyboardButton("📆 Weekly", callback_data="aa_schedule_weekly")],
        [InlineKeyboardButton("⏰ Hourly", callback_data="aa_schedule_hourly")],
        [InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_target_specific_chats(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle target specific chats selection"""
    query = update.callback_query
    await query.answer()
    
    session = context.user_data.get('aa_session', {})
    session['step'] = 'target_chats_input'
    context.user_data['aa_session'] = session
    
    text = """
➕ **Step 4/6: Target Chats**

Please send me a list of chat IDs or usernames, one per line.

**Examples:**
```
@mychannel
@mygroup
-1001234567890
```

Send the list now:
    """
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_schedule_once(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle schedule once selection"""
    query = update.callback_query
    await query.answer()
    
    session = context.user_data.get('aa_session', {})
    session['data']['schedule_type'] = 'once'
    session['data']['schedule_time'] = 'now'
    
    # Show review
    await show_campaign_review(query, context, session)

async def handle_auto_ads_schedule_daily(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle schedule daily selection"""
    query = update.callback_query
    await query.answer()
    
    session = context.user_data.get('aa_session', {})
    session['data']['schedule_type'] = 'daily'
    session['step'] = 'schedule_time'
    context.user_data['aa_session'] = session
    
    text = """
➕ **Step 5/6: Schedule Time**

Please send me the time when you want this campaign to run daily (e.g., "09:00", "14:30"):
    """
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_auto_ads_schedule_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle schedule weekly selection"""
    query = update.callback_query
    await query.answer()
    
    session = context.user_data.get('aa_session', {})
    session['data']['schedule_type'] = 'weekly'
    session['data']['schedule_time'] = 'Monday 09:00'
    
    # Show review
    await show_campaign_review(query, context, session)

async def handle_auto_ads_schedule_hourly(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle schedule hourly selection"""
    query = update.callback_query
    await query.answer()
    
    session = context.user_data.get('aa_session', {})
    session['data']['schedule_type'] = 'hourly'
    session['data']['schedule_time'] = 'every hour'
    
    # Show review
    await show_campaign_review(query, context, session)

async def show_campaign_review(query, context, session):
    """Show campaign review and confirm"""
    data = session['data']
    
    # Format buttons if present
    button_text = "No buttons"
    if data.get('buttons'):
        button_list = [f"• {btn['text']} → {btn['url']}" for btn in data['buttons']]
        button_text = "\n".join(button_list)
    
    text = f"""
➕ **Step 6/6: Review & Confirm**

**Campaign Name:** {data.get('campaign_name', 'N/A')}
**Account ID:** {data.get('account_id', 'N/A')}
**Content Type:** {data.get('ad_content', {}).get('type', 'text')}
**Target Chats:** {len(data.get('target_chats', [])) if data.get('target_chats') != ['all'] else 'All Groups'}
**Buttons:** 
{button_text}
**Schedule:** {data.get('schedule_type', 'once').title()} at {data.get('schedule_time', 'now')}

Ready to create this campaign?
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ Create Campaign", callback_data="aa_confirm_create_campaign")],
        [InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_auto_ads_confirm_create_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Confirm and create campaign"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    session = context.user_data.get('aa_session', {})
    data = session.get('data', {})
    
    try:
        service = get_bump_service(bot_instance=context.bot)
        campaign_id = service.add_campaign(
            user_id=user_id,
            account_id=data['account_id'],
            campaign_name=data['campaign_name'],
            ad_content=data['ad_content'],
            target_chats=data['target_chats'],
            buttons=data.get('buttons'),
            schedule_type=data.get('schedule_type', 'once'),
            schedule_time=data.get('schedule_time', 'now')
        )
        
        # Clear session first
        del context.user_data['aa_session']
        
        # Show "Campaign Started" message
        start_message = f"""
🚀 **Campaign Started!**

**Name:** {data['campaign_name']}
**Schedule:** {data.get('schedule_type', 'once').title()}
**Status:** Running...

⏳ Sending ads to all target groups now...
        """
        await query.edit_message_text(start_message, parse_mode=ParseMode.MARKDOWN)
        
        # AUTO-START the campaign immediately
        logger.info(f"🚀 Auto-starting campaign {campaign_id} after creation")
        results = await service.execute_campaign(campaign_id)
        
        # Show final success message with navigation
        # Campaign created and started silently - no success message needed
        # Just show navigation options
        keyboard = [
            [InlineKeyboardButton("📋 My Campaigns", callback_data="aa_my_campaigns")],
            [InlineKeyboardButton("🔙 Auto Ads Menu", callback_data="auto_ads_menu")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Campaign created and running in background.",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        await query.edit_message_text(
            f"❌ **Error Creating Campaign**\n\n{str(e)}\n\nPlease try again or contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_auto_ads_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (session files)"""
    if 'aa_session' not in context.user_data:
        return
    
    session = context.user_data['aa_session']
    if session.get('type') != 'upload' or session.get('step') != 'upload_file':
        return
    
    document = update.message.document
    
    # Check file extension
    if not document.file_name.endswith('.session'):
        await update.message.reply_text(
            "❌ **Invalid File**\n\nPlease upload a file with .session extension.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Check file size
    if document.file_size > 50000:  # 50KB
        await update.message.reply_text(
            "❌ **File Too Large**\n\nSession files should be less than 50KB.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        # Download file
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        
        # Encode to base64
        session_string = base64.b64encode(file_bytes).decode('utf-8')
        
        session['data']['session_string'] = session_string
        session['data']['file_name'] = document.file_name
        session['step'] = 'account_name'
        
        await update.message.reply_text(
            "✅ **File Uploaded Successfully!**\n\n📤 **Step 2/3: Account Name**\n\nPlease send me a name for this account (e.g., \"Marketing Bot\", \"Promo Account\"):",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error processing session file: {e}")
        await update.message.reply_text(
            f"❌ **Error Processing File**\n\n{str(e)}\n\nPlease try again or use manual setup.",
            parse_mode=ParseMode.MARKDOWN
        )

# Continue with account name after session upload
async def handle_session_upload_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle account name after session upload"""
    if 'aa_session' not in context.user_data:
        return
    
    session = context.user_data['aa_session']
    if session.get('type') != 'upload' or session.get('step') != 'account_name':
        return
    
    user_id = update.effective_user.id
    account_name = update.message.text
    session['data']['account_name'] = account_name
    session['step'] = 'phone_api'
    
    context.user_data['aa_session'] = session
    
    await update.message.reply_text(
        "📤 **Step 3/3: API Credentials**\n\nPlease send me your API ID and API Hash separated by a space (e.g., `12345678 abcdef1234567890abcdef1234567890`):\n\nGet them from https://my.telegram.org",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_session_upload_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle API credentials after session upload"""
    session = context.user_data.get('aa_session', {})
    if session.get('type') != 'upload' or session.get('step') != 'phone_api':
        return
    
    user_id = update.effective_user.id
    text = update.message.text
    
    # Parse API ID and API Hash
    parts = text.split()
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Invalid format. Please send API ID and API Hash separated by a space (e.g., `12345678 abcdef1234567890`):",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    api_id, api_hash = parts
    session['data']['api_id'] = api_id
    session['data']['api_hash'] = api_hash
    session['data']['phone_number'] = 'N/A'  # Not provided in this flow
    
    # Save account to database
    try:
        account_id = db.add_telegram_account(
            user_id=user_id,
            account_name=session['data']['account_name'],
            phone_number=session['data']['phone_number'],
            api_id=api_id,
            api_hash=api_hash,
            session_string=session['data']['session_string']
        )
        
        keyboard = [[InlineKeyboardButton("🚀 Go to Auto Ads System", callback_data="auto_ads_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ **Account Added Successfully!**\n\nAccount Name: {session['data']['account_name']}\nAccount ID: {account_id}\n\nYou can now create campaigns using this account!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        # Clear session
        del context.user_data['aa_session']
        
    except Exception as e:
        logger.error(f"Error adding account: {e}")
        await update.message.reply_text(
            f"❌ **Error Adding Account**\n\n{str(e)}\n\nPlease try again or contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_button_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button input from user"""
    session = context.user_data.get('aa_session', {})
    if session.get('step') != 'button_input':
        return
    
    text = update.message.text.strip()
    
    # Check if user wants to finish
    if text.lower() in ['done', 'finish', 'complete', 'end']:
        session['step'] = 'target_chats'
        context.user_data['aa_session'] = session
        
        # Show target selection
        target_text = """
➕ **Step 5/6: Target Chats**

Where should this be posted?

**Option 1:** All groups the account is in
**Option 2:** Specific chats (you'll provide chat IDs/usernames)

Choose an option:
        """
        
        keyboard = [
            [InlineKeyboardButton("📢 All Groups", callback_data="aa_target_all_groups")],
            [InlineKeyboardButton("🎯 Specific Chats", callback_data="aa_target_specific_chats")],
            [InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        button_count = len(session['data'].get('buttons', []))
        await update.message.reply_text(
            f"✅ **Buttons Saved!** ({button_count} button{'s' if button_count != 1 else ''})\n\n{target_text}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    # Parse button input
    buttons = session['data'].get('buttons', [])
    
    # Support multiple buttons separated by newlines
    lines = text.split('\n')
    parsed_count = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Expected format: [Button Text] - [URL]
        if ' - ' in line:
            parts = line.split(' - ', 1)
            button_text = parts[0].strip()
            button_url = parts[1].strip()
            
            if button_text and button_url:
                buttons.append({'text': button_text, 'url': button_url})
                parsed_count += 1
    
    session['data']['buttons'] = buttons
    context.user_data['aa_session'] = session
    
    if parsed_count > 0:
        await update.message.reply_text(
            f"✅ **Button{'s' if parsed_count > 1 else ''} Added!** ({parsed_count})\n\n"
            f"Total buttons: {len(buttons)}\n\n"
            f"**Send more buttons or type 'done' when finished.**",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ **Invalid Format!**\n\n"
            "**Please use this format:**\n"
            "`Button Text - URL`\n\n"
            "**Example:**\n"
            "`Shop Now - https://example.com`\n\n"
            "Try again or type 'done' to finish.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_target_chats_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle target chats input"""
    session = context.user_data.get('aa_session', {})
    if session.get('step') != 'target_chats_input':
        return
    
    text = update.message.text
    chats = [line.strip() for line in text.split('\n') if line.strip()]
    
    session['data']['target_chats'] = chats
    session['step'] = 'schedule'
    context.user_data['aa_session'] = session
    
    # Show schedule selection
    text_msg = """
➕ **Step 5/6: Schedule**

When should this campaign run?

Choose a schedule type:
    """
    
    keyboard = [
        [InlineKeyboardButton("▶️ Once (Now)", callback_data="aa_schedule_once")],
        [InlineKeyboardButton("📅 Daily", callback_data="aa_schedule_daily")],
        [InlineKeyboardButton("📆 Weekly", callback_data="aa_schedule_weekly")],
        [InlineKeyboardButton("⏰ Hourly", callback_data="aa_schedule_hourly")],
        [InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_schedule_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle schedule time input"""
    session = context.user_data.get('aa_session', {})
    if session.get('step') != 'schedule_time':
        return
    
    time_str = update.message.text
    session['data']['schedule_time'] = time_str
    context.user_data['aa_session'] = session
    
    # Show review
    data = session['data']
    
    # Format buttons if present
    button_text = "No buttons"
    if data.get('buttons'):
        button_list = [f"• {btn['text']} → {btn['url']}" for btn in data['buttons']]
        button_text = "\n".join(button_list)
    
    text = f"""
➕ **Step 6/6: Review & Confirm**

**Campaign Name:** {data.get('campaign_name', 'N/A')}
**Account ID:** {data.get('account_id', 'N/A')}
**Content Type:** {data.get('ad_content', {}).get('type', 'text')}
**Target Chats:** {len(data.get('target_chats', [])) if data.get('target_chats') != ['all'] else 'All Groups'}
**Buttons:** 
{button_text}
**Schedule:** {data.get('schedule_type', 'once').title()} at {data.get('schedule_time', 'now')}

Ready to create this campaign?
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ Create Campaign", callback_data="aa_confirm_create_campaign")],
        [InlineKeyboardButton("❌ Cancel", callback_data="aa_my_campaigns")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🗄️ DATABASE INITIALIZATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def init_enhanced_auto_ads_tables():
    """Initialize auto ads database tables"""
    from utils import get_db_connection
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Auto ads accounts table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS auto_ads_accounts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                account_name VARCHAR(255),
                phone_number VARCHAR(50),
                api_id VARCHAR(100),
                api_hash VARCHAR(255),
                session_string TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Auto ads campaigns table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS auto_ads_campaigns (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                account_id INTEGER REFERENCES auto_ads_accounts(id) ON DELETE CASCADE,
                campaign_name VARCHAR(255),
                ad_content JSONB,
                target_chats JSONB,
                buttons JSONB,
                schedule_type VARCHAR(50),
                schedule_time VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                sent_count INTEGER DEFAULT 0,
                last_sent TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Account usage tracking table (for anti-ban)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS account_usage_tracking (
                id SERIAL PRIMARY KEY,
                account_id INTEGER REFERENCES auto_ads_accounts(id) ON DELETE CASCADE,
                account_created_date TIMESTAMP,
                daily_limit INTEGER DEFAULT 50,
                messages_sent_today INTEGER DEFAULT 0,
                last_reset_date DATE DEFAULT CURRENT_DATE,
                total_messages_sent INTEGER DEFAULT 0,
                last_message_sent_at TIMESTAMP,
                is_in_cooldown BOOLEAN DEFAULT FALSE,
                cooldown_until TIMESTAMP,
                peer_flood_detected_at TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        cur.execute('CREATE INDEX IF NOT EXISTS idx_auto_ads_accounts_user_id ON auto_ads_accounts(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_auto_ads_campaigns_user_id ON auto_ads_campaigns(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_auto_ads_campaigns_account_id ON auto_ads_campaigns(account_id)')
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("✅ Auto ads tables initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Error initializing auto ads tables: {e}")
        raise

