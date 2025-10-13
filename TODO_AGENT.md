# 🎯 Daily Rewards System - Agent TODO List

## Current Status: IMPLEMENTATION COMPLETE - TESTING PHASE

## High Priority Issues
- [x] **CRITICAL**: Daily Rewards button NOT visible in user start menu → FIXED with toggle system
- [x] **CRITICAL**: Daily Rewards toggle NOT in admin "Edit Bot Look" panel → ADDED
- [x] Verify all handlers registered in KNOWN_HANDLERS → CONFIRMED
- [x] Verify DB column names match (products: id/name/available) → FIXED
- [x] Scan for syntax errors across all files → ALL CLEAN

## Discovery Tasks (Completed)
- [x] Locate user start menu construction in user.py → Found lines 208-222, 235-250
- [x] Locate admin "Edit Bot Look" / "Bot UI Management" menu → Found line 663
- [x] Check if Daily Rewards button code exists but not rendering → WAS hardcoded, now gated
- [x] Verify handler imports in main.py → All present
- [x] Run py_compile on all core files → ALL PASS

## Implementation Tasks (Completed)
- [x] Add bot_settings helpers (get/set/is_daily_rewards_enabled) to utils.py → Lines 3868-3908
- [x] Add toggle handler to admin.py → Lines 685-712 (handle_toggle_daily_rewards_button)
- [x] Register toggle_daily_rewards_button in main.py KNOWN_HANDLERS → Line 756
- [x] Gate Daily Rewards button insertion in user.py (default + classic themes) → Lines 213-214, 241-242
- [x] Import handler in main.py → Line 139
- [x] Update Bot UI menu to show toggle → Lines 669-683

## Testing Checklist (Pending)
- [ ] py_compile: main.py, utils.py, admin.py, user.py, daily_rewards_handlers.py
- [ ] Toggle OFF → Daily Rewards hidden in start menu
- [ ] Toggle ON → Daily Rewards visible in start menu
- [ ] Claim daily reward works
- [ ] Open case works with animation
- [ ] Stats/leaderboard render correctly
- [ ] No new exceptions in logs

## Completed
- ✅ Fixed database column names in admin_manage_rewards (id/name/available)
- ✅ All 10 daily rewards handlers created
- ✅ Handlers registered in main.py (initial registration)

## Notes
- Default state: Daily Rewards should be ON (visible)
- Must work for both default and classic theme layouts
- Preserve existing indentation and code style
- No regressions to 100% delivery system

---
Last Updated: Starting discovery phase

