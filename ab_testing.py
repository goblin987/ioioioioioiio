# --- START OF FILE ab_testing.py ---

import logging
import sqlite3
import json
import random
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils import get_db_connection, is_primary_admin, send_message_with_retry

logger = logging.getLogger(__name__)

# --- A/B Testing Core Functions ---

class ABTestManager:
    """Manages A/B testing functionality."""
    
    @staticmethod
    def get_user_variant(test_name: str, user_id: int) -> Optional[str]:
        """
        Gets the variant assigned to a user for a specific test.
        If user is not assigned, assigns them to a variant.
        """
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Check if test exists and is active
            c.execute("""
                SELECT id, variant_a_config, variant_b_config 
                FROM ab_tests 
                WHERE test_name = ? AND active = 1
            """, (test_name,))
            
            test = c.fetchone()
            if not test:
                return None  # Test doesn't exist or is inactive
            
            test_id = test['id']
            
            # Check if user already has an assignment
            c.execute("""
                SELECT variant FROM ab_test_assignments 
                WHERE test_id = ? AND user_id = ?
            """, (test_id, user_id))
            
            existing_assignment = c.fetchone()
            if existing_assignment:
                return existing_assignment['variant']
            
            # Assign user to a variant using deterministic hash
            # This ensures consistent assignment across sessions
            hash_input = f"{test_name}_{user_id}".encode('utf-8')
            hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
            variant = 'A' if hash_value % 2 == 0 else 'B'
            
            # Store the assignment
            c.execute("""
                INSERT INTO ab_test_assignments 
                (test_id, user_id, variant, assigned_at)
                VALUES (?, ?, ?, ?)
            """, (test_id, user_id, variant, datetime.now(timezone.utc).isoformat()))
            
            conn.commit()
            logger.debug(f"Assigned user {user_id} to variant {variant} for test {test_name}")
            return variant
            
        except Exception as e:
            logger.error(f"Error getting user variant: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_variant_config(test_name: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Gets the configuration for the user's assigned variant."""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            variant = ABTestManager.get_user_variant(test_name, user_id)
            if not variant:
                return None
            
            # Get the configuration for this variant
            config_column = 'variant_a_config' if variant == 'A' else 'variant_b_config'
            c.execute(f"""
                SELECT {config_column} FROM ab_tests 
                WHERE test_name = ? AND active = 1
            """, (test_name,))
            
            result = c.fetchone()
            if result and result[config_column]:
                return json.loads(result[config_column])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting variant config: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def track_event(test_name: str, user_id: int, event_type: str, event_value: float = None):
        """Tracks a conversion event for A/B testing."""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Get test and user's variant
            c.execute("""
                SELECT t.id, a.variant 
                FROM ab_tests t
                JOIN ab_test_assignments a ON t.id = a.test_id
                WHERE t.test_name = ? AND a.user_id = ? AND t.active = 1
            """, (test_name, user_id))
            
            result = c.fetchone()
            if not result:
                logger.debug(f"No active test assignment found for {test_name}, user {user_id}")
                return
            
            test_id, variant = result['id'], result['variant']
            
            # Record the event
            c.execute("""
                INSERT INTO ab_test_events 
                (test_id, user_id, event_type, event_value, created_at, variant)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                test_id, user_id, event_type, event_value,
                datetime.now(timezone.utc).isoformat(), variant
            ))
            
            conn.commit()
            logger.debug(f"Tracked event {event_type} for user {user_id}, test {test_name}, variant {variant}")
            
        except Exception as e:
            logger.error(f"Error tracking A/B test event: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_test_results(test_name: str) -> Dict[str, Any]:
        """Gets the current results for an A/B test."""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Get test info
            c.execute("""
                SELECT id, description, target_metric, min_sample_size, created_at
                FROM ab_tests WHERE test_name = ?
            """, (test_name,))
            
            test = c.fetchone()
            if not test:
                return {}
            
            test_id = test['id']
            
            # Get assignment counts
            c.execute("""
                SELECT variant, COUNT(*) as count
                FROM ab_test_assignments 
                WHERE test_id = ?
                GROUP BY variant
            """, (test_id,))
            
            assignments = {row['variant']: row['count'] for row in c.fetchall()}
            
            # Get event statistics
            c.execute("""
                SELECT 
                    variant,
                    event_type,
                    COUNT(*) as event_count,
                    COUNT(DISTINCT user_id) as unique_users,
                    AVG(event_value) as avg_value,
                    SUM(event_value) as total_value
                FROM ab_test_events 
                WHERE test_id = ?
                GROUP BY variant, event_type
            """, (test_id,))
            
            events = {}
            for row in c.fetchall():
                variant = row['variant']
                if variant not in events:
                    events[variant] = {}
                events[variant][row['event_type']] = {
                    'count': row['event_count'],
                    'unique_users': row['unique_users'],
                    'avg_value': row['avg_value'],
                    'total_value': row['total_value']
                }
            
            # Calculate conversion rates
            conversion_rates = {}
            for variant in ['A', 'B']:
                assigned = assignments.get(variant, 0)
                if assigned > 0 and variant in events:
                    target_events = events[variant].get(test['target_metric'], {})
                    converted = target_events.get('unique_users', 0)
                    conversion_rates[variant] = (converted / assigned) * 100
                else:
                    conversion_rates[variant] = 0
            
            return {
                'test_info': dict(test),
                'assignments': assignments,
                'events': events,
                'conversion_rates': conversion_rates,
                'total_users': sum(assignments.values()),
                'is_significant': sum(assignments.values()) >= test['min_sample_size']
            }
            
        except Exception as e:
            logger.error(f"Error getting test results: {e}")
            return {}
        finally:
            if conn:
                conn.close()

# --- UI Helper Functions ---

def apply_ab_test_ui(test_name: str, user_id: int, base_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies A/B test configuration to UI elements.
    Returns modified config based on user's variant.
    """
    variant_config = ABTestManager.get_variant_config(test_name, user_id)
    if not variant_config:
        return base_config
    
    # Merge variant config with base config
    result = base_config.copy()
    result.update(variant_config)
    return result

def get_test_button_text(test_name: str, user_id: int, default_text: str, variant_texts: Dict[str, str]) -> str:
    """Gets button text based on A/B test variant."""
    variant = ABTestManager.get_user_variant(test_name, user_id)
    if variant and variant in variant_texts:
        return variant_texts[variant]
    return default_text

def track_button_click(test_name: str, user_id: int, button_name: str):
    """Tracks a button click event for A/B testing."""
    ABTestManager.track_event(test_name, user_id, f"button_click_{button_name}")

def track_purchase(test_name: str, user_id: int, amount: float):
    """Tracks a purchase event for A/B testing."""
    ABTestManager.track_event(test_name, user_id, "purchase", amount)

def track_page_view(test_name: str, user_id: int, page_name: str):
    """Tracks a page view event for A/B testing."""
    ABTestManager.track_event(test_name, user_id, f"page_view_{page_name}")

# --- Admin Handlers ---

async def handle_ab_testing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Shows the A/B testing management menu."""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get active tests count
        c.execute("SELECT COUNT(*) as count FROM ab_tests WHERE active = 1")
        active_tests = c.fetchone()['count']
        
        # Get total users in tests
        c.execute("SELECT COUNT(DISTINCT user_id) as count FROM ab_test_assignments")
        users_in_tests = c.fetchone()['count']
        
        msg = "🧪 **A/B Testing Dashboard**\n\n"
        msg += f"📊 **Overview:**\n"
        msg += f"• Active Tests: {active_tests}\n"
        msg += f"• Users in Tests: {users_in_tests}\n\n"
        msg += "Manage your A/B tests to optimize user experience and conversion rates."
        
        keyboard = [
            [InlineKeyboardButton("📋 View All Tests", callback_data="ab_view_tests")],
            [InlineKeyboardButton("➕ Create New Test", callback_data="ab_create_test")],
            [InlineKeyboardButton("📈 Test Results", callback_data="ab_test_results")],
            [InlineKeyboardButton("⚙️ Test Templates", callback_data="ab_test_templates")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error showing A/B testing menu: {e}")
        await query.edit_message_text(
            "❌ Error loading A/B testing dashboard.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")
            ]])
        )
    finally:
        if conn:
            conn.close()

async def handle_ab_view_tests(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Shows all A/B tests."""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT test_name, description, active, created_at,
                   (SELECT COUNT(*) FROM ab_test_assignments WHERE test_id = ab_tests.id) as user_count
            FROM ab_tests
            ORDER BY created_at DESC
        """)
        
        tests = c.fetchall()
        
        msg = "📋 **All A/B Tests**\n\n"
        
        if not tests:
            msg += "No tests created yet."
        else:
            for test in tests:
                status = "🟢 Active" if test['active'] else "🔴 Inactive"
                msg += f"**{test['test_name']}** {status}\n"
                msg += f"📝 {test['description'] or 'No description'}\n"
                msg += f"👥 {test['user_count']} users assigned\n"
                msg += f"📅 Created: {test['created_at'][:10]}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Create New Test", callback_data="ab_create_test")],
            [InlineKeyboardButton("⬅️ Back to A/B Testing", callback_data="ab_testing_menu")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error viewing A/B tests: {e}")
        await query.edit_message_text(
            "❌ Error loading tests.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to A/B Testing", callback_data="ab_testing_menu")
            ]])
        )
    finally:
        if conn:
            conn.close()

async def create_sample_tests():
    """Creates some sample A/B tests for demonstration."""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Sample test 1: Button text optimization
        sample_test_1 = {
            'test_name': 'checkout_button_text',
            'description': 'Testing different checkout button texts',
            'variant_a_config': json.dumps({
                'button_text': 'Buy Now',
                'button_color': 'green'
            }),
            'variant_b_config': json.dumps({
                'button_text': 'Add to Cart',
                'button_color': 'blue'
            }),
            'target_metric': 'purchase',
            'min_sample_size': 100
        }
        
        # Sample test 2: Product display layout
        sample_test_2 = {
            'test_name': 'product_layout',
            'description': 'Testing different product display layouts',
            'variant_a_config': json.dumps({
                'layout': 'grid',
                'show_prices': True,
                'show_stock': False
            }),
            'variant_b_config': json.dumps({
                'layout': 'list',
                'show_prices': True,
                'show_stock': True
            }),
            'target_metric': 'page_view_product',
            'min_sample_size': 150
        }
        
        for test in [sample_test_1, sample_test_2]:
            try:
                c.execute("""
                    INSERT INTO ab_tests 
                    (test_name, description, variant_a_config, variant_b_config, 
                     active, created_at, target_metric, min_sample_size)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """, (
                    test['test_name'], test['description'],
                    test['variant_a_config'], test['variant_b_config'],
                    datetime.now(timezone.utc).isoformat(),
                    test['target_metric'], test['min_sample_size']
                ))
            except sqlite3.IntegrityError:
                # Test already exists
                pass
        
        conn.commit()
        logger.info("Sample A/B tests created")
        
    except Exception as e:
        logger.error(f"Error creating sample tests: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

async def handle_ab_create_test(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Create a new A/B test"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    msg = "➕ **Create New A/B Test**\n\n"
    msg += "Coming soon! Create custom A/B tests including:\n\n"
    msg += "• Button text variations\n"
    msg += "• Layout experiments\n"
    msg += "• Color scheme tests\n"
    msg += "• Message format tests\n"
    msg += "• Pricing display tests\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to A/B Testing", callback_data="ab_testing_menu")]]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ab_test_templates(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show A/B test templates"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    msg = "📋 **A/B Test Templates**\n\n"
    msg += "Pre-built test templates for common scenarios:\n\n"
    msg += "🔘 **Button Text Test**\n"
    msg += "   Compare 'Buy Now' vs 'Add to Cart'\n\n"
    msg += "🎨 **Layout Test**\n"
    msg += "   Grid vs List product display\n\n"
    msg += "💰 **Price Display Test**\n"
    msg += "   Show/hide stock numbers\n\n"
    msg += "📱 **Mobile Optimization**\n"
    msg += "   Different mobile layouts\n"
    
    keyboard = [
        [InlineKeyboardButton("🔘 Use Button Text Template", callback_data="ab_template_button_text")],
        [InlineKeyboardButton("🎨 Use Layout Template", callback_data="ab_template_layout")],
        [InlineKeyboardButton("⬅️ Back to A/B Testing", callback_data="ab_testing_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ab_test_results(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show A/B test results"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    # Use existing handle_ab_view_tests for now
    await handle_ab_view_tests(update, context, params)

# --- END OF FILE ab_testing.py ---
