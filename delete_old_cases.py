"""
One-time script to delete all pre-created cases from database
Run this once to clean up old cases
"""

import psycopg2
from utils import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_all_cases():
    """Delete all cases from database"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get count before deletion
        c.execute('SELECT COUNT(*) FROM case_settings')
        count_before = c.fetchone()[0]
        logger.info(f"Found {count_before} cases in database")
        
        # Delete all case rewards
        c.execute('DELETE FROM case_reward_pools')
        logger.info("✅ Deleted all case reward pools")
        
        # Delete all lose emojis
        c.execute('DELETE FROM case_lose_emojis')
        logger.info("✅ Deleted all lose emojis")
        
        # Delete all cases
        c.execute('DELETE FROM case_settings')
        logger.info("✅ Deleted all cases")
        
        conn.commit()
        
        # Verify
        c.execute('SELECT COUNT(*) FROM case_settings')
        count_after = c.fetchone()[0]
        logger.info(f"Cases remaining: {count_after}")
        
        if count_after == 0:
            logger.info("🎉 SUCCESS! All old cases deleted. Database is now clean.")
        else:
            logger.error(f"⚠️ WARNING: {count_after} cases still remain!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("DELETE OLD CASES SCRIPT")
    print("=" * 60)
    print("\nThis will delete ALL cases from the database.")
    print("Admin will need to create new cases through the UI.")
    print("\nRunning in 3 seconds...")
    
    import time
    time.sleep(3)
    
    delete_all_cases()
    
    print("\n" + "=" * 60)
    print("DONE! Check the logs above.")
    print("=" * 60)

