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
    msg += "Choose the type of A/B test you want to create:\n\n"
    msg += "🔘 **Button Text Test** - Compare different button labels\n"
    msg += "📱 **Message Layout Test** - Test message formats\n"
    msg += "🎯 **Feature Toggle Test** - Test new features\n"
    msg += "💰 **Pricing Test** - Test different price displays\n"
    msg += "🎨 **UI Element Test** - Test interface changes\n\n"
    msg += "Select a test type to get started:"
    
    keyboard = [
        [InlineKeyboardButton("🔘 Button Text Test", callback_data="ab_create_button_test")],
        [InlineKeyboardButton("📱 Message Layout Test", callback_data="ab_create_layout_test")],
        [InlineKeyboardButton("🎯 Feature Toggle Test", callback_data="ab_create_feature_test")],
        [InlineKeyboardButton("💰 Pricing Test", callback_data="ab_create_pricing_test")],
        [InlineKeyboardButton("🎨 UI Element Test", callback_data="ab_create_ui_test")],
        [InlineKeyboardButton("⬅️ Back to A/B Testing", callback_data="ab_testing_menu")]
    ]
    
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
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get test results
        c.execute("""
            SELECT test_name, variant_a, variant_b, participants_a, participants_b, 
                   conversions_a, conversions_b, status, created_at, ended_at
            FROM ab_tests 
            WHERE status IN ('completed', 'active')
            ORDER BY created_at DESC
            LIMIT 10
        """)
        tests = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error getting A/B test results: {e}")
        tests = []
    finally:
        if conn:
            conn.close()
    
    msg = "📊 **A/B Test Results Dashboard**\n\n"
    
    if not tests:
        msg += "❌ **No Test Results Found**\n\n"
        msg += "Create and run A/B tests to see results here.\n"
        msg += "Results will show conversion rates, statistical significance, and recommendations."
        
        keyboard = [
            [InlineKeyboardButton("➕ Create First Test", callback_data="ab_create_test")],
            [InlineKeyboardButton("⬅️ Back to A/B Testing", callback_data="ab_testing_menu")]
        ]
    else:
        msg += f"Found {len(tests)} test results:\n\n"
        
        for test in tests[:5]:  # Show top 5 results
            # Calculate conversion rates
            conv_rate_a = (test['conversions_a'] / test['participants_a'] * 100) if test['participants_a'] > 0 else 0
            conv_rate_b = (test['conversions_b'] / test['participants_b'] * 100) if test['participants_b'] > 0 else 0
            
            # Determine winner
            if conv_rate_b > conv_rate_a:
                winner = f"🏆 Variant B (+{conv_rate_b - conv_rate_a:.1f}%)"
            elif conv_rate_a > conv_rate_b:
                winner = f"🏆 Variant A (+{conv_rate_a - conv_rate_b:.1f}%)"
            else:
                winner = "🤝 Tie"
            
            status_emoji = "✅" if test['status'] == 'completed' else "🔄"
            
            msg += f"{status_emoji} **{test['test_name'][:25]}**\n"
            msg += f"   A: {conv_rate_a:.1f}% ({test['participants_a']} users)\n"
            msg += f"   B: {conv_rate_b:.1f}% ({test['participants_b']} users)\n"
            msg += f"   {winner}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("📈 Detailed Analysis", callback_data="ab_detailed_analysis")],
            [InlineKeyboardButton("📋 Export Results", callback_data="ab_export_results")],
            [InlineKeyboardButton("🔄 Refresh Data", callback_data="ab_test_results")],
            [InlineKeyboardButton("⬅️ Back to A/B Testing", callback_data="ab_testing_menu")]
        ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- Missing A/B Test Template Handlers ---

