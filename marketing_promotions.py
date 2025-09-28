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
    
    # Create clean, centered button layout - 2 rows as requested
    keyboard = []
    
    # Add admin panel button for admins at the top
    if is_primary_admin(user_id):
        keyboard.append([InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_menu")])
    
    # Add regular user buttons
    keyboard.extend([
        [InlineKeyboardButton("🛍️ Shop", callback_data="minimalist_shop")],
        [InlineKeyboardButton("👤 Profile", callback_data="minimalist_profile"), 
         InlineKeyboardButton("💳 Top Up", callback_data="minimalist_topup")]
    ])
    
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
    
    # Navigation buttons on same row as requested
    keyboard.append([
        InlineKeyboardButton("⬅️ Back to Cities", callback_data="minimalist_shop"),
        InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_minimalist_district_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle district selection - show products in clean grid layout as requested"""
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
        
        # Get all products in this district
        c.execute("""
            SELECT 
                product_type,
                size,
                price,
                available,
                id
            FROM products 
            WHERE city = %s AND district = %s AND available > 0
            ORDER BY product_type, price, size
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
    
    # Group products by type for grid layout
    product_groups = {}
    for product in products:
        product_type = product['product_type']
        if product_type not in product_groups:
            product_groups[product_type] = []
        product_groups[product_type].append(product)
    
    # Create header message
    msg = f"🏙️ **{city_name}** | 🏘️ **{district_name}**\n"
    msg += "**Select product type:**\n\n"
    
    keyboard = []
    
    # STEP 1: Find the longest product name for consistent button width
    longest_product_name_length = 0
    for product_type in product_groups.keys():
        emoji = get_product_emoji(product_type)
        name_with_emoji = f"{emoji} {product_type}"
        if len(name_with_emoji) > longest_product_name_length:
            longest_product_name_length = len(name_with_emoji)
    
    # STEP 2: Create grid with consistent product name button width
    # [Product Name (padded)] [Option1] [Option2] [Option3] etc.
    
    for product_type, type_products in product_groups.items():
        # Remove duplicate products with same price and size
        unique_products = {}
        for product in type_products:
            key = f"{product['price']:.2f}_{product['size']}"
            if key not in unique_products:
                unique_products[key] = product
        
        unique_products_list = list(unique_products.values())
        
        if unique_products_list:  # Only create row if there are unique products
            row = []
            emoji = get_product_emoji(product_type)
            
            # YOLO MODE: Force consistent width with invisible padding
            product_name_base = f"{emoji} {product_type}"
            # Calculate target width (longest product name + some buffer)
            target_width = max(20, longest_product_name_length + 2)
            
            # Pad with invisible characters that still force width
            if len(product_name_base) < target_width:
                padding_needed = target_width - len(product_name_base)
                # Use combination of thin space + zero-width space for invisible padding
                padded_product_name = product_name_base + ("\u2009\u200B" * padding_needed)
            else:
                padded_product_name = product_name_base
            
            # Product name button with consistent width (blank/non-clickable)
            product_name_btn = InlineKeyboardButton(
                padded_product_name,
                callback_data="ignore"  # Blank button that does nothing
            )
            row.append(product_name_btn)
            
            # Add unique clickable price/weight buttons to the right
            for product in unique_products_list:
                price_text = f"{product['price']:.0f}€ {product['size']}"
                # Use product ID to avoid callback_data length limit (64 bytes)
                option_btn = InlineKeyboardButton(
                    price_text,
                    callback_data=f"minimalist_product_select|{product['id']}"
                )
                row.append(option_btn)
            
            # Add the complete row (product name + all its unique options)
            keyboard.append(row)
    
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
    
    # Handle both old format (product_id) and new format (city|district|type|size|price)
    if len(params) == 1:
        # Old format: just product_id
        product_id = int(params[0])
        
        # Get product details from database
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                SELECT id, city, district, product_type, size, price, available, name, original_text
                FROM products WHERE id = %s
            """, (product_id,))
            product = c.fetchone()
        except Exception as e:
            logger.error(f"Error loading product {product_id}: {e}")
            await query.answer("Error loading product", show_alert=True)
            return
        finally:
            if conn:
                conn.close()
                
        if not product:
            await query.answer("Product not found", show_alert=True)
            return
            
        city_name = product['city']
        district_name = product['district']
        product_type = product['product_type']
        size = product['size']
        price = product['price']
        available = product['available']
        
    elif len(params) == 5:
        # New format: city|district|type|size|price
        city_name = params[0]
        district_name = params[1]
        product_type = params[2]
        size = params[3]
        price = float(params[4])
        
        # Find the specific product
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                SELECT id, available, name, original_text
                FROM products 
                WHERE city = %s AND district = %s AND product_type = %s AND size = %s AND price = %s
                ORDER BY id LIMIT 1
            """, (city_name, district_name, product_type, size, price))
            product = c.fetchone()
        except Exception as e:
            logger.error(f"Error loading product {city_name}-{district_name}-{product_type}-{size}-{price}: {e}")
            await query.answer("Error loading product", show_alert=True)
            return
        finally:
            if conn:
                conn.close()
                
        if not product:
            await query.answer("Product not found", show_alert=True)
            return
            
        product_id = product['id']
        available = product['available']
    else:
        await query.answer("Invalid product selection format", show_alert=True)
        return
    
    # Get user balance
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = %s", (query.from_user.id,))
        user_result = c.fetchone()
        user_balance = user_result['balance'] if user_result else 0.0
        
    except Exception as e:
        logger.error(f"Error loading user balance: {e}")
        await query.answer("Error loading user data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    # Store product selection for purchase
    context.user_data['selected_product_id'] = product_id
    product_dict = {
        'id': product_id,
        'city': city_name,
        'district': district_name,
        'product_type': product_type,
        'size': size,
        'price': price,
        'available': available
    }
    context.user_data['selected_product'] = product_dict
    
    emoji = get_product_emoji(product_type)
    
    # Clean, minimal product details as requested
    msg = f"🏙️ **{city_name}** | 🏘️ **{district_name}**\n\n"
    msg += f"{emoji} **{product_type}** - **{size}**\n\n"
    msg += f"💰 **Price:** **{price:.2f} EUR**\n"
    msg += f"🔢 **Available:** **{available}**\n\n"
    
    # Check if user has sufficient balance
    has_balance = user_balance >= price
    
    # 4-button layout as requested: Pay Now, Apply Discount, Back to Products, Home
    keyboard = [
        [InlineKeyboardButton("💳 Pay Now", callback_data=f"minimalist_pay_options|{product_id}")],
        [InlineKeyboardButton("🎫 Apply Discount Code", callback_data=f"minimalist_discount_code|{product_id}")],
        [InlineKeyboardButton("⬅️ Back to Products", callback_data=f"minimalist_district_select|{city_name}|{district_name}"),
         InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_minimalist_pay_options(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle Pay Now - direct payment processing without intermediate screen"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not params:
        await query.answer("Invalid payment selection", show_alert=True)
        return
    
    product_id = int(params[0])
    product = context.user_data.get('selected_product')
    
    if not product:
        await query.answer("Product selection expired", show_alert=True)
        return
    
    await query.answer("⏳ Processing payment...")
    
    # Check user balance first
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get user balance
        c.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        user_result = c.fetchone()
        user_balance = user_result['balance'] if user_result else 0.0
        product_price = float(product['price'])
        
        if user_balance >= product_price:
            # User has sufficient balance - process payment directly
            await process_minimalist_balance_payment(query, context, product, user_balance)
        else:
            # User doesn't have sufficient balance - show crypto payment options
            await show_minimalist_crypto_options(query, context, product, user_balance)
            
    except Exception as e:
        logger.error(f"Error processing minimalist payment for user {user_id}: {e}")
        await query.answer("Payment error occurred", show_alert=True)
    finally:
        if conn:
            conn.close()

async def process_minimalist_balance_payment(query, context, product, user_balance):
    """Process payment directly using user's balance"""
    user_id = query.from_user.id
    product_price = float(product['price'])
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("BEGIN")
        
        # Reserve the product
        c.execute("""
            UPDATE products 
            SET reserved = reserved + 1 
            WHERE id = %s AND available > reserved
        """, (product['id'],))
        
        if c.rowcount == 0:
            await query.edit_message_text("❌ Sorry, this item was just taken by another user!", parse_mode=None)
            return
        
        # Deduct from user balance
        new_balance = user_balance - product_price
        c.execute("""
            UPDATE users 
            SET balance = %s, total_purchases = total_purchases + 1 
            WHERE user_id = %s
        """, (new_balance, user_id))
        
        # Record the purchase
        c.execute("""
            INSERT INTO purchases (user_id, product_id, price, payment_method, status)
            VALUES (%s, %s, %s, 'balance', 'completed')
        """, (user_id, product['id'], product_price))
        
        # Reduce product availability
        c.execute("""
            UPDATE products 
            SET available = available - 1, reserved = reserved - 1
            WHERE id = %s
        """, (product['id'],))
        
        conn.commit()
        
        # Send success message with product details
        await send_minimalist_success_message(query, context, product, new_balance)
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error processing balance payment: {e}")
        await query.edit_message_text("❌ Payment failed. Please try again.", parse_mode=None)
    finally:
        if conn:
            conn.close()

async def show_minimalist_crypto_options(query, context, product, user_balance):
    """Show crypto payment options using the original working function"""
    from user import SUPPORTED_CRYPTO, format_currency
    from utils import is_currency_supported
    
    # Set up context for basket payment (what handle_select_basket_crypto expects)
    product_price = float(product['price'])
    
    # Create basket-style snapshot for the single product
    basket_snapshot = [{
        'product_id': product['id'],
        'price': product_price,
        'name': product['product_type'],
        'size': product['size'],
        'product_type': product['product_type'],
        'city': product['city'],
        'district': product['district'],
        'original_text': product.get('original_text', '')
    }]
    
    # Set the context variables that handle_select_basket_crypto expects
    context.user_data['basket_pay_snapshot'] = basket_snapshot
    context.user_data['basket_pay_total_eur'] = product_price
    context.user_data['basket_pay_discount_code'] = None  # No discount for direct purchase
    
    # Build crypto buttons using the original working logic
    asset_buttons = []
    row = []
    supported_currencies = {}
    
    # Validate each currency against NOWPayments API (same as original)
    for code, display_name in SUPPORTED_CRYPTO.items():
        if is_currency_supported(code):
            supported_currencies[code] = display_name
        else:
            logger.warning(f"Currency {code} not supported by NOWPayments API")
    
    # If no currencies are supported, show error
    if not supported_currencies:
        logger.error("No supported currencies found from NOWPayments API")
        msg = "❌ No payment methods available at the moment. Please try again later."
        back_callback = f"minimalist_district_select|{product['city']}|{product['district']}"
        kb = [[InlineKeyboardButton("⬅️ Back", callback_data=back_callback)]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=None)
        return
    
    # Build buttons for supported currencies (same layout as original)
    for code, display_name in supported_currencies.items():
        row.append(InlineKeyboardButton(display_name, callback_data=f"select_basket_crypto|{code}"))
        if len(row) >= 3:  # 3 buttons per row like original
            asset_buttons.append(row)
            row = []
    if row: 
        asset_buttons.append(row)

    # Add back button - use the consistent navigation
    back_callback = f"minimalist_district_select|{product['city']}|{product['district']}"
    asset_buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=back_callback)])

    # Use the original message format
    amount_str = format_currency(product_price)
    prompt_msg = f"Choose crypto to pay {amount_str} EUR for your items:"

    await query.edit_message_text(prompt_msg, reply_markup=InlineKeyboardMarkup(asset_buttons), parse_mode=None)

async def send_minimalist_success_message(query, context, product, new_balance):
    """Send success message after payment"""
    emoji = get_product_emoji(product['product_type'])
    
    msg = f"✅ **Payment Successful!**\n\n"
    msg += f"{emoji} **Product:** {product['product_type']} {product['size']}\n"
    msg += f"💰 **Paid:** {product['price']:.2f} EUR\n"
    msg += f"💳 **New Balance:** {new_balance:.2f} EUR\n\n"
    msg += f"📦 **Your Product Details:**\n"
    msg += f"🏙️ **Location:** {product['city']} → {product['district']}\n"
    msg += f"📱 **Order ID:** #{product['id']}\n\n"
    msg += "**Thank you for your purchase!** 🎉\n"
    msg += "Your product is ready for pickup at the specified location."
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Shop More", callback_data="minimalist_shop")],
        [InlineKeyboardButton("🏠 Home", callback_data="minimalist_home")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def handle_minimalist_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle discount code application - redirect to existing system"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not params:
        await query.answer("Invalid discount request", show_alert=True)
        return
    
    product_id = int(params[0])
    product = context.user_data.get('selected_product')
    
    if not product:
        await query.answer("Product selection expired", show_alert=True)
        return
    
    # First, we need to set up the payment context that the existing discount system expects
    # The existing system expects single_item_pay_snapshot to be set
    
    # Convert to the format expected by the existing payment system
    city_name = product['city']
    district_name = product['district']
    product_type = product['product_type'] 
    size = product['size']
    price = str(product['price'])
    
    # Find city_id and district_id from the names
    city_id = None
    district_id = None
    
    # Import the existing data structures
    from utils import CITIES, DISTRICTS
    
    # Find city_id
    for c_id, c_name in CITIES.items():
        if c_name == city_name:
            city_id = c_id
            break
    
    # Find district_id
    if city_id:
        for d_id, d_name in DISTRICTS.get(city_id, {}).items():
            if d_name == district_name:
                district_id = d_id
                break
    
    if not city_id or not district_id:
        await query.answer("Location data error", show_alert=True)
        return
    
    # Set up the payment context that the existing discount system expects
    context.user_data['single_item_pay_back_params'] = [city_id, district_id, product_type, size, price]
    context.user_data['single_item_pay_final_eur'] = float(price)
    context.user_data['single_item_pay_snapshot'] = product
    
    # Use the existing discount system
    from user import handle_apply_discount_single_pay
    
    # Call the existing discount handler
    await handle_apply_discount_single_pay(update, context, params)


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
            SELECT balance, total_purchases
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
            member_since = "Member"  # Since we don't have created_at column
        
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
