"""
Auto Ads Bump Service (Simplified for Botshop)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Service for managing automated ad campaigns with scheduling and anti-ban protection.
Simplified version adapted for botshop PostgreSQL integration.

Author: TgCF Pro Team (Adapted for Botshop)
License: MIT
Version: 2.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from auto_ads_database import AutoAdsDatabase
from auto_ads_telethon_manager import auto_ads_telethon_manager
from auto_ads_config import AutoAdsConfig

logger = logging.getLogger(__name__)

class AutoAdsBumpService:
    """Service for managing automated ad campaigns"""
    
    def __init__(self, bot_instance=None):
        self.db = AutoAdsDatabase()
        self.telethon_manager = auto_ads_telethon_manager
        self.bot_instance = bot_instance
        self.active_campaigns = {}
    
    def get_user_campaigns(self, user_id: int) -> List[Dict]:
        """Get all campaigns for a user"""
        return self.db.get_user_campaigns(user_id)
    
    def get_campaign(self, campaign_id: int) -> Optional[Dict]:
        """Get campaign by ID"""
        return self.db.get_campaign(campaign_id)
    
    def delete_campaign(self, campaign_id: int) -> bool:
        """Delete a campaign"""
        try:
            self.db.delete_campaign(campaign_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting campaign: {e}")
            return False
    
    def toggle_campaign(self, campaign_id: int) -> bool:
        """Toggle campaign active status"""
        try:
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                return False
            
            new_status = not campaign['is_active']
            self.db.update_campaign_status(campaign_id, new_status)
            return True
        except Exception as e:
            logger.error(f"Error toggling campaign: {e}")
            return False
    
    def add_campaign(self, user_id: int, account_id: int, campaign_name: str,
                    ad_content: any, target_chats: list, buttons: list = None,
                    schedule_type: str = 'once', schedule_time: str = None) -> int:
        """Add a new campaign"""
        return self.db.add_campaign(
            user_id=user_id,
            account_id=account_id,
            campaign_name=campaign_name,
            ad_content=ad_content,
            target_chats=target_chats,
            buttons=buttons,
            schedule_type=schedule_type,
            schedule_time=schedule_time
        )
    
    async def execute_campaign(self, campaign_id: int) -> Dict[str, any]:
        """Execute a campaign immediately"""
        results = {
            'success': False,
            'message': '',
            'sent_count': 0,
            'failed_count': 0,
            'details': []
        }
        
        try:
            # Get campaign
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                results['message'] = "Campaign not found"
                return results
            
            # Get account
            account = self.db.get_account(campaign['account_id'])
            if not account:
                results['message'] = "Account not found"
                return results
            
            # Get Telethon client
            client = await self.telethon_manager.get_validated_client(account)
            if not client:
                results['message'] = "Failed to connect account"
                return results
            
            # Extract campaign data
            ad_content = campaign['ad_content']
            target_chats = campaign['target_chats']
            buttons = campaign.get('buttons')
            
            # Execute based on content type
            if isinstance(ad_content, dict):
                if ad_content.get('bridge_channel'):
                    # Forward from bridge channel
                    results = await self._execute_bridge_forward(
                        client, ad_content, target_chats, buttons
                    )
                elif ad_content.get('forwarded_message'):
                    # Forward existing message
                    results = await self._execute_message_forward(
                        client, ad_content, target_chats
                    )
                else:
                    # Send text message
                    text = ad_content.get('text', '')
                    results = await self._execute_text_message(
                        client, text, target_chats, buttons
                    )
            else:
                # Simple text message
                results = await self._execute_text_message(
                    client, str(ad_content), target_chats, buttons
                )
            
            # Update campaign stats
            if results['success']:
                self.db.update_campaign_last_run(campaign_id)
                results['message'] = f"Campaign executed: {results['sent_count']} successful, {results['failed_count']} failed"
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing campaign {campaign_id}: {e}")
            results['message'] = f"Error: {str(e)}"
            return results
    
    async def _execute_bridge_forward(self, client, ad_content: dict, 
                                     target_chats: list, buttons: list = None) -> Dict:
        """Execute campaign by forwarding from bridge channel"""
        results = {'success': True, 'sent_count': 0, 'failed_count': 0, 'details': []}
        
        try:
            source_chat = ad_content['bridge_channel_entity']
            message_id = ad_content['bridge_message_id']
            
            for target_chat in target_chats:
                try:
                    # Add delay between messages (anti-ban)
                    if results['sent_count'] > 0:
                        delay = self._get_safe_delay()
                        logger.info(f"Waiting {delay:.1f}s before next message...")
                        await asyncio.sleep(delay)
                    
                    # Forward message
                    target_entity = await client.get_entity(target_chat)
                    source_entity = await client.get_entity(source_chat)
                    
                    forwarded = await client.forward_messages(
                        entity=target_entity,
                        messages=message_id,
                        from_peer=source_entity
                    )
                    
                    if forwarded:
                        results['sent_count'] += 1
                        results['details'].append(f"✅ {target_chat}")
                        logger.info(f"✅ Forwarded to {target_chat}")
                    else:
                        results['failed_count'] += 1
                        results['details'].append(f"❌ {target_chat}")
                        
                except Exception as e:
                    results['failed_count'] += 1
                    results['details'].append(f"❌ {target_chat}: {str(e)}")
                    logger.error(f"Failed to forward to {target_chat}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in bridge forward execution: {e}")
            results['success'] = False
            results['message'] = str(e)
            return results
    
    async def _execute_message_forward(self, client, ad_content: dict, 
                                      target_chats: list) -> Dict:
        """Execute campaign by forwarding existing message"""
        results = {'success': True, 'sent_count': 0, 'failed_count': 0, 'details': []}
        
        try:
            source_chat = ad_content['original_chat_id']
            message_id = ad_content['original_message_id']
            
            for target_chat in target_chats:
                try:
                    # Add delay between messages
                    if results['sent_count'] > 0:
                        delay = self._get_safe_delay()
                        await asyncio.sleep(delay)
                    
                    # Forward message
                    success = await self.telethon_manager.forward_message_to_targets(
                        client, source_chat, message_id, [target_chat]
                    )
                    
                    if success['successful']:
                        results['sent_count'] += 1
                        results['details'].append(f"✅ {target_chat}")
                    else:
                        results['failed_count'] += 1
                        results['details'].append(f"❌ {target_chat}")
                        
                except Exception as e:
                    results['failed_count'] += 1
                    results['details'].append(f"❌ {target_chat}: {str(e)}")
                    logger.error(f"Failed to forward to {target_chat}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in message forward execution: {e}")
            results['success'] = False
            results['message'] = str(e)
            return results
    
    async def _execute_text_message(self, client, text: str, 
                                   target_chats: list, buttons: list = None) -> Dict:
        """Execute campaign by sending text message"""
        results = {'success': True, 'sent_count': 0, 'failed_count': 0, 'details': []}
        
        try:
            for target_chat in target_chats:
                try:
                    # Add delay between messages
                    if results['sent_count'] > 0:
                        delay = self._get_safe_delay()
                        await asyncio.sleep(delay)
                    
                    # Send message
                    success = await self.telethon_manager.send_text_message(
                        client, target_chat, text, buttons
                    )
                    
                    if success:
                        results['sent_count'] += 1
                        results['details'].append(f"✅ {target_chat}")
                    else:
                        results['failed_count'] += 1
                        results['details'].append(f"❌ {target_chat}")
                        
                except Exception as e:
                    results['failed_count'] += 1
                    results['details'].append(f"❌ {target_chat}: {str(e)}")
                    logger.error(f"Failed to send to {target_chat}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in text message execution: {e}")
            results['success'] = False
            results['message'] = str(e)
            return results
    
    def _get_safe_delay(self) -> float:
        """Get a safe random delay between messages (anti-ban)"""
        min_delay = AutoAdsConfig.MIN_DELAY_BETWEEN_MESSAGES
        max_delay = AutoAdsConfig.MAX_DELAY_BETWEEN_MESSAGES
        
        # Use random delay for unpredictable timing
        base_delay = random.uniform(min_delay, max_delay)
        
        # Add occasional longer pauses (10% chance of 2x delay)
        if random.random() < 0.1:
            base_delay *= 2
            logger.info(f"🛡️ ANTI-BAN: Extended delay for natural behavior")
        
        return base_delay
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.telethon_manager.cleanup()

