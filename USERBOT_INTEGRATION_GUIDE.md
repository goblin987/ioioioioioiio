# 🤖 Userbot System Integration Guide

## ✅ FILES CREATED

All new files have been created and are ready to use:

1. **`userbot_database.py`** - PostgreSQL database operations (771 lines)
2. **`userbot_config.py`** - Configuration management (187 lines)
3. **`userbot_manager.py`** - Pyrogram client wrapper (447 lines)
4. **`product_delivery.py`** - Product delivery logic (365 lines)
5. **`userbot_admin.py`** - Admin interface handlers (613 lines)
6. **`requirements.txt`** - Updated with pyrogram and TgCrypto

## 🔧 REQUIRED INTEGRATIONS

You need to manually integrate the userbot system with these existing files:

### 1. **main.py** - Initialize Userbot System

Add these imports at the top:
```python
# Userbot system imports
try:
    from userbot_database import init_userbot_tables
    from userbot_manager import userbot_manager
    from userbot_config import userbot_config
    USERBOT_AVAILABLE = True
except ImportError:
    logger.warning("Userbot system not available")
    USERBOT_AVAILABLE = False
```

Add to your initialization function (usually `post_init` or similar):
```python
# Initialize userbot tables
if USERBOT_AVAILABLE:
    try:
        init_userbot_tables()
        logger.info("✅ Userbot tables initialized")
        
        # Initialize userbot if configured
        if userbot_config.is_configured() and userbot_config.is_enabled():
            await userbot_manager.initialize()
            logger.info("✅ Userbot initialized")
    except Exception as e:
        logger.error(f"❌ Userbot initialization failed: {e}")
```

Add to your shutdown function:
```python
# Shutdown userbot
if USERBOT_AVAILABLE and userbot_manager.is_connected:
    try:
        await userbot_manager.disconnect()
        logger.info("✅ Userbot disconnected")
    except Exception as e:
        logger.error(f"❌ Userbot shutdown error: {e}")
```

Register handlers in `KNOWN_HANDLERS`:
```python
# Userbot control handlers
"userbot_control": handle_userbot_control,
"userbot_setup_start": handle_userbot_setup_start,
"userbot_connect": handle_userbot_connect,
"userbot_disconnect": handle_userbot_disconnect,
"userbot_test": handle_userbot_test,
"userbot_settings": handle_userbot_settings,
"userbot_stats": handle_userbot_stats,
"userbot_reset_confirm": handle_userbot_reset_confirm,
"userbot_reset_confirmed": handle_userbot_reset_confirmed,
"userbot_toggle_enabled": handle_userbot_toggle_enabled,
"userbot_toggle_reconnect": handle_userbot_toggle_reconnect,
"userbot_toggle_notifications": handle_userbot_toggle_notifications,
```

Register message handlers in `STATE_HANDLERS`:
```python
'awaiting_userbot_api_id': handle_userbot_api_id_message,
'awaiting_userbot_api_hash': handle_userbot_api_hash_message,
'awaiting_userbot_phone': handle_userbot_phone_message,
'awaiting_userbot_verification_code': handle_userbot_verification_code_message,
```

Import the handlers:
```python
from userbot_admin import (
    handle_userbot_control,
    handle_userbot_setup_start,
    handle_userbot_connect,
    handle_userbot_disconnect,
    handle_userbot_test,
    handle_userbot_settings,
    handle_userbot_stats,
    handle_userbot_reset_confirm,
    handle_userbot_reset_confirmed,
    handle_userbot_toggle_enabled,
    handle_userbot_toggle_reconnect,
    handle_userbot_toggle_notifications,
    handle_userbot_api_id_message,
    handle_userbot_api_hash_message,
    handle_userbot_phone_message,
    handle_userbot_verification_code_message
)
```

### 2. **admin.py** - Add Userbot Control Button

In your main admin menu handler, add the userbot button:
```python
async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    # ... existing code ...
    
    keyboard = [
        # ... existing buttons ...
        [InlineKeyboardButton("🤖 Userbot Control", callback_data="userbot_control")],
        # ... more buttons ...
    ]
```

### 3. **payment.py** - Trigger Userbot Delivery

Find your purchase finalization function (after successful payment) and add:

