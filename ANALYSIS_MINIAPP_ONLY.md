# Issue Analysis: Mini App Only Mode & Edit Welcome Text

## Date: 2025-12-07

---

## ISSUE 1: "Switch to Mini App Only" Button Doesn't Work

### What Should Happen:
1. Admin clicks "📱 Switch to Mini App Only" in Bot UI Management
2. Setting `ui_mode = "miniapp"` is saved to database
3. When regular users send `/start`:
   - Old "🛍️ Shop" button should be HIDDEN
   - Only "🌐 Open Shop App" (Mini App) button shows
   - Optional: Different welcome text for Mini App mode

### What Actually Happens:
1. ✅ Button exists in admin menu (line 909 in admin.py)
2. ✅ Handler registered: `toggle_ui_mode` → `handle_toggle_ui_mode` (line 834 in main.py)
3. ✅ Setting is saved to database (line 1029 in admin.py)
4. ❌ **BUG**: Setting is NEVER checked in user start menu!
5. ❌ Result: Both buttons still show regardless of setting

### Root Cause:
**File:** `user.py` - `_build_start_menu_content()` function

The menu builder ALWAYS creates both buttons:
```python
default_keyboard = [
    [InlineKeyboardButton(text="🌐 Open Shop App", web_app=WebAppInfo(url=webapp_url))],
    [InlineKeyboardButton(f"{EMOJI_SHOP} {shop_button_text}", callback_data="shop")],  # ← Always added!
]
```

It never checks `get_bot_setting("ui_mode")` to conditionally hide the shop button.

### Fix Required:

**Location:** `user.py` lines 220-224

**Current Code:**
```python
webapp_url = f"{WEBHOOK_URL.rstrip('/')}/webapp_fresh/app.html?v=3.0&t={int(time.time())}"
default_keyboard = [
    [InlineKeyboardButton(text="🌐 Open Shop App", web_app=WebAppInfo(url=webapp_url))],
    [InlineKeyboardButton(f"{EMOJI_SHOP} {shop_button_text}", callback_data="shop")],
]
```

**Fixed Code:**
```python
from utils import get_bot_setting

webapp_url = f"{WEBHOOK_URL.rstrip('/')}/webapp_fresh/app.html?v=3.0&t={int(time.time())}"
ui_mode = get_bot_setting("ui_mode", "bot")  # Default to "bot" if not set

default_keyboard = [
    [InlineKeyboardButton(text="🌐 Open Shop App", web_app=WebAppInfo(url=webapp_url))],
]

# Only add old Shop button if ui_mode is "bot"
if ui_mode == "bot":
    default_keyboard.append([InlineKeyboardButton(f"{EMOJI_SHOP} {shop_button_text}", callback_data="shop")])
```

---

## ISSUE 2: "Edit Welcome Text" Doesn't Work

### What Should Happen:
1. Admin clicks "✏️ Edit Welcome Text"
2. Bot prompts: "Send new welcome text"
3. Admin sends text
4. Text is saved to database as `miniapp_welcome_text`
5. When users send `/start`, the custom text shows

### What Actually Happens:
1. ✅ Button exists (line 912 in admin.py)
2. ✅ Handler registered: `edit_miniapp_text_start` (line 835 in main.py)
3. ✅ State set to `awaiting_miniapp_text` (line 932 in admin.py)
4. ✅ Save handler exists: `handle_admin_save_miniapp_text` (line 943 in admin.py)
5. ❌ **BUG #1**: State handler NOT registered in main.py!
6. ❌ **BUG #2**: Custom text never used in start menu!

### Root Causes:

#### Bug 2A: Missing State Handler Registration
**File:** `main.py` - `STATE_HANDLERS` dict

The state `awaiting_miniapp_text` is NOT in STATE_HANDLERS, so when admin sends text, it's ignored.

**Fix Required:**
```python
STATE_HANDLERS = {
    # ... existing handlers ...
    'awaiting_miniapp_text': admin.handle_admin_save_miniapp_text,  # ← ADD THIS
    'awaiting_miniapp_btn': admin.handle_admin_save_miniapp_btn,    # ← ADD THIS TOO
    # ...
}
```

#### Bug 2B: Custom Welcome Text Never Used
**File:** `user.py` - `_build_start_menu_content()` function

The welcome message is built from template but never checks for custom `miniapp_welcome_text` setting.

