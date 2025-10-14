#!/usr/bin/env python3
"""
Bot Shop Diagnostic Tool
Run this to check for common issues
"""

import sys
import os

print("🔍 BOT SHOP DIAGNOSTIC TOOL")
print("=" * 50)

# Check 1: Python version
print("\n1️⃣ Checking Python version...")
if sys.version_info >= (3, 8):
    print(f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
else:
    print(f"   ❌ Python {sys.version_info.major}.{sys.version_info.minor} (need 3.8+)")

# Check 2: Required files
print("\n2️⃣ Checking required files...")
required_files = [
    'main.py', 'utils.py', 'user.py', 'admin.py', 'payment.py',
    'daily_rewards_system.py', 'case_opening_handlers.py',
    'marquee_text_system.py', 'running_ads_display.py'
]
for file in required_files:
    if os.path.exists(file):
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} MISSING!")

# Check 3: Environment variables
print("\n3️⃣ Checking environment variables...")
env_vars = [
    'DATABASE_URL', 'BOT_TOKEN', 'POSTGRES_HOST',
    'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD'
]
for var in env_vars:
    if os.getenv(var):
        print(f"   ✅ {var} is set")
    else:
        print(f"   ⚠️  {var} not set (may use defaults)")

# Check 4: Database connection
print("\n4️⃣ Testing database connection...")
try:
    from utils import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    conn.close()
    print("   ✅ Database connection successful!")
except Exception as e:
    print(f"   ❌ Database connection failed: {e}")

# Check 5: Critical tables
print("\n5️⃣ Checking critical database tables...")
try:
    from utils import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    tables_to_check = [
        'users', 'products', 'purchases', 'basket',
        'daily_reward_schedule', 'case_settings', 'user_points',
        'marquee_settings'
    ]
    
    for table in tables_to_check:
        cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table}'
            )
        """)
        exists = cursor.fetchone()[0]
        if exists:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   ✅ {table} ({count} rows)")
        else:
            print(f"   ❌ {table} MISSING!")
    
    conn.close()
except Exception as e:
    print(f"   ❌ Table check failed: {e}")

# Check 6: Import test
print("\n6️⃣ Testing Python imports...")
modules_to_test = [
    'telegram', 'psycopg2', 'PIL', 'flask', 'asyncio'
]
for module in modules_to_test:
    try:
        __import__(module)
        print(f"   ✅ {module}")
    except ImportError:
        print(f"   ❌ {module} NOT INSTALLED!")

# Check 7: Syntax check
print("\n7️⃣ Checking Python syntax...")
files_to_check = [
    'main.py', 'utils.py', 'user.py', 'admin.py',
    'daily_rewards_system.py', 'marquee_text_system.py'
]
import py_compile
for file in files_to_check:
    try:
        py_compile.compile(file, doraise=True)
        print(f"   ✅ {file}")
    except py_compile.PyCompileError as e:
        print(f"   ❌ {file}: {e}")

# Summary
print("\n" + "=" * 50)
print("📊 DIAGNOSTIC COMPLETE")
print("\nNext steps:")
print("1. Fix any ❌ errors above")
print("2. Check DEBUGGING_GUIDE.md for detailed help")
print("3. Review Render logs for runtime errors")
print("4. Test bot with /start command")
print("\n✅ If all checks passed, your bot should be working!")