```python
from product_delivery import deliver_product_via_userbot, deliver_basket_via_userbot
from userbot_config import userbot_config
from userbot_manager import userbot_manager

async def _finalize_purchase(user_id, product_data, order_id, context):
    # ... existing purchase finalization code ...
    
    # Send normal bot confirmation first
    await send_confirmation_message(user_id, order_id, context)
    
    # Try userbot delivery if enabled
    if userbot_config.is_enabled() and userbot_manager.is_connected:
        logger.info(f"🤖 Attempting userbot delivery for order {order_id}")
        
        result = await deliver_product_via_userbot(
            user_id=user_id,
            product_data=product_data,
            order_id=order_id,
            context=context
        )
        
        if result['success']:
            logger.info(f"✅ Userbot delivery successful for order {order_id}")
        elif result.get('fallback'):
            logger.warning(f"⚠️ Userbot delivery failed, using fallback for order {order_id}")
            # Your existing delivery method here
            await send_product_via_bot(user_id, product_data, context)
    else:
        # Userbot not enabled, use regular delivery
        await send_product_via_bot(user_id, product_data, context)
    
    # ... rest of finalization ...
```

For basket purchases:
```python
async def _finalize_basket_purchase(user_id, basket_items, total_amount, order_id, context):
    # ... existing code ...
    
    if userbot_config.is_enabled() and userbot_manager.is_connected:
        result = await deliver_basket_via_userbot(
            user_id=user_id,
            basket_items=basket_items,
            total_amount=total_amount,
            order_id=order_id,
            context=context
        )
        
        if result['success']:
            logger.info(f"✅ Basket delivered via userbot")
        elif result.get('fallback'):
            # Use regular bot delivery
            await send_basket_via_bot(user_id, basket_items, context)
    else:
        await send_basket_via_bot(user_id, basket_items, context)
```

## 📦 DEPLOYMENT STEPS

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize Database:**
   The tables will be created automatically on first run when you call `init_userbot_tables()`

3. **Setup Userbot:**
   - Go to `/admin` in your bot
   - Click "🤖 Userbot Control"
   - Follow the setup wizard
   - Enter API ID and Hash from https://my.telegram.org
   - Enter phone number and verification code
   - Userbot will connect automatically

4. **Test Delivery:**
   - After setup, click "🧪 Test" button
   - You should receive a test message from the userbot
   - If successful, the userbot is ready!

5. **Enable Delivery:**
   - Go to "⚙️ Settings"
   - Toggle "🟢 Enable Delivery"
   - Configure TTL, retries, etc.

## 🔒 SECURITY NOTES

- **Session Security:** Session strings are stored in PostgreSQL, ensure database is secure
- **API Credentials:** API ID and Hash are stored in database, not environment variables
- **Phone Privacy:** Verification codes are sent to admin via Telegram, not logged
- **Auto-Reconnect:** Userbot will automatically reconnect if disconnected (if enabled)

## 🧪 TESTING CHECKLIST

Before going live, test:
- [ ] Setup wizard completes successfully
- [ ] Phone verification works
- [ ] Session persists across bot restarts
- [ ] Test message sends successfully
- [ ] Product delivery works with TTL
- [ ] Media files send correctly (photos/videos)
- [ ] Fallback to regular delivery works if userbot fails
- [ ] Enable/disable toggle works
- [ ] Statistics track correctly
- [ ] Reset configuration works

## 📊 MONITORING

Check these regularly:
- **Connection Status:** Should show "✅ Connected"
- **Success Rate:** Should be >95%
- **Failed Deliveries:** Check error messages in statistics
- **Auto-Reconnect:** Verify it reconnects after disconnections

## 🐛 TROUBLESHOOTING

**Userbot won't connect:**
- Check API ID and Hash are correct
- Verify phone number is valid
- Check session wasn't invalidated
- Try resetting configuration and setting up again

**Deliveries failing:**
- Check userbot is connected
- Verify user hasn't blocked the userbot
- Check for FloodWait errors (rate limiting)
- Enable fallback delivery

**Session expired:**
- Reset configuration
- Run setup wizard again
- Enter new verification code

## 📝 NOTES

- **Separate Account Required:** Use a different Telegram account for userbot (NOT your bot account)
- **Rate Limits:** Telegram has rate limits, userbot respects them
- **Optional Feature:** Userbot is completely optional, bot works without it
- **Graceful Fallback:** If userbot fails, regular bot delivery takes over

## 🎉 DONE!

Your userbot system is now ready! The implementation is complete with:
- ✅ Full admin interface through bot
- ✅ Secure configuration storage
- ✅ Automatic failover
- ✅ Delivery statistics
- ✅ Self-destructing messages
- ✅ Complete error handling

Enjoy secure product delivery with self-destructing secret chats! 🔐

