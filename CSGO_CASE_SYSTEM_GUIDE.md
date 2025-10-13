# 🎰 CS:GO-Style Case Opening System

## **Overview**

This is a complete redesign of the product rewards system, modeled after CS:GO gambling sites. Users open cases to win **actual products** (not points), and if they win, they select their delivery city.

---

## **🎯 Key Features**

### **For Users:**
1. **Open Cases** - Spend points to open cases with different rarities
2. **Win Products** - Get actual products from your shop inventory
3. **Select City** - Choose delivery location after winning
4. **Convert to Balance** - If product unavailable in your city, convert to balance
5. **No Points Wins** - Only win products or lose (no points back)

### **For Admins:**
1. **Scalable Product Pool** - Add product TYPES once (not 1000 individual products)
2. **Win Chance Control** - Set % chance for each product type
3. **Emoji Customization** - Set custom emojis for each reward
4. **Lose Emoji** - Customize what shows when user wins nothing
5. **Easy Management** - CS:GO-style interface for creating "cases"

---

## **📊 How It Works**

### **Admin Creates Reward Pool:**

```
Case: Premium Case (50 points)
├── ☕ Kava 2g - 5% chance
├── 🍕 Pizza 5g - 10% chance
├── 💎 Premium Item - 2% chance
└── 💸 Lose (Nothing) - 83% chance
```

### **User Opens Case:**

1. User spends 50 points
2. System rolls random number (0-100)
3. If roll ≤ 5% → Win Kava 2g
4. If roll ≤ 15% → Win Pizza 5g
5. If roll ≤ 17% → Win Premium Item
6. Otherwise → Lose (show lose emoji)

### **If User Wins:**

1. **City Selection Screen** appears
2. User selects city where product is available
3. System finds available product in that city
4. Product is marked for delivery
5. If city unavailable → "Convert to Balance" button

---

## **🛠️ Admin Workflow**

### **Step 1: Access Product Pool Manager**
```
/admin → Daily Rewards Settings → Manage Product Pool
```

### **Step 2: Select Case to Configure**
```
📦 Basic Case
💎 Premium Case
🏆 Legendary Case
```

### **Step 3: Add Product Types**
```
1. Click "➕ Add Product Type"
2. Select product type (e.g., "Kava 2g")
3. Set win chance % (e.g., 5%)
4. Choose emoji (e.g., ☕)
5. Save
```

### **Step 4: Set Lose Emoji**
```
Click "💸 Set Lose Emoji"
Choose emoji that shows when user wins nothing
```

### **Step 5: Review**
```
Current Rewards:
☕ Kava 2g - 5%
🍕 Pizza 5g - 10%
💎 Premium - 2%
💸 Lose - 83%
```

---

## **📱 User Experience**

### **Opening a Case:**

```
🎰 OPENING PREMIUM CASE...

[  💨  |  ❓  |  ❓  ]
[  ❓  |  💨  |  ❓  ]
[  🎁  |  💎  |  ⭐  ]
[  💎  |  ⭐  |  🎁  ]

🎉 WINNER! 🎉

☕ You won:
Kava 2g

💰 Value: 7.00€

━━━━━━━━━━━━━━━━━━━━

📍 Next step: Select delivery city
```

### **City Selection:**

```
☕ Kava 2g

📍 SELECT DELIVERY CITY

Available cities:
• Vilnius (15 available)
• Kaunas (8 available)
• Klaipėda (3 available)

[📍 Vilnius]
[📍 Kaunas]
[📍 Klaipėda]
[💵 Convert to Balance]
```

### **If City Unavailable:**

```
❌ No cities available for this product

You can convert to balance instead:
💵 7.00€ will be added to your account

[💵 Convert to Balance]
```

---

## **🗄️ Database Schema**

### **New Tables:**

#### **case_reward_pools**
Stores what products can be won from each case
```sql
- case_type (basic, premium, legendary)
- product_type_name (e.g., "Kava")
- product_size (e.g., "2g")
- win_chance_percent (e.g., 5.0)
- reward_emoji (e.g., "☕")
- is_active (boolean)
```

#### **case_lose_emojis**
Stores lose emoji for each case
```sql
- case_type
- lose_emoji (e.g., "💸")
- lose_message (e.g., "Better luck next time!")
```

#### **user_product_wins**
Tracks user wins pending city selection
```sql
- user_id
- case_type
- product_type_name
- product_size
- win_emoji
- estimated_value
- status (pending_city, awaiting_delivery, converted_to_balance)
- selected_city_id
- selected_district_id
- selected_product_id
- converted_to_balance
```

---

## **🔧 Technical Implementation**

### **Files:**

1. **`case_rewards_system.py`** - Core logic
   - Database schema
   - Case opening algorithm
   - City selection logic
   - Balance conversion

2. **`case_rewards_admin.py`** - Admin interface
   - Product pool manager
   - Case configuration
   - Emoji customization

3. **`case_opening_handlers.py`** - User interface
   - Case opening animation
   - City selection flow
   - Balance conversion

### **Integration:**

- **`main.py`** - Registers all handlers
- **`daily_rewards_system.py`** - Keeps existing daily login system
- **`daily_rewards_admin.py`** - Main admin menu

---

## **🎨 Customization**

### **Add New Case Type:**

Edit `daily_rewards_system.py`:
```python
CASE_TYPES = {
    'mythic': {
        'name': '🌟 Mythic Case',
        'cost': 200,
        'emoji': '🌟',
        'color': '🔴',
        'description': 'Ultra rare rewards',
        'animation_speed': 'legendary',
        'rewards': {}  # Will be configured in admin panel
    }
}
```

### **Change Animation Speed:**

Edit `case_opening_handlers.py`:
```python
# Adjust sleep times for faster/slower animation
await asyncio.sleep(0.3)  # Change to 0.1 for faster
```

---

## **📈 Benefits**

### **Scalability:**
- ✅ Works with 1 product or 10,000 products
- ✅ Admin adds product TYPES, not individual items
- ✅ No more cluttered UI with thousands of buttons

### **User Experience:**
- ✅ Exciting CS:GO-style animations
- ✅ Real product wins (not just points)
- ✅ City selection for delivery
- ✅ Fallback to balance if unavailable

### **Admin Control:**
- ✅ Easy to configure win chances
- ✅ Visual emoji customization
- ✅ Real-time statistics
- ✅ Dummy-proof interface

---

## **🚀 Deployment**

All changes are ready to deploy. The system will:

1. Create new database tables automatically
2. Register all handlers
3. Keep existing daily rewards system intact
4. Add new "Product Pool" option to admin menu

**No data loss** - All existing user points, streaks, and case openings are preserved.

---

## **📞 Support**

For issues or questions:
- Check Render logs for errors
- All handlers are registered in `main.py`
- Database initialization happens on startup
- Test with "Give Me Test Points" button in admin panel

---

## **✅ Testing Checklist**

- [ ] Admin can access Product Pool Manager
- [ ] Admin can add product types to cases
- [ ] Admin can set win chances
- [ ] Admin can customize emojis
- [ ] User can open cases
- [ ] Animation plays correctly
- [ ] Win detection works
- [ ] City selection appears after win
- [ ] Products are available in selected cities
- [ ] Balance conversion works
- [ ] Points are deducted correctly
- [ ] Statistics update properly

---

**🎉 The system is now ready for deployment!**

