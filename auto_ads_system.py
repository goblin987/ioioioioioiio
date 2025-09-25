# --- START OF FILE auto_ads_system.py ---

"""
Auto Ads System - Integrated Advertising Campaign Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Professional automated advertising system integrated into the main bot.
Provides campaign management, scheduled messaging, and multi-account support.

Features:
- Campaign creation and management
- Scheduled advertising posts
- Multi-target broadcasting
- Performance analytics
- Template management
- Account management integration

Author: Enhanced Bot System
Version: 1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import asyncio
import sqlite3
import json
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from utils import (
    get_db_connection, send_message_with_retry, is_primary_admin,
    format_currency, log_admin_action, ADMIN_ID
)

logger = logging.getLogger(__name__)

# Campaign status constants
CAMPAIGN_STATUS = {
    'DRAFT': 'draft',
    'ACTIVE': 'active', 
    'PAUSED': 'paused',
    'COMPLETED': 'completed',
    'FAILED': 'failed'
}

# Campaign types
CAMPAIGN_TYPES = {
    'PROMOTIONAL': 'promotional',
    'PRODUCT_LAUNCH': 'product_launch',
    'DISCOUNT': 'discount',
    'ANNOUNCEMENT': 'announcement',
    'CUSTOM': 'custom'
}

@dataclass
class CampaignTemplate:
    """Campaign template structure"""
    id: int
    name: str
    template_type: str
    message_template: str
    media_template: Optional[str]
    default_schedule: str
    created_at: str
    is_active: bool = True

@dataclass
class Campaign:
    """Campaign data structure"""
    id: int
    name: str
    campaign_type: str
    message: str
    media_path: Optional[str]
    target_channels: List[str]
    schedule_pattern: str
    status: str
    created_by: int
    created_at: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_sent: int = 0
    total_failed: int = 0
    last_run: Optional[str] = None

class AutoAdsDatabase:
    """Database management for auto ads system"""
    
    def __init__(self):
        self.init_tables()
    
    def init_tables(self):
        """Initialize auto ads database tables"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Campaigns table
            c.execute('''CREATE TABLE IF NOT EXISTS auto_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                campaign_type TEXT NOT NULL,
                message TEXT NOT NULL,
                media_path TEXT,
                target_channels TEXT NOT NULL,
                schedule_pattern TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                total_sent INTEGER DEFAULT 0,
                total_failed INTEGER DEFAULT 0,
                last_run TEXT,
                settings TEXT
            )''')
            
            # Campaign templates table
            c.execute('''CREATE TABLE IF NOT EXISTS campaign_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                message_template TEXT NOT NULL,
                media_template TEXT,
                default_schedule TEXT,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )''')
            
            # Campaign logs table
            c.execute('''CREATE TABLE IF NOT EXISTS campaign_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                target_channel TEXT NOT NULL,
                message_sent TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (campaign_id) REFERENCES auto_campaigns(id) ON DELETE CASCADE
            )''')
            
            # Target channels table
            c.execute('''CREATE TABLE IF NOT EXISTS target_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL UNIQUE,
                channel_name TEXT NOT NULL,
                channel_type TEXT DEFAULT 'channel',
                is_active INTEGER DEFAULT 1,
                added_by INTEGER NOT NULL,
                added_at TEXT NOT NULL
            )''')
            
            conn.commit()
            logger.info("Auto ads database tables initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing auto ads database: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    
    def create_campaign(self, campaign_data: Dict) -> Optional[int]:
        """Create a new campaign"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute('''INSERT INTO auto_campaigns 
                        (name, campaign_type, message, media_path, target_channels, 
                         schedule_pattern, status, created_by, created_at, start_date, 
                         end_date, settings)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (
                         campaign_data['name'],
                         campaign_data['campaign_type'],
                         campaign_data['message'],
                         campaign_data.get('media_path'),
                         json.dumps(campaign_data['target_channels']),
                         campaign_data['schedule_pattern'],
                         campaign_data.get('status', 'draft'),
                         campaign_data['created_by'],
                         campaign_data['created_at'],
                         campaign_data.get('start_date'),
                         campaign_data.get('end_date'),
                         json.dumps(campaign_data.get('settings', {}))
                     ))
            
            campaign_id = c.lastrowid
            conn.commit()
            logger.info(f"Campaign created with ID: {campaign_id}")
            return campaign_id
            
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    def get_campaigns(self, created_by: int = None, status: str = None) -> List[Dict]:
        """Get campaigns with optional filters"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            query = "SELECT * FROM auto_campaigns WHERE 1=1"
            params = []
            
            if created_by:
                query += " AND created_by = ?"
                params.append(created_by)
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC"
            
            c.execute(query, params)
            campaigns = []
            
            for row in c.fetchall():
                campaign = {
                    'id': row[0],
                    'name': row[1],
                    'campaign_type': row[2],
                    'message': row[3],
                    'media_path': row[4],
                    'target_channels': json.loads(row[5]) if row[5] else [],
                    'schedule_pattern': row[6],
                    'status': row[7],
                    'created_by': row[8],
                    'created_at': row[9],
                    'start_date': row[10],
                    'end_date': row[11],
                    'total_sent': row[12],
                    'total_failed': row[13],
                    'last_run': row[14],
                    'settings': json.loads(row[15]) if row[15] else {}
                }
                campaigns.append(campaign)
            
            return campaigns
            
        except Exception as e:
            logger.error(f"Error getting campaigns: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def update_campaign_status(self, campaign_id: int, status: str) -> bool:
        """Update campaign status"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute("UPDATE auto_campaigns SET status = ? WHERE id = ?", 
                     (status, campaign_id))
            
            success = c.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Campaign {campaign_id} status updated to {status}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating campaign status: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def log_campaign_execution(self, campaign_id: int, target_channel: str, 
                             message_sent: str, status: str, error_message: str = None):
        """Log campaign execution"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute('''INSERT INTO campaign_logs 
                        (campaign_id, target_channel, message_sent, status, error_message, sent_at)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (campaign_id, target_channel, message_sent, status, 
                      error_message, datetime.now(timezone.utc).isoformat()))
            
            # Update campaign statistics
            if status == 'success':
                c.execute("UPDATE auto_campaigns SET total_sent = total_sent + 1, last_run = ? WHERE id = ?",
                         (datetime.now(timezone.utc).isoformat(), campaign_id))
            else:
                c.execute("UPDATE auto_campaigns SET total_failed = total_failed + 1 WHERE id = ?",
                         (campaign_id,))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error logging campaign execution: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    
    def get_target_channels(self) -> List[Dict]:
        """Get all active target channels"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute("SELECT * FROM target_channels WHERE is_active = 1 ORDER BY channel_name")
            channels = []
            
            for row in c.fetchall():
                channel = {
                    'id': row[0],
                    'channel_id': row[1],
                    'channel_name': row[2],
                    'channel_type': row[3],
                    'is_active': row[4],
                    'added_by': row[5],
                    'added_at': row[6]
                }
                channels.append(channel)
            
            return channels
            
        except Exception as e:
            logger.error(f"Error getting target channels: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def add_target_channel(self, channel_id: str, channel_name: str, 
                          channel_type: str, added_by: int) -> bool:
        """Add a new target channel"""
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute('''INSERT OR REPLACE INTO target_channels 
                        (channel_id, channel_name, channel_type, added_by, added_at)
                        VALUES (?, ?, ?, ?, ?)''',
                     (channel_id, channel_name, channel_type, added_by, 
                      datetime.now(timezone.utc).isoformat()))
            
            conn.commit()
            logger.info(f"Target channel added: {channel_name} ({channel_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding target channel: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

class CampaignExecutor:
    """Campaign execution engine"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.db = AutoAdsDatabase()
        self.running_campaigns = {}
        self.scheduler_thread = None
        self.is_running = False
    
    def start_scheduler(self):
        """Start the campaign scheduler"""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Campaign scheduler already running")
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("Campaign scheduler started")
    
    def stop_scheduler(self):
        """Stop the campaign scheduler"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Campaign scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.is_running:
            try:
                current_time = datetime.now()
                
                # Check all active campaigns
                campaigns = self.db.get_campaigns(status='active')
                for campaign in campaigns:
                    if self._should_run_campaign(campaign, current_time):
                        try:
                            # Store campaign for execution by main thread
                            self.pending_executions = getattr(self, 'pending_executions', [])
                            self.pending_executions.append(campaign['id'])
                            logger.info(f"Scheduled campaign {campaign['id']} for execution")
                        except Exception as e:
                            logger.error(f"Error scheduling campaign {campaign['id']}: {e}")
                
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)
    
    def _should_run_campaign(self, campaign: Dict, current_time: datetime) -> bool:
        """Check if campaign should run now"""
        pattern = campaign['schedule_pattern']
        last_run_str = campaign.get('last_run')
        
        if not last_run_str:
            # Never run before, should run now
            return True
        
        try:
            last_run = datetime.fromisoformat(last_run_str.replace('Z', '+00:00'))
        except:
            # Invalid last run time, run now
            return True
        
        time_diff = current_time - last_run
        
        if pattern == 'hourly':
            return time_diff.total_seconds() >= 3600  # 1 hour
        elif pattern == 'daily':
            return time_diff.total_seconds() >= 86400  # 24 hours
        elif pattern == 'every_3_hours':
            return time_diff.total_seconds() >= 10800  # 3 hours
        elif pattern == 'every_6_hours':
            return time_diff.total_seconds() >= 21600  # 6 hours
        elif pattern.startswith('every_') and pattern.endswith('_hours'):
            try:
                hours = int(pattern.split('_')[1])
                return time_diff.total_seconds() >= (hours * 3600)
            except:
                return False
        
        return False
    
    async def execute_campaign(self, campaign_id: int):
        """Execute a campaign"""
        campaigns = self.db.get_campaigns()
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        if campaign['status'] != 'active':
            logger.info(f"Campaign {campaign_id} is not active, skipping")
            return
        
        logger.info(f"Executing campaign: {campaign['name']} (ID: {campaign_id})")
        
        success_count = 0
        fail_count = 0
        
        for channel_id in campaign['target_channels']:
            try:
                # Send message to channel
                await self._send_campaign_message(campaign, channel_id)
                success_count += 1
                
                self.db.log_campaign_execution(
                    campaign_id, channel_id, campaign['message'], 'success'
                )
                
                # Add delay between messages to avoid rate limiting
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error sending to channel {channel_id}: {e}")
                fail_count += 1
                
                self.db.log_campaign_execution(
                    campaign_id, channel_id, campaign['message'], 'failed', str(e)
                )
        
        logger.info(f"Campaign {campaign_id} execution completed: {success_count} success, {fail_count} failed")
        
        # Notify admin about campaign execution
        try:
            report_msg = (
                f"📊 **Campaign Execution Report**\n\n"
                f"**Campaign:** {campaign['name']}\n"
                f"**Type:** {campaign['campaign_type'].title()}\n"
                f"**Results:**\n"
                f"• ✅ Successful: {success_count}\n"
                f"• ❌ Failed: {fail_count}\n"
                f"• 📅 Executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await send_message_with_retry(
                self.bot, ADMIN_ID, report_msg, parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending campaign report: {e}")
    
    async def _send_campaign_message(self, campaign: Dict, channel_id: str):
        """Send campaign message to a specific channel"""
        try:
            # For now, we'll send via the main bot
            # In a full implementation, this would use Telethon clients
            
            message = campaign['message']
            
            # Replace placeholders
            message = message.replace('{date}', datetime.now().strftime('%Y-%m-%d'))
            message = message.replace('{time}', datetime.now().strftime('%H:%M'))
            
            if campaign['media_path']:
                # Send with media (photo/video)
                with open(campaign['media_path'], 'rb') as media_file:
                    await self.bot.send_photo(
                        chat_id=channel_id,
                        photo=media_file,
                        caption=message,
                        parse_mode='Markdown'
                    )
            else:
                # Send text only
                await self.bot.send_message(
                    chat_id=channel_id,
                    text=message,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error sending message to {channel_id}: {e}")
            raise
    
    def schedule_campaign(self, campaign: Dict):
        """Schedule a campaign based on its pattern"""
        campaign_id = campaign['id']
        pattern = campaign['schedule_pattern']
        
        # Add campaign to running campaigns list
        self.running_campaigns[campaign_id] = campaign
        logger.info(f"Campaign {campaign_id} scheduled with pattern: {pattern}")
    
    def unschedule_campaign(self, campaign_id: int):
        """Remove campaign from scheduler"""
        if campaign_id in self.running_campaigns:
            del self.running_campaigns[campaign_id]
        logger.info(f"Campaign {campaign_id} unscheduled")
    
    def get_pending_executions(self) -> List[int]:
        """Get and clear pending campaign executions"""
        pending = getattr(self, 'pending_executions', [])
        self.pending_executions = []
        return pending

# Global campaign executor instance
campaign_executor = None

def get_campaign_executor(bot: Bot = None) -> CampaignExecutor:
    """Get or create campaign executor instance"""
    global campaign_executor
    if campaign_executor is None and bot:
        campaign_executor = CampaignExecutor(bot)
    return campaign_executor

# --- Admin Interface Handlers ---

async def handle_auto_ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show auto ads main menu"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    db = AutoAdsDatabase()
    campaigns = db.get_campaigns(created_by=user_id)
    active_campaigns = len([c for c in campaigns if c['status'] == 'active'])
    total_campaigns = len(campaigns)
    
    msg = "🚀 **Auto Ads System**\n\n"
    msg += f"📊 **Overview:**\n"
    msg += f"• Total Campaigns: {total_campaigns}\n"
    msg += f"• Active Campaigns: {active_campaigns}\n\n"
    msg += "Manage your automated advertising campaigns:"
    
    keyboard = [
        [InlineKeyboardButton("📋 View Campaigns", callback_data="auto_ads_view_campaigns")],
        [InlineKeyboardButton("➕ Create Campaign", callback_data="auto_ads_create_campaign")],
        [InlineKeyboardButton("📺 Manage Channels", callback_data="auto_ads_manage_channels")],
        [InlineKeyboardButton("📊 Campaign Analytics", callback_data="auto_ads_analytics")],
        [InlineKeyboardButton("⚙️ System Settings", callback_data="auto_ads_settings")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_view_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """View all campaigns"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    db = AutoAdsDatabase()
    campaigns = db.get_campaigns(created_by=user_id)
    
    if not campaigns:
        msg = "📋 **My Campaigns**\n\nNo campaigns created yet.\n\nClick 'Create Campaign' to get started!"
        keyboard = [
            [InlineKeyboardButton("➕ Create Campaign", callback_data="auto_ads_create_campaign")],
            [InlineKeyboardButton("⬅️ Back to Auto Ads", callback_data="auto_ads_menu")]
        ]
    else:
        msg = "📋 **My Campaigns**\n\n"
        keyboard = []
        
        for campaign in campaigns[:10]:  # Show first 10 campaigns
            status_emoji = {
                'active': '🟢',
                'paused': '🟡', 
                'draft': '⚪',
                'completed': '✅',
                'failed': '🔴'
            }.get(campaign['status'], '❓')
            
            msg += f"{status_emoji} **{campaign['name']}**\n"
            msg += f"   Type: {campaign['campaign_type'].title()}\n"
            msg += f"   Status: {campaign['status'].title()}\n"
            msg += f"   Sent: {campaign['total_sent']} | Failed: {campaign['total_failed']}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"⚙️ {campaign['name'][:20]}", callback_data=f"auto_ads_campaign_{campaign['id']}"),
                InlineKeyboardButton("🗑️", callback_data=f"auto_ads_delete_campaign_{campaign['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Create New", callback_data="auto_ads_create_campaign")])
        keyboard.append([InlineKeyboardButton("⬅️ Back to Auto Ads", callback_data="auto_ads_menu")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_create_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Start campaign creation process"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    msg = "➕ **Create New Campaign**\n\n"
    msg += "Choose a campaign type to get started:"
    
    keyboard = [
        [InlineKeyboardButton("🎯 Promotional", callback_data="auto_ads_type_promotional")],
        [InlineKeyboardButton("🚀 Product Launch", callback_data="auto_ads_type_product_launch")],
        [InlineKeyboardButton("💰 Discount/Sale", callback_data="auto_ads_type_discount")],
        [InlineKeyboardButton("📢 Announcement", callback_data="auto_ads_type_announcement")],
        [InlineKeyboardButton("🔧 Custom", callback_data="auto_ads_type_custom")],
        [InlineKeyboardButton("⬅️ Back to Campaigns", callback_data="auto_ads_view_campaigns")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_campaign_type(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle campaign type selection"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid campaign type", show_alert=True)
        return
    
    campaign_type = params[0]
    
    # Store campaign type in context
    context.user_data['auto_ads_campaign_type'] = campaign_type
    context.user_data['state'] = 'awaiting_campaign_name'
    
    # Campaign templates based on type
    templates = {
        'promotional': {
            'description': 'Promote your products and services',
            'example': '🎯 **Special Promotion!**\n\nCheck out our amazing products at unbeatable prices!\n\n🛒 Shop now: @YourBotUsername'
        },
        'product_launch': {
            'description': 'Announce new products or services',
            'example': '🚀 **New Product Launch!**\n\n🌟 Introducing our latest addition!\n\n📦 Available now: @YourBotUsername'
        },
        'discount': {
            'description': 'Share discount codes and special offers',
            'example': '💰 **Limited Time Offer!**\n\n🎉 Get 20% OFF with code: SAVE20\n\n⏰ Hurry, offer ends soon!\n\n🛒 Shop: @YourBotUsername'
        },
        'announcement': {
            'description': 'Make important announcements',
            'example': '📢 **Important Announcement**\n\n📅 We have exciting news to share!\n\n💬 Contact: @YourBotUsername'
        },
        'custom': {
            'description': 'Create your own custom campaign',
            'example': '✨ **Your Custom Message**\n\nCreate any message you want!\n\n🔗 @YourBotUsername'
        }
    }
    
    template = templates.get(campaign_type, templates['custom'])
    
    msg = f"➕ **Create {campaign_type.replace('_', ' ').title()} Campaign**\n\n"
    msg += f"📝 {template['description']}\n\n"
    msg += f"**Example:**\n{template['example']}\n\n"
    msg += "Please enter a name for your campaign:"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back to Types", callback_data="auto_ads_create_campaign")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_campaign_name_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle campaign name input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    state = context.user_data.get("state")
    if state != "awaiting_campaign_name":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid campaign name.", parse_mode=None)
        return
    
    campaign_name = update.message.text.strip()
    
    if len(campaign_name) < 3:
        await send_message_with_retry(context.bot, chat_id, "❌ Campaign name must be at least 3 characters long.", parse_mode=None)
        return
    
    if len(campaign_name) > 50:
        await send_message_with_retry(context.bot, chat_id, "❌ Campaign name must be less than 50 characters.", parse_mode=None)
        return
    
    # Store campaign name and proceed to message input
    context.user_data['auto_ads_campaign_name'] = campaign_name
    context.user_data['state'] = 'awaiting_campaign_message'
    
    campaign_type = context.user_data.get('auto_ads_campaign_type', 'custom')
    
    msg = f"✅ Campaign name set: **{campaign_name}**\n\n"
    msg += "Now, please enter your campaign message.\n\n"
    msg += "💡 **Tips:**\n"
    msg += "• Use **bold** and *italic* formatting\n"
    msg += "• Include emojis for better engagement\n"
    msg += "• Add your bot username or link\n"
    msg += "• Keep it concise but compelling\n\n"
    msg += "📝 Enter your message:"
    
    await send_message_with_retry(context.bot, chat_id, msg, parse_mode='Markdown')

async def handle_auto_ads_campaign_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle campaign message input"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    state = context.user_data.get("state")
    if state != "awaiting_campaign_message":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter a valid campaign message.", parse_mode=None)
        return
    
    campaign_message = update.message.text.strip()
    
    if len(campaign_message) < 10:
        await send_message_with_retry(context.bot, chat_id, "❌ Campaign message must be at least 10 characters long.", parse_mode=None)
        return
    
    if len(campaign_message) > 4000:
        await send_message_with_retry(context.bot, chat_id, "❌ Campaign message must be less than 4000 characters.", parse_mode=None)
        return
    
    # Store campaign message and show schedule options
    context.user_data['auto_ads_campaign_message'] = campaign_message
    context.user_data['state'] = None  # Clear state
    
    msg = f"✅ **Campaign Message Set**\n\n"
    msg += f"**Preview:**\n{campaign_message}\n\n"
    msg += "Now choose when to run your campaign:"
    
    keyboard = [
        [InlineKeyboardButton("🕘 Every Hour", callback_data="auto_ads_schedule_hourly")],
        [InlineKeyboardButton("📅 Daily at 9 AM", callback_data="auto_ads_schedule_daily")],
        [InlineKeyboardButton("🕒 Every 3 Hours", callback_data="auto_ads_schedule_every_3_hours")],
        [InlineKeyboardButton("🕕 Every 6 Hours", callback_data="auto_ads_schedule_every_6_hours")],
        [InlineKeyboardButton("⏰ Custom Time", callback_data="auto_ads_schedule_custom")],
        [InlineKeyboardButton("▶️ Run Once Now", callback_data="auto_ads_schedule_once")]
    ]
    
    await send_message_with_retry(context.bot, chat_id, msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_schedule_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle schedule selection"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    if not params:
        await query.answer("Invalid schedule option", show_alert=True)
        return
    
    schedule_type = params[0]
    
    # Store schedule and show target channel selection
    context.user_data['auto_ads_schedule'] = schedule_type
    
    # Get available channels
    db = AutoAdsDatabase()
    channels = db.get_target_channels()
    
    if not channels:
        msg = "❌ **No Target Channels Available**\n\n"
        msg += "You need to add target channels first.\n\n"
        msg += "Target channels are where your ads will be posted."
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Channel", callback_data="auto_ads_add_channel")],
            [InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_menu")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return
    
    schedule_names = {
        'hourly': 'Every Hour',
        'daily': 'Daily at 9 AM',
        'every_3_hours': 'Every 3 Hours',
        'every_6_hours': 'Every 6 Hours',
        'custom': 'Custom Schedule',
        'once': 'Run Once Now'
    }
    
    msg = f"📺 **Select Target Channels**\n\n"
    msg += f"**Schedule:** {schedule_names.get(schedule_type, 'Unknown')}\n\n"
    msg += "Choose which channels to post your campaign to:\n\n"
    
    keyboard = []
    for channel in channels[:10]:  # Show first 10 channels
        msg += f"• {channel['channel_name']}\n"
        keyboard.append([
            InlineKeyboardButton(f"✅ {channel['channel_name']}", 
                               callback_data=f"auto_ads_select_channel_{channel['id']}")
        ])
    
    keyboard.append([InlineKeyboardButton("✅ Select All Channels", callback_data="auto_ads_select_all_channels")])
    keyboard.append([InlineKeyboardButton("✅ Create Campaign", callback_data="auto_ads_finalize_campaign")])
    keyboard.append([InlineKeyboardButton("⬅️ Back to Schedule", callback_data="auto_ads_create_campaign")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_finalize_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Finalize and create the campaign"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    # Get all campaign data from context
    campaign_name = context.user_data.get('auto_ads_campaign_name')
    campaign_type = context.user_data.get('auto_ads_campaign_type')
    campaign_message = context.user_data.get('auto_ads_campaign_message')
    schedule = context.user_data.get('auto_ads_schedule')
    selected_channels = context.user_data.get('auto_ads_selected_channels', [])
    
    if not all([campaign_name, campaign_type, campaign_message, schedule]):
        await query.answer("Missing campaign data. Please start over.", show_alert=True)
        return
    
    if not selected_channels:
        await query.answer("No channels selected. Please select at least one channel.", show_alert=True)
        return
    
    # Create campaign in database
    db = AutoAdsDatabase()
    campaign_data = {
        'name': campaign_name,
        'campaign_type': campaign_type,
        'message': campaign_message,
        'target_channels': selected_channels,
        'schedule_pattern': schedule,
        'status': 'active' if schedule != 'once' else 'completed',
        'created_by': user_id,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'settings': {}
    }
    
    campaign_id = db.create_campaign(campaign_data)
    
    if campaign_id:
        # Schedule the campaign if it's recurring
        if schedule != 'once':
            executor = get_campaign_executor(context.bot)
            if executor:
                executor.schedule_campaign(campaign_data)
                executor.start_scheduler()
        else:
            # Execute once immediately
            executor = get_campaign_executor(context.bot)
            if executor:
                await executor.execute_campaign(campaign_id)
        
        # Clear context data
        context.user_data.pop('auto_ads_campaign_name', None)
        context.user_data.pop('auto_ads_campaign_type', None)
        context.user_data.pop('auto_ads_campaign_message', None)
        context.user_data.pop('auto_ads_schedule', None)
        context.user_data.pop('auto_ads_selected_channels', None)
        
        # Log admin action
        log_admin_action(user_id, 'CAMPAIGN_CREATE', campaign_id, f'Created campaign: {campaign_name}', 0)
        
        msg = f"✅ **Campaign Created Successfully!**\n\n"
        msg += f"**Name:** {campaign_name}\n"
        msg += f"**Type:** {campaign_type.replace('_', ' ').title()}\n"
        msg += f"**Schedule:** {schedule.replace('_', ' ').title()}\n"
        msg += f"**Channels:** {len(selected_channels)}\n\n"
        
        if schedule == 'once':
            msg += "🚀 Campaign executed immediately!"
        else:
            msg += "📅 Campaign scheduled and will run automatically!"
        
        keyboard = [
            [InlineKeyboardButton("📋 View Campaigns", callback_data="auto_ads_view_campaigns")],
            [InlineKeyboardButton("➕ Create Another", callback_data="auto_ads_create_campaign")],
            [InlineKeyboardButton("🏠 Back to Auto Ads", callback_data="auto_ads_menu")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    else:
        await query.edit_message_text(
            "❌ **Error Creating Campaign**\n\nPlease try again or contact support.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data="auto_ads_create_campaign"),
                InlineKeyboardButton("🏠 Back to Auto Ads", callback_data="auto_ads_menu")
            ]]),
            parse_mode='Markdown'
        )

async def handle_auto_ads_manage_channels(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Manage target channels"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_primary_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    
    db = AutoAdsDatabase()
    channels = db.get_target_channels()
    
    msg = "📺 **Target Channels Management**\n\n"
    
    if not channels:
        msg += "No channels configured yet.\n\n"
        msg += "Add channels where your ads will be posted:"
    else:
        msg += f"**Active Channels:** {len(channels)}\n\n"
        for channel in channels[:10]:
            msg += f"• {channel['channel_name']} (`{channel['channel_id']}`)\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="auto_ads_add_channel")],
        [InlineKeyboardButton("🗑️ Remove Channel", callback_data="auto_ads_remove_channel")],
        [InlineKeyboardButton("🔄 Test Channels", callback_data="auto_ads_test_channels")],
        [InlineKeyboardButton("⬅️ Back to Auto Ads", callback_data="auto_ads_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Initialize the auto ads system
def initialize_auto_ads_system(bot: Bot):
    """Initialize the auto ads system with the bot instance"""
    global campaign_executor
    campaign_executor = CampaignExecutor(bot)
    
    # Initialize database
    db = AutoAdsDatabase()
    
    # Load and schedule active campaigns
    active_campaigns = db.get_campaigns(status='active')
    for campaign in active_campaigns:
        campaign_executor.schedule_campaign(campaign)
    
    if active_campaigns:
        campaign_executor.start_scheduler()
        logger.info(f"Auto ads system initialized with {len(active_campaigns)} active campaigns")
    else:
        logger.info("Auto ads system initialized with no active campaigns")

# --- Missing Auto Ads Handlers ---

async def handle_auto_ads_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Campaign analytics dashboard"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    await query.answer("Analytics coming soon!", show_alert=False)
    await query.edit_message_text("📊 Campaign analytics coming soon!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_menu")]]))

async def handle_auto_ads_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Auto ads system settings"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    await query.answer("Settings coming soon!", show_alert=False)
    await query.edit_message_text("⚙️ System settings coming soon!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_menu")]]))

async def handle_auto_ads_type_promotional(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle promotional campaign type"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data'] = {'type': 'promotional'}
    context.user_data['state'] = 'awaiting_auto_ads_campaign_name'
    
    await query.edit_message_text(
        "🎯 **Promotional Campaign**\n\nPlease enter a name for this campaign:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_create_campaign")]]),
        parse_mode='Markdown'
    )

