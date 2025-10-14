#!/usr/bin/env python3
"""
Manual migration script to create daily_reward_schedule table
Run this if the table is not being created automatically
"""

import logging
from utils import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_daily_reward_schedule_table():
    """Manually create the daily_reward_schedule table"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        logger.info("=" * 80)
        logger.info("🔧 MANUAL TABLE CREATION SCRIPT")
        logger.info("=" * 80)
        
        # Check if table exists
        c.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'daily_reward_schedule'
            )
        """)
        table_exists = c.fetchone()[0]
        logger.info(f"📊 Table 'daily_reward_schedule' exists: {table_exists}")
        
        if table_exists:
            logger.info("✅ Table already exists! Checking data...")
            c.execute('SELECT COUNT(*) FROM daily_reward_schedule')
            count = c.fetchone()[0]
            logger.info(f"📊 Table has {count} rows")
            
            if count > 0:
                c.execute('SELECT * FROM daily_reward_schedule ORDER BY day_number LIMIT 7')
                rows = c.fetchall()
                logger.info("📋 Current schedule:")
                for row in rows:
                    logger.info(f"   Day {row['day_number']}: {row['points']} pts - {row['description']}")
                logger.info("=" * 80)
                logger.info("✅ Table is properly configured!")
                return True
        
        logger.info("🔧 Creating daily_reward_schedule table...")
        
        # Create table
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_reward_schedule (
                day_number INTEGER PRIMARY KEY,
                points INTEGER NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logger.info("✅ Table created successfully")
        
        # Insert default schedule
        c.execute('SELECT COUNT(*) FROM daily_reward_schedule')
        count = c.fetchone()[0]
        
        if count == 0:
            logger.info("📝 Inserting default 7-day schedule...")
            default_schedule = [
                (1, 50, 'Welcome bonus'),
                (2, 15, 'Day 2 reward'),
                (3, 25, 'Day 3 reward'),
                (4, 40, 'Day 4 reward'),
                (5, 60, 'Day 5 reward'),
                (6, 90, 'Day 6 reward'),
                (7, 150, 'Week complete!'),
            ]
            c.executemany('''
                INSERT INTO daily_reward_schedule (day_number, points, description)
                VALUES (%s, %s, %s)
            ''', default_schedule)
            logger.info("✅ Inserted 7 default days")
        
        # Commit changes
        logger.info("💾 Committing changes...")
        conn.commit()
        logger.info("✅ Changes committed successfully")
        
        # Verify
        c.execute('SELECT COUNT(*) FROM daily_reward_schedule')
        final_count = c.fetchone()[0]
        logger.info(f"✅ Final verification: {final_count} rows in table")
        
        c.execute('SELECT * FROM daily_reward_schedule ORDER BY day_number')
        rows = c.fetchall()
        logger.info("📋 Final schedule:")
        for row in rows:
            logger.info(f"   Day {row['day_number']}: {row['points']} pts - {row['description']}")
        
        logger.info("=" * 80)
        logger.info("✅✅✅ TABLE CREATION COMPLETE! ✅✅✅")
        logger.info("=" * 80)
        return True
        
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = create_daily_reward_schedule_table()
    if success:
        print("\n✅ SUCCESS! The daily_reward_schedule table is ready.")
        print("You can now use the Daily Rewards feature.")
    else:
        print("\n❌ FAILED! Check the error messages above.")

