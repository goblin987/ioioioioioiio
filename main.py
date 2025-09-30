# --- START OF FILE main.py ---

import logging
import asyncio
import os
import signal
import sqlite3 # Keep for error handling if needed directly
from functools import wraps
from datetime import timedelta
import threading # Added for Flask thread
import json # Added for webhook processing
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP
import hmac # For webhook signature verification
import hashlib # For webhook signature verification

# --- Telegram Imports ---
from telegram import Update, BotCommand, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, Defaults, ContextTypes,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters,
    PicklePersistence, JobQueue
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest, NetworkError, RetryAfter, TelegramError

# --- Flask Imports ---
from flask import Flask, request, Response # Added for webhook server
import nest_asyncio # Added to allow nested asyncio loops

# --- Local Imports ---
from utils import (
    TOKEN, ADMIN_ID, init_db, load_all_data, LANGUAGES, THEMES,
    SUPPORT_USERNAME, BASKET_TIMEOUT, clear_all_expired_baskets,
    SECONDARY_ADMIN_IDS, WEBHOOK_URL,
    NOWPAYMENTS_IPN_SECRET,
    get_db_connection,
    get_pending_deposit, remove_pending_deposit, FEE_ADJUSTMENT,
    send_message_with_retry,
    log_admin_action,
    format_currency,
    clean_expired_pending_payments,
    get_expired_payments_for_notification,
    clean_abandoned_reservations,
    get_crypto_price_eur,
    get_first_primary_admin_id, # Admin helper for notifications
    is_user_banned  # Import ban check helper
)

# Import auto ads system initialization
try:
    from auto_ads_system import init_enhanced_auto_ads_tables
except ImportError:
    def init_enhanced_auto_ads_tables(): 
        logging.getLogger(__name__).warning("Auto ads system not available")
        return True

import user # Import user module
from user import (
    start, handle_shop, handle_city_selection, handle_district_selection,
    handle_type_selection, handle_product_selection, handle_add_to_basket,
    handle_view_basket, handle_clear_basket, handle_remove_from_basket,
    handle_profile, handle_language_selection, handle_price_list,
    handle_price_list_city, handle_reviews_menu, handle_leave_review,
    handle_view_reviews, handle_leave_review_message, handle_back_start,
    handle_user_discount_code_message, apply_discount_start, remove_discount,
    handle_leave_review_now, handle_refill, handle_view_history,
    handle_refill_amount_message, validate_discount_code,
    handle_apply_discount_basket_pay,
    handle_skip_discount_basket_pay,
    handle_basket_discount_code_message,
    _show_crypto_choices_for_basket,
    handle_pay_single_item,
    handle_confirm_pay, # Direct import of the function
    # <<< ADDED Single Item Discount Flow Handlers from user.py >>>
    handle_apply_discount_single_pay,
    handle_skip_discount_single_pay,
    handle_single_item_discount_code_message
)
import admin # Import admin module
import marketing_promotions # Import marketing and promotions module
from marketing_promotions import (
    init_marketing_tables, handle_marketing_promotions_menu, handle_ui_theme_designer,
    handle_select_ui_theme, handle_classic_welcome, handle_minimalist_welcome, handle_minimalist_shop,
    handle_minimalist_city_select, handle_minimalist_district_select, 
    handle_minimalist_product_type, handle_minimalist_product_select,
    handle_minimalist_pay_options, handle_minimalist_discount_code,
    handle_minimalist_home, handle_minimalist_profile, handle_minimalist_topup,
    handle_modern_welcome, handle_modern_shop, handle_modern_city_select,
    handle_modern_district_select, handle_modern_product_type, handle_modern_product_select,
    handle_modern_pay_options, handle_modern_discount_code, handle_modern_deals,
    handle_modern_deal_select, handle_modern_profile, handle_modern_wallet,
    handle_modern_promotions, handle_modern_app, handle_modern_home,
    handle_admin_hot_deals_menu, handle_admin_add_hot_deal, handle_admin_hot_deal_product,
    handle_admin_deal_custom_price, handle_admin_deal_discount, handle_admin_deal_title_only,
    handle_admin_deal_quantity_limit, handle_admin_manage_hot_deals,
    handle_admin_edit_hot_deal, handle_admin_toggle_hot_deal, handle_admin_delete_hot_deal,
    handle_select_custom_template, handle_delete_custom_template, handle_city_header_noop,
    handle_confirm_delete_theme, handle_execute_delete_theme, handle_edit_preset_theme,
    handle_edit_custom_theme, handle_preview_active_theme,
    handle_pay_single_item_hot_deal, handle_admin_deal_skip_title, handle_admin_hot_deal_product_preserve,
    handle_hot_deal_price_message, handle_hot_deal_discount_message, 
    handle_hot_deal_title_message, handle_hot_deal_quantity_message, handle_admin_app_info_menu, handle_admin_add_app_info,
    handle_admin_manage_app_info, handle_admin_edit_app_info, handle_admin_toggle_info_status,
    handle_admin_delete_app_info, handle_app_info_title_message, handle_app_info_content_message,
    handle_admin_disable_auto_deals, handle_admin_enable_auto_deals,
    handle_admin_bot_look_editor, handle_bot_look_presets, handle_bot_preset_select,
    handle_bot_look_custom, handle_bot_edit_menu, handle_bot_select_button,
    handle_bot_place_button, handle_bot_remove_button, handle_bot_add_row, handle_bot_save_menu,
    handle_bot_clear_menu, handle_bot_save_layout, handle_bot_look_preview, handle_bot_name_layout,
    handle_bot_custom_select, handle_template_name_message, handle_bot_edit_header,
    handle_bot_show_variables, handle_bot_reset_header, handle_header_message_input
)
from admin import (
    handle_admin_menu, handle_sales_analytics_menu, handle_sales_dashboard,
    handle_sales_select_period, handle_sales_run, handle_adm_city, handle_adm_dist,
    handle_adm_type, handle_adm_add, handle_adm_size, handle_adm_custom_size,
    handle_confirm_add_drop, cancel_add, handle_adm_manage_cities, handle_adm_add_city,
    handle_adm_edit_city, handle_adm_delete_city, handle_adm_manage_districts,
    handle_adm_manage_districts_city, handle_adm_add_district, handle_adm_edit_district,
    handle_adm_remove_district, handle_adm_manage_products, handle_adm_manage_products_city,
    handle_adm_manage_products_dist, handle_adm_manage_products_type, handle_adm_delete_prod,
    handle_adm_manage_types, handle_adm_add_type, handle_adm_delete_type,
    handle_adm_edit_type_menu, handle_adm_change_type_emoji, handle_adm_change_type_name,
    handle_adm_reassign_type_start, handle_adm_reassign_select_old, handle_adm_reassign_confirm,
    handle_adm_manage_discounts, handle_adm_toggle_discount, handle_adm_delete_discount,
    handle_adm_add_discount_start, handle_adm_use_generated_code, handle_adm_set_discount_type,
    handle_adm_discount_code_message, handle_adm_discount_value_message,
    handle_adm_set_media,
    handle_adm_broadcast_start, handle_cancel_broadcast,
    handle_confirm_broadcast,
    handle_adm_broadcast_target_type, handle_adm_broadcast_target_city, handle_adm_broadcast_target_status,
    handle_adm_clear_reservations_confirm,
    handle_confirm_yes,
    handle_adm_bot_media_message,  # Import bot media handler
    # Bulk product handlers
    handle_adm_bulk_city, handle_adm_bulk_dist, handle_adm_bulk_type, handle_adm_bulk_add,
    handle_adm_bulk_size, handle_adm_bulk_custom_size, handle_adm_bulk_custom_size_message,
    handle_adm_bulk_price_message, handle_adm_bulk_drop_details_message,
    handle_adm_bulk_remove_last_message, handle_adm_bulk_back_to_messages, handle_adm_bulk_execute_messages,
    cancel_bulk_add,
    # Message handlers that actually exist
    handle_adm_add_city_message, handle_adm_edit_city_message, handle_adm_add_district_message,
    handle_adm_edit_district_message, handle_adm_custom_size_message,
    handle_adm_drop_details_message, handle_adm_price_message,
    # Product type message handlers
    handle_adm_new_type_name_message, handle_adm_new_type_emoji_message,
    handle_adm_new_type_description_message, handle_adm_edit_type_emoji_message,
    # User search handlers
    handle_adm_search_user_start, handle_adm_search_username_message,
    # User detail handlers
    handle_adm_user_deposits, handle_adm_user_purchases, handle_adm_user_actions,
    handle_adm_user_discounts, handle_adm_user_overview,
)
from viewer_admin import (
    handle_viewer_admin_menu,
    handle_viewer_added_products,
    handle_viewer_view_product_media,
    handle_manage_users_start,
    handle_view_user_profile,
    handle_adjust_balance_start,
    handle_toggle_ban_user,
    handle_adjust_balance_amount_message,
    handle_adjust_balance_reason_message
)

# Import new feature modules
try:
    import stock_management
    from stock_management import (
        handle_stock_management_menu, handle_stock_check_now, handle_stock_clear_alerts, handle_stock_detailed_report,
        handle_stock_analytics, handle_stock_configure_thresholds, handle_stock_view_alerts,
        handle_stock_export_analytics, handle_stock_set_global_thresholds,
        handle_stock_configure_by_type, handle_stock_reset_thresholds, handle_stock_confirm_reset,
        check_low_stock_alerts
    )
except ImportError:
    import logging
    logging.getLogger(__name__).error("Could not import stock_management module")
    # Create dummy handlers
    async def handle_stock_management_menu(update, context, params=None):
        await update.callback_query.edit_message_text("Stock management not available")
    async def handle_stock_check_now(update, context, params=None):
        await update.callback_query.edit_message_text("Stock check not available")
    async def handle_stock_clear_alerts(update, context, params=None):
        await update.callback_query.edit_message_text("Stock alerts not available")
    async def handle_stock_detailed_report(update, context, params=None):
        await update.callback_query.edit_message_text("Stock report not available")
    async def handle_stock_analytics(update, context, params=None):
        await update.callback_query.edit_message_text("Stock analytics not available")
    async def handle_stock_configure_thresholds(update, context, params=None):
        await update.callback_query.edit_message_text("Stock configuration not available")
    async def handle_stock_view_alerts(update, context, params=None):
        await update.callback_query.edit_message_text("Stock alerts not available")
    async def check_low_stock_alerts():
        pass

try:
    import product_price_editor
    from product_price_editor import (
        handle_product_price_editor_menu, handle_price_search_products, handle_price_edit_by_city,
        handle_price_edit_by_category, handle_price_search_message, handle_price_edit_product,
        handle_price_new_price_message, handle_price_set_quick, handle_price_show_all_products,
        handle_price_change_history, handle_price_bulk_updates, handle_price_bulk_increase,
        handle_price_bulk_decrease, handle_price_bulk_apply, handle_price_city_products,
        handle_price_category_products, init_price_editor_tables,
        # New handlers for the redesigned price editor
        handle_price_bulk_all_locations, handle_price_bulk_select, handle_price_edit_by_city_district,
        handle_price_city_select, handle_price_city_district_select, handle_price_district_select,
        handle_price_city_product_select, handle_price_district_product_select,
        handle_price_city_apply, handle_price_district_apply
    )
except ImportError:
    import logging
    logging.getLogger(__name__).error("Could not import product_price_editor module")
    # Create dummy handlers
    async def handle_product_price_editor_menu(update, context, params=None):
        await update.callback_query.edit_message_text("Product price editor not available")
    async def handle_price_search_products(update, context, params=None):
        await update.callback_query.edit_message_text("Price search not available")
    async def handle_price_edit_by_city(update, context, params=None):
        await update.callback_query.edit_message_text("Price editing not available")
    async def handle_price_edit_by_category(update, context, params=None):
        await update.callback_query.edit_message_text("Price editing not available")
    async def handle_price_search_message(update, context):
        pass
    async def handle_price_edit_product(update, context, params=None):
        await update.callback_query.edit_message_text("Price editing not available")
    async def handle_price_new_price_message(update, context):
        pass
    async def handle_price_set_quick(update, context, params=None):
        await update.callback_query.edit_message_text("Price editing not available")
    async def handle_price_show_all_products(update, context, params=None):
        await update.callback_query.edit_message_text("Price editing not available")
    async def handle_price_change_history(update, context, params=None):
        await update.callback_query.edit_message_text("Price history not available")
    def init_price_editor_tables(): pass

# Interactive welcome editor removed - functionality replaced by Visual Bot UI Editor

