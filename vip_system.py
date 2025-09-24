# --- START OF FILE vip_system.py ---

"""
Advanced VIP & Customer Ranking System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Comprehensive VIP system with customizable levels, requirements, and benefits.
Allows admins to create custom customer tiers like "Diamond Customer" with
configurable purchase requirements and exclusive perks.

Features:
- Customizable VIP levels with admin-defined names and emojis
- Configurable purchase requirements for each level
- VIP benefits and perks system
- Automatic level progression tracking
- VIP-only features and discounts
- Level-up notifications and celebrations
- Admin dashboard for VIP management

Author: Enhanced Bot System
Version: 1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils import (
    get_db_connection, send_message_with_retry, format_currency,
    is_primary_admin, log_admin_action, LANGUAGES
)

logger = logging.getLogger(__name__)

class VIPManager:
    """Manages VIP levels and customer ranking system"""
    
    @staticmethod
    def init_vip_tables():
        """Initialize VIP system database tables"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # VIP levels configuration table
            c.execute('''CREATE TABLE IF NOT EXISTS vip_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level_name TEXT NOT NULL UNIQUE,
                level_emoji TEXT NOT NULL,
                min_purchases INTEGER NOT NULL,
                max_purchases INTEGER,
                level_order INTEGER NOT NULL,
                benefits TEXT,
                discount_percentage REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )''')
            
            # VIP benefits table
            c.execute('''CREATE TABLE IF NOT EXISTS vip_benefits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vip_level_id INTEGER NOT NULL,
                benefit_type TEXT NOT NULL,
                benefit_value TEXT NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (vip_level_id) REFERENCES vip_levels(id) ON DELETE CASCADE
            )''')
            
            # User VIP history table
            c.execute('''CREATE TABLE IF NOT EXISTS user_vip_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                old_level_name TEXT,
                new_level_name TEXT NOT NULL,
                level_up_date TEXT NOT NULL,
                purchases_at_levelup INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )''')
            
            conn.commit()
            
            # Create default VIP levels if none exist
            c.execute("SELECT COUNT(*) as count FROM vip_levels")
            if c.fetchone()['count'] == 0:
                VIPManager._create_default_levels(c)
                conn.commit()
            
            logger.info("VIP system database tables initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing VIP tables: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def _create_default_levels(cursor):
        """Create default VIP levels"""
        default_levels = [
            {
                'level_name': 'New Customer',
                'level_emoji': '🌱',
                'min_purchases': 0,
                'max_purchases': 2,
                'level_order': 1,
                'benefits': json.dumps(['Welcome bonus eligibility']),
                'discount_percentage': 0.0
            },
            {
                'level_name': 'Regular Customer',
                'level_emoji': '⭐',
                'min_purchases': 3,
                'max_purchases': 9,
                'level_order': 2,
                'benefits': json.dumps(['Standard support', 'Regular updates']),
                'discount_percentage': 2.0
            },
            {
                'level_name': 'VIP Customer',
                'level_emoji': '👑',
                'min_purchases': 10,
                'max_purchases': 24,
                'level_order': 3,
                'benefits': json.dumps(['Priority support', 'Early access', '5% discount']),
                'discount_percentage': 5.0
            },
            {
                'level_name': 'Diamond Customer',
                'level_emoji': '💎',
                'min_purchases': 25,
                'max_purchases': None,
                'level_order': 4,
                'benefits': json.dumps(['Premium support', 'Exclusive products', '10% discount', 'Free shipping']),
                'discount_percentage': 10.0
            }
        ]
        
        for level in default_levels:
            cursor.execute('''INSERT INTO vip_levels 
                            (level_name, level_emoji, min_purchases, max_purchases, 
                             level_order, benefits, discount_percentage, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (level['level_name'], level['level_emoji'], level['min_purchases'],
                          level['max_purchases'], level['level_order'], level['benefits'],
                          level['discount_percentage'], datetime.now(timezone.utc).isoformat()))
        
        logger.info("Created default VIP levels")
    
    @staticmethod
    def get_user_vip_level(user_purchases: int) -> Dict:
        """Get user's VIP level based on purchase count"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Find the appropriate level
            c.execute("""
                SELECT level_name, level_emoji, min_purchases, max_purchases, 
                       benefits, discount_percentage, level_order
                FROM vip_levels 
                WHERE is_active = 1 
                AND min_purchases <= ?
                AND (max_purchases IS NULL OR max_purchases >= ?)
                ORDER BY level_order DESC
                LIMIT 1
            """, (user_purchases, user_purchases))
            
            level_data = c.fetchone()
            
            if level_data:
                benefits = json.loads(level_data['benefits']) if level_data['benefits'] else []
                
                return {
                    'level_name': level_data['level_name'],
                    'level_emoji': level_data['level_emoji'],
                    'min_purchases': level_data['min_purchases'],
                    'max_purchases': level_data['max_purchases'],
                    'benefits': benefits,
                    'discount_percentage': level_data['discount_percentage'],
                    'level_order': level_data['level_order']
                }
            else:
                # Fallback to basic level
                return {
                    'level_name': 'New Customer',
                    'level_emoji': '🌱',
                    'min_purchases': 0,
                    'max_purchases': 2,
                    'benefits': [],
                    'discount_percentage': 0.0,
                    'level_order': 1
                }
                
        except Exception as e:
            logger.error(f"Error getting user VIP level: {e}")
            return {
                'level_name': 'New Customer',
                'level_emoji': '🌱',
                'min_purchases': 0,
                'max_purchases': 2,
                'benefits': [],
                'discount_percentage': 0.0,
                'level_order': 1
            }
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_next_level_info(user_purchases: int) -> Optional[Dict]:
        """Get information about the next VIP level"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Find the next level
            c.execute("""
                SELECT level_name, level_emoji, min_purchases, benefits, discount_percentage
                FROM vip_levels 
                WHERE is_active = 1 
                AND min_purchases > ?
                ORDER BY level_order ASC
                LIMIT 1
            """, (user_purchases,))
            
            next_level = c.fetchone()
            
            if next_level:
                benefits = json.loads(next_level['benefits']) if next_level['benefits'] else []
                purchases_needed = next_level['min_purchases'] - user_purchases
                
                return {
                    'level_name': next_level['level_name'],
                    'level_emoji': next_level['level_emoji'],
                    'min_purchases': next_level['min_purchases'],
                    'purchases_needed': purchases_needed,
                    'benefits': benefits,
                    'discount_percentage': next_level['discount_percentage']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next level info: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def check_level_up(user_id: int, new_purchase_count: int) -> Optional[Dict]:
        """Check if user should level up and process it"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Get user's current level from history
            c.execute("""
                SELECT new_level_name FROM user_vip_history 
                WHERE user_id = ? 
                ORDER BY level_up_date DESC 
                LIMIT 1
            """, (user_id,))
            
            current_level_result = c.fetchone()
            current_level_name = current_level_result['new_level_name'] if current_level_result else None
            
            # Get current and new levels
            old_level = VIPManager.get_user_vip_level(new_purchase_count - 1) if new_purchase_count > 0 else None
            new_level = VIPManager.get_user_vip_level(new_purchase_count)
            
            # Check if level changed
            if (old_level and new_level and 
                old_level['level_order'] < new_level['level_order']):
                
                # Record level up
                c.execute("""
                    INSERT INTO user_vip_history 
                    (user_id, old_level_name, new_level_name, level_up_date, purchases_at_levelup)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id,
                    old_level['level_name'],
                    new_level['level_name'],
                    datetime.now(timezone.utc).isoformat(),
                    new_purchase_count
                ))
                
                conn.commit()
                
                logger.info(f"User {user_id} leveled up: {old_level['level_name']} → {new_level['level_name']}")
                
                return {
                    'leveled_up': True,
                    'old_level': old_level,
                    'new_level': new_level,
                    'purchases_at_levelup': new_purchase_count
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking level up for user {user_id}: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_all_vip_levels() -> List[Dict]:
        """Get all VIP levels for admin management"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute("""
                SELECT id, level_name, level_emoji, min_purchases, max_purchases,
                       level_order, benefits, discount_percentage, is_active
                FROM vip_levels 
                ORDER BY level_order ASC
            """)
            
            levels = []
            for row in c.fetchall():
                benefits = json.loads(row['benefits']) if row['benefits'] else []
                levels.append({
                    'id': row['id'],
                    'level_name': row['level_name'],
                    'level_emoji': row['level_emoji'],
                    'min_purchases': row['min_purchases'],
                    'max_purchases': row['max_purchases'],
                    'level_order': row['level_order'],
                    'benefits': benefits,
                    'discount_percentage': row['discount_percentage'],
                    'is_active': row['is_active'] == 1
                })
            
            return levels
            
        except Exception as e:
            logger.error(f"Error getting VIP levels: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def create_vip_level(level_data: Dict) -> bool:
        """Create a new VIP level"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute('''INSERT INTO vip_levels 
                        (level_name, level_emoji, min_purchases, max_purchases,
                         level_order, benefits, discount_percentage, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                     (
                         level_data['level_name'],
                         level_data['level_emoji'],
                         level_data['min_purchases'],
                         level_data.get('max_purchases'),
                         level_data['level_order'],
                         json.dumps(level_data.get('benefits', [])),
                         level_data.get('discount_percentage', 0.0),
                         datetime.now(timezone.utc).isoformat()
                     ))
            
            conn.commit()
            logger.info(f"Created VIP level: {level_data['level_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating VIP level: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def update_vip_level(level_id: int, level_data: Dict) -> bool:
        """Update an existing VIP level"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute('''UPDATE vip_levels 
                        SET level_name = ?, level_emoji = ?, min_purchases = ?,
                            max_purchases = ?, level_order = ?, benefits = ?,
                            discount_percentage = ?, updated_at = ?
                        WHERE id = ?''',
                     (
                         level_data['level_name'],
                         level_data['level_emoji'],
                         level_data['min_purchases'],
                         level_data.get('max_purchases'),
                         level_data['level_order'],
                         json.dumps(level_data.get('benefits', [])),
                         level_data.get('discount_percentage', 0.0),
                         datetime.now(timezone.utc).isoformat(),
                         level_id
                     ))
            
            success = c.rowcount > 0
            if success:
                conn.commit()
                logger.info(f"Updated VIP level ID {level_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating VIP level: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_vip_statistics() -> Dict:
        """Get VIP system statistics for admin dashboard"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Get user distribution by level
            c.execute("""
                SELECT 
                    vl.level_name,
                    vl.level_emoji,
                    COUNT(CASE WHEN u.total_purchases >= vl.min_purchases 
                               AND (vl.max_purchases IS NULL OR u.total_purchases <= vl.max_purchases) 
                               THEN 1 END) as user_count,
                    vl.level_order
                FROM vip_levels vl
                CROSS JOIN users u
                WHERE vl.is_active = 1
                GROUP BY vl.id, vl.level_name, vl.level_emoji, vl.level_order
                ORDER BY vl.level_order ASC
            """)
            
            level_distribution = []
            total_users = 0
            
            for row in c.fetchall():
                user_count = row['user_count']
                total_users += user_count
                level_distribution.append({
                    'level_name': row['level_name'],
                    'level_emoji': row['level_emoji'],
                    'user_count': user_count,
                    'level_order': row['level_order']
                })
            
            # Get recent level ups
            c.execute("""
                SELECT uvh.user_id, uvh.old_level_name, uvh.new_level_name, 
                       uvh.level_up_date, u.username
                FROM user_vip_history uvh
                LEFT JOIN users u ON uvh.user_id = u.user_id
                ORDER BY uvh.level_up_date DESC
                LIMIT 10
            """)
            
            recent_levelups = []
            for row in c.fetchall():
                recent_levelups.append({
                    'user_id': row['user_id'],
                    'username': row['username'] or f"ID_{row['user_id']}",
                    'old_level': row['old_level_name'],
                    'new_level': row['new_level_name'],
                    'date': row['level_up_date']
                })
            
            return {
                'level_distribution': level_distribution,
                'total_users': total_users,
                'recent_levelups': recent_levelups
            }
            
        except Exception as e:
            logger.error(f"Error getting VIP statistics: {e}")
            return {
                'level_distribution': [],
                'total_users': 0,
                'recent_levelups': []
            }
        finally:
            if conn:
                conn.close()

# --- Enhanced User Status Functions ---

def get_user_status_enhanced(purchases: int) -> str:
    """Enhanced user status function using VIP system"""
    level_info = VIPManager.get_user_vip_level(purchases)
    return f"{level_info['level_name']} {level_info['level_emoji']}"

def get_progress_bar_enhanced(purchases: int) -> str:
    """Enhanced progress bar showing progress to next level"""
    current_level = VIPManager.get_user_vip_level(purchases)
    next_level = VIPManager.get_next_level_info(purchases)
    
    if not next_level:
        # User is at max level
        return '[🟩🟩🟩🟩🟩] MAX'
    
    # Calculate progress to next level
    current_min = current_level['min_purchases']
    next_min = next_level['min_purchases']
    progress = purchases - current_min
    total_needed = next_min - current_min
    
    if total_needed <= 0:
        filled_bars = 5
    else:
        filled_bars = min(5, int((progress / total_needed) * 5))
    
    empty_bars = 5 - filled_bars
    progress_bar = '[' + '🟩' * filled_bars + '⬜' * empty_bars + ']'
    
    purchases_left = next_min - purchases
    if purchases_left > 0:
        progress_bar += f" ({purchases_left} to {next_level['level_emoji']})"
    
    return progress_bar

def get_user_vip_benefits(purchases: int) -> List[str]:
    """Get list of benefits for user's current VIP level"""
    level_info = VIPManager.get_user_vip_level(purchases)
    return level_info.get('benefits', [])

def get_user_vip_discount(purchases: int) -> Decimal:
    """Get VIP discount percentage for user"""
    level_info = VIPManager.get_user_vip_level(purchases)
    return Decimal(str(level_info.get('discount_percentage', 0.0)))

# --- Admin Interface Handlers ---

async def handle_vip_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show VIP management menu for admins"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    # Get VIP statistics
    stats = VIPManager.get_vip_statistics()
    
    msg = "👑 **VIP System Management**\n\n"
    msg += f"📊 **Customer Distribution:**\n"
    
    for level in stats['level_distribution']:
        percentage = (level['user_count'] / stats['total_users'] * 100) if stats['total_users'] > 0 else 0
        msg += f"• {level['level_emoji']} {level['level_name']}: {level['user_count']} ({percentage:.1f}%)\n"
    
    if stats['recent_levelups']:
        msg += f"\n🎉 **Recent Level Ups:**\n"
        for levelup in stats['recent_levelups'][:3]:
            try:
                date_str = datetime.fromisoformat(levelup['date'].replace('Z', '+00:00')).strftime('%m-%d')
            except:
                date_str = "Recent"
            msg += f"• @{levelup['username']}: {levelup['old_level']} → {levelup['new_level']} ({date_str})\n"
    
    keyboard = [
        [InlineKeyboardButton("📋 Manage Levels", callback_data="vip_manage_levels")],
        [InlineKeyboardButton("➕ Create New Level", callback_data="vip_create_level")],
        [InlineKeyboardButton("📊 VIP Analytics", callback_data="vip_analytics")],
        [InlineKeyboardButton("🎁 VIP Benefits", callback_data="vip_manage_benefits")],
        [InlineKeyboardButton("👑 VIP Customers", callback_data="vip_list_customers")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_vip_manage_levels(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show all VIP levels for management"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    levels = VIPManager.get_all_vip_levels()
    
    msg = "📋 **Manage VIP Levels**\n\n"
    msg += "Current level configuration:\n\n"
    
    keyboard = []
    
    for level in levels:
        status = "✅" if level['is_active'] else "❌"
        max_purchases = level['max_purchases'] if level['max_purchases'] else "∞"
        discount = level['discount_percentage']
        
        msg += f"{status} **{level['level_emoji']} {level['level_name']}**\n"
        msg += f"   Purchases: {level['min_purchases']} - {max_purchases}\n"
        msg += f"   Discount: {discount}%\n"
        msg += f"   Benefits: {len(level['benefits'])}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(f"✏️ {level['level_name']}", callback_data=f"vip_edit_level_{level['id']}"),
            InlineKeyboardButton("🗑️", callback_data=f"vip_delete_level_{level['id']}")
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Add New Level", callback_data="vip_create_level")])
    keyboard.append([InlineKeyboardButton("🔄 Reset to Defaults", callback_data="vip_reset_defaults")])
    keyboard.append([InlineKeyboardButton("⬅️ Back to VIP Menu", callback_data="vip_management_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_vip_create_level(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Start creating a new VIP level"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    context.user_data['state'] = 'awaiting_vip_level_name'
    context.user_data['vip_creation_data'] = {}
    
    msg = "➕ **Create New VIP Level**\n\n"
    msg += "Enter a name for the new VIP level:\n\n"
    msg += "💡 **Examples:**\n"
    msg += "• Diamond Customer\n"
    msg += "• Platinum Member\n"
    msg += "• Elite Buyer\n"
    msg += "• Premium User\n"
    msg += "• Gold Status\n\n"
    msg += "📝 Enter the level name:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="vip_manage_levels")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    await query.answer("Enter VIP level name")

async def handle_vip_level_name_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle VIP level name input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get("state") != "awaiting_vip_level_name":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid level name.", parse_mode=None)
        return
    
    level_name = update.message.text.strip()
    
    if len(level_name) < 3:
        await send_message_with_retry(context.bot, chat_id, "❌ Level name must be at least 3 characters.", parse_mode=None)
        return
    
    if len(level_name) > 30:
        await send_message_with_retry(context.bot, chat_id, "❌ Level name must be less than 30 characters.", parse_mode=None)
        return
    
    # Check if name already exists
    levels = VIPManager.get_all_vip_levels()
    if any(level['level_name'].lower() == level_name.lower() for level in levels):
        await send_message_with_retry(context.bot, chat_id, f"❌ VIP level '{level_name}' already exists.", parse_mode=None)
        return
    
    # Store name and ask for emoji
    context.user_data['vip_creation_data']['level_name'] = level_name
    context.user_data['state'] = 'awaiting_vip_level_emoji'
    
    msg = f"✅ Level name: **{level_name}**\n\n"
    msg += "Now choose an emoji for this level:\n\n"
    msg += "💡 **Popular choices:**"
    
    emoji_options = [
        ("💎", "Diamond"), ("👑", "Crown"), ("🌟", "Star"),
        ("🔥", "Fire"), ("⚡", "Lightning"), ("🏆", "Trophy"),
        ("💰", "Money"), ("🎯", "Target"), ("🚀", "Rocket")
    ]
    
    keyboard = []
    for emoji, name in emoji_options:
        keyboard.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"vip_select_emoji|{emoji}")])
    
    keyboard.append([InlineKeyboardButton("🔤 Custom Emoji", callback_data="vip_custom_emoji")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="vip_manage_levels")])
    
    await send_message_with_retry(context.bot, chat_id, msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_vip_select_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle emoji selection for VIP level"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid emoji selection", show_alert=True)
        return
    
    emoji = params[0]
    
    # Store emoji and ask for purchase requirements
    context.user_data['vip_creation_data']['level_emoji'] = emoji
    context.user_data['state'] = 'awaiting_vip_min_purchases'
    
    level_name = context.user_data['vip_creation_data']['level_name']
    
    msg = f"✅ **{emoji} {level_name}**\n\n"
    msg += "Enter the **minimum number of purchases** required for this level:\n\n"
    msg += "💡 **Examples:**\n"
    msg += "• 0 = New customers\n"
    msg += "• 5 = Regular customers\n"
    msg += "• 15 = VIP customers\n"
    msg += "• 50 = Diamond customers\n\n"
    msg += "📝 Enter minimum purchases:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="vip_manage_levels")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    await query.answer("Enter minimum purchases")

async def handle_vip_custom_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle custom emoji input for VIP level"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    context.user_data['state'] = 'awaiting_vip_custom_emoji'
    
    level_name = context.user_data.get('vip_creation_data', {}).get('level_name', 'Unknown')
    
    msg = f"🔤 **Custom Emoji for {level_name}**\n\n"
    msg += "Enter a custom emoji for this VIP level:\n\n"
    msg += "💡 **Tips:**\n"
    msg += "• Use any single emoji\n"
    msg += "• Avoid text or multiple characters\n"
    msg += "• Make it unique and memorable\n\n"
    msg += "📝 Send your custom emoji:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="vip_create_level")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    await query.answer("Send custom emoji")

async def handle_vip_custom_emoji_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom emoji input message"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get("state") != "awaiting_vip_custom_emoji":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid emoji.", parse_mode=None)
        return
    
    emoji = update.message.text.strip()
    
    if len(emoji) > 4:  # Allow for multi-byte emojis
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter only a single emoji.", parse_mode=None)
        return
    
    if not emoji:
        await send_message_with_retry(context.bot, chat_id, "❌ Emoji cannot be empty.", parse_mode=None)
        return
    
    # Continue with the emoji selection process
    context.user_data['state'] = 'awaiting_vip_min_purchases'
    context.user_data['vip_creation_data']['level_emoji'] = emoji
    
    level_name = context.user_data['vip_creation_data']['level_name']
    
    msg = f"✅ **{emoji} {level_name}**\n\n"
    msg += "Enter the **minimum number of purchases** required for this level:\n\n"
    msg += "💡 **Examples:**\n"
    msg += "• 0 = New customers\n"
    msg += "• 5 = Regular customers\n"
    msg += "• 15 = VIP customers\n"
    msg += "• 50 = Diamond customers\n\n"
    msg += "📝 Enter minimum purchases:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="vip_manage_levels")]]
    
    await send_message_with_retry(context.bot, chat_id, msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_vip_max_purchases_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle maximum purchases input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get("state") != "awaiting_vip_max_purchases":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid number or 'unlimited'.", parse_mode=None)
        return
    
    max_input = update.message.text.strip().lower()
    
    if max_input in ['unlimited', 'infinite', '∞', 'no limit']:
        max_purchases = None
    else:
        try:
            max_purchases = int(max_input)
            if max_purchases < 0:
                await send_message_with_retry(context.bot, chat_id, "❌ Maximum purchases cannot be negative.", parse_mode=None)
                return
            
            min_purchases = context.user_data['vip_creation_data']['min_purchases']
            if max_purchases <= min_purchases:
                await send_message_with_retry(context.bot, chat_id, f"❌ Maximum purchases ({max_purchases}) must be greater than minimum ({min_purchases}).", parse_mode=None)
                return
        except ValueError:
            await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid number or 'unlimited'.", parse_mode=None)
            return
    
    # Store and finalize level creation
    context.user_data['vip_creation_data']['max_purchases'] = max_purchases
    context.user_data['vip_creation_data']['level_order'] = 999  # Will be adjusted
    context.user_data['vip_creation_data']['benefits'] = ['Custom VIP level']
    context.user_data['vip_creation_data']['discount_percentage'] = 0.0
    
    # Create the level
    success = VIPManager.create_vip_level(context.user_data['vip_creation_data'])
    
    # Clear context
    context.user_data.pop('state', None)
    context.user_data.pop('vip_creation_data', None)
    
    if success:
        level_name = context.user_data.get('vip_creation_data', {}).get('level_name', 'New Level')
        emoji = context.user_data.get('vip_creation_data', {}).get('level_emoji', '✨')
        
        msg = f"✅ **VIP Level Created Successfully!**\n\n"
        msg += f"**Level:** {emoji} {level_name}\n"
        msg += f"**Requirements:** {min_purchases} - {max_purchases or '∞'} purchases\n\n"
        msg += "The new VIP level is now active and will be applied to users automatically!"
        
        keyboard = [
            [InlineKeyboardButton("📋 Manage Levels", callback_data="vip_manage_levels")],
            [InlineKeyboardButton("👑 VIP Menu", callback_data="vip_management_menu")]
        ]
        
        await send_message_with_retry(context.bot, chat_id, msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Error creating VIP level. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data="vip_create_level")
            ]]),
            parse_mode='Markdown'
        )

async def handle_vip_min_purchases_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle minimum purchases input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get("state") != "awaiting_vip_min_purchases":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid number.", parse_mode=None)
        return
    
    try:
        min_purchases = int(update.message.text.strip())
        if min_purchases < 0:
            await send_message_with_retry(context.bot, chat_id, "❌ Minimum purchases cannot be negative.", parse_mode=None)
            return
    except ValueError:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid number.", parse_mode=None)
        return
    
    # Store and ask for maximum purchases
    context.user_data['vip_creation_data']['min_purchases'] = min_purchases
    context.user_data['state'] = 'awaiting_vip_max_purchases'
    
    level_name = context.user_data['vip_creation_data']['level_name']
    emoji = context.user_data['vip_creation_data']['level_emoji']
    
    msg = f"✅ **{emoji} {level_name}**\n"
    msg += f"Min purchases: {min_purchases}\n\n"
    msg += "Enter the **maximum number of purchases** for this level:\n\n"
    msg += "💡 **Options:**\n"
    msg += "• Enter a number (e.g., 24)\n"
    msg += "• Enter 'unlimited' for no maximum\n\n"
    msg += "📝 Enter maximum purchases:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="vip_manage_levels")]]
    
    await send_message_with_retry(context.bot, chat_id, msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- Level Up Notification System ---

async def notify_user_level_up(user_id: int, level_up_info: Dict, bot):
    """Send level up notification to user"""
    try:
        old_level = level_up_info['old_level']
        new_level = level_up_info['new_level']
        
        msg = f"🎉 **LEVEL UP!** 🎉\n\n"
        msg += f"Congratulations! You've been promoted!\n\n"
        msg += f"**Old Level:** {old_level['level_emoji']} {old_level['level_name']}\n"
        msg += f"**New Level:** {new_level['level_emoji']} {new_level['level_name']}\n\n"
        msg += f"🎁 **New Benefits:**\n"
        
        for benefit in new_level['benefits']:
            msg += f"• {benefit}\n"
        
        if new_level['discount_percentage'] > 0:
            msg += f"\n💰 **VIP Discount:** {new_level['discount_percentage']}% on all purchases!\n"
        
        msg += f"\nThank you for being a valued customer! 🙏"
        
        await send_message_with_retry(bot, user_id, msg, parse_mode='Markdown')
        logger.info(f"Sent level up notification to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error sending level up notification to user {user_id}: {e}")

# --- VIP Benefits System ---

def apply_vip_discount(user_purchases: int, original_price: Decimal) -> Tuple[Decimal, Decimal]:
    """Apply VIP discount to price and return (discounted_price, discount_amount)"""
    vip_discount_percent = get_user_vip_discount(user_purchases)
    
    if vip_discount_percent > 0:
        discount_amount = (original_price * vip_discount_percent / 100).quantize(Decimal('0.01'))
        discounted_price = original_price - discount_amount
        return discounted_price, discount_amount
    
    return original_price, Decimal('0.00')

def has_vip_benefit(user_purchases: int, benefit_name: str) -> bool:
    """Check if user has a specific VIP benefit"""
    benefits = get_user_vip_benefits(user_purchases)
    return any(benefit_name.lower() in benefit.lower() for benefit in benefits)

# --- Integration with Purchase System ---

async def process_vip_level_up(user_id: int, new_purchase_count: int, bot):
    """Process potential VIP level up after purchase"""
    try:
        level_up_info = VIPManager.check_level_up(user_id, new_purchase_count)
        
        if level_up_info and level_up_info.get('leveled_up'):
            # Send notification to user
            await notify_user_level_up(user_id, level_up_info, bot)
            
            # Log admin action for tracking
            log_admin_action(
                admin_id=0,  # System action
                action='VIP_LEVEL_UP',
                target_user_id=user_id,
                reason=f"Leveled up to {level_up_info['new_level']['level_name']}",
                old_value=level_up_info['old_level']['level_name'],
                new_value=level_up_info['new_level']['level_name']
            )
            
            return level_up_info
        
        return None
        
    except Exception as e:
        logger.error(f"Error processing VIP level up for user {user_id}: {e}")
        return None

async def handle_vip_status_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show user's VIP status and benefits"""
    query = update.callback_query
    user_id = query.from_user.id
    lang = context.user_data.get("lang", "en")
    lang_data = LANGUAGES.get(lang, LANGUAGES['en'])
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get user's purchase count
        c.execute("SELECT total_purchases FROM users WHERE user_id = ?", (user_id,))
        user_result = c.fetchone()
        
        if not user_result:
            await query.answer("User data not found", show_alert=True)
            return
        
        purchases = user_result['total_purchases']
        
        # Get current VIP level
        current_level = VIPManager.get_user_vip_level(purchases)
        next_level = VIPManager.get_next_level_info(purchases)
        
        msg = f"👑 **Your VIP Status**\n\n"
        msg += f"**Current Level:** {current_level['level_emoji']} {current_level['level_name']}\n"
        msg += f"**Total Purchases:** {purchases}\n\n"
        
        # Show current benefits
        if current_level['benefits']:
            msg += f"🎁 **Your Benefits:**\n"
            for benefit in current_level['benefits']:
                msg += f"• {benefit}\n"
        
        if current_level['discount_percentage'] > 0:
            msg += f"\n💰 **VIP Discount:** {current_level['discount_percentage']}% on all purchases!\n"
        
        # Show progress to next level
        if next_level:
            purchases_needed = next_level['purchases_needed']
            msg += f"\n🎯 **Next Level:** {next_level['level_emoji']} {next_level['level_name']}\n"
            msg += f"**Purchases needed:** {purchases_needed}\n\n"
            
            # Show what they'll get
            if next_level['benefits']:
                msg += f"🌟 **Upcoming Benefits:**\n"
                for benefit in next_level['benefits']:
                    msg += f"• {benefit}\n"
            
            if next_level['discount_percentage'] > current_level['discount_percentage']:
                msg += f"\n💎 **Higher Discount:** {next_level['discount_percentage']}% (current: {current_level['discount_percentage']}%)\n"
        else:
            msg += f"\n🏆 **Congratulations!** You've reached the highest VIP level!\n"
        
        # Get VIP history
        c.execute("""
            SELECT old_level_name, new_level_name, level_up_date
            FROM user_vip_history 
            WHERE user_id = ?
            ORDER BY level_up_date DESC
            LIMIT 3
        """, (user_id,))
        
        vip_history = c.fetchall()
        
        if vip_history:
            msg += f"\n📈 **Recent Level Ups:**\n"
            for history in vip_history:
                try:
                    date_str = datetime.fromisoformat(history['level_up_date'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
                except:
                    date_str = "Recent"
                msg += f"• {history['old_level_name']} → {history['new_level_name']} ({date_str})\n"
        
        keyboard = [
            [InlineKeyboardButton("🛍️ Shop Now", callback_data="shop")],
            [InlineKeyboardButton("📊 VIP Perks Info", callback_data="vip_perks_info")],
            [InlineKeyboardButton("⬅️ Back to Profile", callback_data="profile")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error showing VIP status for user {user_id}: {e}")
        await query.edit_message_text(
            "❌ Error loading VIP status. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Profile", callback_data="profile")
            ]])
        )
    finally:
        if conn:
            conn.close()

async def handle_vip_perks_info(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show detailed information about all VIP levels and perks"""
    query = update.callback_query
    user_id = query.from_user.id
    
    levels = VIPManager.get_all_vip_levels()
    
    msg = "🌟 **VIP System Overview**\n\n"
    msg += "Earn rewards by making purchases and unlock exclusive benefits!\n\n"
    
    for level in levels:
        if not level['is_active']:
            continue
            
        max_purchases = level['max_purchases'] if level['max_purchases'] else "∞"
        
        msg += f"**{level['level_emoji']} {level['level_name']}**\n"
        msg += f"Purchases required: {level['min_purchases']} - {max_purchases}\n"
        
        if level['benefits']:
            msg += f"Benefits:\n"
            for benefit in level['benefits']:
                msg += f"  • {benefit}\n"
        
        if level['discount_percentage'] > 0:
            msg += f"  • {level['discount_percentage']}% discount on all purchases\n"
        
        msg += "\n"
    
    msg += "🎯 **How to Level Up:**\n"
    msg += "• Make more purchases to increase your level\n"
    msg += "• Higher levels unlock better benefits\n"
    msg += "• VIP discounts apply automatically\n"
    msg += "• Level up notifications sent instantly\n"
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Start Shopping", callback_data="shop")],
        [InlineKeyboardButton("👑 My VIP Status", callback_data="vip_status_menu")],
        [InlineKeyboardButton("⬅️ Back to Profile", callback_data="profile")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_vip_edit_level(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle VIP level editing"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid level ID", show_alert=True)
        return
    
    level_id = int(params[0])
    levels = VIPManager.get_all_vip_levels()
    level = next((l for l in levels if l['id'] == level_id), None)
    
    if not level:
        await query.answer("Level not found", show_alert=True)
        return
    
    max_purchases = level['max_purchases'] if level['max_purchases'] else "∞"
    
    msg = f"✏️ **Edit VIP Level**\n\n"
    msg += f"**{level['level_emoji']} {level['level_name']}**\n\n"
    msg += f"📊 **Current Settings:**\n"
    msg += f"• Purchases: {level['min_purchases']} - {max_purchases}\n"
    msg += f"• Discount: {level['discount_percentage']}%\n"
    msg += f"• Benefits: {len(level['benefits'])}\n"
    msg += f"• Status: {'✅ Active' if level['is_active'] else '❌ Inactive'}\n\n"
    msg += "Choose what to edit:"
    
    keyboard = [
        [InlineKeyboardButton("📝 Edit Name", callback_data=f"vip_edit_name|{level_id}")],
        [InlineKeyboardButton("😀 Edit Emoji", callback_data=f"vip_edit_emoji|{level_id}")],
        [InlineKeyboardButton("🔢 Edit Requirements", callback_data=f"vip_edit_requirements|{level_id}")],
        [InlineKeyboardButton("💰 Edit Discount", callback_data=f"vip_edit_discount|{level_id}")],
        [InlineKeyboardButton("🎁 Edit Benefits", callback_data=f"vip_edit_benefits|{level_id}")],
        [InlineKeyboardButton("🔄 Toggle Active", callback_data=f"vip_toggle_active|{level_id}")],
        [InlineKeyboardButton("🗑️ Delete Level", callback_data=f"vip_delete_level|{level_id}")],
        [InlineKeyboardButton("⬅️ Back to Levels", callback_data="vip_manage_levels")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_vip_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show VIP analytics dashboard"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    stats = VIPManager.get_vip_statistics()
    
    msg = "📊 **VIP Analytics Dashboard**\n\n"
    
    if stats['total_users'] > 0:
        msg += f"👥 **Total Customers:** {stats['total_users']}\n\n"
        
        msg += f"📈 **Level Distribution:**\n"
        for level in stats['level_distribution']:
            percentage = (level['user_count'] / stats['total_users'] * 100) if stats['total_users'] > 0 else 0
            msg += f"• {level['level_emoji']} {level['level_name']}: {level['user_count']} ({percentage:.1f}%)\n"
        
        if stats['recent_levelups']:
            msg += f"\n🎉 **Recent Level Ups:**\n"
            for levelup in stats['recent_levelups'][:5]:
                try:
                    date_str = datetime.fromisoformat(levelup['date'].replace('Z', '+00:00')).strftime('%m-%d')
                except:
                    date_str = "Recent"
                msg += f"• @{levelup['username']}: {levelup['new_level']} ({date_str})\n"
    else:
        msg += "No customer data available yet."
    
    keyboard = [
        [InlineKeyboardButton("📋 Export Data", callback_data="vip_export_analytics")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="vip_analytics")],
        [InlineKeyboardButton("⬅️ Back to VIP Menu", callback_data="vip_management_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_vip_manage_benefits(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Manage VIP benefits system"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    msg = "🎁 **VIP Benefits Management**\n\n"
    msg += "Configure benefits for each VIP level:\n\n"
    msg += "💡 **Available Benefit Types:**\n"
    msg += "• Discount percentages\n"
    msg += "• Priority support\n"
    msg += "• Early access to products\n"
    msg += "• Exclusive product access\n"
    msg += "• Free shipping\n"
    msg += "• Custom rewards\n\n"
    msg += "Select a VIP level to configure its benefits:"
    
    levels = VIPManager.get_all_vip_levels()
    keyboard = []
    
    for level in levels:
        if level['is_active']:
            keyboard.append([InlineKeyboardButton(
                f"{level['level_emoji']} {level['level_name']} ({len(level['benefits'])} benefits)",
                callback_data=f"vip_configure_benefits|{level['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to VIP Menu", callback_data="vip_management_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_vip_list_customers(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """List VIP customers"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get top customers by purchase count
        c.execute("""
            SELECT user_id, username, total_purchases, balance
            FROM users 
            WHERE total_purchases > 0
            ORDER BY total_purchases DESC
            LIMIT 20
        """)
        
        customers = c.fetchall()
        
        msg = "👑 **VIP Customer List**\n\n"
        
        if not customers:
            msg += "No customers with purchases found."
        else:
            msg += f"Top {len(customers)} customers by purchase count:\n\n"
            
            for i, customer in enumerate(customers, 1):
                username = customer['username'] or f"ID_{customer['user_id']}"
                purchases = customer['total_purchases']
                balance = format_currency(customer['balance'])
                
                # Get VIP level
                level_info = VIPManager.get_user_vip_level(purchases)
                
                msg += f"{i}. {level_info['level_emoji']} @{username}\n"
                msg += f"   Purchases: {purchases} | Balance: {balance}\n"
                msg += f"   Level: {level_info['level_name']}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh List", callback_data="vip_list_customers")],
            [InlineKeyboardButton("📊 Analytics", callback_data="vip_analytics")],
            [InlineKeyboardButton("⬅️ Back to VIP Menu", callback_data="vip_management_menu")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error listing VIP customers: {e}")
        await query.edit_message_text(
            "❌ Error loading customer list.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to VIP Menu", callback_data="vip_management_menu")
            ]])
        )
    finally:
        if conn:
            conn.close()

# --- END OF FILE vip_system.py ---
