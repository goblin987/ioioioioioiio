"""
TgCF Pro - Configuration Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Enterprise configuration management with environment variable validation,
security features, and professional deployment settings.

Features:
- Secure environment variable handling
- Configuration validation and error reporting
- Professional deployment configuration
- Enterprise security settings

Author: TgCF Pro Team
License: MIT
Version: 1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Bot Owner Configuration (single user mode)
    OWNER_USER_ID = os.getenv('OWNER_USER_ID')  # Your Telegram user ID (optional)
    
    # Storage Channel Configuration (for persistent media storage)
    STORAGE_CHANNEL_ID = os.getenv('STORAGE_CHANNEL_ID')  # Private channel for storing media files
    
    # Web Interface Configuration
    PASSWORD = os.getenv('PASSWORD', 'hocus pocus qwerty utopia')
    WEB_PORT = int(os.getenv('WEB_PORT', 5000))
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL')
    
# PostgreSQL Configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'shop_db')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
POSTGRES_URL = os.getenv('DATABASE_URL', f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}')

# Persistent Storage Configuration
PERSISTENT_DISK_PATH = '/mnt/data'  # Render persistent disk mount point (same as main bot)

# Environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# Forwarding Configuration
MAX_MESSAGES_PER_BATCH = 100
DELAY_BETWEEN_MESSAGES = 0.1

# Error Handling Configuration - YOLO MODE OPTIMIZED
MAX_RETRY_ATTEMPTS = 5  # More aggressive retries
RETRY_DELAY_BASE = 1.5  # Faster retry intervals
CLIENT_VALIDATION_TIMEOUT = 15  # Faster validation
CONNECTION_TIMEOUT = 30  # Faster timeouts

# Session Management - YOLO MODE
SESSION_VALIDATION_INTERVAL = 120  # 2 minutes - more frequent validation
AUTO_RECONNECT_ENABLED = True
AGGRESSIVE_MODE = True  # YOLO MODE FLAG

class Config:
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required_vars = ['BOT_TOKEN']
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True