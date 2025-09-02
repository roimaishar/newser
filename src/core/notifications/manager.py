#!/usr/bin/env python3
"""
Unified notification manager.

Orchestrates notifications across multiple channels with intelligent routing,
scheduling, and deduplication.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(Enum):
    """Available notification channels."""
    SLACK = "slack"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"


class NotificationManager:
    """
    Unified notification manager for all notification channels.
    
    Handles routing, scheduling, deduplication, and delivery tracking.
    """
    
    def __init__(self):
        """Initialize notification manager."""
        self.channels = {}
        self.sent_notifications = set()  # Simple deduplication
        self.default_channels = {NotificationChannel.SLACK}
    
    def register_channel(self, channel_type: NotificationChannel, channel_instance):
        """
        Register a notification channel.
        
        Args:
            channel_type: Type of channel
            channel_instance: Channel implementation
        """
        self.channels[channel_type] = channel_instance
        logger.info(f"Registered notification channel: {channel_type.value}")
    
    def send_notification(
        self,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: Optional[Set[NotificationChannel]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[NotificationChannel, bool]:
        """
        Send notification through specified channels.
        
        Args:
            message: Notification message
            priority: Message priority
            channels: Channels to send through (uses default if None)
            metadata: Additional metadata for formatting
            
        Returns:
            Dictionary mapping channels to success status
        """
        if channels is None:
            channels = self.default_channels
        
        # Generate notification ID for deduplication
        notification_id = self._generate_notification_id(message, metadata)
        
        if notification_id in self.sent_notifications:
            logger.info(f"Skipping duplicate notification: {notification_id}")
            return {}
        
        results = {}
        
        for channel in channels:
            if channel not in self.channels:
                logger.warning(f"Channel {channel.value} not registered, skipping")
                results[channel] = False
                continue
            
            try:
                channel_instance = self.channels[channel]
                success = self._send_to_channel(
                    channel_instance, channel, message, priority, metadata
                )
                results[channel] = success
                
                if success:
                    logger.info(f"Successfully sent notification via {channel.value}")
                else:
                    logger.error(f"Failed to send notification via {channel.value}")
                    
            except Exception as e:
                logger.error(f"Error sending notification via {channel.value}: {e}")
                results[channel] = False
        
        # Mark as sent if at least one channel succeeded
        if any(results.values()):
            self.sent_notifications.add(notification_id)
        
        return results
    
    def send_news_summary(
        self,
        articles: List[Dict[str, Any]],
        analysis_result: Optional[Any] = None,
        channels: Optional[Set[NotificationChannel]] = None
    ) -> Dict[NotificationChannel, bool]:
        """
        Send formatted news summary.
        
        Args:
            articles: News articles to summarize
            analysis_result: Optional analysis result
            channels: Channels to send through
            
        Returns:
            Dictionary mapping channels to success status
        """
        if channels is None:
            channels = self.default_channels
        
        results = {}
        
        for channel in channels:
            if channel not in self.channels:
                logger.warning(f"Channel {channel.value} not registered for news summary")
                results[channel] = False
                continue
            
            try:
                channel_instance = self.channels[channel]
                
                # Use channel-specific news summary method if available
                if hasattr(channel_instance, 'send_news_summary'):
                    success = channel_instance.send_news_summary(
                        articles, 
                        analysis=None,  # Legacy parameter
                        hebrew_result=analysis_result
                    )
                else:
                    # Fallback to generic message
                    summary_message = self._format_news_summary(articles, analysis_result)
                    success = self._send_to_channel(
                        channel_instance, channel, summary_message, 
                        NotificationPriority.NORMAL, {}
                    )
                
                results[channel] = success
                
            except Exception as e:
                logger.error(f"Error sending news summary via {channel.value}: {e}")
                results[channel] = False
        
        return results
    
    def send_alert(
        self,
        message: str,
        severity: str = "info",
        channels: Optional[Set[NotificationChannel]] = None
    ) -> Dict[NotificationChannel, bool]:
        """
        Send alert notification.
        
        Args:
            message: Alert message
            severity: Alert severity (info, warning, error, critical)
            channels: Channels to send through
            
        Returns:
            Dictionary mapping channels to success status
        """
        # Map severity to priority
        priority_map = {
            "info": NotificationPriority.LOW,
            "warning": NotificationPriority.NORMAL,
            "error": NotificationPriority.HIGH,
            "critical": NotificationPriority.URGENT
        }
        
        priority = priority_map.get(severity, NotificationPriority.NORMAL)
        
        if channels is None:
            # For alerts, use all available channels for high priority
            if priority in (NotificationPriority.HIGH, NotificationPriority.URGENT):
                channels = set(self.channels.keys())
            else:
                channels = self.default_channels
        
        results = {}
        
        for channel in channels:
            if channel not in self.channels:
                continue
            
            try:
                channel_instance = self.channels[channel]
                
                # Use channel-specific alert method if available
                if hasattr(channel_instance, 'send_alert'):
                    success = channel_instance.send_alert(message, severity)
                else:
                    # Fallback to generic message with alert prefix
                    alert_message = f"🚨 ALERT ({severity.upper()}): {message}"
                    success = self._send_to_channel(
                        channel_instance, channel, alert_message, priority, {}
                    )
                
                results[channel] = success
                
            except Exception as e:
                logger.error(f"Error sending alert via {channel.value}: {e}")
                results[channel] = False
        
        return results
    
    def _send_to_channel(
        self,
        channel_instance,
        channel_type: NotificationChannel,
        message: str,
        priority: NotificationPriority,
        metadata: Dict[str, Any]
    ) -> bool:
        """Send message to a specific channel."""
        # Try different send methods based on channel capabilities
        send_methods = ['send_message', 'send', 'notify']
        
        for method_name in send_methods:
            if hasattr(channel_instance, method_name):
                method = getattr(channel_instance, method_name)
                try:
                    return method(message)
                except Exception as e:
                    logger.debug(f"Method {method_name} failed for {channel_type.value}: {e}")
                    continue
        
        logger.error(f"No compatible send method found for channel {channel_type.value}")
        return False
    
    def _generate_notification_id(self, message: str, metadata: Optional[Dict[str, Any]]) -> str:
        """Generate unique ID for notification deduplication."""
        import hashlib
        
        # Create hash from message content and key metadata
        content = message
        if metadata:
            # Include relevant metadata for uniqueness
            relevant_keys = ['timestamp', 'articles_count', 'analysis_type']
            metadata_str = '|'.join(
                f"{k}:{v}" for k, v in metadata.items() 
                if k in relevant_keys
            )
            content += f"|{metadata_str}"
        
        return hashlib.md5(content.encode()).hexdigest()
    
    def _format_news_summary(self, articles: List[Dict[str, Any]], analysis_result: Any) -> str:
        """Fallback formatting for news summary."""
        summary = f"📰 News Update: {len(articles)} articles"
        
        if analysis_result and hasattr(analysis_result, 'summary'):
            summary += f"\n\n{analysis_result.summary}"
        
        return summary
    
    def clear_sent_notifications(self):
        """Clear sent notifications cache (for testing)."""
        self.sent_notifications.clear()
    
    def get_channel_status(self) -> Dict[str, Any]:
        """Get status of all registered channels."""
        status = {}
        
        for channel_type, channel_instance in self.channels.items():
            try:
                # Try to get health status if available
                if hasattr(channel_instance, 'health_check'):
                    channel_status = channel_instance.health_check()
                elif hasattr(channel_instance, 'test_connection'):
                    channel_status = {
                        'available': channel_instance.test_connection()
                    }
                else:
                    channel_status = {
                        'available': True,
                        'note': 'No health check available'
                    }
                
                status[channel_type.value] = channel_status
                
            except Exception as e:
                status[channel_type.value] = {
                    'available': False,
                    'error': str(e)
                }
        
        return status