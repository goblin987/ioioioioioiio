"""
Scout System Admin Interface
Admin panel for managing scout keywords and monitoring triggers
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils import is_primary_admin, get_db_connection
from userbot_scout import add_keyword, toggle_keyword, delete_keyword, toggle_scout_mode

logger = logging.getLogger(__name__)

# ==================== MAIN SCOUT MENU ====================

async def handle_scout_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main scout system menu"""
    query = update.callback_query
    
    if not is_primary_admin(query.from_user.id):
        await query.answer("Access denied", show_alert=True)
        return
    
    # Get stats
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as count FROM scout_keywords WHERE is_active = TRUE")
    active_keywords = c.fetchone()['count']
    
    c.execute("SELECT COUNT(*) as count FROM userbots WHERE scout_mode_enabled = TRUE")
    scout_bots = c.fetchone()['count']
    
    c.execute("SELECT COUNT(*) as count FROM scout_triggers WHERE triggered_at > NOW() - INTERVAL '24 hours'")
    triggers_24h = c.fetchone()['count']
    
    c.execute("SELECT COUNT(*) as count FROM scout_triggers WHERE response_sent = TRUE AND triggered_at > NOW() - INTERVAL '24 hours'")
    responses_24h = c.fetchone()['count']
    
    conn.close()
    
    msg = (
        f"🔍 **Scout System Control Panel**\n\n"
        f"📊 **Statistics (Last 24h):**\n"
        f"• Active Keywords: {active_keywords}\n"
        f"• Scout Userbots: {scout_bots}\n"
        f"• Triggers Detected: {triggers_24h}\n"
        f"• Responses Sent: {responses_24h}\n\n"
        f"Scout userbots automatically reply when they detect keywords in groups."
    )
    
    keyboard = [
        [InlineKeyboardButton("🔑 Manage Keywords", callback_data="scout_keywords|0")],
        [InlineKeyboardButton("🤖 Configure Userbots", callback_data="scout_userbots")],
        [InlineKeyboardButton("📊 View Triggers Log", callback_data="scout_triggers|0")],
        [InlineKeyboardButton("⬅️ Back", callback_data="userbot_control")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ==================== KEYWORDS MANAGEMENT ====================

async def handle_scout_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """List all keywords with pagination"""
    query = update.callback_query
    
    if not is_primary_admin(query.from_user.id):
        await query.answer("Access denied", show_alert=True)
        return
    
    page = int(params[0]) if params else 0
    per_page = 10
    offset = page * per_page
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get total count
    c.execute("SELECT COUNT(*) as count FROM scout_keywords")
    total = c.fetchone()['count']
    
    # Get keywords for this page
    c.execute("""
        SELECT id, keyword, match_type, response_text, is_active, uses_count
        FROM scout_keywords
        ORDER BY is_active DESC, uses_count DESC, id DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    keywords = c.fetchall()
    conn.close()
    
    total_pages = (total + per_page - 1) // per_page
    
    msg = f"🔑 **Scout Keywords** (Page {page + 1}/{max(total_pages, 1)})\n\n"
    
    if not keywords:
        msg += "No keywords configured yet.\n\nAdd your first keyword to start scout mode!"
    else:
        for kw in keywords:
            status = "✅" if kw['is_active'] else "❌"
            response_preview = kw['response_text'][:40] + "..." if len(kw['response_text']) > 40 else kw['response_text']
            msg += f"{status} **{kw['keyword']}** ({kw['match_type']})\n"
            msg += f"   Uses: {kw['uses_count']} | Response: {response_preview}\n"
            msg += f"   [Edit](scout_edit_keyword|{kw['id']}) | [Toggle](scout_toggle_keyword|{kw['id']}) | [Delete](scout_delete_keyword|{kw['id']})\n\n"
    
    keyboard = []
    keyboard.append([InlineKeyboardButton("➕ Add Keyword", callback_data="scout_add_keyword_start")])
    
    # Pagination
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"scout_keywords|{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"scout_keywords|{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"scout_keywords|{page}"),
        InlineKeyboardButton("⬅️ Back", callback_data="scout_menu")
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def handle_scout_add_keyword_start(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Start adding a new keyword"""
    query = update.callback_query
    
    if not is_primary_admin(query.from_user.id):
        await query.answer("Access denied", show_alert=True)
        return
    
    msg = (
        "➕ **Add Scout Keyword**\n\n"
        "**Step 1:** Enter the keyword to detect\n\n"
        "Examples:\n"
        "• `discount code` - detect when someone asks for discounts\n"
        "• `steam games` - detect steam game mentions\n"
        "• `looking for shop` - detect people looking for shops\n\n"
        "Type your keyword:"
    )
    
    context.user_data['state'] = 'awaiting_scout_keyword'
    context.user_data['scout_keyword_data'] = {}
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="scout_keywords|0")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def handle_scout_keyword_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin messages for keyword creation"""
    user_id = update.effective_user.id
    
    if not is_primary_admin(user_id):
        return
    
    state = context.user_data.get('state')
    text = update.message.text.strip()
    
    if state == 'awaiting_scout_keyword':
        # Save keyword and ask for response
        context.user_data['scout_keyword_data']['keyword'] = text
        context.user_data['state'] = 'awaiting_scout_response'
        
        msg = (
            f"✅ Keyword: **{text}**\n\n"
            f"**Step 2:** Enter the auto-reply message\n\n"
            f"This message will be sent when the keyword is detected.\n\n"
            f"Example:\n"
            f"`🎮 Check out our shop! Get 10% off with code WELCOME10\n@YourBotName`\n\n"
            f"Type your response:"
        )
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="scout_keywords|0")]]
        
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif state == 'awaiting_scout_response':
        # Save response and show confirmation
        context.user_data['scout_keyword_data']['response_text'] = text
        context.user_data['state'] = None
        
        keyword_data = context.user_data['scout_keyword_data']
        
        # Add to database
        keyword_id = add_keyword(
            keyword=keyword_data['keyword'],
            response_text=keyword_data['response_text'],
            match_type='contains',  # Default
            case_sensitive=False,  # Default
            response_delay=3,  # Default
            created_by=user_id
        )
        
        if keyword_id:
            msg = (
                f"✅ **Keyword Added Successfully!**\n\n"
                f"**Keyword:** {keyword_data['keyword']}\n"
                f"**Response:** {keyword_data['response_text'][:100]}...\n"
                f"**Match Type:** Contains (case-insensitive)\n"
                f"**Delay:** 3 seconds\n\n"
                f"Scout userbots will now reply when this keyword is detected in groups!"
            )
        else:
            msg = "❌ Error adding keyword. Please try again."
        
        keyboard = [
            [InlineKeyboardButton("🔑 Back to Keywords", callback_data="scout_keywords|0")],
            [InlineKeyboardButton("🔍 Scout Menu", callback_data="scout_menu")]
        ]
        
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        # Clear context
        context.user_data.pop('scout_keyword_data', None)


async def handle_scout_toggle_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Toggle keyword active status"""
    query = update.callback_query
    
    if not is_primary_admin(query.from_user.id):
        await query.answer("Access denied", show_alert=True)
        return
    
    keyword_id = int(params[0]) if params else None
    
    if not keyword_id:
        await query.answer("Error: Invalid keyword ID", show_alert=True)
        return
    
    # Get current status
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT is_active FROM scout_keywords WHERE id = %s", (keyword_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await query.answer("Error: Keyword not found", show_alert=True)
        return
    
    new_status = not result['is_active']
    toggle_keyword(keyword_id, new_status)
    
    await query.answer(f"✅ Keyword {'enabled' if new_status else 'disabled'}", show_alert=True)
    
    # Refresh the list
    await handle_scout_keywords(update, context, ['0'])


async def handle_scout_delete_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Delete a keyword"""
    query = update.callback_query
    
    if not is_primary_admin(query.from_user.id):
        await query.answer("Access denied", show_alert=True)
        return
    
    keyword_id = int(params[0]) if params else None
    
    if not keyword_id:
        await query.answer("Error: Invalid keyword ID", show_alert=True)
        return
    
    delete_keyword(keyword_id)
    
    await query.answer("✅ Keyword deleted", show_alert=True)
    
    # Refresh the list
    await handle_scout_keywords(update, context, ['0'])


# ==================== USERBOT CONFIGURATION ====================

async def handle_scout_userbots(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Configure scout mode for userbots"""
    query = update.callback_query
    
    if not is_primary_admin(query.from_user.id):
        await query.answer("Access denied", show_alert=True)
        return
    
    # Get all userbots
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, name, is_connected, scout_mode_enabled
        FROM userbots
        ORDER BY id
    """)
    userbots = c.fetchall()
    conn.close()
    
    msg = "🤖 **Configure Scout Userbots**\n\n"
    
    if not userbots:
        msg += "No userbots available. Add userbots first in Userbot Control Panel."
    else:
        msg += "Enable scout mode for userbots that should monitor groups:\n\n"
        for ub in userbots:
            status = "✅" if ub['scout_mode_enabled'] else "❌"
            connected = "🟢" if ub['is_connected'] else "🔴"
            msg += f"{status} {connected} **{ub['name']}**\n"
    
    keyboard = []
    for ub in userbots:
        action = "disable" if ub['scout_mode_enabled'] else "enable"
        label = f"{'✅' if ub['scout_mode_enabled'] else '❌'} {ub['name']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"scout_toggle_bot|{ub['id']}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="scout_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def handle_scout_toggle_bot(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Toggle scout mode for a userbot"""
    query = update.callback_query
    
    if not is_primary_admin(query.from_user.id):
        await query.answer("Access denied", show_alert=True)
        return
    
    userbot_id = int(params[0]) if params else None
    
    if not userbot_id:
        await query.answer("Error: Invalid userbot ID", show_alert=True)
        return
    
    # Get current status
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT scout_mode_enabled FROM userbots WHERE id = %s", (userbot_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await query.answer("Error: Userbot not found", show_alert=True)
        return
    
    new_status = not result['scout_mode_enabled']
    toggle_scout_mode(userbot_id, new_status)
    
    await query.answer(f"✅ Scout mode {'enabled' if new_status else 'disabled'}", show_alert=True)
    
    # Refresh the list
    await handle_scout_userbots(update, context)


# ==================== TRIGGERS LOG ====================

async def handle_scout_triggers(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """View scout triggers log"""
    query = update.callback_query
    
    if not is_primary_admin(query.from_user.id):
        await query.answer("Access denied", show_alert=True)
        return
    
    page = int(params[0]) if params else 0
    per_page = 15
    offset = page * per_page
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get total count
    c.execute("SELECT COUNT(*) as count FROM scout_triggers")
    total = c.fetchone()['count']
    
    # Get triggers for this page
    c.execute("""
        SELECT st.*, sk.keyword, ub.name as userbot_name
        FROM scout_triggers st
        LEFT JOIN scout_keywords sk ON st.keyword_id = sk.id
        LEFT JOIN userbots ub ON st.userbot_id = ub.id
        ORDER BY st.triggered_at DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    triggers = c.fetchall()
    conn.close()
    
    total_pages = (total + per_page - 1) // per_page
    
    msg = f"📊 **Scout Triggers Log** (Page {page + 1}/{max(total_pages, 1)})\n\n"
    
    if not triggers:
        msg += "No triggers logged yet."
    else:
        for t in triggers:
            status = "✅" if t['response_sent'] else "❌"
            chat_name = t['chat_title'] or f"Chat {t['chat_id']}"
            user_display = f"@{t['user_username']}" if t['user_username'] else f"User {t['user_id']}"
            
            msg += f"{status} **{t['keyword']}** by {t['userbot_name']}\n"
            msg += f"   {chat_name} | {user_display}\n"
            msg += f"   {t['triggered_at'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    keyboard = []
    
    # Pagination
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"scout_triggers|{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"scout_triggers|{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"scout_triggers|{page}"),
        InlineKeyboardButton("⬅️ Back", callback_data="scout_menu")
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