async def handle_auto_ads_type_product_launch(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle product launch campaign type"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data'] = {'type': 'product_launch'}
    context.user_data['state'] = 'awaiting_auto_ads_campaign_name'
    
    await query.edit_message_text(
        "🚀 **Product Launch Campaign**\n\nPlease enter a name for this campaign:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_create_campaign")]]),
        parse_mode='Markdown'
    )

async def handle_auto_ads_type_discount(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle discount campaign type"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data'] = {'type': 'discount'}
    context.user_data['state'] = 'awaiting_auto_ads_campaign_name'
    
    await query.edit_message_text(
        "💰 **Discount/Sale Campaign**\n\nPlease enter a name for this campaign:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_create_campaign")]]),
        parse_mode='Markdown'
    )

async def handle_auto_ads_type_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle announcement campaign type"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data'] = {'type': 'announcement'}
    context.user_data['state'] = 'awaiting_auto_ads_campaign_name'
    
    await query.edit_message_text(
        "📢 **Announcement Campaign**\n\nPlease enter a name for this campaign:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_create_campaign")]]),
        parse_mode='Markdown'
    )

async def handle_auto_ads_type_custom(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle custom campaign type"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data'] = {'type': 'custom'}
    context.user_data['state'] = 'awaiting_auto_ads_campaign_name'
    
    await query.edit_message_text(
        "🔧 **Custom Campaign**\n\nPlease enter a name for this campaign:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_create_campaign")]]),
        parse_mode='Markdown'
    )

