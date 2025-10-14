# 🐛 BOT SHOP DEBUGGING GUIDE

## 📊 Current Status: ✅ NO SYNTAX ERRORS

All Python files compile successfully. The bot should be running without syntax issues.

---

## 🔍 How to Debug with Cursor

### **1. Check Render Logs (Real-time)**
```bash
# In Cursor terminal:
curl -H "Authorization: Bearer YOUR_RENDER_API_KEY" \
  https://api.render.com/v1/services/YOUR_SERVICE_ID/logs
```

Or visit: https://dashboard.render.com → Your Service → Logs

---

### **2. Common Issues to Check**

#### **A. Database Connection Issues**
**Symptoms:**
- Users can't add to basket
- Products don't load
- "Error processing purchase"

**Debug Steps:**
1. Check `utils.py` line 1110-1129 (database connection)
2. Verify environment variables:
   ```
   DATABASE_URL
   POSTGRES_HOST
   POSTGRES_PORT
   POSTGRES_DB
   POSTGRES_USER
   POSTGRES_PASSWORD
   ```

**Quick Fix:**
```python
# Test database connection
python -c "from utils import get_db_connection; conn = get_db_connection(); print('✅ DB Connected!'); conn.close()"
```

---

#### **B. Product Delivery Issues**
**Symptoms:**
- Products not delivered after payment
- Userbot errors
- "Delivery failed"

**Debug Steps:**
1. Check `userbot_pool.py` line 25+ (UserbotPool class)
2. Check `product_delivery.py` for delivery logic
3. Verify userbot is connected:
   ```python
   # Check in Render logs for:
   "✅ Userbot handlers registered"
   "✅ Userbot connected"
   ```

**Files to Check:**
- `userbot_pool.py` - Main delivery logic
- `product_delivery.py` - Delivery handlers
- `case_opening_handlers.py` line 558-594 - Auto-delivery

---

#### **C. Payment Processing Issues**
**Symptoms:**
- Balance not deducted
- Purchase fails
- Items not removed from stock

**Debug Steps:**
1. Check `payment.py` line 870-1509 (`_finalize_purchase`)
2. Check `payment.py` line 1458+ (`process_purchase_with_balance`)
3. Look for errors in logs:
   ```
   "DB error deducting balance"
   "Failed to deduct balance"
   "Insufficient balance"
   ```

**Common Causes:**
- Race conditions (multiple purchases at once)
- Database locks
- Balance calculation errors

---

#### **D. Daily Rewards / Case Opening Issues**
**Symptoms:**
- "Daily rewards not working"
- Case opening crashes
- "Invalid case type"
- "List index out of range"

**Debug Steps:**
1. Check if tables exist:
   ```sql
   SELECT * FROM daily_reward_schedule LIMIT 1;
   SELECT * FROM case_settings LIMIT 1;
   SELECT * FROM user_points WHERE user_id = YOUR_USER_ID;
   ```

2. Check initialization in `main.py` line 2221-2255:
   ```
   "🎁 STARTING DAILY REWARDS INITIALIZATION"
   "✅ Daily rewards system initialized"
   ```

3. Check `daily_rewards_system.py` for errors
4. Check `case_opening_handlers.py` for animation issues

**Recent Fixes:**
- ✅ Fixed `district_id` → `district` column issue
- ✅ Fixed `product_name` → `name` column issue
- ✅ Fixed case creation bugs
- ✅ Fixed city selection errors

---

#### **E. Running Ads Issues**
**Symptoms:**
- Button doesn't show custom text
- Admin can't change text
- Button does nothing when clicked

**Debug Steps:**
1. Check if `marquee_settings` table exists:
   ```sql
   SELECT * FROM marquee_settings LIMIT 1;
   ```

2. Check `marquee_text_system.py` line 21+ (init_marquee_tables)
3. Check `running_ads_display.py` (should do nothing on click)

**Expected Behavior:**
- Button shows custom text (e.g., "🔥 HOT DEALS!")
- Clicking does nothing (static display)
- Admin can change text via Running Ads Management

---

## 🚨 Error Handler Locations

### **Main Error Handler**
- **File**: `main.py`
- **Line**: 1481-1538
- **Function**: `error_handler()`

**Handles:**
- `BadRequest` - Telegram API errors
- `NetworkError` - Connection issues
- `Forbidden` - Bot blocked by user
- `RetryAfter` - Rate limiting
- `NameError` - Missing variables
- `AttributeError` - Missing attributes
- Database errors

---

### **Rate Limiting System**
- **File**: `utils.py`
- **Line**: 1993-2096
- **Class**: `TelegramRateLimiter`

**Prevents:**
- "Too Many Requests" errors
- Message flooding
- API rate limit violations

**Limits:**
- 25 messages/second globally
- 16 messages/second per chat

---

