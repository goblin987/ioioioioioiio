# Auto Ads System - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

Your auto ads system is now **fully functional**! Here's how to use it.

---

## What You Can Do Now

✅ **Message Forwarding** - Auto-forward messages from one channel to many others  
✅ **Scheduled Posts** - Post ads at specific times  
✅ **Recurring Bumps** - Repost messages every X minutes/hours  
✅ **Multi-Account** - Use multiple Telegram accounts  
✅ **Smart Modes** - Forward (with tag), Copy (no tag), or Custom messages  

---

## Prerequisites

Before you start, get your Telegram API credentials:

1. Go to https://my.telegram.org/auth
2. Login with your phone number
3. Click "API development tools"
4. Create a new application
5. Save your `api_id` and `api_hash`

**Example:**
```
api_id: 12345678
api_hash: abcdef1234567890abcdef1234567890
```

---

## Step 1: Add Your First Account

1. Open your bot and send `/admin`
2. Navigate to: **Marketing Tools** → **🚀 Auto Ads System**
3. Click **Manage Accounts** → **➕ Add Account**
4. Click **📝 Manual Setup**
5. Enter:
   - Account Name: "My Main Account"
   - Phone: +1234567890 (with country code)
   - API ID: Your `api_id`
   - API Hash: Your `api_hash`
6. Click **Send Code**
7. Enter the code you receive from Telegram
8. If you have 2FA, enter your password

**Done!** Your account is now connected.

---

## Step 2: Create a Forwarding Config

1. Go back to **Auto Ads System** → **My Configs**
2. Click **➕ Add Forwarding**
3. Select your account
4. Enter:
   - Config Name: "Channel A to Channel B"
   - Source Chat: `@channel_a` or `-100123456789`
   - Target Chat: `@channel_b` or `-100987654321`
5. Click **Save**

**Tips:**
- Source can be: channel username (@channel), channel ID (-100xxx), or group ID
- Target must be a channel/group where your account has posting rights
- You can create multiple configs for different channel pairs

---

## Step 3: Create Your First Campaign

### Option A: One-Time Scheduled Post

1. Go to **My Campaigns** → **➕ Create Campaign**
2. Select your config
3. Enter:
   - Campaign Name: "New Product Launch"
   - Schedule Time: Select date/time (e.g., tomorrow at 2 PM)
   - Forwarding Mode: Choose "Forward" or "Copy"
   - Source Message: Enter message ID from source channel
4. Click **Create**

**Result:** Message will be forwarded at the scheduled time.

---

### Option B: Recurring Bump (Auto-Repost)

1. Go to **My Campaigns** → **➕ Create Campaign**
2. Select your config
3. Enter:
   - Campaign Name: "Hourly Product Bump"
   - Interval Minutes: `60` (repost every hour)
   - Forwarding Mode: "Copy" (to avoid "Forwarded from" tag)
   - Source Message: Enter message ID
4. Click **Create**

**Result:** Message will be reposted every hour automatically!

---

## Understanding Forwarding Modes

### 🔗 Forward Mode
- Uses Telegram's native forwarding
- Shows "Forwarded from [Source]" tag
- Best for: Sharing news, announcements

### 📋 Copy Mode
- Copies the message and sends as new
- No "Forwarded from" tag
- Best for: Looking like original content

### ✍️ Custom Mode
- Send your own custom message
- Write text directly in campaign
- Best for: Ads, promotions with your own text

---

## How Message IDs Work

Every Telegram message has an ID. To get it:

### Method 1: Desktop/Web
1. Right-click message in channel
2. Click "Copy Message Link"
3. Link looks like: `https://t.me/channel_name/12345`
4. The number at the end (12345) is the message ID

### Method 2: Bot
1. Forward message to any bot that shows IDs
2. Or use your own bot with message.message_id

---

## Example Use Cases

### 📢 Use Case 1: News Distribution
**Goal:** Forward news from main channel to 5 regional channels

**Setup:**
1. Add account with access to all channels
2. Create 5 configs (main → region1, main → region2, etc.)
3. Create campaign with interval: 10 minutes
4. Set mode: Forward

**Result:** Latest news from main channel reposted to all regions every 10 minutes

---

### 🛍️ Use Case 2: Product Promotions
**Goal:** Post product ad every 2 hours in multiple groups

**Setup:**
1. Add account
2. Create configs for each group
3. Create recurring campaign: interval 120 minutes
4. Mode: Copy (no forwarded tag)
5. Source: Your best-performing ad message

**Result:** Ad appears fresh (not forwarded) every 2 hours in all groups

---

### ⏰ Use Case 3: Scheduled Announcements
**Goal:** Post announcement at specific time tomorrow

**Setup:**
1. Add account
2. Create config for target channel
3. Create campaign with schedule: Tomorrow 10:00 AM
4. Mode: Custom message

**Result:** Announcement posted exactly at scheduled time