**Current Code (around line 180):**
```python
welcome_msg = lang_data.get("welcome", "Welcome, {username}!").format(username=username)
```

**Fixed Code:**
```python
from utils import get_bot_setting

# Check if Mini App mode and custom text exists
ui_mode = get_bot_setting("ui_mode", "bot")
custom_miniapp_text = get_bot_setting("miniapp_welcome_text", None)

if ui_mode == "miniapp" and custom_miniapp_text:
    # Use custom Mini App welcome text
    welcome_msg = custom_miniapp_text.format(username=username)
else:
    # Use default welcome from language file
    welcome_msg = lang_data.get("welcome", "Welcome, {username}!").format(username=username)
```

---

## ISSUE 3: Edit Button Text (Likely Same Issue)

### Handler Exists:
- `edit_miniapp_btn_start` (line 913 callback)
- State: `awaiting_miniapp_btn`
- Save handler probably exists but not registered

### Same Fixes Needed:
1. Register state handler in main.py
2. Use the saved button text in menu builder

---

## COMPLETE FIX SUMMARY

### File 1: `user.py` - _build_start_menu_content()

**Line ~217-224: Add UI mode check**
```python
from utils import get_bot_setting

# ... existing code ...

# Check UI mode setting
ui_mode = get_bot_setting("ui_mode", "bot")
custom_welcome = get_bot_setting("miniapp_welcome_text", None)

# Build welcome message
if ui_mode == "miniapp" and custom_welcome:
    welcome_msg = custom_welcome.format(username=username)
else:
    welcome_msg = lang_data.get("welcome", "Welcome, {username}!").format(username=username)

# ... later in function ...

# Build keyboard with conditional shop button
webapp_url = f"{WEBHOOK_URL.rstrip('/')}/webapp_fresh/app.html?v=3.0&t={int(time.time())}"
default_keyboard = [
    [InlineKeyboardButton(text="🌐 Open Shop App", web_app=WebAppInfo(url=webapp_url))],
]

# Only show old Shop button if not in Mini App Only mode
if ui_mode == "bot":
    default_keyboard.append([InlineKeyboardButton(f"{EMOJI_SHOP} {shop_button_text}", callback_data="shop")])
```

### File 2: `main.py` - STATE_HANDLERS

**Add missing state handlers:**
```python
STATE_HANDLERS = {
    # ... existing handlers ...
    
    # Bot UI Management States
    'awaiting_miniapp_text': admin.handle_admin_save_miniapp_text,
    'awaiting_miniapp_btn': admin.handle_admin_save_miniapp_btn,
    
    # ... rest of handlers ...
}
```

### File 3: `admin.py` - Verify button text handler exists

Check if `handle_admin_save_miniapp_btn` exists. If not, create it similar to text handler.

---

## TESTING CHECKLIST

After fixes are applied:

### Test 1: Switch to Mini App Only
1. ✅ Go to Admin → Bot UI Management
2. ✅ Click "📱 Switch to Mini App Only"
3. ✅ Should see confirmation alert
4. ✅ Send `/start` as regular user
5. ✅ Should see ONLY "🌐 Open Shop App" button
6. ✅ Should NOT see "🛍️ Shop" button
7. ✅ Mini App should open when clicked

### Test 2: Edit Welcome Text  
1. ✅ Click "✏️ Edit Welcome Text"
2. ✅ Should see prompt to send text
3. ✅ Send: "Welcome {username}! Use our Mini App below! 🚀"
4. ✅ Should see success message
5. ✅ Send `/start` as regular user
6. ✅ Should see custom welcome text with username filled in

### Test 3: Switch Back to Bot UI
1. ✅ Click "🤖 Switch to Bot UI"
2. ✅ Send `/start` as regular user
3. ✅ Should see BOTH "🌐 Open Shop App" AND "🛍️ Shop" buttons
4. ✅ Should see default welcome text (not custom)

### Test 4: Edit Button Text
1. ✅ Click "🔘 Edit Button Text"
2. ✅ Should be able to edit button labels
3. ✅ Changes should reflect in start menu

---

## IMPLEMENTATION PLAN

1. First fix username issue (wait for Render deployment)
2. After username is confirmed working:
3. Implement Mini App Only fixes in user.py
4. Add state handlers in main.py
5. Test thoroughly in admin menu
6. Commit with descriptive message
7. Push ONCE after testing

---

**Status:** READY TO IMPLEMENT AFTER USERNAME FIX IS CONFIRMED

