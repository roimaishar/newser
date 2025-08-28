#!/usr/bin/env python3
"""
Smart notification formatting based on content analysis.

Automatically selects optimal format based on urgency, time, content type, and user preferences.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SmartFormatter:
    """Intelligently formats notifications based on context."""
    
    def __init__(self):
        self.urgency_keywords = ['פיגוע', 'רצח', 'מלחמה', 'טיל', 'פצוע', 'הרוג', 'חירום']
        self.political_keywords = ['ממשלה', 'כנסת', 'בחירות', 'מפלגה', 'הפגנה']
        self.security_keywords = ['ביטחון', 'צבא', 'משטרה', 'שב"כ', 'מוסד']
    
    def auto_select_push_format(self, articles: List[Dict], hebrew_result=None, user_prefs: Dict = None) -> str:
        """
        Automatically select best push notification format.
        
        Args:
            articles: News articles
            hebrew_result: Analysis result
            user_prefs: User preferences
            
        Returns:
            Format style name
        """
        if not articles:
            return "minimal"
        
        # Check urgency level
        urgency_score = self._calculate_urgency(articles)
        
        # Check time of day
        hour = datetime.now().hour
        is_business_hours = 8 <= hour <= 18
        
        # User preference override
        if user_prefs and 'push_format' in user_prefs:
            return user_prefs['push_format']
        
        # Auto-selection logic
        if urgency_score >= 8:  # Critical news
            return "urgent"
        elif urgency_score >= 6:  # Important news
            return "headlines" if is_business_hours else "topic"
        elif len(articles) >= 5:  # Many articles
            return "topic"
        else:
            return "minimal"
    
    def auto_select_slack_format(self, articles: List[Dict], hebrew_result=None, user_prefs: Dict = None) -> str:
        """
        Automatically select best Slack format.
        
        Args:
            articles: News articles
            hebrew_result: Analysis result
            user_prefs: User preferences
            
        Returns:
            Format style name
        """
        if not articles:
            return "headlines_first"
        
        # Check if this is a scheduled update vs ad-hoc
        hour = datetime.now().hour
        is_hourly_update = hour % 1 == 0  # Rough approximation
        
        # User preference override
        if user_prefs and 'slack_format' in user_prefs:
            return user_prefs['slack_format']
        
        # Auto-selection logic
        urgency_score = self._calculate_urgency(articles)
        
        if urgency_score >= 8:  # Breaking news
            return "headlines_first"
        elif len(articles) >= 7:  # Many articles
            return "expandable"
        elif is_hourly_update:  # Regular updates
            return "executive"
        else:
            return "headlines_first"
    
    def _calculate_urgency(self, articles: List[Dict]) -> int:
        """Calculate urgency score 1-10 based on content."""
        if not articles:
            return 1
        
        urgency_score = 0
        
        for article in articles:
            title = article.get('title', '').lower()
            
            # Check for urgent keywords
            if any(keyword in title for keyword in self.urgency_keywords):
                urgency_score += 3
            
            # Check for security content
            if any(keyword in title for keyword in self.security_keywords):
                urgency_score += 2
            
            # Check for political content
            if any(keyword in title for keyword in self.political_keywords):
                urgency_score += 1
        
        # Normalize by article count
        avg_urgency = urgency_score / len(articles)
        
        # Scale to 1-10
        return min(10, max(1, int(avg_urgency * 2) + len(articles) // 2))
    
    def get_optimal_timing(self, urgency_score: int) -> Dict[str, Any]:
        """Get optimal notification timing based on urgency."""
        if urgency_score >= 8:
            return {
                "immediate": True,
                "quiet_hours_override": True,
                "retry_failed": True
            }
        elif urgency_score >= 6:
            return {
                "immediate": True,
                "quiet_hours_override": False,
                "retry_failed": True
            }
        else:
            return {
                "immediate": False,
                "quiet_hours_override": False,
                "retry_failed": False,
                "batch_with_next": True
            }
