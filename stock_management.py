# --- START OF FILE stock_management.py ---

import logging
import sqlite3
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from utils import (
    get_db_connection, send_message_with_retry, format_currency,
    is_primary_admin, get_first_primary_admin_id, ADMIN_ID
)

logger = logging.getLogger(__name__)

# Stock management constants
LOW_STOCK_THRESHOLD = 5
CRITICAL_STOCK_THRESHOLD = 2
STOCK_ALERT_COOLDOWN_HOURS = 6

# --- Stock Alert Functions ---

async def check_low_stock_alerts():
    """
    Checks for products with low stock and sends alerts to admins.
    This should be called periodically (e.g., every hour).
    """
    logger.info("🔍 Running low stock check...")
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Find products with low stock that haven't been alerted recently
        now = datetime.now(timezone.utc)
        cooldown_time = now - timedelta(hours=STOCK_ALERT_COOLDOWN_HOURS)
        
        c.execute("""
            SELECT id, city, district, product_type, size, price, available, 
                   low_stock_threshold, last_stock_alert
            FROM products 
            WHERE stock_alerts_enabled = 1 
            AND available > 0 
            AND available <= low_stock_threshold
            AND (last_stock_alert IS NULL OR last_stock_alert < ?)
            ORDER BY available ASC
        """, (cooldown_time.isoformat(),))
        
        low_stock_products = c.fetchall()
        
        if not low_stock_products:
            logger.info("✅ No low stock alerts needed")
            return
        
        # Group alerts by severity
        critical_products = [p for p in low_stock_products if p['available'] <= CRITICAL_STOCK_THRESHOLD]
        warning_products = [p for p in low_stock_products if p['available'] > CRITICAL_STOCK_THRESHOLD]
        
        # Create alert message
        alert_message = "🚨 **STOCK ALERT** 🚨\n\n"
        
        if critical_products:
            alert_message += "🔴 **CRITICAL - Immediate Action Required:**\n"
            for product in critical_products:
                alert_message += f"• {product['city']} → {product['district']} → {product['product_type']} {product['size']}\n"
                alert_message += f"  💰 {format_currency(product['price'])} | 📦 Only {product['available']} left!\n\n"
        
        if warning_products:
            alert_message += "🟡 **LOW STOCK - Restock Soon:**\n"
            for product in warning_products:
                alert_message += f"• {product['city']} → {product['district']} → {product['product_type']} {product['size']}\n"
                alert_message += f"  💰 {format_currency(product['price'])} | 📦 {product['available']} remaining\n\n"
        
        alert_message += f"⏰ Alert generated at: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        # Store alert in database and update last_stock_alert
        for product in low_stock_products:
            # Log the alert
            c.execute("""
                INSERT INTO stock_alerts 
                (product_id, alert_type, alert_message, created_at, notified_admins)
                VALUES (?, ?, ?, ?, ?)
            """, (
                product['id'],
                'critical' if product['available'] <= CRITICAL_STOCK_THRESHOLD else 'low',
                f"Stock level: {product['available']}",
                now.isoformat(),
                str(ADMIN_ID)
            ))
            
            # Update last alert time
            c.execute("""
                UPDATE products SET last_stock_alert = ? WHERE id = ?
            """, (now.isoformat(), product['id']))
        
        conn.commit()
        
        # Send alert to primary admin
        # Note: Bot instance will be passed to this function when called from main
        logger.info(f"📧 Stock alert ready for {len(low_stock_products)} products")
        return alert_message
        
    except Exception as e:
        logger.error(f"Error checking low stock alerts: {e}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def get_stock_summary() -> Dict:
    """Returns a summary of current stock levels."""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get stock statistics
        c.execute("""
            SELECT 
                COUNT(*) as total_products,
                SUM(available) as total_stock,
                COUNT(CASE WHEN available <= ? THEN 1 END) as critical_stock,
                COUNT(CASE WHEN available <= ? AND available > ? THEN 1 END) as low_stock,
                COUNT(CASE WHEN available = 0 THEN 1 END) as out_of_stock
            FROM products
        """, (CRITICAL_STOCK_THRESHOLD, LOW_STOCK_THRESHOLD, CRITICAL_STOCK_THRESHOLD))
        
        stats = c.fetchone()
        
        # Get top low stock products
        c.execute("""
            SELECT city, district, product_type, size, available, price
            FROM products 
            WHERE available > 0 AND available <= ?
            ORDER BY available ASC
            LIMIT 10
        """, (LOW_STOCK_THRESHOLD,))
        
        low_stock_products = c.fetchall()
        
        return {
            'total_products': stats['total_products'],
            'total_stock': stats['total_stock'],
            'critical_stock': stats['critical_stock'],
            'low_stock': stats['low_stock'],
            'out_of_stock': stats['out_of_stock'],
            'low_stock_products': low_stock_products
        }
        
    except Exception as e:
        logger.error(f"Error getting stock summary: {e}")
        return {}
    finally:
        if conn:
            conn.close()

async def update_stock_threshold(product_id: int, threshold: int) -> bool:
    """Updates the low stock threshold for a specific product."""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE products SET low_stock_threshold = ? WHERE id = ?
        """, (threshold, product_id))
        
        if c.rowcount > 0:
            conn.commit()
            logger.info(f"Updated stock threshold for product {product_id} to {threshold}")
            return True
        else:
            logger.warning(f"Product {product_id} not found for threshold update")
            return False
            
    except Exception as e:
        logger.error(f"Error updating stock threshold: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

async def toggle_stock_alerts(product_id: int, enabled: bool) -> bool:
    """Enables or disables stock alerts for a specific product."""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE products SET stock_alerts_enabled = ? WHERE id = ?
        """, (1 if enabled else 0, product_id))
        
        if c.rowcount > 0:
            conn.commit()
            logger.info(f"{'Enabled' if enabled else 'Disabled'} stock alerts for product {product_id}")
            return True
        else:
            logger.warning(f"Product {product_id} not found for alert toggle")
            return False
            
    except Exception as e:
        logger.error(f"Error toggling stock alerts: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- Admin Handlers for Stock Management ---

async def handle_stock_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Shows the stock management menu."""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    # Get stock summary
    summary = get_stock_summary()
    
    msg = "📦 **Stock Management Dashboard**\n\n"
    msg += f"📊 **Overview:**\n"
    msg += f"• Total Products: {summary.get('total_products', 0)}\n"
    msg += f"• Total Stock: {summary.get('total_stock', 0)} units\n"
    msg += f"• 🔴 Critical Stock: {summary.get('critical_stock', 0)} products\n"
    msg += f"• 🟡 Low Stock: {summary.get('low_stock', 0)} products\n"
    msg += f"• ❌ Out of Stock: {summary.get('out_of_stock', 0)} products\n\n"
    
    if summary.get('low_stock_products'):
        msg += "⚠️ **Products Needing Attention:**\n"
        for product in summary['low_stock_products'][:5]:  # Show top 5
            msg += f"• {product['city']} → {product['product_type']} {product['size']} ({product['available']} left)\n"
        
        if len(summary['low_stock_products']) > 5:
            msg += f"... and {len(summary['low_stock_products']) - 5} more\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 Detailed Stock Report", callback_data="stock_detailed_report")],
        [InlineKeyboardButton("🚨 View Stock Alerts", callback_data="stock_view_alerts")],
        [InlineKeyboardButton("⚙️ Configure Thresholds", callback_data="stock_configure_thresholds")],
        [InlineKeyboardButton("🔄 Run Stock Check Now", callback_data="stock_check_now")],
        [InlineKeyboardButton("📈 Stock Analytics", callback_data="stock_analytics")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_stock_check_now(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Manually triggers a stock check."""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    await query.answer("Running stock check...", show_alert=False)
    
    try:
        await check_low_stock_alerts()
        await query.edit_message_text(
            "✅ Stock check completed! Any low stock alerts have been generated.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Stock Management", callback_data="stock_management_menu")
            ]])
        )
    except Exception as e:
        logger.error(f"Error in manual stock check: {e}")
        await query.edit_message_text(
            "❌ Error running stock check. Please check logs.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Stock Management", callback_data="stock_management_menu")
            ]])
        )