try:
    import welcome_editor
    from welcome_editor import (
        handle_welcome_editor_menu, handle_welcome_edit_text, handle_welcome_edit_buttons,
        handle_welcome_rearrange_buttons, handle_welcome_text_message, handle_welcome_preview,
        handle_welcome_templates, handle_welcome_template_friendly, handle_welcome_template_professional,
        handle_welcome_template_ecommerce, handle_welcome_template_gaming, handle_welcome_auto_arrange, 
        handle_welcome_preview_buttons, handle_welcome_move_button, handle_welcome_toggle_buttons,
        handle_welcome_edit_button_text, handle_welcome_use_template, handle_welcome_toggle_button,
        handle_welcome_set_position, handle_welcome_reset_confirm, handle_welcome_reset_execute,
        handle_welcome_save_changes, init_welcome_tables, get_active_welcome_message, get_start_menu_buttons
    )
except ImportError:
    import logging
    logging.getLogger(__name__).error("Could not import welcome_editor module")
    # Create dummy handlers
    async def handle_welcome_editor_menu(update, context, params=None):
        await update.callback_query.edit_message_text("Welcome editor not available")
    async def handle_welcome_edit_text(update, context, params=None):
        await update.callback_query.edit_message_text("Welcome editor not available")
    async def handle_welcome_edit_buttons(update, context, params=None):
        await update.callback_query.edit_message_text("Welcome editor not available")
    async def handle_welcome_rearrange_buttons(update, context, params=None):
        await update.callback_query.edit_message_text("Welcome editor not available")
    async def handle_welcome_text_message(update, context):
        pass
    async def handle_welcome_preview(update, context, params=None):
        await update.callback_query.edit_message_text("Welcome editor not available")
    async def handle_welcome_reset_confirm(update, context, params=None):
        await update.callback_query.edit_message_text("Welcome editor not available")
    async def handle_welcome_reset_execute(update, context, params=None):
        await update.callback_query.edit_message_text("Welcome editor not available")
    async def handle_welcome_save_changes(update, context, params=None):
        await update.callback_query.edit_message_text("Welcome editor not available")
    def init_welcome_tables(): pass
    def get_active_welcome_message(): return "Welcome!"
    def get_start_menu_buttons(): return []


try:
    import referral_system
    from referral_system import (
        handle_referral_menu, handle_referral_create_code, handle_referral_share_code,
        handle_referral_copy_code, handle_referral_admin_menu, process_referral_purchase,
        handle_referral_how_it_works, handle_referral_view_details, handle_referral_tips,
        handle_referral_admin_stats, handle_referral_admin_top_referrers,
        handle_referral_admin_settings, handle_referral_admin_reset,
        # 🚀 YOLO MODE: NEW ADMIN HANDLERS!
        handle_referral_admin_toggle, handle_referral_admin_set_percentage,
        handle_referral_admin_set_bonus, handle_referral_admin_set_min_purchase,
        handle_referral_admin_reset_confirm,
        # 🚀 MESSAGE HANDLERS FOR ADMIN SETTINGS
        handle_referral_percentage_message, handle_referral_bonus_message,
        handle_referral_min_purchase_message,
        # 🚀 PAYMENT MENU REFERRAL HANDLERS
        handle_referral_code_payment, handle_referral_code_payment_message,
        handle_cancel_referral_code
    )
except ImportError:
    import logging
    logging.getLogger(__name__).error("Could not import referral_system module")
    # Create dummy handlers
    async def handle_referral_menu(update, context, params=None):
        await update.callback_query.edit_message_text("Referral system not available")
    async def handle_referral_create_code(update, context, params=None):
        await update.callback_query.edit_message_text("Referral system not available")
    async def handle_referral_share_code(update, context, params=None):
        await update.callback_query.edit_message_text("Referral system not available")
    async def handle_referral_copy_code(update, context, params=None):
        await update.callback_query.edit_message_text("Referral system not available")
    async def handle_referral_admin_menu(update, context, params=None):
        await update.callback_query.edit_message_text("Referral system not available")
    async def process_referral_purchase(user_id, amount): return False

try:
    import testforwarder_integration
    from testforwarder_integration import (
        handle_testforwarder_menu, handle_testforwarder_manual_setup,
        handle_testforwarder_message, handle_testforwarder_login_code, handle_testforwarder_2fa,
        handle_testforwarder_bump_service, handle_testforwarder_my_configs,
        handle_testforwarder_add_forwarding, handle_testforwarder_settings, handle_testforwarder_help,
        handle_testforwarder_manage_accounts, handle_testforwarder_edit_account, handle_testforwarder_delete_account,
        handle_testforwarder_edit_config, handle_testforwarder_delete_config,
        handle_testforwarder_add_campaign, handle_testforwarder_my_campaigns,
        handle_testforwarder_edit_campaign, handle_testforwarder_delete_campaign,
        handle_testforwarder_select_account, handle_testforwarder_run_campaign,
        handle_testforwarder_select_forwarding_account, handle_testforwarder_upload_session,
        handle_testforwarder_add_buttons_yes, handle_testforwarder_add_buttons_no,
        handle_testforwarder_target_all_groups, handle_testforwarder_target_specific_chats,
        handle_testforwarder_schedule_daily, handle_testforwarder_schedule_weekly,
        handle_testforwarder_schedule_hourly, handle_testforwarder_schedule_custom,
        get_testforwarder_bot
    )
