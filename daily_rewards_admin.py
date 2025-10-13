"""
Daily Rewards Admin Interface - Clean & Robust
Dummy-proof admin panel for managing cases and rewards
"""

import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import get_db_connection, is_primary_admin
from daily_rewards_system import CASE_TYPES, DAILY_REWARDS

logger = logging.getLogger(__name__)

# ============================================================================
# MAIN ADMIN MENU
# ============================================================================

async def handle_admin_daily_rewards_main(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Clean, simple admin main menu"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    # Get quick stats
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('SELECT COUNT(*) as count FROM user_points')
        total_users = c.fetchone()['count']
        
        c.execute('SELECT SUM(points) as total FROM user_points')
        result = c.fetchone()
        total_points = result['total'] if result and result['total'] else 0
        
        c.execute('SELECT COUNT(*) as count FROM case_openings')
        total_cases = c.fetchone()['count']
        
        msg = "🎁 **DAILY REWARDS ADMIN**\n\n"
        msg += f"👥 Active Users: **{total_users}**\n"
        msg += f"💰 Points in Circulation: **{total_points}**\n"
        msg += f"📦 Cases Opened: **{total_cases}**\n\n"
        msg += "**What would you like to manage?**"
        
    except Exception as e:
        logger.error(f"Error loading admin stats: {e}")
        msg = "🎁 **DAILY REWARDS ADMIN**\n\n❌ Error loading stats"
    finally:
        conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🎁 Manage Product Pool", callback_data="admin_product_pool")],
        [InlineKeyboardButton("📦 Manage Cases", callback_data="admin_manage_cases")],
        [InlineKeyboardButton("📊 View Statistics", callback_data="admin_case_stats")],
        [InlineKeyboardButton("🎯 Give Me Test Points", callback_data="admin_give_test_points")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================================================
# PRODUCT POOL MANAGER (Robust UI like Edit Bot Look)
# ============================================================================

async def handle_admin_product_pool(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Product pool manager - Step 1: Select product"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get all products with stock
        c.execute('''
            SELECT id, name, product_emoji, stock, price
            FROM products
            WHERE stock > 0
            ORDER BY price DESC
            LIMIT 20
        ''')
        products = c.fetchall()
        
        msg = "🎁 **PRODUCT POOL MANAGER**\n\n"
        msg += "**Step 1:** Select a product to configure\n\n"
        
        if products:
            msg += "**Available Products:**\n"
            for product in products:
                emoji = product['product_emoji'] or '🎁'
                msg += f"{emoji} {product['name']} - {product['price']}€ (Stock: {product['stock']})\n"
            msg += "\n💡 Click a product below to set its win chance and emoji"
        else:
            msg += "❌ No products available\n\n"
            msg += "Add products with stock first!"
        
        keyboard = []
        
        # Create buttons for each product (2 per row)
        for i in range(0, len(products), 2):
            row = []
            for j in range(2):
                if i + j < len(products):
                    product = products[i + j]
                    emoji = product['product_emoji'] or '🎁'
                    row.append(InlineKeyboardButton(
                        f"{emoji} {product['name'][:15]}",
                        callback_data=f"admin_edit_product_pool|{product['id']}"
                    ))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("📦 Add More Products", callback_data="adm_products")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_daily_rewards_main")])
        
    except Exception as e:
        logger.error(f"Error loading product pool: {e}")
        msg = f"❌ Error: {e}"
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_daily_rewards_main")]]
    finally:
        conn.close()
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_edit_product_pool(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Edit specific product in pool - Step 2: Configure"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid product", show_alert=True)
        return
    
    product_id = int(params[0])
    await query.answer()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get product details
        c.execute('''
            SELECT id, name, product_emoji, stock, price
            FROM products
            WHERE id = %s
        ''', (product_id,))
        product = c.fetchone()
        
        if not product:
            await query.answer("Product not found", show_alert=True)
            return
        
        emoji = product['product_emoji'] or '🎁'
        
        msg = f"{emoji} **CONFIGURE PRODUCT**\n\n"
        msg += f"**Product:** {product['name']}\n"
        msg += f"**Value:** {product['price']}€\n"
        msg += f"**Stock:** {product['stock']}\n"
        msg += f"**Current Emoji:** {emoji}\n\n"
        msg += "**What would you like to do?**"
        
        keyboard = [
            [InlineKeyboardButton("🎨 Change Emoji", callback_data=f"admin_set_emoji|{product_id}")],
            [InlineKeyboardButton("📊 Set Win Chance %", callback_data=f"admin_set_chance|{product_id}")],
            [InlineKeyboardButton("📦 Edit Product Details", callback_data=f"edit_product|{product_id}")],
            [InlineKeyboardButton("⬅️ Back to Pool", callback_data="admin_product_pool")]
        ]
        
    except Exception as e:
        logger.error(f"Error loading product: {e}")
        msg = f"❌ Error: {e}"
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_product_pool")]]
    finally:
        conn.close()
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_set_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Emoji picker for product"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid product", show_alert=True)
        return
    
    product_id = int(params[0])
    await query.answer()
    
    msg = "🎨 **EMOJI PICKER**\n\n"
    msg += "**Popular Emojis for Rewards:**\n\n"
    msg += "Click an emoji to set it for this product\n"
    
    # Emoji categories
    emojis = {
        "Gaming": ["🎮", "🕹️", "👾", "🎯", "🎲", "🃏"],
        "Tech": ["💻", "📱", "⌚", "🎧", "🎤", "📷"],
        "Rewards": ["🎁", "💎", "🏆", "⭐", "💰", "🔥"],
        "Fun": ["✨", "🎉", "🎊", "🎈", "🎆", "🎇"]
    }
    
    keyboard = []
    
    for category, emoji_list in emojis.items():
        msg += f"\n**{category}:**\n"
        row = []
        for emoji in emoji_list:
            msg += f"{emoji} "
            row.append(InlineKeyboardButton(
                emoji,
                callback_data=f"admin_save_emoji|{product_id}|{emoji}"
            ))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_edit_product_pool|{product_id}")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_save_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Save selected emoji"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params or len(params) < 2:
        await query.answer("Invalid data", show_alert=True)
        return
    
    product_id = int(params[0])
    emoji = params[1]
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''
            UPDATE products
            SET product_emoji = %s
            WHERE id = %s
        ''', (emoji, product_id))
        conn.commit()
        
        await query.answer(f"✅ Emoji set to {emoji}!", show_alert=True)
    except Exception as e:
        logger.error(f"Error saving emoji: {e}")
        await query.answer(f"❌ Error: {e}", show_alert=True)
        if conn and conn.status == 1:
            conn.rollback()
    finally:
        conn.close()
    
    # Return to product config
    await handle_admin_edit_product_pool(update, context, [str(product_id)])

async def handle_admin_set_chance(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Set win chance percentage"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid product", show_alert=True)
        return
    
    product_id = int(params[0])
    await query.answer()
    
    msg = "📊 **SET WIN CHANCE**\n\n"
    msg += "**How rare should this product be?**\n\n"
    msg += "Select a win chance percentage:\n"
    msg += "• Lower % = More rare = More exciting!\n"
    msg += "• Higher % = More common = More wins!\n\n"
    msg += "💡 Recommended ranges:\n"
    msg += "• Cheap items: 10-20%\n"
    msg += "• Mid-tier: 5-10%\n"
    msg += "• Expensive: 1-5%\n"
    msg += "• Ultra rare: 0.1-1%"
    
    # Preset percentages
    percentages = [0.1, 0.5, 1, 2, 5, 10, 15, 20]
    
    keyboard = []
    row = []
    for i, pct in enumerate(percentages):
        row.append(InlineKeyboardButton(
            f"{pct}%",
            callback_data=f"admin_save_chance|{product_id}|{pct}"
        ))
        if (i + 1) % 4 == 0:  # 4 buttons per row
            keyboard.append(row)
            row = []
    
    if row:  # Add remaining buttons
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_edit_product_pool|{product_id}")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_save_chance(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Save win chance (placeholder - needs database schema)"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params or len(params) < 2:
        await query.answer("Invalid data", show_alert=True)
        return
    
    product_id = int(params[0])
    chance = float(params[1])
    
    # TODO: Save to product_pool_config table
    # For now, just show success
    await query.answer(f"✅ Win chance set to {chance}%! (Feature coming soon)", show_alert=True)
    
    # Return to product config
    await handle_admin_edit_product_pool(update, context, [str(product_id)])

# ============================================================================
# CASE MANAGER
# ============================================================================

async def handle_admin_manage_cases(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Manage cases - list all cases"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    msg = "📦 **CASE MANAGER**\n\n"
    msg += "**Current Cases:**\n\n"
    
    for case_type, config in CASE_TYPES.items():
        msg += f"{config['emoji']} **{config['name']}**\n"
        msg += f"   💰 Cost: {config['cost']} points\n"
        msg += f"   📝 {config['description']}\n\n"
    
    msg += "💡 Click a case to edit or create a new one"
    
    keyboard = []
    
    # Existing cases
    for case_type, config in CASE_TYPES.items():
        keyboard.append([InlineKeyboardButton(
            f"{config['emoji']} Edit {config['name']}",
            callback_data=f"admin_edit_case|{case_type}"
        )])
    
    keyboard.append([InlineKeyboardButton("➕ Create New Case", callback_data="admin_create_case")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_daily_rewards_main")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_edit_case(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Edit specific case"""
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
    
    msg = f"{config['emoji']} **EDIT CASE**\n\n"
    msg += f"**Name:** {config['name']}\n"
    msg += f"**Cost:** {config['cost']} points\n"
    msg += f"**Description:** {config['description']}\n"
    msg += f"**Animation:** {config['animation_speed']}\n\n"
    msg += "**Reward Chances:**\n"
    for outcome, chance in config['rewards'].items():
        msg += f"   • {outcome}: {chance}%\n"
    
    msg += "\n**What would you like to edit?**"
    
    keyboard = [
        [InlineKeyboardButton("💰 Change Cost", callback_data=f"admin_case_cost|{case_type}")],
        [InlineKeyboardButton("📝 Change Description", callback_data=f"admin_case_desc|{case_type}")],
        [InlineKeyboardButton("🎰 Edit Rewards", callback_data=f"admin_case_rewards|{case_type}")],
        [InlineKeyboardButton("⬅️ Back to Cases", callback_data="admin_manage_cases")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_case_cost(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Change case cost"""
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
    
    msg = "💰 **SET CASE COST**\n\n"
    msg += "Select a new cost for this case:\n\n"
    msg += "💡 Recommended pricing:\n"
    msg += "• Basic: 10-30 points\n"
    msg += "• Premium: 40-70 points\n"
    msg += "• Legendary: 80-150 points"
    
    costs = [10, 20, 30, 50, 75, 100, 150, 200]
    
    keyboard = []
    row = []
    for i, cost in enumerate(costs):
        row.append(InlineKeyboardButton(
            f"{cost} pts",
            callback_data=f"admin_save_case_cost|{case_type}|{cost}"
        ))
        if (i + 1) % 4 == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"admin_edit_case|{case_type}")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_save_case_cost(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Save case cost (placeholder)"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    if not params or len(params) < 2:
        await query.answer("Invalid data", show_alert=True)
        return
    
    case_type = params[0]
    cost = int(params[1])
    
    # TODO: Save to database
    await query.answer(f"✅ Cost set to {cost} points! (Feature coming soon)", show_alert=True)
    
    # Return to case editor
    await handle_admin_edit_case(update, context, [case_type])

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def handle_admin_give_test_points(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Give admin 200 test points"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''
            INSERT INTO user_points (user_id, points)
            VALUES (%s, 200)
            ON CONFLICT (user_id) DO UPDATE
            SET points = user_points.points + 200
        ''', (user_id,))
        conn.commit()
        
        c.execute('SELECT points FROM user_points WHERE user_id = %s', (user_id,))
        result = c.fetchone()
        new_total = result['points'] if result else 200
        
        await query.answer(f"✅ Added 200 points! Total: {new_total}", show_alert=True)
    except Exception as e:
        logger.error(f"Error giving test points: {e}")
        await query.answer(f"❌ Error: {e}", show_alert=True)
        if conn and conn.status == 1:
            conn.rollback()
    finally:
        conn.close()
    
    await handle_admin_daily_rewards_main(update, context)

async def handle_admin_case_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """View statistics"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        msg = "📊 **STATISTICS**\n\n"
        
        # Case opening breakdown
        c.execute('''
            SELECT case_type, COUNT(*) as opens, SUM(points_spent) as spent
            FROM case_openings
            GROUP BY case_type
        ''')
        case_stats = c.fetchall()
        
        if case_stats:
            msg += "**Cases Opened:**\n"
            for stat in case_stats:
                msg += f"   {stat['case_type']}: {stat['opens']} opens ({stat['spent']} pts)\n"
        else:
            msg += "No cases opened yet\n"
        
        msg += "\n**Outcome Distribution:**\n"
        c.execute('''
            SELECT outcome_type, COUNT(*) as count
            FROM case_openings
            GROUP BY outcome_type
            ORDER BY count DESC
        ''')
        outcomes = c.fetchall()
        
        if outcomes:
            for outcome in outcomes:
                msg += f"   {outcome['outcome_type']}: {outcome['count']}\n"
        else:
            msg += "No outcomes yet\n"
        
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
        msg = f"❌ Error: {e}"
    finally:
        conn.close()
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_daily_rewards_main")]]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

