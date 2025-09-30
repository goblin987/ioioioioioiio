"""
Multi-Userbot Database Management
Handles all database operations for the multi-userbot system
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from utils import get_db_connection

logger = logging.getLogger(__name__)

# ==================== SCHEMA CREATION ====================

def init_userbot_tables():
    """Initialize userbot tables - called from main.py"""
    return create_multi_userbot_schema()

def create_multi_userbot_schema():
    """Create all tables for multi-userbot system"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Main userbot accounts table
        c.execute("""
            CREATE TABLE IF NOT EXISTS userbots (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                api_id TEXT NOT NULL,
                api_hash TEXT NOT NULL,
                phone_number TEXT NOT NULL UNIQUE,
                session_string TEXT,
                is_enabled BOOLEAN DEFAULT TRUE,
                is_connected BOOLEAN DEFAULT FALSE,
                status_message TEXT,
                priority INTEGER DEFAULT 0,
                max_deliveries_per_hour INTEGER DEFAULT 30,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_connected_at TIMESTAMP WITH TIME ZONE,
                last_error TEXT
            )
        """)
        
        # Userbot delivery assignments
        c.execute("""
            CREATE TABLE IF NOT EXISTS userbot_deliveries (
                id SERIAL PRIMARY KEY,
                userbot_id INTEGER NOT NULL REFERENCES userbots(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                order_id TEXT NOT NULL,
                delivery_status TEXT NOT NULL,
                delivery_time REAL,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE
            )
        """)
        
        # Userbot statistics
        c.execute("""
            CREATE TABLE IF NOT EXISTS userbot_stats (
                userbot_id INTEGER PRIMARY KEY REFERENCES userbots(id) ON DELETE CASCADE,
                total_deliveries INTEGER DEFAULT 0,
                successful_deliveries INTEGER DEFAULT 0,
                failed_deliveries INTEGER DEFAULT 0,
                total_delivery_time REAL DEFAULT 0,
                last_delivery_at TIMESTAMP WITH TIME ZONE,
                deliveries_last_hour INTEGER DEFAULT 0,
                last_hour_reset_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Global userbot settings
        c.execute("""
            CREATE TABLE IF NOT EXISTS userbot_settings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                enabled BOOLEAN DEFAULT TRUE,
                load_balancing_strategy TEXT DEFAULT 'round_robin',
                auto_reconnect BOOLEAN DEFAULT TRUE,
                max_retry_attempts INTEGER DEFAULT 3,
                retry_delay_seconds INTEGER DEFAULT 5,
                secret_chat_ttl_hours INTEGER DEFAULT 24,
                saved_messages_cleanup_hours INTEGER DEFAULT 6,
                delivery_delay_seconds INTEGER DEFAULT 30,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert default settings if not exists
        c.execute("SELECT COUNT(*) FROM userbot_settings WHERE id = 1")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO userbot_settings (id) VALUES (1)")
        
        # Create indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_userbots_enabled ON userbots(is_enabled)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_userbots_connected ON userbots(is_connected)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_userbots_priority ON userbots(priority DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_userbot_deliveries_status ON userbot_deliveries(delivery_status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_userbot_deliveries_userbot_id ON userbot_deliveries(userbot_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_userbot_deliveries_created_at ON userbot_deliveries(created_at DESC)")
        
        conn.commit()
        logger.info("✅ Multi-userbot database schema created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating multi-userbot schema: {e}", exc_info=True)
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False
    finally:
        if conn:
            conn.close()

# ==================== USERBOT MANAGEMENT ====================

def add_userbot(name: str, api_id: str, api_hash: str, phone_number: str, 
                session_string: Optional[str] = None, priority: int = 0) -> Optional[int]:
    """Add a new userbot"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO userbots (name, api_id, api_hash, phone_number, session_string, priority)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, api_id, api_hash, phone_number, session_string, priority))
        
        userbot_id = c.fetchone()[0]
        
        # Initialize stats
        c.execute("""
            INSERT INTO userbot_stats (userbot_id)
            VALUES (%s)
        """, (userbot_id,))
        
        conn.commit()
        logger.info(f"✅ Added userbot '{name}' (ID: {userbot_id})")
        return userbot_id
        
    except Exception as e:
        logger.error(f"❌ Error adding userbot: {e}", exc_info=True)
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return None
    finally:
        if conn:
            conn.close()

def get_userbot(userbot_id: int) -> Optional[Dict[str, Any]]:
    """Get userbot by ID"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("SELECT * FROM userbots WHERE id = %s", (userbot_id,))
        row = c.fetchone()
        
        if row:
            return dict(row)
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting userbot {userbot_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_all_userbots() -> List[Dict[str, Any]]:
    """Get all userbots"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT u.*, 
                   s.total_deliveries, s.successful_deliveries, s.failed_deliveries,
                   s.last_delivery_at, s.deliveries_last_hour
            FROM userbots u
            LEFT JOIN userbot_stats s ON u.id = s.userbot_id
            ORDER BY u.priority DESC, u.id ASC
        """)
        
        return [dict(row) for row in c.fetchall()]
        
    except Exception as e:
        logger.error(f"❌ Error getting all userbots: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_available_userbots() -> List[Dict[str, Any]]:
    """Get all enabled and connected userbots"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT u.*, 
                   s.deliveries_last_hour, s.last_hour_reset_at
            FROM userbots u
            LEFT JOIN userbot_stats s ON u.id = s.userbot_id
            WHERE u.is_enabled = TRUE AND u.is_connected = TRUE
            ORDER BY u.priority DESC, u.id ASC
        """)
        
        userbots = [dict(row) for row in c.fetchall()]
        
        # Filter out userbots that exceeded rate limit
        available = []
        for ub in userbots:
            # Reset hourly counter if needed
            if ub.get('last_hour_reset_at'):
                reset_time = ub['last_hour_reset_at']
                if datetime.now(reset_time.tzinfo) - reset_time > timedelta(hours=1):
                    reset_hourly_deliveries(ub['id'])
                    ub['deliveries_last_hour'] = 0
            
            # Check rate limit
            if ub.get('deliveries_last_hour', 0) < ub.get('max_deliveries_per_hour', 30):
                available.append(ub)
        
        return available
        
    except Exception as e:
        logger.error(f"❌ Error getting available userbots: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_userbot_connection(userbot_id: int, is_connected: bool, 
                               status_message: Optional[str] = None,
                               error_message: Optional[str] = None):
    """Update userbot connection status"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        updates = ["is_connected = %s", "updated_at = CURRENT_TIMESTAMP"]
        params = [is_connected]
        
        if is_connected:
            updates.append("last_connected_at = CURRENT_TIMESTAMP")
        
        if status_message is not None:
            updates.append("status_message = %s")
            params.append(status_message)
        
        if error_message is not None:
            updates.append("last_error = %s")
            params.append(error_message)
        
        params.append(userbot_id)
        
        c.execute(f"""
            UPDATE userbots
            SET {', '.join(updates)}
            WHERE id = %s
        """, params)
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"❌ Error updating userbot connection: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            conn.close()

def update_userbot_session(userbot_id: int, session_string: str):
    """Update userbot session string"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE userbots
            SET session_string = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (session_string, userbot_id))
        
        conn.commit()
        logger.info(f"✅ Updated session for userbot {userbot_id}")
        
    except Exception as e:
        logger.error(f"❌ Error updating userbot session: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            conn.close()

def toggle_userbot_enabled(userbot_id: int, is_enabled: bool):
    """Enable/disable userbot"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE userbots
            SET is_enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (is_enabled, userbot_id))
        
        conn.commit()
        logger.info(f"✅ Userbot {userbot_id} {'enabled' if is_enabled else 'disabled'}")
        
    except Exception as e:
        logger.error(f"❌ Error toggling userbot enabled: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            conn.close()

def update_userbot_priority(userbot_id: int, priority: int):
    """Update userbot priority"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE userbots
            SET priority = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (priority, userbot_id))
        
        conn.commit()
        logger.info(f"✅ Updated userbot {userbot_id} priority to {priority}")
        
    except Exception as e:
        logger.error(f"❌ Error updating userbot priority: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            conn.close()

def update_userbot_name(userbot_id: int, name: str):
    """Update userbot name"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE userbots
            SET name = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (name, userbot_id))
        
        conn.commit()
        logger.info(f"✅ Updated userbot {userbot_id} name to '{name}'")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating userbot name: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False
    finally:
        if conn:
            conn.close()

def delete_userbot(userbot_id: int):
    """Delete userbot"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("DELETE FROM userbots WHERE id = %s", (userbot_id,))
        conn.commit()
        logger.info(f"✅ Deleted userbot {userbot_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error deleting userbot: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False
    finally:
        if conn:
            conn.close()

# ==================== DELIVERY TRACKING ====================

def record_delivery_start(userbot_id: int, user_id: int, order_id: str) -> Optional[int]:
    """Record delivery start"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO userbot_deliveries (userbot_id, user_id, order_id, delivery_status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING id
        """, (userbot_id, user_id, order_id))
        
        delivery_id = c.fetchone()[0]
        conn.commit()
        return delivery_id
        
    except Exception as e:
        logger.error(f"❌ Error recording delivery start: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return None
    finally:
        if conn:
            conn.close()

def record_delivery_complete(delivery_id: int, success: bool, delivery_time: float,
                             error_message: Optional[str] = None):
    """Record delivery completion"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        status = 'delivered' if success else 'failed'
        
        c.execute("""
            UPDATE userbot_deliveries
            SET delivery_status = %s, delivery_time = %s, error_message = %s, 
                completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING userbot_id
        """, (status, delivery_time, error_message, delivery_id))
        
        result = c.fetchone()
        if result:
            userbot_id = result[0]
            
            # Update stats
            if success:
                c.execute("""
                    UPDATE userbot_stats
                    SET total_deliveries = total_deliveries + 1,
                        successful_deliveries = successful_deliveries + 1,
                        total_delivery_time = total_delivery_time + %s,
                        deliveries_last_hour = deliveries_last_hour + 1,
                        last_delivery_at = CURRENT_TIMESTAMP
                    WHERE userbot_id = %s
                """, (delivery_time, userbot_id))
            else:
                c.execute("""
                    UPDATE userbot_stats
                    SET total_deliveries = total_deliveries + 1,
                        failed_deliveries = failed_deliveries + 1,
                        deliveries_last_hour = deliveries_last_hour + 1,
                        last_delivery_at = CURRENT_TIMESTAMP
                    WHERE userbot_id = %s
                """, (userbot_id,))
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"❌ Error recording delivery complete: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            conn.close()

def reset_hourly_deliveries(userbot_id: int):
    """Reset hourly delivery counter"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE userbot_stats
            SET deliveries_last_hour = 0, last_hour_reset_at = CURRENT_TIMESTAMP
            WHERE userbot_id = %s
        """, (userbot_id,))
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"❌ Error resetting hourly deliveries: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            conn.close()

# ==================== GLOBAL SETTINGS ====================

def get_global_settings() -> Dict[str, Any]:
    """Get global userbot settings"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("SELECT * FROM userbot_settings WHERE id = 1")
        row = c.fetchone()
        
        if row:
            return dict(row)
        return {}
        
    except Exception as e:
        logger.error(f"❌ Error getting global settings: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def update_global_settings(**kwargs):
    """Update global userbot settings"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        
        for key, value in kwargs.items():
            updates.append(f"{key} = %s")
            params.append(value)
        
        c.execute(f"""
            UPDATE userbot_settings
            SET {', '.join(updates)}
            WHERE id = 1
        """, params)
        
        conn.commit()
        logger.info(f"✅ Updated global settings: {kwargs}")
        
    except Exception as e:
        logger.error(f"❌ Error updating global settings: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            conn.close()

# ==================== STATISTICS ====================

def get_overall_stats() -> Dict[str, Any]:
    """Get overall statistics for all userbots"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Overall stats
        c.execute("""
            SELECT 
                COUNT(*) as total_userbots,
                SUM(CASE WHEN is_connected THEN 1 ELSE 0 END) as connected_userbots,
                SUM(CASE WHEN is_enabled THEN 1 ELSE 0 END) as enabled_userbots
            FROM userbots
        """)
        overall = dict(c.fetchone())
        
        # Delivery stats
        c.execute("""
            SELECT 
                SUM(total_deliveries) as total_deliveries,
                SUM(successful_deliveries) as successful_deliveries,
                SUM(failed_deliveries) as failed_deliveries,
                AVG(total_delivery_time / NULLIF(successful_deliveries, 0)) as avg_delivery_time
            FROM userbot_stats
        """)
        delivery_stats = dict(c.fetchone())
        
        # Last 24 hours
        c.execute("""
            SELECT COUNT(*) as deliveries_24h
            FROM userbot_deliveries
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        recent = dict(c.fetchone())
        
        return {**overall, **delivery_stats, **recent}
        
    except Exception as e:
        logger.error(f"❌ Error getting overall stats: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def get_userbot_stats(userbot_id: int) -> Dict[str, Any]:
    """Get statistics for specific userbot"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT u.*, s.*
            FROM userbots u
            LEFT JOIN userbot_stats s ON u.id = s.userbot_id
            WHERE u.id = %s
        """, (userbot_id,))
        
        row = c.fetchone()
        if row:
            return dict(row)
        return {}
        
    except Exception as e:
        logger.error(f"❌ Error getting userbot stats: {e}")
        return {}
    finally:
        if conn:
            conn.close()
