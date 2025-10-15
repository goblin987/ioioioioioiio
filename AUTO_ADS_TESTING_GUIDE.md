# Auto Ads System - Testing Guide

## 🧪 Complete Testing Checklist

This guide will help you test the newly implemented auto ads system end-to-end.

---

## Prerequisites

Before testing, ensure you have:

1. ✅ Bot running with no errors
2. ✅ PostgreSQL database connected
3. ✅ Telegram API credentials (api_id & api_hash from https://my.telegram.org)
4. ✅ At least one Telegram account for testing
5. ✅ Access to the admin panel

---

## Test 1: Database Tables Created

**What to verify:** All required tables exist with correct schema

### Steps:
1. Connect to your PostgreSQL database
2. Run these queries:

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name LIKE 'auto_ads%';

-- Expected output:
-- auto_ads_accounts
-- auto_ads_configs
-- auto_ads_campaigns

-- Check auto_ads_accounts schema
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'auto_ads_accounts';

-- Should include: api_id, api_hash columns

-- Check auto_ads_campaigns schema
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'auto_ads_campaigns';

-- Should include: user_id, config_id, interval_minutes, forwarding_mode, source_message_id
```

**Expected Result:** All tables exist with new columns added

---

## Test 2: Access Auto Ads Menu

**What to verify:** Menu loads without errors

### Steps:
1. Start your bot
2. Send `/admin` to the bot
3. Click "Marketing Tools" (or wherever auto ads is located)
4. Click "🚀 Auto Ads System"

**Expected Result:**
- Menu displays with options:
  - Manage Accounts
  - My Configs
  - My Campaigns
  - Bump Service
  - Settings
  - Help

**Check Logs:**
```
ℹ️ Telethon accounts will be loaded when first accessed
✅ Campaign executor services configured
```

---

## Test 3: Add Telegram Account

**What to verify:** Can add account with API credentials

### Steps:

#### Option A: Manual Login (Recommended)
1. In Auto Ads menu → Click "Manage Accounts"
2. Click "➕ Add Account"
3. Click "📝 Manual Setup (Phone + Code)"
4. Enter account details:
   - **Account Name**: "Test Account 1"
   - **Phone Number**: +1234567890
   - **API ID**: Your api_id from my.telegram.org
   - **API Hash**: Your api_hash from my.telegram.org
5. Click "Send Code"
6. Enter the code you receive via Telegram
7. If 2FA enabled, enter your password

#### Option B: Session File Upload
1. In Auto Ads menu → Click "Manage Accounts"
2. Click "➕ Add Account"
3. Click "📤 Upload Session File"
4. Upload your .session file
5. Provide API ID and API Hash

**Expected Result:**
- Account added successfully
- Shows in "Manage Accounts" list
- Database entry created

**Check Database:**
```sql
SELECT id, account_name, phone_number, is_active, 
       CASE WHEN api_id IS NOT NULL THEN 'YES' ELSE 'NO' END as has_api_id,
       CASE WHEN api_hash IS NOT NULL THEN 'YES' ELSE 'NO' END as has_api_hash,
       CASE WHEN session_string IS NOT NULL THEN 'YES' ELSE 'NO' END as has_session
FROM auto_ads_accounts;
```

**Check Logs:**
```
✅ Telethon client {account_id} created and connected
✅ Loaded account {account_id} (+1234567890)
```

---

## Test 4: Create Forwarding Config

**What to verify:** Can create source → target mapping

### Steps:
1. In Auto Ads menu → Click "My Configs"
2. Click "➕ Add Forwarding"
3. Select your account
4. Enter forwarding details:
   - **Config Name**: "Test Channel Forward"
   - **Source Chat**: @source_channel (or chat ID)
   - **Target Chat**: @target_channel (or chat ID)
5. Click "Save"

**Expected Result:**
- Config created successfully
- Shows in "My Configs" list

**Check Database:**
```sql
SELECT c.id, c.config_name, c.source_chat, c.target_chat, 
       a.account_name, c.is_active
FROM auto_ads_configs c
JOIN auto_ads_accounts a ON c.account_id = a.id;
```

**Note:** Make sure you have admin/posting rights in the target channel!

---

## Test 5: Create One-Time Scheduled Campaign

**What to verify:** Can create campaign with schedule

### Steps:
1. In Auto Ads menu → Click "My Campaigns"
2. Click "➕ Create Campaign"
3. Select your config
4. Enter campaign details:
   - **Campaign Name**: "Test Scheduled Post"
   - **Schedule Time**: 5 minutes from now
   - **Message/Source**: Provide message or source message ID
   - **Forwarding Mode**: "Forward" or "Copy"
5. Click "Create"

**Expected Result:**
- Campaign created successfully
- Shows in "My Campaigns" list
- Status: "Pending" or "Scheduled"

**Check Database:**
```sql
SELECT id, name, schedule_time, interval_minutes, 
       is_active, sent_count, last_sent,
       forwarding_mode
FROM auto_ads_campaigns;
```

**Expected:** `schedule_time` set, `interval_minutes` NULL, `sent_count` = 0

---

## Test 6: Test Campaign Execution (Manual)

**What to verify:** Campaign can be tested before scheduling

### Steps:
1. In "My Campaigns" → Select your campaign
2. Click "🧪 Test Campaign"
3. Enter test chat ID (your own chat or test channel)
4. Click "Send Test"

**Expected Result:**
- Message forwarded/sent to test chat
- Success message displayed
- No changes to campaign stats (it's just a test)

**Check Logs:**
```
✅ Forwarded message {message_id} from {source} to {target}
-- OR --
✅ Copied message {message_id} from {source} to {target}
-- OR --
✅ Sent message to {chat_id}
```

---

## Test 7: Wait for Scheduled Execution

**What to verify:** Scheduler executes campaigns automatically

### Steps:
1. Wait for the scheduled time
2. Monitor logs
3. Check target channel/chat

**Expected Result:**
- Campaign executes at scheduled time (within 60 seconds)
- Message appears in target channel
- Campaign stats updated

**Check Logs:**
```
🚀 BumpService scheduler started
⏰ Executing scheduled campaign {campaign_id}
✅ Executed campaign {campaign_id}
✅ Campaign {campaign_id} executed successfully via CampaignExecutor
```

**Check Database:**
```sql
SELECT id, name, sent_count, last_sent 
FROM auto_ads_campaigns 
WHERE id = {your_campaign_id};
```

**Expected:** `sent_count` = 1, `last_sent` updated

---

## Test 8: Create Recurring Bump Campaign

**What to verify:** Recurring bumps work

### Steps:
1. Create new campaign
2. Set:
   - **Campaign Name**: "Test Recurring Bump"
   - **Schedule Time**: Leave empty or set start time
   - **Interval Minutes**: 5 (bump every 5 minutes)
   - **Message**: Choose message to bump
3. Click "Create"

**Expected Result:**
- Campaign created
- First execution happens immediately or at schedule time
- Re-executes every 5 minutes

**Check Logs After 5 Minutes:**
```
⏰ Executing scheduled campaign {campaign_id}
✅ Executed campaign {campaign_id}
```

**Check Database:**
```sql
SELECT id, name, interval_minutes, sent_count, last_sent,
       EXTRACT(EPOCH FROM (NOW() - last_sent))/60 as minutes_since_last
FROM auto_ads_campaigns 
WHERE interval_minutes IS NOT NULL;
```

**Monitor:** `sent_count` should increment every 5 minutes

---

## Test 9: Campaign Performance Tracking

**What to verify:** Stats tracked correctly

### Steps:
1. In "My Campaigns" → Select campaign
2. Click "📊 View Stats"

**Expected Result:**
- Shows sent count
- Shows last execution time
- Shows campaign status (active/inactive)

**Check Database:**
```sql
SELECT 
    id,
    name,
    sent_count,
    last_sent,
    CASE 
        WHEN is_active THEN 'Active' 
        ELSE 'Inactive' 
    END as status,
    EXTRACT(EPOCH FROM (NOW() - last_sent))/60 as minutes_since_last
FROM auto_ads_campaigns
ORDER BY last_sent DESC NULLS LAST;
```

---

## Test 10: Edit/Delete Campaign

**What to verify:** CRUD operations work

### Steps:

#### Edit Campaign:
1. Select campaign → Click "✏️ Edit"
2. Change interval or schedule
3. Click "Save"

**Check Database:**
```sql
SELECT * FROM auto_ads_campaigns WHERE id = {campaign_id};
```

#### Toggle Active/Inactive:
1. Select campaign → Click "⏸️ Pause" or "▶️ Resume"

**Expected:** `is_active` changes

#### Delete Campaign:
1. Select campaign → Click "🗑️ Delete"
2. Confirm deletion

**Expected:** Campaign removed from database

```sql
SELECT * FROM auto_ads_campaigns WHERE id = {campaign_id};
-- Should return 0 rows
```

---

## Test 11: Multiple Accounts

**What to verify:** System supports multiple accounts

### Steps:
1. Add second account (repeat Test 3)
2. Create config for second account
3. Create campaign using second account's config
4. Verify both accounts work independently

**Expected Result:**
- Both accounts loaded and connected
- Campaigns from different accounts execute correctly

**Check Logs:**
```
✅ Loaded account 1 (+1234567890)
✅ Loaded account 2 (+0987654321)
✅ Loaded 2 out of 2 accounts
```

---

## Test 12: Forwarding Modes

**What to verify:** All 3 modes work

### Test Forward Mode:
1. Create campaign with `forwarding_mode='forward'`
2. Check target: Should show "Forwarded from {source}"

### Test Copy Mode:
1. Create campaign with `forwarding_mode='copy'`
2. Check target: No "Forwarded from" tag

### Test Custom Mode:
1. Create campaign with custom message text
2. Check target: Your custom message sent

---

## Test 13: Error Handling

**What to verify:** Graceful error handling

### Test Invalid Config:
1. Create campaign with invalid source/target chat
2. Try to execute

**Expected:** Error logged, campaign not marked as sent

### Test Disconnected Account:
1. Revoke account session from Telegram
2. Wait for next campaign execution

**Expected:** Error logged, campaign fails gracefully

**Check Logs:**
```
❌ Campaign {campaign_id} execution failed
Error executing campaign: ...
```

---

## Test 14: Scheduler Lifecycle

**What to verify:** Scheduler starts/stops correctly

### Steps:
1. Restart bot
2. Check logs for scheduler start
3. Stop bot
4. Check logs for cleanup

**Expected Logs:**
```
# On start:
🚀 BumpService scheduler started
✅ BumpService scheduler task created

# On stop:
🛑 BumpService scheduler stopped
🧹 BumpService cleaned up
```

---

## Common Issues & Solutions

### Issue: "TelethonManager not initialized"
**Solution:** Make sure TelethonManager is passed to BumpService during initialization

### Issue: "No client found for account X"
**Solution:** 
- Check account has valid `api_id`, `api_hash`, and `session_string`
- Check account `is_active = TRUE`
- Try manual account reload

### Issue: Campaigns not executing
**Solution:**
- Check scheduler is running (look for "🚀 BumpService scheduler started" in logs)
- Check campaign `is_active = TRUE`
- Check schedule_time or interval_minutes set correctly
- Verify database query in scheduler_loop

### Issue: "Session expired" or "Not authorized"
**Solution:**
- Re-login to account (delete and re-add)
- Generate new session string
- Check API credentials are correct

### Issue: Rate limit errors
**Solution:**
- Reduce campaign frequency
- Add delay between campaigns (already has 2s delay)
- Use different accounts for different channels

---

## Performance Testing

### Test High Volume:
1. Create 10+ campaigns
2. Set all to execute within 5 minutes
3. Monitor execution

**Expected:**
- All campaigns execute
- 2-second delay between each
- No crashes or data loss

### Test Long Running:
1. Create recurring campaign (every 10 minutes)
2. Let run for 24 hours
3. Check stability

**Expected:**
- Consistent execution
- No memory leaks
- Stats accurate

---

## Success Criteria

✅ All database tables created with correct schema  
✅ Can add account with API credentials  
✅ Can create forwarding configs  
✅ Can create scheduled campaigns  
✅ Can create recurring bump campaigns  
✅ Scheduler executes campaigns automatically  
✅ Statistics tracked correctly  
✅ All 3 forwarding modes work  
✅ Multiple accounts supported  
✅ Error handling works gracefully  
✅ Edit/delete operations work  
✅ Test campaign function works  
✅ Scheduler starts/stops correctly  

---

## Next Steps After Testing

If all tests pass:
1. ✅ Mark implementation as complete
2. 📝 Document any custom configurations needed
3. 🚀 Deploy to production
4. 📊 Monitor logs and performance
5. 🔧 Adjust intervals/delays as needed

If tests fail:
1. 📋 Note which test failed
2. 🔍 Check error logs
3. 🐛 Debug specific component
4. 🔄 Re-test after fix

---

## Support & Debugging

### Enable Debug Logging:
```python
logger.setLevel(logging.DEBUG)
```

### Useful Queries:
```sql
-- All active campaigns due now
SELECT * FROM auto_ads_campaigns
WHERE is_active = TRUE
AND (schedule_time <= NOW() OR interval_minutes IS NOT NULL);

-- Campaign execution history
SELECT id, name, sent_count, last_sent,
       NOW() - last_sent as time_since_last
FROM auto_ads_campaigns
ORDER BY last_sent DESC;

-- Accounts with clients loaded
SELECT a.*, 
       CASE WHEN session_string IS NOT NULL THEN 'YES' ELSE 'NO' END as has_session
FROM auto_ads_accounts a
WHERE is_active = TRUE;
```

---

**Good luck with testing! 🚀**

