"""
Case Opening Handlers - User-facing
Handles case opening, city selection, and balance conversion
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import get_db_connection
from daily_rewards_system import get_all_cases, get_user_points
from case_rewards_system import (
    open_product_case,
    get_available_cities_for_product,
    select_delivery_city,
    convert_win_to_balance
)

logger = logging.getLogger(__name__)

# ============================================================================
# CASE OPENING MENU
# ============================================================================

async def handle_case_opening_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show available cases to open"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    # Get user points
    points = get_user_points(user_id)
    
    # Get available cases from database
    cases = get_all_cases()
    
    msg = f"🎰 OPEN CASES\n\n"
    msg += f"💰 Your Points: {points}\n\n"
    
    if not cases:
        msg += "❌ No cases available yet.\nAdmin needs to create cases first."
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="daily_rewards_menu")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    msg += "Select a case to open:\n\n"
    
    keyboard = []
    
    for case_type, config in cases.items():
        can_afford = points >= config['cost']
        status = "✅" if can_afford else "🔒"
        
        keyboard.append([InlineKeyboardButton(
            f"{status} {config['emoji']} {config['name']} - {config['cost']} pts",
            callback_data=f"open_case|{case_type}" if can_afford else "noop"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="daily_rewards_menu")])
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================================
# CASE OPENING ANIMATION
# ============================================================================

async def handle_open_case(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Open a case with animation"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not params:
        await query.answer("Invalid case", show_alert=True)
        return
    
    case_type = params[0]
    cases = get_all_cases()
    config = cases.get(case_type)
    
    if not config:
        await query.answer("Case not found", show_alert=True)
        return
    
    # Check if user has enough points
    points = get_user_points(user_id)
    if points < config['cost']:
        await query.answer(f"❌ Not enough points! Need {config['cost']}, have {points}", show_alert=True)
        return
    
    await query.answer()
    
    # Get reward pool to show actual emojis in animation
    from case_rewards_system import get_case_reward_pool, get_db_connection
    rewards = get_case_reward_pool(case_type)
    
    # Get lose emoji
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT lose_emoji FROM case_lose_emojis WHERE case_type = %s', (case_type,))
    lose_data = c.fetchone()
    lose_emoji = lose_data['lose_emoji'] if lose_data else '💸'
    conn.close()
    
    # Build emoji list for animation (ONLY rewards + lose emoji)
    emoji_list = []
    if rewards:
        for r in rewards:
            if r['reward_emoji']:  # Only add non-null emojis
                emoji_list.append(r['reward_emoji'])
    
    # Add lose emoji
    if lose_emoji:
        emoji_list.append(lose_emoji)
    
    # Fallback if no emojis configured
    if not emoji_list:
        emoji_list = ['🎁', '💎', '⭐', '💸']
    
    # STEP 1: Show emoji legend/preview (what each emoji means)
    legend_msg = f"🎰 {config['emoji']} {config['name'].upper()}\n"
    legend_msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    legend_msg += f"💰 Cost: {config['cost']} points\n\n"
    legend_msg += f"🎁 **POSSIBLE OUTCOMES:**\n\n"
    
    if rewards:
        for r in rewards:
            if r['reward_emoji']:
                legend_msg += f"{r['reward_emoji']} = {r['product_type_name']} {r['product_size']} ({r['win_chance_percent']}%)\n"
    
    if lose_emoji:
        # Calculate lose chance
        total_win = sum(r['win_chance_percent'] for r in rewards if r['reward_emoji']) if rewards else 0
        lose_chance = 100 - total_win
        legend_msg += f"{lose_emoji} = Lose Nothing ({lose_chance:.0f}%)\n"
    
    legend_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    legend_msg += f"🎰 Opening in 3..."
    
    await query.edit_message_text(legend_msg)
    await asyncio.sleep(1)
    
    await query.edit_message_text(legend_msg.replace("Opening in 3...", "Opening in 2..."))
    await asyncio.sleep(1)
    
    await query.edit_message_text(legend_msg.replace("Opening in 3...", "Opening in 1..."))
    await asyncio.sleep(1)
    
    # STEP 2: Open the case FIRST (to know the result)
    result = open_product_case(user_id, case_type, config['cost'])
    
    if not result['success']:
        await query.edit_message_text(
            f"❌ Error: {result.get('message', 'Unknown error')}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="case_opening_menu")
            ]])
        )
        return
    
    # Determine the FINAL emoji (what we'll land on)
    if result['outcome'] == 'lose':
        final_emoji = lose_emoji
    else:
        final_emoji = result['emoji']  # Winning product emoji
    
    # STEP 3: OPTIMIZED animation - fewer frames, faster
    import random
    total_frames = 20  # Reduced from 30 for speed
    last_message = ""  # Track last message to avoid duplicates
    
    for i in range(total_frames):
        # Last 2 frames: show the FINAL emoji
        if i >= 18:
            center = final_emoji
            left = final_emoji
            right = final_emoji
        else:
            # Random spinning
            left = random.choice(emoji_list)
            center = random.choice(emoji_list)
            right = random.choice(emoji_list)
        
        # Progress bar (10 segments - even shorter)
        progress = int((i / total_frames) * 10)
        bar_filled = "█" * progress
        bar_empty = "░" * (10 - progress)
        progress_bar = f"{bar_filled}{bar_empty}"
        
        # Dynamic speed: start fast, end slow
        if i < 8:
            speed = 0.08  # Fast start
        elif i < 15:
            speed = 0.12  # Medium
        else:
            speed = 0.35  # Slow finish
        
        # Build frame with ONLY 2 arrows + frame counter (ensures uniqueness)
        frame_msg = f"🎰 {config['emoji']} SPINNING... [{i+1}/{total_frames}]\n\n"
        frame_msg += f"         ▼\n"
        frame_msg += f"    {left}  {center}  {right}\n"
        frame_msg += f"         ▼\n\n"
        frame_msg += f"{progress_bar}"
        
        # Skip if identical to last message (avoid Telegram error)
        if frame_msg == last_message:
            await asyncio.sleep(speed)
            continue
        
        try:
            await query.edit_message_text(frame_msg)
            last_message = frame_msg
        except Exception as e:
            logger.warning(f"⚠️ Frame {i} edit failed (likely duplicate): {e}")
            # Continue anyway
        
        await asyncio.sleep(speed)
    
    # STEP 4: Hold final result for 1 second
    final_frame = f"🎰 {config['emoji']} RESULT!\n\n"
    final_frame += f"         ▼\n"
    final_frame += f"    {final_emoji}  **{final_emoji}**  {final_emoji}\n"
    final_frame += f"         ▼\n\n"
    final_frame += f"{'█' * 10}"
    
    await query.edit_message_text(final_frame)
    await asyncio.sleep(1.0)  # Hold result
    
    # STEP 5: Show detailed result
    if result['outcome'] == 'lose':
        # User lost - show final frame with arrows pointing to center
        final_frame = (
            f"          ▼\n"
            f"     [ {lose_emoji}  **{lose_emoji}**  {lose_emoji} ]\n"
            f"          ▼"
        )
        msg = f"💸 {config['emoji']} {config['name'].upper()}\n\n"
        msg += f"{final_frame}\n\n"
        msg += f"{result['emoji']} {result['message']}\n\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"💸 Lost {config['cost']} points\n"
        msg += f"💰 Remaining: {points - config['cost']} points"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data=f"open_case|{case_type}")],
            [InlineKeyboardButton("⬅️ Back to Cases", callback_data="case_opening_menu")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        
    else:
        # User won a product! Show final frame with winning emoji and arrows
        win_emoji = result['emoji']
        final_frame = (
            f"          ▼\n"
            f"     [ {win_emoji}  **{win_emoji}**  {win_emoji} ]\n"
            f"          ▼"
        )
        msg = f"🎉 WINNER! 🎉\n\n"
        msg += f"{final_frame}\n\n"
        msg += f"{result['emoji']} You won:\n"
        msg += f"**{result['product_type']} {result['product_size']}**\n\n"
        msg += f"💰 Value: ~{result['estimated_value']:.2f}€\n\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "📍 Next step: Select delivery city"
        
        keyboard = [
            [InlineKeyboardButton("📍 Select City", callback_data=f"select_city|{result['win_id']}")],
            [InlineKeyboardButton("💵 Convert to Balance", callback_data=f"convert_to_balance|{result['win_id']}")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================================================
# CITY SELECTION
# ============================================================================

async def handle_select_city(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show available cities for product delivery"""
    query = update.callback_query
    user_id = query.from_user.id
    
    logger.info(f"🏙️ handle_select_city called: user={user_id}, params={params}")
    
    if not params:
        logger.error(f"❌ No params provided to handle_select_city")
        await query.answer("Invalid win", show_alert=True)
        return
    
    try:
        win_id = int(params[0])
        logger.info(f"✅ Parsed win_id: {win_id}")
    except (ValueError, IndexError) as e:
        logger.error(f"❌ Error parsing win_id from params {params}: {e}")
        await query.answer("Invalid win ID", show_alert=True)
        return
    
    await query.answer()
    
    # Get win details
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT product_type_name, product_size, win_emoji, estimated_value
            FROM user_product_wins
            WHERE id = %s AND user_id = %s AND status = 'pending_city'
        ''', (win_id, user_id))
        
        win = c.fetchone()
        
        if not win:
            await query.edit_message_text(
                "❌ Win not found or already processed",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="daily_rewards_menu")
                ]])
            )
            return
        
        # Get available cities
        cities = get_available_cities_for_product(win['product_type_name'], win['product_size'])
        
        msg = f"{win['win_emoji']} {win['product_type_name']} {win['product_size']}\n\n"
        msg += "📍 SELECT DELIVERY CITY\n\n"
        
        if cities:
            msg += "Available cities:\n"
            for city in cities:
                msg += f"• {city['city_name']} ({city['product_count']} available)\n"
            msg += "\n"
        else:
            msg += "❌ No cities available for this product\n\n"
            msg += "You can convert to balance instead:\n"
            msg += f"💵 {win['estimated_value']:.2f}€ will be added to your account"
        
        keyboard = []
        
        for city in cities:
            keyboard.append([InlineKeyboardButton(
                f"📍 {city['city_name']}",
                callback_data=f"select_district|{win_id}|{city['city_id']}"
            )])
        
        keyboard.append([InlineKeyboardButton(
            "💵 Convert to Balance",
            callback_data=f"convert_to_balance|{win_id}"
        )])
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        
    finally:
        conn.close()

async def handle_select_district(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show districts in selected city"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not params or len(params) < 2:
        await query.answer("Invalid data", show_alert=True)
        return
    
    win_id = int(params[0])
    city_id = int(params[1])
    
    await query.answer()
    
    # Get win details and districts
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT product_type_name, product_size, win_emoji
            FROM user_product_wins
            WHERE id = %s AND user_id = %s
        ''', (win_id, user_id))
        
        win = c.fetchone()
        
        if not win:
            await query.answer("Win not found", show_alert=True)
            return
        
        # Get districts with available products
        c.execute('''
            SELECT DISTINCT 
                d.id as district_id,
                d.name as district_name,
                COUNT(p.id) as product_count
            FROM districts d
            JOIN products p ON p.district_id = d.id
            WHERE d.city_id = %s
                AND p.product_type = %s
                AND p.size = %s
                AND p.available > 0
            GROUP BY d.id, d.name
            ORDER BY d.name
        ''', (city_id, win['product_type_name'], win['product_size']))
        
        districts = c.fetchall()
        
        # Get city name
        c.execute('SELECT name FROM cities WHERE id = %s', (city_id,))
        city = c.fetchone()
        
        msg = f"{win['win_emoji']} {win['product_type_name']} {win['product_size']}\n\n"
        msg += f"📍 {city['name']} - SELECT DISTRICT\n\n"
        
        keyboard = []
        
        for district in districts:
            keyboard.append([InlineKeyboardButton(
                f"{district['district_name']} ({district['product_count']} available)",
                callback_data=f"select_product|{win_id}|{city_id}|{district['district_id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Cities", callback_data=f"select_city|{win_id}")])
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        
    finally:
        conn.close()

