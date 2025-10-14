"""
Marquee Text Admin Handlers
Allows admins to configure running text animation
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from admin import is_primary_admin
from marquee_text_system import (
    get_marquee_settings,
    update_marquee_text,
    update_marquee_enabled,
    update_marquee_speed,
    get_current_marquee_frame
)

logger = logging.getLogger(__name__)

async def handle_admin_marquee_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main marquee settings menu"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    settings = get_marquee_settings()
    
    if not settings:
        msg = "❌ Marquee system not initialized"
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_bot_ui_menu")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Show preview
    preview = get_current_marquee_frame(0)
    
    msg = "📢 MARQUEE TEXT SETTINGS\n\n"
    msg += f"Current Text: {settings['text']}\n\n"
    msg += f"Status: {'✅ ENABLED' if settings['enabled'] else '❌ DISABLED'}\n"
    msg += f"Speed: {settings['speed'].upper()}\n\n"
    msg += f"Preview:\n"
    msg += f"┌{'─' * 22}┐\n"
    msg += f"│ {preview} │\n"
    msg += f"└{'─' * 22}┘\n\n"
    msg += "Configure your running text animation below"
    
    keyboard = [
        [InlineKeyboardButton("✏️ Change Text", callback_data="admin_marquee_change_text")],
        [
            InlineKeyboardButton(
                "✅ Disable" if settings['enabled'] else "▶️ Enable",
                callback_data="admin_marquee_toggle"
            )
        ],
        [InlineKeyboardButton("⚡ Change Speed", callback_data="admin_marquee_speed")],
        [InlineKeyboardButton("👁️ Preview Animation", callback_data="admin_marquee_preview")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_bot_ui_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_marquee_change_text(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Prompt admin to enter new marquee text"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    msg = "✏️ CHANGE MARQUEE TEXT\n\n"
    msg += "Send me the new text you want to display.\n\n"
    msg += "Tips:\n"
    msg += "• Use emojis for visual appeal 🎉\n"
    msg += "• Keep it short and catchy\n"
    msg += "• Text will scroll automatically\n\n"
    msg += "Example: 🔥 HOT DEALS TODAY! 🔥"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_marquee_settings")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Set state for text input
    context.user_data['awaiting_marquee_text'] = True

async def handle_marquee_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process new marquee text input"""
    user_id = update.message.from_user.id
    
    if not is_primary_admin(user_id):
        return
    
    if not context.user_data.get('awaiting_marquee_text'):
        return
    
    new_text = update.message.text.strip()
    
    if not new_text:
        await update.message.reply_text("❌ Text cannot be empty!")
        return
    
    if len(new_text) > 200:
        await update.message.reply_text("❌ Text too long! Max 200 characters.")
        return
    
    # Update text
    success = update_marquee_text(new_text)
    
    if success:
        preview = get_current_marquee_frame(0)
        
        msg = f"✅ MARQUEE TEXT UPDATED!\n\n"
        msg += f"New text: {new_text}\n\n"
        msg += f"Preview:\n"
        msg += f"┌{'─' * 22}┐\n"
        msg += f"│ {preview} │\n"
        msg += f"└{'─' * 22}┘"
        
        keyboard = [[InlineKeyboardButton("⬅️ Back to Settings", callback_data="admin_marquee_settings")]]
        
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ Failed to update text. Please try again.")
    
    # Clear state
    context.user_data['awaiting_marquee_text'] = False

async def handle_admin_marquee_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Toggle marquee animation on/off"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    settings = get_marquee_settings()
    
    if not settings:
        await query.answer("❌ Marquee not initialized", show_alert=True)
        return
    
    # Toggle
    new_state = not settings['enabled']
    success = update_marquee_enabled(new_state)
    
    if success:
        await query.answer(
            f"✅ Marquee {'enabled' if new_state else 'disabled'}!",
            show_alert=True
        )
    else:
        await query.answer("❌ Failed to update", show_alert=True)
    
    # Refresh menu
    await handle_admin_marquee_settings(update, context)

async def handle_admin_marquee_speed(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show speed selection menu"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    settings = get_marquee_settings()
    current_speed = settings['speed'] if settings else 'medium'
    
    msg = "⚡ MARQUEE SPEED\n\n"
    msg += "Select animation speed:\n\n"
    msg += f"{'✅' if current_speed == 'slow' else '⚪'} SLOW - 1.0s per character\n"
    msg += f"{'✅' if current_speed == 'medium' else '⚪'} MEDIUM - 0.5s per character\n"
    msg += f"{'✅' if current_speed == 'fast' else '⚪'} FAST - 0.2s per character\n\n"
    msg += "Faster = more eye-catching\n"
    msg += "Slower = easier to read"
    
    keyboard = [
        [InlineKeyboardButton("🐌 Slow", callback_data="admin_marquee_set_speed|slow")],
        [InlineKeyboardButton("🚶 Medium", callback_data="admin_marquee_set_speed|medium")],
        [InlineKeyboardButton("🚀 Fast", callback_data="admin_marquee_set_speed|fast")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_marquee_settings")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_marquee_set_speed(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Set marquee speed"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params or len(params) < 1:
        await query.answer("Invalid speed", show_alert=True)
        return
    
    speed = params[0]
    
    success = update_marquee_speed(speed)
    
    if success:
        await query.answer(f"✅ Speed set to {speed.upper()}!", show_alert=True)
    else:
        await query.answer("❌ Failed to update speed", show_alert=True)
    
    # Refresh menu
    await handle_admin_marquee_speed(update, context)

async def handle_admin_marquee_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show animated preview of marquee"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    settings = get_marquee_settings()
    
    if not settings:
        await query.answer("❌ Marquee not initialized", show_alert=True)
        return
    
    msg = "👁️ MARQUEE PREVIEW\n\n"
    msg += "Watch the animation below:\n\n"
    
    # Show 5 frames
    for i in range(5):
        frame = get_current_marquee_frame(i * 3)
        msg += f"┌{'─' * 22}┐\n"
        msg += f"│ {frame} │\n"
        msg += f"└{'─' * 22}┘\n\n"
    
    msg += "This is how it will look when animated!"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_marquee_settings")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

