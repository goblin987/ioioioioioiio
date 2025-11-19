"""
Auto Ads Database Management (PostgreSQL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Professional database layer for auto ads system using PostgreSQL.
Provides secure data persistence, account management, campaign storage, and performance analytics.

Author: TgCF Pro Team (Adapted for Botshop PostgreSQL)
License: MIT
Version: 2.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
from typing import Dict, List, Optional
from utils import get_db_connection

logger = logging.getLogger(__name__)

class AutoAdsDatabase:
    """PostgreSQL database manager for auto ads system"""
    
    def __init__(self):
        """Initialize database connection using botshop's utils.get_db_connection()"""
        pass  # Connection is managed per-query via get_db_connection()
    
    def _get_conn(self):
        """Get PostgreSQL database connection from utils"""
        return get_db_connection()
    
    def add_telegram_account(self, user_id: int, account_name: str, phone_number: str, 
                           api_id: str, api_hash: str, session_string: str = None) -> int:
        """Add Telegram account"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO auto_ads_accounts 
                (user_id, account_name, phone_number, api_id, api_hash, session_string)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (user_id, account_name, phone_number, api_id, api_hash, session_string))
            account_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"✅ Added auto ads account {account_name} (ID: {account_id})")
            return account_id
        except Exception as e:
            logger.error(f"❌ Error adding telegram account: {e}")
            if conn:
                conn.rollback()
                conn.close()
            raise
    
    def get_user_accounts(self, user_id: int) -> List[Dict]:
        """Get all Telegram accounts for a user"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('''
                SELECT id, user_id, account_name, phone_number, api_id, api_hash, 
                       session_string, is_active, created_at
                FROM auto_ads_accounts 
                WHERE user_id = %s AND is_active = TRUE
                ORDER BY created_at DESC
            ''', (user_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            return [{
                'id': row[0],
                'user_id': row[1],
                'account_name': row[2],
                'phone_number': row[3],
                'api_id': row[4],
                'api_hash': row[5],
                'session_string': row[6],
                'is_active': row[7],
                'created_at': row[8]
            } for row in rows]
        except Exception as e:
            logger.error(f"❌ Error getting user accounts: {e}")
            return []
    
    def get_account(self, account_id: int) -> Optional[Dict]:
        """Get account by ID"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('''
                SELECT id, user_id, account_name, phone_number, api_id, api_hash, 
                       session_string, is_active, created_at
                FROM auto_ads_accounts 
                WHERE id = %s
            ''', (account_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'user_id': row[1],
                    'account_name': row[2],
                    'phone_number': row[3],
                    'api_id': row[4],
                    'api_hash': row[5],
                    'session_string': row[6],
                    'is_active': row[7],
                    'created_at': row[8]
                }
            return None
        except Exception as e:
            logger.error(f"❌ Error getting account: {e}")
            return None
    
    def update_account_session(self, account_id: int, session_string: str):
        """Update account session string"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('''
                UPDATE auto_ads_accounts 
                SET session_string = %s
                WHERE id = %s
            ''', (session_string, account_id))
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"✅ Updated session for account {account_id}")
        except Exception as e:
            logger.error(f"❌ Error updating account session: {e}")
            if conn:
                conn.rollback()
                conn.close()
    
    def delete_account(self, account_id: int):
        """Delete Telegram account and clean up all related data"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            
            # Get account info before deletion for logging
            cur.execute('SELECT account_name, phone_number FROM auto_ads_accounts WHERE id = %s', (account_id,))
            account_info = cur.fetchone()
            
            # Completely remove the account record (not just deactivate)
            cur.execute('DELETE FROM auto_ads_accounts WHERE id = %s', (account_id,))
            
            # Also clean up related data
            cur.execute('DELETE FROM auto_ads_campaigns WHERE account_id = %s', (account_id,))
            cur.execute('DELETE FROM account_usage_tracking WHERE account_id = %s', (account_id,))
            
            conn.commit()
            cur.close()
            conn.close()
            
            if account_info:
                logger.info(f"✅ Completely deleted account '{account_info[0]}' ({account_info[1]}) and all related data")
            else:
                logger.info(f"✅ Deleted account {account_id} and all related data")
        except Exception as e:
            logger.error(f"❌ Error deleting account: {e}")
            if conn:
                conn.rollback()
                conn.close()
    
    def add_campaign(self, user_id: int, account_id: int, campaign_name: str, 
                    ad_content: any, target_chats: list, buttons: list = None,
                    schedule_type: str = 'once', schedule_time: str = None) -> int:
        """Add a new campaign"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            
            # Convert data to JSON
            ad_content_json = json.dumps(ad_content) if isinstance(ad_content, (dict, list)) else ad_content
            target_chats_json = json.dumps(target_chats) if isinstance(target_chats, list) else target_chats
            buttons_json = json.dumps(buttons) if buttons else None
            
            cur.execute('''
                INSERT INTO auto_ads_campaigns 
                (user_id, account_id, campaign_name, ad_content, target_chats, buttons,
                 schedule_type, schedule_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (user_id, account_id, campaign_name, ad_content_json, target_chats_json, 
                  buttons_json, schedule_type, schedule_time))
            
            campaign_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"✅ Added campaign '{campaign_name}' (ID: {campaign_id})")
            return campaign_id
        except Exception as e:
            logger.error(f"❌ Error adding campaign: {e}")
            if conn:
                conn.rollback()
                conn.close()
            raise
    
    def get_user_campaigns(self, user_id: int) -> List[Dict]:
        """Get all campaigns for a user"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('''
                SELECT c.id, c.user_id, c.account_id, c.campaign_name, c.ad_content,
                       c.target_chats, c.buttons, c.schedule_type, c.schedule_time,
                       c.is_active, c.sent_count, c.last_sent, c.created_at,
                       a.account_name, a.phone_number
                FROM auto_ads_campaigns c
                LEFT JOIN auto_ads_accounts a ON c.account_id = a.id
                WHERE c.user_id = %s
                ORDER BY c.created_at DESC
            ''', (user_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            campaigns = []
            for row in rows:
                campaign = {
                    'id': row[0],
                    'user_id': row[1],
                    'account_id': row[2],
                    'campaign_name': row[3],
                    'ad_content': self._parse_json(row[4]),
                    'target_chats': self._parse_json(row[5]),
                    'buttons': self._parse_json(row[6]),
                    'schedule_type': row[7],
                    'schedule_time': row[8],
                    'is_active': row[9],
                    'sent_count': row[10] or 0,
                    'last_sent': row[11],
                    'created_at': row[12],
                    'account_name': row[13],
                    'phone_number': row[14]
                }
                campaigns.append(campaign)
            
            return campaigns
        except Exception as e:
            logger.error(f"❌ Error getting user campaigns: {e}")
            return []
    
    def get_campaign(self, campaign_id: int) -> Optional[Dict]:
        """Get a campaign by ID"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('''
                SELECT c.id, c.user_id, c.account_id, c.campaign_name, c.ad_content,
                       c.target_chats, c.buttons, c.schedule_type, c.schedule_time,
                       c.is_active, c.sent_count, c.last_sent, c.created_at,
                       a.account_name, a.phone_number
                FROM auto_ads_campaigns c
                LEFT JOIN auto_ads_accounts a ON c.account_id = a.id
                WHERE c.id = %s
            ''', (campaign_id,))
            
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'user_id': row[1],
                    'account_id': row[2],
                    'campaign_name': row[3],
                    'ad_content': self._parse_json(row[4]),
                    'target_chats': self._parse_json(row[5]),
                    'buttons': self._parse_json(row[6]),
                    'schedule_type': row[7],
                    'schedule_time': row[8],
                    'is_active': row[9],
                    'sent_count': row[10] or 0,
                    'last_sent': row[11],
                    'created_at': row[12],
                    'account_name': row[13],
                    'phone_number': row[14]
                }
            return None
        except Exception as e:
            logger.error(f"❌ Error getting campaign: {e}")
            return None
    
    def update_campaign_last_run(self, campaign_id: int):
        """Update the last run time for a campaign"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('''
                UPDATE auto_ads_campaigns 
                SET last_sent = NOW(),
                    sent_count = COALESCE(sent_count, 0) + 1
                WHERE id = %s
            ''', (campaign_id,))
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"✅ Updated last run for campaign {campaign_id}")
        except Exception as e:
            logger.error(f"❌ Error updating campaign last run: {e}")
            if conn:
                conn.rollback()
                conn.close()
    
    def update_campaign_status(self, campaign_id: int, is_active: bool):
        """Update campaign active status"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('''
                UPDATE auto_ads_campaigns 
                SET is_active = %s
                WHERE id = %s
            ''', (is_active, campaign_id))
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"✅ Updated campaign {campaign_id} status to {is_active}")
        except Exception as e:
            logger.error(f"❌ Error updating campaign status: {e}")
            if conn:
                conn.rollback()
                conn.close()
    
    def delete_campaign(self, campaign_id: int):
        """Delete a campaign"""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('DELETE FROM auto_ads_campaigns WHERE id = %s', (campaign_id,))
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"✅ Deleted campaign {campaign_id}")
        except Exception as e:
            logger.error(f"❌ Error deleting campaign: {e}")
            if conn:
                conn.rollback()
                conn.close()
    
    def _parse_json(self, json_str):
        """Parse JSON string, return empty dict/list on error"""
        if not json_str:
            return None
        try:
            if isinstance(json_str, (dict, list)):
                return json_str
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return {}