async def handle_select_product(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Select specific product for delivery"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not params or len(params) < 3:
        await query.answer("Invalid data", show_alert=True)
        return
    
    win_id = int(params[0])
    city_id = int(params[1])
    district_id = int(params[2])
    
    await query.answer()
    
    # Get available products
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT product_type_name, product_size, win_emoji
            FROM user_product_wins
            WHERE id = %s AND user_id = %s
        ''', (win_id, user_id))
        
        win = c.fetchone()
        
        if not win:
            await query.answer("Win not found", show_alert=True)
            return
        
        # Get products
        c.execute('''
            SELECT id, product_name, price
            FROM products
            WHERE district_id = %s
                AND product_type = %s
                AND size = %s
                AND available > 0
            ORDER BY price
            LIMIT 10
        ''', (district_id, win['product_type_name'], win['product_size']))
        
        products = c.fetchall()
        
        if not products:
            await query.edit_message_text(
                "❌ No products available in this district",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data=f"select_district|{win_id}|{city_id}")
                ]])
            )
            return
        
        # Auto-select first product
        product = products[0]
        
        # Confirm delivery
        success = select_delivery_city(win_id, city_id, district_id, product['id'])
        
        if success:
            msg = f"✅ DELIVERY CONFIRMED!\n\n"
            msg += f"{win['win_emoji']} {win['product_type_name']} {win['product_size']}\n\n"
            msg += f"📦 Product: {product['product_name']}\n"
            msg += f"💰 Value: {product['price']:.2f}€\n\n"
            msg += "Your product will be delivered soon!\n"
            msg += "Check your orders for delivery details."
            
            keyboard = [
                [InlineKeyboardButton("🎰 Open Another Case", callback_data="case_opening_menu")],
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data="daily_rewards_menu")]
            ]
            
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("❌ Error processing delivery", show_alert=True)
        
    finally:
        conn.close()

async def handle_convert_to_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Convert product win to balance"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not params:
        await query.answer("Invalid win", show_alert=True)
        return
    
    win_id = int(params[0])
    
    # Get win details
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT product_type_name, product_size, win_emoji, estimated_value
            FROM user_product_wins
            WHERE id = %s AND user_id = %s
        ''', (win_id, user_id))
        
        win = c.fetchone()
        
        if not win:
            await query.answer("Win not found", show_alert=True)
            return
        
        # Convert to balance
        success = convert_win_to_balance(win_id, user_id)
        
        if success:
            await query.answer(f"✅ Added {win['estimated_value']:.2f}€ to your balance!", show_alert=True)
            
            msg = f"💵 CONVERTED TO BALANCE\n\n"
            msg += f"{win['win_emoji']} {win['product_type_name']} {win['product_size']}\n\n"
            msg += f"✅ Added to balance: {win['estimated_value']:.2f}€\n\n"
            msg += "You can now use this balance to purchase any products!"
            
            keyboard = [
                [InlineKeyboardButton("🎰 Open Another Case", callback_data="case_opening_menu")],
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data="daily_rewards_menu")]
            ]
            
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("❌ Error converting to balance", show_alert=True)
        
    finally:
        conn.close()