async def handle_ab_template_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Use button text A/B test template"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    await query.answer("Button text template coming soon!", show_alert=False)
    await query.edit_message_text("🔘 Button text A/B test template coming soon!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="ab_test_templates")]]))

async def handle_ab_template_layout(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Use layout A/B test template"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    await query.answer("Layout template coming soon!", show_alert=False)
    await query.edit_message_text("🎨 Layout A/B test template coming soon!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="ab_test_templates")]]))

# --- Additional A/B Test Creation Handlers ---

async def handle_ab_create_button_test(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Create button text A/B test"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    # Set up test creation state
    context.user_data['ab_test_creation'] = {
        'type': 'button_text',
        'step': 'name'
    }
    context.user_data['state'] = 'awaiting_ab_test_name'
    
    msg = "🔘 **Create Button Text A/B Test**\n\n"
    msg += "This test will compare two different button labels to see which gets more clicks.\n\n"
    msg += "**Examples:**\n"
    msg += "• 'Buy Now' vs 'Add to Cart'\n"
    msg += "• 'Get Started' vs 'Try Free'\n"
    msg += "• 'Learn More' vs 'Discover'\n\n"
    msg += "Please enter a name for this test:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="ab_create_test")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ab_create_layout_test(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Create layout A/B test"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['ab_test_creation'] = {
        'type': 'layout',
        'step': 'name'
    }
    context.user_data['state'] = 'awaiting_ab_test_name'
    
    msg = "📱 **Create Message Layout A/B Test**\n\n"
    msg += "This test will compare two different message layouts or formats.\n\n"
    msg += "**Examples:**\n"
    msg += "• Long detailed description vs short summary\n"
    msg += "• Text with emojis vs plain text\n"
    msg += "• Bullet points vs paragraphs\n\n"
    msg += "Please enter a name for this test:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="ab_create_test")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ab_create_feature_test(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Create feature toggle A/B test"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['ab_test_creation'] = {
        'type': 'feature_toggle',
        'step': 'name'
    }
    context.user_data['state'] = 'awaiting_ab_test_name'
    
    msg = "🎯 **Create Feature Toggle A/B Test**\n\n"
    msg += "This test will show/hide a feature for different user groups.\n\n"
    msg += "**Examples:**\n"
    msg += "• Show/hide referral program button\n"
    msg += "• Enable/disable VIP badges\n"
    msg += "• Show/hide stock quantities\n\n"
    msg += "Please enter a name for this test:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="ab_create_test")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ab_create_pricing_test(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Create pricing A/B test"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['ab_test_creation'] = {
        'type': 'pricing',
        'step': 'name'
    }
    context.user_data['state'] = 'awaiting_ab_test_name'
    
    msg = "💰 **Create Pricing Display A/B Test**\n\n"
    msg += "This test will compare different ways of displaying prices.\n\n"
    msg += "**Examples:**\n"
    msg += "• Show/hide original price with discount\n"
    msg += "• Display price per unit vs total price\n"
    msg += "• Show/hide 'Save X%' labels\n\n"
    msg += "Please enter a name for this test:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="ab_create_test")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ab_create_ui_test(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Create UI element A/B test"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['ab_test_creation'] = {
        'type': 'ui_element',
        'step': 'name'
    }
    context.user_data['state'] = 'awaiting_ab_test_name'
    
    msg = "🎨 **Create UI Element A/B Test**\n\n"
    msg += "This test will compare different user interface elements.\n\n"
    msg += "**Examples:**\n"
    msg += "• Different button colors or styles\n"
    msg += "• Icon vs text navigation\n"
    msg += "• Grid vs list product layout\n\n"
    msg += "Please enter a name for this test:"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="ab_create_test")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ab_test_name_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle A/B test name input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get("state") != "awaiting_ab_test_name":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid test name.", parse_mode=None)
        return
    
    test_name = update.message.text.strip()
    
    if len(test_name) < 3:
        await send_message_with_retry(context.bot, chat_id, "❌ Test name must be at least 3 characters long.", parse_mode=None)
        return
    
    # Store test name and create the test
    test_data = context.user_data.get('ab_test_creation', {})
    test_type = test_data.get('type', 'unknown')
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Create the A/B test
        c.execute("""
            INSERT INTO ab_tests 
            (test_name, test_type, variant_a, variant_b, status, participants_a, participants_b,
             conversions_a, conversions_b, created_at, target_audience)
            VALUES (?, ?, ?, ?, 'draft', 0, 0, 0, 0, ?, 'all_users')
        """, (
            test_name,
            test_type,
            f"Variant A ({test_type})",
            f"Variant B ({test_type})",
            datetime.now().isoformat()
        ))
        
        conn.commit()
        
        # Clear state
        context.user_data.pop('state', None)
        context.user_data.pop('ab_test_creation', None)
        
        msg = f"✅ **A/B Test Created Successfully!**\n\n"
        msg += f"**Test Name:** {test_name}\n"
        msg += f"**Type:** {test_type.replace('_', ' ').title()}\n"
        msg += f"**Status:** Draft\n\n"
        msg += "Your A/B test has been created! You can now configure variants and start the test."
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Configure Test", callback_data="ab_configure_test")],
            [InlineKeyboardButton("📊 View Tests", callback_data="ab_view_tests")],
            [InlineKeyboardButton("🏠 A/B Testing Menu", callback_data="ab_testing_menu")]
        ]
        
        await send_message_with_retry(context.bot, chat_id, msg, 
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error creating A/B test: {e}")
        await send_message_with_retry(context.bot, chat_id, "❌ Error creating test. Please try again.", parse_mode=None)
    finally:
        if conn:
            conn.close()

async def handle_ab_detailed_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show detailed A/B test analysis"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    msg = "📈 **Detailed A/B Test Analysis**\n\n"
    msg += "Advanced statistical analysis of your A/B tests:\n\n"
    msg += "📊 **Statistical Significance**\n"
    msg += "• Confidence intervals\n"
    msg += "• P-values and significance levels\n"
    msg += "• Sample size recommendations\n\n"
    msg += "📈 **Performance Metrics**\n"
    msg += "• Conversion rate trends\n"
    msg += "• User engagement patterns\n"
    msg += "• Revenue impact analysis\n\n"
    msg += "🎯 **Recommendations**\n"
    msg += "• When to end tests\n"
    msg += "• Implementation suggestions\n"
    msg += "• Next test ideas"
    
    keyboard = [
        [InlineKeyboardButton("📋 Generate Report", callback_data="ab_generate_report")],
        [InlineKeyboardButton("⬅️ Back to Results", callback_data="ab_test_results")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_ab_export_results(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Export A/B test results"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all test data for export
        c.execute("""
            SELECT test_name, test_type, variant_a, variant_b, 
                   participants_a, participants_b, conversions_a, conversions_b,
                   status, created_at, ended_at
            FROM ab_tests
            ORDER BY created_at DESC
        """)
        tests = c.fetchall()
        
        if not tests:
            await query.answer("No tests to export", show_alert=True)
            return
        
        # Create export summary
        export_data = f"📋 **A/B Test Results Export**\n"
        export_data += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        export_data += f"Total Tests: {len(tests)}\n\n"
        
        for test in tests[:10]:  # Export top 10 tests
            conv_rate_a = (test['conversions_a'] / test['participants_a'] * 100) if test['participants_a'] > 0 else 0
            conv_rate_b = (test['conversions_b'] / test['participants_b'] * 100) if test['participants_b'] > 0 else 0
            
            export_data += f"**{test['test_name']}** ({test['test_type']})\n"
            export_data += f"• Variant A: {conv_rate_a:.1f}% ({test['participants_a']} users)\n"
            export_data += f"• Variant B: {conv_rate_b:.1f}% ({test['participants_b']} users)\n"
            export_data += f"• Status: {test['status']}\n\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Back to Results", callback_data="ab_test_results")]]
        await query.edit_message_text(export_data, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error exporting A/B test results: {e}")
        await query.answer("Export failed", show_alert=True)
    finally:
        if conn:
            conn.close()

# --- END OF FILE ab_testing.py ---