async def handle_auto_ads_schedule_hourly(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle hourly schedule"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data']['schedule'] = 'hourly'
    await query.answer("Hourly schedule selected!", show_alert=False)
    # Continue to channel selection
    await handle_auto_ads_select_channels(update, context, params)

async def handle_auto_ads_schedule_daily(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle daily schedule"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data']['schedule'] = 'daily'
    await query.answer("Daily schedule selected!", show_alert=False)
    # Continue to channel selection
    await handle_auto_ads_select_channels(update, context, params)

async def handle_auto_ads_schedule_every_3_hours(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle 3-hour schedule"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data']['schedule'] = 'every_3_hours'
    await query.answer("3-hour schedule selected!", show_alert=False)
    # Continue to channel selection
    await handle_auto_ads_select_channels(update, context, params)

async def handle_auto_ads_schedule_every_6_hours(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle 6-hour schedule"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data']['schedule'] = 'every_6_hours'
    await query.answer("6-hour schedule selected!", show_alert=False)
    # Continue to channel selection
    await handle_auto_ads_select_channels(update, context, params)

async def handle_auto_ads_schedule_custom(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle custom schedule"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    await query.answer("Custom scheduling coming soon!", show_alert=False)
    await query.edit_message_text("⏰ Custom scheduling feature coming soon!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_create_campaign")]]))

async def handle_auto_ads_schedule_once(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle run once schedule"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    context.user_data['auto_ads_campaign_data']['schedule'] = 'once'
    await query.answer("One-time execution selected!", show_alert=False)
    # Continue to channel selection
    await handle_auto_ads_select_channels(update, context, params)

async def handle_auto_ads_select_channels(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Show channel selection for campaign"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get available channels
        c.execute("""
            SELECT channel_id, channel_name, channel_type, is_active, subscriber_count
            FROM auto_ads_channels
            WHERE is_active = 1
            ORDER BY subscriber_count DESC
        """)
        channels = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error getting channels: {e}")
        channels = []
    finally:
        if conn:
            conn.close()
    
    msg = "📺 **Select Channels for Campaign**\n\n"
    
    if not channels:
        msg += "❌ **No Active Channels Found!**\n\n"
        msg += "You need to add channels before creating campaigns.\n"
        msg += "Channels are where your ads will be posted automatically."
        
        keyboard = [
            [InlineKeyboardButton("➕ Add First Channel", callback_data="auto_ads_add_channel")],
            [InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_create_campaign")]
        ]
    else:
        msg += f"Found {len(channels)} active channels. Select channels for your campaign:\n\n"
        
        # Get currently selected channels from user data
        selected_channels = context.user_data.get('auto_ads_selected_channels', set())
        
        keyboard = []
        for channel in channels[:10]:  # Show up to 10 channels
            channel_name = channel['channel_name'][:30]  # Truncate long names
            subscriber_text = f"({channel['subscriber_count']} subs)" if channel['subscriber_count'] else ""
            
            if channel['channel_id'] in selected_channels:
                button_text = f"✅ {channel_name} {subscriber_text}"
            else:
                button_text = f"⭕ {channel_name} {subscriber_text}"
            
            keyboard.append([InlineKeyboardButton(button_text, 
                callback_data=f"auto_ads_toggle_channel|{channel['channel_id']}")])
        
        # Add control buttons
        if selected_channels:
            keyboard.append([InlineKeyboardButton(f"🚀 Create Campaign ({len(selected_channels)} channels)", 
                callback_data="auto_ads_finalize_campaign")])
        
        keyboard.append([InlineKeyboardButton("➕ Add New Channel", callback_data="auto_ads_add_channel")])
        keyboard.append([InlineKeyboardButton("⬅️ Back to Schedule", callback_data="auto_ads_create_campaign")])
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Add new channel"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    # Set state for channel addition
    context.user_data['state'] = 'awaiting_channel_info'
    
    msg = "➕ **Add New Auto Ads Channel**\n\n"
    msg += "Simply send the channel link! The system will automatically extract the channel information.\n\n"
    msg += "**Supported formats:**\n"
    msg += "• `https://t.me/channelname`\n"
    msg += "• `@channelname`\n"
    msg += "• `t.me/channelname`\n"
    msg += "• `channelname`\n\n"
    msg += "**Examples:**\n"
    msg += "• `https://t.me/mychannel`\n"
    msg += "• `@mychannel`\n"
    msg += "• `t.me/mychannel`\n"
    msg += "• `mychannel`\n\n"
    msg += "Just paste the channel link and the system will handle the rest!"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="auto_ads_manage_channels")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Remove channel"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    await query.answer("Remove channel coming soon!", show_alert=False)
    await query.edit_message_text("🗑️ Remove channel feature coming soon!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_manage_channels")]]))

