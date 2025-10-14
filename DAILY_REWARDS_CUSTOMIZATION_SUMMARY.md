# Daily Rewards Customization System

## 🎯 Goal
Make the bot **fully customizable** for sellers who buy it. Admins can now personalize everything about the Daily Rewards system.

## ✅ What's Been Implemented

### 1. **Database Schema** (daily_rewards_system.py)
- ✅ New table: `daily_reward_schedule` stores customizable reward amounts per day
- ✅ Default 7-day schedule inserted on first run
- ✅ Supports infinite days (not limited to 7)

### 2. **Core Functions** (daily_rewards_system.py)
- ✅ `get_reward_schedule()` - Fetch current schedule from database
- ✅ `update_reward_for_day(day, points, desc)` - Update any day's reward
- ✅ `get_reward_for_day(day)` - Get reward for any day (with progressive calculation)
- ✅ `get_rolling_calendar(user_id, streak)` - **Rolling 7-day view**
  - Shows last 6 claimed days + next unclaimed day
  - After Day 7, calendar "rolls" forward
  - Example: Day 8 user sees Days 2-8, Day 15 user sees Days 9-15

### 3. **Admin Panel** (daily_rewards_admin.py)
- ✅ New button: "📅 Manage Reward Schedule" in main menu
- ✅ `handle_admin_reward_schedule()` - View all days with edit buttons
- ✅ `handle_admin_edit_reward_day()` - Edit specific day (16 preset amounts + custom)
- ✅ `handle_admin_save_reward_day()` - Save new reward amount
- ✅ `handle_admin_custom_reward_day()` - Prompt for custom amount
- ✅ `handle_custom_reward_amount_input()` - Handle text input
- ✅ `handle_admin_add_reward_days()` - Add 7/14/30 more days
- ✅ `handle_admin_confirm_add_days()` - Execute adding days with progressive rewards

### 4. **Progressive Reward System**
- ✅ Infinite streak support (no 7-day limit)
- ✅ After Day 7, rewards automatically calculated:
  - Repeats 7-day cycle with 50% multiplier per cycle
  - Example: Day 8 = Day 1 reward × 1.5, Day 15 = Day 1 reward × 2.0

## 🔄 Rolling Calendar Logic

**User on Day 1-7:**
```
✅ Day 1: 50 pts
✅ Day 2: 15 pts (claimed)
⬜️ Day 3: 25 pts (next)
⬜️ Day 4: 40 pts
⬜️ Day 5: 60 pts
⬜️ Day 6: 90 pts
⬜️ Day 7: 150 pts
```

**User on Day 8:**
```
✅ Day 2: 15 pts (oldest visible)
✅ Day 3: 25 pts
✅ Day 4: 40 pts
✅ Day 5: 60 pts
✅ Day 6: 90 pts
✅ Day 7: 150 pts
⬜️ Day 8: 75 pts (next - Day 1 × 1.5)
```

**User on Day 15:**
```
✅ Day 9: 90 pts
✅ Day 10: 135 pts
...
✅ Day 14: 225 pts
⬜️ Day 15: 100 pts (next)
```

## 📋 Still TODO

### 5. **Update User-Facing Handler** (daily_rewards_handlers.py)
- ⏳ Update `handle_daily_rewards_menu()` to use `get_rolling_calendar()`
- ⏳ Display rolling calendar instead of fixed Day 1-7

### 6. **Register Handlers** (main.py)
- ⏳ Import new handlers from daily_rewards_admin.py
- ⏳ Register callbacks: `admin_reward_schedule`, `admin_edit_reward_day`, etc.
- ⏳ Add state handler: `awaiting_custom_reward_amount`

### 7. **Testing & Deployment**
- ⏳ Test admin panel (edit rewards, add days)
- ⏳ Test rolling calendar display for users
- ⏳ Test progressive rewards (Day 8+)
- ⏳ Deploy to Render

## 🎨 Admin UI Preview

```
📅 DAILY REWARD SCHEDULE

Customize how many points users get each day!

Current Schedule:
Day 1: 50 pts - Welcome bonus
Day 2: 15 pts - Day 2 reward
Day 3: 25 pts - Day 3 reward
Day 4: 40 pts - Day 4 reward
Day 5: 60 pts - Day 5 reward
Day 6: 90 pts - Day 6 reward
Day 7: 150 pts - Week complete!

💡 Click a day to edit its reward amount

[Day 1] [Day 2] [Day 3]
[Day 4] [Day 5] [Day 6]
[Day 7]

[➕ Add More Days]
[⬅️ Back]
```

**When editing Day 1:**
```
✏️ EDIT DAY 1 REWARD

Current: 50 points

Select new reward amount:

[10 pts] [15 pts] [20 pts] [25 pts]
[30 pts] [40 pts] [50 pts] [60 pts]
[75 pts] [90 pts] [100 pts] [150 pts]
[200 pts] [250 pts] [300 pts] [500 pts]

[✏️ Enter Custom Amount]
[⬅️ Back]
```

## 🚀 Benefits for Sellers

1. **Full Customization**: Change any day's reward amount
2. **Infinite Progression**: Users can claim rewards forever (not just 7 days)
3. **Easy to Use**: Click-to-edit interface, no coding needed
4. **Progressive Rewards**: Automatic calculation for days beyond schedule
5. **Rolling Calendar**: Users always see their progress, not just Day 1-7
6. **Scalable**: Can add 7, 14, 30+ days at once

## 📊 Database Schema

```sql
CREATE TABLE daily_reward_schedule (
    day_number INTEGER PRIMARY KEY,
    points INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔗 Next Steps

1. Complete `daily_rewards_handlers.py` update
2. Register all handlers in `main.py`
3. Test thoroughly
4. Deploy and document for sellers

