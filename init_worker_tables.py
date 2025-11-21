"""
Database initialization script for Worker Management System.
Creates workers, worker_activity_log tables and extends products table.
"""

import logging

# Import database connection from utils
from utils import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_worker_tables():
    """Initialize worker management tables"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        logger.info("Starting worker tables initialization...")
        
        # 1. Create workers table
        logger.info("Creating workers table...")
        c.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                added_by BIGINT NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                permissions JSONB DEFAULT '[]'::jsonb,
                allowed_locations JSONB DEFAULT '{}'::jsonb,
                is_active BOOLEAN DEFAULT true
            )
        """)
        
        # 2. Create worker_activity_log table
        logger.info("Creating worker_activity_log table...")
        c.execute("""
            CREATE TABLE IF NOT EXISTS worker_activity_log (
                id SERIAL PRIMARY KEY,
                worker_id INTEGER REFERENCES workers(id) ON DELETE CASCADE,
                action_type TEXT NOT NULL,
                product_id INTEGER,
                product_count INTEGER DEFAULT 1,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details JSONB DEFAULT '{}'::jsonb
            )
        """)
        
        # 3. Add indexes for performance
        logger.info("Creating indexes...")
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_workers_user_id ON workers(user_id)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_workers_is_active ON workers(is_active)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_worker_activity_worker_id ON worker_activity_log(worker_id)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_worker_activity_timestamp ON worker_activity_log(timestamp)
        """)
        
        # 4. Check if products table needs added_by_worker_id column
        logger.info("Checking products table for added_by_worker_id column...")
        c.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'products' AND column_name = 'added_by_worker_id'
        """)
        
        if not c.fetchone():
            logger.info("Adding added_by_worker_id column to products table...")
            c.execute("""
                ALTER TABLE products 
                ADD COLUMN added_by_worker_id INTEGER REFERENCES workers(id) ON DELETE SET NULL
            """)
            
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_added_by_worker ON products(added_by_worker_id)
            """)
            logger.info("✅ Added added_by_worker_id column to products table")
        else:
            logger.info("✅ added_by_worker_id column already exists in products table")
        
        conn.commit()
        logger.info("✅ Worker tables initialized successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error initializing worker tables: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_worker_tables()

