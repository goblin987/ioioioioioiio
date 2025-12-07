# Critical Fixes for Mini App

## Issue 1: Username Display (user_662295169)

**Location**: Wherever profile data is rendered (search for "Welcome" in your HTML)

**Fix**: Replace username logic with:
```javascript
const user = tg.initDataUnsafe?.user;
const displayName = user?.first_name || user?.username || user?.last_name || `User_${user?.id || 'Unknown'}`;
```

## Issue 2: Balance Not Updating After Refill

**Location**: `pollPayment()` function (already partially fixed)

**Add this function after pollPayment**:
```javascript
async function loadUserBalance() {
    try {
        const user = tg.initDataUnsafe?.user;
        const userId = user ? user.id : 0;
        
        const response = await fetch(`/webapp_fresh/api/user_balance?user_id=${userId}`);
        const data = await response.json();
        
        if(data.balance !== undefined) {
            // Update balance display wherever it appears
            const balanceEl = document.querySelector('[class*="balance"]') || 
                             document.getElementById('user-balance');
            if(balanceEl) {
                balanceEl.innerText = `€${parseFloat(data.balance).toFixed(2)}`;
            }
            console.log('Balance updated:', data.balance);
        }
    } catch(e) {
        console.error('Error loading balance:', e);
    }
}
```

## Issue 3: Reseller Management by Username

**File**: `admin.py` or `reseller_management.py`

**Problem**: Admin tries to add resellers by @username but system expects user_id

**Fix**: Add username lookup before reseller creation:
```python
# In reseller add function
if username.startswith('@'):
    username = username[1:]  # Remove @

# Look up user_id from username
c.execute("SELECT user_id FROM users WHERE username = %s", (username,))
result = c.fetchone()

if not result:
    return {"error": f"User @{username} not found in database. They must interact with the bot first."}

user_id = result['user_id']
# Continue with reseller creation using user_id
```

## Issue 4: Cart UX Improvements

**Add loading states to addToBasket**:
```javascript
async function addToBasket(ids, name, price, e) {
    // Show loading
    if(e && e.target) {
        const btn = e.target.closest('button') || e.target;
        btn.disabled = true;
        btn.style.opacity = '0.5';
        btn.innerText = '...';
    }
    
    // ... existing code ...
    
    // Success feedback
    if(window.Telegram?.WebApp?.HapticFeedback) {
        Telegram.WebApp.HapticFeedback.impactOccurred('medium');
    }
    
    // Restore button
    if(e && e.target) {
        const btn = e.target.closest('button') || e.target;
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.innerText = 'ADD';
    }
}
```

## Issue 5: Remove From Basket Glitches

**Add smooth remove animation**:
```javascript
async function removeFromBasket(index) {
    const item = basket[index];
    if(!item) return;
    
    // Haptic feedback
    if(window.Telegram?.WebApp?.HapticFeedback) {
        Telegram.WebApp.HapticFeedback.impactOccurred('light');
    }
    
    // Find and animate the cart item
    const cartItems = document.querySelectorAll('.cart-item');
    if(cartItems[index]) {
        cartItems[index].style.transition = 'all 0.3s ease';
        cartItems[index].style.opacity = '0';
        cartItems[index].style.transform = 'translateX(-100%)';
        
        await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    // ... existing API call code ...
}
```

## Testing Checklist

- [ ] Username shows first_name or username (not user_id)
- [ ] Balance updates immediately after refill
- [ ] Reseller can be added by @username
- [ ] Cart add shows loading state
- [ ] Cart remove has smooth animation
- [ ] Haptic feedback works on cart actions

## Deploy Instructions

1. Apply fixes to `webapp_fresh/app.html`
2. Apply reseller fix to admin/reseller management code
3. Test each feature
4. Commit and push
5. Wait 2min for Render deployment
6. Clear browser cache and test