## 📝 Logging Levels

### **Current Setup**
```python
# utils.py line 29
logging.basicConfig(level=logging.INFO)
```

### **Change to DEBUG for More Info**
```python
logging.basicConfig(level=logging.DEBUG)
```

### **Key Log Messages to Watch**

#### **✅ Success Messages:**
```
"✅ Daily rewards system initialized"
"✅ Userbot handlers registered"
"✅ Product delivery initiated"
"✅ DELIVERY CONFIRMED!"
"✅ Case rewards system initialized"
```

#### **❌ Error Messages:**
```
"❌ CRITICAL ERROR connecting to"
"❌ Failed to initiate product delivery"
"❌ Error processing delivery"
"❌ No products available"
"❌ Database error"
```

#### **⚠️ Warning Messages:**
```
"⚠️ Userbot not connected"
"⚠️ Rate limit hit"
"⚠️ Insufficient balance"
"⚠️ Product not available"
```

---

## 🔧 Quick Fixes

### **1. Restart Bot**
```bash
# Trigger Render redeploy
git commit --allow-empty -m "Restart bot"
git push origin main
```

### **2. Clear User State**
```python
# In admin panel or database:
DELETE FROM user_data WHERE user_id = YOUR_USER_ID;
```

### **3. Reset Daily Rewards**
```sql
DELETE FROM daily_logins WHERE user_id = YOUR_USER_ID;
DELETE FROM user_points WHERE user_id = YOUR_USER_ID;
```

### **4. Fix Stuck Baskets**
```sql
UPDATE products SET reserved = 0 WHERE reserved > 0;
```

### **5. Check Database Tables**
```sql
-- List all tables
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Check if critical tables exist
SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'products');
SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'daily_reward_schedule');
SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'case_settings');
```

---

## 🎯 Testing Checklist

### **User Flow Testing:**
- [ ] User can /start bot
- [ ] User can select city
- [ ] User can select district
- [ ] User can view products
- [ ] User can add to basket
- [ ] User can view basket
- [ ] User can pay with balance
- [ ] Product is delivered after payment
- [ ] Daily rewards work
- [ ] Case opening works
- [ ] Running Ads button appears

### **Admin Flow Testing:**
- [ ] Admin can access admin panel
- [ ] Admin can add products
- [ ] Admin can view stock
- [ ] Admin can manage users
- [ ] Admin can configure daily rewards
- [ ] Admin can manage cases
- [ ] Admin can change running ads text
- [ ] Admin can edit bot UI

---

## 📞 Support

If you encounter persistent issues:

1. **Check Render Logs** (last 100 lines)
2. **Check Database** (verify tables exist)
3. **Check Environment Variables** (all set correctly)
4. **Check Userbot Connection** (if using delivery)
5. **Review Recent Changes** (git log)

---

## 🔥 Most Common Bugs (Fixed)

### **✅ FIXED:**
1. ~~`product_name` column doesn't exist~~ → Changed to `name`
2. ~~`district_id` column doesn't exist~~ → Changed to `district`
3. ~~Case creation fails~~ → Fixed text input handlers
4. ~~City selection crashes~~ → Fixed SQL joins
5. ~~Daily rewards table missing~~ → Added initialization
6. ~~Animation too slow~~ → Reduced frames
7. ~~Message not modified error~~ → Added deduplication
8. ~~Cursor already closed~~ → Fixed query order

### **⚠️ WATCH OUT FOR:**
1. Database connection pool exhaustion
2. Rate limiting (too many messages)
3. Userbot disconnections
4. Media file size limits
5. Telegram API changes

---

## 🎓 Cursor Debugging Tips

### **1. Use Cursor's AI Chat**
Ask: "Why is [feature] not working?" with error logs

### **2. Use Cursor's Code Search**
- Cmd/Ctrl + Shift + F to search codebase
- Look for error messages in logs

### **3. Use Cursor's Terminal**
- Run Python scripts directly
- Test database connections
- Check file permissions

### **4. Use Cursor's Git Integration**
- View recent changes
- Revert problematic commits
- Compare working vs broken code

---

## 📊 Performance Monitoring

### **Key Metrics to Watch:**
- Response time (< 1 second ideal)
- Database query time (< 100ms ideal)
- Memory usage (< 512MB on Render free tier)
- Error rate (< 1% ideal)

### **Render Dashboard:**
- CPU usage
- Memory usage
- Request count
- Error logs

---

## 🚀 Optimization Tips

1. **Database Indexes** - Add indexes on frequently queried columns
2. **Connection Pooling** - Reuse database connections
3. **Caching** - Cache product lists, user data
4. **Async Operations** - Use async for I/O operations
5. **Rate Limiting** - Already implemented ✅

---

**Last Updated:** 2025-10-14  
**Bot Version:** Production  
**Status:** ✅ All systems operational

