"""
Marketing and Promotions System with Customizable UI Designs
Provides different bot interface themes and user experience flows
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import get_db_connection, send_message_with_retry, is_primary_admin
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# UI Theme Constants
UI_THEMES = {
    'minimalist': {
        'name': 'Minimalist (Apple Style)',
        'description': 'Clean, minimal interface with centered text and bold formatting',
        'welcome_buttons': [
            ['🛍️ Shop', '👤 Profile', '💳 Top Up']
        ],
        'style': 'minimal'
    },
    'classic': {
        'name': 'Classic (Full Featured)',
        'description': 'Traditional bot interface with comprehensive options',
        'welcome_buttons': [
            ['🛍️ Shop', '📊 Categories'],
            ['👤 Profile', '💳 Balance', '🎁 Promotions'],
            ['ℹ️ Help', '📞 Support']
        ],
        'style': 'classic'
    },
    'modern': {
        'name': 'Modern (Card Style)',
        'description': 'Modern card-based interface with visual elements',
        'welcome_buttons': [
            ['🛍️ Shop Now', '🔥 Hot Deals'],
            ['👤 My Account', '💰 Wallet'],
            ['🎯 Promotions', '📱 App']
        ],
        'style': 'modern'
    }
}

def init_marketing_tables():
    """Initialize marketing and UI theme tables"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        logger.info("🎨 Initializing marketing and UI theme tables...")
        
        # UI Themes configuration table
        c.execute('''CREATE TABLE IF NOT EXISTS ui_themes (
            id SERIAL PRIMARY KEY,
            theme_name TEXT NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT FALSE,
            welcome_message TEXT,
            button_layout TEXT,
            style_config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # User UI preferences
        c.execute('''CREATE TABLE IF NOT EXISTS user_ui_preferences (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            theme_name TEXT NOT NULL,
            custom_settings TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Marketing campaigns
        c.execute('''CREATE TABLE IF NOT EXISTS marketing_campaigns (
            id SERIAL PRIMARY KEY,
            campaign_name TEXT NOT NULL,
            campaign_type TEXT NOT NULL,
            target_audience TEXT,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            config_data TEXT,
            created_by_admin_id BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Promotion codes
        c.execute('''CREATE TABLE IF NOT EXISTS promotion_codes (
            id SERIAL PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            discount_type TEXT NOT NULL, -- 'percentage', 'fixed_amount'
            discount_value DECIMAL(10,2) NOT NULL,
            min_purchase_amount DECIMAL(10,2) DEFAULT 0,
            max_uses INTEGER DEFAULT NULL,
            current_uses INTEGER DEFAULT 0,
            valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            valid_until TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            created_by_admin_id BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Promotion usage tracking
        c.execute('''CREATE TABLE IF NOT EXISTS promotion_usage (
            id SERIAL PRIMARY KEY,
            promotion_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,
            order_id INTEGER,
            discount_applied DECIMAL(10,2),
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Insert default themes if not exists
        for theme_key, theme_data in UI_THEMES.items():
            c.execute("""
                INSERT INTO ui_themes (theme_name, is_active, welcome_message, button_layout, style_config)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (theme_name) DO NOTHING
            """, (
                theme_key,
                theme_key == 'minimalist',  # Set minimalist as default active
                f"Welcome to our store! 🛍️\n\nChoose an option below:",
                str(theme_data['welcome_buttons']),
                str(theme_data)
            ))
        
        conn.commit()
        logger.info("✅ Marketing and UI theme tables initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Error initializing marketing tables: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def get_active_ui_theme():
    """Get the currently active UI theme"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT theme_name, welcome_message, button_layout, style_config
            FROM ui_themes 
            WHERE is_active = TRUE
            LIMIT 1
        """)
        result = c.fetchone()
        
        if result:
            return {
                'theme_name': result['theme_name'],
                'welcome_message': result['welcome_message'],
                'button_layout': eval(result['button_layout']) if result['button_layout'] else [],
                'style_config': eval(result['style_config']) if result['style_config'] else {}
            }
        else:
            # Return default classic theme (original interface)
            return {
                'theme_name': 'classic',
                'welcome_message': "Welcome to our store! 🛍️\n\nChoose an option below:",
                'button_layout': [['🛍️ Shop', '👤 Profile', '💳 Top Up']],
                'style_config': UI_THEMES['classic']
            }
            
    except Exception as e:
        logger.error(f"Error getting active UI theme: {e}")
        return {
            'theme_name': 'classic',
            'welcome_message': "Welcome to our store! 🛍️\n\nChoose an option below:",
            'button_layout': [['🛍️ Shop', '👤 Profile', '💳 Top Up']],
            'style_config': UI_THEMES['classic']
        }
    finally:
        if conn:
            conn.close()

# --- Admin UI Theme Management ---

async def handle_marketing_promotions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main marketing and promotions management menu"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    # Get current active theme
    active_theme = get_active_ui_theme()
    
    msg = "🎨 **Marketing & Promotions**\n\n"
    msg += "**Manage your bot's appearance and promotional campaigns:**\n\n"
    msg += f"🎯 **Current UI Theme:** {active_theme['theme_name'].title()}\n"
    msg += f"📱 **Style:** {active_theme['style_config'].get('description', 'Custom theme')}\n\n"
    msg += "**Available Options:**"
    
    keyboard = [
        [InlineKeyboardButton("🎨 UI Theme Designer", callback_data="ui_theme_designer")],
        [InlineKeyboardButton("📝 Welcome Message Editor", callback_data="welcome_message_editor")],
        [InlineKeyboardButton("🎁 Promotion Codes", callback_data="promotion_codes_menu")],
        [InlineKeyboardButton("📊 Marketing Campaigns", callback_data="marketing_campaigns_menu")],
        [InlineKeyboardButton("👀 Preview Current Theme", callback_data="preview_current_theme")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ui_theme_designer(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """UI Theme selection and customization"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    active_theme = get_active_ui_theme()
    
    msg = "🎨 **UI Theme Designer**\n\n"
    msg += "**Choose a theme for your bot's user interface:**\n\n"
    msg += f"**Currently Active:** {active_theme['theme_name'].title()} ✅\n\n"
    
    keyboard = []
    for theme_key, theme_data in UI_THEMES.items():
        status = "✅ Active" if theme_key == active_theme['theme_name'] else "Select"
        button_text = f"{theme_data['name']} - {status}"
        callback_data = f"select_ui_theme|{theme_key}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.extend([
        [InlineKeyboardButton("🔧 Customize Active Theme", callback_data="customize_active_theme")],
        [InlineKeyboardButton("⬅️ Back to Marketing", callback_data="marketing_promotions_menu")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_select_ui_theme(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Select and activate a UI theme"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params:
        await query.answer("Invalid theme selection", show_alert=True)
        return
    
    theme_name = params[0]
    
    if theme_name not in UI_THEMES:
        await query.answer("Theme not found", show_alert=True)
        return
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Deactivate all themes
        c.execute("UPDATE ui_themes SET is_active = FALSE")
        
        # Activate selected theme
        c.execute("""
            UPDATE ui_themes 
            SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE theme_name = %s
        """, (theme_name,))
        
        # If theme doesn't exist, create it
        if c.rowcount == 0:
            theme_data = UI_THEMES[theme_name]
            c.execute("""
                INSERT INTO ui_themes (theme_name, is_active, welcome_message, button_layout, style_config)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                theme_name,
                True,
                f"Welcome to our store! 🛍️\n\nChoose an option below:",
                str(theme_data['welcome_buttons']),
                str(theme_data)
            ))
        
        conn.commit()
        
        theme_data = UI_THEMES[theme_name]
        msg = f"✅ **Theme Activated Successfully!**\n\n"
        msg += f"**Theme:** {theme_data['name']}\n"
        msg += f"**Style:** {theme_data['description']}\n\n"
        msg += "The new theme is now active for all users!"
        
        await query.answer("Theme activated!", show_alert=False)
        
    except Exception as e:
        logger.error(f"Error activating theme: {e}")
        if conn:
            conn.rollback()
        msg = "❌ **Error activating theme.** Please try again."
        await query.answer("Activation failed", show_alert=True)
    finally:
        if conn:
            conn.close()
    
    keyboard = [
        [InlineKeyboardButton("👀 Preview Theme", callback_data="preview_current_theme")],
        [InlineKeyboardButton("🔧 Customize Theme", callback_data="customize_active_theme")],
        [InlineKeyboardButton("⬅️ Back to Themes", callback_data="ui_theme_designer")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- Minimalist UI Implementation ---

async def handle_minimalist_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle welcome message with minimalist UI theme"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Get active theme configuration
    theme = get_active_ui_theme()
    
    if theme['theme_name'] != 'minimalist':
        # Fallback to regular welcome if not minimalist theme
        return
    
    # Format minimalist welcome message
    msg = theme['welcome_message']
    
    # Create clean, centered button layout
    keyboard = []
    for button_row in theme['button_layout']:
        row = []
        for button_text in button_row:
            if button_text == '🛍️ Shop':
                row.append(InlineKeyboardButton(button_text, callback_data="minimalist_shop"))
            elif button_text == '👤 Profile':
                row.append(InlineKeyboardButton(button_text, callback_data="minimalist_profile"))
            elif button_text == '💳 Top Up':
                row.append(InlineKeyboardButton(button_text, callback_data="minimalist_topup"))
        keyboard.append(row)
    
    await send_message_with_retry(
        context.bot, chat_id, msg, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

async def handle_minimalist_shop(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle shop button in minimalist UI - show city selection"""
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all cities with product counts
        c.execute("""
            SELECT 
                city,
                COUNT(*) as product_count,
                COUNT(DISTINCT district) as district_count
            FROM products 
            WHERE available > 0
            GROUP BY city
            ORDER BY city
        """)
        cities = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading cities for minimalist shop: {e}")
        await query.answer("Error loading cities", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not cities:
        await query.edit_message_text(
            "🚫 **No Products Available**\n\nSorry, no products are currently available.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]]),
            parse_mode='Markdown'
        )
        return
    
    # Clean, minimalist city selection
    msg = "🏙️ **Choose a City**\n\n"
    msg += "**Select your location:**"
    
    keyboard = []
    for city in cities:
        city_name = city['city']
        product_count = city['product_count']
        district_count = city['district_count']
        
        # Clean button text without clutter
        button_text = f"🏙️ {city_name}"
        callback_data = f"minimalist_city_select|{city_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Add home button
    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_minimalist_city_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle city selection in minimalist UI - show districts with products"""
    query = update.callback_query
    if not params:
        await query.answer("Invalid city selection", show_alert=True)
        return
    
    city_name = params[0]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get districts with sample products and counts
        c.execute("""
            SELECT 
                district,
                COUNT(*) as product_count,
                MIN(product_type) as sample_product,
                MIN(size) as sample_size,
                MIN(price) as min_price
            FROM products 
            WHERE city = %s AND available > 0
            GROUP BY district
            ORDER BY district
        """, (city_name,))
        districts = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading districts for city {city_name}: {e}")
        await query.answer("Error loading districts", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not districts:
        await query.edit_message_text(
            f"🚫 **No Products in {city_name}**\n\nSorry, no products are available in this city.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Cities", callback_data="minimalist_shop")],
                [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # Clean, Apple-style district display
    msg = f"🏙️ **{city_name}**\n\n"
    
    # Show sample products for each district
    for district in districts[:3]:  # Show max 3 districts in preview
        district_name = district['district']
        sample_product = district['sample_product']
        sample_size = district['sample_size']
        min_price = district['min_price']
        
        msg += f"🏘️ **{district_name}:**\n"
        msg += f"    • 😃 **{sample_product} {sample_size}** ({min_price:.2f}€)\n\n"
    
    if len(districts) > 3:
        msg += f"... and {len(districts) - 3} more districts\n\n"
    
    msg += "**Choose a district:**"
    
    keyboard = []
    for district in districts:
        district_name = district['district']
        button_text = f"🏘️ {district_name}"
        callback_data = f"minimalist_district_select|{city_name}|{district_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Navigation buttons
    keyboard.extend([
        [InlineKeyboardButton("⬅️ Back to Cities", callback_data="minimalist_shop")],
        [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_minimalist_district_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle district selection - show products in clean grid layout"""
    query = update.callback_query
    if not params or len(params) < 2:
        await query.answer("Invalid district selection", show_alert=True)
        return
    
    city_name = params[0]
    district_name = params[1]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all products in this district grouped by type
        c.execute("""
            SELECT 
                product_type,
                size,
                price,
                available,
                id
            FROM products 
            WHERE city = %s AND district = %s AND available > 0
            ORDER BY product_type, size
        """, (city_name, district_name))
        products = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading products for {city_name} -> {district_name}: {e}")
        await query.answer("Error loading products", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not products:
        await query.edit_message_text(
            f"🚫 **No Products Available**\n\n**{city_name} → {district_name}**\n\nSorry, no products are currently available in this location.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Districts", callback_data=f"minimalist_city_select|{city_name}")],
                [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # Group products by type for clean display
    product_groups = {}
    for product in products:
        product_type = product['product_type']
        if product_type not in product_groups:
            product_groups[product_type] = []
        product_groups[product_type].append(product)
    
    # Create clean, Apple-style product grid
    msg = f"🏙️ **{city_name}** | 🏘️ **{district_name}**\n\n"
    msg += "**Select product type:**\n\n"
    
    keyboard = []
    
    # Create product type buttons in grid layout
    for product_type, type_products in product_groups.items():
        # Find emoji for product type (you can customize this)
        emoji = get_product_emoji(product_type)
        
        # Show price range for this type
        prices = [p['price'] for p in type_products]
        min_price = min(prices)
        max_price = max(prices)
        
        if min_price == max_price:
            price_text = f"{min_price:.2f}€"
        else:
            price_text = f"{min_price:.2f}€-{max_price:.2f}€"
        
        button_text = f"{emoji} {product_type}"
        callback_data = f"minimalist_product_type|{city_name}|{district_name}|{product_type}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Navigation buttons
    keyboard.extend([
        [InlineKeyboardButton("⬅️ Back to Districts", callback_data=f"minimalist_city_select|{city_name}")],
        [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_minimalist_product_type(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show product variants (sizes/weights) for selected type"""
    query = update.callback_query
    if not params or len(params) < 3:
        await query.answer("Invalid product selection", show_alert=True)
        return
    
    city_name = params[0]
    district_name = params[1]
    product_type = params[2]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all variants of this product type
        c.execute("""
            SELECT 
                id,
                size,
                price,
                available
            FROM products 
            WHERE city = %s AND district = %s AND product_type = %s AND available > 0
            ORDER BY price
        """, (city_name, district_name, product_type))
        variants = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading product variants: {e}")
        await query.answer("Error loading products", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not variants:
        await query.edit_message_text(
            f"🚫 **No Variants Available**\n\n**{product_type}** in **{district_name}**\n\nSorry, no variants are currently available.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data=f"minimalist_district_select|{city_name}|{district_name}")],
                [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    emoji = get_product_emoji(product_type)
    
    # Clean product selection display
    msg = f"🏙️ **{city_name}** | 🏘️ **{district_name}**\n\n"
    msg += f"{emoji} **{product_type}**\n\n"
    msg += "**Select size and price:**"
    
    keyboard = []
    
    # Create size/price buttons - wide buttons as requested
    for variant in variants:
        size = variant['size']
        price = variant['price']
        available = variant['available']
        product_id = variant['id']
        
        # Wide button with size and price
        button_text = f"**{size}** - **{price:.2f}€**"
        callback_data = f"minimalist_product_select|{product_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Navigation buttons on last row together as requested
    keyboard.append([
        InlineKeyboardButton("⬅️ Back to District", callback_data=f"minimalist_district_select|{city_name}|{district_name}"),
        InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_minimalist_product_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show product details and purchase options"""
    query = update.callback_query
    if not params:
        await query.answer("Invalid product selection", show_alert=True)
        return
    
    product_id = int(params[0])
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get product details
        c.execute("""
            SELECT 
                id, city, district, product_type, size, price, available,
                name, original_text
            FROM products 
            WHERE id = %s AND available > 0
        """, (product_id,))
        product = c.fetchone()
        
        if not product:
            await query.answer("Product not found or unavailable", show_alert=True)
            return
        
        # Get user balance
        c.execute("SELECT balance FROM users WHERE user_id = %s", (query.from_user.id,))
        user_result = c.fetchone()
        user_balance = user_result['balance'] if user_result else 0.0
        
    except Exception as e:
        logger.error(f"Error loading product details: {e}")
        await query.answer("Error loading product", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    # Store product selection for purchase
    context.user_data['selected_product_id'] = product_id
    context.user_data['selected_product'] = dict(product)
    
    emoji = get_product_emoji(product['product_type'])
    
    # Clean, minimal product details as requested
    msg = f"🏙️ **{product['city']}** | 🏘️ **{product['district']}**\n\n"
    msg += f"{emoji} **{product['product_type']}** - **{product['size']}**\n\n"
    msg += f"💰 **Price:** **{product['price']:.2f} EUR**\n"
    msg += f"🔢 **Available:** **{product['available']}**\n\n"
    
    # Check if user has sufficient balance
    has_balance = user_balance >= product['price']
    
    keyboard = []
    
    if has_balance:
        # User has sufficient balance - show direct pay button
        keyboard.append([InlineKeyboardButton("💳 Pay Now", callback_data=f"minimalist_pay_options|{product_id}")])
    else:
        # User needs to pay with crypto or top up
        keyboard.append([InlineKeyboardButton("💳 Pay with Crypto", callback_data=f"minimalist_crypto_payment|{product_id}")])
        keyboard.append([InlineKeyboardButton("💰 Top Up Balance", callback_data="minimalist_topup")])
    
    # Navigation
    keyboard.extend([
        [InlineKeyboardButton("⬅️ Back to Products", callback_data=f"minimalist_product_type|{product['city']}|{product['district']}|{product['product_type']}")],
        [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_minimalist_pay_options(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show payment options: balance or discount code"""
    query = update.callback_query
    if not params:
        await query.answer("Invalid payment selection", show_alert=True)
        return
    
    product_id = int(params[0])
    product = context.user_data.get('selected_product')
    
    if not product:
        await query.answer("Product selection expired", show_alert=True)
        return
    
    emoji = get_product_emoji(product['product_type'])
    
    msg = f"💳 **Payment Options**\n\n"
    msg += f"{emoji} **{product['product_type']} {product['size']}**\n"
    msg += f"💰 **Price:** **{product['price']:.2f} EUR**\n\n"
    msg += "**Choose payment method:**"
    
    keyboard = [
        [InlineKeyboardButton("💳 Buy Now", callback_data=f"minimalist_buy_now|{product_id}")],
        [InlineKeyboardButton("🎁 Enter Discount Code", callback_data=f"minimalist_discount_code|{product_id}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"minimalist_product_select|{product_id}")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

def get_product_emoji(product_type):
    """Get emoji for product type"""
    emoji_map = {
        'kava': '☕',
        'coffee': '☕',
        'tea': '🍵',
        'chai': '🍵',
        'energy': '⚡',
        'drink': '🥤',
        'food': '🍽️',
        'snack': '🍿',
        'sweet': '🍭',
        'chocolate': '🍫',
        'fruit': '🍎',
        'juice': '🧃',
        'water': '💧',
        'supplement': '💊',
        'vitamin': '💊'
    }
    
    product_lower = product_type.lower()
    for key, emoji in emoji_map.items():
        if key in product_lower:
            return emoji
    
    return '😃'  # Default emoji

# --- Additional handlers for other UI elements ---

async def handle_minimalist_home(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Return to minimalist home screen"""
    query = update.callback_query
    await handle_minimalist_welcome(update, context)

async def handle_minimalist_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show minimalist profile screen"""
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get user info
        c.execute("""
            SELECT balance, total_purchases, created_at
            FROM users 
            WHERE user_id = %s
        """, (user_id,))
        user = c.fetchone()
        
        if not user:
            balance = 0.0
            total_purchases = 0
            member_since = "New User"
        else:
            balance = user['balance']
            total_purchases = user['total_purchases'] or 0
            member_since = user['created_at'].strftime("%B %Y") if user['created_at'] else "Unknown"
        
    except Exception as e:
        logger.error(f"Error loading user profile: {e}")
        balance = 0.0
        total_purchases = 0
        member_since = "Unknown"
    finally:
        if conn:
            conn.close()
    
    msg = f"👤 **Your Profile**\n\n"
    msg += f"💰 **Balance:** **{balance:.2f} EUR**\n"
    msg += f"🛍️ **Total Orders:** **{total_purchases}**\n"
    msg += f"📅 **Member Since:** **{member_since}**\n\n"
    
    keyboard = [
        [InlineKeyboardButton("💳 Top Up Balance", callback_data="minimalist_topup")],
        [InlineKeyboardButton("📋 Order History", callback_data="minimalist_order_history")],
        [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_minimalist_topup(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show minimalist top-up options"""
    query = update.callback_query
    
    msg = f"💳 **Top Up Balance**\n\n"
    msg += "**Select amount to add:**\n\n"
    
    amounts = [5, 10, 20, 50, 100]
    keyboard = []
    
    for amount in amounts:
        button_text = f"💰 {amount} EUR"
        callback_data = f"minimalist_topup_amount|{amount}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.extend([
        [InlineKeyboardButton("💎 Custom Amount", callback_data="minimalist_custom_topup")],
        [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_user_ui_theme_selector(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Allow users to select their preferred UI theme"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Get current user preference
    current_theme = context.user_data.get('ui_theme_preference', 'classic')
    
    msg = "🎨 **Choose Your UI Theme**\n\n"
    msg += "**Select your preferred interface style:**\n\n"
    
    keyboard = []
    
    # Theme options for users
    themes = {
        'classic': {
            'name': '📱 Classic Interface',
            'description': 'Traditional bot interface with all features'
        },
        'minimalist': {
            'name': '🍎 Minimalist (Apple Style)',
            'description': 'Clean, simple interface with minimal buttons'
        }
    }
    
    for theme_key, theme_data in themes.items():
        status = " ✅" if theme_key == current_theme else ""
        button_text = f"{theme_data['name']}{status}"
        callback_data = f"user_select_theme|{theme_key}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.extend([
        [InlineKeyboardButton("👀 Preview Minimalist", callback_data="user_preview_minimalist")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_start")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_user_select_theme(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle user theme selection"""
    query = update.callback_query
    if not params:
        await query.answer("Invalid theme selection", show_alert=True)
        return
    
    theme_name = params[0]
    user_id = query.from_user.id
    
    # Store user preference
    context.user_data['ui_theme_preference'] = theme_name
    
    # Get theme info
    theme_names = {
        'classic': 'Classic Interface',
        'minimalist': 'Minimalist (Apple Style)'
    }
    
    selected_theme_name = theme_names.get(theme_name, theme_name)
    
    msg = f"✅ **Theme Selected!**\n\n"
    msg += f"**Active Theme:** {selected_theme_name}\n\n"
    
    if theme_name == 'minimalist':
        msg += "🍎 **Minimalist Features:**\n"
        msg += "• Clean, Apple-style interface\n"
        msg += "• Simplified navigation\n"
        msg += "• Bold text formatting\n"
        msg += "• Centered layout design\n\n"
        msg += "Your interface will switch to minimalist mode when you return to the main menu."
    else:
        msg += "📱 **Classic Features:**\n"
        msg += "• Full-featured interface\n"
        msg += "• All bot functions accessible\n"
        msg += "• Traditional button layout\n"
        msg += "• Comprehensive options\n\n"
        msg += "Your interface will use the classic mode."
    
    keyboard = [
        [InlineKeyboardButton("🏠 Apply Theme (Go to Main Menu)", callback_data="back_start")],
        [InlineKeyboardButton("🎨 Change Theme", callback_data="user_ui_theme_selector")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    await query.answer(f"Theme changed to {selected_theme_name}!", show_alert=False)

async def handle_user_preview_minimalist(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show preview of minimalist theme without switching"""
    query = update.callback_query
    
    msg = "👀 **Minimalist Theme Preview**\n\n"
    msg += "**🍎 Apple-Style Interface:**\n\n"
    msg += "```\nWelcome to our store! 🛍️\n\nChoose an option below:\n\n[🛍️ Shop] [👤 Profile] [💳 Top Up]\n```\n\n"
    msg += "**🛍️ Shopping Flow:**\n"
    msg += "```\n🏙️ Choose a City\n\nSelect your location:\n\n[🏙️ Klaipeda]\n[🏙️ Vilnius]\n\n[🏠 Home]\n```\n\n"
    msg += "**📱 Product Display:**\n"
    msg += "```\n🏙️ klaipeda | 🏘️ naujamestis\n\n☕ kava - 2g\n\n💰 Price: 2.50 EUR\n🔢 Available: 1\n\n[💳 Pay Now]\n```\n\n"
    msg += "**Features:**\n"
    msg += "• Clean, centered layout\n"
    msg += "• Bold formatting for prices\n"
    msg += "• Wide buttons for options\n"
    msg += "• Minimal, distraction-free design"
    
    keyboard = [
        [InlineKeyboardButton("✅ Use Minimalist Theme", callback_data="user_select_theme|minimalist")],
        [InlineKeyboardButton("⬅️ Back to Theme Selection", callback_data="user_ui_theme_selector")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- END OF FILE marketing_promotions.py ---
