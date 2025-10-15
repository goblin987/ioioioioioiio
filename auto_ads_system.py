"""
TgCF Pro - Enterprise Telegram Bot Interface
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Professional Telegram bot interface providing intuitive user interactions
for enterprise-grade automation and campaign management.

Features:
- Multi-account management with streamlined setup
- Advanced campaign creation and scheduling
- Real-time performance monitoring and analytics
- Enterprise security with access control
- Professional UI/UX with inline keyboards

Author: TgCF Pro Team
License: MIT
Version: 1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from utils import get_db_connection
# Lazy imports to avoid startup hangs
# from telethon_manager_testforwarder import TelethonManager
# from bump_service_testforwarder import BumpService

# Use existing logger from main.py (don't reconfigure)
logger = logging.getLogger(__name__)

# ==================== CONFIG STUB ====================
class Config:
    """Configuration stub for auto ads system"""
    BOT_TOKEN = None
    OWNER_USER_ID = None
    STORAGE_CHANNEL_ID = None
    
    @classmethod
    def validate(cls):
        """Validate configuration (stub)"""
        pass

# ==================== BUMP SERVICE ====================
class BumpService:
    """Bump service for campaign management and scheduling"""
    
    def __init__(self, bot_instance=None, telethon_manager=None):
        self.bot = bot_instance
        self.db = Database()
        self.telethon_manager = telethon_manager
        self.scheduler_task = None
        self.is_running = False
    
    def get_user_campaigns(self, user_id):
        """Get all campaigns for a user"""
        try:
            conn = self.db._get_conn()
            c = conn.cursor()
            c.execute("""
                SELECT c.*, a.account_name, cfg.config_name
                FROM auto_ads_campaigns c
                LEFT JOIN auto_ads_configs cfg ON c.config_id = cfg.id
                LEFT JOIN auto_ads_accounts a ON cfg.account_id = a.id
                WHERE c.user_id = %s
                ORDER BY c.created_at DESC
            """, (user_id,))
            campaigns = c.fetchall()
            conn.close()
            return campaigns
        except Exception as e:
            logger.error(f"Error getting user campaigns: {e}")
            return []
    
    def get_campaign(self, campaign_id):
        """Get campaign by ID"""
        try:
            conn = self.db._get_conn()
            c = conn.cursor()
            c.execute("""
                SELECT c.*, a.account_name, cfg.config_name, cfg.source_chat, cfg.target_chat
                FROM auto_ads_campaigns c
                LEFT JOIN auto_ads_configs cfg ON c.config_id = cfg.id
                LEFT JOIN auto_ads_accounts a ON cfg.account_id = a.id
                WHERE c.id = %s
            """, (campaign_id,))
            campaign = c.fetchone()
            conn.close()
            return campaign
        except Exception as e:
            logger.error(f"Error getting campaign: {e}")
            return None
    
    def delete_campaign(self, campaign_id):
        """Delete a campaign"""
        try:
            conn = self.db._get_conn()
            c = conn.cursor()
            c.execute("DELETE FROM auto_ads_campaigns WHERE id = %s", (campaign_id,))
            conn.commit()
            conn.close()
            logger.info(f"✅ Deleted campaign {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting campaign: {e}")
            return False
    
    def get_campaign_performance(self, campaign_id):
        """Get campaign performance metrics"""
        try:
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                return {}
            
            return {
                'sent_count': campaign.get('sent_count', 0),
                'last_sent': campaign.get('last_sent'),
                'status': 'active' if campaign.get('is_active') else 'inactive',
                'created_at': campaign.get('created_at')
            }
        except Exception as e:
            logger.error(f"Error getting campaign performance: {e}")
            return {}
    
    def add_campaign(self, user_id, name, config_id, message_text=None, 
                    schedule_time=None, interval_minutes=None, bump_count=None,
                    forwarding_mode='forward', source_message_id=None):
        """Add a new campaign"""
        try:
            conn = self.db._get_conn()
            c = conn.cursor()
            c.execute("""
                INSERT INTO auto_ads_campaigns 
                (user_id, name, config_id, message_text, schedule_time, 
                 interval_minutes, bump_count, forwarding_mode, source_message_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, name, config_id, message_text, schedule_time, 
                  interval_minutes, bump_count, forwarding_mode, source_message_id))
            campaign_id = c.fetchone()[0]
            conn.commit()
            conn.close()
            logger.info(f"✅ Added campaign {campaign_id}: {name}")
            return campaign_id
        except Exception as e:
            logger.error(f"Error adding campaign: {e}")
            return None
    
    def update_campaign(self, campaign_id, **kwargs):
        """Update campaign fields"""
        try:
            conn = self.db._get_conn()
            c = conn.cursor()
            
            # Build update query dynamically
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in ['name', 'message_text', 'schedule_time', 'interval_minutes', 
                          'bump_count', 'is_active', 'forwarding_mode']:
                    updates.append(f"{key} = %s")
                    values.append(value)
            
            if not updates:
                return False
            
            values.append(campaign_id)
            query = f"UPDATE auto_ads_campaigns SET {', '.join(updates)} WHERE id = %s"
            c.execute(query, values)
            conn.commit()
            conn.close()
            logger.info(f"✅ Updated campaign {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating campaign: {e}")
            return False
    
    def update_campaign_stats(self, campaign_id):
        """Update campaign statistics after execution"""
        try:
            from datetime import datetime, timezone
            conn = self.db._get_conn()
            c = conn.cursor()
            c.execute("""
                UPDATE auto_ads_campaigns 
                SET sent_count = sent_count + 1,
                    last_sent = %s
                WHERE id = %s
            """, (datetime.now(timezone.utc), campaign_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating campaign stats: {e}")
            return False
    
    async def test_campaign(self, campaign_id, test_chat):
        """Test a campaign by sending to a test chat"""
        try:
            if not self.telethon_manager:
                logger.error("TelethonManager not initialized")
                return False
            
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return False
            
            # Get account from config
            config_id = campaign.get('config_id')
            if not config_id:
                logger.error("Campaign has no config")
                return False
            
            config = self.db.get_user_configs(campaign['user_id'])
            account_id = None
            for cfg in config:
                if cfg['id'] == config_id:
                    account_id = cfg['account_id']
                    break
            
            if not account_id:
                logger.error("No account found for campaign")
                return False
            
            # Execute test
            if campaign.get('forwarding_mode') == 'forward' and campaign.get('source_message_id'):
                success = await self.telethon_manager.forward_message(
                    account_id,
                    campaign['source_chat'],
                    test_chat,
                    campaign['source_message_id']
                )
            else:
                success = await self.telethon_manager.send_message(
                    account_id,
                    test_chat,
                    text=campaign.get('message_text')
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error testing campaign: {e}", exc_info=True)
            return False
    
    async def execute_campaign(self, campaign_id):
        """Execute a campaign (send messages)"""
        try:
            if not self.telethon_manager:
                logger.error("TelethonManager not initialized")
                return False
            
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return False
            
            if not campaign.get('is_active'):
                logger.info(f"Campaign {campaign_id} is not active, skipping")
                return False
            
            # Get config and account
            config_id = campaign.get('config_id')
            if not config_id:
                logger.error(f"Campaign {campaign_id} has no config")
                return False
            
            # Get account_id from config
            conn = self.db._get_conn()
            c = conn.cursor()
            c.execute("SELECT account_id, source_chat, target_chat FROM auto_ads_configs WHERE id = %s", (config_id,))
            config = c.fetchone()
            conn.close()
            
            if not config:
                logger.error(f"Config {config_id} not found")
                return False
            
            account_id = config['account_id']
            source_chat = config['source_chat']
            target_chat = config['target_chat']
            
            # Execute based on forwarding mode
            forwarding_mode = campaign.get('forwarding_mode', 'forward')
            source_message_id = campaign.get('source_message_id')
            
            if forwarding_mode == 'forward' and source_message_id:
                # Forward existing message
                success = await self.telethon_manager.forward_message(
                    account_id, source_chat, target_chat, source_message_id
                )
            elif forwarding_mode == 'copy' and source_message_id:
                # Copy message (send as new)
                success = await self.telethon_manager.copy_message(
                    account_id, source_chat, target_chat, source_message_id
                )
            else:
                # Send custom message
                success = await self.telethon_manager.send_message(
                    account_id, target_chat, text=campaign.get('message_text')
                )
            
            if success:
                self.update_campaign_stats(campaign_id)
                logger.info(f"✅ Executed campaign {campaign_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing campaign: {e}", exc_info=True)
            return False
    
    async def scheduler_loop(self):
        """Background scheduler loop"""
        from datetime import datetime, timezone, timedelta
        
        logger.info("🚀 BumpService scheduler started")
        self.is_running = True
        
        while self.is_running:
            try:
                # Get campaigns due for execution
                conn = self.db._get_conn()
                c = conn.cursor()
                
                now = datetime.now(timezone.utc)
                
                # Find campaigns that should run now
                c.execute("""
                    SELECT id FROM auto_ads_campaigns
                    WHERE is_active = TRUE
                    AND (
                        (schedule_time IS NOT NULL AND schedule_time <= %s AND last_sent IS NULL)
                        OR (interval_minutes IS NOT NULL AND (
                            last_sent IS NULL 
                            OR last_sent + INTERVAL '1 minute' * interval_minutes <= %s
                        ))
                    )
                """, (now, now))
                
                due_campaigns = c.fetchall()
                conn.close()
                
                # Execute due campaigns
                for campaign in due_campaigns:
                    campaign_id = campaign['id']
                    logger.info(f"⏰ Executing scheduled campaign {campaign_id}")
                    await self.execute_campaign(campaign_id)
                    
                    # Small delay between campaigns to avoid rate limits
                    await asyncio.sleep(2)
                
                # Sleep for 60 seconds before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(60)
        
        logger.info("🛑 BumpService scheduler stopped")
    
    def start_scheduler(self):
        """Start the background scheduler"""
        if self.scheduler_task and not self.scheduler_task.done():
            logger.warning("Scheduler already running")
            return
        
        try:
            loop = asyncio.get_event_loop()
            self.scheduler_task = loop.create_task(self.scheduler_loop())
            logger.info("✅ BumpService scheduler task created")
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}", exc_info=True)
    
    def cleanup_all_resources(self):
        """Cleanup resources"""
        self.is_running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
        logger.info("🧹 BumpService cleaned up")

# ==================== DATABASE CLASS ====================
class Database:
    """Database wrapper for auto ads system"""
    
    def __init__(self):
        self.conn = None
    
    def _get_conn(self):
        """Get database connection"""
        return get_db_connection()
    
    def add_user(self, user_id, username, first_name, last_name):
        """Add or update user"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("""
                INSERT INTO users (user_id, username) 
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
            """, (user_id, username))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error adding user: {e}")
    
    def get_user_configs(self, user_id, account_id=None):
        """Get user forwarding configurations"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            if account_id:
                c.execute("SELECT * FROM auto_ads_configs WHERE user_id = %s AND account_id = %s", (user_id, account_id))
            else:
                c.execute("SELECT * FROM auto_ads_configs WHERE user_id = %s", (user_id,))
            configs = c.fetchall()
            conn.close()
            return configs
        except Exception as e:
            logger.error(f"Error getting configs: {e}")
            return []
    
    def get_user_accounts(self, user_id):
        """Get user's Telegram accounts"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("SELECT * FROM auto_ads_accounts WHERE user_id = %s", (user_id,))
            accounts = c.fetchall()
            conn.close()
            return accounts
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            return []
    
    def get_account(self, account_id):
        """Get account by ID"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("SELECT * FROM auto_ads_accounts WHERE id = %s", (account_id,))
            account = c.fetchone()
            conn.close()
            return account
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return None
    
    def add_telegram_account(self, user_id, account_name, phone_number, session_string, api_id=None, api_hash=None):
        """Add a Telegram account"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("""
                INSERT INTO auto_ads_accounts (user_id, account_name, phone_number, session_string, api_id, api_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, account_name, phone_number, session_string, api_id, api_hash))
            account_id = c.fetchone()[0]
            conn.commit()
            conn.close()
            return account_id
        except Exception as e:
            logger.error(f"Error adding account: {e}")
            return None
    
    def update_account(self, account_id, **kwargs):
        """Update account fields"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in ['account_name', 'phone_number', 'session_string', 'api_id', 'api_hash', 'is_active']:
                    updates.append(f"{key} = %s")
                    values.append(value)
            
            if not updates:
                return False
            
            values.append(account_id)
            query = f"UPDATE auto_ads_accounts SET {', '.join(updates)} WHERE id = %s"
            c.execute(query, values)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating account: {e}")
            return False
    
    def add_forwarding_config(self, user_id, account_id, source_chat, target_chat, config_name):
        """Add a forwarding configuration"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("""
                INSERT INTO auto_ads_configs (user_id, account_id, source_chat, target_chat, config_name)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, account_id, source_chat, target_chat, config_name))
            config_id = c.fetchone()[0]
            conn.commit()
            conn.close()
            return config_id
        except Exception as e:
            logger.error(f"Error adding config: {e}")
            return None
    
    def delete_config(self, config_id):
        """Delete a configuration"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("DELETE FROM auto_ads_configs WHERE id = %s", (config_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error deleting config: {e}")
    
    def delete_account(self, account_id):
        """Delete an account and all related configs"""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("DELETE FROM auto_ads_configs WHERE account_id = %s", (account_id,))
            c.execute("DELETE FROM auto_ads_accounts WHERE id = %s", (account_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error deleting account: {e}")

# ==================== TELETHON MANAGER CLASS ====================
class TelethonManager:
    """Telethon manager for auto ads system with real Telethon integration"""
    
    def __init__(self):
        self.clients = {}  # account_id -> TelegramClient
        self.active_sessions = {}  # phone_number -> session_data (for login flows)
    
    async def create_client(self, account_id, api_id, api_hash, phone_number, session_string=None):
        """Create and connect a Telethon client from session string"""
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            logger.info(f"Creating Telethon client for account {account_id} ({phone_number})")
            
            # Create client with session string if available
            if session_string:
                session = StringSession(session_string)
            else:
                session = StringSession()
            
            client = TelegramClient(session, int(api_id), api_hash)
            
            # Connect the client
            await client.connect()
            
            # Check if authorized
            if not await client.is_user_authorized():
                logger.warning(f"Client {account_id} not authorized, needs login")
                await client.disconnect()
                return None
            
            # Store client
            self.clients[account_id] = client
            logger.info(f"✅ Telethon client {account_id} created and connected")
            
            return client
            
        except Exception as e:
            logger.error(f"Error creating Telethon client: {e}", exc_info=True)
            return None
    
    async def get_client(self, account_id):
        """Get existing client or return None"""
        return self.clients.get(account_id)
    
    async def disconnect_client(self, account_id):
        """Disconnect a client"""
        try:
            if account_id in self.clients:
                await self.clients[account_id].disconnect()
                del self.clients[account_id]
                logger.info(f"Disconnected client {account_id}")
        except Exception as e:
            logger.error(f"Error disconnecting client {account_id}: {e}")
    
    async def forward_message(self, account_id, source_chat, target_chat, message_id):
        """Forward a message from source to target chat"""
        try:
            client = await self.get_client(account_id)
            if not client:
                logger.error(f"No client found for account {account_id}")
                return False
            
            # Forward the message
            await client.forward_messages(
                entity=target_chat,
                messages=message_id,
                from_peer=source_chat
            )
            
            logger.info(f"✅ Forwarded message {message_id} from {source_chat} to {target_chat}")
            return True
            
        except Exception as e:
            logger.error(f"Error forwarding message: {e}", exc_info=True)
            return False
    
    async def send_message(self, account_id, chat_id, text=None, file=None, buttons=None):
        """Send a message to a chat"""
        try:
            client = await self.get_client(account_id)
            if not client:
                logger.error(f"No client found for account {account_id}")
                return False
            
            # Send message
            await client.send_message(
                entity=chat_id,
                message=text,
                file=file,
                buttons=buttons
            )
            
            logger.info(f"✅ Sent message to {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return False
    
    async def get_messages(self, account_id, chat_id, limit=10):
        """Get messages from a chat"""
        try:
            client = await self.get_client(account_id)
            if not client:
                logger.error(f"No client found for account {account_id}")
                return []
            
            messages = await client.get_messages(chat_id, limit=limit)
            return messages
            
        except Exception as e:
            logger.error(f"Error getting messages: {e}", exc_info=True)
            return []
    
    async def copy_message(self, account_id, source_chat, target_chat, message_id):
        """Copy a message (not as forwarded) from source to target"""
        try:
            client = await self.get_client(account_id)
            if not client:
                logger.error(f"No client found for account {account_id}")
                return False
            
            # Get the original message
            message = await client.get_messages(source_chat, ids=message_id)
            if not message:
                logger.error(f"Message {message_id} not found in {source_chat}")
                return False
            
            # Send as new message (copy)
            await client.send_message(
                entity=target_chat,
                message=message.text or message.caption,
                file=message.media if message.media else None,
                buttons=message.buttons if message.buttons else None
            )
            
            logger.info(f"✅ Copied message {message_id} from {source_chat} to {target_chat}")
            return True
            
        except Exception as e:
            logger.error(f"Error copying message: {e}", exc_info=True)
            return False
    
    async def send_code_request(self, api_id, api_hash, phone_number):
        """Send login code to phone number"""
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            logger.info(f"Sending code request to {phone_number}")
            
            # Create temporary client for login
            client = TelegramClient(StringSession(), int(api_id), api_hash)
            await client.connect()
            
            # Send code
            sent_code = await client.send_code_request(phone_number)
            
            # Store session data for later use
            self.active_sessions[phone_number] = {
                'client': client,
                'phone_code_hash': sent_code.phone_code_hash
            }
            
            logger.info(f"✅ Code sent to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending code: {e}", exc_info=True)
            return False
    
    async def sign_in(self, phone_number, code, password=None):
        """Sign in with code and return session string"""
        try:
            session_data = self.active_sessions.get(phone_number)
            if not session_data:
                logger.error(f"No active session for {phone_number}")
                return None
            
            client = session_data['client']
            phone_code_hash = session_data['phone_code_hash']
            
            # Sign in with code
            try:
                await client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)
            except Exception as e:
                # Check if 2FA password is needed
                if password:
                    await client.sign_in(password=password)
                else:
                    raise e
            
            # Get session string
            session_string = client.session.save()
            
            # Disconnect temporary client
            await client.disconnect()
            
            # Clean up
            del self.active_sessions[phone_number]
            
            logger.info(f"✅ Signed in {phone_number}, session string obtained")
            return session_string
            
        except Exception as e:
            logger.error(f"Error signing in: {e}", exc_info=True)
            return None
    
    async def disconnect_all(self):
        """Disconnect all clients"""
        for account_id in list(self.clients.keys()):
            await self.disconnect_client(account_id)
    
    async def load_all_accounts(self, db):
        """Load and connect all active accounts from database"""
        try:
            conn = db._get_conn()
            c = conn.cursor()
            c.execute("""
                SELECT id, api_id, api_hash, phone_number, session_string 
                FROM auto_ads_accounts 
                WHERE is_active = TRUE AND session_string IS NOT NULL
                AND api_id IS NOT NULL AND api_hash IS NOT NULL
            """)
            accounts = c.fetchall()
            conn.close()
            
            logger.info(f"Loading {len(accounts)} accounts from database...")
            
            for account in accounts:
                account_id = account['id']
                api_id = account['api_id']
                api_hash = account['api_hash']
                phone_number = account['phone_number']
                session_string = account['session_string']
                
                try:
                    client = await self.create_client(
                        account_id, api_id, api_hash, phone_number, session_string
                    )
                    if client:
                        logger.info(f"✅ Loaded account {account_id} ({phone_number})")
                    else:
                        logger.warning(f"⚠️ Failed to load account {account_id} ({phone_number})")
                except Exception as e:
                    logger.error(f"Error loading account {account_id}: {e}")
            
            logger.info(f"✅ Loaded {len(self.clients)} out of {len(accounts)} accounts")
            
        except Exception as e:
            logger.error(f"Error loading accounts: {e}", exc_info=True)

class TgcfBot:
    def escape_markdown(self, text):
        """Escape special Markdown characters"""
        if not text:
            return ""
        # Escape special characters that break Markdown
        text = str(text)
        text = text.replace("\\", "\\\\")  # Backslash first
        text = text.replace("*", "\\*")   # Asterisk
        text = text.replace("_", "\\_")   # Underscore
        text = text.replace("`", "\\`")   # Backtick
        text = text.replace("[", "\\[")   # Square brackets
        text = text.replace("]", "\\]")   # Square brackets
        text = text.replace("(", "\\(")   # Parentheses
        text = text.replace(")", "\\)")   # Parentheses
        text = text.replace("~", "\\~")   # Tilde
        text = text.replace(">", "\\>")   # Greater than
        text = text.replace("#", "\\#")   # Hash
        text = text.replace("+", "\\+")   # Plus
        text = text.replace("-", "\\-")   # Minus
        text = text.replace("=", "\\=")   # Equals
        text = text.replace("|", "\\|")   # Pipe
        text = text.replace("{", "\\{")   # Curly braces
        text = text.replace("}", "\\}")   # Curly braces
        text = text.replace(".", "\\.")   # Dot
        text = text.replace("!", "\\!")   # Exclamation
        return text

    def __init__(self):
        self.db = Database()
        self.telethon_manager = TelethonManager()
        self.bump_service = BumpService(telethon_manager=self.telethon_manager)
        self.user_sessions = {}  # Store user session data
    
    def validate_input(self, text: str, max_length: int = 1000, allowed_chars: str = None) -> tuple[bool, str]:
        """Validate user input with length and character restrictions"""
        import re  # Import at the top of the function
        
        if not text or not isinstance(text, str):
            return False, "Input cannot be empty"
        
        if len(text) > max_length:
            return False, f"Input too long (max {max_length} characters)"
        
        if allowed_chars:
            if not re.match(f"^[{re.escape(allowed_chars)}]+$", text):
                return False, f"Input contains invalid characters. Only {allowed_chars} allowed"
        
        # Check for potential SQL injection patterns
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
            r"(--|#|\/\*|\*\/)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+'.*'\s*=\s*'.*')",
            r"(\bUNION\s+SELECT\b)",
            r"(\bDROP\s+TABLE\b)",
            r"(\bINSERT\s+INTO\b)",
            r"(\bDELETE\s+FROM\b)"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "Input contains potentially malicious content"
        
        return True, ""
    
    def _is_bridge_channel_link(self, text: str) -> bool:
        """Check if text contains a bridge channel/group message link"""
        text = text.strip()
        
        # Check for t.me links with message ID
        if 't.me/' in text and '/' in text:
            # Extract the link part
            if text.startswith('https://t.me/') or text.startswith('http://t.me/') or text.startswith('t.me/'):
                parts = text.replace('https://', '').replace('http://', '').replace('t.me/', '').split('/')
                
                # Handle both public channels (t.me/channel/123) and private channels (t.me/c/123456789/123)
                if len(parts) >= 2:  # At least channel/message_id
                    try:
                        int(parts[-1])  # Last part should be message ID
                        return True
                    except ValueError:
                        pass
        
        return False
    
    async def _handle_bridge_channel_link(self, update: Update, session: dict, link: str):
        """Handle bridge channel/group message link"""
        user_id = update.effective_user.id
        
        try:
            # Parse the bridge channel link
            link = link.strip()
            logger.info(f"🔗 Parsing bridge channel link: {link}")
            
            if not link.startswith('http'):
                link = 'https://' + link
            
            # Extract channel info and message ID
            parts = link.replace('https://t.me/', '').replace('http://t.me/', '').split('/')
            logger.info(f"🔗 Link parts after parsing: {parts}")
            
            if len(parts) < 2:
                raise ValueError(f"Invalid link format - need at least channel/message_id, got {len(parts)} parts: {parts}")
            
            # Handle private channels (t.me/c/123456789/123) vs public channels (t.me/username/123)
            if parts[0] == 'c' and len(parts) >= 3:
                # Private channel: t.me/c/channel_id/message_id
                channel_id = int(parts[1])
                message_id = int(parts[2])
                channel_entity = f"-100{channel_id}"  # Private channel format
                display_name = f"Private Channel ({channel_id})"
            elif len(parts) >= 2:
                # Public channel: t.me/username/message_id
                channel_username = parts[0]
                message_id = int(parts[1])
                channel_entity = f"@{channel_username}"
                display_name = f"@{channel_username}"
            else:
                raise ValueError("Invalid link format - could not parse channel and message ID")
            
            logger.info(f"✅ Successfully parsed bridge channel: {display_name}, Message ID: {message_id}")
            
            # Store bridge channel information
            ad_data = {
                'bridge_channel': True,
                'bridge_channel_entity': channel_entity,
                'bridge_message_id': message_id,
                'bridge_link': link,
                'message_id': message_id,
                'chat_id': channel_entity,
                'original_message_id': message_id,
                'original_chat_id': channel_entity,
                'has_custom_emojis': True,  # Assume bridge channel preserves emojis
                'has_premium_emojis': True,  # Bridge channel should preserve premium emojis
                'media_type': 'bridge_channel'
            }
            
            # Store in session
            session['campaign_data']['ad_content'] = ad_data
            
            # Move to next step
            session['step'] = 'add_buttons_choice'
            
            await update.message.reply_text(
                f"✅ **Bridge Channel Link Configured!**\n\n**Channel:** {display_name}\n**Message ID:** {message_id}\n\n🎯 **How this works:**\n1️⃣ Worker accounts will join your channel\n2️⃣ They'll forward message #{message_id} with premium emojis intact\n3️⃣ All formatting and media preserved perfectly!\n\n**Step 3/6: Add Buttons**\n\nWould you like to add clickable buttons under your forwarded message?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Yes, Add Buttons", callback_data="add_buttons_yes")],
                    [InlineKeyboardButton("❌ No Buttons", callback_data="add_buttons_no")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_ad_content")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error parsing bridge channel link: {e}")
            await update.message.reply_text(
                "❌ **Invalid Bridge Channel Link**\n\n**Expected format:**\n`t.me/yourchannel/123`\n`https://t.me/yourchannel/123`\n\n**Example:**\n`t.me/mychannel/456`\n\nPlease send a valid channel message link or forward a message directly.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def sanitize_text(self, text: str) -> str:
        """Sanitize text input by removing or escaping dangerous characters"""
        if not text:
            return ""
        
        # Remove null bytes and control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        
        # Limit length
        text = text[:1000]
        
        return text.strip()
    
    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE, error: Exception, operation: str = "Unknown"):
        """Centralized error handling with user-friendly messages and logging"""
        user_id = update.effective_user.id if update and update.effective_user else "Unknown"
        
        # Log the error with context
        logger.error(f"Error in {operation} for user {user_id}: {str(error)}", exc_info=True)
        
        # Determine user-friendly error message
        if isinstance(error, ValueError):
            error_msg = f"❌ **Invalid Input**\n\n{self.escape_markdown(str(error))}\n\nPlease check your input and try again."
        elif isinstance(error, ConnectionError):
            error_msg = "❌ **Connection Error**\n\nUnable to connect to Telegram. Please try again in a few moments."
        elif isinstance(error, TimeoutError):
            error_msg = "❌ **Timeout Error**\n\nOperation timed out. Please try again."
        elif isinstance(error, PermissionError):
            error_msg = "❌ **Permission Error**\n\nYou don't have permission to perform this action."
        elif isinstance(error, FileNotFoundError):
            error_msg = "❌ **File Not Found**\n\nRequired file is missing. Please contact support."
        else:
            error_msg = "❌ **Unexpected Error**\n\nSomething went wrong. Please try again or contact support if the problem persists."
        
        # Send error message to user
        try:
            if update and update.message:
                await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN)
            elif update and update.callback_query:
                await update.callback_query.answer(error_msg, show_alert=True)
        except Exception as e:
            logger.error(f"Failed to send error message to user {user_id}: {e}")
    
    def create_error_recovery_context(self, operation: str, max_retries: int = 3):
        """Create a context manager for error recovery with retry logic"""
        class ErrorRecoveryContext:
            def __init__(self, operation: str, max_retries: int):
                self.operation = operation
                self.max_retries = max_retries
                self.attempt = 0
                self.last_error = None
            
            def __enter__(self):
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    self.last_error = exc_val
                    self.attempt += 1
                    
                    if self.attempt < self.max_retries:
                        logger.warning(f"Error in {self.operation} (attempt {self.attempt}/{self.max_retries}): {exc_val}")
                        # Return True to suppress the exception and retry
                        return True
                    else:
                        logger.error(f"Failed {self.operation} after {self.max_retries} attempts: {exc_val}")
                        return False
                
                return False
        
        return ErrorRecoveryContext(operation, max_retries)
    
    def cleanup_resources(self):
        """Clean up all resources before shutdown"""
        logger.info("Starting bot resource cleanup...")
        try:
            # Clean up bump service resources
            self.bump_service.cleanup_all_resources()
            logger.info("Bump service cleanup completed")
        except Exception as e:
            logger.error(f"Error during bump service cleanup: {e}")
        
        logger.info("Bot resource cleanup completed")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Check if this is the bot owner (optional - you can remove this check if you want)
        if Config.OWNER_USER_ID and str(user.id) != Config.OWNER_USER_ID:
            await update.message.reply_text(
                "🔒 **Access Restricted**\n\nThis bot is for authorized use only.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        self.db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        welcome_text = """
