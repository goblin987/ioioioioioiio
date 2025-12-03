#!/usr/bin/env python3
"""
Project Sanitization Script
Removes all identifiable information from the codebase for commercial distribution.
"""

import os
import re
import glob

# Files to delete (contain debug/personal info)
FILES_TO_DELETE = [
    "AUTO_ADS_FIXES_SUMMARY.md",
    "AUTO_ADS_IMPLEMENTATION_SUMMARY.md",
    "AUTO_ADS_KNOWN_ISSUES.md",
    "AUTO_ADS_QUICKSTART.md",
    "AUTO_ADS_TESTING_GUIDE.md",
    "CASE_OPENING_FIXES_LOG.txt",
    "DAILY_REWARDS_CUSTOMIZATION_SUMMARY.md",
    "DAILY_REWARDS_GUIDE.md",
    "DEBUGGING_GUIDE.md",
    "MINIAPP_PROGRESS.md",
    "RATE_LIMITING_SYSTEM.md",
    "SECURITY_AUDIT_RESULTS.md",
    "SECURITY_SUMMARY_FOR_OWNER.md",
    "SELLER_CUSTOMIZATION_GUIDE.md",
    "TESTING_GUIDE_DAILY_REWARDS.md",
]

# Patterns to remove/replace in code files
SANITIZE_PATTERNS = [
    (r'Author:\s*.*', 'Author: BotShop Development Team'),
    (r'TgCF Pro Team.*', 'BotShop Development Team'),
    (r'goblin987', 'bot-developer'),
    (r'goblingoblinu@gmail\.com', 'support@example.com'),
    (r'your-email@example\.com', 'support@example.com'),
]

def sanitize_file(filepath):
    """Remove identifiable information from a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        for pattern, replacement in SANITIZE_PATTERNS:
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Sanitized: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"❌ Error sanitizing {filepath}: {e}")
        return False

def main():
    print("🔒 Starting Project Sanitization...")
    print("=" * 60)
    
    # Delete documentation files
    deleted_count = 0
    for filename in FILES_TO_DELETE:
        if os.path.exists(filename):
            os.remove(filename)
            print(f"🗑️  Deleted: {filename}")
            deleted_count += 1
    
    # Sanitize Python files
    python_files = glob.glob("*.py")
    sanitized_count = 0
    for filepath in python_files:
        if filepath == "sanitize_project.py":
            continue
        if sanitize_file(filepath):
            sanitized_count += 1
    
    # Sanitize markdown files (remaining ones)
    md_files = glob.glob("*.md")
    for filepath in md_files:
        if sanitize_file(filepath):
            sanitized_count += 1
    
    print("=" * 60)
    print(f"✅ Sanitization Complete!")
    print(f"   - Deleted: {deleted_count} files")
    print(f"   - Sanitized: {sanitized_count} files")
    print("\n⚠️  NEXT STEP: Git history sanitization")
    print("   Run: git filter-branch --env-filter 'SANITIZE_COMMITS' --tag-name-filter cat -- --branches --tags")

if __name__ == "__main__":
    main()

