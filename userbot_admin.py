"""
Userbot Admin Interface
Handles all admin interface for userbot configuration and management
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime

from userbot_config import userbot_config
from userbot_manager import userbot_manager
from userbot_database import (
    get_delivery_stats,
    get_connection_status,
    reset_userbot_config,
    init_userbot_tables
)
from product_delivery import test_userbot_delivery
from utils import is_primary_admin, send_message_with_retry

logger = logging.getLogger(__name__)

# ==================== MAIN USERBOT CONTROL PANEL ====================

async def handle_userbot_control(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main userbot control panel"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    # Check if configured
    if not userbot_config.is_configured():
        await _show_setup_wizard(query, context)
        return
    
    # Show status dashboard
    await _show_status_dashboard(query, context)

async def _show_setup_wizard(query, context):
    """Show initial setup wizard"""
    msg = "🤖 <b>Userbot Setup Wizard</b>\n\n"
    msg += "Welcome to the userbot configuration!\n\n"
    msg += "<b>What is a userbot?</b>\n"
    msg += "A userbot delivers products to customers via secret chats with self-destructing messages for enhanced privacy.\n\n"
    msg += "<b>Requirements:</b>\n"
    msg += "• A separate Telegram account (NOT your bot account)\n"
    msg += "• API ID and API Hash from https://my.telegram.org\n"
    msg += "• Phone number for verification\n\n"
    msg += "Click <b>Start Setup</b> to begin!"
    
    keyboard = [
        [InlineKeyboardButton("🚀 Start Setup", callback_data="userbot_setup_start")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def _show_status_dashboard(query, context):
    """Show userbot status dashboard"""
    config = userbot_config.get_dict()
    status = get_connection_status()
    stats = get_delivery_stats()
    
    msg = "🤖 <b>Userbot Control Panel</b>\n\n"
    
    # Configuration status
    config_status = "✅ Configured" if userbot_config.is_configured() else "❌ Not Configured"
    msg += f"<b>Configuration Status:</b> {config_status}\n"
    
    # Connection status
    is_connected = status.get('is_connected', False)
    conn_status = "✅ Connected" if is_connected else "❌ Disconnected"
    status_msg = status.get('status_message', 'Unknown')
    msg += f"<b>Connection Status:</b> {conn_status}\n"
    msg += f"*{status_msg}*\n"
    
    # Last updated
    last_updated = status.get('last_updated')
    if last_updated:
        msg += f"<b>Last Updated:</b> {last_updated.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    
    msg += "\n<b>Settings:</b>\n"
    
    # Enabled status
    enabled = config.get('enabled', False)
    enabled_status = "✅ Enabled" if enabled else "❌ Disabled"
    msg += f"• Delivery: {enabled_status}\n"
    
    # Auto-reconnect
    auto_reconnect = config.get('auto_reconnect', True)
    reconnect_status = "✅ Enabled" if auto_reconnect else "❌ Disabled"
    msg += f"• Auto-Reconnect: {reconnect_status}\n"
    
    # Notifications
    notifications = config.get('send_notifications', True)
    notif_status = "✅ Enabled" if notifications else "❌ Disabled"
    msg += f"• Admin Notifications: {notif_status}\n"
    
    # TTL
    ttl = config.get('secret_chat_ttl', 86400)
    ttl_hours = ttl // 3600
    msg += f"• Message TTL: {ttl_hours} hours\n"
    
    # Max retries
    max_retries = config.get('max_retries', 3)
    msg += f"• Max Retries: {max_retries}\n"
    
    msg += "\n<b>Statistics:</b>\n"
    msg += f"• Total Deliveries: {stats['total']}\n"
    msg += f"• Success Rate: {stats['success_rate']}%\n"
    msg += f"• Failed Deliveries: {stats['failed']}\n"
    
    # Build keyboard based on connection status
    keyboard = []
    
    if is_connected:
        keyboard.append([
            InlineKeyboardButton("🔌 Disconnect", callback_data="userbot_disconnect"),
            InlineKeyboardButton("🧪 Test", callback_data="userbot_test")
        ])
    else:
        keyboard.append([InlineKeyboardButton("🔌 Connect", callback_data="userbot_connect")])
    
    keyboard.extend([
        [InlineKeyboardButton("⚙️ Settings", callback_data="userbot_settings"),
         InlineKeyboardButton("📊 Stats", callback_data="userbot_stats")],
        [InlineKeyboardButton("🗑️ Reset Config", callback_data="userbot_reset_confirm")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== SETUP WIZARD ====================

async def handle_userbot_setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Start setup wizard - ask for API ID"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    msg = "🔧 <b>Step 1/3: API ID</b>\n\n"
    msg += "Get your API ID from: https://my.telegram.org\n\n"
    msg += "1. Log in with your phone number\n"
    msg += "2. Go to 'API development tools'\n"
    msg += "3. Create an application if you haven't\n"
    msg += "4. Copy your <b>API ID</b>\n\n"
    msg += "📝 <b>Please send your API ID now:</b>"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="userbot_control")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    # Set state
    context.user_data['state'] = 'awaiting_userbot_api_id'

async def handle_userbot_api_id_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle API ID input"""
    if context.user_data.get('state') != 'awaiting_userbot_api_id':
        return
    
    user_id = update.effective_user.id
    if not is_primary_admin(user_id):
        return
    
    api_id = update.message.text.strip()
    
    # Validate API ID (should be numeric)
    if not api_id.isdigit():
        await update.message.reply_text(
            "❌ <b>Invalid API ID</b>\n\nAPI ID should be a number. Please try again:",
            parse_mode='HTML'
        )
        return
    
    # Store in context
    context.user_data['userbot_api_id'] = api_id
    context.user_data['state'] = 'awaiting_userbot_api_hash'
    
    msg = "✅ <b>API ID Saved!</b>\n\n"
    msg += "🔧 <b>Step 2/3: API Hash</b>\n\n"
    msg += "From the same page (https://my.telegram.org), copy your <b>API Hash</b>.\n\n"
    msg += "📝 <b>Please send your API Hash now:</b>"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="userbot_control")]]
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_userbot_api_hash_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle API Hash input"""
    if context.user_data.get('state') != 'awaiting_userbot_api_hash':
        return
    
    user_id = update.effective_user.id
    if not is_primary_admin(user_id):
        return
    
    api_hash = update.message.text.strip()
    
    # Validate API Hash (should be alphanumeric, 32 chars)
    if len(api_hash) < 20:
        await update.message.reply_text(
            "❌ <b>Invalid API Hash</b>\n\nAPI Hash seems too short. Please check and try again:",
            parse_mode='HTML'
        )
        return
    
    # Store in context
    context.user_data['userbot_api_hash'] = api_hash
    context.user_data['state'] = 'awaiting_userbot_phone'
    
    msg = "✅ <b>API Hash Saved!</b>\n\n"
    msg += "🔧 <b>Step 3/3: Phone Number</b>\n\n"
    msg += "Enter the phone number for your userbot account.\n\n"
    msg += "<b>Format:</b> +1234567890 (include country code)\n\n"
    msg += "📝 <b>Please send your phone number now:</b>"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="userbot_control")]]
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_userbot_phone_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number input and start authentication"""
    if context.user_data.get('state') != 'awaiting_userbot_phone':
        return
    
    user_id = update.effective_user.id
    if not is_primary_admin(user_id):
        return
    
    phone_number = update.message.text.strip()
    
    # Validate phone number (should start with +)
    if not phone_number.startswith('+'):
        await update.message.reply_text(
            "❌ <b>Invalid Phone Number</b>\n\nPhone number must start with + and include country code.\n\nExample: +1234567890\n\nPlease try again:",
            parse_mode='HTML'
        )
        return
    
    # Get API credentials from context
    api_id = context.user_data.get('userbot_api_id')
    api_hash = context.user_data.get('userbot_api_hash')
    
    if not api_id or not api_hash:
        await update.message.reply_text("❌ <b>Error:</b> Setup data lost. Please start again.")
        context.user_data.pop('state', None)
        return
    
    # Save config to database
    userbot_config.save(api_id, api_hash, phone_number)
    
    # Start phone authentication
    await update.message.reply_text("⏳ <b>Sending verification code...</b>", parse_mode='HTML')
    
    result = await userbot_manager.start_phone_auth(phone_number)
    
    if not result['success']:
        error_msg = result.get('error', 'Unknown error')
        await update.message.reply_text(
            f"❌ <b>Authentication Failed</b>\n\n{error_msg}\n\nPlease try again or contact support.",
            parse_mode='HTML'
        )
        context.user_data.pop('state', None)
        return
    
    # Store phone for verification step
    context.user_data['userbot_phone'] = phone_number
    context.user_data['state'] = 'awaiting_userbot_verification_code'
    
    msg = "✅ <b>Verification Code Sent!</b>\n\n"
    msg += f"A verification code has been sent to <b>{phone_number}</b>.\n\n"
    msg += "📝 <b>Please send the verification code now:</b>"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="userbot_control")]]
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_userbot_verification_code_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verification code input"""
    if context.user_data.get('state') != 'awaiting_userbot_verification_code':
        return
    
    user_id = update.effective_user.id
    if not is_primary_admin(user_id):
        return
    
    code = update.message.text.strip()
    phone_number = context.user_data.get('userbot_phone')
    
    if not phone_number:
        await update.message.reply_text("❌ <b>Error:</b> Phone number not found. Please start again.")
        context.user_data.pop('state', None)
        return
    
    await update.message.reply_text("⏳ <b>Verifying code...</b>", parse_mode='HTML')
    
    result = await userbot_manager.verify_phone_code(phone_number, code)
    
    if not result['success']:
        error_msg = result.get('error', 'Unknown error')
        await update.message.reply_text(
            f"❌ <b>Verification Failed</b>\n\n{error_msg}\n\nPlease try again:",
            parse_mode='HTML'
        )
        return
    
    # Clear state
    context.user_data.pop('state', None)
    context.user_data.pop('userbot_api_id', None)
    context.user_data.pop('userbot_api_hash', None)
    context.user_data.pop('userbot_phone', None)
    
    # Success message
    username = result.get('username', 'User')
    msg = "🎉 <b>Setup Complete!</b>\n\n"
    msg += f"Userbot authenticated as <b>@{username}</b>!\n\n"
    msg += "✅ Configuration saved\n"
    msg += "✅ Session stored securely\n\n"
    msg += "Now connecting to Telegram..."
    
    await update.message.reply_text(msg, parse_mode='HTML')
    
    # Initialize userbot
    await asyncio.sleep(1)
    success = await userbot_manager.initialize()
    
    if success:
        await update.message.reply_text(
            "✅ <b>Userbot Connected!</b>\n\nYour userbot is now ready to deliver products via secret chats!",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "⚠️ <b>Connection Issue</b>\n\nSetup complete but failed to connect. Try reconnecting from the control panel.",
            parse_mode='HTML'
        )

# ==================== CONNECTION MANAGEMENT ====================

async def handle_userbot_connect(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Connect userbot"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer("Connecting...", show_alert=False)
    
    success = await userbot_manager.initialize()
    
    if success:
        await query.answer("✅ Connected successfully!", show_alert=True)
    else:
        await query.answer("❌ Connection failed. Check logs.", show_alert=True)
    
    # Refresh dashboard
    await _show_status_dashboard(query, context)

async def handle_userbot_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Disconnect userbot"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer("Disconnecting...", show_alert=False)
    
    success = await userbot_manager.disconnect()
    
    if success:
        await query.answer("✅ Disconnected successfully!", show_alert=True)
    else:
        await query.answer("❌ Disconnect failed. Check logs.", show_alert=True)
    
    # Refresh dashboard
    await _show_status_dashboard(query, context)

async def handle_userbot_test(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Test userbot delivery"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer("Sending test message...", show_alert=False)
    
    result = await test_userbot_delivery(user_id)
    
    if result['success']:
        await query.answer("✅ Test message sent! Check your messages.", show_alert=True)
    else:
        error_msg = result.get('error', 'Unknown error')
        await query.answer(f"❌ Test failed: {error_msg}", show_alert=True)

# ==================== SETTINGS PANEL ====================

async def handle_userbot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show settings panel"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    config = userbot_config.get_dict()
    
    msg = "⚙️ <b>Userbot Settings</b>\n\n"
    msg += "Configure userbot behavior:\n\n"
    
    # Current settings
    enabled = config.get('enabled', False)
    auto_reconnect = config.get('auto_reconnect', True)
    notifications = config.get('send_notifications', True)
    ttl = config.get('secret_chat_ttl', 86400)
    ttl_hours = ttl // 3600
    max_retries = config.get('max_retries', 3)
    retry_delay = config.get('retry_delay', 5)
    
    msg += f"<b>Delivery:</b> {'✅ Enabled' if enabled else '❌ Disabled'}\n"
    msg += f"<b>Auto-Reconnect:</b> {'✅ Enabled' if auto_reconnect else '❌ Disabled'}\n"
    msg += f"<b>Notifications:</b> {'✅ Enabled' if notifications else '❌ Disabled'}\n"
    msg += f"<b>Message TTL:</b> {ttl_hours} hours\n"
    msg += f"<b>Max Retries:</b> {max_retries}\n"
    msg += f"<b>Retry Delay:</b> {retry_delay} seconds\n"
    
    keyboard = [
        [InlineKeyboardButton(
            f"{'🔴 Disable' if enabled else '🟢 Enable'} Delivery",
            callback_data=f"userbot_toggle_enabled|{not enabled}"
        )],
        [InlineKeyboardButton(
            f"{'🔴 Disable' if auto_reconnect else '🟢 Enable'} Auto-Reconnect",
            callback_data=f"userbot_toggle_reconnect|{not auto_reconnect}"
        )],
        [InlineKeyboardButton(
            f"{'🔴 Disable' if notifications else '🟢 Enable'} Notifications",
            callback_data=f"userbot_toggle_notifications|{not notifications}"
        )],
        [InlineKeyboardButton("⏰ Change TTL", callback_data="userbot_change_ttl"),
         InlineKeyboardButton("🔄 Change Retries", callback_data="userbot_change_retries")],
        [InlineKeyboardButton("⬅️ Back", callback_data="userbot_control")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_userbot_toggle_enabled(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Toggle userbot enabled/disabled"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        return
    
    enabled = params[0] == 'True'
    userbot_config.set_enabled(enabled)
    
    status = "enabled" if enabled else "disabled"
    await query.answer(f"✅ Delivery {status}!", show_alert=True)
    
    # Refresh settings (with a small delay to avoid BadRequest)
    await asyncio.sleep(0.5)
    try:
        await handle_userbot_settings(update, context)
    except Exception as e:
        # If refresh fails, just ignore (likely unchanged message)
        logger.warning(f"Could not refresh settings after toggle: {e}")

async def handle_userbot_toggle_reconnect(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Toggle auto-reconnect"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        return
    
    auto_reconnect = params[0] == 'True'
    userbot_config.set_auto_reconnect(auto_reconnect)
    
    status = "enabled" if auto_reconnect else "disabled"
    await query.answer(f"✅ Auto-reconnect {status}!", show_alert=True)
    
    # Refresh settings (with a small delay to avoid BadRequest)
    await asyncio.sleep(0.5)
    try:
        await handle_userbot_settings(update, context)
    except Exception as e:
        logger.warning(f"Could not refresh settings after toggle: {e}")

async def handle_userbot_toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Toggle notifications"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        return
    
    notifications = params[0] == 'True'
    userbot_config.set_notifications(notifications)
    
    status = "enabled" if notifications else "disabled"
    await query.answer(f"✅ Notifications {status}!", show_alert=True)
    
    # Refresh settings (with a small delay to avoid BadRequest)
    await asyncio.sleep(0.5)
    try:
        await handle_userbot_settings(update, context)
    except Exception as e:
        logger.warning(f"Could not refresh settings after toggle: {e}")

# ==================== STATISTICS PANEL ====================

async def handle_userbot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show delivery statistics"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    stats = get_delivery_stats()
    
    msg = "📊 <b>Delivery Statistics</b>\n\n"
    msg += f"<b>Total Deliveries:</b> {stats['total']}\n"
    msg += f"<b>Successful:</b> {stats['success']} ✅\n"
    msg += f"<b>Failed:</b> {stats['failed']} ❌\n"
    msg += f"<b>Success Rate:</b> {stats['success_rate']}%\n\n"
    
    # Recent deliveries
    recent = stats.get('recent_deliveries', [])
    if recent:
        msg += "<b>Recent Deliveries:</b>\n\n"
        for delivery in recent[:5]:
            status_emoji = "✅" if delivery['delivery_status'] == 'success' else "❌"
            delivered_at = delivery.get('delivered_at')
            time_str = delivered_at.strftime('%Y-%m-%d %H:%M') if delivered_at else 'N/A'
            msg += f"{status_emoji} User {delivery['user_id']} - {time_str}\n"
            if delivery.get('error_message'):
                msg += f"   *Error: {delivery['error_message'][:50]}*\n"
    else:
        msg += "No deliveries yet."
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="userbot_control")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== RESET CONFIRMATION ====================

async def handle_userbot_reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Confirm reset configuration"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    msg = "⚠️ <b>Reset Userbot Configuration</b>\n\n"
    msg += "This will:\n"
    msg += "• Delete all configuration\n"
    msg += "• Remove saved session\n"
    msg += "• Disconnect userbot\n"
    msg += "• Keep delivery statistics\n\n"
    msg += "<b>Are you sure you want to reset?</b>"
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Reset", callback_data="userbot_reset_confirmed"),
         InlineKeyboardButton("❌ Cancel", callback_data="userbot_control")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_userbot_reset_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Reset userbot configuration"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    # Disconnect first
    await userbot_manager.disconnect()
    
    # Reset config
    success = reset_userbot_config()
    
    if success:
        await query.answer("✅ Configuration reset!", show_alert=True)
        msg = "✅ <b>Configuration Reset</b>\n\nUserbot configuration has been reset. You can set it up again anytime."
        keyboard = [
            [InlineKeyboardButton("🚀 Setup Again", callback_data="userbot_setup_start")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await query.answer("❌ Reset failed. Check logs.", show_alert=True)

# Import asyncio for the phone verification handler
import asyncio

