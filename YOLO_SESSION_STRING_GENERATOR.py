"""
🚀 YOLO MODE: Telethon Session String Generator

Use this script to generate a session string offline, then paste it into the bot.
This bypasses the SMS verification issue.

INSTRUCTIONS:
1. Install Telethon: pip install telethon
2. Run this script: python YOLO_SESSION_STRING_GENERATOR.py
3. Enter your phone number when prompted
4. You'll receive the code on YOUR device (not via bot)
5. Enter the code
6. Copy the session string
7. In the bot, choose "Paste Session String (YOLO)" and paste it

"""

from telethon import TelegramClient
from telethon.sessions import StringSession

# Your API credentials
api_id = int(input("Enter API ID: ").strip())
api_hash = input("Enter API Hash: ").strip()
phone = input("Enter phone number (with country code, e.g. +254757022149): ").strip()

print("\n🔐 Connecting to Telegram...")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(f"📱 Sending verification code to {phone}...")
    
    # This will prompt for phone, code, and password (if 2FA)
    client.start(phone=phone)
    
    # Get the session string
    session_string = client.session.save()
    
    print("\n" + "="*80)
    print("✅ SUCCESS! Your session string is:")
    print("="*80)
    print(session_string)
    print("="*80)
    print("\n📋 Copy the string above and paste it into your bot!")
    print("🔑 In bot: Auto Ads → Add Account → Paste Session String (YOLO)")
    print("\n⚠️  KEEP THIS SECRET! Anyone with this string has full access to your Telegram account!")

