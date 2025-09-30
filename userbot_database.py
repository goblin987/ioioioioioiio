"""
Userbot Database Operations for PostgreSQL
Handles all database operations for the Telegram userbot system.
"""

import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Optional, Dict, List
import os

logger = logging.getLogger(__name__)

def get_db_connection():
    """Get PostgreSQL database connection using existing method"""
    from utils import get_db_connection as get_conn
    return get_conn()

def init_userbot_tables():
    """Initialize all userbot-related PostgreSQL tables"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Userbot configuration table
        c.execute('''
            CREATE TABLE IF NOT EXISTS userbot_config (
                id SERIAL PRIMARY KEY,
                api_id TEXT,
                api_hash TEXT,
                phone_number TEXT,
                enabled BOOLEAN DEFAULT FALSE,
                auto_reconnect BOOLEAN DEFAULT TRUE,
                send_notifications BOOLEAN DEFAULT TRUE,
                max_retries INTEGER DEFAULT 3,
                retry_delay INTEGER DEFAULT 5,
                secret_chat_ttl INTEGER DEFAULT 86400,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Userbot session storage
        c.execute('''
            CREATE TABLE IF NOT EXISTS userbot_sessions (
                id SERIAL PRIMARY KEY,
                session_string TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Connection status tracking
        c.execute('''
            CREATE TABLE IF NOT EXISTS userbot_status (
                id SERIAL PRIMARY KEY,
                is_connected BOOLEAN NOT NULL DEFAULT FALSE,
                status_message TEXT,
                last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Secret chat tracking
        c.execute('''
            CREATE TABLE IF NOT EXISTS userbot_secret_chats (
                user_id BIGINT PRIMARY KEY NOT NULL,
                secret_chat_id BIGINT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_delivered_at TIMESTAMP WITH TIME ZONE
            )
        ''')
        
        # Delivery statistics
        c.execute('''
            CREATE TABLE IF NOT EXISTS userbot_delivery_stats (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                order_id TEXT NOT NULL,
                delivery_status TEXT NOT NULL,
                delivered_at TIMESTAMP WITH TIME ZONE,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Delivery keywords
        c.execute('''
            CREATE TABLE IF NOT EXISTS userbot_delivery_keywords (
                keyword TEXT PRIMARY KEY NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Create indexes
        c.execute('CREATE INDEX IF NOT EXISTS idx_userbot_delivery_stats_user_id ON userbot_delivery_stats(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_userbot_delivery_stats_order_id ON userbot_delivery_stats(order_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_userbot_delivery_stats_status ON userbot_delivery_stats(delivery_status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_userbot_secret_chats_user_id ON userbot_secret_chats(user_id)')
        
        # Initialize status record if not exists
        c.execute('''
            INSERT INTO userbot_status (id, is_connected, status_message)
            VALUES (1, FALSE, 'Not initialized')
            ON CONFLICT (id) DO NOTHING
        ''')
        
        conn.commit()
        logger.info("✅ Userbot tables initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Error initializing userbot tables: {e}", exc_info=True)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

# ==================== CONFIG OPERATIONS ====================

def save_userbot_config(api_id: str, api_hash: str, phone_number: str) -> bool:
    """Save userbot configuration to PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO userbot_config 
            (id, api_id, api_hash, phone_number, enabled, created_at, updated_at)
            VALUES (1, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                api_id = EXCLUDED.api_id,
                api_hash = EXCLUDED.api_hash,
                phone_number = EXCLUDED.phone_number,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        ''', (api_id, api_hash, phone_number))
        
        result = c.fetchone()
        conn.commit()
        logger.info("✅ Userbot config saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving userbot config: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_userbot_config() -> Optional[Dict]:
    """Get userbot configuration from PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('SELECT * FROM userbot_config WHERE id = 1')
        result = c.fetchone()
        
        if result:
            return dict(result)
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting userbot config: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()

def update_userbot_setting(setting_name: str, value) -> bool:
    """Update a specific userbot setting"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute(f'''
            UPDATE userbot_config 
            SET {setting_name} = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (value,))
        
        conn.commit()
        logger.info(f"✅ Updated userbot setting: {setting_name} = {value}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating userbot setting {setting_name}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def is_userbot_configured() -> bool:
    """Check if userbot is configured"""
    config = get_userbot_config()
    if not config:
        return False
    return bool(config.get('api_id') and config.get('api_hash') and config.get('phone_number'))

def is_userbot_enabled() -> bool:
    """Check if userbot delivery is enabled"""
    config = get_userbot_config()
    if not config:
        return False
    return config.get('enabled', False)

def reset_userbot_config() -> bool:
    """Reset userbot configuration (delete all config)"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('DELETE FROM userbot_config WHERE id = 1')
        c.execute('DELETE FROM userbot_sessions')
        c.execute('UPDATE userbot_status SET is_connected = FALSE, status_message = %s WHERE id = 1', ('Configuration reset',))
        
        conn.commit()
        logger.info("✅ Userbot config reset successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error resetting userbot config: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ==================== SESSION OPERATIONS ====================

def save_session_string(session_string: str) -> bool:
    """Save Pyrogram session string to PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Delete old sessions first
        c.execute('DELETE FROM userbot_sessions')
        
        # Insert new session
        c.execute('''
            INSERT INTO userbot_sessions (session_string, created_at)
            VALUES (%s, CURRENT_TIMESTAMP)
        ''', (session_string,))
        
        conn.commit()
        logger.info("✅ Session string saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving session string: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_session_string() -> Optional[str]:
    """Get Pyrogram session string from PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('SELECT session_string FROM userbot_sessions ORDER BY created_at DESC LIMIT 1')
        result = c.fetchone()
        
        if result:
            return result['session_string']
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting session string: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()

# ==================== STATUS OPERATIONS ====================

def update_connection_status(is_connected: bool, status_message: str = None) -> bool:
    """Update userbot connection status"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            UPDATE userbot_status 
            SET is_connected = %s, 
                status_message = %s,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (is_connected, status_message))
        
        conn.commit()
        logger.info(f"✅ Connection status updated: {is_connected} - {status_message}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating connection status: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_connection_status() -> Dict:
    """Get current userbot connection status"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('SELECT * FROM userbot_status WHERE id = 1')
        result = c.fetchone()
        
        if result:
            return dict(result)
        return {
            'is_connected': False,
            'status_message': 'Unknown',
            'last_updated': None
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting connection status: {e}", exc_info=True)
        return {
            'is_connected': False,
            'status_message': 'Error',
            'last_updated': None
        }
    finally:
        if conn:
            conn.close()

# ==================== DELIVERY STATS OPERATIONS ====================

def log_delivery(user_id: int, order_id: str, status: str, error_message: str = None) -> bool:
    """Log a delivery attempt"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        delivered_at = datetime.now(timezone.utc) if status == 'success' else None
        
        c.execute('''
            INSERT INTO userbot_delivery_stats 
            (user_id, order_id, delivery_status, delivered_at, error_message, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ''', (user_id, order_id, status, delivered_at, error_message))
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error logging delivery: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_delivery_stats() -> Dict:
    """Get delivery statistics"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Total deliveries
        c.execute("SELECT COUNT(*) as total FROM userbot_delivery_stats")
        total = c.fetchone()['total']
        
        # Successful deliveries
        c.execute("SELECT COUNT(*) as success FROM userbot_delivery_stats WHERE delivery_status = 'success'")
        success = c.fetchone()['success']
        
        # Failed deliveries
        c.execute("SELECT COUNT(*) as failed FROM userbot_delivery_stats WHERE delivery_status = 'failed'")
        failed = c.fetchone()['failed']
        
        # Success rate
        success_rate = (success / total * 100) if total > 0 else 0
        
        # Last 10 deliveries
        c.execute('''
            SELECT user_id, order_id, delivery_status, delivered_at, error_message
            FROM userbot_delivery_stats
            ORDER BY created_at DESC
            LIMIT 10
        ''')
        recent_deliveries = [dict(row) for row in c.fetchall()]
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': round(success_rate, 2),
            'recent_deliveries': recent_deliveries
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting delivery stats: {e}", exc_info=True)
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'success_rate': 0,
            'recent_deliveries': []
        }
    finally:
        if conn:
            conn.close()

# ==================== SECRET CHAT OPERATIONS ====================

def save_secret_chat(user_id: int, secret_chat_id: int) -> bool:
    """Save secret chat ID for a user"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO userbot_secret_chats (user_id, secret_chat_id, created_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                secret_chat_id = EXCLUDED.secret_chat_id,
                last_delivered_at = CURRENT_TIMESTAMP
        ''', (user_id, secret_chat_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving secret chat: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_secret_chat_id(user_id: int) -> Optional[int]:
    """Get secret chat ID for a user"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('SELECT secret_chat_id FROM userbot_secret_chats WHERE user_id = %s', (user_id,))
        result = c.fetchone()
        
        if result:
            return result['secret_chat_id']
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting secret chat ID: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()