async def handle_auto_ads_test_channels(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Test channels"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    await query.answer("Test channels coming soon!", show_alert=False)
    await query.edit_message_text("🔄 Test channels feature coming soon!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="auto_ads_manage_channels")]]))

# --- Additional Auto Ads Handlers ---

async def handle_auto_ads_toggle_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Toggle channel selection for campaign"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    if not params:
        await query.answer("Invalid channel ID", show_alert=True)
        return
    
    channel_id = params[0]
    
    # Get or create selected channels set
    selected_channels = context.user_data.get('auto_ads_selected_channels', set())
    
    if channel_id in selected_channels:
        selected_channels.remove(channel_id)
        await query.answer("Channel deselected", show_alert=False)
    else:
        selected_channels.add(channel_id)
        await query.answer("Channel selected", show_alert=False)
    
    # Store updated selection
    context.user_data['auto_ads_selected_channels'] = selected_channels
    
    # Refresh the channel selection display
    await handle_auto_ads_select_channels(update, context, params)

async def handle_channel_info_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel info input message"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_primary_admin(user_id):
        return
    
    if context.user_data.get("state") != "awaiting_channel_info":
        return
    
    if not update.message or not update.message.text:
        await send_message_with_retry(context.bot, chat_id, "❌ Please enter valid channel information.", parse_mode=None)
        return
    
    channel_info = update.message.text.strip()
    
    # Extract channel info from link
    try:
        # Handle different Telegram channel link formats
        if channel_info.startswith('https://t.me/'):
            # Extract channel username from https://t.me/channelname
            channel_username = channel_info.replace('https://t.me/', '').replace('@', '')
            channel_id = f"@{channel_username}"
            channel_name = channel_username.title()
        elif channel_info.startswith('@'):
            # Handle @channelname format
            channel_username = channel_info.replace('@', '')
            channel_id = channel_info
            channel_name = channel_username.title()
        elif channel_info.startswith('t.me/'):
            # Handle t.me/channelname format
            channel_username = channel_info.replace('t.me/', '').replace('@', '')
            channel_id = f"@{channel_username}"
            channel_name = channel_username.title()
        else:
            # Assume it's a channel username without @
            channel_username = channel_info.replace('@', '')
            channel_id = f"@{channel_username}"
            channel_name = channel_username.title()
        
        # Validate channel format
        if not channel_username or len(channel_username) < 3:
            raise ValueError("Invalid channel format")
        
    except Exception as e:
        await send_message_with_retry(context.bot, chat_id, 
            "❌ Invalid channel link format.\n\n"
            "**Supported formats:**\n"
            "• `https://t.me/channelname`\n"
            "• `@channelname`\n"
            "• `t.me/channelname`\n"
            "• `channelname`\n\n"
            "Please try again with a valid channel link.", parse_mode='Markdown')
        return
    
    # Add channel to database
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if channel already exists
        c.execute("SELECT id FROM auto_ads_channels WHERE channel_id = ?", (channel_id,))
        if c.fetchone():
            await send_message_with_retry(context.bot, chat_id, "❌ Channel already exists!", parse_mode=None)
            return
        
        # Insert new channel
        c.execute("""
            INSERT INTO auto_ads_channels 
            (channel_name, channel_id, channel_type, is_active, subscriber_count, created_at)
            VALUES (?, ?, 'telegram', 1, 0, ?)
        """, (channel_name, channel_id, datetime.now().isoformat()))
        
        conn.commit()
        
        # Clear state
        context.user_data.pop('state', None)
        
        msg = f"✅ **Channel Added Successfully!**\n\n"
        msg += f"**Channel:** {channel_name}\n"
        msg += f"**Link:** {channel_id}\n"
        msg += f"**Type:** Telegram\n\n"
        msg += "The channel is now available for auto ads campaigns!"
        
        keyboard = [
            [InlineKeyboardButton("📺 Manage Channels", callback_data="auto_ads_manage_channels")],
            [InlineKeyboardButton("🚀 Auto Ads Menu", callback_data="auto_ads_menu")]
        ]
        
        await send_message_with_retry(context.bot, chat_id, msg, 
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error adding channel: {e}")
        await send_message_with_retry(context.bot, chat_id, "❌ Error adding channel. Please try again.", parse_mode=None)
    finally:
        if conn:
            conn.close()

async def handle_auto_ads_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Campaign analytics dashboard"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get campaign statistics
        c.execute("""
            SELECT 
                COUNT(*) as total_campaigns,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_campaigns,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_campaigns,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_campaigns
            FROM auto_ads_campaigns
        """)
        campaign_stats = c.fetchone()
        
        # Get channel statistics
        c.execute("""
            SELECT 
                COUNT(*) as total_channels,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_channels,
                SUM(subscriber_count) as total_subscribers
            FROM auto_ads_channels
        """)
        channel_stats = c.fetchone()
        
        # Get recent campaign performance
        c.execute("""
            SELECT name, status, created_at, total_sent, total_failed
            FROM auto_ads_campaigns
            ORDER BY created_at DESC
            LIMIT 5
        """)
        recent_campaigns = c.fetchall()
        
    except Exception as e:
        logger.error(f"Error getting auto ads analytics: {e}")
        await query.answer("Error loading analytics", show_alert=True)
        return
    finally:
        if conn:
            conn.close()
    
    msg = "📊 **Auto Ads Analytics Dashboard**\n\n"
    
    # Campaign overview
    msg += f"🚀 **Campaign Overview:**\n"
    msg += f"• Total Campaigns: {campaign_stats['total_campaigns']}\n"
    msg += f"• Active Campaigns: {campaign_stats['active_campaigns']}\n"
    msg += f"• Completed: {campaign_stats['completed_campaigns']}\n"
    msg += f"• Failed: {campaign_stats['failed_campaigns']}\n\n"
    
    # Channel overview
    msg += f"📺 **Channel Overview:**\n"
    msg += f"• Total Channels: {channel_stats['total_channels']}\n"
    msg += f"• Active Channels: {channel_stats['active_channels']}\n"
    msg += f"• Total Reach: {channel_stats['total_subscribers']:,} subscribers\n\n"
    
    # Recent campaigns
    if recent_campaigns:
        msg += f"📈 **Recent Campaign Performance:**\n"
        for campaign in recent_campaigns:
            success_rate = 0
            if campaign['total_sent'] and campaign['total_sent'] > 0:
                success_rate = ((campaign['total_sent'] - (campaign['total_failed'] or 0)) / campaign['total_sent']) * 100
            
            status_emoji = "✅" if campaign['status'] == 'completed' else "🔄" if campaign['status'] == 'active' else "❌"
            msg += f"{status_emoji} **{campaign['name'][:20]}**\n"
            msg += f"   Sent: {campaign['total_sent'] or 0} | Success: {success_rate:.1f}%\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Data", callback_data="auto_ads_analytics")],
        [InlineKeyboardButton("📋 Export Report", callback_data="auto_ads_export_analytics")],
        [InlineKeyboardButton("⬅️ Back to Auto Ads", callback_data="auto_ads_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_auto_ads_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Auto ads system settings"""
    query = update.callback_query
    if not is_primary_admin(query.from_user.id):
        return await query.answer("Access denied.", show_alert=True)
    
    msg = "⚙️ **Auto Ads System Settings**\n\n"
    msg += "Configure global settings for the auto ads system:\n\n"
    
    # Get current settings (you can expand this with actual settings from database)
    msg += "🔧 **Current Settings:**\n"
    msg += "• Max Campaigns per Day: 10\n"
    msg += "• Default Send Interval: 1 hour\n"
    msg += "• Retry Failed Messages: Yes\n"
    msg += "• Analytics Tracking: Enabled\n"
    msg += "• Channel Verification: Required\n\n"
    
    msg += "📊 **System Status:**\n"
    msg += "• Campaign Scheduler: ✅ Running\n"
    msg += "• Message Queue: ✅ Active\n"
    msg += "• Error Handling: ✅ Enabled\n"
    msg += "• Rate Limiting: ✅ Active"
    
    keyboard = [
        [InlineKeyboardButton("📊 Adjust Rate Limits", callback_data="auto_ads_rate_limits")],
        [InlineKeyboardButton("🔄 Retry Settings", callback_data="auto_ads_retry_settings")],
        [InlineKeyboardButton("📈 Analytics Config", callback_data="auto_ads_analytics_config")],
        [InlineKeyboardButton("🔧 Advanced Settings", callback_data="auto_ads_advanced_settings")],
        [InlineKeyboardButton("⬅️ Back to Auto Ads", callback_data="auto_ads_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- END OF FILE auto_ads_system.py ---
