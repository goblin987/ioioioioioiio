"""
Running Ads Display Handler
Static button - does nothing when clicked (just shows the ad text)
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def handle_running_ads_display(update: Update, context: ContextTypes.DEFAULT_TYPE, params=None):
    """Handle running ads button click - do nothing (static display only)"""
    query = update.callback_query
    
    # Just answer the callback to remove loading state
    # Don't show any message or change anything
    await query.answer("📢 Running Ads", show_alert=False)
    
    # Button is purely decorative - no action needed
    logger.info(f"User {query.from_user.id} clicked running ads button (static display)")