---

## Monitoring & Management

### View Campaign Stats
1. Go to **My Campaigns**
2. Click on any campaign
3. Click **📊 View Stats**

**You'll see:**
- Total sends
- Last execution time
- Status (active/paused)
- Next scheduled time

### Pause/Resume Campaign
1. Select campaign
2. Click **⏸️ Pause** or **▶️ Resume**

### Edit Campaign
1. Select campaign
2. Click **✏️ Edit**
3. Modify interval, schedule, or message
4. Click **Save**

### Delete Campaign
1. Select campaign
2. Click **🗑️ Delete**
3. Confirm

---

## Testing Before Going Live

### Test Any Campaign
1. Select your campaign
2. Click **🧪 Test Campaign**
3. Enter your own chat ID (e.g., your "Saved Messages")
4. Click **Send Test**

**Result:** Message sent to test chat only, stats not affected

---

## Common Scenarios

### Scenario 1: Channel Cross-Posting
**Want:** Post same content to 3 channels simultaneously

**Solution:**
1. Create 3 separate configs (same source, different targets)
2. Create 3 campaigns with same schedule
3. All post at same time

---

### Scenario 2: Staggered Posting
**Want:** Post to channels with 5-minute gaps

**Solution:**
1. Campaign 1: Schedule at 10:00 AM
2. Campaign 2: Schedule at 10:05 AM
3. Campaign 3: Schedule at 10:10 AM

---

### Scenario 3: 24/7 Auto-Reposting
**Want:** Keep bumping message forever

**Solution:**
1. Create campaign with interval: 180 (every 3 hours)
2. Leave it active
3. System automatically reposts indefinitely

---

## Pro Tips

### 💡 Tip 1: Use Copy Mode for Ads
Copy mode makes content look original, not forwarded. Better engagement!

### 💡 Tip 2: Test First
Always use the Test function before creating recurring campaigns.

### 💡 Tip 3: Respect Rate Limits
Telegram limits how fast you can post. Keep intervals ≥5 minutes for safety.

### 💡 Tip 4: Multiple Accounts
Use different accounts for different niches to avoid restrictions.

### 💡 Tip 5: Monitor Logs
Check bot logs for errors like "Rate limit" or "Permission denied".

---

## Troubleshooting

### ❌ "Failed to load account"
**Cause:** Wrong API credentials or expired session  
**Fix:** Re-add account with correct API ID/Hash

### ❌ "Permission denied" when forwarding
**Cause:** Account doesn't have posting rights  
**Fix:** Make account admin in target channel

### ❌ Campaign not executing
**Cause:** Schedule time not set or campaign paused  
**Fix:** Check schedule, ensure campaign is active

### ❌ "Rate limit exceeded"
**Cause:** Posting too fast  
**Fix:** Increase interval between campaigns

---

## Safety & Best Practices

### ✅ DO:
- Test campaigns before going live
- Use reasonable intervals (≥10 minutes)
- Get permission from channel owners
- Keep API credentials secure
- Monitor for Telegram restrictions

### ❌ DON'T:
- Spam channels every few seconds
- Post to channels without permission
- Share your API credentials
- Use the same message repeatedly in short time
- Exceed Telegram's rate limits

---

## What Happens Automatically

### On Bot Start:
1. Database tables created/updated
2. All active accounts loaded and connected
3. Scheduler starts running
4. Checks for due campaigns every 60 seconds

### Every 60 Seconds:
1. Scheduler checks database
2. Finds campaigns due for execution
3. Executes them via Telethon
4. Updates statistics
5. Waits 60 seconds, repeats

### When Campaign Executes:
1. Gets account and config from database
2. Connects via Telethon client
3. Forwards/copies/sends message
4. Updates sent_count and last_sent
5. Logs success/failure

---

## Architecture Overview

```
User creates campaign
       ↓
Stored in database (auto_ads_campaigns)
       ↓
BumpService scheduler checks every 60s
       ↓
Finds due campaigns
       ↓
Uses TelethonManager to send via Telethon
       ↓
Message forwarded/copied to target
       ↓
Stats updated in database
       ↓
Repeats if recurring (interval set)
```

---

## Need More Help?

- 📖 **Full Documentation:** See `AUTO_ADS_IMPLEMENTATION_SUMMARY.md`
- 🧪 **Testing Guide:** See `AUTO_ADS_TESTING_GUIDE.md`
- 🐛 **Known Issues:** See `AUTO_ADS_KNOWN_ISSUES.md`
- 📝 **Code:** Check `auto_ads_system.py`

---

## Ready to Start!

You're all set! Here's your first mission:

1. ✅ Get API credentials from https://my.telegram.org
2. ✅ Add your first account
3. ✅ Create a test config
4. ✅ Create a test campaign
5. ✅ Watch it execute automatically!

**Welcome to automated Telegram marketing! 🚀**

