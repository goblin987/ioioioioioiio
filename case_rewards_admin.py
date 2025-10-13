"""
Case Rewards Admin Interface - CS:GO Style
Manage product pools for cases (product types, not individual products)
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import get_db_connection, is_primary_admin
from daily_rewards_system import CASE_TYPES
from case_rewards_system import (
    get_all_product_types,
    get_case_reward_pool,
    add_product_to_case_pool,
    remove_product_from_case_pool,
    set_case_lose_emoji
)

logger = logging.getLogger(__name__)

# ============================================================================
# PRODUCT POOL MANAGER (NEW SYSTEM)
# ============================================================================

async def handle_admin_product_pool_v2(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """New product pool manager - Step 1: Select case type"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    msg = "🎁 PRODUCT POOL MANAGER\n\n"
    msg += "Step 1: Select a case to configure\n\n"
    msg += "Each case can have multiple product types with different win chances.\n"
    msg += "Users win PRODUCTS (not points) or NOTHING.\n\n"
    msg += "Select a case:"
    
    keyboard = []
    
    for case_type, config in CASE_TYPES.items():
        keyboard.append([InlineKeyboardButton(
            f"{config['emoji']} {config['name']}",
            callback_data=f"admin_case_pool|{case_type}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_daily_rewards_main")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_case_pool(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Step 2: Manage specific case pool"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid case", show_alert=True)
        return
    
    case_type = params[0]
    config = CASE_TYPES.get(case_type)
    
    if not config:
        await query.answer("Case not found", show_alert=True)
        return
    
    await query.answer()
    
    # Get current reward pool
    rewards = get_case_reward_pool(case_type)
    
    msg = f"{config['emoji']} {config['name'].upper()} - REWARD POOL\n\n"
    msg += f"Cost: {config['cost']} points\n\n"
    
    if rewards:
        msg += "Current Rewards:\n"
        total_chance = 0
        for reward in rewards:
            emoji = reward['reward_emoji'] or '🎁'
            msg += f"{emoji} {reward['product_type_name']} {reward['product_size']}\n"
            msg += f"   Win Chance: {reward['win_chance_percent']}%\n\n"
            total_chance += reward['win_chance_percent']
        
        lose_chance = 100 - total_chance
        msg += f"💸 Lose (Nothing): {lose_chance:.1f}%\n\n"
    else:
        msg += "❌ No rewards configured yet!\n\n"
    
    msg += "What would you like to do?"
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Product Type", callback_data=f"admin_add_product_to_case|{case_type}")],
        [InlineKeyboardButton("🗑️ Remove Product", callback_data=f"admin_remove_from_case|{case_type}")],
        [InlineKeyboardButton("💸 Set Lose Emoji", callback_data=f"admin_set_lose_emoji|{case_type}")],
        [InlineKeyboardButton("⬅️ Back to Cases", callback_data="admin_product_pool_v2")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_add_product_to_case(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Step 3: Select product type to add"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid case", show_alert=True)
        return
    
    case_type = params[0]
    await query.answer()
    
    # Get all available product types
    product_types = get_all_product_types()
    
    msg = "➕ ADD PRODUCT TO CASE\n\n"
    msg += "Select a product type:\n\n"
    
    if product_types:
        msg += "Available Product Types:\n"
        for pt in product_types[:10]:  # Show first 10
            msg += f"• {pt['name']} {pt['size']} - {pt['min_price']}€ (Stock: {pt['total_available']})\n"
    else:
        msg += "❌ No products available\n"
    
    keyboard = []
    
    # Create buttons for product types (2 per row)
    for i in range(0, min(len(product_types), 10), 2):
        row = []
        for j in range(2):
            if i + j < len(product_types):
                pt = product_types[i + j]
                row.append(InlineKeyboardButton(
                    f"{pt['name']} {pt['size']}",
                    callback_data=f"admin_select_product|{case_type}|{pt['name']}|{pt['size']}"
                ))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_case_pool|{case_type}")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_select_product(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Step 4: Set win chance for selected product"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params or len(params) < 3:
        await query.answer("Invalid data", show_alert=True)
        return
    
    case_type = params[0]
    product_type = params[1]
    size = params[2]
    
    await query.answer()
    
    msg = f"➕ ADD: {product_type} {size}\n\n"
    msg += "Select win chance percentage:\n\n"
    msg += "💡 Tips:\n"
    msg += "• Lower % = More rare = More exciting\n"
    msg += "• Total of all products should be < 100%\n"
    msg += "• Remaining % = Lose chance\n\n"
    msg += "Example: If total products = 30%, lose chance = 70%"
    
    # Win chance presets
    chances = [0.5, 1, 2, 5, 10, 15, 20, 25]
    
    keyboard = []
    row = []
    for i, chance in enumerate(chances):
        row.append(InlineKeyboardButton(
            f"{chance}%",
            callback_data=f"admin_set_product_chance|{case_type}|{product_type}|{size}|{chance}"
        ))
        if (i + 1) % 4 == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_add_product_to_case|{case_type}")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_set_product_chance(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Step 5: Set emoji for product"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params or len(params) < 4:
        await query.answer("Invalid data", show_alert=True)
        return
    
    case_type = params[0]
    product_type = params[1]
    size = params[2]
    chance = float(params[3])
    
    # Store in context for next step
    context.user_data['pending_product'] = {
        'case_type': case_type,
        'product_type': product_type,
        'size': size,
        'chance': chance
    }
    
    await query.answer()
    
    msg = f"🎨 SET EMOJI\n\n"
    msg += f"Product: {product_type} {size}\n"
    msg += f"Win Chance: {chance}%\n\n"
    msg += "Select an emoji for this reward:"
    
    # Emoji picker
    emojis = {
        "Food": ["☕", "🍕", "🍔", "🌮", "🍜", "🍱"],
        "Rewards": ["🎁", "💎", "🏆", "⭐", "💰", "🔥"],
        "Gaming": ["🎮", "🕹️", "👾", "🎯", "🎲", "🃏"],
        "Fun": ["✨", "🎉", "🎊", "🎈", "🎆", "🎇"]
    }
    
    keyboard = []
    
    for category, emoji_list in emojis.items():
        row = []
        for emoji in emoji_list:
            row.append(InlineKeyboardButton(
                emoji,
                callback_data=f"admin_save_product_reward|{emoji}"
            ))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_select_product|{case_type}|{product_type}|{size}")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_save_product_reward(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Step 6: Save product to case pool"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid emoji", show_alert=True)
        return
    
    emoji = params[0]
    
    # Get pending product from context
    pending = context.user_data.get('pending_product')
    if not pending:
        await query.answer("Session expired, please try again", show_alert=True)
        return
    
    # Save to database
    success = add_product_to_case_pool(
        pending['case_type'],
        pending['product_type'],
        pending['size'],
        pending['chance'],
        emoji
    )
    
    if success:
        await query.answer(f"✅ Added {emoji} {pending['product_type']} {pending['size']} ({pending['chance']}%)", show_alert=True)
        # Clear context
        context.user_data.pop('pending_product', None)
        # Return to case pool view
        await handle_admin_case_pool(update, context, [pending['case_type']])
    else:
        await query.answer("❌ Error saving product", show_alert=True)

async def handle_admin_remove_from_case(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Remove product from case pool"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid case", show_alert=True)
        return
    
    case_type = params[0]
    await query.answer()
    
    # Get current rewards
    rewards = get_case_reward_pool(case_type)
    
    msg = "🗑️ REMOVE PRODUCT\n\n"
    msg += "Select a product to remove:"
    
    keyboard = []
    
    for reward in rewards:
        emoji = reward['reward_emoji'] or '🎁'
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {reward['product_type_name']} {reward['product_size']} ({reward['win_chance_percent']}%)",
            callback_data=f"admin_confirm_remove|{case_type}|{reward['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_case_pool|{case_type}")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_confirm_remove(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Confirm removal"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params or len(params) < 2:
        await query.answer("Invalid data", show_alert=True)
        return
    
    case_type = params[0]
    pool_id = int(params[1])
    
    success = remove_product_from_case_pool(pool_id)
    
    if success:
        await query.answer("✅ Product removed", show_alert=True)
        await handle_admin_case_pool(update, context, [case_type])
    else:
        await query.answer("❌ Error removing product", show_alert=True)

async def handle_admin_set_lose_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Set lose emoji for case"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid case", show_alert=True)
        return
    
    case_type = params[0]
    await query.answer()
    
    msg = "💸 SET LOSE EMOJI\n\n"
    msg += "Select an emoji that shows when user wins NOTHING:"
    
    lose_emojis = ["💸", "😢", "💔", "😭", "💨", "👎", "❌", "🚫"]
    
    keyboard = []
    row = []
    for i, emoji in enumerate(lose_emojis):
        row.append(InlineKeyboardButton(
            emoji,
            callback_data=f"admin_save_lose_emoji|{case_type}|{emoji}"
        ))
        if (i + 1) % 4 == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_case_pool|{case_type}")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_save_lose_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Save lose emoji"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params or len(params) < 2:
        await query.answer("Invalid data", show_alert=True)
        return
    
    case_type = params[0]
    emoji = params[1]
    
    success = set_case_lose_emoji(case_type, emoji, "Better luck next time!")
    
    if success:
        await query.answer(f"✅ Lose emoji set to {emoji}", show_alert=True)
        await handle_admin_case_pool(update, context, [case_type])
    else:
        await query.answer("❌ Error saving emoji", show_alert=True)