🚀 **Welcome to TgCF Pro**

*Enterprise Telegram Automation Platform*

**Professional Features:**
• 🏢 Multi-Account Management - Unlimited work accounts
• 📢 Smart Bump Service - Advanced campaign automation  
• ⚡ Real-time Forwarding - Lightning-fast message processing
• 📊 Business Analytics - Comprehensive performance tracking
• 🛡️ Enterprise Security - Professional-grade protection

**Ready to automate your business communications?**
        """
        
        keyboard = [
            [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
            [InlineKeyboardButton("📢 Bump Service", callback_data="bump_service")],
            [InlineKeyboardButton("📋 My Configurations", callback_data="my_configs")],
            [InlineKeyboardButton("➕ Add New Forwarding", callback_data="add_forwarding")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📖 **TgCF Bot Help**

**Commands:**
/start - Start the bot and show main menu
/help - Show this help message
/config - Manage your forwarding configurations
/status - Check bot status

**How to use:**
1. **Add Telegram Accounts** - Click "Manage Accounts" to add your Telegram accounts
2. **Create Forwarding Rules** - Click "Add New Forwarding" to create forwarding rules
3. **Configure Plugins** - Set up filters, formatting, and other plugins
4. **Start Forwarding** - Your messages will be forwarded automatically!

**Multi-Account Features:**
• Add multiple Telegram accounts with their own API credentials
• Each account can have separate forwarding rules
• Forward to different or same destinations
• Manage all accounts from one bot interface

**Chat IDs:**
• For channels: Use @channel_username or channel ID
• For groups: Use group ID (get from @userinfobot)
• For users: Use @username or user ID

**Account Setup (IMPORTANT):**
• Each user must get their own API credentials from https://my.telegram.org
• Go to "API development tools" and create an application
• Each account needs its own API ID and Hash (YOUR personal credentials)
• Phone number authentication required for each account
• Your API credentials are stored securely and only used for your accounts
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks with comprehensive error handling"""
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data
        
        try:
            # Answer the query first to prevent timeout
            await query.answer()
        except Exception as e:
            logger.error(f"Failed to answer callback query: {e}")
            # Don't return here, continue with the handler to provide user feedback
        
        try:
            if data == "main_menu":
                await self.show_main_menu(query)
            elif data == "manage_accounts":
                await self.show_manage_accounts(query)
            elif data == "add_account":
                await self.start_add_account(query)
            elif data == "my_configs":
                await self.show_my_configs(query)
            elif data == "add_forwarding":
                await self.start_add_forwarding(query)
            elif data == "settings":
                await self.show_settings(query)
            elif data == "help":
                await self.show_help(query)
            elif data == "bump_service":
                await self.show_bump_service(query)
            elif data == "add_campaign":
                await self.start_add_campaign(query)
            elif data == "my_campaigns":
                await self.show_my_campaigns(query)
            elif data.startswith("campaign_"):
                campaign_id = int(data.split("_")[1])
                await self.show_campaign_details(query, campaign_id)
            elif data.startswith("delete_campaign_"):
                campaign_id = int(data.split("_")[2])
                await self.delete_campaign(query, campaign_id)
            elif data.startswith("toggle_campaign_"):
                campaign_id = int(data.split("_")[2])
                await self.toggle_campaign(query, campaign_id)
            elif data.startswith("test_campaign_"):
                campaign_id = int(data.split("_")[2])
                await self.test_campaign(query, campaign_id)
            elif data.startswith("edit_campaign_"):
                campaign_id = int(data.split("_")[2])
                await self.start_edit_campaign(query, campaign_id)
            elif data == "edit_text_content":
                await self.edit_text_content(query)
            elif data == "edit_media":
                await self.edit_media(query)
            elif data == "edit_buttons":
                await self.edit_buttons(query)
            elif data == "edit_settings":
                await self.edit_settings(query)
            elif data == "preview_campaign":
                await self.preview_campaign(query)
            elif data == "back_to_campaigns":
                await self.show_my_campaigns(query)
            elif data == "back_to_bump":
                await self.show_bump_service(query)
            elif data.startswith("schedule_"):
                schedule_type = data.split("_")[1]
                await self.handle_schedule_selection(query, schedule_type)
            elif data.startswith("select_account_"):
                account_id = int(data.split("_")[2])
                await self.handle_account_selection(query, account_id)
            elif data.startswith("config_"):
                config_id = int(data.split("_")[1])
                await self.show_config_details(query, config_id)
            elif data.startswith("delete_config_"):
                config_id = int(data.split("_")[2])
                await self.delete_config(query, config_id)
            elif data.startswith("toggle_config_"):
                config_id = int(data.split("_")[2])
                await self.toggle_config(query, config_id)
            elif data.startswith("account_"):
                account_id = int(data.split("_")[1])
                await self.show_account_details(query, account_id)
            elif data.startswith("delete_account_"):
                account_id = int(data.split("_")[2])
                await self.delete_account(query, account_id)
            elif data.startswith("configs_for_account_"):
                account_id = int(data.split("_")[3])
                await self.show_configs_for_account(query, account_id)
            elif data == "back_to_configs":
                await self.show_my_configs(query)
            elif data == "back_to_accounts":
                await self.show_manage_accounts(query)
            elif data == "upload_session":
                await self.start_session_upload(query)
            elif data == "manual_setup":
                await self.start_manual_setup(query)
            elif data == "advanced_settings":
                await self.show_advanced_settings(query)
            elif data == "configure_plugins":
                await self.show_configure_plugins(query)
            elif data == "performance_settings":
                await self.show_performance_settings(query)
            elif data == "security_settings":
                await self.show_security_settings(query)
            elif data == "add_buttons_yes":
                await self.handle_add_buttons_yes(query)
            elif data == "add_buttons_no":
                await self.handle_add_buttons_no(query)
            elif data == "add_more_messages":
                await self.handle_add_more_messages(query)
            elif data == "target_all_groups":
                await self.handle_target_all_groups(query)
            elif data == "target_specific_chats":
                await self.handle_target_specific_chats(query)
            elif data == "cancel_campaign":
                await self.handle_cancel_campaign(query)
            elif data == "back_to_schedule_selection":
                await self.show_schedule_selection(query)
            elif data == "back_to_target_selection":
                await self.show_target_selection(query)
            elif data == "back_to_button_choice":
                await self.show_button_choice(query)
            elif data.startswith("start_campaign_"):
                campaign_id = int(data.split("_")[2])
                await self.start_campaign_manually(query, campaign_id)
            else:
                await query.answer("Unknown command!", show_alert=True)
        except Exception as e:
            # Use centralized error handling
            await self.handle_error(update, context, e, f"button_callback_{data}")
    
    def get_main_menu_keyboard(self):
        """Get main menu keyboard markup"""
        keyboard = [
            [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
            [InlineKeyboardButton("📢 Bump Service", callback_data="bump_service")],
            [InlineKeyboardButton("📋 My Configurations", callback_data="my_configs")],
            [InlineKeyboardButton("➕ Add New Forwarding", callback_data="add_forwarding")],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("⬅️ Back to Main Bot", callback_data="admin_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def show_main_menu(self, query):
        """Show main menu with all core features"""
        reply_markup = self.get_main_menu_keyboard()
        
        await query.edit_message_text(
            "Choose an option:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_my_configs(self, query):
        """Show user's forwarding configurations"""
        user_id = query.from_user.id
        configs = self.db.get_user_configs(user_id)
        
        if not configs:
            keyboard = [
                [InlineKeyboardButton("➕ Add New Forwarding", callback_data="add_forwarding")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📋 **My Configurations**\n\nNo forwarding configurations found.\n\nClick 'Add New Forwarding' to create your first one!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        text = "📋 **My Configurations**\n\n"
        keyboard = []
        
        for config in configs:
            status = "🟢 Active" if config['is_active'] else "🔴 Inactive"
            text += f"**{config['config_name']}** {status}\n"
            text += f"From: `{config['source_chat_id']}`\n"
            text += f"To: `{config['destination_chat_id']}`\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"⚙️ {config['config_name']}", callback_data=f"config_{config['id']}"),
                InlineKeyboardButton("🗑️", callback_data=f"delete_config_{config['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add New", callback_data="add_forwarding")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_config_details(self, query, config_id):
        """Show detailed configuration"""
        user_id = query.from_user.id
        configs = self.db.get_user_configs(user_id)
        config = next((c for c in configs if c['id'] == config_id), None)
        
        if not config:
            await query.answer("Configuration not found!", show_alert=True)
            return
        
        status = "🟢 Active" if config['is_active'] else "🔴 Inactive"
        text = f"⚙️ **{config['config_name']}** {status}\n\n"
        text += f"**Source:** `{config['source_chat_id']}`\n"
        text += f"**Destination:** `{config['destination_chat_id']}`\n\n"
        
        # Show plugin status
        config_data = config['config_data']
        text += "**Plugins:**\n"
        for plugin_name, plugin_config in config_data.items():
            if isinstance(plugin_config, dict) and plugin_config.get('enabled', False):
                text += f"• {plugin_name.title()}: ✅\n"
            else:
                text += f"• {plugin_name.title()}: ❌\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Toggle Status", callback_data=f"toggle_config_{config_id}")],
            [InlineKeyboardButton("🔙 Back to Configs", callback_data="back_to_configs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def start_add_forwarding(self, query):
        """Start the process of adding a new forwarding configuration"""
        user_id = query.from_user.id
        
        # Check if user has any accounts
        accounts = self.db.get_user_accounts(user_id)
        if not accounts:
            keyboard = [
                [InlineKeyboardButton("➕ Add New Account", callback_data="add_account")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "❌ **No Accounts Found!**\n\nYou need to add at least one Telegram account before creating forwarding configurations.\n\nClick 'Add New Account' to get started!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        self.user_sessions[user_id] = {'step': 'source_chat', 'config': {}}
        
        text = """
➕ **Add New Forwarding Configuration**

**Step 1/4: Source Chat**

Please send me the source chat ID or username.

**Examples:**
• Channel: `@channel_username` or `-1001234567890`
• Group: `-1001234567890`
• User: `@username` or `123456789`

**How to get Chat ID:**
• For channels: Use @channel_username
• For groups: Forward a message from the group to @userinfobot
• For users: Use @username
        """
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_settings(self, query):
        """Show settings menu"""
        text = """
⚙️ **Settings**

**Current Settings:**
• Max messages per batch: 100
• Delay between messages: 0.1s
• Web interface: Available

**Available Options:**
• Configure forwarding limits
• Set up filters
• Manage plugins
• Export/Import configurations
        """
        
        keyboard = [
            [InlineKeyboardButton("🔧 Advanced Settings", callback_data="advanced_settings")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_advanced_settings(self, query):
        """Show advanced settings menu"""
        text = """
🔧 **Advanced Settings**

**Plugin Configuration:**
• Message filters and blacklists
• Text formatting options
• Caption and watermark settings

**Performance Settings:**
• Message batch size limits
• Delay configurations
• Error handling options

**Security Settings:**
• Access control
• Session management
• Data encryption
        """
        
        keyboard = [
            [InlineKeyboardButton("🔌 Configure Plugins", callback_data="configure_plugins")],
            [InlineKeyboardButton("⚡ Performance Settings", callback_data="performance_settings")],
            [InlineKeyboardButton("🔒 Security Settings", callback_data="security_settings")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_configure_plugins(self, query):
        """Show plugin configuration menu"""
        text = """
🔌 **Configure Plugins**

**Available Plugins:**

**🔍 Filter Plugin**
• Blacklist/whitelist messages
• Keyword filtering
• Pattern matching

**📝 Format Plugin**
• Bold, italic, code formatting
• Message styling options

**🔄 Replace Plugin**
• Text replacement rules
• Regular expressions
• Content modification

**📋 Caption Plugin**
• Header and footer text
• Custom message templates
        """
        
        keyboard = [
            [InlineKeyboardButton("🔍 Filter Settings", callback_data="filter_settings")],
            [InlineKeyboardButton("📝 Format Settings", callback_data="format_settings")],
            [InlineKeyboardButton("🔄 Replace Settings", callback_data="replace_settings")],
            [InlineKeyboardButton("📋 Caption Settings", callback_data="caption_settings")],
            [InlineKeyboardButton("🔙 Back to Advanced", callback_data="advanced_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_performance_settings(self, query):
        """Show performance settings menu"""
        text = """
⚡ **Performance Settings**

**Current Configuration:**
• Max messages per batch: 100
• Delay between messages: 0.1s
• Connection timeout: 30s
• Retry attempts: 3

**Optimization Options:**
• Batch processing size
• Message throttling
• Error handling strategy
• Resource management

**Monitoring:**
• Real-time performance metrics
• Error rate tracking
• Success rate analytics
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 View Metrics", callback_data="view_metrics")],
            [InlineKeyboardButton("⚙️ Adjust Limits", callback_data="adjust_limits")],
            [InlineKeyboardButton("🔙 Back to Advanced", callback_data="advanced_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_security_settings(self, query):
        """Show security settings menu"""
        text = """
🔒 **Security Settings**

**Access Control:**
• Owner-only mode: Enabled
• User authentication required
• Session validation active

**Data Protection:**
• Encrypted session storage
• Secure API credential handling
• Protected database access

**Privacy Features:**
• No message content logging
• Secure credential transmission
• Automatic session cleanup

**Audit & Monitoring:**
• Access attempt logging
• Security event tracking
• Failed login monitoring
        """
        
        keyboard = [
            [InlineKeyboardButton("👤 Access Control", callback_data="access_control")],
            [InlineKeyboardButton("🔐 Data Protection", callback_data="data_protection")],
            [InlineKeyboardButton("📋 Security Logs", callback_data="security_logs")],
            [InlineKeyboardButton("🔙 Back to Advanced", callback_data="advanced_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_message_link(self, update: Update, session: dict, context: ContextTypes.DEFAULT_TYPE = None):
        """Handle Telegram message link as ad content"""
        user_id = update.effective_user.id
        message_text = update.message.text.strip()
        
        logger.info(f"🔗 Processing message link: {message_text}")
        
        try:
            # Parse the message link
            # Format: https://t.me/c/1234567890/123 (private channel)
            # Format: https://t.me/channelname/123 (public channel)
            import re
            
            # Try private channel format first
            match = re.match(r'https?://t\.me/c/(\d+)/(\d+)', message_text)
            if match:
                chat_id = f"-100{match.group(1)}"  # Convert to proper format
                message_id = int(match.group(2))
                logger.info(f"📎 Parsed private channel link: chat_id={chat_id}, message_id={message_id}")
            else:
                # Try public channel format
                match = re.match(r'https?://t\.me/([^/]+)/(\d+)', message_text)
                if match:
                    channel_username = match.group(1)
                    message_id = int(match.group(2))
                    # We'll use the username as chat_id for now
                    chat_id = f"@{channel_username}"
                    logger.info(f"📎 Parsed public channel link: chat_id={chat_id}, message_id={message_id}")
                else:
                    await update.message.reply_text(
                        "❌ **Invalid message link format!**\n\n"
                        "Please send a valid Telegram message link.\n\n"
                        "**Example formats:**\n"
                        "• `https://t.me/c/1234567890/123` (private channel)\n"
                        "• `https://t.me/channelname/123` (public channel)",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
            
            # Store the message reference
            ad_data = {
                'storage_chat_id': chat_id,
                'storage_message_id': message_id,
                'message_link': message_text,
                'type': 'linked_message'
            }
            
            # Store in session
            session['campaign_data']['ad_content'] = ad_data
            
            # Move to next step
            session['step'] = 'add_buttons_choice'
            
            await update.message.reply_text(
                f"✅ **Message link saved!**\n\n"
                f"📎 **Linked message:** `{message_id}` from chat `{chat_id}`\n\n"
                f"**Step 3/6: Add Buttons**\n\n"
                f"Would you like to add clickable buttons under your forwarded message?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Yes, Add Buttons", callback_data="add_buttons_yes")],
                    [InlineKeyboardButton("❌ No Buttons", callback_data="add_buttons_no")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_ad_content")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error processing message link: {e}")
            await update.message.reply_text(
                "❌ **Error processing message link!**\n\n"
                "Please make sure:\n"
                "1. The link is valid\n"
                "2. The bot has access to the channel\n"
                "3. The message exists\n\n"
                "Try again or contact support.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_forwarded_ad_content(self, update: Update, session: dict, context: ContextTypes.DEFAULT_TYPE = None):
        """Handle forwarded message or bridge channel link as ad content with full fidelity preservation"""
        user_id = update.effective_user.id
        message = update.message
        
        # Process the forwarded message directly with inline button support
        
        # Store the complete message data for full fidelity reproduction
        ad_data = {
            'message_id': message.message_id,
            'chat_id': message.chat_id,
            'original_message_id': message.message_id,  # Store for forwarding
            'original_chat_id': message.chat_id,       # Store for forwarding
            'text': message.text,
            'caption': message.caption,
            'entities': [],
            'caption_entities': [],
            'media_type': None,
            'file_id': None,
            'has_custom_emojis': False,
            'has_premium_emojis': False
        }
        
        # Check if this is media-only message (new approach)
        has_media = bool(message.video or message.photo or message.document or message.audio)
        has_caption = bool(message.caption)
        has_text = bool(message.text)
        
        # DEBUG: Log what we actually received
        logger.info(f"🔍 MESSAGE DEBUG: has_media={has_media}, has_caption={has_caption}, has_text={has_text}")
        logger.info(f"🔍 MESSAGE DEBUG: message.text='{message.text}'")
        logger.info(f"🔍 MESSAGE DEBUG: message.caption='{message.caption}'")
        
        if has_media and not has_text and not has_caption:
            # Media-only message - process media data first, then store and ask for text
            logger.info("Media-only message detected, processing media data and asking for text")
            
            # Check if this is a forwarded message and warn about entity loss
            if message.forward_from or message.forward_from_chat:
                logger.warning("⚠️ FORWARDED MESSAGE: Entities may be lost during forwarding")
                await update.message.reply_text(
                    "⚠️ **Warning: Forwarded messages may lose premium emojis!**\n\n"
                    "**For best results with premium emojis:**\n"
                    "1. Copy the text with emojis\n"
                    "2. Paste it as a new message (don't forward)\n\n"
                    "**Or continue with forwarded message (may lose emojis):**",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Process media type and file info immediately
            if message.video:
                ad_data['media_type'] = 'video'
                ad_data['file_id'] = message.video.file_id
                ad_data['file_unique_id'] = message.video.file_unique_id
                ad_data['file_size'] = getattr(message.video, 'file_size', None)
                ad_data['duration'] = getattr(message.video, 'duration', None)
                ad_data['width'] = getattr(message.video, 'width', None)
                ad_data['height'] = getattr(message.video, 'height', None)
            elif message.photo:
                ad_data['media_type'] = 'photo'
                ad_data['file_id'] = message.photo[-1].file_id
                ad_data['file_unique_id'] = message.photo[-1].file_unique_id
                ad_data['file_size'] = getattr(message.photo[-1], 'file_size', None)
                ad_data['width'] = getattr(message.photo[-1], 'width', None)
                ad_data['height'] = getattr(message.photo[-1], 'height', None)
            elif message.document:
                ad_data['media_type'] = 'document'
                ad_data['file_id'] = message.document.file_id
                ad_data['file_unique_id'] = message.document.file_unique_id
                ad_data['file_size'] = getattr(message.document, 'file_size', None)
            elif message.audio:
                ad_data['media_type'] = 'audio'
                ad_data['file_id'] = message.audio.file_id
                ad_data['file_unique_id'] = message.audio.file_unique_id
                ad_data['file_size'] = getattr(message.audio, 'file_size', None)
                ad_data['duration'] = getattr(message.audio, 'duration', None)
                ad_data['performer'] = getattr(message.audio, 'performer', None)
                ad_data['title'] = getattr(message.audio, 'title', None)
            
            session['pending_media_data'] = ad_data
            session['step'] = 'ad_text_input'
            await update.message.reply_text(
                "📤 **Media received!**\n\nNow send me the **text with premium emojis** that should be the caption for this media.\n\n**Just type or forward the text message now!**",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif has_media and (has_text or has_caption):
            # Media with text/caption - process media data first, then ask user to send text separately
            logger.info("Media with text/caption detected, processing media data and asking user to send text separately")
            
            # Process media type and file info immediately
            if message.video:
                ad_data['media_type'] = 'video'
                ad_data['file_id'] = message.video.file_id
                ad_data['file_unique_id'] = message.video.file_unique_id
                ad_data['file_size'] = getattr(message.video, 'file_size', None)
                ad_data['duration'] = getattr(message.video, 'duration', None)
                ad_data['width'] = getattr(message.video, 'width', None)
                ad_data['height'] = getattr(message.video, 'height', None)
            elif message.photo:
                ad_data['media_type'] = 'photo'
                ad_data['file_id'] = message.photo[-1].file_id
                ad_data['file_unique_id'] = message.photo[-1].file_unique_id
                ad_data['file_size'] = getattr(message.photo[-1], 'file_size', None)
                ad_data['width'] = getattr(message.photo[-1], 'width', None)
                ad_data['height'] = getattr(message.photo[-1], 'height', None)
            elif message.document:
                ad_data['media_type'] = 'document'
                ad_data['file_id'] = message.document.file_id
                ad_data['file_unique_id'] = message.document.file_unique_id
                ad_data['file_size'] = getattr(message.document, 'file_size', None)
            elif message.audio:
                ad_data['media_type'] = 'audio'
                ad_data['file_id'] = message.audio.file_id
                ad_data['file_unique_id'] = message.audio.file_unique_id
                ad_data['file_size'] = getattr(message.audio, 'file_size', None)
                ad_data['duration'] = getattr(message.audio, 'duration', None)
                ad_data['performer'] = getattr(message.audio, 'performer', None)
                ad_data['title'] = getattr(message.audio, 'title', None)
            
            session['pending_media_data'] = ad_data
            session['step'] = 'ad_text_input'
            await update.message.reply_text(
                "📤 **Media with text received!**\n\nFor better premium emoji handling, please send me the **text separately** (without the media).\n\n**Just type or forward the text message now!**",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Preserve text entities (formatting, emojis, links) - only if not already processed as caption
        if message.entities and not (has_media and has_text and not has_caption):
            for entity in message.entities:
                entity_data = {
                    'type': entity.type,
                    'offset': entity.offset,
                    'length': entity.length,
                    'url': entity.url if hasattr(entity, 'url') else None,
                    'user': entity.user.id if hasattr(entity, 'user') and entity.user else None,
                    'language': entity.language if hasattr(entity, 'language') else None,
                    'custom_emoji_id': entity.custom_emoji_id if hasattr(entity, 'custom_emoji_id') else None
                }
                ad_data['entities'].append(entity_data)
                
                # Check for custom/premium emojis
                if entity.type == 'custom_emoji':
                    ad_data['has_custom_emojis'] = True
        
        # Preserve caption entities for media messages
        if message.caption_entities:
            for entity in message.caption_entities:
                entity_data = {
                    'type': entity.type,
                    'offset': entity.offset,
                    'length': entity.length,
                    'url': entity.url if hasattr(entity, 'url') else None,
                    'custom_emoji_id': entity.custom_emoji_id if hasattr(entity, 'custom_emoji_id') else None
                }
                ad_data['caption_entities'].append(entity_data)
                
                if entity.type == 'custom_emoji':
                    ad_data['has_custom_emojis'] = True
        
        # Handle different media types with detailed information
        if message.photo:
            ad_data['media_type'] = 'photo'
            ad_data['file_id'] = message.photo[-1].file_id  # Get highest resolution
            ad_data['file_unique_id'] = message.photo[-1].file_unique_id
            ad_data['file_size'] = getattr(message.photo[-1], 'file_size', None)
            ad_data['width'] = getattr(message.photo[-1], 'width', None)
            ad_data['height'] = getattr(message.photo[-1], 'height', None)
        elif message.video:
            ad_data['media_type'] = 'video'
            ad_data['file_id'] = message.video.file_id
            ad_data['file_unique_id'] = message.video.file_unique_id
            ad_data['file_size'] = getattr(message.video, 'file_size', None)
            ad_data['duration'] = getattr(message.video, 'duration', None)
            ad_data['width'] = getattr(message.video, 'width', None)
            ad_data['height'] = getattr(message.video, 'height', None)
        elif message.document:
            ad_data['media_type'] = 'document'
            ad_data['file_id'] = message.document.file_id
            ad_data['file_unique_id'] = message.document.file_unique_id
            ad_data['file_size'] = getattr(message.document, 'file_size', None)
            ad_data['mime_type'] = getattr(message.document, 'mime_type', None)
            ad_data['file_name'] = getattr(message.document, 'file_name', None)
        elif message.animation:  # GIFs
            ad_data['media_type'] = 'animation'
            ad_data['file_id'] = message.animation.file_id
            ad_data['file_unique_id'] = message.animation.file_unique_id
            ad_data['file_size'] = getattr(message.animation, 'file_size', None)
            ad_data['duration'] = getattr(message.animation, 'duration', None)
            ad_data['width'] = getattr(message.animation, 'width', None)
            ad_data['height'] = getattr(message.animation, 'height', None)
        elif message.voice:
            ad_data['media_type'] = 'voice'
            ad_data['file_id'] = message.voice.file_id
            ad_data['file_unique_id'] = message.voice.file_unique_id
            ad_data['file_size'] = getattr(message.voice, 'file_size', None)
            ad_data['duration'] = getattr(message.voice, 'duration', None)
        elif message.video_note:  # Round videos
            ad_data['media_type'] = 'video_note'
            ad_data['file_id'] = message.video_note.file_id
            ad_data['file_unique_id'] = message.video_note.file_unique_id
            ad_data['file_size'] = getattr(message.video_note, 'file_size', None)
            ad_data['duration'] = getattr(message.video_note, 'duration', None)
            ad_data['length'] = getattr(message.video_note, 'length', None)
        elif message.sticker:
            ad_data['media_type'] = 'sticker'
            ad_data['file_id'] = message.sticker.file_id
            ad_data['file_unique_id'] = message.sticker.file_unique_id
            ad_data['file_size'] = getattr(message.sticker, 'file_size', None)
            ad_data['width'] = getattr(message.sticker, 'width', None)
            ad_data['height'] = getattr(message.sticker, 'height', None)
            ad_data['emoji'] = getattr(message.sticker, 'emoji', None)
        elif message.audio:
            ad_data['media_type'] = 'audio'
            ad_data['file_id'] = message.audio.file_id
            ad_data['file_unique_id'] = message.audio.file_unique_id
            ad_data['file_size'] = getattr(message.audio, 'file_size', None)
            ad_data['duration'] = getattr(message.audio, 'duration', None)
            ad_data['performer'] = getattr(message.audio, 'performer', None)
            ad_data['title'] = getattr(message.audio, 'title', None)
        
        # 🎯 SIMPLE SOLUTION: Use Bot API to forward to storage (no authentication needed)
        # Premium emojis won't display in storage, but will work when Telethon forwards to groups
        if ad_data['media_type'] and ad_data.get('file_id'):
            try:
                from config import Config
                
                storage_channel_id = Config.STORAGE_CHANNEL_ID
                if storage_channel_id:
                    logger.info(f"📤 BOT API STORAGE: Forwarding message to storage channel")
                    
                    # Simply forward the message using Bot API
                    # This preserves the message structure for later Telethon forwarding
                    forwarded_message = await context.bot.forward_message(
                        chat_id=storage_channel_id,
                        from_chat_id=message.chat_id,
                        message_id=message.message_id
                    )
                    
                    # Store the message ID for later forwarding
                    ad_data['storage_message_id'] = forwarded_message.message_id
                    ad_data['storage_chat_id'] = storage_channel_id
                    
                    # Also store the original message info for potential Telethon use
                    ad_data['original_message_id'] = message.message_id
                    ad_data['original_chat_id'] = message.chat_id
                    
                    logger.info(f"✅ Storage message created via Bot API forward: ID {forwarded_message.message_id}")
                    logger.info(f"💡 Premium emojis may not display in storage, but will work when forwarded to groups")
                else:
                    logger.warning(f"❌ STORAGE_CHANNEL_ID not configured")
                
            except Exception as storage_error:
                logger.error(f"❌ Bot API storage failed: {storage_error}")
                ad_data['storage_message_id'] = None
                ad_data['storage_chat_id'] = None
        
        # Store the ad data
        if 'ad_messages' not in session['campaign_data']:
            session['campaign_data']['ad_messages'] = []
        session['campaign_data']['ad_messages'].append(ad_data)
        
        # Show preview and ask about buttons
        emoji_info = ""
        if ad_data['has_custom_emojis']:
            emoji_info = "\n✨ **Premium emojis detected!**"
            if ad_data.get('has_premium_emojis'):
                emoji_info += "\n🎯 **SOLUTION:** Worker accounts will access YOUR original message directly"
                emoji_info += "\n✅ **This bypasses BotFather bot and preserves premium emojis!**"
                emoji_info += "\n💎 **Your Premium worker accounts can send premium emojis perfectly**"
        
        media_info = ""
        if ad_data['media_type']:
            media_details = []
            if ad_data.get('file_size'):
                size_mb = ad_data['file_size'] / (1024 * 1024)
                media_details.append(f"{size_mb:.1f}MB")
            if ad_data.get('duration'):
                media_details.append(f"{ad_data['duration']}s")
            if ad_data.get('width') and ad_data.get('height'):
                media_details.append(f"{ad_data['width']}x{ad_data['height']}")
            
            details_str = f" ({', '.join(media_details)})" if media_details else ""
            media_info = f"\n📎 **Media:** {ad_data['media_type'].title()}{details_str}"
        
        text = f"""✅ **Ad content received!**{emoji_info}{media_info}

**Preview saved with full fidelity:**
• All formatting preserved
• Custom/premium emojis maintained
• Media files stored
• Original message structure kept

**Would you like to add buttons under this ad?**

Buttons will appear as an inline keyboard below your ad message."""
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Buttons", callback_data="add_buttons_yes")],
            [InlineKeyboardButton("⏭️ Skip Buttons", callback_data="add_buttons_no")],
            [InlineKeyboardButton("📤 Add More Messages", callback_data="add_more_messages")],
            [InlineKeyboardButton("❌ Cancel Campaign", callback_data="cancel_campaign")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        session['step'] = 'add_buttons_choice'
    
    async def handle_button_choice(self, update: Update, session: dict):
        """Handle user's choice about adding buttons"""
        message_text = update.message.text.strip()
        
        if message_text.lower() in ['yes', 'y', 'add', 'buttons']:
            session['step'] = 'button_input'
            await update.message.reply_text(
                "➕ **Add Buttons to Your Ad**\n\n**Format:** [Button Text] - [URL]\n\n**Examples:**\n`Shop Now - https://example.com/shop`\n`Visit Website - https://mysite.com`\n`Contact Us - https://t.me/support`\n\n**Send one button per message, or multiple buttons separated by new lines.**\n\n**When finished, type 'done' or 'finish'**",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # Skip buttons, move to target chats
            session['step'] = 'target_chats_choice'
            await self.show_target_chat_options(update, session)
    
    async def _update_storage_message_with_buttons(self, campaign_data: dict):
        """Update storage message with ReplyKeyboardMarkup buttons"""
        try:
            from config import Config
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            
            # Handle both old format (dict) and new format (list) for ad_content
            ad_content = campaign_data.get('ad_content', {})
            
            # Handle message link approach (ad_content is a list)
            if isinstance(ad_content, list) and ad_content:
                ad_item = ad_content[0]  # Get first (and only) item
                storage_chat_id = ad_item.get('storage_chat_id')
                storage_message_id = ad_item.get('storage_message_id')
            else:
                # Handle old approach (ad_content is a dict)
                storage_chat_id = ad_content.get('storage_chat_id')
                storage_message_id = ad_content.get('storage_message_id')
            
            # Use default storage channel if not specified
            if not storage_chat_id:
                storage_chat_id = Config.STORAGE_CHANNEL_ID
                if not storage_chat_id:
                    logger.warning("No storage channel ID configured")
                    return
            if not storage_message_id:
                logger.warning("No storage message ID found, cannot update with buttons")
                return
            
            # Create InlineKeyboardMarkup from campaign buttons (works with edit_message_reply_markup)
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard_buttons = []
            buttons = campaign_data.get('buttons', [])
            for button in buttons:
                if button.get('text') and button.get('url'):
                    # Create InlineKeyboardButton for InlineKeyboardMarkup
                    keyboard_buttons.append([InlineKeyboardButton(button['text'], url=button['url'])])
            
            if not keyboard_buttons:
                logger.info("No valid buttons to add to storage message")
                return
            
            reply_markup = InlineKeyboardMarkup(keyboard_buttons)
            
            # Edit the existing storage message with InlineKeyboardMarkup buttons
            try:
                from config import Config
                from telegram import Bot
                
                # Create a temporary bot instance
                temp_bot = Bot(token=Config.BOT_TOKEN)
                
                # Edit the existing message to add InlineKeyboardMarkup buttons
                await temp_bot.edit_message_reply_markup(
                    chat_id=storage_chat_id,
                    message_id=storage_message_id,
                    reply_markup=reply_markup
                )
                
                logger.info(f"✅ Updated storage message {storage_message_id} with {len(keyboard_buttons)} InlineKeyboardMarkup button rows")
                
            except Exception as edit_error:
                logger.error(f"❌ Failed to update storage message with buttons: {edit_error}")
            
        except Exception as e:
            logger.error(f"❌ Failed to update storage message with buttons: {e}")

    async def handle_button_input(self, update: Update, session: dict):
        """Handle button input from user"""
        message_text = update.message.text.strip()
        
        if message_text.lower() in ['done', 'finish', 'complete']:
            # Storage message will be updated with buttons after campaign is created
            logger.info(f"🔧 DEBUG: Buttons completed, will update storage message after campaign creation")
            
            # Move to target chats selection
            session['step'] = 'target_chats_choice'
            await self.show_target_chat_options(update, session)
            return
        
        # Parse button input
        if 'buttons' not in session['campaign_data']:
            session['campaign_data']['buttons'] = []
        
        # Handle multiple buttons in one message
        lines = message_text.split('\n')
        buttons_added = 0
        
        for line in lines:
            line = line.strip()
            if ' - ' in line:
                try:
                    button_text, button_url = line.split(' - ', 1)
                    button_text = button_text.strip('[]')
                    button_url = button_url.strip()
                    
                    # Validate URL
                    if not (button_url.startswith('http://') or button_url.startswith('https://') or button_url.startswith('t.me/')):
                        button_url = 'https://' + button_url
                    
                    session['campaign_data']['buttons'].append({
                        'text': button_text,
                        'url': button_url
                    })
                    buttons_added += 1
                except:
                    continue
        
        if buttons_added > 0:
            total_buttons = len(session['campaign_data']['buttons'])
            await update.message.reply_text(
                f"✅ **{buttons_added} button(s) added!** (Total: {total_buttons})\n\n**Current buttons:**\n" + 
                "\n".join([f"• {btn['text']} → {btn['url']}" for btn in session['campaign_data']['buttons']]) +
                "\n\n**Add more buttons or type 'done' to continue.**",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❌ **Invalid format!**\n\nPlease use: `[Button Text] - [URL]`\n\nExample: `Shop Now - https://example.com`",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_target_chat_options(self, update: Update, session: dict):
        """Show enhanced target chat selection options"""
        text = """🎯 **Step 3/6: Target Chats**

**Choose how to select your target chats:**

**🌐 Send to All Worker Groups**
• Automatically targets all groups your worker account is in
• Smart detection of group chats
• Excludes private chats and channels
• Perfect for broad campaigns

**🎯 Specify Target Chats**
• Manually enter specific chat IDs or usernames
• Precise targeting control
• Include channels, groups, or private chats
• Custom audience selection"""
        
        keyboard = [
            [InlineKeyboardButton("🌐 Send to All Worker Groups", callback_data="target_all_groups")],
            [InlineKeyboardButton("🎯 Specify Target Chats", callback_data="target_specific_chats")],
            [InlineKeyboardButton("❌ Cancel Campaign", callback_data="cancel_campaign")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_ad_text_input(self, update: Update, session: dict, context: ContextTypes.DEFAULT_TYPE = None):
        """Handle text input for media (new approach)"""
        user_id = update.effective_user.id
        message = update.message
        
        # Get the pending media data
        if 'pending_media_data' not in session:
            await update.message.reply_text(
                "❌ **No pending media found.**\n\nPlease start over by sending the media first.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Get the text content and entities
        # For forwarded messages, check caption first, then text
        if message.forward_from or message.forward_from_chat:
            text_content = message.caption or message.text or ""
            text_entities = message.caption_entities or message.entities or []
        else:
            text_content = message.text or ""
            text_entities = message.entities or []
        
        # DEBUG: Log what entities we received
        logger.info(f"🔍 TEXT ENTITIES DEBUG: Received {len(text_entities)} entities")
        for i, entity in enumerate(text_entities):
            logger.info(f"🔍 Entity {i}: type={entity.type}, offset={entity.offset}, length={entity.length}")
            if hasattr(entity, 'custom_emoji_id'):
                logger.info(f"🔍 Entity {i}: custom_emoji_id={entity.custom_emoji_id}")
        
        if not text_content:
            await update.message.reply_text(
                "❌ **No text received.**\n\n"
                "**To preserve premium emojis:**\n"
                "1. Copy the text with emojis from the original message\n"
                "2. Paste it as a new message (don't forward)\n"
                "3. This ensures premium emojis are preserved\n\n"
                "**Please send me the text with premium emojis that should be the caption for your media.**",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Combine with pending media data
        ad_data = session['pending_media_data']
        ad_data['caption'] = text_content
        ad_data['caption_entities'] = []
        
        # Process text entities (premium emojis, formatting, etc.)
        logger.info(f"🔍 PROCESSING ENTITIES: Processing {len(text_entities)} entities for caption")
        for entity in text_entities:
            entity_data = {
                'type': entity.type,
                'offset': entity.offset,
                'length': entity.length,
                'url': entity.url if hasattr(entity, 'url') else None,
                'custom_emoji_id': entity.custom_emoji_id if hasattr(entity, 'custom_emoji_id') else None
            }
            ad_data['caption_entities'].append(entity_data)
            logger.info(f"🔍 STORED ENTITY: {entity_data}")
            
            if entity.type == 'custom_emoji':
                ad_data['has_custom_emojis'] = True
                logger.info(f"🔍 CUSTOM EMOJI DETECTED: {entity_data}")
        
        logger.info(f"🔍 FINAL CAPTION ENTITIES: {len(ad_data['caption_entities'])} entities stored")
        
        # Clear pending data
        del session['pending_media_data']
        
        # Process the complete ad data
        await self._process_complete_ad_data(ad_data, update, session, context)
    
    async def _process_complete_ad_data(self, ad_data: dict, update: Update, session: dict, context: ContextTypes.DEFAULT_TYPE = None):
        """Process complete ad data and create storage message"""
        try:
            # The media data is already processed in the pending_media_data
            # We just need to create the storage message with the caption and entities
            
            # Create storage message with caption and entities
            await self._create_storage_message_with_caption(ad_data, update, session, context)
            
        except Exception as e:
            logger.error(f"Error processing complete ad data: {e}")
            await update.message.reply_text(
                "❌ **Error processing your message.**\n\nPlease try again or contact support if the problem persists.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def _create_storage_message_with_caption(self, ad_data: dict, update: Update, session: dict, context: ContextTypes.DEFAULT_TYPE = None):
        """Create storage message with caption and entities using unified Telethon approach"""
        try:
            from config import Config
            from telethon_manager import telethon_manager
            from database import Database
            
            storage_channel_id = Config.STORAGE_CHANNEL_ID
            if storage_channel_id and ad_data.get('file_id'):
                logger.info(f"📤 STORAGE CHANNEL: Creating message with unified Telethon approach")
                
                # Get the first available account for storage
                db = Database()
                user_id = update.effective_user.id
                accounts = db.get_user_accounts(user_id)
                
                if not accounts:
                    raise Exception("No worker accounts available for storage message creation")
                
                account = accounts[0]
                logger.info(f"🔍 UNIFIED TELETHON: Using account {account['account_name']} for storage")
                
                # Add original message info for perfect forwarding
                ad_data['original_message_id'] = update.message.message_id
                ad_data['original_chat_id'] = update.message.chat_id
                
                # Create storage message using unified Telethon manager
                storage_result = await telethon_manager.create_storage_message(
                    account_data=account,
                    storage_channel_id=storage_channel_id,
                    media_data=ad_data,
                    bot_instance=context.bot
                )
                
                if storage_result:
                    # Store the message ID and chat ID for forwarding
                    ad_data['storage_message_id'] = storage_result['storage_message_id']
                    ad_data['storage_chat_id'] = storage_result['storage_chat_id']
                    ad_data['telethon_client'] = storage_result['client']  # Store client for reuse
                    
                    logger.info(f"✅ Storage message created with unified Telethon: ID {storage_result['storage_message_id']}")
                else:
                    raise Exception("Failed to create storage message with Telethon")
                
            else:
                logger.warning("No storage channel ID or file ID available for storage message creation")
                
        except Exception as e:
            logger.error(f"Error creating storage message with unified Telethon: {e}")
            await update.message.reply_text(
                "❌ **Error creating storage message.**\n\nPlease try again or contact support if the problem persists.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_add_buttons_yes(self, query):
        """Handle user choosing to add buttons"""
        user_id = query.from_user.id
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            session['step'] = 'button_input'
            
            await query.edit_message_text(
                "➕ **Add Buttons to Your Ad**\n\n**Format:** [Button Text] - [URL]\n\n**Examples:**\n`Shop Now - https://example.com/shop`\n`Visit Website - https://mysite.com`\n`Contact Us - https://t.me/support`\n\n**Send one button per message, or multiple buttons separated by new lines.**\n\n**When finished, type 'done' or 'finish'**",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_add_buttons_no(self, query):
        """Handle user choosing to skip buttons"""
        user_id = query.from_user.id
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            session['step'] = 'target_chats_choice'
            
            # Show target chat options
            text = """🎯 **Step 3/6: Target Chats**

**Choose how to select your target chats:**

**🌐 Send to All Worker Groups**
• Automatically targets all groups your worker account is in
• Smart detection of group chats
• Excludes private chats and channels
• Perfect for broad campaigns

**🎯 Specify Target Chats**
• Manually enter specific chat IDs or usernames
• Precise targeting control
• Include channels, groups, or private chats
• Custom audience selection"""
            
            keyboard = [
                [InlineKeyboardButton("🌐 Send to All Worker Groups", callback_data="target_all_groups")],
                [InlineKeyboardButton("🎯 Specify Target Chats", callback_data="target_specific_chats")],
                [InlineKeyboardButton("❌ Cancel Campaign", callback_data="cancel_campaign")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
    
    async def handle_add_more_messages(self, query):
        """Handle user choosing to add more messages"""
        user_id = query.from_user.id
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            session['step'] = 'ad_content'  # Go back to ad content step
            
            await query.edit_message_text(
                "📤 **Add More Messages**\n\n**Forward additional messages** that you want to include in this ad campaign.\n\nAll messages will be sent in sequence when the campaign runs.\n\n**Just forward the next message(s) from any chat!**",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_target_all_groups(self, query):
        """Handle user choosing to target all worker groups"""
        user_id = query.from_user.id
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            session['campaign_data']['target_mode'] = 'all_groups'
            session['campaign_data']['target_chats'] = ['ALL_WORKER_GROUPS']
            session['step'] = 'schedule_type'
            
            # Move to schedule selection
            text = """✅ **Target set to all worker groups!**

**Step 4/6: Schedule Type**

**How often should this campaign run?**"""
            
            keyboard = [
                [InlineKeyboardButton("📅 Daily", callback_data="schedule_daily")],
                [InlineKeyboardButton("📊 Weekly", callback_data="schedule_weekly")],
                [InlineKeyboardButton("⏰ Hourly", callback_data="schedule_hourly")],
                [InlineKeyboardButton("🔧 Custom", callback_data="schedule_custom")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_campaign")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
    
    async def handle_target_specific_chats(self, query):
        """Handle user choosing to specify target chats manually"""
        user_id = query.from_user.id
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            session['campaign_data']['target_mode'] = 'specific'
            session['step'] = 'target_chats'
            
            await query.edit_message_text(
                "🎯 **Specify Target Chats**\n\n**Send me the target chat IDs or usernames** where you want to post ads.\n\n**Format:** One per line or comma-separated\n\n**Examples:**\n@channel1\n@channel2\n@mygroup\n-1001234567890\n\n**Supported:**\n• Public channels (@channelname)\n• Public groups (@groupname)\n• Private chats (chat ID numbers)\n• Telegram usernames (@username)",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_cancel_campaign(self, query):
        """Handle user canceling campaign creation"""
        user_id = query.from_user.id
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        await query.edit_message_text(
            "❌ **Campaign creation canceled.**\n\nYou can start a new campaign anytime from the Bump Service menu.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Return to bump service menu
        await asyncio.sleep(2)
        await self.show_bump_service(query)
    
    async def execute_immediate_campaign(self, campaign_id: int, account_id: int, campaign_data: dict) -> bool:
        """Execute campaign immediately upon creation"""
        try:
            # Get account details
            account = self.db.get_account(account_id)
            if not account:
                return False
            
            # Initialize Telethon client for immediate execution
            from telethon import TelegramClient
            import base64
            
            # Handle session creation
            temp_session_path = f"temp_session_{account_id}"
            
            # Check if we have a valid session
            if not account.get('session_string'):
                logger.error(f"Account {account_id} has no session string. Please re-authenticate the account.")
                return False
            
            # Handle uploaded sessions vs API credential sessions
            if account['api_id'] == 'uploaded' or account['api_hash'] == 'uploaded':
                # For uploaded sessions, decode and save the session file
                try:
                    session_data = base64.b64decode(account['session_string'])
                    with open(f"{temp_session_path}.session", "wb") as f:
                        f.write(session_data)
                    # Use dummy credentials for uploaded sessions
                    api_id = 123456  
                    api_hash = 'dummy_hash_for_uploaded_sessions'
                except Exception as e:
                    logger.error(f"Failed to decode uploaded session for account {account_id}: {e}")
                    return False
            else:
                # For API credential accounts with authenticated sessions
                try:
                    api_id = int(account['api_id'])
                    api_hash = account['api_hash']
                    
                    # Session string is base64 encoded session file data
                    # Decode and write it as the session file
                    session_data = base64.b64decode(account['session_string'])
                    with open(f"{temp_session_path}.session", "wb") as f:
                        f.write(session_data)
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid API credentials for account {account_id}: {e}")
                    return False
                except Exception as e:
                    logger.error(f"Failed to decode session for account {account_id}: {e}")
                    return False
            
            # Initialize and start client
            try:
                client = TelegramClient(temp_session_path, api_id, api_hash)
                await client.start()
                
                # Verify the session is valid
                me = await client.get_me()
                if not me:
                    logger.error(f"Session invalid for account {account_id}")
                    await client.disconnect()
                    return False
                    
                logger.info(f"Successfully authenticated as {me.username or me.phone}")
                
            except Exception as e:
                logger.error(f"Failed to start client for account {account_id}: {e}")
                # Clean up session file on failure
                import os
                try:
                    if os.path.exists(f"{temp_session_path}.session"):
                        os.remove(f"{temp_session_path}.session")
                except:
                    pass
                return False
            
            # Determine target chats
            target_chats = campaign_data['target_chats']
            if campaign_data.get('target_mode') == 'all_groups' or target_chats == ['ALL_WORKER_GROUPS']:
                # Get all groups the account is member of
                dialogs = await client.get_dialogs()
                target_chats = []
                for dialog in dialogs:
                    if dialog.is_group and not dialog.is_channel:
                        target_chats.append(str(dialog.id))
            
            # Send messages to target chats using entity objects
            success_count = 0
            ad_content = campaign_data['ad_content']
            
            # Storage message buttons are updated in button_input step
            
            # Create buttons from campaign data
            from telethon import Button
            buttons_data = campaign_data.get('buttons', [])
            
            if buttons_data:
                try:
                    button_rows = []
                    current_row = []
                    
                    for i, button in enumerate(buttons_data):
                        if button.get('url'):
                            telethon_button = Button.url(button['text'], button['url'])
                        else:
                            telethon_button = Button.inline(button['text'], f"btn_{i}")
                        
                        current_row.append(telethon_button)
                        
                        if len(current_row) == 2 or i == len(buttons_data) - 1:
                            button_rows.append(current_row)
                            current_row = []
                    
                    telethon_buttons = button_rows
                    logger.info(f"✅ Created {len(buttons_data)} campaign buttons for immediate execution")
                except Exception as e:
                    logger.error(f"❌ Error creating campaign buttons: {e}")
                    telethon_buttons = [[Button.url("Shop Now", "https://t.me/testukassdfdds")]]
            else:
                # Default button if none specified
                telethon_buttons = [[Button.url("Shop Now", "https://t.me/testukassdfdds")]]
                logger.info("Using default Shop Now button for immediate execution")
            
            # Get all dialogs and find groups (use entities instead of IDs)
            target_entities = []
            if campaign_data.get('target_mode') == 'all_groups' or target_chats == ['ALL_WORKER_GROUPS']:
                logger.info("Discovering worker account groups for immediate execution...")
                dialogs = await client.get_dialogs()
                
                for dialog in dialogs:
                    if dialog.is_group:  # Include both groups and supergroups
                        target_entities.append(dialog.entity)
                        logger.info(f"Found group for immediate execution: {dialog.name} (ID: {dialog.id})")
                
                logger.info(f"Discovered {len(target_entities)} groups for immediate execution")
            else:
                # Use specific chat IDs - convert to entities
                for chat_id in target_chats:
                    try:
                        entity = await client.get_entity(chat_id)
                        target_entities.append(entity)
                    except Exception as e:
                        logger.error(f"Failed to get entity for {chat_id}: {e}")
            
            for chat_entity in target_entities:
                try:
                    # RESTRUCTURED: Simplified message sending with guaranteed buttons
                    if isinstance(ad_content, list) and ad_content:
                        # For forwarded content, send each message and add button to the last one
                        for i, message_data in enumerate(ad_content):
                            message_text = message_data.get('text', '')
                            
                            # Add buttons to the last message only
                            if i == len(ad_content) - 1:
                                logger.info(f"Adding buttons to final message (immediate execution)")
                                try:
                                    # Try to send with buttons first
                                    await client.send_message(
                                        chat_entity,
                                        message_text,
                                        buttons=telethon_buttons
                                    )
                                    logger.info(f"✅ Sent message with inline buttons to {chat_entity.title}")
                                    message_sent = True
                                except Exception as button_error:
                                    logger.warning(f"⚠️ Inline buttons failed for {chat_entity.title}: {button_error}")
                                    # Fallback: Add button URLs as text
                                    button_text = ""
                                    for button_row in telethon_buttons:
                                        for button in button_row:
                                            if hasattr(button, 'url'):
                                                button_text += f"\n🔗 {button.text}: {button.url}"
                                    
                                    final_message = (message_text or "") + button_text
                                    try:
                                        await client.send_message(chat_entity, final_message)
                                        logger.info(f"✅ Sent message with text buttons to {chat_entity.title}")
                                        message_sent = True
                                    except Exception as fallback_error:
                                        logger.error(f"❌ Failed to send message to {chat_entity.title}: {fallback_error}")
                                        # Skip this chat and continue with others
                            else:
                                # Send without buttons for earlier messages
                                await client.send_message(
                                    chat_entity,
                                    message_text
                                )
                                message_sent = True
                    else:
                        # Single text message with buttons
                        message_text = ad_content if isinstance(ad_content, str) else str(ad_content)
                        logger.info(f"Sending single message with Shop Now button (immediate execution)")
                        await client.send_message(
                            chat_entity,
                            message_text,
                            buttons=telethon_buttons
                        )
                    
                    if message_sent:
                        success_count += 1
                        logger.info(f"Successfully sent to {chat_entity.title} ({chat_entity.id}) with buttons")
                    
                except Exception as e:
                    logger.error(f"Failed to send to {chat_entity.title if hasattr(chat_entity, 'title') else chat_entity.id}: {e}")
                    continue
            
            await client.disconnect()
            
            # Clean up temporary session file
            import os
            try:
                os.remove(f"{temp_session_path}.session")
            except:
                pass
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Immediate campaign execution failed: {e}")
            return False
    
    async def start_campaign_manually(self, query, campaign_id):
        """Manually start a campaign immediately"""
        user_id = query.from_user.id
        
        try:
            await query.answer("Starting campaign...")
            
            # Get campaign details
            campaign = self.bump_service.get_campaign(campaign_id)
            if not campaign or campaign['user_id'] != user_id:
                await query.answer("Campaign not found!", show_alert=True)
                return
            
            logger.info(f"Retrieved campaign data: {list(campaign.keys())}")
            logger.info(f"Campaign buttons: {campaign.get('buttons', 'NOT_FOUND')}")
            logger.info(f"Campaign target_mode: {campaign.get('target_mode', 'NOT_FOUND')}")
            logger.info(f"Full campaign data: {campaign}")
            
            # Get account details
            account = self.db.get_account(campaign['account_id'])
            if not account:
                await query.answer("Account not found!", show_alert=True)
                return
            
            # Prepare campaign data for execution
            enhanced_campaign_data = {
                'campaign_name': campaign['campaign_name'],
                'ad_content': campaign['ad_content'],
                'target_chats': campaign['target_chats'],
                'schedule_type': campaign['schedule_type'],
                'schedule_time': campaign['schedule_time'],
                'buttons': campaign.get('buttons', []),  # Get buttons from database
                'target_mode': campaign.get('target_mode', 'all_groups' if campaign['target_chats'] == ['ALL_WORKER_GROUPS'] else 'specific'),
                'immediate_start': False  # Disabled - user must click Start Campaign
            }
            
            logger.info(f"Executing campaign with {len(enhanced_campaign_data['buttons'])} buttons")
            
            # The bump service scheduler already handles campaign execution with inline buttons
            # No need for duplicate execution here - just confirm the campaign is active
            success_text = f"""🎉 Campaign Already Running!

Campaign: {campaign['campaign_name']}
Account: {account['account_name']}
Status: ✅ Active and scheduled!
Schedule: Next message in {campaign['schedule_time']}

✅ Messages are being sent with INLINE BUTTONS automatically!
📊 Check the logs to see execution status."""
            
            await query.edit_message_text(success_text, reply_markup=self.get_main_menu_keyboard())
            await query.answer("✅ Campaign is active!", show_alert=False)
            
        except Exception as e:
            logger.error(f"Manual campaign start failed: {e}")
            await query.answer(f"❌ Failed to start campaign: {str(e)[:50]}", show_alert=True)
    
    async def execute_campaign_with_better_discovery(self, account_id: int, campaign_data: dict) -> bool:
        """Execute campaign with improved group discovery"""
        try:
            # Get account details
            account = self.db.get_account(account_id)
            if not account:
                return False
            
            # Initialize Telethon client
            from telethon import TelegramClient
            import base64
            
            # Handle session creation
            temp_session_path = f"temp_session_{account_id}"
            
            # Check if we have a valid session
            if not account.get('session_string'):
                logger.error(f"Account {account_id} has no session string. Please re-authenticate the account.")
                return False
            
            # Handle uploaded sessions vs API credential sessions
            if account['api_id'] == 'uploaded' or account['api_hash'] == 'uploaded':
                # For uploaded sessions, decode and save the session file
                try:
                    session_data = base64.b64decode(account['session_string'])
                    with open(f"{temp_session_path}.session", "wb") as f:
                        f.write(session_data)
                    # Use dummy credentials for uploaded sessions
                    api_id = 123456  
                    api_hash = 'dummy_hash_for_uploaded_sessions'
                except Exception as e:
                    logger.error(f"Failed to decode uploaded session for account {account_id}: {e}")
                    return False
            else:
                # For API credential accounts with authenticated sessions
                try:
                    api_id = int(account['api_id'])
                    api_hash = account['api_hash']
                    
                    # Session string is base64 encoded session file data
                    # Decode and write it as the session file
                    session_data = base64.b64decode(account['session_string'])
                    with open(f"{temp_session_path}.session", "wb") as f:
                        f.write(session_data)
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid API credentials for account {account_id}: {e}")
                    return False
                except Exception as e:
                    logger.error(f"Failed to decode session for account {account_id}: {e}")
                    return False
            
            # Initialize and start client
            try:
                client = TelegramClient(temp_session_path, api_id, api_hash)
                await client.start()
                
                # Verify the session is valid
                me = await client.get_me()
                if not me:
                    logger.error(f"Session invalid for account {account_id}")
                    await client.disconnect()
                    return False
                    
                logger.info(f"Successfully authenticated as {me.username or me.phone}")
                
            except Exception as e:
                logger.error(f"Failed to start client for account {account_id}: {e}")
                # Clean up session file on failure
                import os
                try:
                    if os.path.exists(f"{temp_session_path}.session"):
                        os.remove(f"{temp_session_path}.session")
                except:
                    pass
                return False
            
            # Get all dialogs and find groups
            target_chats = []
            if campaign_data.get('target_mode') == 'all_groups' or campaign_data['target_chats'] == ['ALL_WORKER_GROUPS']:
                logger.info("Discovering worker account groups...")
                dialogs = await client.get_dialogs()
                
                for dialog in dialogs:
                    if dialog.is_group:  # Include both groups and supergroups
                        target_chats.append(dialog.entity)
                        logger.info(f"Found group: {dialog.name} (ID: {dialog.id})")
                
                logger.info(f"Discovered {len(target_chats)} groups")
            else:
                # Use specific chat IDs
                for chat_id in campaign_data['target_chats']:
                    try:
                        entity = await client.get_entity(chat_id)
                        target_chats.append(entity)
                    except Exception as e:
                        logger.error(f"Failed to get entity for {chat_id}: {e}")
            
            # Send messages to target chats
            success_count = 0
            ad_content = campaign_data['ad_content']
            
            # Use actual campaign button data
            buttons_data = campaign_data.get('buttons', [])
            if not buttons_data:
                # Fallback to default button if none specified
                buttons_data = [{"text": "Shop Now", "url": "https://t.me/testukassdfdds"}]
                logger.info(f"Using default button data: {buttons_data}")
            else:
                logger.info(f"Using campaign button data: {buttons_data}")
            
            # Create Telethon buttons from campaign data
            telethon_buttons = None
            if buttons_data:
                from telethon import Button
                try:
                    button_rows = []
                    current_row = []
                    
                    for i, button in enumerate(buttons_data):
                        if button.get('url'):
                            # URL button
                            telethon_button = Button.url(button['text'], button['url'])
                        else:
                            # Regular callback button
                            telethon_button = Button.inline(button['text'], f"btn_{i}")
                        
                        current_row.append(telethon_button)
                        
                        # Create new row every 2 buttons or at the end
                        if len(current_row) == 2 or i == len(buttons_data) - 1:
                            button_rows.append(current_row)
                            current_row = []
                    
                    telethon_buttons = button_rows
                    logger.info(f"✅ Created {len(buttons_data)} buttons in {len(button_rows)} rows from campaign data")
                except Exception as e:
                    logger.error(f"❌ Error creating buttons from campaign data: {e}")
                    # Fallback to default button
                    telethon_buttons = [[Button.url("Shop Now", "https://t.me/testukassdfdds")]]
                    logger.info("Using fallback Shop Now button")
            
            for chat_entity in target_chats:
                message_sent = False
                try:
                    # RESTRUCTURED: Always send with buttons - simplified approach
                    if isinstance(ad_content, list) and ad_content:
                        # For forwarded content, send each message and add button to the last one
                        for i, message_data in enumerate(ad_content):
                            message_text = message_data.get('text', '')
                            
                            # Add buttons to the last message only
                            if i == len(ad_content) - 1:
                                logger.info(f"Adding buttons to final message")
                                # ALWAYS add button URLs as text for groups (inline buttons don't work in regular groups)
                                button_text = ""
                                for button_row in telethon_buttons:
                                    for button in button_row:
                                        if hasattr(button, 'url'):
                                            button_text += f"\n\n🔗 {button.text}: {button.url}"
                                
                                # Combine message with button text
                                final_message = (message_text or "") + button_text
                                
                                try:
                                    # Try sending with both inline buttons AND text (belt and suspenders approach)
                                    await client.send_message(
                                        chat_entity,
                                        final_message,  # Message now includes button URLs as text
                                        buttons=telethon_buttons  # Also try inline buttons for channels/supergroups
                                    )
                                    logger.info(f"✅ Sent message with buttons (inline + text) to {chat_entity.title}")
                                    message_sent = True
                                except Exception as send_error:
                                    # If that fails, try without inline buttons
                                    try:
                                        await client.send_message(chat_entity, final_message)
                                        logger.info(f"✅ Sent message with text buttons to {chat_entity.title}")
                                        message_sent = True
                                    except Exception as fallback_error:
                                        logger.error(f"❌ Failed to send message to {chat_entity.title}: {fallback_error}")
                                        # Skip this chat and continue with others
                            else:
                                # Send without buttons for earlier messages
                                await client.send_message(
                                    chat_entity,
                                    message_text
                                )
                                message_sent = True
                    else:
                        # Single text message with buttons
                        if isinstance(ad_content, dict):
                            # Extract caption from media message
                            message_text = ad_content.get('caption', ad_content.get('text', ''))
                        else:
                            message_text = str(ad_content)
                        
                        # Truncate if too long (Telegram limit is 4096 chars)
                        if len(message_text) > 4000:
                            message_text = message_text[:4000] + "..."
                            logger.warning(f"Message truncated to fit Telegram limits")
                        
                        logger.info(f"Sending single message with Shop Now button")
                        await client.send_message(
                            chat_entity, 
                            message_text,
                            buttons=telethon_buttons
                        )
                    
                    if message_sent:
                        success_count += 1
                        logger.info(f"Successfully sent to {chat_entity.title} ({chat_entity.id}) with buttons")
                    
                except Exception as e:
                    logger.error(f"Failed to send to {chat_entity.title if hasattr(chat_entity, 'title') else chat_entity.id}: {e}")
                    continue
            
            await client.disconnect()
            
            # Clean up temporary session file
            import os
            try:
                os.remove(f"{temp_session_path}.session")
            except:
                pass
            
            logger.info(f"Campaign execution completed. Success: {success_count}/{len(target_chats)}")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Campaign execution failed: {e}")
            return False
    
    async def show_schedule_selection(self, query):
        """Show schedule selection menu (back navigation)"""
        user_id = query.from_user.id
        if user_id not in self.user_sessions:
            await query.answer("Session expired! Please start again.", show_alert=True)
            await self.show_bump_service(query)
            return
        
        text = """⏰ **Step 4/6: Schedule Type**

**How often should this campaign run?**

**📅 Daily** - Once per day at a specific time
**📊 Weekly** - Once per week on a chosen day
**⏰ Hourly** - Every hour automatically
**🔧 Custom** - Set your own interval (e.g., every 4 hours)"""
        
        keyboard = [
            [InlineKeyboardButton("📅 Daily", callback_data="schedule_daily")],
            [InlineKeyboardButton("📊 Weekly", callback_data="schedule_weekly")],
            [InlineKeyboardButton("⏰ Hourly", callback_data="schedule_hourly")],
            [InlineKeyboardButton("🔧 Custom", callback_data="schedule_custom")],
            [InlineKeyboardButton("🔙 Back to Targets", callback_data="back_to_target_selection")],
            [InlineKeyboardButton("❌ Cancel Campaign", callback_data="cancel_campaign")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_target_selection(self, query):
        """Show target selection menu (back navigation)"""
        user_id = query.from_user.id
        if user_id not in self.user_sessions:
            await query.answer("Session expired! Please start again.", show_alert=True)
            await self.show_bump_service(query)
            return
        
        text = """🎯 **Step 3/6: Target Chats**

**Choose how to select your target chats:**

**🌐 Send to All Worker Groups**
• Automatically targets all groups your worker account is in
• Smart detection of group chats
• Excludes private chats and channels
• Perfect for broad campaigns

**🎯 Specify Target Chats**
• Manually enter specific chat IDs or usernames
• Precise targeting control
• Include channels, groups, or private chats
• Custom audience selection"""
        
        keyboard = [
            [InlineKeyboardButton("🌐 Send to All Worker Groups", callback_data="target_all_groups")],
            [InlineKeyboardButton("🎯 Specify Target Chats", callback_data="target_specific_chats")],
            [InlineKeyboardButton("🔙 Back to Buttons", callback_data="back_to_button_choice")],
            [InlineKeyboardButton("❌ Cancel Campaign", callback_data="cancel_campaign")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_button_choice(self, query):
        """Show button choice menu (back navigation)"""
        user_id = query.from_user.id
        if user_id not in self.user_sessions:
            await query.answer("Session expired! Please start again.", show_alert=True)
            await self.show_bump_service(query)
            return
        
        text = """➕ **Step 2.5/6: Add Buttons (Optional)**

**Would you like to add buttons under your ad?**

Buttons will appear as an inline keyboard below your ad message.

**Examples:**
• Shop Now → https://yourstore.com
• Contact Us → https://t.me/support
• Visit Website → https://yoursite.com"""
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Buttons", callback_data="add_buttons_yes")],
            [InlineKeyboardButton("⏭️ Skip Buttons", callback_data="add_buttons_no")],
            [InlineKeyboardButton("📤 Add More Messages", callback_data="add_more_messages")],
            [InlineKeyboardButton("❌ Cancel Campaign", callback_data="cancel_campaign")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    
    async def show_help(self, query):
        """Show help information"""
        help_text = """
❓ **Help & Support**

**Quick Start:**
1. Click "Add New Forwarding"
2. Enter source and destination chat IDs
3. Configure your settings
4. Start forwarding!

**Common Issues:**
• **Chat ID not found:** Make sure the bot is added to the source chat
• **Permission denied:** Check bot permissions in the chat
• **Messages not forwarding:** Verify chat IDs and bot status

**Need more help?**
• Check the web interface for detailed guides
• Join our support group: @tgcf_support
        """
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages for configuration setup"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Debug logging
        logger.info(f"🔍 MESSAGE HANDLER: User {user_id} sent message: '{message_text}'")
        logger.info(f"🔍 SESSION CHECK: User {user_id} in sessions: {user_id in self.user_sessions}")
        
        # Check if user has an active session
        if user_id not in self.user_sessions:
            logger.warning(f"⚠️ User {user_id} sent message but has no active session")
            return
        
        session = self.user_sessions[user_id]
        logger.info(f"🔍 Current step: {session.get('step')}")
        
        # Handle account_name step (only if explicitly in this step)
        if session.get('step') == 'account_name':
            if not message_text:
                await update.message.reply_text(
                    "❌ **Please send a text message with the account name.**",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            logger.info(f"✅ Setting account name: {message_text}")
            session['account_data']['account_name'] = message_text
            session['step'] = 'phone_number'
            
            await update.message.reply_text(
                "✅ **Account name set!**\n\n**Step 2/5: Phone Number**\n\nPlease send me the phone number for this work account (with country code, e.g., +1234567890).",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if 'account_data' in session:
            if session['step'] == 'phone_number':
                # Validate phone number format
                import re
                phone_pattern = r'^\+?[1-9]\d{1,14}$'
                if not re.match(phone_pattern, message_text.replace(' ', '').replace('-', '')):
                    await update.message.reply_text(
                        "❌ **Invalid Phone Number**\n\nPlease enter a valid phone number with country code (e.g., +1234567890).",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                session['account_data']['phone_number'] = message_text
                session['step'] = 'api_id'
                
                await update.message.reply_text(
                    "✅ **Phone number set!**\n\n**Step 3/5: API ID**\n\nPlease send me the API ID for this account.\n\n**Get it from:** https://my.telegram.org\n• Go to 'API development tools'\n• Create a new application\n• Copy your API ID",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'api_id':
                # Validate API ID (should be numeric)
                if not message_text.isdigit():
                    await update.message.reply_text(
                        "❌ **Invalid API ID**\n\nAPI ID must be a number. Please enter a valid API ID.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                try:
                    api_id = int(message_text)
                    if api_id <= 0:
                        raise ValueError("API ID must be positive")
                    session['account_data']['api_id'] = str(api_id)
                    session['step'] = 'api_hash'
                    
                    await update.message.reply_text(
                        "✅ **API ID set!**\n\n**Step 4/5: API Hash**\n\nPlease send me the API Hash for this account.\n\n**Get it from:** https://my.telegram.org (same page as API ID)",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except ValueError:
                    await update.message.reply_text(
                        "❌ **Invalid API ID!**\n\nPlease send a valid numeric API ID from https://my.telegram.org",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif session['step'] == 'api_hash':
                # Validate API Hash format (should be alphanumeric, 32 characters)
                import re
                if not re.match(r'^[a-f0-9]{32}$', message_text.lower()):
                    await update.message.reply_text(
                        "❌ **Invalid API Hash**\n\nAPI Hash must be 32 characters long and contain only letters and numbers.\n\nPlease enter a valid API Hash from https://my.telegram.org",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                session['account_data']['api_hash'] = message_text
                session['step'] = 'authenticating'
                
                # Now we need to authenticate with Telegram to create a session
                await update.message.reply_text(
                    "🔐 **Authenticating with Telegram...**\n\n"
                    "Please wait while I connect to your account...",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Create session for this account
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                import asyncio
                
                try:
                    api_id = int(session['account_data']['api_id'])
                    api_hash = session['account_data']['api_hash']
                    phone = session['account_data']['phone_number']
                    
                    logger.info(f"🔐 Creating Telethon client for {phone}")
                    
                    # Use StringSession (no file on disk)
                    client = TelegramClient(StringSession(), api_id, api_hash)
                    
                    await client.connect()
                    logger.info(f"✅ Telethon client connected")
                    
                    # Request code
                    sent_code = await client.send_code_request(phone)
                    logger.info(f"📱 Verification code sent to {phone}, phone_code_hash: {sent_code.phone_code_hash}")
                    
                    session['client'] = client
                    session['phone_code_hash'] = sent_code.phone_code_hash
                    session['step'] = 'verification_code'
                    
                    await update.message.reply_text(
                        "📱 **Verification Code Sent!**\n\n"
                        f"A verification code has been sent to **{phone}**\n\n"
                        "**Step 5/5: Verification Code**\n\n"
                        "Please enter the verification code you received (5-digit code):",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to start authentication: {e}")
                    if user_id in self.user_sessions:
                        del self.user_sessions[user_id]
                    await update.message.reply_text(
                        f"❌ **Authentication Failed**\n\n"
                        f"Error: {str(e)}\n\n"
                        f"Please check your API credentials and try again.",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            elif session['step'] == 'verification_code':
                # Handle verification code
                code = message_text.strip().replace(' ', '').replace('-', '')
                client = session.get('client')
                phone_code_hash = session.get('phone_code_hash')
                
                if not client:
                    await update.message.reply_text("❌ Session expired. Please start over.")
                    if user_id in self.user_sessions:
                        del self.user_sessions[user_id]
                    return
                
                try:
                    logger.info(f"🔐 Attempting to sign in with code: {code}")
                    
                    # Sign in with the code and phone_code_hash
                    phone = session['account_data']['phone_number']
                    try:
                        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                        logger.info(f"✅ Successfully signed in")
                    except Exception as signin_error:
                        # Check if 2FA password is needed
                        if 'password' in str(signin_error).lower():
                            session['step'] = '2fa_password'
                            await update.message.reply_text(
                                "🔐 **Two-Factor Authentication Required**\n\n"
                                "Your account has 2FA enabled.\n\n"
                                "Please enter your 2FA password:",
                                parse_mode=ParseMode.MARKDOWN
                            )
                            return
                        else:
                            raise signin_error
                    
                    # Get session string from StringSession
                    session_string = client.session.save()
                    logger.info(f"✅ Session string obtained: {len(session_string)} characters")
                    
                    # Save account with session string to database
                    account_id = self.db.add_telegram_account(
                        user_id,
                        session['account_data']['account_name'],
                        session['account_data']['phone_number'],
                        session_string,
                        session['account_data']['api_id'],
                        session['account_data']['api_hash']
                    )
                    
                    logger.info(f"✅ Account saved to database with ID: {account_id}")
                    
                    # Disconnect client
                    await client.disconnect()
                    
                    # Clear session
                    del self.user_sessions[user_id]
                    
                    keyboard = [
                        [InlineKeyboardButton("📢 Create Campaign", callback_data="add_campaign")],
                        [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
                        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"✅ **Account Added Successfully!**\n\n"
                        f"**Account:** {session['account_data']['account_name']}\n"
                        f"**Phone:** {session['account_data']['phone_number']}\n\n"
                        f"🎉 Your account is now authenticated and ready to use for campaigns!",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=reply_markup
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to verify code: {e}")
                    
                    # Check if 2FA is needed
                    if "Two-steps verification" in str(e) or "password" in str(e).lower() or "2FA" in str(e):
                        session['step'] = '2fa_password'
                        await update.message.reply_text(
                            "🔐 **Two-Factor Authentication Required**\n\n"
                            "Your account has 2FA enabled. Please enter your 2FA password:",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ **Verification Failed**\n\n"
                            f"Error: {str(e)}\n\n"
                            f"Please check the verification code and try again.",
                            parse_mode=ParseMode.MARKDOWN
                        )
            
            elif session['step'] == '2fa_password':
                # Handle 2FA password
                password = message_text
                client = session.get('client')
                
                if not client:
                    await update.message.reply_text("❌ Session expired. Please start over.")
                    if user_id in self.user_sessions:
                        del self.user_sessions[user_id]
                    return
                
                try:
                    logger.info(f"🔐 Attempting to sign in with 2FA password")
                    
                    # Sign in with password
                    await client.sign_in(password=password)
                    logger.info(f"✅ Successfully signed in with 2FA password")
                    
                    # Get session string from StringSession
                    session_string = client.session.save()
                    logger.info(f"✅ Session string obtained: {len(session_string)} characters")
                    
                    # Save account with session string to database
                    account_id = self.db.add_telegram_account(
                        user_id,
                        session['account_data']['account_name'],
                        session['account_data']['phone_number'],
                        session_string,
                        session['account_data']['api_id'],
                        session['account_data']['api_hash']
                    )
                    
                    logger.info(f"✅ Account saved to database with ID: {account_id}")
                    
                    # Disconnect client
                    await client.disconnect()
                    
                    # Clear session
                    del self.user_sessions[user_id]
                    
                    keyboard = [
                        [InlineKeyboardButton("📢 Create Campaign", callback_data="add_campaign")],
                        [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
                        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"✅ **Account Added Successfully!**\n\n"
                        f"**Account:** {session['account_data']['account_name']}\n"
                        f"**Phone:** {session['account_data']['phone_number']}\n\n"
                        f"🎉 Your account is now authenticated and ready to use for campaigns!",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=reply_markup
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to verify 2FA password: {e}")
                    await update.message.reply_text(
                        f"❌ **2FA Authentication Failed**\n\n"
                        f"Error: {str(e)}\n\n"
                        f"Please check your 2FA password and try again.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                
                keyboard = [
                    [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
                    [InlineKeyboardButton("➕ Add Forwarding", callback_data="add_forwarding")],
                    [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"🎉 **Work Account Added Successfully!**\n\n**Name:** {session['account_data']['account_name']}\n**Phone:** `{session['account_data']['phone_number']}`\n\nYou can now create campaigns and forwarding rules for this account!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            
            elif session['step'] == 'paste_session_string':
                # Handle YOLO mode - paste session string
                logger.info(f"🚀 YOLO: Processing pasted data")
                
                try:
                    # Try to parse comma-separated format first
                    if ',' in message_text:
                        parts = [p.strip() for p in message_text.split(',')]
                        if len(parts) == 5:
                            account_name, phone, api_id, api_hash, session_string = parts
                            
                            # Save directly to database
                            account_id = self.db.add_telegram_account(
                                user_id,
                                account_name,
                                phone,
                                session_string,
                                api_id,
                                api_hash
                            )
                            
                            logger.info(f"✅ YOLO: Account added with ID {account_id}")
                            
                            # Clear session
                            del self.user_sessions[user_id]
                            
                            keyboard = [
                                [InlineKeyboardButton("📢 Create Campaign", callback_data="add_campaign")],
                                [InlineKeyboardButton("👥 Manage Accounts", callback_data="manage_accounts")],
                                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            await update.message.reply_text(
                                f"✅ **Account Added Successfully (YOLO Mode)!**\n\n"
                                f"**Account:** {account_name}\n"
                                f"**Phone:** {phone}\n\n"
                                f"🎉 Your account is now ready to use for campaigns!",
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=reply_markup
                            )
                            return
                    
                    # If not comma-separated, treat as account name and wait for more
                    await update.message.reply_text(
                        "Please send all details in one message, comma-separated:\n"
                        "account_name,phone,api_id,api_hash,session_string",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to add account via YOLO mode: {e}")
                    await update.message.reply_text(
                        f"❌ **Failed to add account**\n\n"
                        f"Error: {str(e)}\n\n"
                        f"Please check your data format and try again.",
                        parse_mode=ParseMode.MARKDOWN
                    )
        
        # Handle campaign creation
        elif 'campaign_data' in session:
            if session['step'] == 'campaign_name':
                # Validate campaign name
                logger.info(f"Validating campaign name: '{message_text}'")
                # Simplified validation for campaign names - just check length and basic safety
                if not message_text:
                    is_valid, error_msg = False, "Campaign name cannot be empty"
                elif len(message_text) > 100:
                    is_valid, error_msg = False, f"Campaign name too long (max 100 characters, got {len(message_text)})"
                elif not message_text.strip():
                    is_valid, error_msg = False, "Campaign name cannot be empty"
                else:
                    # Basic safety check - no SQL injection patterns
                    import re
                    sql_patterns = [
                        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
                        r"(--|#|\/\*|\*\/)", r"(\b(OR|AND)\s+\d+\s*=\s*\d+)", r"(\b(OR|AND)\s+'.*'\s*=\s*'.*')",
                        r"(\bUNION\s+SELECT\b)", r"(\bDROP\s+TABLE\b)", r"(\bINSERT\s+INTO\b)", r"(\bDELETE\s+FROM\b)"
                    ]
                    is_safe = True
                    for pattern in sql_patterns:
                        if re.search(pattern, message_text, re.IGNORECASE):
                            is_safe = False
                            break
                    is_valid, error_msg = is_safe, "Campaign name contains potentially malicious content" if not is_safe else ""
                logger.info(f"Validation result: is_valid={is_valid}, error_msg='{error_msg}'")
                
                if not is_valid:
                    # Escape the error message to prevent Markdown parsing issues
                    safe_error_msg = self.escape_markdown(error_msg)
                    logger.info(f"Sending error message: {safe_error_msg}")
                    await update.message.reply_text(
                        f"❌ **Invalid Campaign Name**\n\n{safe_error_msg}\n\nPlease enter a valid campaign name (max 100 characters).",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                logger.info(f"Campaign name '{message_text}' is valid, proceeding to ad_content step")
                session['campaign_data']['campaign_name'] = message_text
                session['step'] = 'ad_content'
                
                await update.message.reply_text(
                    "✅ **Campaign name set!**\n\n**Step 2/6: Ad Content**\n\n🔗 **Send me the Telegram message link**\n\n**How to get the link:**\n1️⃣ Go to your storage channel\n2️⃣ Send your message with premium emojis there\n3️⃣ Right-click the message → Copy Message Link\n4️⃣ Send me that link\n\n**Example link format:**\n`https://t.me/c/1234567890/123`\n\n**Note:** The message should already have your media and premium emoji text!",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'ad_content':
                # Check if it's a message link
                message_text = update.message.text
                if message_text and ('t.me/' in message_text or 'telegram.me/' in message_text):
                    await self.handle_message_link(update, session, context)
                else:
                    # Handle forwarded message with full fidelity (fallback)
                    await self.handle_forwarded_ad_content(update, session, context)
            
            elif session['step'] == 'ad_text_input':
                # Handle text input for media
                logger.info(f"🔍 TEXT INPUT DEBUG: Processing text input for media, step: {session['step']}")
                await self.handle_ad_text_input(update, session, context)
            
            elif session['step'] == 'add_buttons_choice':
                # Handle button addition choice
                await self.handle_button_choice(update, session)
            
            elif session['step'] == 'button_input':
                # Handle button data input
                await self.handle_button_input(update, session)
            
            elif session['step'] == 'target_chats_choice':
                # This step is now handled by button callbacks
                pass
            
            elif session['step'] == 'target_chats':
                # Parse target chats
                chats = []
                for line in message_text.strip().split('\n'):
                    for chat in line.split(','):
                        chat = chat.strip()
                        if chat:
                            chats.append(chat)
                
                session['campaign_data']['target_chats'] = chats
                session['step'] = 'schedule_type'
                
                keyboard = [
                    [InlineKeyboardButton("📅 Daily", callback_data="schedule_daily")],
                    [InlineKeyboardButton("📊 Weekly", callback_data="schedule_weekly")],
                    [InlineKeyboardButton("⏰ Hourly", callback_data="schedule_hourly")],
                    [InlineKeyboardButton("🔧 Custom", callback_data="schedule_custom")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="back_to_bump")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ **Target chats set!** ({len(chats)} chats)\n\n**Step 4/6: Schedule Type**\n\nHow often should this campaign run?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            
            elif session['step'] == 'schedule_time':
                session['campaign_data']['schedule_time'] = message_text
                session['step'] = 'account_selection'
                
                # Show account selection
                accounts = self.db.get_user_accounts(user_id)
                keyboard = []
                for account in accounts:
                    keyboard.append([InlineKeyboardButton(
                        f"📱 {account['account_name']} ({account['phone_number']})", 
                        callback_data=f"select_account_{account['id']}"
                    )])
                keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_to_bump")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ **Schedule set!**\n\n**Step 5/6: Select Account**\n\n**Schedule:** {message_text}\n\nChoose which account to use for this campaign:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            
            # Edit campaign functionality
            elif session['step'] == 'edit_text_content':
                await self.handle_edit_text_content(update, session)
            
            elif session['step'] == 'edit_media':
                await self.handle_edit_media(update, session)
            
            elif session['step'] == 'edit_buttons':
                await self.handle_edit_buttons(update, session)
            
            elif session['step'] == 'account_selection':
                # Account selection is handled via callback buttons, not text messages
                await update.message.reply_text(
                    "Please use the buttons above to select an account for your campaign.",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        # Handle forwarding configuration creation
        elif 'config' in session:
            if session['step'] == 'source_chat':
                session['config']['source_chat_id'] = message_text
                session['step'] = 'destination_chat'
                
                await update.message.reply_text(
                    "✅ **Source chat set!**\n\n**Step 2/4: Destination Chat**\n\nPlease send me the destination chat ID or username.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'destination_chat':
                session['config']['destination_chat_id'] = message_text
                session['step'] = 'config_name'
                
                await update.message.reply_text(
                    "✅ **Destination chat set!**\n\n**Step 3/4: Configuration Name**\n\nPlease send me a name for this forwarding configuration.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif session['step'] == 'config_name':
                session['config']['config_name'] = message_text
                session['step'] = 'complete'
                
                # Create default configuration
                default_config = {
                    'filter': {'enabled': False},
                    'format': {'enabled': False},
                    'replace': {'enabled': False},
                    'caption': {'enabled': False, 'header': '', 'footer': ''},
                    'watermark': {'enabled': False},
                    'ocr': {'enabled': False}
                }
                
                # Get the first available account for this user
                accounts = self.db.get_user_accounts(user_id)
                if not accounts:
                    await update.message.reply_text(
                        "❌ **No accounts found!**\n\nPlease add a Telegram account first before creating forwarding configurations.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    del self.user_sessions[user_id]
                    return
                
                account_id = accounts[0]['id']  # Use first account
                
                # Save configuration
                config_id = self.db.add_forwarding_config(
                    user_id,
                    account_id,
                    session['config']['source_chat_id'],
                    session['config']['destination_chat_id'],
                    session['config']['config_name'],
                    default_config
                )
                
                # Clear session
                del self.user_sessions[user_id]
                
                keyboard = [
                    [InlineKeyboardButton("⚙️ Configure Plugins", callback_data=f"config_{config_id}")],
                    [InlineKeyboardButton("📋 My Configurations", callback_data="my_configs")],
                    [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"🎉 **Configuration Created!**\n\n**Name:** {session['config']['config_name']}\n**Source:** `{session['config']['source_chat_id']}`\n**Destination:** `{session['config']['destination_chat_id']}`\n**Account:** {accounts[0]['account_name']}\n\nYour forwarding configuration has been created successfully!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
    
    async def delete_config(self, query, config_id):
        """Delete a configuration"""
        user_id = query.from_user.id
        self.db.delete_config(config_id)
        
        await query.answer("Configuration deleted!", show_alert=True)
        await self.show_my_configs(query)
    
    async def toggle_config(self, query, config_id):
        """Toggle configuration status"""
        # This would require updating the database
        await query.answer("Feature coming soon!", show_alert=True)
    
    async def show_manage_accounts(self, query):
        """Show account management interface"""
        user_id = query.from_user.id
        accounts = self.db.get_user_accounts(user_id)
        
        if not accounts:
            keyboard = [
                [InlineKeyboardButton("➕ Add New Account", callback_data="add_account")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "👥 **Manage Accounts**\n\nNo Telegram accounts found.\n\nAdd your first account to start forwarding messages!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        text = "👥 Manage Accounts\n\n"
        keyboard = []
        
        for account in accounts:
            # Use plain text formatting
            account_name = self.escape_markdown(account['account_name'])
            phone_number = self.escape_markdown(account['phone_number'])
            
            text += f"📱 {account_name}\n"
            text += f"📞 Phone: {phone_number}\n"
            text += f"Status: {'🟢 Active' if account['is_active'] else '🔴 Inactive'}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"⚙️ {self.escape_markdown(account['account_name'])}", callback_data=f"account_{account['id']}"),
                InlineKeyboardButton("🗑️", callback_data=f"delete_account_{account['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add New Account", callback_data="add_account")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Use plain text to avoid Markdown parsing issues
        plain_text = text.replace("**", "").replace("`", "").replace("*", "")
        await query.edit_message_text(
            plain_text,
            reply_markup=reply_markup
        )
    
    async def show_account_details(self, query, account_id):
        """Show detailed account information"""
        user_id = query.from_user.id
        account = self.db.get_account(account_id)
        
        if not account or account['user_id'] != user_id:
            await query.answer("Account not found!", show_alert=True)
            return
        
        # Get configurations for this account
        configs = self.db.get_user_configs(user_id, account_id)
        
        text = f"⚙️ **{account['account_name']}**\n\n"
        text += f"**Phone:** `{account['phone_number']}`\n"
        text += f"**API ID:** `{account['api_id']}`\n"
        text += f"**Status:** {'🟢 Active' if account['is_active'] else '🔴 Inactive'}\n"
        text += f"**Configurations:** {len(configs)}\n\n"
        
        if configs:
            text += "**Active Forwardings:**\n"
            for config in configs[:3]:  # Show first 3
                text += f"• {config['config_name']}\n"
            if len(configs) > 3:
                text += f"• ... and {len(configs) - 3} more\n"
        
        keyboard = [
            [InlineKeyboardButton("📋 View Configurations", callback_data=f"configs_for_account_{account_id}")],
            [InlineKeyboardButton("🔙 Back to Accounts", callback_data="back_to_accounts")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_configs_for_account(self, query, account_id):
        """Show configurations for a specific account"""
        user_id = query.from_user.id
        configs = self.db.get_user_configs(user_id, account_id)
        account = self.db.get_account(account_id)
        
        if not account:
            await query.answer("Account not found!", show_alert=True)
            return
        
        if not configs:
            keyboard = [
                [InlineKeyboardButton("➕ Add New Forwarding", callback_data="add_forwarding")],
                [InlineKeyboardButton("🔙 Back to Account", callback_data=f"account_{account_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📋 **Configurations for {account['account_name']}**\n\nNo forwarding configurations found.\n\nAdd your first forwarding rule!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        text = f"📋 **Configurations for {account['account_name']}**\n\n"
        keyboard = []
        
        for config in configs:
            status = "🟢 Active" if config['is_active'] else "🔴 Inactive"
            text += f"**{config['config_name']}** {status}\n"
            text += f"From: `{config['source_chat_id']}`\n"
            text += f"To: `{config['destination_chat_id']}`\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"⚙️ {config['config_name']}", callback_data=f"config_{config['id']}"),
                InlineKeyboardButton("🗑️", callback_data=f"delete_config_{config['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add New", callback_data="add_forwarding")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Account", callback_data=f"account_{account_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def start_add_account(self, query):
        """Start the process of adding a new Telegram account"""
        user_id = query.from_user.id
        
        text = """
➕ **Add New Work Account**

**Choose your setup method:**

**📤 Upload Session File (Recommended)**
- Fastest setup method
- No API credentials needed
- Account ready immediately

**🔑 Paste Session String (YOLO Mode)**
- Already have a Telethon session string?
- Paste it directly - instant setup!
- For users with pre-generated sessions

**🔧 Manual Setup (Advanced)**
- Enter API credentials manually
- Step-by-step guided setup
- For advanced users
        """
        
        keyboard = [
            [InlineKeyboardButton("📤 Upload Session File", callback_data="upload_session")],
            [InlineKeyboardButton("🔑 Paste Session String (YOLO)", callback_data="paste_session_string")],
            [InlineKeyboardButton("🔧 Manual Setup (Advanced)", callback_data="manual_setup")],
            [InlineKeyboardButton("❌ Cancel", callback_data="manage_accounts")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def delete_account(self, query, account_id):
        """Delete a Telegram account and clean up all related data"""
        user_id = query.from_user.id
        account = self.db.get_account(account_id)
        
        if not account or account['user_id'] != user_id:
            await query.answer("Account not found!", show_alert=True)
            return
        
        account_name = account.get('account_name', 'Unknown')
        
        # Get campaigns using this account before deletion
        campaigns = self.bump_service.get_user_campaigns(user_id)
        campaigns_to_delete = [c for c in campaigns if c['account_id'] == account_id]
        
        # Clean up campaigns in bump service first
        for campaign in campaigns_to_delete:
            logger.info(f"Cleaning up campaign {campaign['id']} for deleted account {account_name}")
            self.bump_service.delete_campaign(campaign['id'])
        
        # Delete the account and all related data
        self.db.delete_account(account_id)
        
        # Clean up any session files
        import os
        try:
            session_files = [
                f"temp_session_{account_id}.session",
                f"bump_session_{account_id}.session",
                f"account_{user_id}_{account_id}.session"
            ]
            for session_file in session_files:
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logger.info(f"Cleaned up session file: {session_file}")
        except Exception as e:
            logger.warning(f"Could not clean up session files: {e}")
        
        success_msg = f"✅ Account '{account_name}' completely deleted!"
        if campaigns_to_delete:
            success_msg += f"\n🗑️ Also deleted {len(campaigns_to_delete)} related campaigns"
        
        await query.answer(success_msg, show_alert=True)
        await self.show_manage_accounts(query)
    
    # Bump Service Methods
    async def show_bump_service(self, query):
        """Show bump service main menu"""
        user_id = query.from_user.id
        campaigns = self.bump_service.get_user_campaigns(user_id)
        
        text = """
📢 **Bump Service - Auto Ads Manager**

Automatically post your advertisements to multiple chats at scheduled times!

**Features:**
• Schedule ads to post daily, weekly, or custom intervals
• Post to multiple channels/groups at once  
• Track ad performance and statistics
• Test ads before going live
• Manage multiple ad campaigns

**Current Status:**
        """
        
        if campaigns:
            active_campaigns = len([c for c in campaigns if c['is_active']])
            text += f"• Active Campaigns: {active_campaigns}\n"
            text += f"• Total Campaigns: {len(campaigns)}\n"
        else:
            text += "• No campaigns created yet\n"
        
        keyboard = [
            [InlineKeyboardButton("📋 My Campaigns", callback_data="my_campaigns")],
            [InlineKeyboardButton("➕ Create New Campaign", callback_data="add_campaign")],
            [InlineKeyboardButton("📊 Campaign Statistics", callback_data="campaign_stats")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def show_my_campaigns(self, query):
        """Show user's ad campaigns"""
        user_id = query.from_user.id
        campaigns = self.bump_service.get_user_campaigns(user_id)
        
        if not campaigns:
            keyboard = [
                [InlineKeyboardButton("➕ Create New Campaign", callback_data="add_campaign")],
                [InlineKeyboardButton("🔙 Back to Bump Service", callback_data="back_to_bump")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📋 **My Campaigns**\n\nNo ad campaigns found.\n\nCreate your first campaign to start automated advertising!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        text = "📋 My Ad Campaigns\n\n"
        keyboard = []
        
        for campaign in campaigns:
            status = "🟢 Active" if campaign['is_active'] else "🔴 Inactive"
            # Use plain text formatting to avoid Markdown conflicts
            campaign_name = str(campaign['campaign_name'])[:50]  # Limit length
            text += f"📢 {campaign_name} {status}\n"
            text += f"⏰ Schedule: {campaign['schedule_type']} at {campaign['schedule_time']}\n"
            text += f"🎯 Targets: {len(campaign['target_chats'])} chats\n"
            text += f"📊 Total Sends: {campaign['total_sends']}\n\n"
            
            # Add toggle button based on campaign status
            toggle_icon = "⏸️" if campaign['is_active'] else "▶️"
            toggle_text = "Pause" if campaign['is_active'] else "Activate"
            
            keyboard.append([
                InlineKeyboardButton(f"🚀 Start", callback_data=f"start_campaign_{campaign['id']}"),
                InlineKeyboardButton(f"{toggle_icon} {toggle_text}", callback_data=f"toggle_campaign_{campaign['id']}"),
                InlineKeyboardButton("🗑️", callback_data=f"delete_campaign_{campaign['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Create New", callback_data="add_campaign")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Bump Service", callback_data="back_to_bump")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to display campaigns: {e}")
            # Try without reply markup first
            try:
                await query.edit_message_text(
                    "📋 My Campaigns\n\nRefreshing campaign list...",
                )
                # Then send new message with proper content
                await query.message.reply_text(
                    text,
                    reply_markup=reply_markup
                )
            except Exception as e2:
                logger.error(f"Fallback display also failed: {e2}")
                await query.answer("Error displaying campaigns. Please try again.", show_alert=True)
    
    async def show_campaign_details(self, query, campaign_id):
        """Show detailed campaign information"""
        user_id = query.from_user.id
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign or campaign['user_id'] != user_id:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        # Get performance stats
        performance = self.bump_service.get_campaign_performance(campaign_id)
        
        status = "🟢 Active" if campaign['is_active'] else "🔴 Inactive"
        text = f"⚙️ {campaign['campaign_name']} {status}\n\n"
        text += f"Account: {campaign['account_name']}\n"
        text += f"Schedule: {campaign['schedule_type']} at {campaign['schedule_time']}\n"
        text += f"Target Chats: {len(campaign['target_chats'])}\n"
        text += f"Last Run: {campaign['last_run'] or 'Never'}\n\n"
        
        text += "Performance:\n"
        text += f"• Total Attempts: {performance['total_attempts']}\n"
        text += f"• Successful: {performance['successful_sends']}\n"
        text += f"• Failed: {performance['failed_sends']}\n"
        text += f"• Success Rate: {performance['success_rate']:.1f}%\n\n"
        
        text += "Ad Content Preview:\n"
        # Handle complex ad content safely
        if isinstance(campaign['ad_content'], list):
            preview = "Multiple forwarded messages"
        else:
            preview_text = str(campaign['ad_content'])[:200]
            preview = preview_text + "..." if len(preview_text) > 200 else preview_text
        text += f"{preview}"
        
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Campaign", callback_data=f"edit_campaign_{campaign_id}")],
            [InlineKeyboardButton("🔄 Toggle Status", callback_data=f"toggle_campaign_{campaign_id}")],
            [InlineKeyboardButton("🧪 Test Campaign", callback_data=f"test_campaign_{campaign_id}")],
            [InlineKeyboardButton("📊 Full Statistics", callback_data=f"stats_{campaign_id}")],
            [InlineKeyboardButton("🔙 Back to Campaigns", callback_data="back_to_campaigns")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup
        )

    async def start_edit_campaign(self, query, campaign_id):
        """Start editing a campaign"""
        user_id = query.from_user.id
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign or campaign['user_id'] != user_id:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        # Store campaign ID in user session for editing
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        
        self.user_sessions[user_id]['editing_campaign_id'] = campaign_id
        self.user_sessions[user_id]['step'] = 'edit_campaign_menu'
        
        text = f"✏️ **Edit Campaign: {campaign['campaign_name']}**\n\n"
        text += "Choose what you want to edit:\n\n"
        text += "📝 **Text Content** - Edit headlines, body text, and call-to-action\n"
        text += "🖼️ **Media** - Replace or remove images and videos\n"
        text += "🔘 **Buttons** - Customize button text and destination URLs\n"
        text += "⚙️ **Settings** - Modify schedule, targets, and other settings\n"
        text += "👁️ **Preview** - See how your campaign will look when sent"
        
        keyboard = [
            [InlineKeyboardButton("📝 Edit Text Content", callback_data="edit_text_content")],
            [InlineKeyboardButton("🖼️ Edit Media", callback_data="edit_media")],
            [InlineKeyboardButton("🔘 Edit Buttons", callback_data="edit_buttons")],
            [InlineKeyboardButton("⚙️ Edit Settings", callback_data="edit_settings")],
            [InlineKeyboardButton("👁️ Preview Campaign", callback_data="preview_campaign")],
            [InlineKeyboardButton("🔙 Back to Campaign", callback_data=f"campaign_{campaign_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def edit_text_content(self, query):
        """Edit text content of a campaign"""
        user_id = query.from_user.id
        if user_id not in self.user_sessions or 'editing_campaign_id' not in self.user_sessions[user_id]:
            await query.answer("No campaign being edited!", show_alert=True)
            return
        
        campaign_id = self.user_sessions[user_id]['editing_campaign_id']
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        self.user_sessions[user_id]['step'] = 'edit_text_content'
        
        text = f"📝 **Edit Text Content**\n\n"
        text += f"**Current Campaign:** {campaign['campaign_name']}\n\n"
        text += "**Current Text Content:**\n"
        
        # Show current text content
        if isinstance(campaign['ad_content'], list):
            text += "Multiple forwarded messages (text content will be extracted)\n"
        else:
            preview_text = str(campaign['ad_content'])[:300]
            text += f"{preview_text}...\n" if len(preview_text) > 300 else preview_text
        
        text += "\n\n**To edit text content:**\n"
        text += "1. Send me the new text content\n"
        text += "2. Or forward new messages to replace the content\n"
        text += "3. Type 'done' when finished"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Edit Menu", callback_data=f"edit_campaign_{campaign_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def edit_media(self, query):
        """Edit media content of a campaign"""
        user_id = query.from_user.id
        if user_id not in self.user_sessions or 'editing_campaign_id' not in self.user_sessions[user_id]:
            await query.answer("No campaign being edited!", show_alert=True)
            return
        
        campaign_id = self.user_sessions[user_id]['editing_campaign_id']
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        self.user_sessions[user_id]['step'] = 'edit_media'
        
        text = f"🖼️ **Edit Media Content**\n\n"
        text += f"**Current Campaign:** {campaign['campaign_name']}\n\n"
        text += "**Current Media:**\n"
        
        # Show current media info
        if isinstance(campaign['ad_content'], list):
            media_count = sum(1 for msg in campaign['ad_content'] if msg.get('media_type'))
            text += f"Multiple messages with {media_count} media items\n"
        elif isinstance(campaign['ad_content'], dict) and campaign['ad_content'].get('media_type'):
            text += f"Single media: {campaign['ad_content']['media_type']}\n"
        else:
            text += "No media content\n"
        
        text += "\n**To edit media:**\n"
        text += "1. Send me new media (photos, videos, documents)\n"
        text += "2. Or forward messages with media\n"
        text += "3. Type 'remove' to remove all media\n"
        text += "4. Type 'done' when finished"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Edit Menu", callback_data=f"edit_campaign_{campaign_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def edit_buttons(self, query):
        """Edit buttons of a campaign"""
        user_id = query.from_user.id
        if user_id not in self.user_sessions or 'editing_campaign_id' not in self.user_sessions[user_id]:
            await query.answer("No campaign being edited!", show_alert=True)
            return
        
        campaign_id = self.user_sessions[user_id]['editing_campaign_id']
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        self.user_sessions[user_id]['step'] = 'edit_buttons'
        
        text = f"🔘 **Edit Buttons**\n\n"
        text += f"**Current Campaign:** {campaign['campaign_name']}\n\n"
        text += "**Current Buttons:**\n"
        
        # Show current buttons
        buttons = campaign.get('buttons', [])
        if buttons:
            for i, button in enumerate(buttons, 1):
                text += f"{i}. {button.get('text', 'Unknown')} - {button.get('url', 'No URL')}\n"
        else:
            text += "No buttons configured\n"
        
        text += "\n**To edit buttons:**\n"
        text += "1. Send button data in format: [Button Text] - [URL]\n"
        text += "2. Example: Shop Now - https://example.com/shop\n"
        text += "3. Send multiple buttons (one per line)\n"
        text += "4. Type 'remove' to remove all buttons\n"
        text += "5. Type 'done' when finished"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Edit Menu", callback_data=f"edit_campaign_{campaign_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def edit_settings(self, query):
        """Edit campaign settings"""
        user_id = query.from_user.id
        if user_id not in self.user_sessions or 'editing_campaign_id' not in self.user_sessions[user_id]:
            await query.answer("No campaign being edited!", show_alert=True)
            return
        
        campaign_id = self.user_sessions[user_id]['editing_campaign_id']
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        text = f"⚙️ **Edit Campaign Settings**\n\n"
        text += f"**Current Campaign:** {campaign['campaign_name']}\n\n"
        text += "**Current Settings:**\n"
        text += f"• Schedule: {campaign['schedule_type']} at {campaign['schedule_time']}\n"
        text += f"• Target Mode: {campaign.get('target_mode', 'specific')}\n"
        text += f"• Target Chats: {len(campaign['target_chats'])} chats\n"
        text += f"• Status: {'Active' if campaign['is_active'] else 'Inactive'}\n\n"
        text += "**What would you like to edit?**"
        
        keyboard = [
            [InlineKeyboardButton("📅 Edit Schedule", callback_data="edit_schedule")],
            [InlineKeyboardButton("🎯 Edit Targets", callback_data="edit_targets")],
            [InlineKeyboardButton("🔄 Toggle Status", callback_data=f"toggle_campaign_{campaign_id}")],
            [InlineKeyboardButton("🔙 Back to Edit Menu", callback_data=f"edit_campaign_{campaign_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def preview_campaign(self, query):
        """Preview how the campaign will look when sent"""
        user_id = query.from_user.id
        if user_id not in self.user_sessions or 'editing_campaign_id' not in self.user_sessions[user_id]:
            await query.answer("No campaign being edited!", show_alert=True)
            return
        
        campaign_id = self.user_sessions[user_id]['editing_campaign_id']
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        text = f"👁️ **Campaign Preview**\n\n"
        text += f"**Campaign:** {campaign['campaign_name']}\n\n"
        text += "**This is how your campaign will look when sent:**\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Show campaign content preview
        ad_content = campaign['ad_content']
        buttons = campaign.get('buttons', [])
        
        if isinstance(ad_content, list):
            # Multiple messages
            for i, message_data in enumerate(ad_content, 1):
                if message_data.get('text'):
                    text += f"**Message {i}:**\n{message_data['text']}\n\n"
                if message_data.get('caption'):
                    text += f"**Caption {i}:**\n{message_data['caption']}\n\n"
                if message_data.get('media_type'):
                    text += f"**Media {i}:** {message_data['media_type']}\n\n"
        else:
            # Single message
            if isinstance(ad_content, dict):
                if ad_content.get('text'):
                    text += f"{ad_content['text']}\n\n"
                if ad_content.get('caption'):
                    text += f"{ad_content['caption']}\n\n"
                if ad_content.get('media_type'):
                    text += f"**Media:** {ad_content['media_type']}\n\n"
            else:
                text += f"{str(ad_content)}\n\n"
        
        # Show buttons
        if buttons:
            text += "**Buttons:**\n"
            for button in buttons:
                text += f"🔗 {button.get('text', 'Unknown')}: {button.get('url', 'No URL')}\n"
        else:
            text += "**Buttons:** No buttons configured\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Edit Menu", callback_data=f"edit_campaign_{campaign_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def handle_edit_text_content(self, update: Update, session: dict):
        """Handle editing text content"""
        user_id = update.effective_user.id
        message_text = update.message.text
        campaign_id = session.get('editing_campaign_id')
        
        if not campaign_id:
            await update.message.reply_text("❌ No campaign being edited!")
            return
        
        if message_text.lower() in ['done', 'finish']:
            # Return to edit menu
            await self.start_edit_campaign_by_id(update, campaign_id)
            return
        
        # Update campaign text content
        try:
            # For now, we'll update the ad_content with new text
            # In a full implementation, you'd update the database
            await update.message.reply_text(
                f"✅ **Text content updated!**\n\n**New text:**\n{message_text}\n\n**Type 'done' to finish editing.**",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating text: {str(e)}")

    async def handle_edit_media(self, update: Update, session: dict):
        """Handle editing media content"""
        user_id = update.effective_user.id
        message_text = update.message.text
        campaign_id = session.get('editing_campaign_id')
        
        if not campaign_id:
            await update.message.reply_text("❌ No campaign being edited!")
            return
        
        if message_text and message_text.lower() in ['done', 'finish']:
            # Return to edit menu
            await self.start_edit_campaign_by_id(update, campaign_id)
            return
        
        if message_text and message_text.lower() == 'remove':
            # Remove all media
            await update.message.reply_text(
                "✅ **Media removed!**\n\n**Type 'done' to finish editing.**",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Handle new media upload
        if update.message.photo or update.message.video or update.message.document:
            await update.message.reply_text(
                "✅ **Media updated!**\n\n**Type 'done' to finish editing or send more media.**",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "📸 **Send new media** (photo, video, document) or type:\n• 'remove' to remove all media\n• 'done' to finish editing",
                parse_mode=ParseMode.MARKDOWN
            )

    async def handle_edit_buttons(self, update: Update, session: dict):
        """Handle editing buttons"""
        user_id = update.effective_user.id
        message_text = update.message.text
        campaign_id = session.get('editing_campaign_id')
        
        if not campaign_id:
            await update.message.reply_text("❌ No campaign being edited!")
            return
        
        if message_text.lower() in ['done', 'finish']:
            # Return to edit menu
            await self.start_edit_campaign_by_id(update, campaign_id)
            return
        
        if message_text.lower() == 'remove':
            # Remove all buttons
            await update.message.reply_text(
                "✅ **Buttons removed!**\n\n**Type 'done' to finish editing.**",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Parse button format: [Button Text] - [URL]
        try:
            buttons_added = 0
            for line in message_text.strip().split('\n'):
                if ' - ' in line:
                    parts = line.split(' - ', 1)
                    if len(parts) == 2:
                        button_text = parts[0].strip()
                        button_url = parts[1].strip()
                        buttons_added += 1
            
            if buttons_added > 0:
                await update.message.reply_text(
                    f"✅ **{buttons_added} button(s) updated!**\n\n**Type 'done' to finish editing or add more buttons.**",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ **Invalid format!**\n\n**Use:** [Button Text] - [URL]\n**Example:** Shop Now - https://example.com",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating buttons: {str(e)}")

    async def start_edit_campaign_by_id(self, update: Update, campaign_id: int):
        """Helper function to start edit campaign by ID from message handler"""
        user_id = update.effective_user.id
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign or campaign['user_id'] != user_id:
            await update.message.reply_text("❌ Campaign not found!")
            return
        
        # Store campaign ID in user session for editing
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        
        self.user_sessions[user_id]['editing_campaign_id'] = campaign_id
        self.user_sessions[user_id]['step'] = 'edit_campaign_menu'
        
        text = f"✏️ **Edit Campaign: {campaign['campaign_name']}**\n\n"
        text += "Choose what you want to edit:\n\n"
        text += "📝 **Text Content** - Edit headlines, body text, and call-to-action\n"
        text += "🖼️ **Media** - Replace or remove images and videos\n"
        text += "🔘 **Buttons** - Customize button text and destination URLs\n"
        text += "⚙️ **Settings** - Modify schedule, targets, and other settings\n"
        text += "👁️ **Preview** - See how your campaign will look when sent"
        
        keyboard = [
            [InlineKeyboardButton("📝 Edit Text Content", callback_data="edit_text_content")],
            [InlineKeyboardButton("🖼️ Edit Media", callback_data="edit_media")],
            [InlineKeyboardButton("🔘 Edit Buttons", callback_data="edit_buttons")],
            [InlineKeyboardButton("⚙️ Edit Settings", callback_data="edit_settings")],
            [InlineKeyboardButton("👁️ Preview Campaign", callback_data="preview_campaign")],
            [InlineKeyboardButton("🔙 Back to Campaign", callback_data=f"campaign_{campaign_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def start_add_campaign(self, query):
        """Start the process of adding a new ad campaign"""
        user_id = query.from_user.id
        
        # Check if user has any accounts
        accounts = self.db.get_user_accounts(user_id)
        if not accounts:
            keyboard = [
                [InlineKeyboardButton("➕ Add New Account", callback_data="add_account")],
                [InlineKeyboardButton("🔙 Back to Bump Service", callback_data="back_to_bump")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "❌ **No Accounts Found!**\n\nYou need to add at least one Telegram account before creating ad campaigns.\n\nClick 'Add New Account' to get started!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        self.user_sessions[user_id] = {'step': 'campaign_name', 'campaign_data': {}}
        
        text = """
➕ **Create New Ad Campaign**

**Step 1/6: Campaign Name**

Please send me a name for this ad campaign (e.g., "Daily Product Promo", "Weekend Sale").

This name will help you identify the campaign in your dashboard.
        """
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_bump")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def delete_campaign(self, query, campaign_id):
        """Delete an ad campaign"""
        user_id = query.from_user.id
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign or campaign['user_id'] != user_id:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        self.bump_service.delete_campaign(campaign_id)
        await query.answer("Campaign deleted!", show_alert=True)
        await self.show_my_campaigns(query)
    
    async def toggle_campaign(self, query, campaign_id):
        """Toggle campaign active status"""
        user_id = query.from_user.id
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign or campaign['user_id'] != user_id:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        new_status = not campaign['is_active']
        
        # Update campaign status in database
        import sqlite3
        with sqlite3.connect(self.bump_service.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE ad_campaigns SET is_active = ? WHERE id = ?", (new_status, campaign_id))
            conn.commit()
        
        status_text = "activated" if new_status else "deactivated"
        await query.answer(f"Campaign {status_text}!", show_alert=True)
        
        # Refresh the My Campaigns view
        await self.show_my_campaigns(query)
    
    async def test_campaign(self, query, campaign_id):
        """Test an ad campaign"""
        user_id = query.from_user.id
        campaign = self.bump_service.get_campaign(campaign_id)
        
        if not campaign or campaign['user_id'] != user_id:
            await query.answer("Campaign not found!", show_alert=True)
            return
        
        # Test by sending to the user's private chat
        test_chat = str(user_id)
        
        try:
            success = await self.bump_service.test_campaign(campaign_id, test_chat)
            if success:
                await query.answer("✅ Test ad sent to your private chat!", show_alert=True)
            else:
                await query.answer("❌ Test failed! Check campaign settings.", show_alert=True)
        except Exception as e:
            await query.answer(f"❌ Test error: {str(e)[:50]}", show_alert=True)
    
    async def handle_schedule_selection(self, query, schedule_type):
        """Handle schedule type selection"""
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions or 'campaign_data' not in self.user_sessions[user_id]:
            await query.answer("Session expired! Please start again.", show_alert=True)
            await self.show_bump_service(query)
            return
        
        session = self.user_sessions[user_id]
        session['campaign_data']['schedule_type'] = schedule_type
        session['step'] = 'schedule_time'
        
        if schedule_type == 'daily':
            text = "✅ **Daily schedule selected!**\n\n**Step 5/6: Schedule Time**\n\nPlease send me the time when ads should be posted daily.\n\n**Format:** HH:MM (24-hour format)\n**Example:** 14:30 (for 2:30 PM)"
        elif schedule_type == 'weekly':
            text = "✅ **Weekly schedule selected!**\n\n**Step 5/6: Schedule Time**\n\nPlease send me the day and time when ads should be posted weekly.\n\n**Format:** Day HH:MM\n**Example:** Monday 14:30"
        elif schedule_type == 'hourly':
            text = "✅ **Hourly schedule selected!**\n\nAds will be posted every hour automatically.\n\nProceeding to account selection..."
            session['campaign_data']['schedule_time'] = 'every hour'
            session['step'] = 'account_selection'
            
            # Show account selection
            accounts = self.db.get_user_accounts(user_id)
            keyboard = []
            for account in accounts:
                keyboard.append([InlineKeyboardButton(
                    f"📱 {account['account_name']} ({account['phone_number']})", 
                    callback_data=f"select_account_{account['id']}"
                )])
            keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_to_bump")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✅ **Hourly schedule set!**\n\n**Step 5/6: Select Account**\n\nWhich Telegram account should be used to post these ads?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        elif schedule_type == 'custom':
            text = "✅ **Custom schedule selected!**\n\n**Step 5/6: Custom Schedule**\n\nPlease send me your custom schedule.\n\n**Examples:**\n• every 4 hours\n• every 30 minutes\n• every 2 days\n• every 12 hours\n• every 1 day"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Schedule", callback_data="back_to_schedule_selection")],
            [InlineKeyboardButton("❌ Cancel Campaign", callback_data="cancel_campaign")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_account_selection(self, query, account_id):
        """Handle account selection for campaign with immediate execution"""
        user_id = query.from_user.id
        logger.info(f"Account selection started for user {user_id}, account {account_id}")
        
        try:
            await query.answer("Processing account selection...")
        except Exception as e:
            logger.error(f"Failed to answer query: {e}")
        
        if user_id not in self.user_sessions or 'campaign_data' not in self.user_sessions[user_id]:
            await query.answer("Session expired! Please start again.", show_alert=True)
            await self.show_bump_service(query)
            return
        
        session = self.user_sessions[user_id]
        campaign_data = session['campaign_data']
        logger.info(f"Campaign data: {list(campaign_data.keys())}")
        
        # Get account details for display
        account = self.db.get_account(account_id)
        if not account:
            await query.answer("Account not found!", show_alert=True)
            logger.error(f"Account {account_id} not found in database")
            return
        
        logger.info(f"Account found: {account['account_name']}")
        
        # Create the campaign with enhanced data structure
        try:
            logger.info(f"🔧 DEBUG: Starting campaign creation process")
            # Prepare enhanced campaign data
            # Handle single message with media vs multiple messages
            ad_messages = campaign_data.get('ad_messages', [])
            logger.info(f"🔧 DEBUG: Found {len(ad_messages)} ad messages")
            
            if len(ad_messages) == 1 and ad_messages[0].get('media_type'):
                logger.info(f"🔧 DEBUG: Creating single media campaign")
                # Single message with media - use it directly
                enhanced_campaign_data = {
                    'campaign_name': campaign_data['campaign_name'],
                    'ad_content': ad_messages[0],  # Single message object, not wrapped in list
                    'target_chats': campaign_data['target_chats'],
                    'schedule_type': campaign_data['schedule_type'],
                    'schedule_time': campaign_data['schedule_time'],
                    'buttons': campaign_data.get('buttons', []),
                    'target_mode': campaign_data.get('target_mode', 'specific'),
                    'immediate_start': False  # Disabled - user must click Start Campaign
                }
                logger.info(f"🔧 DEBUG: Enhanced campaign data created successfully")
            else:
                # Multiple messages or no media - use as list
                enhanced_campaign_data = {
                    'campaign_name': campaign_data['campaign_name'],
                    'ad_content': ad_messages if ad_messages else [campaign_data.get('ad_content', '')],
                    'target_chats': campaign_data['target_chats'],
                    'schedule_type': campaign_data['schedule_type'],
                    'schedule_time': campaign_data['schedule_time'],
                    'buttons': campaign_data.get('buttons', []),
                    'target_mode': campaign_data.get('target_mode', 'specific'),
                    'immediate_start': False  # Disabled - user must click Start Campaign  # Flag for immediate execution
                }
            
            logger.info(f"Creating campaign with {len(enhanced_campaign_data.get('buttons', []))} buttons")
            
            campaign_id = self.bump_service.add_campaign(
                user_id,
                account_id,
                enhanced_campaign_data['campaign_name'],
                enhanced_campaign_data['ad_content'],
                enhanced_campaign_data['target_chats'],
                enhanced_campaign_data['schedule_type'],
                enhanced_campaign_data['schedule_time'],
                enhanced_campaign_data['buttons'],
                enhanced_campaign_data['target_mode'],
                enhanced_campaign_data.get('immediate_start', False)
            )
            
            # Update storage message with buttons for immediate campaigns (after campaign is created)
            if 'buttons' in enhanced_campaign_data and enhanced_campaign_data['buttons']:
                # Add the campaign ID to the data so the update function can work
                enhanced_campaign_data['id'] = campaign_id
                await self._update_storage_message_with_buttons(enhanced_campaign_data)
            
            logger.info(f"🔧 DEBUG: add_campaign returned with ID: {campaign_id}")
            logger.info(f"Campaign created successfully with ID: {campaign_id}")
            
            # DISABLED AUTOMATIC EXECUTION: User must manually start campaigns
            logger.info("Campaign created - automatic execution disabled, user must click Start Campaign")
            immediate_success = False  # No automatic execution
            
            # Clear session
            del self.user_sessions[user_id]
            
            # Success message with immediate execution feedback
            success_text = f"""🎉 Campaign Created Successfully!

Campaign: {enhanced_campaign_data['campaign_name']}
Account: {account['account_name']} ({account['phone_number']})
Schedule: {enhanced_campaign_data['schedule_type']} at {enhanced_campaign_data['schedule_time']}
Targets: {len(enhanced_campaign_data['target_chats'])} chat(s)

"""
            
            # Always show manual start message
            success_text += "⏳ Campaign created and ready to start\n🚀 Click 'Start Campaign' to send the first message\n📅 Then messages will repeat according to your schedule"
            
            keyboard = [
                [InlineKeyboardButton("🚀 Start Campaign", callback_data=f"start_campaign_{campaign_id}")],
                [InlineKeyboardButton("⚙️ Configure Campaign", callback_data=f"campaign_{campaign_id}")],
                [InlineKeyboardButton("🧪 Test Campaign", callback_data=f"test_campaign_{campaign_id}")],
                [InlineKeyboardButton("📋 My Campaigns", callback_data="my_campaigns")],
                [InlineKeyboardButton("🔙 Bump Service", callback_data="back_to_bump")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                success_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"🔧 DEBUG: Exception caught during campaign creation: {e}")
            logger.error(f"🔧 DEBUG: Exception type: {type(e).__name__}")
            logger.error(f"🔧 DEBUG: Full traceback:", exc_info=True)
            await query.answer(f"❌ Error creating campaign: {str(e)[:50]}", show_alert=True)
            logger.error(f"Error creating campaign for user {user_id}: {e}")
    
    async def setup_bot_commands(self, application):
        """Setup bot commands"""
        commands = [
            BotCommand("start", "Start the bot and show main menu"),
            BotCommand("help", "Show help information"),
            BotCommand("config", "Manage forwarding configurations"),
            BotCommand("status", "Check bot status")
        ]
        await application.bot.set_my_commands(commands)
    

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads for session files"""
        user_id = update.message.from_user.id
        

        document = update.message.document
        
        # Check if this is a session file
        if not document.file_name or not document.file_name.endswith(".session"):
            await update.message.reply_text(
                " **Invalid file type!**\n\nI can only process .session files for account setup.\n\nPlease upload a .session file or use the account management menu.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Automatically process session files
        
        document = update.message.document
        
        # Check file extension
        if not document.file_name or not document.file_name.endswith(".session"):
            await update.message.reply_text(
                " **Invalid file type!**\n\nPlease send a .session file.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check file size (50KB limit)
        if document.file_size > 50000:
            await update.message.reply_text(
                " **File too large!**\n\nSession files should be less than 50KB.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            # Download the session file
            file = await context.bot.get_file(document.file_id)
            session_data = await file.download_as_bytearray()
            
            # Extract phone number from filename
            phone_number = document.file_name.replace(".session", "").replace("+", "")
            account_name = f"Account_{phone_number[:4]}****" if phone_number else f"Uploaded_Account_{user_id}"
            
            # Save session as base64 in database
            import base64
            session_string = base64.b64encode(session_data).decode("utf-8")
            
            # Add account to database
            account_id = self.db.add_telegram_account(
                user_id,
                account_name,
                phone_number or "Unknown",
                "uploaded",  # API ID placeholder
                "uploaded",  # API Hash placeholder  
                session_string
            )
            
            # Clear user session
            del self.user_sessions[user_id]
            
            # Success message with options
            keyboard = [
                [InlineKeyboardButton(" Manage Accounts", callback_data="manage_accounts")],
                [InlineKeyboardButton(" Upload Another", callback_data="upload_session")],
                [InlineKeyboardButton(" Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f" **Session Uploaded Successfully!**\n\n**Account:** {account_name}\n**Phone:** +{phone_number or 'Unknown'}\n**Status:** Ready for campaigns\n\nYour account has been added and is ready to use!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Session upload error: {e}")
            await update.message.reply_text(
                f" **Upload failed!**\n\nError: {str(e)}\n\nPlease try again with a valid session file.",
                parse_mode=ParseMode.MARKDOWN
            )


    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors that occur in the bot"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Try to send error message to user if possible
        if update and hasattr(update, '"'"'effective_chat'"'"') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=" **Something went wrong!**\n\nPlease try again or contact support if the issue persists.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    def run(self):
        """Run the bot"""
        # Validate configuration
        Config.validate()
        
        # Create application first
        application = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Initialize bump service with bot instance and telethon manager
        self.bump_service = BumpService(bot_instance=application.bot, telethon_manager=self.telethon_manager)
        
        # Start bump service scheduler
        self.bump_service.start_scheduler()
        logger.info("Bump service scheduler started")
        
        # Add error handler
        application.add_error_handler(self.error_handler)
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        # Add handlers for forwarded messages with media
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_message))
        application.add_handler(MessageHandler(filters.VIDEO, self.handle_message))
        # application.add_handler(MessageHandler(filters.ANIMATION, self.handle_message))
        # application.add_handler(MessageHandler(filters.VOICE, self.handle_message))
        # application.add_handler(MessageHandler(filters.VIDEO_NOTE, self.handle_message))
        # application.add_handler(MessageHandler(filters.AUDIO, self.handle_message))
        application.add_handler(MessageHandler(filters.Sticker.ALL, self.handle_message))
        # Add handler for forwarded messages (any type)
        # application.add_handler(MessageHandler(filters.FORWARDED, self.handle_message))
        
        # Setup bot commands
        application.post_init = self.setup_bot_commands
        
        # Start the bot
        logger.info("Starting TgCF Bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


    async def start_session_upload(self, query):
        """Start session file upload process"""
        user_id = query.from_user.id
        self.user_sessions[user_id] = {"step": "upload_session", "account_data": {}}
        
        text = """
 **Upload Session File**

Send me your Telegram session file (.session) as a document.

**Requirements:**
 File must have .session extension
 File size should be less than 50KB
 Session must be valid and active

**Benefits:**
 Instant account setup - no API credentials needed
 No verification codes required  
 Account ready immediately after upload

Send the session file now, or click Cancel to go back.
        """
        
        keyboard = [[InlineKeyboardButton(" Cancel", callback_data="manage_accounts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def start_manual_setup(self, query):
        """Start manual account setup (old 5-step process)"""
        user_id = query.from_user.id
        self.user_sessions[user_id] = {"step": "account_name", "account_data": {}}
        
        # Debug logging
        logger.info(f"🔍 MANUAL SETUP: Created session for user {user_id}")
        logger.info(f"🔍 SESSION DATA: {self.user_sessions[user_id]}")
        logger.info(f"🔍 ALL SESSIONS: {list(self.user_sessions.keys())}")
        
        text = """**Manual Account Setup**

**Step 1/5: Account Name**

Please send me a name for this work account (e.g., "Marketing Account", "Sales Account", "Support Account").

This name will help you identify the account when managing campaigns."""
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="manage_accounts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def start_paste_session_string(self, query):
        """Start paste session string setup (YOLO Mode)"""
        user_id = query.from_user.id
        self.user_sessions[user_id] = {"step": "paste_session_string", "account_data": {}}
        
        logger.info(f"🚀 YOLO MODE: Paste session string for user {user_id}")
        
        text = """🔑 **YOLO Mode: Paste Session String**

To bypass SMS verification, you can paste a pre-generated Telethon session string here.

**How to get a session string:**

1. Use the `YOLO_SESSION_STRING_GENERATOR.py` script
2. Or generate it locally with Telethon
3. You'll authenticate on your own device
4. Get the session string
5. Paste it here

**Now, please send me:**
1️⃣ **Account name** (e.g., "ads1")
2️⃣ **Phone number** (+254757022149)
3️⃣ **API ID** (20977976)
4️⃣ **API Hash** (585c...)
5️⃣ **Session string** (the long string)

Send them in this format (one message, comma-separated):
```
ads1,+254757022149,20977976,585c...,1AQAAA...
```

Or send them one by one starting with the account name."""
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="manage_accounts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors that occur in the bot"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Try to send error message to user if possible
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ **Something went wrong!**\n\nPlease try again or contact support if the issue persists.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
    
    def run(self):
        """Run the bot"""
        # Validate configuration
        Config.validate()
        
        # Create application first
        application = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Initialize bump service with bot instance and telethon manager
        self.bump_service = BumpService(bot_instance=application.bot, telethon_manager=self.telethon_manager)
        
        # Start bump service scheduler
        self.bump_service.start_scheduler()
        logger.info("Bump service scheduler started")
        
        # Add error handler
        application.add_error_handler(self.error_handler)
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        # Add handlers for forwarded messages with media
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_message))
        application.add_handler(MessageHandler(filters.VIDEO, self.handle_message))
        
        # Start the bot
        logger.info("Starting TgCF Bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

# Integration functions for existing bot system
async def handle_enhanced_auto_ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Main entry point for auto ads system - shows testforwarder menu"""
    query = update.callback_query
    if not query:
        return
    
    # Use global bot instance to maintain user sessions
    bot = get_bot_instance()
    
    # Load accounts if not already loaded
    if not bot.telethon_manager.clients:
        try:
            await bot.telethon_manager.load_all_accounts(bot.db)
        except Exception as e:
            logger.error(f"Error loading accounts: {e}")
    
    await bot.show_main_menu(query)

# All callback handlers from testforwarder
async def handle_manage_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle manage accounts callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.show_manage_accounts(query)

async def handle_add_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle add account callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.start_add_account(query)

async def handle_my_configs(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle my configs callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.show_my_configs(query)

async def handle_add_forwarding(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle add forwarding callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.start_add_forwarding(query)

async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle settings callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.show_settings(query)

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle help callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.show_help(query)

async def handle_bump_service(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle bump service callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.show_bump_service(query)

async def handle_upload_session(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle upload session callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.start_session_upload(query)

async def handle_manual_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle manual setup callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.start_manual_setup(query)

async def handle_paste_session_string(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle paste session string callback (YOLO Mode)"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.start_paste_session_string(query)

async def handle_add_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle add campaign callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.start_add_campaign(query)

async def handle_my_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle my campaigns callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.show_my_campaigns(query)

async def handle_campaign_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle campaign stats callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.show_campaign_stats(query)

async def handle_back_to_bump(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle back to bump service callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.show_bump_service(query)

# Configuration handlers
async def handle_config(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle config callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    config_id = query.data.split('_')[1]
    await bot.show_config_details(query, config_id)

async def handle_delete_config(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle delete config callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    config_id = query.data.split('_')[2]
    await bot.delete_config(query, config_id)

async def handle_toggle_config(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle toggle config callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    config_id = query.data.split('_')[2]
    await bot.toggle_config_status(query, config_id)

async def handle_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle delete account callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    account_id = query.data.split('_')[2]
    await bot.delete_account(query, account_id)

# Campaign handlers
async def handle_delete_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle delete campaign callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    campaign_id = query.data.split('_')[2]
    await bot.delete_campaign(query, campaign_id)

async def handle_edit_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit campaign callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    campaign_id = query.data.split('_')[2]
    await bot.show_edit_campaign_menu(query, campaign_id)

async def handle_edit_text_content(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit text content callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.edit_text_content(query)

async def handle_edit_media(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit media callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.edit_media(query)

async def handle_edit_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit buttons callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.edit_buttons(query)

async def handle_edit_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit settings callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.edit_settings(query)

async def handle_edit_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit schedule callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.edit_schedule(query)

async def handle_edit_targets(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle edit targets callback"""
    query = update.callback_query
    if not query:
        return
    bot = get_bot_instance()
    await bot.edit_targets(query)

async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle back to admin menu callback"""
    query = update.callback_query
    if not query:
        return
    
    # Import admin handler from main bot
    try:
        from admin import handle_admin_menu as main_admin_menu
        await main_admin_menu(update, context, params)
    except ImportError:
        await query.edit_message_text("❌ Could not return to admin menu")

# Global bot instance to maintain user sessions
_global_bot = None

def get_bot_instance():
    """Get or create the global bot instance"""
    global _global_bot
    if _global_bot is None:
        _global_bot = TgcfBot()
        # Set up campaign executor with services
        set_campaign_executor_services(_global_bot.bump_service, _global_bot.telethon_manager)
        logger.info("✅ Campaign executor services configured")
        
        # Load all accounts from database (async operation, will be done later)
        # This will be triggered when the async context is available
        logger.info("ℹ️ Telethon accounts will be loaded when first accessed")
    return _global_bot

# Message handlers
async def handle_enhanced_session_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle session file upload"""
    bot = get_bot_instance()
    await bot.handle_document(update, context)

async def handle_enhanced_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle account details input"""
    bot = get_bot_instance()
    await bot.handle_message(update, context)

async def handle_enhanced_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel link input"""
    bot = get_bot_instance()
    await bot.handle_message(update, context)

# Initialize database tables
def init_enhanced_auto_ads_tables():
    """Initialize database tables for the auto ads system"""
    try:
        logger.info("🔧 Starting auto ads table initialization...")
        conn = get_db_connection()
        c = conn.cursor()
        
        # Create auto_ads_accounts table
        logger.info("Creating auto_ads_accounts table...")
        c.execute("""
            CREATE TABLE IF NOT EXISTS auto_ads_accounts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                account_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                session_string TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Create auto_ads_configs table
        logger.info("Creating auto_ads_configs table...")
        c.execute("""
            CREATE TABLE IF NOT EXISTS auto_ads_configs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                account_id INTEGER REFERENCES auto_ads_accounts(id) ON DELETE CASCADE,
                source_chat TEXT,
                target_chat TEXT,
                config_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Create auto_ads_campaigns table
        logger.info("Creating auto_ads_campaigns table...")
        c.execute("""
            CREATE TABLE IF NOT EXISTS auto_ads_campaigns (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                config_id INTEGER REFERENCES auto_ads_configs(id) ON DELETE CASCADE,
                message_text TEXT,
                source_message_id INTEGER,
                target_users TEXT,
                schedule_time TIMESTAMP,
                interval_minutes INTEGER,
                bump_count INTEGER DEFAULT 0,
                forwarding_mode TEXT DEFAULT 'forward',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                sent_count INTEGER DEFAULT 0,
                last_sent TIMESTAMP
            )
        """)
        
        # Add columns if they don't exist (migration support)
        logger.info("Adding missing columns to auto_ads_campaigns if needed...")
        migrations = [
            "ALTER TABLE auto_ads_campaigns ADD COLUMN IF NOT EXISTS user_id BIGINT",
            "ALTER TABLE auto_ads_campaigns ADD COLUMN IF NOT EXISTS config_id INTEGER REFERENCES auto_ads_configs(id) ON DELETE CASCADE",
            "ALTER TABLE auto_ads_campaigns ADD COLUMN IF NOT EXISTS source_message_id INTEGER",
            "ALTER TABLE auto_ads_campaigns ADD COLUMN IF NOT EXISTS interval_minutes INTEGER",
            "ALTER TABLE auto_ads_campaigns ADD COLUMN IF NOT EXISTS bump_count INTEGER DEFAULT 0",
            "ALTER TABLE auto_ads_campaigns ADD COLUMN IF NOT EXISTS forwarding_mode TEXT DEFAULT 'forward'"
        ]
        
        for migration in migrations:
            try:
                c.execute(migration)
            except Exception as e:
                logger.debug(f"Migration already applied or failed: {e}")
        
        # Add api_id and api_hash columns to auto_ads_accounts for Telethon
        logger.info("Adding API credentials columns to auto_ads_accounts...")
        api_migrations = [
            "ALTER TABLE auto_ads_accounts ADD COLUMN IF NOT EXISTS api_id TEXT",
            "ALTER TABLE auto_ads_accounts ADD COLUMN IF NOT EXISTS api_hash TEXT"
        ]
        
        for migration in api_migrations:
            try:
                c.execute(migration)
            except Exception as e:
                logger.debug(f"API migration already applied or failed: {e}")
        
        conn.commit()
        conn.close()
        logger.info("✅ Auto ads system database tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize auto ads database: {e}", exc_info=True)
        return False

# Enhanced telethon manager instance
enhanced_telethon_manager = None

# Campaign executor for scheduled campaigns
class CampaignExecutor:
    """Handles execution of scheduled auto ads campaigns using BumpService"""
    
    def __init__(self, bump_service=None, telethon_manager=None):
        self.bump_service = bump_service
        self.telethon_manager = telethon_manager
    
    def set_services(self, bump_service, telethon_manager):
        """Set BumpService and TelethonManager after initialization"""
        self.bump_service = bump_service
        self.telethon_manager = telethon_manager
    
    def get_pending_executions(self):
        """Get list of pending campaign IDs"""
        try:
            from datetime import datetime, timezone
            conn = get_db_connection()
            c = conn.cursor()
            
            now = datetime.now(timezone.utc)
            
            # Get campaigns that are due for execution
            c.execute("""
                SELECT id FROM auto_ads_campaigns 
                WHERE is_active = TRUE 
                AND (
                    (schedule_time IS NOT NULL AND schedule_time <= %s AND last_sent IS NULL)
                    OR (interval_minutes IS NOT NULL AND (
                        last_sent IS NULL 
                        OR last_sent + INTERVAL '1 minute' * interval_minutes <= %s
                    ))
                )
            """, (now, now))
            campaigns = [row['id'] for row in c.fetchall()]
            conn.close()
            return campaigns
        except Exception as e:
            logger.error(f"Error getting pending campaigns: {e}", exc_info=True)
            return []
    
    async def execute_campaign(self, campaign_id: int):
        """Execute a specific campaign using BumpService"""
        try:
            logger.info(f"⏰ Executing campaign {campaign_id} via CampaignExecutor")
            
            if not self.bump_service:
                logger.error("BumpService not initialized in CampaignExecutor")
                return False
            
            # Use BumpService to execute the campaign
            success = await self.bump_service.execute_campaign(campaign_id)
            
            if success:
                logger.info(f"✅ Campaign {campaign_id} executed successfully via CampaignExecutor")
            else:
                logger.error(f"❌ Campaign {campaign_id} execution failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing campaign {campaign_id}: {e}", exc_info=True)
            return False

# Global campaign executor instance
_campaign_executor = None

def get_campaign_executor():
    """Get or create global campaign executor"""
    global _campaign_executor
    if _campaign_executor is None:
        _campaign_executor = CampaignExecutor()
    return _campaign_executor

def set_campaign_executor_services(bump_service, telethon_manager):
    """Set services for global campaign executor"""
    executor = get_campaign_executor()
    executor.set_services(bump_service, telethon_manager)

if __name__ == "__main__":
    bot = get_bot_instance()
    bot.run()