except ImportError:
    import logging
    logging.getLogger(__name__).error("Could not import testforwarder_integration module")
    # Create dummy handlers for testforwarder integration
    async def handle_testforwarder_menu(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_manual_setup(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_message(update, context):
        pass
    async def handle_testforwarder_login_code(update, context):
        pass
    async def handle_testforwarder_2fa(update, context):
        pass
    async def handle_testforwarder_bump_service(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_my_configs(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_add_forwarding(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_settings(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_help(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_manage_accounts(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_edit_account(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_delete_account(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_edit_config(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_delete_config(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_add_campaign(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_my_campaigns(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_edit_campaign(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_delete_campaign(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_select_account(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_run_campaign(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_select_forwarding_account(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_upload_session(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_add_buttons_yes(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_add_buttons_no(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_target_all_groups(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_target_specific_chats(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_schedule_daily(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_schedule_weekly(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_schedule_hourly(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    async def handle_testforwarder_schedule_custom(update, context, params=None):
        await update.callback_query.edit_message_text("Testforwarder integration not available")
    def get_testforwarder_bot():
        return None

try:
    import vip_system
    from vip_system import (
        handle_vip_management_menu, handle_vip_manage_levels, handle_vip_create_level,
        handle_vip_select_emoji, handle_vip_level_name_message, handle_vip_min_purchases_message,
        handle_vip_max_purchases_message, handle_vip_status_menu, handle_vip_perks_info, 
        handle_vip_custom_emoji, handle_vip_custom_emoji_message, handle_vip_edit_level,
        handle_vip_analytics, handle_vip_manage_benefits, handle_vip_list_customers,
        handle_vip_configure_benefits, handle_vip_delete_level, handle_vip_reset_defaults,
        handle_vip_edit_name, handle_vip_edit_emoji, handle_vip_edit_requirements,
        handle_vip_edit_discount, handle_vip_edit_benefits, handle_vip_toggle_active,
        handle_vip_add_benefit, handle_vip_remove_benefit, handle_vip_confirm_delete,
        handle_vip_confirm_reset, handle_vip_export_analytics,
        handle_vip_set_emoji, handle_vip_set_discount, handle_vip_name_edit_message,
        handle_vip_custom_product_discounts, handle_vip_priority_support,
        handle_vip_early_access, handle_vip_view_all_benefits,
        process_vip_level_up, VIPManager
    )
except ImportError:
    import logging
    logging.getLogger(__name__).error("Could not import vip_system module")
    # Create dummy handlers
    async def handle_vip_management_menu(update, context, params=None):
        await update.callback_query.edit_message_text("VIP system not available")
    async def handle_vip_manage_levels(update, context, params=None):
        await update.callback_query.edit_message_text("VIP system not available")
    async def handle_vip_create_level(update, context, params=None):
        await update.callback_query.edit_message_text("VIP system not available")
    async def handle_vip_select_emoji(update, context, params=None):
        await update.callback_query.edit_message_text("VIP system not available")
    async def handle_vip_level_name_message(update, context):
        pass
    async def handle_vip_min_purchases_message(update, context):
        pass
    async def handle_vip_custom_emoji(update, context, params=None):
        await update.callback_query.edit_message_text("VIP system not available")
    async def handle_vip_custom_emoji_message(update, context):
        pass
    async def process_vip_level_up(user_id, purchases, bot): return None
    class VIPManager:
        @staticmethod
        def init_vip_tables(): pass

try:
    from reseller_management import (
        handle_manage_resellers_menu,
        handle_reseller_manage_id_message,
        handle_reseller_toggle_status,
        handle_manage_reseller_discounts_select_reseller,
        handle_manage_specific_reseller_discounts,
        handle_reseller_add_discount_select_type,
        handle_reseller_add_discount_enter_percent,
        handle_reseller_edit_discount,
        handle_reseller_percent_message,
        handle_reseller_delete_discount_confirm,
    )
except ImportError:
    logger_dummy_reseller = logging.getLogger(__name__ + "_dummy_reseller")
    logger_dummy_reseller.error("Could not import handlers from reseller_management.py.")
    async def handle_manage_resellers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
        query = update.callback_query; msg = "Reseller Status Mgmt handler not found."
        if query: await query.edit_message_text(msg)
        else: await send_message_with_retry(context.bot, update.effective_chat.id, msg)
    async def handle_manage_reseller_discounts_select_reseller(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
        query = update.callback_query; msg = "Reseller Discount Mgmt handler not found."
        if query: await query.edit_message_text(msg)
        else: await send_message_with_retry(context.bot, update.effective_chat.id, msg)
    async def handle_reseller_manage_id_message(update: Update, context: ContextTypes.DEFAULT_TYPE): pass
    async def handle_reseller_toggle_status(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None): pass
    async def handle_manage_specific_reseller_discounts(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None): pass
    async def handle_reseller_add_discount_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None): pass
    async def handle_reseller_add_discount_enter_percent(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None): pass
    async def handle_reseller_edit_discount(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None): pass
    async def handle_reseller_percent_message(update: Update, context: ContextTypes.DEFAULT_TYPE): pass
    async def handle_reseller_delete_discount_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None): pass

import payment
from payment import credit_user_balance
from stock import handle_view_stock

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

nest_asyncio.apply()

flask_app = Flask(__name__)
telegram_app: Application | None = None
main_loop = None

# --- Callback Data Parsing Decorator ---
def callback_query_router(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Check if user is banned before processing any callback query
        if update.effective_user:
            user_id = update.effective_user.id
            
            if await is_user_banned(user_id):
                logger.info(f"Ignoring callback query from banned user {user_id}.")
                if update.callback_query:
                    try:
                        await update.callback_query.answer("❌ Your access has been restricted.", show_alert=True)
                    except Exception as e:
                        logger.error(f"Error answering callback from banned user {user_id}: {e}")
                return
        
        query = update.callback_query
        if query and query.data:
            parts = query.data.split('|')
            command = parts[0]
            params = parts[1:]
            target_func_name = f"handle_{command}"

            KNOWN_HANDLERS = {
                # User Handlers (from user.py)
                "start": user.start, "back_start": user.handle_back_start, "shop": user.handle_shop,
                "verification_cancel": user.handle_verification_cancel,
                "select_language": user.handle_select_language,
                "city": user.handle_city_selection, "dist": user.handle_district_selection,
                "type": user.handle_type_selection, "product": user.handle_product_selection,
                "add": user.handle_add_to_basket,
                "pay_single_item": user.handle_pay_single_item,
                "view_basket": user.handle_view_basket,
                "clear_basket": user.handle_clear_basket, "remove": user.handle_remove_from_basket,
                "profile": user.handle_profile, "language": user.handle_language_selection,
                "price_list": user.handle_price_list, "price_list_city": user.handle_price_list_city,
                "reviews": user.handle_reviews_menu, "leave_review": user.handle_leave_review,
                "view_reviews": user.handle_view_reviews, "leave_review_now": user.handle_leave_review_now,
                "refill": user.handle_refill,
                "view_history": user.handle_view_history,
                "apply_discount_start": user.apply_discount_start, "remove_discount": user.remove_discount,
                "confirm_pay": user.handle_confirm_pay, # <<< CORRECTED
                "apply_discount_basket_pay": user.handle_apply_discount_basket_pay,
                "skip_discount_basket_pay": user.handle_skip_discount_basket_pay,
                # <<< ADDED Single Item Discount Flow Callbacks (from user.py) >>>
                "apply_discount_single_pay": user.handle_apply_discount_single_pay,
                "skip_discount_single_pay": user.handle_skip_discount_single_pay,

                # Payment Handlers (from payment.py)
                "select_basket_crypto": payment.handle_select_basket_crypto,
                "cancel_crypto_payment": payment.handle_cancel_crypto_payment,
                "select_refill_crypto": payment.handle_select_refill_crypto,

                # Primary Admin Handlers (from admin.py)
                "admin_menu": admin.handle_admin_menu,
                "sales_analytics_menu": admin.handle_sales_analytics_menu, "sales_dashboard": admin.handle_sales_dashboard,
                "sales_select_period": admin.handle_sales_select_period, "sales_run": admin.handle_sales_run,
                "adm_city": admin.handle_adm_city, "adm_dist": admin.handle_adm_dist, "adm_type": admin.handle_adm_type,
                "adm_add": admin.handle_adm_add, "adm_size": admin.handle_adm_size, "adm_custom_size": admin.handle_adm_custom_size,
                "confirm_add_drop": admin.handle_confirm_add_drop, "cancel_add": admin.cancel_add,
                "adm_manage_cities": admin.handle_adm_manage_cities, "adm_add_city": admin.handle_adm_add_city,
                "adm_edit_city": admin.handle_adm_edit_city, "adm_delete_city": admin.handle_adm_delete_city,
                "adm_manage_districts": admin.handle_adm_manage_districts, "adm_manage_districts_city": admin.handle_adm_manage_districts_city,
                "adm_add_district": admin.handle_adm_add_district, "adm_edit_district": admin.handle_adm_edit_district,
                "adm_remove_district": admin.handle_adm_remove_district,
                "adm_manage_products": admin.handle_adm_manage_products, "adm_manage_products_city": admin.handle_adm_manage_products_city,
                "adm_manage_products_dist": admin.handle_adm_manage_products_dist, "adm_manage_products_type": admin.handle_adm_manage_products_type,
                "adm_delete_prod": admin.handle_adm_delete_prod,
                "adm_manage_types": admin.handle_adm_manage_types,
                "adm_skip_type_emoji": admin.handle_adm_skip_type_emoji,
                "adm_edit_type_menu": admin.handle_adm_edit_type_menu,
                "adm_change_type_emoji": admin.handle_adm_change_type_emoji,
                "adm_change_type_name": admin.handle_adm_change_type_name,
                "adm_add_type": admin.handle_adm_add_type,
                "adm_delete_type": admin.handle_adm_delete_type,
                "adm_reassign_type_start": admin.handle_adm_reassign_type_start,
                "adm_reassign_select_old": admin.handle_adm_reassign_select_old,
                "adm_reassign_confirm": admin.handle_adm_reassign_confirm,
                "confirm_force_delete_prompt": admin.handle_confirm_force_delete_prompt, # Changed from confirm_force_delete_type
                "adm_manage_discounts": admin.handle_adm_manage_discounts, "adm_toggle_discount": admin.handle_adm_toggle_discount,
                "adm_delete_discount": admin.handle_adm_delete_discount, "adm_add_discount_start": admin.handle_adm_add_discount_start,
                "adm_use_generated_code": admin.handle_adm_use_generated_code, "adm_set_discount_type": admin.handle_adm_set_discount_type,
                "adm_discount_code_message": admin.handle_adm_discount_code_message,
                "adm_discount_value_message": admin.handle_adm_discount_value_message,
                "adm_set_media": admin.handle_adm_set_media,
                "adm_clear_reservations_confirm": admin.handle_adm_clear_reservations_confirm,
                "confirm_yes": admin.handle_confirm_yes,
                "adm_broadcast_start": admin.handle_adm_broadcast_start,
                "adm_broadcast_target_type": admin.handle_adm_broadcast_target_type,
                "adm_broadcast_target_city": admin.handle_adm_broadcast_target_city,
                "adm_broadcast_target_status": admin.handle_adm_broadcast_target_status,
                "cancel_broadcast": admin.handle_cancel_broadcast,
                "confirm_broadcast": admin.handle_confirm_broadcast,
                "adm_manage_reviews": admin.handle_adm_manage_reviews,
                "adm_delete_review_confirm": admin.handle_adm_delete_review_confirm,
                "adm_manage_welcome": admin.handle_adm_manage_welcome,
                "adm_activate_welcome": admin.handle_adm_activate_welcome,
                "adm_add_welcome_start": admin.handle_adm_add_welcome_start,
                "adm_edit_welcome": admin.handle_adm_edit_welcome,
                "adm_delete_welcome_confirm": admin.handle_adm_delete_welcome_confirm,
                "adm_edit_welcome_text": admin.handle_adm_edit_welcome_text,
                "adm_edit_welcome_desc": admin.handle_adm_edit_welcome_desc,
                "adm_reset_default_confirm": admin.handle_reset_default_welcome,
                "confirm_save_welcome": admin.handle_confirm_save_welcome,
                # Bulk product handlers
                "adm_bulk_city": admin.handle_adm_bulk_city,
                "adm_bulk_dist": admin.handle_adm_bulk_dist,
                "adm_bulk_type": admin.handle_adm_bulk_type,
                "adm_bulk_add": admin.handle_adm_bulk_add,
                "adm_bulk_size": admin.handle_adm_bulk_size,
                "adm_bulk_custom_size": admin.handle_adm_bulk_custom_size,
                "cancel_bulk_add": admin.cancel_bulk_add,
                # New bulk message handlers
                "adm_bulk_remove_last_message": admin.handle_adm_bulk_remove_last_message,
                "adm_bulk_back_to_messages": admin.handle_adm_bulk_back_to_messages,
                "adm_bulk_execute_messages": admin.handle_adm_bulk_execute_messages,
                "adm_bulk_create_all": admin.handle_adm_bulk_confirm_all,

                # Viewer Admin Handlers (from viewer_admin.py)
                "viewer_admin_menu": handle_viewer_admin_menu,
                "viewer_added_products": handle_viewer_added_products,
                "viewer_view_product_media": handle_viewer_view_product_media,
                "adm_manage_users": handle_manage_users_start,
                "adm_view_user": handle_view_user_profile,
                "adm_adjust_balance_start": handle_adjust_balance_start,
                "adm_toggle_ban": handle_toggle_ban_user,

                # Reseller Management Handlers (from reseller_management.py)
                "manage_resellers_menu": handle_manage_resellers_menu,
                "reseller_toggle_status": handle_reseller_toggle_status,
                "manage_reseller_discounts_select_reseller": handle_manage_reseller_discounts_select_reseller,
                "reseller_manage_specific": handle_manage_specific_reseller_discounts,
                "reseller_add_discount_select_type": handle_reseller_add_discount_select_type,
                "reseller_add_discount_enter_percent": handle_reseller_add_discount_enter_percent,
                "reseller_edit_discount": handle_reseller_edit_discount,
                "reseller_delete_discount_confirm": handle_reseller_delete_discount_confirm,

                # Stock Handler (from stock.py)
                "view_stock": handle_view_stock,
                
                # User Search Handlers (from admin.py)
                "adm_search_user_start": admin.handle_adm_search_user_start,
                "adm_user_deposits": admin.handle_adm_user_deposits,
                "adm_user_purchases": admin.handle_adm_user_purchases,
                "adm_user_actions": admin.handle_adm_user_actions,
                "adm_user_discounts": admin.handle_adm_user_discounts,
    "adm_debug_reseller_discount": admin.handle_adm_debug_reseller_discount,
    "adm_recent_purchases": admin.handle_adm_recent_purchases,
                "adm_user_overview": admin.handle_adm_user_overview,
                
                # New organized admin menu handlers
                "admin_analytics_menu": admin.handle_admin_analytics_menu,
                "admin_products_menu": admin.handle_admin_products_menu,
                "admin_locations_menu": admin.handle_admin_locations_menu,
                "admin_users_menu": admin.handle_admin_users_menu,
                "admin_marketing_menu": admin.handle_admin_marketing_menu,
                "admin_bot_ui_menu": admin.handle_admin_bot_ui_menu,
                "admin_system_menu": admin.handle_admin_system_menu,
                "toggle_human_verification": admin.handle_toggle_human_verification,
                "set_verification_attempts": admin.handle_set_verification_attempts,
                "toggle_language_selection": admin.handle_toggle_language_selection,
                "change_language_placement": admin.handle_change_language_placement,
                "set_language_placement": admin.handle_set_language_placement,
                "admin_maintenance_menu": admin.handle_admin_maintenance_menu,
                "admin_system_health": admin.handle_admin_system_health,
                "admin_user_stats": admin.handle_admin_user_stats,
                "admin_financial_reports": admin.handle_admin_financial_reports,
                "admin_db_cleanup": admin.handle_admin_db_cleanup,
                "admin_system_stats": admin.handle_admin_system_stats,
                "admin_restart_services": admin.handle_admin_restart_services,
                "admin_view_logs": admin.handle_admin_view_logs,
                
                # Stock management handlers
                "stock_management_menu": handle_stock_management_menu,
                "stock_check_now": handle_stock_check_now,
                "stock_clear_alerts": handle_stock_clear_alerts,
                "stock_detailed_report": handle_stock_detailed_report,
                
                # A/B testing handlers
                
                # Referral system handlers
                "referral_menu": handle_referral_menu,
                "referral_create_code": handle_referral_create_code,
                "referral_share_code": handle_referral_share_code,
                "referral_copy_code": handle_referral_copy_code,
                "referral_admin_menu": handle_referral_admin_menu,
                "referral_how_it_works": handle_referral_how_it_works,
                "referral_view_details": handle_referral_view_details,
                "referral_tips": handle_referral_tips,
                "referral_admin_stats": handle_referral_admin_stats,
                "referral_admin_top_referrers": handle_referral_admin_top_referrers,
                "referral_admin_settings": handle_referral_admin_settings,
                "referral_admin_reset": handle_referral_admin_reset,
                # 🚀 YOLO MODE: NEW ADMIN CALLBACK HANDLERS!
                "referral_admin_toggle": handle_referral_admin_toggle,
                "referral_admin_set_percentage": handle_referral_admin_set_percentage,
                "referral_admin_set_bonus": handle_referral_admin_set_bonus,
                "referral_admin_set_min_purchase": handle_referral_admin_set_min_purchase,
                "referral_admin_reset_confirm": handle_referral_admin_reset_confirm,
                "referral_admin_reset_confirmed": handle_referral_admin_reset,
                # 🚀 PAYMENT MENU REFERRAL HANDLERS
                "referral_code": handle_referral_code_payment,
                "cancel_referral_code": handle_cancel_referral_code,
                
    # Testforwarder integration handlers
    "auto_ads_menu": handle_testforwarder_menu,
    "tf_main_menu": handle_testforwarder_menu,
    "tf_manage_accounts": handle_testforwarder_menu,
    "tf_manual_setup": handle_testforwarder_manual_setup,
    "tf_bump_service": handle_testforwarder_bump_service,
    "tf_my_configs": handle_testforwarder_my_configs,
    "tf_add_forwarding": handle_testforwarder_add_forwarding,
    "tf_help": handle_testforwarder_help,
    # Original testforwarder callback data
    "manage_accounts": handle_testforwarder_manage_accounts,
    "bump_service": handle_testforwarder_bump_service,
    "my_configs": handle_testforwarder_my_configs,
    "add_forwarding": handle_testforwarder_add_forwarding,
    "settings": handle_testforwarder_settings,
    "help": handle_testforwarder_help,
    "manual_setup": handle_testforwarder_manual_setup,
    "edit_account": handle_testforwarder_edit_account,
    "delete_account": handle_testforwarder_delete_account,
    "main_menu": handle_testforwarder_menu,
    "edit_config": handle_testforwarder_edit_config,
    "delete_config": handle_testforwarder_delete_config,
    "add_campaign": handle_testforwarder_add_campaign,
    "my_campaigns": handle_testforwarder_my_campaigns,
    "edit_campaign": handle_testforwarder_edit_campaign,
    "delete_campaign": handle_testforwarder_delete_campaign,
    "select_account": handle_testforwarder_select_account,
    "select_account_1": handle_testforwarder_select_account,
    "select_account_2": handle_testforwarder_select_account,
    "select_account_3": handle_testforwarder_select_account,
    "select_account_4": handle_testforwarder_select_account,
    "select_account_5": handle_testforwarder_select_account,
    "run_campaign": handle_testforwarder_run_campaign,
    "run_campaign_1": handle_testforwarder_run_campaign,
    "run_campaign_2": handle_testforwarder_run_campaign,
    "run_campaign_3": handle_testforwarder_run_campaign,
    "run_campaign_4": handle_testforwarder_run_campaign,
    "run_campaign_5": handle_testforwarder_run_campaign,
    "select_forwarding_account": handle_testforwarder_select_forwarding_account,
    "upload_session": handle_testforwarder_upload_session,
    "add_buttons_yes": handle_testforwarder_add_buttons_yes,
    "add_buttons_no": handle_testforwarder_add_buttons_no,
    "target_all_groups": handle_testforwarder_target_all_groups,
    "target_specific_chats": handle_testforwarder_target_specific_chats,
    "schedule_daily": handle_testforwarder_schedule_daily,
    "schedule_weekly": handle_testforwarder_schedule_weekly,
    "schedule_hourly": handle_testforwarder_schedule_hourly,
    "schedule_custom": handle_testforwarder_schedule_custom,
                
                # VIP system handlers
                "vip_management_menu": handle_vip_management_menu,
                "vip_manage_levels": handle_vip_manage_levels,
                "vip_create_level": handle_vip_create_level,
                "vip_select_emoji": handle_vip_select_emoji,
                "vip_status_menu": handle_vip_status_menu,
                "vip_perks_info": handle_vip_perks_info,
                "vip_custom_emoji": handle_vip_custom_emoji,
                "vip_edit_level": handle_vip_edit_level,
                "vip_analytics": handle_vip_analytics,
                "vip_manage_benefits": handle_vip_manage_benefits,
                "vip_list_customers": handle_vip_list_customers,
                "vip_configure_benefits": handle_vip_configure_benefits,
                "vip_delete_level": handle_vip_delete_level,
                "vip_reset_defaults": handle_vip_reset_defaults,
                "vip_edit_name": handle_vip_edit_name,
                "vip_edit_emoji": handle_vip_edit_emoji,
                "vip_edit_requirements": handle_vip_edit_requirements,
                "vip_edit_discount": handle_vip_edit_discount,
                "vip_edit_benefits": handle_vip_edit_benefits,
                "vip_toggle_active": handle_vip_toggle_active,
                "vip_add_benefit": handle_vip_add_benefit,
                "vip_remove_benefit": handle_vip_remove_benefit,
                "vip_confirm_delete": handle_vip_confirm_delete,
                "vip_confirm_reset": handle_vip_confirm_reset,
                "vip_export_analytics": handle_vip_export_analytics,
                "vip_set_emoji": handle_vip_set_emoji,
                "vip_set_discount": handle_vip_set_discount,
                "vip_custom_product_discounts": handle_vip_custom_product_discounts,
                "vip_priority_support": handle_vip_priority_support,
                "vip_early_access": handle_vip_early_access,
                "vip_view_all_benefits": handle_vip_view_all_benefits,
                
                # Missing stock management handlers
                "stock_analytics": handle_stock_analytics,
                "stock_configure_thresholds": handle_stock_configure_thresholds,
                "stock_view_alerts": handle_stock_view_alerts,
                "stock_export_analytics": handle_stock_export_analytics,
                "stock_set_global_thresholds": handle_stock_set_global_thresholds,
                "stock_configure_by_type": handle_stock_configure_by_type,
                "stock_reset_thresholds": handle_stock_reset_thresholds,
                "stock_confirm_reset": handle_stock_confirm_reset,
                
                # Missing A/B test handlers  
                
                # Welcome editor handlers
                "welcome_editor_menu": handle_welcome_editor_menu,
                "welcome_edit_text": handle_welcome_edit_text,
                "welcome_edit_buttons": handle_welcome_edit_buttons,
                "welcome_rearrange_buttons": handle_welcome_rearrange_buttons,
                "welcome_preview": handle_welcome_preview,
                "welcome_templates": handle_welcome_templates,
                "welcome_template_friendly": handle_welcome_template_friendly,
                "welcome_template_professional": handle_welcome_template_professional,
                "welcome_template_ecommerce": handle_welcome_template_ecommerce,
                "welcome_template_gaming": handle_welcome_template_gaming,
                "welcome_auto_arrange": handle_welcome_auto_arrange,
                "welcome_preview_buttons": handle_welcome_preview_buttons,
                "welcome_move_button": handle_welcome_move_button,
                "welcome_toggle_buttons": handle_welcome_toggle_buttons,
                "welcome_edit_button_text": handle_welcome_edit_button_text,
                "welcome_use_template": handle_welcome_use_template,
                "welcome_toggle_button": handle_welcome_toggle_button,
                "welcome_set_position": handle_welcome_set_position,
                "welcome_reset_confirm": handle_welcome_reset_confirm,
                "welcome_reset_execute": handle_welcome_reset_execute,
                "welcome_save_changes": handle_welcome_save_changes,
                
                
                # Product price editor handlers
                "product_price_editor_menu": handle_product_price_editor_menu,
                "price_search_products": handle_price_search_products,
                "price_edit_by_city": handle_price_edit_by_city,
                "price_edit_by_category": handle_price_edit_by_category,
                "price_edit_product": handle_price_edit_product,
                "price_set_quick": handle_price_set_quick,
                "price_show_all_products": handle_price_show_all_products,
                "price_change_history": handle_price_change_history,
                "price_bulk_updates": handle_price_bulk_updates,
                "price_bulk_increase": handle_price_bulk_increase,
                "price_bulk_decrease": handle_price_bulk_decrease,
                "price_bulk_apply": handle_price_bulk_apply,
                "price_city_products": handle_price_city_products,
                "price_category_products": handle_price_category_products,
                # New redesigned price editor handlers
                "price_bulk_all_locations": handle_price_bulk_all_locations,
                "price_bulk_select": handle_price_bulk_select,
                "price_edit_by_city_district": handle_price_edit_by_city_district,
                "price_city_select": handle_price_city_select,
                "price_city_district_select": handle_price_city_district_select,
                "price_district_select": handle_price_district_select,
                "price_city_product_select": handle_price_city_product_select,
                "price_district_product_select": handle_price_district_product_select,
                "price_city_apply": handle_price_city_apply,
                "price_district_apply": handle_price_district_apply,
                # Marketing and UI Theme handlers
                "marketing_promotions_menu": handle_marketing_promotions_menu,
                "ui_theme_designer": handle_ui_theme_designer,
                "select_ui_theme": handle_select_ui_theme,
                "preview_current_theme": handle_marketing_promotions_menu,  # Placeholder - redirect to main menu
                "marketing_campaigns_menu": handle_marketing_promotions_menu,  # Placeholder - redirect to main menu
                "promotion_codes_menu": handle_marketing_promotions_menu,  # Placeholder - redirect to main menu
                "stock_type_kava": admin.handle_adm_manage_types,  # Placeholder - redirect to product types management
                "minimalist_product_info": handle_marketing_promotions_menu,  # Placeholder - show product info
                "ignore": handle_marketing_promotions_menu,  # Ignore spacer buttons - redirect to main menu
                "minimalist_shop": handle_minimalist_shop,
                "minimalist_city_select": handle_minimalist_city_select,
                "minimalist_district_select": handle_minimalist_district_select,
                "minimalist_product_type": handle_minimalist_product_type,
                "minimalist_product_select": handle_minimalist_product_select,
                "minimalist_pay_options": handle_minimalist_pay_options,
                "minimalist_discount_code": handle_minimalist_discount_code,
                "minimalist_home": handle_minimalist_home,
                "minimalist_profile": handle_minimalist_profile,
                "minimalist_topup": handle_minimalist_topup,
                # Modern UI Theme Handlers
                "modern_welcome": handle_modern_welcome,
                "modern_shop": handle_modern_shop,
                "modern_city_select": handle_modern_city_select,
                "modern_district_select": handle_modern_district_select,
                "modern_product_type": handle_modern_product_type,
                "modern_product_select": handle_modern_product_select,
                "modern_pay_options": handle_modern_pay_options,
                "modern_discount_code": handle_modern_discount_code,
                "modern_deals": handle_modern_deals,
                "modern_deal_select": handle_modern_deal_select,
                "modern_profile": handle_modern_profile,
                "modern_wallet": handle_modern_wallet,
                "modern_promotions": handle_modern_promotions,
                "modern_app": handle_modern_app,
                "modern_home": handle_modern_home,
                # Hot Deals Management Handlers
                "admin_hot_deals_menu": handle_admin_hot_deals_menu,
                "admin_add_hot_deal": handle_admin_add_hot_deal,
                "admin_hot_deal_product": handle_admin_hot_deal_product,
                "admin_deal_custom_price": handle_admin_deal_custom_price,
                "admin_deal_discount": handle_admin_deal_discount,
                "admin_deal_title_only": handle_admin_deal_title_only,
                "admin_deal_quantity_limit": handle_admin_deal_quantity_limit,
                "admin_manage_hot_deals": handle_admin_manage_hot_deals,
                "admin_edit_hot_deal": handle_admin_edit_hot_deal,
                "admin_toggle_hot_deal": handle_admin_toggle_hot_deal,
                "admin_delete_hot_deal": handle_admin_delete_hot_deal,
                "select_custom_template": handle_select_custom_template,
                "delete_custom_template": handle_delete_custom_template,
                "confirm_delete_theme": handle_confirm_delete_theme,
                "execute_delete_theme": handle_execute_delete_theme,
                "edit_preset_theme": handle_edit_preset_theme,
                "edit_custom_theme": handle_edit_custom_theme,
                "preview_active_theme": handle_preview_active_theme,
                "theme_noop": handle_marketing_promotions_menu,  # No-op for active theme buttons
                "city_header_noop": handle_city_header_noop,  # Non-clickable city header
                "pay_single_item_hot_deal": handle_pay_single_item_hot_deal,  # Hot deals payment (no discounts)
                "admin_deal_skip_title": handle_admin_deal_skip_title,  # Skip title step
                "admin_hot_deal_product_preserve": handle_admin_hot_deal_product_preserve,  # Cancel with context preservation
                # App Info Management Handlers
                "admin_app_info_menu": handle_admin_app_info_menu,
                "admin_add_app_info": handle_admin_add_app_info,
                "admin_manage_app_info": handle_admin_manage_app_info,
                "admin_edit_app_info": handle_admin_edit_app_info,
                "admin_toggle_info_status": handle_admin_toggle_info_status,
                "admin_delete_app_info": handle_admin_delete_app_info,
                # YOLO MODE: Simple auto deals control - dummy proof
                "admin_disable_auto_deals": handle_admin_disable_auto_deals,
                "admin_enable_auto_deals": handle_admin_enable_auto_deals,
                # YOLO MODE: Fix Info button - register info callback
                "info": handle_modern_app,
                # YOLO MODE: Add Reviews button for custom UI
                "reviews": user.handle_reviews_menu,
                # YOLO MODE: Add missing original UI callbacks
                "price_list": user.handle_price_list,
                "language": user.handle_language_selection,
                # Visual Button Board Editor Handlers
                "admin_bot_look_editor": handle_admin_bot_look_editor,
                "bot_look_presets": handle_bot_look_presets,
                "bot_preset_select": handle_bot_preset_select,
                "bot_look_custom": handle_bot_look_custom,
                "bot_edit_menu": handle_bot_edit_menu,
                "bot_select_button": handle_bot_select_button,
                "bot_place_button": handle_bot_place_button,
                "bot_remove_button": handle_bot_remove_button,
                "bot_add_row": handle_bot_add_row,
                "bot_save_menu": handle_bot_save_menu,
                "bot_clear_menu": handle_bot_clear_menu,
                "bot_save_layout": handle_bot_save_layout,
                "bot_look_preview": handle_bot_look_preview,
                "bot_name_layout": handle_bot_name_layout,
                "bot_custom_select": handle_bot_custom_select,
                "bot_edit_header": handle_bot_edit_header,
                "bot_show_variables": handle_bot_show_variables,
                "bot_reset_header": handle_bot_reset_header,
                "bot_noop": handle_marketing_promotions_menu,  # Placeholder for separator buttons
            }

            target_func = KNOWN_HANDLERS.get(command)

            if target_func and asyncio.iscoroutinefunction(target_func):
                await target_func(update, context, params)
            else:
                logger.warning(f"No async handler function found or mapped for callback command: {command}")
                try: await query.answer("Unknown action.", show_alert=True)
                except Exception as e: logger.error(f"Error answering unknown callback query {command}: {e}")
        elif query:
            logger.warning("Callback query handler received update without data.")
            try: await query.answer()
            except Exception as e: logger.error(f"Error answering callback query without data: {e}")
        else:
            logger.warning("Callback query handler received update without query object.")
    return wrapper

@callback_query_router
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query handler (ban check is now handled in the decorator)."""
    # Ban check is handled in @callback_query_router decorator
    pass

# --- Start Command Wrapper with Ban Check ---
async def start_command_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for /start command that includes ban check"""
    user_id = update.effective_user.id
    
    # Check if user is banned before processing /start command
    if await is_user_banned(user_id):
        logger.info(f"Banned user {user_id} attempted to use /start command.")
        ban_message = "❌ Your access to this bot has been restricted. If you believe this is an error, please contact support."
        await send_message_with_retry(context.bot, update.effective_chat.id, ban_message, parse_mode=None)
        return
    
    # If not banned, proceed with normal start command
    await user.start(update, context)

# --- Admin Command Wrapper with Ban Check ---
async def admin_command_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for /admin command that includes ban check"""
    user_id = update.effective_user.id
    
    # Check if user is banned before processing /admin command
    if await is_user_banned(user_id):
        logger.info(f"Banned user {user_id} attempted to use /admin command.")
        ban_message = "❌ Your access to this bot has been restricted. If you believe this is an error, please contact support."
        await send_message_with_retry(context.bot, update.effective_chat.id, ban_message, parse_mode=None)
        return
    
    # If not banned, proceed with normal admin command
    await admin.handle_admin_menu(update, context)

# --- Central Message Handler (for states) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user: return

    user_id = update.effective_user.id
    state = context.user_data.get('state')
    logger.debug(f"Message received from user {user_id}, state: {state}")

    STATE_HANDLERS = {
        # User Handlers (from user.py)
        'awaiting_verification': user.handle_verification_message,
        'awaiting_verification_limit': admin.handle_verification_limit_message,
        'awaiting_review': user.handle_leave_review_message,
        'awaiting_user_discount_code': user.handle_user_discount_code_message,
        'awaiting_basket_discount_code': user.handle_basket_discount_code_message,
        'awaiting_refill_amount': user.handle_refill_amount_message,
        'awaiting_single_item_discount_code': user.handle_single_item_discount_code_message, # <<< ADDED
        'awaiting_refill_crypto_choice': None,
        'awaiting_basket_crypto_choice': None,
        
        # 🚀 YOLO MODE: REFERRAL ADMIN MESSAGE HANDLERS!
        'awaiting_referral_percentage': handle_referral_percentage_message,
        'awaiting_referral_bonus': handle_referral_bonus_message,
        'awaiting_referral_min_purchase': handle_referral_min_purchase_message,
        'awaiting_referral_code_payment': handle_referral_code_payment_message,
        
        # Auto ads system message handlers (removed - using testforwarder integration)
        
        # VIP system message handlers
        'awaiting_vip_level_name': handle_vip_level_name_message,
        'awaiting_vip_min_purchases': handle_vip_min_purchases_message,
        'awaiting_vip_max_purchases': handle_vip_max_purchases_message,
        'awaiting_vip_custom_emoji': handle_vip_custom_emoji_message,
        'awaiting_vip_name_edit': handle_vip_name_edit_message,
        'awaiting_welcome_text': handle_welcome_text_message,
        'awaiting_price_search': handle_price_search_message,
        'awaiting_new_price': handle_price_new_price_message,
        
        # Enhanced auto ads message handlers (testforwarder integration)
        'awaiting_session_file': handle_testforwarder_message,
        'awaiting_account_details': handle_testforwarder_message,
        'awaiting_channel_link': handle_testforwarder_message,

        # Admin Message Handlers (from admin.py)
        'awaiting_new_city_name': admin.handle_adm_add_city_message,
        'awaiting_edit_city_name': admin.handle_adm_edit_city_message,
        'awaiting_new_district_name': admin.handle_adm_add_district_message,
        'awaiting_edit_district_name': admin.handle_adm_edit_district_message,
        'awaiting_custom_size': admin.handle_adm_custom_size_message,
        'awaiting_drop_details': admin.handle_adm_drop_details_message,
        'awaiting_price': admin.handle_adm_price_message,
        # Discount code message handlers
        'awaiting_discount_code': admin.handle_adm_discount_code_message,
        'awaiting_discount_value': admin.handle_adm_discount_value_message,
        # Product type message handlers
        'awaiting_new_type_name': admin.handle_adm_new_type_name_message,
        'awaiting_new_type_emoji': admin.handle_adm_new_type_emoji_message,
        'awaiting_new_type_description': admin.handle_adm_new_type_description_message,
        'awaiting_edit_type_emoji': admin.handle_adm_edit_type_emoji_message,
        # Bulk product message handlers
        'awaiting_bulk_custom_size': admin.handle_adm_bulk_custom_size_message,
        'awaiting_bulk_price': admin.handle_adm_bulk_price_message,
        'awaiting_bulk_drop_details': admin.handle_adm_bulk_drop_details_message,
        'awaiting_bulk_messages': admin.handle_adm_bulk_drop_details_message,
        
        # Template naming handler (from marketing_promotions.py)
        'awaiting_template_name': handle_template_name_message,
        
        # Header message editing handler (from marketing_promotions.py)
        'awaiting_header_message': handle_header_message_input,
        
        # Hot deals handlers
        'awaiting_hot_deal_price': handle_hot_deal_price_message,
        'awaiting_hot_deal_discount': handle_hot_deal_discount_message,
        'awaiting_hot_deal_title': handle_hot_deal_title_message,
        'awaiting_hot_deal_quantity': handle_hot_deal_quantity_message,
        'awaiting_app_info_title': handle_app_info_title_message,
        'awaiting_app_info_content': handle_app_info_content_message,

        # User Management States (from viewer_admin.py)
        'awaiting_balance_adjustment_amount': handle_adjust_balance_amount_message,
        'awaiting_balance_adjustment_reason': handle_adjust_balance_reason_message,

        # Reseller Management States (from reseller_management.py)
        'awaiting_reseller_manage_id': handle_reseller_manage_id_message,
        'awaiting_reseller_discount_percent': handle_reseller_percent_message,
        
        # User Search States (from admin.py)
        'awaiting_search_username': admin.handle_adm_search_username_message,
        
        # Broadcast States (from admin.py)
        'awaiting_broadcast_message': admin.handle_adm_broadcast_message,
        'awaiting_broadcast_inactive_days': admin.handle_adm_broadcast_inactive_days_message,
        
        # Bot Media States (from admin.py)
        'awaiting_bot_media': admin.handle_adm_bot_media_message,
        
        # Welcome Message States (from admin.py)
        'awaiting_welcome_template_name': admin.handle_adm_welcome_template_name_message,
        'awaiting_welcome_template_text': admin.handle_adm_welcome_template_text_message,
        'awaiting_welcome_template_edit': admin.handle_adm_welcome_template_text_message,
        'awaiting_welcome_description': admin.handle_adm_welcome_description_message,
        'awaiting_welcome_description_edit': admin.handle_adm_welcome_description_message,
        
        
        
    }

    # Check if user is banned before processing ANY message (including state handlers)
    if await is_user_banned(user_id):
        logger.info(f"Ignoring message from banned user {user_id} (state: {state}).")
        # Send ban notification message
        try:
            ban_message = "❌ Your access to this bot has been restricted. If you believe this is an error, please contact support."
            await send_message_with_retry(context.bot, update.effective_chat.id, ban_message, parse_mode=None)
        except Exception as e:
            logger.error(f"Error sending ban message to user {user_id}: {e}")
        return
    
    # Check for admin/user state handlers FIRST
    handler_func = STATE_HANDLERS.get(state)
    if handler_func:
        logger.info(f"🔍 STATE: Handling state '{state}' for user {user_id}")
        await handler_func(update, context)
        return
    
    # If no state handler, try testforwarder bot for text messages and documents
    if update.message and (update.message.text or update.message.document):
        logger.info(f"🔍 MESSAGE: Routing to testforwarder bot for user {user_id}")
        try:
            if update.message.document:
                # Handle document uploads
                bot = get_testforwarder_bot()
                await bot.handle_document(update, context)
            else:
                await handle_testforwarder_message(update, context)
            return  # If testforwarder handled it, don't process further
        except Exception as e:
            logger.error(f"🔍 TESTFORWARDER FAILED: {e}")
    
    # No handler found
    logger.debug(f"No handler found for user {user_id} in state: {state}")

# --- Error Handler ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    logger.error(f"Caught error type: {type(context.error)}")
    chat_id = None
    user_id = None

    if isinstance(update, Update):
        if update.effective_chat: chat_id = update.effective_chat.id
        if update.effective_user: user_id = update.effective_user.id

    logger.debug(f"Error context: user_data={context.user_data}, chat_data={context.chat_data}")

    if chat_id:
        error_message = "An internal error occurred. Please try again later or contact support."
        if isinstance(context.error, BadRequest):
            error_str_lower = str(context.error).lower()
            if "message is not modified" in error_str_lower:
                logger.debug(f"Ignoring 'message is not modified' error for chat {chat_id}.")
                return
            if "query is too old" in error_str_lower:
                 logger.debug(f"Ignoring 'query is too old' error for chat {chat_id}.")
                 return
            logger.warning(f"Telegram API BadRequest for chat {chat_id} (User: {user_id}): {context.error}")
            if "can't parse entities" in error_str_lower:
                error_message = "An error occurred displaying the message due to formatting. Please try again."
            else:
                 error_message = "An error occurred communicating with Telegram. Please try again."
        elif isinstance(context.error, NetworkError):
            logger.warning(f"Telegram API NetworkError for chat {chat_id} (User: {user_id}): {context.error}")
            error_message = "A network error occurred. Please check your connection and try again."
        elif isinstance(context.error, Forbidden):
             logger.warning(f"Forbidden error for chat {chat_id} (User: {user_id}): Bot possibly blocked or kicked.")
             return
        elif isinstance(context.error, RetryAfter):
             retry_seconds = context.error.retry_after + 1
             logger.warning(f"Rate limit hit during update processing for chat {chat_id}. Error: {context.error}")
             return
        elif isinstance(context.error, sqlite3.Error):
            logger.error(f"Database error during update handling for chat {chat_id} (User: {user_id}): {context.error}", exc_info=True)
        elif isinstance(context.error, NameError):
             logger.error(f"NameError encountered for chat {chat_id} (User: {user_id}): {context.error}", exc_info=True)
             if 'clear_expired_basket' in str(context.error): error_message = "An internal processing error occurred (payment). Please try again."
             elif 'handle_adm_welcome_' in str(context.error): error_message = "An internal processing error occurred (welcome msg). Please try again."
             else: error_message = "An internal processing error occurred. Please try again or contact support if it persists."
        elif isinstance(context.error, AttributeError):
             logger.error(f"AttributeError encountered for chat {chat_id} (User: {user_id}): {context.error}", exc_info=True)
             if "'NoneType' object has no attribute 'get'" in str(context.error) and "_process_collected_media" in str(context.error.__traceback__): error_message = "An internal processing error occurred (media group). Please try again."
             elif "'module' object has no attribute" in str(context.error) and "handle_confirm_pay" in str(context.error): error_message = "A critical configuration error occurred. Please contact support immediately."
             else: error_message = "An unexpected internal error occurred. Please contact support."
        else:
             logger.exception(f"An unexpected error occurred during update handling for chat {chat_id} (User: {user_id}).")
             error_message = "An unexpected error occurred. Please contact support."
        try:
            bot_instance = context.bot if hasattr(context, 'bot') else (telegram_app.bot if telegram_app else None)
            if bot_instance: await send_message_with_retry(bot_instance, chat_id, error_message, parse_mode=None)
            else: logger.error("Could not get bot instance to send error message.")
        except Exception as e:
            logger.error(f"Failed to send error message to user {chat_id}: {e}")

# --- Bot Setup Functions ---
async def post_init(application: Application) -> None:
    logger.info("Running post_init setup...")
    logger.info("Setting bot commands...")
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot / Main menu"),
        BotCommand("admin", "Access admin panel (Admin only)"),
    ])
    logger.info("Post_init finished.")

async def post_shutdown(application: Application) -> None:
    logger.info("Running post_shutdown cleanup...")
    logger.info("Post_shutdown finished.")

async def clear_expired_baskets_job_wrapper(context: ContextTypes.DEFAULT_TYPE):
    logger.debug("Running background job: clear_expired_baskets_job")
    try:
        await asyncio.to_thread(clear_all_expired_baskets)
    except Exception as e:
        logger.error(f"Error in background job clear_expired_baskets_job: {e}", exc_info=True)

async def clean_expired_payments_job_wrapper(context: ContextTypes.DEFAULT_TYPE):
    logger.debug("Running background job: clean_expired_payments_job")
    try:
        # Get the list of expired payments before cleaning them up
        expired_user_notifications = await asyncio.to_thread(get_expired_payments_for_notification)
        
        # Clean up the expired payments
        await asyncio.to_thread(clean_expired_pending_payments)
        
        # Send notifications to users
        if expired_user_notifications:
            await send_timeout_notifications(context, expired_user_notifications)
            
    except Exception as e:
        logger.error(f"Error in background job clean_expired_payments_job: {e}", exc_info=True)

async def clean_abandoned_reservations_job_wrapper(context: ContextTypes.DEFAULT_TYPE):
    logger.debug("Running background job: clean_abandoned_reservations_job")
    try:
        await asyncio.to_thread(clean_abandoned_reservations)
    except Exception as e:
        logger.error(f"Error in background job clean_abandoned_reservations_job: {e}", exc_info=True)



async def stock_alerts_job_wrapper(context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for the stock alerts job to handle asyncio properly."""
    logger.debug("Running background job: stock_alerts")
    try:
        alert_message = await check_low_stock_alerts()
        if alert_message and context.application and context.application.bot:
            try:
                await send_message_with_retry(
                    context.application.bot, 
                    ADMIN_ID, 
                    alert_message, 
                    parse_mode='Markdown'
                )
                logger.info("📧 Sent low stock alert to admin")
            except Exception as e:
                logger.error(f"Failed to send stock alert: {e}")
    except Exception as e:
        logger.error(f"Error in stock alerts job: {e}", exc_info=True)

async def auto_ads_execution_job_wrapper(context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for executing pending auto ads campaigns."""
    logger.debug("Running background job: auto_ads_execution")
    try:
        from auto_ads_system import get_campaign_executor
        executor = get_campaign_executor()
        if executor:
            pending_campaigns = executor.get_pending_executions()
            for campaign_id in pending_campaigns:
                try:
                    await executor.execute_campaign(campaign_id)
                except Exception as e:
                    logger.error(f"Error executing campaign {campaign_id}: {e}")
    except Exception as e:
        logger.error(f"Error in auto ads execution job: {e}", exc_info=True)


async def send_timeout_notifications(context: ContextTypes.DEFAULT_TYPE, user_notifications: list):
    """Send timeout notifications to users whose payments have expired."""
    for user_notification in user_notifications:
        user_id = user_notification['user_id']
        user_lang = user_notification['language']
        
        try:
            lang_data = LANGUAGES.get(user_lang, LANGUAGES['en'])
            notification_msg = lang_data.get("payment_timeout_notification", 
                "⏰ Payment Timeout: Your payment for basket items has expired after 2 hours. Reserved items have been released.")
            
            await send_message_with_retry(context.bot, user_id, notification_msg, parse_mode=None)
            logger.info(f"Sent payment timeout notification to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send timeout notification to user {user_id}: {e}")


async def retry_purchase_finalization(user_id: int, basket_snapshot: list, discount_code_used: str | None, payment_id: str, context: ContextTypes.DEFAULT_TYPE, max_retries: int = 3):
    """Retry purchase finalization with exponential backoff in case of failures."""
    import payment
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Retrying purchase finalization for payment {payment_id}, attempt {attempt + 1}/{max_retries}")
            
            # Wait with exponential backoff: 5s, 15s, 45s
            if attempt > 0:
                wait_time = 5 * (3 ** attempt)
                logger.info(f"Waiting {wait_time} seconds before retry attempt {attempt + 1}")
                await asyncio.sleep(wait_time)
            
            # Retry the finalization
            purchase_finalized = await payment.process_successful_crypto_purchase(
                user_id, basket_snapshot, discount_code_used, payment_id, context
            )
            
            if purchase_finalized:
                logger.info(f"✅ SUCCESS: Purchase finalization retry succeeded for payment {payment_id} on attempt {attempt + 1}")
                # Remove the pending deposit on success
                await asyncio.to_thread(remove_pending_deposit, payment_id, trigger="retry_success")
                return True
            else:
                logger.warning(f"Purchase finalization retry failed for payment {payment_id} on attempt {attempt + 1}")
                
        except Exception as e:
            logger.error(f"Exception during purchase finalization retry for payment {payment_id}, attempt {attempt + 1}: {e}", exc_info=True)
    
    # All retries failed
    logger.critical(f"🚨 CRITICAL: All {max_retries} retry attempts failed for purchase finalization payment {payment_id} user {user_id}")
    
    # Send critical alert to admin
    if get_first_primary_admin_id() and telegram_app:
        try:
            await send_message_with_retry(
                telegram_app.bot, 
                ADMIN_ID, 
                f"🚨 CRITICAL FAILURE: Purchase {payment_id} for user {user_id} FAILED after {max_retries} retries. "
                f"Payment was successful but finalization completely failed. URGENT MANUAL INTERVENTION REQUIRED!",
                parse_mode=None
            )
        except Exception as notify_error:
            logger.error(f"Failed to notify admin about critical purchase failure: {notify_error}")
    
    return False


# --- Flask Webhook Routes ---
def verify_nowpayments_signature(request_data_bytes, signature_header, secret_key):
    if not secret_key or not signature_header:
        logger.warning("IPN Secret Key or signature header missing. Cannot verify webhook.")
        return False
    try:
        # Ensure request_data_bytes is used directly if it's already the raw body
        # If you need to re-order, parse then re-serialize
        ordered_data = json.dumps(json.loads(request_data_bytes), sort_keys=True, separators=(',', ':'))
        hmac_hash = hmac.new(secret_key.encode('utf-8'), ordered_data.encode('utf-8'), hashlib.sha512).hexdigest()
        return hmac.compare_digest(hmac_hash, signature_header)
    except Exception as e:
        logger.error(f"Error during signature verification: {e}", exc_info=True)
        return False

# --- Improved Payment Processing with Retry ---
async def process_payment_with_retry(user_id: int, basket_snapshot: list, discount_code_used: str | None, payment_id: str, context: ContextTypes.DEFAULT_TYPE, max_retries: int = 3):
    """Process payment with automatic retry and better error handling"""
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Processing payment {payment_id}, attempt {attempt + 1}/{max_retries}")
            
            # First, verify the payment status with NOWPayments
            payment_status = await payment.check_payment_status(payment_id)
            if payment_status.get('error'):
                logger.error(f"Failed to verify payment status for {payment_id}: {payment_status}")
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                continue
            
            # Check if payment is actually confirmed
            if payment_status.get('payment_status') not in ['finished', 'confirmed', 'partially_paid']:
                logger.warning(f"Payment {payment_id} not confirmed yet, status: {payment_status.get('payment_status')}")
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(10 * (attempt + 1))
                continue
            
            # Process the payment
            success = await payment.process_successful_crypto_purchase(
                user_id, basket_snapshot, discount_code_used, payment_id, context
            )
            
            if success:
                logger.info(f"✅ Payment {payment_id} processed successfully on attempt {attempt + 1}")
                return True
            else:
                logger.warning(f"Payment processing failed for {payment_id} on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                
        except Exception as e:
            logger.error(f"Exception during payment processing {payment_id}, attempt {attempt + 1}: {e}", exc_info=True)
            if attempt < max_retries - 1:
                await asyncio.sleep(5 * (attempt + 1))
    
    # All retries failed
    logger.critical(f"🚨 CRITICAL: All {max_retries} attempts failed for payment {payment_id}")
    
    # Admin notification removed to reduce spam
    
    return False

@flask_app.route("/webhook", methods=['POST'])
def nowpayments_webhook():
    global telegram_app, main_loop, NOWPAYMENTS_IPN_SECRET
    
    # CRITICAL: Log every webhook attempt
    logger.info("🔍 WEBHOOK RECEIVED: NOWPayments webhook endpoint accessed")
    logger.info(f"🔍 WEBHOOK DEBUG: Request method: {request.method}")
    logger.info(f"🔍 WEBHOOK DEBUG: Request headers: {dict(request.headers)}")
    logger.info(f"🔍 WEBHOOK DEBUG: Content length: {request.content_length}")
    logger.info(f"🔍 WEBHOOK DEBUG: Remote address: {request.remote_addr}")
    
    if not telegram_app or not main_loop:
        logger.error("Webhook received but Telegram app or event loop not initialized.")
        return Response(status=503)

    # Check request size limit
    content_length = request.content_length
    if content_length and content_length > 10240:  # 10KB limit
        logger.warning(f"Webhook request too large: {content_length} bytes")
        return Response("Request too large", status=413)

    raw_body = request.get_data() # Get raw body once
    signature = request.headers.get('x-nowpayments-sig')

    # BULLETPROOF: MANDATORY signature verification for security and reliability
    if not NOWPAYMENTS_IPN_SECRET:
        logger.critical("❌ CRITICAL SECURITY ERROR: NOWPAYMENTS_IPN_SECRET not configured! Rejecting all webhooks for security.")
        return Response("IPN Secret not configured", status=500)
    
    if not signature:
        logger.warning("❌ SECURITY REJECTION: No signature header received from webhook. Rejecting for security.")
        return Response("Missing signature header", status=400)
    
    if not verify_nowpayments_signature(raw_body, signature, NOWPAYMENTS_IPN_SECRET):
        logger.warning("❌ SECURITY REJECTION: NOWPayments signature verification FAILED - webhook is fake or corrupted")
        return Response("Invalid signature", status=400)
    
    logger.info("✅ NOWPayments signature verification PASSED - webhook is authentic")

    logger.info(f"NOWPayments IPN Received (signature verification {'PASSED' if NOWPAYMENTS_IPN_SECRET and signature else 'SKIPPED'})")
    
    # Add webhook debugging
    logger.info(f"🔍 WEBHOOK DEBUG: Raw body length: {len(raw_body)} bytes")
    logger.info(f"🔍 WEBHOOK DEBUG: Signature header: {signature}")
    logger.info(f"🔍 WEBHOOK DEBUG: IPN Secret configured: {bool(NOWPAYMENTS_IPN_SECRET)}")
    logger.info(f"🔍 WEBHOOK DEBUG: Webhook URL: {WEBHOOK_URL}/webhook")


    try:
        data = json.loads(raw_body) # Parse JSON from raw body
    except json.JSONDecodeError:
        logger.warning("Webhook received non-JSON request.")
        return Response("Invalid Request: Not JSON", status=400)

    logger.info(f"NOWPayments IPN Data: {json.dumps(data)}") # Log the parsed data

    required_keys = ['payment_id', 'payment_status', 'pay_currency', 'actually_paid']
    if not all(key in data for key in required_keys):
        logger.error(f"Webhook missing required keys. Data: {data}")
        return Response("Missing required keys", status=400)

    payment_id = data.get('payment_id')
    status = data.get('payment_status')
    pay_currency = data.get('pay_currency')
    actually_paid_str = data.get('actually_paid')
    parent_payment_id = data.get('parent_payment_id')
    order_id = data.get('order_id')

    if parent_payment_id:
         logger.info(f"Ignoring child payment webhook update {payment_id} (parent: {parent_payment_id}).")
         return Response("Child payment ignored", status=200)

    if status in ['finished', 'confirmed', 'partially_paid'] and actually_paid_str is not None:
        logger.info(f"🚀 BULLETPROOF: Processing '{status}' payment: {payment_id}")
        logger.info(f"📊 BULLETPROOF: Payment details - Amount: {actually_paid_str} {pay_currency}, Order: {order_id}")
        
        # CRITICAL: Check if payment was already processed to prevent duplicate processing
        try:
            existing_pending = asyncio.run_coroutine_threadsafe(
                asyncio.to_thread(get_pending_deposit, payment_id), main_loop
            ).result(timeout=5)
            
            if not existing_pending:
                logger.warning(f"⚠️ Payment {payment_id} with status '{status}' already processed or not found. Skipping to prevent duplicate processing.")
                return Response("Payment already processed", status=200)
        except Exception as check_e:
            logger.error(f"❌ Error checking existing payment {payment_id}: {check_e}")
            # Continue processing if check fails
        
        try:
            actually_paid_decimal = Decimal(str(actually_paid_str))
            if actually_paid_decimal <= 0:
                logger.warning(f"⚠️ Ignoring webhook for payment {payment_id} with zero 'actually_paid'.")
                if status != 'confirmed': # Only remove if not yet confirmed, might be a final "zero paid" update after other partials
                    asyncio.run_coroutine_threadsafe(asyncio.to_thread(remove_pending_deposit, payment_id, trigger="zero_paid"), main_loop)
                return Response("Zero amount paid", status=200)

            # BULLETPROOF: Get pending info with timeout and retry
            pending_info = None
            for attempt in range(3):  # 3 attempts with exponential backoff
                try:
                    pending_info = asyncio.run_coroutine_threadsafe(
                        asyncio.to_thread(get_pending_deposit, payment_id), main_loop
                    ).result(timeout=10)  # 10 second timeout
                    break
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Timeout getting pending info for {payment_id}, attempt {attempt + 1}/3")
                    if attempt < 2:  # Don't sleep on last attempt
                        time.sleep(1 * (attempt + 1))  # Exponential backoff
                except Exception as e:
                    logger.error(f"❌ Error getting pending info for {payment_id}, attempt {attempt + 1}/3: {e}")
                    if attempt < 2:
                        time.sleep(1 * (attempt + 1))

            if not pending_info:
                 logger.info(f"ℹ️ Webhook Info: Pending deposit {payment_id} not found (likely already processed).")
                 return Response("Pending deposit not found", status=200)

            user_id = pending_info['user_id']
            stored_currency = pending_info['currency']
            target_eur_decimal = Decimal(str(pending_info['target_eur_amount']))
            expected_crypto_decimal = Decimal(str(pending_info.get('expected_crypto_amount', '0.0')))
            is_purchase = pending_info.get('is_purchase') == 1
            basket_snapshot = pending_info.get('basket_snapshot')
            discount_code_used = pending_info.get('discount_code_used')
            log_prefix = "PURCHASE" if is_purchase else "REFILL"

            if stored_currency.lower() != pay_currency.lower():
                 logger.error(f"Currency mismatch {log_prefix} {payment_id}. DB: {stored_currency}, Webhook: {pay_currency}")
                 asyncio.run_coroutine_threadsafe(asyncio.to_thread(remove_pending_deposit, payment_id, trigger="currency_mismatch"), main_loop)
                 return Response("Currency mismatch", status=400)

            paid_eur_equivalent = Decimal('0.0')
            # Use real-time crypto price conversion instead of proportion-based calculation
            try:
                crypto_price_future = asyncio.run_coroutine_threadsafe(
                    asyncio.to_thread(get_crypto_price_eur, pay_currency), main_loop
                )
                crypto_price_eur = crypto_price_future.result(timeout=10)
                
                if crypto_price_eur and crypto_price_eur > Decimal('0.0'):
                    paid_eur_equivalent = (actually_paid_decimal * crypto_price_eur).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    logger.info(f"{log_prefix} {payment_id}: Used real-time price {crypto_price_eur} EUR/{pay_currency.upper()} for conversion.")
                else:
                    logger.warning(f"{log_prefix} {payment_id}: Could not get real-time price for {pay_currency}. Falling back to proportion method.")
                    # Fallback to proportion method if price fetch fails
                    if expected_crypto_decimal > Decimal('0.0'):
                        proportion = actually_paid_decimal / expected_crypto_decimal
                        paid_eur_equivalent = (proportion * target_eur_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        logger.error(f"{log_prefix} {payment_id}: Cannot calculate EUR equivalent (expected crypto amount is zero).")
                        asyncio.run_coroutine_threadsafe(asyncio.to_thread(remove_pending_deposit, payment_id, trigger="zero_expected_crypto"), main_loop)
                        return Response("Cannot calculate EUR equivalent", status=400)
            except Exception as price_e:
                logger.error(f"{log_prefix} {payment_id}: Error getting crypto price: {price_e}. Using proportion fallback.")
                # Fallback to proportion method if price API fails
                if expected_crypto_decimal > Decimal('0.0'):
                    proportion = actually_paid_decimal / expected_crypto_decimal
                    paid_eur_equivalent = (proportion * target_eur_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                else:
                    logger.error(f"{log_prefix} {payment_id}: Cannot calculate EUR equivalent (expected crypto amount is zero).")
                    asyncio.run_coroutine_threadsafe(asyncio.to_thread(remove_pending_deposit, payment_id, trigger="zero_expected_crypto"), main_loop)
                    return Response("Cannot calculate EUR equivalent", status=400)

            logger.info(f"{log_prefix} {payment_id}: User {user_id} paid {actually_paid_decimal} {pay_currency}. Approx EUR value: {paid_eur_equivalent:.2f}. Target EUR: {target_eur_decimal:.2f}")

            dummy_context = ContextTypes.DEFAULT_TYPE(application=telegram_app, chat_id=user_id, user_id=user_id) if telegram_app else None
            if not dummy_context:
                logger.error(f"Cannot process {log_prefix} {payment_id}, telegram_app not ready.")
                return Response("Internal error: App not ready", status=503)

            if is_purchase:
                # CRITICAL: Check payment amount BEFORE processing to prevent underpayment exploitation
                if paid_eur_equivalent < target_eur_decimal:
                    # Underpayment: Reject payment, credit balance, don't give product
                    underpaid_eur = (target_eur_decimal - paid_eur_equivalent).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                    logger.warning(f"❌ UNDERPAYMENT REJECTED: User {user_id} paid {paid_eur_equivalent:.2f} EUR for {target_eur_decimal:.2f} EUR product. Short by {underpaid_eur:.2f} EUR. Crediting balance, NO PRODUCT DELIVERED.")
                    
                    # Credit the received amount to user's balance
                    credit_future = asyncio.run_coroutine_threadsafe(
                        credit_user_balance(user_id, paid_eur_equivalent, f"Underpayment refund on purchase {payment_id}", dummy_context),
                        main_loop
                    )
                    credit_success = False
                    try: 
                        credit_success = credit_future.result(timeout=30)
                    except Exception as e: 
                        logger.error(f"Error crediting underpayment refund for {payment_id}: {e}", exc_info=True)
                    
                    if not credit_success:
                        logger.critical(f"CRITICAL: Failed to credit balance for underpayment {payment_id} user {user_id}. Amount: {paid_eur_equivalent:.2f} EUR. MANUAL CHECK NEEDED!")
                    
                    # Send rejection message to user
                    underpay_msg = f"❌ Payment Rejected: Underpayment detected!\n\nYou paid: {paid_eur_equivalent:.2f} EUR\nRequired: {target_eur_decimal:.2f} EUR\nShort by: {underpaid_eur:.2f} EUR\n\nYour payment has been refunded to your balance. Please try again with the correct amount."
                    asyncio.run_coroutine_threadsafe(send_message_with_retry(telegram_app.bot, user_id, underpay_msg, parse_mode=None), main_loop)
                    
                    # Remove pending deposit as failed
                    asyncio.run_coroutine_threadsafe(asyncio.to_thread(remove_pending_deposit, payment_id, trigger="underpayment_rejected"), main_loop)
                    logger.info(f"Processed underpaid purchase {payment_id} for user {user_id}. Balance credited, items NOT delivered.")
                    return Response("Underpayment rejected", status=200)
                
                # Process payment (overpayment or exact payment) - only if amount is sufficient
                logger.info(f"{log_prefix} {payment_id}: Processing payment for user {user_id}. Paid {paid_eur_equivalent:.2f} EUR, target {target_eur_decimal:.2f} EUR.")
                
                # BULLETPROOF: Use the improved payment processing with retry and comprehensive error handling
                logger.info(f"🔄 BULLETPROOF: Starting purchase finalization for {payment_id} user {user_id}")
                
                finalize_future = asyncio.run_coroutine_threadsafe(
                    process_payment_with_retry(user_id, basket_snapshot, discount_code_used, payment_id, dummy_context),
                    main_loop
                )
                purchase_finalized = False
                
                # BULLETPROOF: Multiple timeout attempts with different strategies
                for attempt in range(3):
                    try: 
                        logger.info(f"🔄 BULLETPROOF: Purchase finalization attempt {attempt + 1}/3 for {payment_id}")
                        purchase_finalized = finalize_future.result(timeout=180)  # 3 minutes per attempt
                        break
                    except asyncio.TimeoutError:
                        logger.warning(f"⏰ BULLETPROOF: Purchase finalization timeout attempt {attempt + 1}/3 for {payment_id}")
                        if attempt < 2:  # Not the last attempt
                            # Try to cancel the future and restart
                            finalize_future.cancel()
                            time.sleep(5)  # Wait 5 seconds
                            # Restart the process
                            finalize_future = asyncio.run_coroutine_threadsafe(
                                process_payment_with_retry(user_id, basket_snapshot, discount_code_used, payment_id, dummy_context),
                                main_loop
                            )
                        else:
                            # Last attempt failed
                            logger.critical(f"🚨 CRITICAL TIMEOUT: Purchase finalization for {payment_id} user {user_id} failed after 3 attempts. Payment may be lost!")
                            # Notify admin immediately about timeout
                            if get_first_primary_admin_id():
                                asyncio.run_coroutine_threadsafe(
                                    send_message_with_retry(telegram_app.bot, get_first_primary_admin_id(), 
                                        f"🚨 CRITICAL TIMEOUT: Purchase {payment_id} for user {user_id} failed after 3 attempts. Payment may be lost! Manual intervention required!"),
                                    main_loop
                                )
                            # DO NOT remove pending deposit - keep it for manual recovery
                            return Response("Purchase finalization timeout - payment kept for manual recovery", status=500)
                    except Exception as e: 
                        logger.critical(f"🚨 CRITICAL ERROR: Purchase finalization for {payment_id} user {user_id} failed with error: {e}. Payment may be lost!")
                        # Notify admin about the error
                        if get_first_primary_admin_id():
                            asyncio.run_coroutine_threadsafe(
                                send_message_with_retry(telegram_app.bot, get_first_primary_admin_id(), 
                                    f"🚨 CRITICAL ERROR: Purchase {payment_id} for user {user_id} failed with error: {str(e)}. Payment may be lost! Manual intervention required!"),
                                main_loop
                            )
                        # DO NOT remove pending deposit - keep it for manual recovery
                        return Response("Purchase finalization error - payment kept for manual recovery", status=500)

                # Process payment (overpayment or exact payment)
                if purchase_finalized:
                    logger.info(f"✅ BULLETPROOF: Purchase finalization SUCCESSFUL for {payment_id} user {user_id}")
                    
                    # Handle overpayment/exact payment
                    if paid_eur_equivalent > target_eur_decimal:
                        # Overpayment: Give product + credit excess
                        overpaid_eur = (paid_eur_equivalent - target_eur_decimal).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                        logger.info(f"💰 BULLETPROOF: Overpayment detected. User {user_id} paid {paid_eur_equivalent:.2f} EUR for {target_eur_decimal:.2f} EUR product. Crediting {overpaid_eur:.2f} EUR to balance.")
                        credit_future = asyncio.run_coroutine_threadsafe(
                            credit_user_balance(user_id, overpaid_eur, f"Overpayment on purchase {payment_id}", dummy_context),
                            main_loop
                        )
                        try: 
                            credit_future.result(timeout=30)
                            # Send overpayment message to user
                            overpay_msg = f"✅ Purchase successful! You overpaid by {overpaid_eur:.2f} EUR. The excess has been added to your balance."
                            asyncio.run_coroutine_threadsafe(send_message_with_retry(telegram_app.bot, user_id, overpay_msg, parse_mode=None), main_loop)
                        except Exception as e:
                            logger.error(f"Error crediting overpayment for {payment_id}: {e}", exc_info=True)
                    else:
                        # Exact payment: Just give product
                        logger.info(f"💰 BULLETPROOF: Exact payment. User {user_id} paid exactly {paid_eur_equivalent:.2f} EUR for {target_eur_decimal:.2f} EUR product.")
                    
                    # CRITICAL: Only remove pending deposit AFTER confirming complete success
                    asyncio.run_coroutine_threadsafe(asyncio.to_thread(remove_pending_deposit, payment_id, trigger="purchase_success"), main_loop)
                    logger.info(f"✅ COMPLETE SUCCESS: {log_prefix} {payment_id} fully processed and pending record removed for user {user_id}")
                else:
                    logger.critical(f"🚨 CRITICAL: {log_prefix} {payment_id} paid, but process_successful_crypto_purchase FAILED for user {user_id}. Pending deposit NOT removed. Manual intervention required.")
                    # Notify admin about critical failure
                    if get_first_primary_admin_id():
                        asyncio.run_coroutine_threadsafe(
                            send_message_with_retry(telegram_app.bot, get_first_primary_admin_id(), 
                                f"🚨 CRITICAL: Payment {payment_id} for user {user_id} FAILED after successful payment! Manual intervention required!"),
                            main_loop
                        )
            else: # Refill
                 credited_eur_amount = paid_eur_equivalent
                 if credited_eur_amount > 0:
                     future = asyncio.run_coroutine_threadsafe(
                         payment.process_successful_refill(user_id, credited_eur_amount, payment_id, dummy_context),
                         main_loop
                     )
                     try:
                          db_update_success = future.result(timeout=30)
                          if db_update_success:
                               asyncio.run_coroutine_threadsafe(asyncio.to_thread(remove_pending_deposit, payment_id, trigger="refill_success"), main_loop)
                               logger.info(f"Successfully processed and removed pending deposit {payment_id} (Status: {status})")
                          else:
                               logger.critical(f"CRITICAL: {log_prefix} {payment_id} ({status}) processed, but process_successful_refill FAILED for user {user_id}. Pending deposit NOT removed. Manual intervention required.")
                     except asyncio.TimeoutError:
                          logger.error(f"Timeout waiting for process_successful_refill result for {payment_id}. Pending deposit NOT removed.")
                     except Exception as e:
                          logger.error(f"Error getting result from process_successful_refill for {payment_id}: {e}. Pending deposit NOT removed.", exc_info=True)
                 else:
                     logger.warning(f"{log_prefix} {payment_id} ({status}): Calculated credited EUR is zero for user {user_id}. Removing pending deposit without updating balance.")
                     asyncio.run_coroutine_threadsafe(asyncio.to_thread(remove_pending_deposit, payment_id, trigger="zero_credit"), main_loop)
        except (ValueError, TypeError) as e:
            logger.error(f"Webhook Error: Invalid number format in webhook data for {payment_id}. Error: {e}. Data: {data}")
        except Exception as e:
            logger.error(f"Webhook Error: Could not process payment update {payment_id}.", exc_info=True)
    elif status in ['failed', 'expired', 'refunded']:
        logger.warning(f"Payment {payment_id} has status '{status}'. Removing pending record.")
        pending_info_for_removal = None
        try:
            pending_info_for_removal = asyncio.run_coroutine_threadsafe(
                 asyncio.to_thread(get_pending_deposit, payment_id), main_loop
            ).result(timeout=5) 
        except Exception as e:
            logger.error(f"Error checking pending deposit for {payment_id} before removal/notification: {e}")
        asyncio.run_coroutine_threadsafe(
            asyncio.to_thread(remove_pending_deposit, payment_id, trigger="failure" if status == 'failed' else "expiry"),
            main_loop
        )
        if pending_info_for_removal and telegram_app:
            user_id = pending_info_for_removal['user_id']
            is_purchase_failure = pending_info_for_removal.get('is_purchase') == 1
            try:
                conn_lang = None; user_lang = 'en'
                try:
                    conn_lang = get_db_connection()
                    c_lang = conn_lang.cursor()
                    c_lang.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
                    lang_res = c_lang.fetchone()
                    if lang_res and lang_res['language'] in LANGUAGES: user_lang = lang_res['language']
                except Exception as lang_e: logger.error(f"Failed to get lang for user {user_id} notify: {lang_e}")
                finally:
                     if conn_lang: conn_lang.close()
                lang_data_local = LANGUAGES.get(user_lang, LANGUAGES['en'])
                if is_purchase_failure: fail_msg = lang_data_local.get("crypto_purchase_failed", "Payment Failed/Expired. Your items are no longer reserved.")
                else: fail_msg = lang_data_local.get("payment_cancelled_or_expired", "Payment Status: Your payment ({payment_id}) was cancelled or expired.").format(payment_id=payment_id)
                dummy_context = ContextTypes.DEFAULT_TYPE(application=telegram_app, chat_id=user_id, user_id=user_id)
                asyncio.run_coroutine_threadsafe(send_message_with_retry(telegram_app.bot, user_id, fail_msg, parse_mode=None), main_loop)
            except Exception as notify_e: logger.error(f"Error notifying user {user_id} about failed/expired payment {payment_id}: {notify_e}")
    else:
         logger.info(f"Webhook received for payment {payment_id} with status: {status} (ignored).")
    return Response(status=200)

@flask_app.route(f"/telegram/{TOKEN}", methods=['POST'])
async def telegram_webhook():
    global telegram_app, main_loop
    if not telegram_app or not main_loop:
        logger.error("Telegram webhook received but app/loop not ready.")
        return Response(status=503)
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, telegram_app.bot)
        asyncio.run_coroutine_threadsafe(telegram_app.process_update(update), main_loop)
        return Response(status=200)
    except json.JSONDecodeError:
        logger.error("Telegram webhook received invalid JSON.")
        return Response("Invalid JSON", status=400)
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        return Response("Internal Server Error", status=500)

@flask_app.route("/health", methods=['GET'])
def health_check():
    """Health check endpoint to verify Flask server is running"""
    logger.info("🔍 HEALTH CHECK: Health check endpoint accessed")
    return Response("OK - Flask server is running", status=200)

@flask_app.route("/webhook-test", methods=['POST'])
def webhook_test():
    """Test endpoint to verify webhook reception"""
    logger.info("🔍 WEBHOOK TEST: Test webhook received!")
    logger.info(f"🔍 WEBHOOK TEST: Headers: {dict(request.headers)}")
    logger.info(f"🔍 WEBHOOK TEST: Raw body: {request.get_data()}")
    return Response("Test webhook received successfully", status=200)

@flask_app.route("/", methods=['GET'])
def root():
    """Root endpoint to verify server is running"""
    logger.info("🔍 ROOT: Root endpoint accessed")
    return Response("Payment Bot Server is Running! Webhook: /webhook", status=200)

def main() -> None:
    global telegram_app, main_loop
    logger.info("🔧 Starting bot...")
    logger.info("🔧 Initializing database...")
    init_db()
    logger.info("✅ Database initialized successfully")
    
    logger.info("🔧 Initializing module-specific tables...")
    try:
        init_welcome_tables()
        logger.info("✅ Welcome tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize welcome tables: {e}", exc_info=True)
    
    try:
        init_interactive_welcome_tables()
        logger.info("✅ Interactive welcome tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize interactive welcome tables: {e}", exc_info=True)
    
    try:
        init_price_editor_tables()
        logger.info("✅ Price editor tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize price editor tables: {e}", exc_info=True)
    
    try:
        init_marketing_tables()
        logger.info("✅ Marketing and UI theme tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize marketing tables: {e}", exc_info=True)
    
    # 🚀 YOLO MODE: INITIALIZE REFERRAL SYSTEM!
    try:
        from referral_system import init_referral_tables
        init_referral_tables()
        logger.info("✅ Referral system tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize referral tables: {e}", exc_info=True)
    
    try:
        logger.info("🔧 About to call init_enhanced_auto_ads_tables()...")
        init_enhanced_auto_ads_tables()
        logger.info("✅ Auto ads tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize auto ads tables: {e}", exc_info=True)
    
    logger.info("🔧 Finished auto ads initialization, continuing with main flow...")
    
    logger.info("🔧 About to call load_all_data()...")
    logger.info("🔧 Loading all data...")
    try:
        load_all_data()
        logger.info("✅ All data loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load data: {e}", exc_info=True)
    logger.info("🔧 Setting up Telegram application...")
    defaults = Defaults(parse_mode=None, block=False)
    app_builder = ApplicationBuilder().token(TOKEN).defaults(defaults).job_queue(JobQueue())
    app_builder.post_init(post_init)
    app_builder.post_shutdown(post_shutdown)
    application = app_builder.build()
    logger.info("✅ Telegram application built successfully")
    
    logger.info("🔧 Adding command handlers...")
    application.add_handler(CommandHandler("start", start_command_wrapper)) # Use wrapped start with ban check
    application.add_handler(CommandHandler("admin", admin_command_wrapper)) # Use wrapped admin with ban check
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(
        (filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL,
        handle_message
    ))
    application.add_error_handler(error_handler)
    logger.info("✅ All handlers added successfully")
    
    telegram_app = application
    main_loop = asyncio.get_event_loop()
    logger.info("✅ Event loop created successfully")
    if BASKET_TIMEOUT > 0:
        job_queue = application.job_queue
        if job_queue:
            logger.info(f"Setting up background jobs...")
            # Basket cleanup job (reduced frequency to 5 minutes for better performance)
            job_queue.run_repeating(clear_expired_baskets_job_wrapper, interval=timedelta(minutes=5), first=timedelta(seconds=10), name="clear_baskets")
            # Payment timeout cleanup job (runs every 10 minutes for better stability)
            job_queue.run_repeating(clean_expired_payments_job_wrapper, interval=timedelta(minutes=10), first=timedelta(minutes=1), name="clean_payments")
            # Abandoned reservation cleanup job (runs every 3 minutes for faster response)
            job_queue.run_repeating(clean_abandoned_reservations_job_wrapper, interval=timedelta(minutes=3), first=timedelta(minutes=2), name="clean_abandoned")
            
            
            # Stock management: Low stock alerts (runs every hour)
            job_queue.run_repeating(stock_alerts_job_wrapper, interval=timedelta(hours=1), first=timedelta(minutes=10), name="stock_alerts")
            
            # Enhanced auto ads: No background job needed (campaigns run on-demand)
            
            logger.info("Background jobs setup complete (basket cleanup + payment timeout + abandoned reservations + stock alerts + auto ads).")
        else: logger.warning("Job Queue is not available. Background jobs skipped.")
    else: logger.warning("BASKET_TIMEOUT is not positive. Skipping background job setup.")

    # Enhanced auto ads system is initialized via database init
    logger.info("Enhanced auto ads system tables initialized via database init")
    
    logger.info("🔧 About to define setup_webhooks_and_run function...")

    async def setup_webhooks_and_run():
        nonlocal application
        logger.info("🔧 Initializing application...")
        try:
            await application.initialize()
            logger.info("✅ Application initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize application: {e}")
            return
        
        logger.info(f"🔧 Setting Telegram webhook to: {WEBHOOK_URL}/telegram/{TOKEN}")
        try:
            webhook_result = await application.bot.set_webhook(url=f"{WEBHOOK_URL}/telegram/{TOKEN}", allowed_updates=Update.ALL_TYPES)
            if webhook_result:
                logger.info("✅ Telegram webhook set successfully.")
            else:
                logger.error("❌ Failed to set Telegram webhook.")
                return
        except Exception as e:
            logger.error(f"❌ Error setting webhook: {e}")
            return
        
        logger.info("🔧 Starting Telegram application...")
        try:
            await application.start()
            logger.info("✅ Telegram application started (webhook mode).")
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram application: {e}")
            return
        
        port = int(os.environ.get("PORT", 10000))
        logger.info(f"🔧 Starting Flask server on port {port}...")
        
        def run_flask():
            try:
                logger.info("🔧 Flask server starting...")
                flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
                logger.info("✅ Flask server running")
            except Exception as e:
                logger.error(f"❌ Flask server error: {e}")
        
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info(f"✅ Flask server started in background thread on port {port}.")
        
        # Wait a moment for Flask to start
        await asyncio.sleep(2)
        
        # Test webhook endpoint
        try:
            import requests
            test_url = f"{WEBHOOK_URL}/health"
            logger.info(f"🔧 Testing health check at: {test_url}")
            response = requests.get(test_url, timeout=10)
            logger.info(f"✅ Health check successful: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Health check failed: {e}")
        
        logger.info("🔧 Main thread entering keep-alive loop...")
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals: main_loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s, main_loop, application)))
        try:
            while True: 
                logger.info("🔄 Keep-alive loop running...")
                await asyncio.sleep(3600)
        except asyncio.CancelledError: 
            logger.info("Keep-alive loop cancelled.")
        finally: 
            logger.info("Exiting keep-alive loop.")

    async def shutdown(signal, loop, application):
        logger.info(f"Received exit signal {signal.name}...")
        logger.info("Shutting down application...")
        if application:
            await application.stop()
            await application.shutdown()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        logger.info(f"Cancelling {len(tasks)} outstanding tasks")
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Flushing metrics")
        loop.stop()

    try:
        logger.info("🔧 About to start main event loop...")
        logger.info("🔧 Starting main event loop...")
        main_loop.run_until_complete(setup_webhooks_and_run())
        logger.info("✅ Main event loop completed successfully")
    except (KeyboardInterrupt, SystemExit) as e:
        logger.info(f"Shutdown initiated by {type(e).__name__}.")
    except Exception as e:
        logger.critical(f"❌ Critical error in main execution loop: {e}", exc_info=True)
        logger.critical(f"❌ Error type: {type(e).__name__}")
        logger.critical(f"❌ Error details: {str(e)}")
    finally:
        logger.info("Main loop finished or interrupted.")
        if main_loop.is_running():
            logger.info("Stopping event loop.") 
            main_loop.stop()
        logger.info("Bot shutdown complete.")

if __name__ == '__main__':
    main()

# --- END OF FILE main.py ---
