"""
Telegram Bot Handlers for Daily Rewards & Case Opening
Premium gamification handlers with next-level animations
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import asyncio
from daily_rewards_system import (
    check_daily_login,
    claim_daily_reward,
    get_user_points,
    open_case,
    get_user_stats,
    get_leaderboard,
    CASE_TYPES,
    DAILY_REWARDS
)
from utils import send_message_with_retry, is_primary_admin

# ============================================================================
# DAILY REWARDS HANDLERS
# ============================================================================

async def handle_daily_rewards_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main daily rewards menu"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    # Check daily login status
    login_info = check_daily_login(user_id)
    user_points = get_user_points(user_id)
    
    # Build message
    msg = "🎁 **DAILY REWARDS** 🎁\n\n"
    
    if login_info.get('is_first_time'):
        msg += "👋 Welcome! This is your first login!\n\n"
    elif login_info.get('streak_broken'):
        msg += "😢 Your streak was broken. Starting fresh!\n\n"
    
    msg += f"🔥 **Current Streak:** {login_info['streak']} day(s)\n"
    msg += f"💰 **Your Points:** {user_points}\n\n"
    
    # Show streak progress
    msg += "📅 **7-Day Streak Calendar:**\n"
    for day in range(1, 8):
        if day < login_info['streak']:
            msg += f"✅ Day {day}: {DAILY_REWARDS[day]} pts\n"
        elif day == login_info['streak']:
            if login_info['can_claim']:
                msg += f"🎯 **Day {day}: {DAILY_REWARDS[day]} pts** ⬅️ Claim Now!\n"
            else:
                msg += f"✅ Day {day}: {DAILY_REWARDS[day]} pts (claimed)\n"
        else:
            msg += f"⬜ Day {day}: {DAILY_REWARDS[day]} pts\n"
    
    msg += f"\n🎁 **Next Reward:** {login_info.get('next_reward', '—')} points"
    
    # Build keyboard
    keyboard = []
    
    if login_info['can_claim']:
        keyboard.append([InlineKeyboardButton(
            f"🎁 Claim {login_info['points_to_award']} Points",
            callback_data="claim_daily_reward"
        )])
    
    keyboard.extend([
        [InlineKeyboardButton("💎 Open Cases", callback_data="case_opening_menu")],
        [InlineKeyboardButton("📊 My Stats", callback_data="my_case_stats")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="case_leaderboard")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_start")]
    ])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_claim_daily_reward(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Claim daily reward with celebration animation"""
    query = update.callback_query
    user_id = query.from_user.id
    
    result = claim_daily_reward(user_id)
    
    if result['success']:
        # Success animation
        msg = "🎉 **REWARD CLAIMED!** 🎉\n\n"
        msg += f"✨ +{result['points_awarded']} Points\n"
        msg += f"🔥 Streak: Day {result['new_streak']}\n"
        msg += f"💰 Total Points: {result['total_points']}\n\n"
        msg += "🎰 Ready to test your luck?\n"
        msg += "Open cases to win products or multiply your points!"
        
        keyboard = [
            [InlineKeyboardButton("💎 Open Cases Now", callback_data="case_opening_menu")],
            [InlineKeyboardButton("⬅️ Back", callback_data="daily_rewards_menu")]
        ]
        
        await query.answer("🎁 Reward claimed!", show_alert=True)
    else:
        msg = result['message']
        keyboard = [
            [InlineKeyboardButton("⬅️ Back", callback_data="daily_rewards_menu")]
        ]
        
        await query.answer("Already claimed today!", show_alert=False)
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================================================
# CASE OPENING HANDLERS
# ============================================================================

