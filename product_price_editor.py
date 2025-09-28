# --- START OF FILE product_price_editor.py ---

import logging
import sqlite3
from decimal import Decimal
from typing import List, Dict, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils import (
    get_db_connection, send_message_with_retry, is_primary_admin,
    format_currency
)

logger = logging.getLogger(__name__)

# --- Product Price Management Functions ---

def get_products_for_price_editing(limit=20, offset=0, search_term=None, city=None, category=None):
    """Get products available for price editing with filters"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Build query with filters
        query = """
            SELECT id, city, district, product_type, size, price, available, 
                   created_at, last_price_update
            FROM products 
            WHERE 1=1
        """
        params = []
        
        if search_term:
            query += " AND (product_type LIKE ? OR city LIKE ? OR district LIKE ?)"
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        if city:
            query += " AND city = ?"
            params.append(city)
        
        if category:
            query += " AND product_type = ?"
            params.append(category)
        
        query += " ORDER BY city, district, product_type, price DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        c.execute(query, params)
        products = c.fetchall()
        
        # Get total count for pagination
        count_query = "SELECT COUNT(*) FROM products WHERE 1=1"
        count_params = []
        
        if search_term:
            count_query += " AND (product_type LIKE ? OR city LIKE ? OR district LIKE ?)"
            count_params.extend([search_pattern, search_pattern, search_pattern])
        
        if city:
            count_query += " AND city = ?"
            count_params.append(city)
        
        if category:
            count_query += " AND product_type = ?"
            count_params.append(category)
        
        c.execute(count_query, count_params)
        result = c.fetchone()
        total_count = result['count']
        
        return products, total_count
        
    except Exception as e:
        logger.error(f"Error getting products for price editing: {e}")
        return [], 0
    finally:
        if conn:
            conn.close()

def update_product_price(product_id: int, new_price: float, admin_user_id: int) -> bool:
    """Update product price and log the change"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get current product info
        c.execute("SELECT price, product_type, city, district FROM products WHERE id = ?", (product_id,))
        product = c.fetchone()
        
        if not product:
            logger.error(f"Product {product_id} not found for price update")
            return False
        
        old_price = product['price']
        
        # Update the price
        c.execute("""
            UPDATE products 
            SET price = ?, last_price_update = ?
            WHERE id = ?
        """, (new_price, datetime.now().isoformat(), product_id))
        
        # Log the price change
        c.execute("""
            INSERT INTO price_change_log 
            (product_id, old_price, new_price, changed_by_admin_id, change_reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            product_id, 
            old_price, 
            new_price, 
            admin_user_id, 
            'Admin price update',
            datetime.now().isoformat()
        ))
        
        conn.commit()
        
        logger.info(f"Price updated for product {product_id}: ${old_price} → ${new_price} by admin {admin_user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating product price: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def init_price_editor_tables():
    """Initialize price change logging table"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Price change log table
        c.execute("""
            CREATE TABLE IF NOT EXISTS price_change_log (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                old_price REAL NOT NULL,
                new_price REAL NOT NULL,
                changed_by_admin_id BIGINT NOT NULL,
                change_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)
        
        # Note: last_price_update column will be added later when needed to avoid startup delays
        logger.info("✅ Price editor tables initialized (column addition skipped for PostgreSQL)")
        
        conn.commit()
        logger.info("Price editor tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing price editor tables: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# --- Admin Handlers ---

async def handle_product_price_editor_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main product price editor menu"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get price statistics
        c.execute("""
            SELECT 
                COUNT(*) as total_products,
                MIN(price) as lowest_price,
                MAX(price) as highest_price,
                AVG(price) as average_price,
                COUNT(DISTINCT city) as cities,
                COUNT(DISTINCT product_type) as categories
            FROM products
        """)
        stats = c.fetchone()
        
        # Get recent price changes
        c.execute("""
            SELECT COUNT(*) as recent_changes
            FROM price_change_log 
            WHERE created_at >= datetime('now', '-7 days')
        """)
        recent_changes = c.fetchone()['recent_changes']
        
    except Exception as e:
        logger.error(f"Error loading price editor menu: {e}")
        stats = None
        recent_changes = 0
    finally:
        if conn:
            conn.close()
    
    msg = "💰 **Product Price Editor** 💰\n\n"
    msg += "**Manage prices for all your existing products!**\n\n"
    
    if stats:
        msg += f"📊 **Price Overview:**\n"
        msg += f"• Total Products: {stats['total_products']:,}\n"
        msg += f"• Price Range: ${stats['lowest_price']:.2f} - ${stats['highest_price']:.2f}\n"
        msg += f"• Average Price: ${stats['average_price']:.2f}\n"
        msg += f"• Cities: {stats['cities']} | Categories: {stats['categories']}\n\n"
    
    msg += f"📈 **Recent Changes:** {recent_changes} price updates in last 7 days\n\n"
    msg += "**Choose your price editing method:**"
    
    keyboard = [
        [InlineKeyboardButton("🌐 Bulk Price Update (All Locations)", callback_data="price_bulk_all_locations")],
        [InlineKeyboardButton("🏙️ Edit by City", callback_data="price_edit_by_city")],
        [InlineKeyboardButton("🏘️ Edit by City & District", callback_data="price_edit_by_city_district")],
        [InlineKeyboardButton("📋 Price Change History", callback_data="price_change_history")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_bulk_all_locations(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Bulk price update for all locations - shows product types and sizes"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all unique product types and sizes with their current price ranges
        c.execute("""
            SELECT 
                product_type,
                size,
                COUNT(*) as total_products,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price,
                COUNT(DISTINCT city) as cities_count,
                COUNT(DISTINCT district) as districts_count
            FROM products 
            GROUP BY product_type, size
            ORDER BY product_type, size
        """)
        product_variants = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading bulk price options: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not product_variants:
        await query.edit_message_text(
            "❌ **No Products Found**\n\nNo products available for bulk price updates.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="product_price_editor_menu")]]),
            parse_mode='Markdown'
        )
        return
    
    msg = "🌐 **Bulk Price Update (All Locations)**\n\n"
    msg += "**Select a product type and size to update prices across ALL cities and districts:**\n\n"
    
    keyboard = []
    for variant in product_variants[:15]:  # Limit to 15 to avoid message length issues
        product_type = variant['product_type']
        size = variant['size']
        total = variant['total_products']
        min_price = variant['min_price']
        max_price = variant['max_price']
        cities = variant['cities_count']
        districts = variant['districts_count']
        
        # Create button text with key info
        button_text = f"{product_type} {size} ({total} items, ${min_price:.2f}-${max_price:.2f})"
        if len(button_text) > 60:  # Telegram button limit
            button_text = f"{product_type} {size} ({total} items)"
        
        callback_data = f"price_bulk_select|{product_type}|{size}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Add navigation buttons
    keyboard.append([InlineKeyboardButton("⬅️ Back to Price Editor", callback_data="product_price_editor_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_bulk_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show bulk price update form for selected product type and size"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 2:
        await query.answer("Invalid selection", show_alert=True)
        return
    
    product_type = params[0]
    size = params[1]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get detailed info about this product variant
        c.execute("""
            SELECT 
                COUNT(*) as total_products,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price,
                COUNT(DISTINCT city) as cities_count,
                COUNT(DISTINCT district) as districts_count,
                SUM(available) as total_stock
            FROM products 
            WHERE product_type = %s AND size = %s
        """, (product_type, size))
        stats = c.fetchone()
        
        # Get sample locations
        c.execute("""
            SELECT city, district, price, available
            FROM products 
            WHERE product_type = %s AND size = %s
            ORDER BY city, district
            LIMIT 5
        """, (product_type, size))
        sample_products = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading bulk price details: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    # Store selection for price input
    context.user_data['bulk_price_product_type'] = product_type
    context.user_data['bulk_price_size'] = size
    context.user_data['state'] = 'awaiting_bulk_price'
    
    msg = f"💰 **Bulk Price Update**\n\n"
    msg += f"**Product:** {product_type} {size}\n"
    msg += f"**Total Products:** {stats['total_products']} items\n"
    msg += f"**Current Price Range:** ${stats['min_price']:.2f} - ${stats['max_price']:.2f}\n"
    msg += f"**Average Price:** ${stats['avg_price']:.2f}\n"
    msg += f"**Locations:** {stats['cities_count']} cities, {stats['districts_count']} districts\n"
    msg += f"**Total Stock:** {stats['total_stock']} units\n\n"
    
    msg += "📍 **Sample Locations:**\n"
    for product in sample_products:
        msg += f"• {product['city']} → {product['district']}: ${product['price']:.2f} ({product['available']} units)\n"
    
    if len(sample_products) < stats['total_products']:
        msg += f"... and {stats['total_products'] - len(sample_products)} more locations\n"
    
    msg += "\n💡 **Price Suggestions:**\n"
    avg_price = stats['avg_price']
    msg += f"• Current Average: ${avg_price:.2f}\n"
    msg += f"• +10%: ${avg_price * 1.10:.2f}\n"
    msg += f"• +5%: ${avg_price * 1.05:.2f}\n"
    msg += f"• -5%: ${avg_price * 0.95:.2f}\n"
    msg += f"• -10%: ${avg_price * 0.90:.2f}\n\n"
    
    msg += "**Enter the new price to apply to ALL locations:**"
    
    keyboard = [
        [InlineKeyboardButton(f"💰 ${avg_price * 1.10:.2f} (+10%)", callback_data=f"price_bulk_apply|{product_type}|{size}|{avg_price * 1.10:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 1.05:.2f} (+5%)", callback_data=f"price_bulk_apply|{product_type}|{size}|{avg_price * 1.05:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 0.95:.2f} (-5%)", callback_data=f"price_bulk_apply|{product_type}|{size}|{avg_price * 0.95:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 0.90:.2f} (-10%)", callback_data=f"price_bulk_apply|{product_type}|{size}|{avg_price * 0.90:.2f}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="price_bulk_all_locations")],
        [InlineKeyboardButton("⬅️ Back", callback_data="price_bulk_all_locations")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_bulk_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Apply bulk price update"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 3:
        await query.answer("Invalid parameters", show_alert=True)
        return
    
    product_type = params[0]
    size = params[1]
    new_price = float(params[2])
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get current products to update
        c.execute("""
            SELECT id, city, district, price 
            FROM products 
            WHERE product_type = %s AND size = %s
        """, (product_type, size))
        products_to_update = c.fetchall()
        
        if not products_to_update:
            await query.answer("No products found to update", show_alert=True)
            return
        
        # Update all prices
        c.execute("""
            UPDATE products 
            SET price = %s, last_price_update = CURRENT_TIMESTAMP
            WHERE product_type = %s AND size = %s
        """, (new_price, product_type, size))
        
        updated_count = c.rowcount
        
        # Log the bulk price change
        for product in products_to_update:
            c.execute("""
                INSERT INTO price_change_log 
                (product_id, old_price, new_price, changed_by_admin_id, change_reason, created_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                product['id'], 
                product['price'], 
                new_price, 
                query.from_user.id,
                f"Bulk update: {product_type} {size}"
            ))
        
        conn.commit()
        
        msg = f"✅ **Bulk Price Update Successful!**\n\n"
        msg += f"**Product:** {product_type} {size}\n"
        msg += f"**New Price:** ${new_price:.2f}\n"
        msg += f"**Updated Products:** {updated_count} items\n\n"
        msg += f"📍 **Locations Updated:**\n"
        
        # Show sample of updated locations
        for i, product in enumerate(products_to_update[:5]):
            old_price = product['price']
            change = ((new_price - old_price) / old_price) * 100
            change_symbol = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            msg += f"• {product['city']} → {product['district']}: ${old_price:.2f} → ${new_price:.2f} {change_symbol}\n"
        
        if len(products_to_update) > 5:
            msg += f"... and {len(products_to_update) - 5} more locations\n"
        
        msg += f"\n🎯 **All prices updated successfully!**"
        
    except Exception as e:
        logger.error(f"Error applying bulk price update: {e}")
        if conn:
            conn.rollback()
        msg = "❌ **Error updating prices.** Please try again."
        await query.answer("Update failed", show_alert=True)
    finally:
        if conn:
            conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🌐 Update Another Product", callback_data="price_bulk_all_locations")],
        [InlineKeyboardButton("🏠 Back to Price Editor", callback_data="product_price_editor_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_edit_by_city(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Edit prices by city - shows all cities"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all cities with product counts and price ranges
        c.execute("""
            SELECT 
                city,
                COUNT(*) as total_products,
                COUNT(DISTINCT product_type) as product_types,
                COUNT(DISTINCT district) as districts,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price
            FROM products 
            GROUP BY city
            ORDER BY city
        """)
        cities = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading cities for price editing: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not cities:
        await query.edit_message_text(
            "❌ **No Cities Found**\n\nNo cities available for price editing.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="product_price_editor_menu")]]),
            parse_mode='Markdown'
        )
        return
    
    msg = "🏙️ **Edit Prices by City**\n\n"
    msg += "**Select a city to edit prices for all products in that city:**\n\n"
    
    keyboard = []
    for city in cities:
        city_name = city['city']
        total = city['total_products']
        types = city['product_types']
        districts = city['districts']
        min_price = city['min_price']
        max_price = city['max_price']
        
        # Create button text with key info
        button_text = f"🏙️ {city_name} ({total} items, {districts} districts)"
        callback_data = f"price_city_select|{city_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Add navigation buttons
    keyboard.append([InlineKeyboardButton("⬅️ Back to Price Editor", callback_data="product_price_editor_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_edit_by_city_district(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Edit prices by city and district - shows cities first"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all cities with district counts
        c.execute("""
            SELECT 
                city,
                COUNT(DISTINCT district) as districts,
                COUNT(*) as total_products,
                MIN(price) as min_price,
                MAX(price) as max_price
            FROM products 
            GROUP BY city
            ORDER BY city
        """)
        cities = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading cities for district editing: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not cities:
        await query.edit_message_text(
            "❌ **No Cities Found**\n\nNo cities available for price editing.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="product_price_editor_menu")]]),
            parse_mode='Markdown'
        )
        return
    
    msg = "🏘️ **Edit Prices by City & District**\n\n"
    msg += "**First, select a city to see its districts:**\n\n"
    
    keyboard = []
    for city in cities:
        city_name = city['city']
        districts = city['districts']
        total = city['total_products']
        
        button_text = f"🏙️ {city_name} ({districts} districts, {total} items)"
        callback_data = f"price_city_district_select|{city_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Add navigation buttons
    keyboard.append([InlineKeyboardButton("⬅️ Back to Price Editor", callback_data="product_price_editor_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_search_products(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Search products for price editing"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    # Set state for search input
    context.user_data['state'] = 'awaiting_price_search'
    
    msg = "🔍 **Search Products for Price Editing**\n\n"
    msg += "**How to search:**\n\n"
    msg += "📝 **Search by:**\n"
    msg += "• Product name/type (e.g., 'iPhone', 'laptop')\n"
    msg += "• City name (e.g., 'New York', 'London')\n"
    msg += "• District name (e.g., 'Downtown', 'Mall')\n\n"
    msg += "🔍 **Search Tips:**\n"
    msg += "• Use partial names (e.g., 'phone' finds 'iPhone')\n"
    msg += "• Search is case-insensitive\n"
    msg += "• Leave empty to see all products\n\n"
    msg += "**Type your search term:**"
    
    keyboard = [
        [InlineKeyboardButton("📋 Show All Products", callback_data="price_show_all_products")],
        [InlineKeyboardButton("❌ Cancel", callback_data="product_price_editor_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_edit_by_city(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Edit prices by city"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get cities with product counts and price ranges
        c.execute("""
            SELECT city, 
                   COUNT(*) as product_count,
                   MIN(price) as min_price,
                   MAX(price) as max_price,
                   AVG(price) as avg_price
            FROM products 
            GROUP BY city 
            ORDER BY product_count DESC
        """)
        cities = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error getting cities for price editing: {e}")
        cities = []
    finally:
        if conn:
            conn.close()
    
    msg = "🏙️ **Edit Prices by City**\n\n"
    msg += "Select a city to edit product prices:\n\n"
    
    keyboard = []
    for city in cities:
        city_info = f"{city['city']} ({city['product_count']} products)"
        price_range = f"${city['min_price']:.2f}-${city['max_price']:.2f}"
        button_text = f"{city_info} - {price_range}"
        
        keyboard.append([InlineKeyboardButton(
            button_text[:60],  # Truncate if too long
            callback_data=f"price_city_products|{city['city']}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Price Editor", callback_data="product_price_editor_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_edit_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Edit prices by product category"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get categories with product counts and price ranges
        c.execute("""
            SELECT product_type, 
                   COUNT(*) as product_count,
                   MIN(price) as min_price,
                   MAX(price) as max_price,
                   AVG(price) as avg_price
            FROM products 
            GROUP BY product_type 
            ORDER BY product_count DESC
        """)
        categories = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error getting categories for price editing: {e}")
        categories = []
    finally:
        if conn:
            conn.close()
    
    msg = "🏷️ **Edit Prices by Category**\n\n"
    msg += "Select a product category to edit prices:\n\n"
    
    keyboard = []
    for category in categories:
        cat_info = f"{category['product_type']} ({category['product_count']} items)"
        price_range = f"${category['min_price']:.2f}-${category['max_price']:.2f}"
        avg_price = f"avg ${category['avg_price']:.2f}"
        button_text = f"{cat_info} - {price_range} ({avg_price})"
        
        keyboard.append([InlineKeyboardButton(
            button_text[:60],  # Truncate if too long
            callback_data=f"price_category_products|{category['product_type']}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Price Editor", callback_data="product_price_editor_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_search_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle price search input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get("state") != "awaiting_price_search":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a search term.", parse_mode=None)
        return
    
    search_term = update.message.text.strip()
    
    if len(search_term) < 2:
        await send_message_with_retry(context.bot, chat_id, "❌ Search term must be at least 2 characters.", parse_mode=None)
        return
    
    # Store search term and show results
    context.user_data['price_search_term'] = search_term
    context.user_data.pop('state', None)
    
    # Get search results
    products, total_count = get_products_for_price_editing(search_term=search_term)
    
    if not products:
        msg = f"🔍 **No Products Found**\n\n"
        msg += f"No products found matching '{search_term}'.\n\n"
        msg += "**Try searching for:**\n"
        msg += "• Product types (iPhone, laptop, etc.)\n"
        msg += "• Cities or districts\n"
        msg += "• Partial names\n\n"
        msg += "Or browse all products instead."
        
        keyboard = [
            [InlineKeyboardButton("📋 Show All Products", callback_data="price_show_all_products")],
            [InlineKeyboardButton("🔍 Search Again", callback_data="price_search_products")],
            [InlineKeyboardButton("⬅️ Back", callback_data="product_price_editor_menu")]
        ]
    else:
        msg = f"🔍 **Search Results: '{search_term}'**\n\n"
        msg += f"Found {total_count} products. Showing first {len(products)}:\n\n"
        
        keyboard = []
        for product in products:
            product_name = f"{product['city']} → {product['product_type']} {product['size']}"
            price_text = f"${product['price']:.2f}"
            stock_text = f"({product['available']} in stock)"
            
            button_text = f"{product_name[:30]} - {price_text} {stock_text}"
            keyboard.append([InlineKeyboardButton(
                button_text[:60],
                callback_data=f"price_edit_product|{product['id']}"
            )])
        
        if total_count > len(products):
            keyboard.append([InlineKeyboardButton(f"📄 Show More ({total_count - len(products)} remaining)", 
                callback_data=f"price_search_more|{search_term}")])
        
        keyboard.extend([
            [InlineKeyboardButton("🔍 New Search", callback_data="price_search_products")],
            [InlineKeyboardButton("⬅️ Back", callback_data="product_price_editor_menu")]
        ])
    
    await send_message_with_retry(context.bot, chat_id, msg, 
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Edit specific product price"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params:
        await query.answer("Invalid product ID", show_alert=True)
        return
    
    product_id = int(params[0])
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get product details
        c.execute("""
            SELECT id, city, district, product_type, size, price, available, 
                   created_at, last_price_update
            FROM products 
            WHERE id = ?
        """, (product_id,))
        product = c.fetchone()
        
        if not product:
            await query.answer("Product not found", show_alert=True)
            return
        
        # Get price history for this product
        c.execute("""
            SELECT old_price, new_price, created_at, change_reason
            FROM price_change_log 
            WHERE product_id = ?
            ORDER BY created_at DESC
            LIMIT 3
        """, (product_id,))
        price_history = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading product for price editing: {e}")
        await query.answer("Error loading product", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    # Store product ID for price input
    context.user_data['price_edit_product_id'] = product_id
    context.user_data['state'] = 'awaiting_new_price'
    
    msg = f"💰 **Edit Product Price**\n\n"
    msg += f"**Product:** {product['city']} → {product['district']}\n"
    msg += f"**Type:** {product['product_type']} {product['size']}\n"
    msg += f"**Current Price:** ${product['price']:.2f}\n"
    msg += f"**Stock:** {product['available']} units\n\n"
    
    if price_history:
        msg += f"📈 **Recent Price Changes:**\n"
        for change in price_history:
            change_date = change['created_at'][:10] if change['created_at'] else "Unknown"
            msg += f"• {change_date}: ${change['old_price']:.2f} → ${change['new_price']:.2f}\n"
        msg += "\n"
    
    msg += f"💡 **Price Suggestions:**\n"
    current_price = product['price']
    msg += f"• 5% increase: ${current_price * 1.05:.2f}\n"
    msg += f"• 10% increase: ${current_price * 1.10:.2f}\n"
    msg += f"• 5% decrease: ${current_price * 0.95:.2f}\n"
    msg += f"• 10% decrease: ${current_price * 0.90:.2f}\n\n"
    msg += "**Enter the new price (numbers only):**"
    
    keyboard = [
        [InlineKeyboardButton(f"💰 ${current_price * 1.05:.2f} (+5%)", callback_data=f"price_set_quick|{product_id}|{current_price * 1.05:.2f}")],
        [InlineKeyboardButton(f"💰 ${current_price * 1.10:.2f} (+10%)", callback_data=f"price_set_quick|{product_id}|{current_price * 1.10:.2f}")],
        [InlineKeyboardButton(f"💰 ${current_price * 0.95:.2f} (-5%)", callback_data=f"price_set_quick|{product_id}|{current_price * 0.95:.2f}")],
        [InlineKeyboardButton(f"💰 ${current_price * 0.90:.2f} (-10%)", callback_data=f"price_set_quick|{product_id}|{current_price * 0.90:.2f}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="price_search_products")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_new_price_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new price input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get("state") != "awaiting_new_price":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid price.", parse_mode=None)
        return
    
    price_input = update.message.text.strip().replace('$', '').replace(',', '')
    
    try:
        new_price = float(price_input)
        if new_price <= 0:
            await send_message_with_retry(context.bot, chat_id, "❌ Price must be greater than 0.", parse_mode=None)
            return
        
        if new_price > 999999:
            await send_message_with_retry(context.bot, chat_id, "❌ Price too high. Maximum is $999,999.", parse_mode=None)
            return
        
    except ValueError:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid number (e.g., 19.99).", parse_mode=None)
        return
    
    product_id = context.user_data.get('price_edit_product_id')
    if not product_id:
        await send_message_with_retry(context.bot, chat_id, "❌ Session expired. Please try again.", parse_mode=None)
        return
    
    # Update the price
    success = update_product_price(product_id, new_price, user_id)
    
    # Clear state
    context.user_data.pop('state', None)
    context.user_data.pop('price_edit_product_id', None)
    
    if success:
        # Get updated product info
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT city, product_type, size, price FROM products WHERE id = ?", (product_id,))
            product = c.fetchone()
            
            msg = f"✅ **Price Updated Successfully!**\n\n"
            msg += f"**Product:** {product['city']} → {product['product_type']} {product['size']}\n"
            msg += f"**New Price:** ${product['price']:.2f}\n\n"
            msg += "The price has been updated and is now live!"
            
        except Exception as e:
            msg = f"✅ **Price Updated Successfully!**\n\n"
            msg += f"**New Price:** ${new_price:.2f}\n\n"
            msg += "The price has been updated and is now live!"
        finally:
            if conn:
                conn.close()
    else:
        msg = "❌ **Error updating price.** Please try again."
    
    keyboard = [
        [InlineKeyboardButton("💰 Edit Another Product", callback_data="price_search_products")],
        [InlineKeyboardButton("🏠 Back to Price Editor", callback_data="product_price_editor_menu")]
    ]
    
    await send_message_with_retry(context.bot, chat_id, msg, 
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_set_quick(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Set price using quick percentage buttons"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 2:
        await query.answer("Invalid parameters", show_alert=True)
        return
    
    product_id = int(params[0])
    new_price = float(params[1])
    
    # Update the price
    success = update_product_price(product_id, new_price, query.from_user.id)
    
    if success:
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT city, product_type, size FROM products WHERE id = ?", (product_id,))
            product = c.fetchone()
            
            msg = f"✅ **Price Updated Successfully!**\n\n"
            msg += f"**Product:** {product['city']} → {product['product_type']} {product['size']}\n"
            msg += f"**New Price:** ${new_price:.2f}\n\n"
            msg += "The price has been updated instantly!"
            
        except Exception as e:
            msg = f"✅ **Price Updated Successfully!**\n\n"
            msg += f"**New Price:** ${new_price:.2f}\n\n"
            msg += "The price has been updated instantly!"
        finally:
            if conn:
                conn.close()
        
        await query.answer("Price updated!", show_alert=False)
    else:
        msg = "❌ **Error updating price.** Please try again."
        await query.answer("Update failed", show_alert=True)
    
    keyboard = [
        [InlineKeyboardButton("💰 Edit Another Product", callback_data="price_search_products")],
        [InlineKeyboardButton("🏠 Back to Price Editor", callback_data="product_price_editor_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_show_all_products(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show all products for price editing"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    page = int(params[0]) if params and params[0].isdigit() else 0
    products_per_page = 10
    
    products, total_count = get_products_for_price_editing(
        limit=products_per_page, 
        offset=page * products_per_page
    )
    
    if not products:
        msg = "📋 **No Products Available**\n\n"
        msg += "No products found in the database.\n"
        msg += "Add products first before editing prices."
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="product_price_editor_menu")]]
    else:
        msg = f"📋 **All Products** (Page {page + 1})\n\n"
        msg += f"Showing {len(products)} of {total_count} total products:\n\n"
        
        keyboard = []
        for product in products:
            product_name = f"{product['city']} → {product['product_type']} {product['size']}"
            price_text = f"${product['price']:.2f}"
            stock_text = f"({product['available']} stock)"
            
            button_text = f"{product_name[:25]} - {price_text} {stock_text}"
            keyboard.append([InlineKeyboardButton(
                button_text[:60],
                callback_data=f"price_edit_product|{product['id']}"
            )])
        
        # Pagination controls
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"price_show_all_products|{page-1}"))
        
        if (page + 1) * products_per_page < total_count:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"price_show_all_products|{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🏠 Back to Price Editor", callback_data="product_price_editor_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_change_history(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show price change history"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get recent price changes with product info
        c.execute("""
            SELECT pcl.old_price, pcl.new_price, pcl.created_at, pcl.change_reason,
                   p.city, p.district, p.product_type, p.size, pcl.changed_by_admin_id
            FROM price_change_log pcl
            JOIN products p ON pcl.product_id = p.id
            ORDER BY pcl.created_at DESC
            LIMIT 20
        """)
        changes = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error getting price change history: {e}")
        changes = []
    finally:
        if conn:
            conn.close()
    
    msg = "📋 **Price Change History**\n\n"
    
    if not changes:
        msg += "No price changes recorded yet.\n\n"
        msg += "Price changes will appear here when admins update product prices."
    else:
        msg += f"Last {len(changes)} price changes:\n\n"
        
        for change in changes:
            try:
                date_str = datetime.fromisoformat(change['created_at'].replace('Z', '+00:00')).strftime('%m-%d %H:%M')
            except:
                date_str = "Recent"
            
            price_change = change['new_price'] - change['old_price']
            change_emoji = "📈" if price_change > 0 else "📉" if price_change < 0 else "➡️"
            
            product_name = f"{change['city']} → {change['product_type']} {change['size']}"
            msg += f"{change_emoji} **{product_name[:30]}**\n"
            msg += f"   ${change['old_price']:.2f} → ${change['new_price']:.2f} ({date_str})\n"
            msg += f"   Admin: {change['changed_by_admin_id']}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh History", callback_data="price_change_history")],
        [InlineKeyboardButton("💰 Edit More Prices", callback_data="price_search_products")],
        [InlineKeyboardButton("⬅️ Back to Price Editor", callback_data="product_price_editor_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_bulk_updates(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle bulk price updates"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    msg = "📊 **Bulk Price Updates**\n\n"
    msg += "Apply price changes to multiple products at once:\n\n"
    msg += "**Bulk Update Options:**\n"
    msg += "• Increase all prices by percentage\n"
    msg += "• Decrease all prices by percentage\n"
    msg += "• Set minimum price threshold\n"
    msg += "• Round prices to nearest dollar\n"
    msg += "• Apply category-specific changes\n\n"
    msg += "⚠️ **Warning:** Bulk updates affect many products at once!"
    
    keyboard = [
        [InlineKeyboardButton("📈 Increase All Prices", callback_data="price_bulk_increase")],
        [InlineKeyboardButton("📉 Decrease All Prices", callback_data="price_bulk_decrease")],
        [InlineKeyboardButton("🎯 Set Minimum Price", callback_data="price_set_minimum")],
        [InlineKeyboardButton("🔄 Round All Prices", callback_data="price_round_all")],
        [InlineKeyboardButton("🏷️ Category Bulk Update", callback_data="price_category_bulk")],
        [InlineKeyboardButton("⬅️ Back to Price Editor", callback_data="product_price_editor_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_bulk_increase(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Bulk increase all prices"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    msg = "📈 **Bulk Price Increase**\n\n"
    msg += "Increase all product prices by a percentage:\n\n"
    msg += "**Common Increases:**\n"
    msg += "• 5% - Small adjustment\n"
    msg += "• 10% - Standard increase\n"
    msg += "• 15% - Significant increase\n"
    msg += "• 20% - Major price adjustment\n\n"
    msg += "⚠️ **This will affect ALL products!**"
    
    keyboard = [
        [InlineKeyboardButton("📈 +5%", callback_data="price_bulk_apply|increase|5")],
        [InlineKeyboardButton("📈 +10%", callback_data="price_bulk_apply|increase|10")],
        [InlineKeyboardButton("📈 +15%", callback_data="price_bulk_apply|increase|15")],
        [InlineKeyboardButton("📈 +20%", callback_data="price_bulk_apply|increase|20")],
        [InlineKeyboardButton("🔧 Custom %", callback_data="price_bulk_custom|increase")],
        [InlineKeyboardButton("⬅️ Back", callback_data="price_bulk_updates")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_bulk_decrease(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Bulk decrease all prices"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    msg = "📉 **Bulk Price Decrease**\n\n"
    msg += "Decrease all product prices by a percentage:\n\n"
    msg += "**Common Decreases:**\n"
    msg += "• 5% - Small discount\n"
    msg += "• 10% - Standard sale\n"
    msg += "• 15% - Big sale\n"
    msg += "• 20% - Major clearance\n\n"
    msg += "⚠️ **This will affect ALL products!**"
    
    keyboard = [
        [InlineKeyboardButton("📉 -5%", callback_data="price_bulk_apply|decrease|5")],
        [InlineKeyboardButton("📉 -10%", callback_data="price_bulk_apply|decrease|10")],
        [InlineKeyboardButton("📉 -15%", callback_data="price_bulk_apply|decrease|15")],
        [InlineKeyboardButton("📉 -20%", callback_data="price_bulk_apply|decrease|20")],
        [InlineKeyboardButton("🔧 Custom %", callback_data="price_bulk_custom|decrease")],
        [InlineKeyboardButton("⬅️ Back", callback_data="price_bulk_updates")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_bulk_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Apply bulk price change"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 2:
        await query.answer("Invalid parameters", show_alert=True)
        return
    
    action = params[0]  # 'increase' or 'decrease'
    percentage = float(params[1])
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all products
        c.execute("SELECT id, price, city, product_type FROM products")
        products = c.fetchall()
        
        if not products:
            await query.answer("No products found", show_alert=True)
            return
        
        # Calculate new prices
        multiplier = (100 + percentage) / 100 if action == 'increase' else (100 - percentage) / 100
        updated_count = 0
        
        for product in products:
            old_price = product['price']
            new_price = round(old_price * multiplier, 2)
            
            # Update price
            c.execute("UPDATE products SET price = ?, last_price_update = ? WHERE id = ?", 
                     (new_price, datetime.now().isoformat(), product['id']))
            
            # Log change
            c.execute("""
                INSERT INTO price_change_log 
                (product_id, old_price, new_price, changed_by_admin_id, change_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                product['id'], old_price, new_price, query.from_user.id,
                f"Bulk {action} {percentage}%", datetime.now().isoformat()
            ))
            
            updated_count += 1
        
        conn.commit()
        
        action_text = "increased" if action == 'increase' else "decreased"
        
        msg = f"✅ **Bulk Price Update Complete!**\n\n"
        msg += f"**Action:** {action_text.title()} by {percentage}%\n"
        msg += f"**Products Updated:** {updated_count:,}\n\n"
        msg += f"All product prices have been {action_text} successfully!"
        
        keyboard = [
            [InlineKeyboardButton("📊 View Changes", callback_data="price_change_history")],
            [InlineKeyboardButton("💰 More Bulk Updates", callback_data="price_bulk_updates")],
            [InlineKeyboardButton("🏠 Back to Price Editor", callback_data="product_price_editor_menu")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        await query.answer(f"{updated_count} prices {action_text}!", show_alert=False)
        
    except Exception as e:
        logger.error(f"Error applying bulk price update: {e}")
        await query.answer("Bulk update failed", show_alert=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

async def handle_price_city_products(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show products in specific city for price editing"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params:
        await query.answer("Invalid city", show_alert=True)
        return
    
    city = params[0]
    products, total_count = get_products_for_price_editing(city=city, limit=15)
    
    msg = f"🏙️ **Products in {city}**\n\n"
    msg += f"Found {total_count} products in {city}:\n\n"
    
    keyboard = []
    for product in products:
        product_name = f"{product['district']} → {product['product_type']} {product['size']}"
        price_text = f"${product['price']:.2f}"
        stock_text = f"({product['available']} stock)"
        
        button_text = f"{product_name[:25]} - {price_text} {stock_text}"
        keyboard.append([InlineKeyboardButton(
            button_text[:60],
            callback_data=f"price_edit_product|{product['id']}"
        )])
    
    keyboard.extend([
        [InlineKeyboardButton("📊 Bulk Update City", callback_data=f"price_bulk_city|{city}")],
        [InlineKeyboardButton("⬅️ Back to Cities", callback_data="price_edit_by_city")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_category_products(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show products in specific category for price editing"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params:
        await query.answer("Invalid category", show_alert=True)
        return
    
    category = params[0]
    products, total_count = get_products_for_price_editing(category=category, limit=15)
    
    msg = f"🏷️ **{category} Products**\n\n"
    msg += f"Found {total_count} {category} products:\n\n"
    
    keyboard = []
    for product in products:
        product_name = f"{product['city']} → {product['district']} {product['size']}"
        price_text = f"${product['price']:.2f}"
        stock_text = f"({product['available']} stock)"
        
        button_text = f"{product_name[:25]} - {price_text} {stock_text}"
        keyboard.append([InlineKeyboardButton(
            button_text[:60],
            callback_data=f"price_edit_product|{product['id']}"
        )])
    
    keyboard.extend([
        [InlineKeyboardButton("📊 Bulk Update Category", callback_data=f"price_bulk_category|{category}")],
        [InlineKeyboardButton("⬅️ Back to Categories", callback_data="price_edit_by_category")]
    ])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Additional handlers for new price editing options

async def handle_price_city_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show product types in selected city for price editing"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params:
        await query.answer("Invalid city selection", show_alert=True)
        return
    
    city_name = params[0]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get product types in this city
        c.execute("""
            SELECT 
                product_type,
                size,
                COUNT(*) as total_products,
                COUNT(DISTINCT district) as districts,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price,
                SUM(available) as total_stock
            FROM products 
            WHERE city = %s
            GROUP BY product_type, size
            ORDER BY product_type, size
        """, (city_name,))
        product_variants = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading city products: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not product_variants:
        await query.edit_message_text(
            f"❌ **No Products Found**\n\nNo products found in {city_name}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="price_edit_by_city")]]),
            parse_mode='Markdown'
        )
        return
    
    msg = f"🏙️ **Edit Prices in {city_name}**\n\n"
    msg += f"**Select a product type to update prices for all {city_name} locations:**\n\n"
    
    keyboard = []
    for variant in product_variants[:15]:
        product_type = variant['product_type']
        size = variant['size']
        total = variant['total_products']
        districts = variant['districts']
        min_price = variant['min_price']
        max_price = variant['max_price']
        
        button_text = f"{product_type} {size} ({total} items, {districts} districts)"
        if len(button_text) > 60:
            button_text = f"{product_type} {size} ({total} items)"
        
        callback_data = f"price_city_product_select|{city_name}|{product_type}|{size}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Cities", callback_data="price_edit_by_city")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_city_district_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show districts in selected city"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params:
        await query.answer("Invalid city selection", show_alert=True)
        return
    
    city_name = params[0]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get districts in this city
        c.execute("""
            SELECT 
                district,
                COUNT(*) as total_products,
                COUNT(DISTINCT product_type) as product_types,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price
            FROM products 
            WHERE city = %s
            GROUP BY district
            ORDER BY district
        """, (city_name,))
        districts = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading city districts: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not districts:
        await query.edit_message_text(
            f"❌ **No Districts Found**\n\nNo districts found in {city_name}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="price_edit_by_city_district")]]),
            parse_mode='Markdown'
        )
        return
    
    msg = f"🏘️ **Select District in {city_name}**\n\n"
    msg += f"**Choose a district to edit prices:**\n\n"
    
    keyboard = []
    for district in districts:
        district_name = district['district']
        total = district['total_products']
        types = district['product_types']
        min_price = district['min_price']
        max_price = district['max_price']
        
        button_text = f"🏘️ {district_name} ({total} items, {types} types)"
        callback_data = f"price_district_select|{city_name}|{district_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Cities", callback_data="price_edit_by_city_district")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_district_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show product types in selected city and district"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 2:
        await query.answer("Invalid selection", show_alert=True)
        return
    
    city_name = params[0]
    district_name = params[1]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get product types in this specific location
        c.execute("""
            SELECT 
                product_type,
                size,
                COUNT(*) as total_products,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price,
                SUM(available) as total_stock
            FROM products 
            WHERE city = %s AND district = %s
            GROUP BY product_type, size
            ORDER BY product_type, size
        """, (city_name, district_name))
        product_variants = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error loading district products: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    if not product_variants:
        await query.edit_message_text(
            f"❌ **No Products Found**\n\nNo products found in {city_name} → {district_name}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"price_city_district_select|{city_name}")]]),
            parse_mode='Markdown'
        )
        return
    
    msg = f"🏘️ **Edit Prices in {city_name} → {district_name}**\n\n"
    msg += f"**Select a product type to update prices:**\n\n"
    
    keyboard = []
    for variant in product_variants:
        product_type = variant['product_type']
        size = variant['size']
        total = variant['total_products']
        min_price = variant['min_price']
        max_price = variant['max_price']
        avg_price = variant['avg_price']
        
        button_text = f"{product_type} {size} (${avg_price:.2f}, {total} items)"
        if len(button_text) > 60:
            button_text = f"{product_type} {size} ({total} items)"
        
        callback_data = f"price_district_product_select|{city_name}|{district_name}|{product_type}|{size}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Districts", callback_data=f"price_city_district_select|{city_name}")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_city_product_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show price update form for city-wide product"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 3:
        await query.answer("Invalid selection", show_alert=True)
        return
    
    city_name = params[0]
    product_type = params[1]
    size = params[2]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get detailed info about this product in this city
        c.execute("""
            SELECT 
                COUNT(*) as total_products,
                COUNT(DISTINCT district) as districts,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price,
                SUM(available) as total_stock
            FROM products 
            WHERE city = %s AND product_type = %s AND size = %s
        """, (city_name, product_type, size))
        stats = c.fetchone()
        
    except Exception as e:
        logger.error(f"Error loading city product details: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    # Store selection for price input
    context.user_data['city_price_city'] = city_name
    context.user_data['city_price_product_type'] = product_type
    context.user_data['city_price_size'] = size
    context.user_data['state'] = 'awaiting_city_price'
    
    msg = f"🏙️ **Update Prices in {city_name}**\n\n"
    msg += f"**Product:** {product_type} {size}\n"
    msg += f"**Total Products:** {stats['total_products']} items\n"
    msg += f"**Districts:** {stats['districts']}\n"
    msg += f"**Current Price Range:** ${stats['min_price']:.2f} - ${stats['max_price']:.2f}\n"
    msg += f"**Average Price:** ${stats['avg_price']:.2f}\n"
    msg += f"**Total Stock:** {stats['total_stock']} units\n\n"
    
    msg += "💡 **Price Suggestions:**\n"
    avg_price = stats['avg_price']
    msg += f"• Current Average: ${avg_price:.2f}\n"
    msg += f"• +10%: ${avg_price * 1.10:.2f}\n"
    msg += f"• +5%: ${avg_price * 1.05:.2f}\n"
    msg += f"• -5%: ${avg_price * 0.95:.2f}\n"
    msg += f"• -10%: ${avg_price * 0.90:.2f}\n\n"
    
    msg += f"**Enter new price to apply to ALL {city_name} locations:**"
    
    keyboard = [
        [InlineKeyboardButton(f"💰 ${avg_price * 1.10:.2f} (+10%)", callback_data=f"price_city_apply|{city_name}|{product_type}|{size}|{avg_price * 1.10:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 1.05:.2f} (+5%)", callback_data=f"price_city_apply|{city_name}|{product_type}|{size}|{avg_price * 1.05:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 0.95:.2f} (-5%)", callback_data=f"price_city_apply|{city_name}|{product_type}|{size}|{avg_price * 0.95:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 0.90:.2f} (-10%)", callback_data=f"price_city_apply|{city_name}|{product_type}|{size}|{avg_price * 0.90:.2f}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"price_city_select|{city_name}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"price_city_select|{city_name}")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_district_product_select(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show price update form for district-specific product"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 4:
        await query.answer("Invalid selection", show_alert=True)
        return
    
    city_name = params[0]
    district_name = params[1]
    product_type = params[2]
    size = params[3]
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get detailed info about this product in this specific location
        c.execute("""
            SELECT 
                COUNT(*) as total_products,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price,
                SUM(available) as total_stock
            FROM products 
            WHERE city = %s AND district = %s AND product_type = %s AND size = %s
        """, (city_name, district_name, product_type, size))
        stats = c.fetchone()
        
    except Exception as e:
        logger.error(f"Error loading district product details: {e}")
        await query.answer("Error loading data", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    # Store selection for price input
    context.user_data['district_price_city'] = city_name
    context.user_data['district_price_district'] = district_name
    context.user_data['district_price_product_type'] = product_type
    context.user_data['district_price_size'] = size
    context.user_data['state'] = 'awaiting_district_price'
    
    msg = f"🏘️ **Update Prices in {city_name} → {district_name}**\n\n"
    msg += f"**Product:** {product_type} {size}\n"
    msg += f"**Total Products:** {stats['total_products']} items\n"
    msg += f"**Current Price Range:** ${stats['min_price']:.2f} - ${stats['max_price']:.2f}\n"
    msg += f"**Average Price:** ${stats['avg_price']:.2f}\n"
    msg += f"**Total Stock:** {stats['total_stock']} units\n\n"
    
    msg += "💡 **Price Suggestions:**\n"
    avg_price = stats['avg_price']
    msg += f"• Current Average: ${avg_price:.2f}\n"
    msg += f"• +10%: ${avg_price * 1.10:.2f}\n"
    msg += f"• +5%: ${avg_price * 1.05:.2f}\n"
    msg += f"• -5%: ${avg_price * 0.95:.2f}\n"
    msg += f"• -10%: ${avg_price * 0.90:.2f}\n\n"
    
    msg += f"**Enter new price for {district_name} location:**"
    
    keyboard = [
        [InlineKeyboardButton(f"💰 ${avg_price * 1.10:.2f} (+10%)", callback_data=f"price_district_apply|{city_name}|{district_name}|{product_type}|{size}|{avg_price * 1.10:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 1.05:.2f} (+5%)", callback_data=f"price_district_apply|{city_name}|{district_name}|{product_type}|{size}|{avg_price * 1.05:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 0.95:.2f} (-5%)", callback_data=f"price_district_apply|{city_name}|{district_name}|{product_type}|{size}|{avg_price * 0.95:.2f}")],
        [InlineKeyboardButton(f"💰 ${avg_price * 0.90:.2f} (-10%)", callback_data=f"price_district_apply|{city_name}|{district_name}|{product_type}|{size}|{avg_price * 0.90:.2f}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"price_district_select|{city_name}|{district_name}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"price_district_select|{city_name}|{district_name}")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_city_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Apply price update to all products of a type in a city"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 4:
        await query.answer("Invalid parameters", show_alert=True)
        return
    
    city_name = params[0]
    product_type = params[1]
    size = params[2]
    new_price = float(params[3])
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get current products to update
        c.execute("""
            SELECT id, district, price 
            FROM products 
            WHERE city = %s AND product_type = %s AND size = %s
        """, (city_name, product_type, size))
        products_to_update = c.fetchall()
        
        if not products_to_update:
            await query.answer("No products found to update", show_alert=True)
            return
        
        # Update all prices
        c.execute("""
            UPDATE products 
            SET price = %s, last_price_update = CURRENT_TIMESTAMP
            WHERE city = %s AND product_type = %s AND size = %s
        """, (new_price, city_name, product_type, size))
        
        updated_count = c.rowcount
        
        # Log the price changes
        for product in products_to_update:
            c.execute("""
                INSERT INTO price_change_log 
                (product_id, old_price, new_price, changed_by_admin_id, change_reason, created_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                product['id'], 
                product['price'], 
                new_price, 
                query.from_user.id,
                f"City update: {city_name} - {product_type} {size}"
            ))
        
        conn.commit()
        
        msg = f"✅ **City Price Update Successful!**\n\n"
        msg += f"**Location:** {city_name}\n"
        msg += f"**Product:** {product_type} {size}\n"
        msg += f"**New Price:** ${new_price:.2f}\n"
        msg += f"**Updated Products:** {updated_count} items\n\n"
        msg += f"📍 **Districts Updated:**\n"
        
        # Show updated districts
        for product in products_to_update[:5]:
            old_price = product['price']
            change = ((new_price - old_price) / old_price) * 100
            change_symbol = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            msg += f"• {product['district']}: ${old_price:.2f} → ${new_price:.2f} {change_symbol}\n"
        
        if len(products_to_update) > 5:
            msg += f"... and {len(products_to_update) - 5} more districts\n"
        
        msg += f"\n🎯 **All {city_name} prices updated successfully!**"
        
    except Exception as e:
        logger.error(f"Error applying city price update: {e}")
        if conn:
            conn.rollback()
        msg = "❌ **Error updating prices.** Please try again."
        await query.answer("Update failed", show_alert=True)
    finally:
        if conn:
            conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🏙️ Update Another City Product", callback_data=f"price_city_select|{city_name}")],
        [InlineKeyboardButton("🏠 Back to Price Editor", callback_data="product_price_editor_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_price_district_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Apply price update to all products of a type in a specific district"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params or len(params) < 5:
        await query.answer("Invalid parameters", show_alert=True)
        return
    
    city_name = params[0]
    district_name = params[1]
    product_type = params[2]
    size = params[3]
    new_price = float(params[4])
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get current products to update
        c.execute("""
            SELECT id, price 
            FROM products 
            WHERE city = %s AND district = %s AND product_type = %s AND size = %s
        """, (city_name, district_name, product_type, size))
        products_to_update = c.fetchall()
        
        if not products_to_update:
            await query.answer("No products found to update", show_alert=True)
            return
        
        # Update all prices
        c.execute("""
            UPDATE products 
            SET price = %s, last_price_update = CURRENT_TIMESTAMP
            WHERE city = %s AND district = %s AND product_type = %s AND size = %s
        """, (new_price, city_name, district_name, product_type, size))
        
        updated_count = c.rowcount
        
        # Log the price changes
        for product in products_to_update:
            c.execute("""
                INSERT INTO price_change_log 
                (product_id, old_price, new_price, changed_by_admin_id, change_reason, created_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                product['id'], 
                product['price'], 
                new_price, 
                query.from_user.id,
                f"District update: {city_name} → {district_name} - {product_type} {size}"
            ))
        
        conn.commit()
        
        msg = f"✅ **District Price Update Successful!**\n\n"
        msg += f"**Location:** {city_name} → {district_name}\n"
        msg += f"**Product:** {product_type} {size}\n"
        msg += f"**New Price:** ${new_price:.2f}\n"
        msg += f"**Updated Products:** {updated_count} items\n\n"
        
        # Show price changes
        for product in products_to_update:
            old_price = product['price']
            change = ((new_price - old_price) / old_price) * 100
            change_symbol = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            msg += f"• Price Change: ${old_price:.2f} → ${new_price:.2f} {change_symbol} ({change:+.1f}%)\n"
        
        msg += f"\n🎯 **All {district_name} prices updated successfully!**"
        
    except Exception as e:
        logger.error(f"Error applying district price update: {e}")
        if conn:
            conn.rollback()
        msg = "❌ **Error updating prices.** Please try again."
        await query.answer("Update failed", show_alert=True)
    finally:
        if conn:
            conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🏘️ Update Another District Product", callback_data=f"price_district_select|{city_name}|{district_name}")],
        [InlineKeyboardButton("🏙️ Back to City Districts", callback_data=f"price_city_district_select|{city_name}")],
        [InlineKeyboardButton("🏠 Back to Price Editor", callback_data="product_price_editor_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- END OF FILE product_price_editor.py ---