async def handle_stock_detailed_report(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Shows a detailed stock report."""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get detailed stock by category
        c.execute("""
            SELECT city, district, product_type, 
                   COUNT(*) as product_count,
                   SUM(available) as total_stock,
                   MIN(available) as min_stock,
                   MAX(available) as max_stock,
                   AVG(available) as avg_stock
            FROM products 
            WHERE available > 0
            GROUP BY city, district, product_type
            ORDER BY city, district, product_type
        """)
        
        stock_data = c.fetchall()
        
        msg = "📊 **Detailed Stock Report**\n\n"
        
        current_city = ""
        for row in stock_data:
            if row['city'] != current_city:
                current_city = row['city']
                msg += f"🏙️ **{current_city}**\n"
            
            msg += f"  📍 {row['district']} - {row['product_type']}\n"
            msg += f"    Products: {row['product_count']} | Stock: {row['total_stock']} units\n"
            msg += f"    Range: {row['min_stock']}-{row['max_stock']} | Avg: {row['avg_stock']:.1f}\n\n"
        
        if not stock_data:
            msg += "No products in stock."
        
        keyboard = [[InlineKeyboardButton("⬅️ Back to Stock Management", callback_data="stock_management_menu")]]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error generating detailed stock report: {e}")
        await query.edit_message_text(
            "❌ Error generating report. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Stock Management", callback_data="stock_management_menu")
            ]])
        )
    finally:
        if conn:
            conn.close()

async def handle_stock_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show stock analytics and insights"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    msg = "📊 **Stock Analytics**\n\n"
    msg += "Coming soon! Advanced stock analytics including:\n\n"
    msg += "• Turnover rates by product type\n"
    msg += "• Stock movement trends\n"
    msg += "• Reorder recommendations\n"
    msg += "• Seasonal patterns\n"
    msg += "• Profit margins by category\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Stock Management", callback_data="stock_management_menu")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_stock_configure_thresholds(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Configure stock alert thresholds"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    msg = "⚙️ **Configure Stock Thresholds**\n\n"
    msg += "Set custom alert thresholds for different product categories:\n\n"
    msg += "• Default threshold: 5 units\n"
    msg += "• Critical threshold: 2 units\n\n"
    msg += "Coming soon: Per-product threshold configuration!"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Stock Management", callback_data="stock_management_menu")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_stock_view_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """View stock alert history"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get recent stock alerts
        c.execute("""
            SELECT sa.alert_type, sa.alert_message, sa.created_at,
                   p.city, p.district, p.product_type, p.size, p.available
            FROM stock_alerts sa
            JOIN products p ON sa.product_id = p.id
            ORDER BY sa.created_at DESC
            LIMIT 20
        """)
        
        alerts = c.fetchall()
        
        msg = "🚨 **Stock Alert History**\n\n"
        
        if not alerts:
            msg += "No stock alerts found.\n\n"
            msg += "Alerts are generated when:\n"
            msg += "• Products fall below threshold\n"
            msg += "• Critical stock levels reached\n"
            msg += "• Items go out of stock\n"
        else:
            for alert in alerts[:10]:
                try:
                    date_str = datetime.fromisoformat(alert['created_at'].replace('Z', '+00:00')).strftime('%m-%d %H:%M')
                except:
                    date_str = "Recent"
                
                alert_icon = "🔴" if alert['alert_type'] == 'critical' else "🟡"
                msg += f"{alert_icon} **{alert['alert_type'].title()} Alert** ({date_str})\n"
                msg += f"   📍 {alert['city']} → {alert['product_type']} {alert['size']}\n"
                msg += f"   📦 Stock: {alert['available']} units\n"
                msg += f"   💬 {alert['alert_message']}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Run Stock Check", callback_data="stock_check_now")],
            [InlineKeyboardButton("⬅️ Back to Stock Management", callback_data="stock_management_menu")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error viewing stock alerts: {e}")
        await query.edit_message_text(
            "❌ Error loading stock alerts.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Stock Management", callback_data="stock_management_menu")
            ]])
        )
    finally:
        if conn:
            conn.close()

# --- END OF FILE stock_management.py ---