async def handle_case_opening_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Case selection menu"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    user_points = get_user_points(user_id)
    
    msg = "💎 **CASE OPENING** 💎\n\n"
    msg += f"💰 **Your Points:** {user_points}\n\n"
    msg += "Choose a case to open:\n\n"
    
    keyboard = []
    
    for case_type, config in CASE_TYPES.items():
        can_afford = user_points >= config['cost']
        
        msg += f"{config['emoji']} **{config['name']}**\n"
        msg += f"   💰 Cost: {config['cost']} points\n"
        msg += f"   📊 {config['description']}\n"
        
        # Show odds
        rewards = config['rewards']
        msg += f"   🎁 Product: {rewards.get('win_product', 0)}%\n"
        
        if can_afford:
            msg += f"   ✅ **Available**\n\n"
            keyboard.append([InlineKeyboardButton(
                f"{config['emoji']} Open {config['name']} ({config['cost']} pts)",
                callback_data=f"open_case|{case_type}"
            )])
        else:
            msg += f"   ❌ Need {config['cost'] - user_points} more points\n\n"
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="daily_rewards_menu")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_open_case(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Open a case with premium animation sequence"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not params:
        await query.answer("Error: No case type specified", show_alert=True)
        return
    
    case_type = params[0]
    
    # Open the case
    result = open_case(user_id, case_type)
    
    if not result['success']:
        await query.answer(result['message'], show_alert=True)
        return
    
    await query.answer("🎰 Opening case...", show_alert=False)
    
    # === PREMIUM ANIMATION SEQUENCE ===
    animation_data = result['animation_data']
    case_emoji = animation_data['case_emoji']
    
    # Step 1: Case intro (0.5s)
    msg = f"{case_emoji} **OPENING CASE** {case_emoji}\n\n"
    msg += "```\n"
    msg += "╔══════════════════╗\n"
    msg += "║                  ║\n"
    msg += f"║   {case_emoji}  READY  {case_emoji}   ║\n"
    msg += "║                  ║\n"
    msg += "╚══════════════════╝\n"
    msg += "```"
    
    await query.edit_message_text(msg, parse_mode='Markdown')
    await asyncio.sleep(0.5)
    
    # Step 2: Spinning animation (reel of items)
    reel_items = animation_data['reel_items']
    
    for i in range(0, len(reel_items), 3):  # Show 3 items at a time
        visible_items = reel_items[i:i+3]
        
        msg = f"{case_emoji} **SPINNING...** {case_emoji}\n\n"
        msg += "```\n"
        msg += "╔══════════════════╗\n"
        
        for item in visible_items:
            msg += f"║      {item['emoji']}  {item['emoji']}  {item['emoji']}      ║\n"
        
        msg += "╚══════════════════╝\n"
        msg += "```\n"
        msg += "🎰 " + "▓" * (i // 3) + "░" * (10 - i // 3)
        
        await query.edit_message_text(msg, parse_mode='Markdown')
        
        # Speed up near the end
        if i < 20:
            await asyncio.sleep(0.1)
        else:
            await asyncio.sleep(0.3)  # Slow down before reveal
    
    # Step 3: Dramatic pause
    await asyncio.sleep(0.5)
    
    # Step 4: REVEAL with particles
    outcome_emoji = animation_data['final_outcome']['emoji']
    outcome_msg = animation_data['final_outcome']['message']
    outcome_value = animation_data['final_outcome']['value']
    glow = animation_data['final_outcome']['glow_color']
    particles = animation_data['particles'][:6]
    
    msg = f"{case_emoji} **CASE OPENED!** {case_emoji}\n\n"
    msg += f"{' '.join(particles)}\n\n"
    msg += "```\n"
    msg += "╔══════════════════╗\n"
    msg += "║                  ║\n"
    msg += f"║   {outcome_emoji}  {outcome_emoji}  {outcome_emoji}   ║\n"
    msg += "║                  ║\n"
    msg += "╚══════════════════╝\n"
    msg += "```\n\n"
    msg += f"{glow} **{outcome_msg}** {glow}\n"
    msg += f"🎁 **{outcome_value}**\n\n"
    msg += f"💰 New Balance: **{result['new_balance']} points**"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Open Another", callback_data="case_opening_menu")],
        [InlineKeyboardButton("📊 My Stats", callback_data="my_case_stats")],
        [InlineKeyboardButton("⬅️ Back", callback_data="daily_rewards_menu")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================================================
# STATS & LEADERBOARD HANDLERS
# ============================================================================

async def handle_my_case_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show user's case opening statistics"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    stats = get_user_stats(user_id)
    
    msg = "📊 **YOUR STATS** 📊\n\n"
    msg += f"💰 **Current Points:** {stats['points']}\n"
    msg += f"💎 **Lifetime Points:** {stats['lifetime_points']}\n"
    msg += f"🎰 **Cases Opened:** {stats['cases_opened']}\n"
    msg += f"🎁 **Products Won:** {stats['products_won']}\n"
    msg += f"📈 **Win Rate:** {stats['win_rate']}%\n\n"
    
    # Visual win rate bar
    win_blocks = int(stats['win_rate'] / 10)
    msg += f"🏆 {'🟩' * win_blocks}{'⬜' * (10 - win_blocks)} {stats['win_rate']}%"
    
    keyboard = [
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="case_leaderboard")],
        [InlineKeyboardButton("⬅️ Back", callback_data="case_opening_menu")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_case_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show top players leaderboard"""
    query = update.callback_query
    
    await query.answer()
    
    top_players = get_leaderboard(10)
    
    msg = "🏆 **LEADERBOARD** 🏆\n\n"
    msg += "**Top 10 Players:**\n\n"
    
    medals = ['🥇', '🥈', '🥉']
    
    for idx, player in enumerate(top_players, 1):
        medal = medals[idx - 1] if idx <= 3 else f"{idx}."
        
        msg += f"{medal} "
        msg += f"**{player['lifetime_points']}** pts"
        msg += f" | {player['total_cases_opened']} cases"
        msg += f" | {player['total_products_won']} 🎁\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 My Stats", callback_data="my_case_stats")],
        [InlineKeyboardButton("⬅️ Back", callback_data="case_opening_menu")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================================================
# ADMIN CONFIGURATION HANDLERS
# ============================================================================

async def handle_admin_daily_rewards_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Admin menu for daily rewards & case opening configuration"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    msg = "⚙️ **DAILY REWARDS & CASES SETTINGS** ⚙️\n\n"
    msg += "Configure gamification system:\n\n"
    
    msg += "**Current Configuration:**\n\n"
    
    for case_type, config in CASE_TYPES.items():
        msg += f"{config['emoji']} **{config['name']}**\n"
        msg += f"   Cost: {config['cost']} points\n"
        msg += f"   Product chance: {config['rewards']['win_product']}%\n\n"
    
    msg += "**Daily Rewards:**\n"
    for day, points in DAILY_REWARDS.items():
        msg += f"Day {day}: {points} points\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 View Statistics", callback_data="admin_case_stats")],
        [InlineKeyboardButton("🎁 Manage Rewards Pool", callback_data="admin_manage_rewards")],
        [InlineKeyboardButton("⚙️ Edit Case Settings", callback_data="admin_edit_cases")],
        [InlineKeyboardButton("👥 Top Players", callback_data="case_leaderboard")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_case_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show admin statistics for case openings"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    from utils import get_db_connection
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Total stats
        c.execute('SELECT COUNT(*) as total FROM case_openings')
        total_openings = c.fetchone()['total']
        
        c.execute('SELECT SUM(points_spent) as total FROM case_openings')
        total_spent = c.fetchone()['total'] or 0
        
        c.execute('SELECT SUM(points_won) as total FROM case_openings')
        total_won = c.fetchone()['total'] or 0
        
        c.execute("SELECT COUNT(*) as total FROM case_openings WHERE outcome_type = 'win_product'")
        products_won = c.fetchone()['total']
        
        c.execute('SELECT COUNT(DISTINCT user_id) as total FROM case_openings')
        unique_players = c.fetchone()['total']
        
        msg = "📊 **CASE OPENING STATISTICS** 📊\n\n"
        msg += f"🎰 **Total Cases Opened:** {total_openings}\n"
        msg += f"👥 **Unique Players:** {unique_players}\n"
        msg += f"💰 **Total Points Spent:** {total_spent}\n"
        msg += f"💎 **Total Points Won:** {total_won}\n"
        msg += f"🎁 **Products Awarded:** {products_won}\n"
        msg += f"📈 **House Edge:** {((total_spent - total_won) / total_spent * 100) if total_spent > 0 else 0:.1f}%\n\n"
        
        # Per case stats
        for case_type in CASE_TYPES.keys():
            c.execute('''
                SELECT COUNT(*) as count, SUM(points_spent) as spent
                FROM case_openings
                WHERE case_type = %s
            ''', (case_type,))
            
            case_stats = c.fetchone()
            msg += f"\n{CASE_TYPES[case_type]['emoji']} **{CASE_TYPES[case_type]['name']}:**\n"
            msg += f"   Opened: {case_stats['count']} times\n"
            msg += f"   Revenue: {case_stats['spent'] or 0} points\n"
        
    finally:
        conn.close()
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_daily_rewards_settings")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_manage_rewards(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Admin interface to manage rewards pool"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    from utils import get_db_connection
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get current products in rewards pool
        c.execute('''
            SELECT id, name, price, available
            FROM products
            WHERE available > 0
            ORDER BY price DESC
            LIMIT 10
        ''')
        products = c.fetchall()
        
        msg = "🎁 **REWARDS POOL MANAGEMENT** 🎁\n\n"
        msg += "**Available Products for Case Rewards:**\n\n"
        
        if products:
            for p in products:
                msg += f"🎯 **{p['name']}**\n"
                msg += f"   💰 Price: €{p['price']:.2f}\n"
                msg += f"   📦 Stock: {p['available']}\n\n"
        else:
            msg += "⚠️ No products available\n\n"
        
        msg += "💡 **Note:** Cases award random products from your active product catalog.\n"
        msg += "To add/remove products, use the Product Management menu.\n"
        
    finally:
        conn.close()
    
    keyboard = [
        [InlineKeyboardButton("📦 Manage Products", callback_data="adm_products")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_manage_rewards")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_daily_rewards_settings")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_edit_cases(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Admin interface to edit case settings"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied", show_alert=True)
        return
    
    await query.answer()
    
    msg = "⚙️ **CASE SETTINGS EDITOR** ⚙️\n\n"
    msg += "**Current Case Configuration:**\n\n"
    
    for case_type, config in CASE_TYPES.items():
        msg += f"{config['emoji']} **{config['name']}**\n"
        msg += f"   💰 Cost: {config['cost']} points\n"
        msg += f"   🎁 Win Product: {config['rewards']['win_product']}%\n"
        msg += f"   💎 Win Points: {config['rewards']['win_points']}%\n"
        msg += f"   ❌ Lose: {config['rewards']['lose']}%\n"
        msg += f"   🎰 Animation: {config['animation_speed']}s\n\n"
    
    msg += "**Daily Streak Rewards:**\n"
    for day, points in DAILY_REWARDS.items():
        msg += f"   Day {day}: {points} points\n"
    
    msg += "\n💡 **Note:** To modify these values, edit the configuration in `daily_rewards_system.py`\n"
    msg += "Restart the bot after making changes.\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 View Statistics", callback_data="admin_case_stats")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_edit_cases")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_daily_rewards_settings")]
    ]
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

