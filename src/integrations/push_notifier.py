#!/usr/bin/env python3
"""
Push notification service for mobile alerts.

Supports multiple push notification providers (Firebase, APNs, OneSignal)
with optimized formatting for mobile consumption.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests

from .notification_formatter import NotificationFormatter

logger = logging.getLogger(__name__)

class PushNotifier:
    """Handles push notifications via various providers."""
    
    def __init__(self, provider: str = "onesignal"):
        """
        Initialize push notifier.
        
        Args:
            provider: Push service provider ('onesignal', 'firebase', 'apns')
        """
        self.provider = provider.lower()
        self.formatter = NotificationFormatter()
        
        # Provider-specific configuration
        if self.provider == "onesignal":
            self.app_id = os.getenv('ONESIGNAL_APP_ID')
            self.api_key = os.getenv('ONESIGNAL_API_KEY')
            self.endpoint = "https://onesignal.com/api/v1/notifications"
        elif self.provider == "firebase":
            self.server_key = os.getenv('FIREBASE_SERVER_KEY')
            self.endpoint = "https://fcm.googleapis.com/fcm/send"
        
        self.timeout = 10
    
    def send_news_notification(self, articles: List[Dict], hebrew_result=None, 
                             style: str = "breaking", segments: Optional[List[str]] = None) -> bool:
        """
        Send news push notification.
        
        Args:
            articles: List of news articles
            hebrew_result: Hebrew analysis result
            style: Notification style ('breaking', 'summary', 'minimal')
            segments: User segments to target (optional)
        """
        if not articles:
            return True  # No notification needed
        
        # Format message for push
        message = self.formatter.format_push_notification(articles, hebrew_result, style)
        
        # Determine urgency
        urgency = self.formatter.get_urgency_level(articles, hebrew_result)
        
        # Send based on provider
        if self.provider == "onesignal":
            return self._send_onesignal(message, urgency, segments)
        elif self.provider == "firebase":
            return self._send_firebase(message, urgency, segments)
        else:
            logger.warning(f"Unsupported push provider: {self.provider}")
            return False
    
    def _send_onesignal(self, message: str, urgency: str, segments: Optional[List[str]]) -> bool:
        """Send via OneSignal."""
        if not self.app_id or not self.api_key:
            logger.warning("OneSignal credentials not configured")
            return False
        
        # Priority mapping
        priority_map = {
            "critical": 10,
            "high": 8,
            "medium": 5,
            "low": 3
        }
        
        payload = {
            "app_id": self.app_id,
            "contents": {"he": message, "en": message},
            "headings": {"he": "חדשות ישראל", "en": "Israel News"},
            "priority": priority_map.get(urgency, 5),
            "included_segments": segments or ["All"],
            "android_channel_id": "news_updates",
            "ios_category": "NEWS_CATEGORY",
            "data": {
                "type": "news_update",
                "urgency": urgency,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Add sound and vibration for urgent news
        if urgency in ["critical", "high"]:
            payload["android_sound"] = "urgent_news"
            payload["ios_sound"] = "urgent_news.wav"
            payload["android_vibration_pattern"] = [100, 50, 100]
        
        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                verify=True
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Push notification sent to {result.get('recipients', 0)} devices")
                return True
            else:
                logger.error(f"OneSignal API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send OneSignal notification: {e}")
            return False
    
    def _send_firebase(self, message: str, urgency: str, segments: Optional[List[str]]) -> bool:
        """Send via Firebase Cloud Messaging."""
        if not self.server_key:
            logger.warning("Firebase server key not configured")
            return False
        
        # Priority mapping
        priority = "high" if urgency in ["critical", "high"] else "normal"
        
        payload = {
            "to": "/topics/news_updates",  # Default topic
            "priority": priority,
            "notification": {
                "title": "חדשות ישראל",
                "body": message,
                "icon": "ic_news",
                "sound": "urgent_news" if urgency in ["critical", "high"] else "default",
                "click_action": "NEWS_ACTIVITY"
            },
            "data": {
                "type": "news_update",
                "urgency": urgency,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        headers = {
            "Authorization": f"key={self.server_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                verify=True
            )
            
            if response.status_code == 200:
                logger.info("Firebase push notification sent successfully")
                return True
            else:
                logger.error(f"Firebase API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Firebase notification: {e}")
            return False
    
    def send_test_notification(self, test_message: str = None) -> bool:
        """Send test notification."""
        message = test_message or f"🧪 Test notification - {datetime.now().strftime('%H:%M')}"
        
        if self.provider == "onesignal":
            return self._send_onesignal(message, "low", ["Test Users"])
        elif self.provider == "firebase":
            return self._send_firebase(message, "low", None)
        
        return False
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification delivery statistics (if supported by provider)."""
        # This would require additional API calls to get delivery stats
        # Implementation depends on specific provider capabilities
        return {
            "provider": self.provider,
            "configured": self._is_configured(),
            "last_sent": None,  # Would track in database
            "delivery_rate": None  # Would get from provider API
        }
    
    def _is_configured(self) -> bool:
        """Check if push service is properly configured."""
        if self.provider == "onesignal":
            return bool(self.app_id and self.api_key)
        elif self.provider == "firebase":
            return bool(self.server_key)
        return False
