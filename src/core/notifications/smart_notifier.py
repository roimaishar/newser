#!/usr/bin/env python3
"""
Smart Notification System - Orchestrates 3-bucket analysis and notification decisions.

Combines:
- 3-bucket data preparation (fresh, since_last, previous_24h)  
- LLM analysis using notification prompt
- Notification scheduling logic
- Direct message sending
"""

import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ..state_manager import StateManager
from .scheduler import NotificationScheduler, format_time_since_last_notification
from ..analysis.hebrew.prompts import get_notification_prompt
# JSON validation not needed for this implementation

logger = logging.getLogger(__name__)


@dataclass
class NotificationDecision:
    """Result from smart notification analysis."""
    should_notify: bool
    compact_push: str
    full_message: str
    fresh_articles_count: int
    since_last_count: int
    previous_24h_count: int
    time_since_last_notification: str
    analysis_timestamp: datetime
    raw_llm_response: Dict[str, Any]


class SmartNotifier:
    """
    Orchestrates intelligent notification system with 3-bucket analysis.
    
    Workflow:
    1. Prepare 3 data buckets (fresh, since_last, previous_24h)
    2. Send to LLM with notification prompt  
    3. Parse LLM decision and content
    4. Apply scheduling logic programmatically
    5. Send notifications if approved
    """
    
    def __init__(self, 
                 state_manager: StateManager,
                 openai_client=None,
                 scheduler: Optional[NotificationScheduler] = None):
        """Initialize smart notifier."""
        self.state_manager = state_manager
        self.openai_client = openai_client
        self.scheduler = scheduler or NotificationScheduler()
        
        if self.openai_client is None:
            from integrations.openai_client import OpenAIClient
            self.openai_client = OpenAIClient()
    
    def prepare_3_bucket_data(self, fresh_articles: List[Dict[str, Any]]) -> Tuple[List, List, List, str]:
        """
        Prepare the 3 buckets of news data for LLM analysis.
        
        Args:
            fresh_articles: Articles just scraped from RSS
            
        Returns:
            (fresh_articles, since_last_notification, previous_24h, time_since_last)
        """
        # Get last notification timestamp
        last_notification_time = self.state_manager.get_last_notification_timestamp()
        
        # If no previous notifications, set a reasonable default (6 hours ago)
        if last_notification_time is None:
            last_notification_time = datetime.now(timezone.utc) - timedelta(hours=6)
            logger.info("No previous notification timestamp found, using 6 hours ago as baseline")
        
        # Get all articles from last 24 hours from database
        all_recent_articles = self.state_manager.get_articles_since_timestamp(
            datetime.now(timezone.utc) - timedelta(hours=24), 
            hours_limit=24
        )
        
        # Split into buckets
        since_last_notification = []
        previous_24_hours = []
        
        for article in all_recent_articles:
            # Parse article timestamp
            article_time = None
            if isinstance(article, dict):
                if 'created_at' in article:
                    article_time = article['created_at']
                elif 'published_date' in article:
                    article_time = article['published_date']
            
            if article_time:
                if isinstance(article_time, str):
                    try:
                        article_time = datetime.fromisoformat(article_time.replace('Z', '+00:00'))
                    except Exception:
                        continue
                
                if article_time > last_notification_time:
                    since_last_notification.append(article)
                else:
                    previous_24_hours.append(article)
        
        # Format time since last notification for LLM
        time_since_last = format_time_since_last_notification(last_notification_time)
        
        logger.info(f"Prepared buckets: {len(fresh_articles)} fresh, "
                   f"{len(since_last_notification)} since last notification, "
                   f"{len(previous_24_hours)} previous 24h")
        
        return fresh_articles, since_last_notification, previous_24_hours, time_since_last
    
    def analyze_with_llm(self, 
                        fresh_articles: List[Dict[str, Any]],
                        since_last_notification: List[Dict[str, Any]], 
                        previous_24_hours: List[Dict[str, Any]],
                        time_since_last: str) -> Optional[NotificationDecision]:
        """Send 3-bucket data to LLM for analysis."""
        try:
            # Generate prompt
            prompt = get_notification_prompt(
                fresh_articles,
                since_last_notification, 
                previous_24_hours,
                time_since_last
            )
            
            # Call LLM
            logger.info("Sending 3-bucket analysis to LLM")
            response = self.openai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "אתה עורך חדשות מקצועי שמחליט על התראות חכמות."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            if not response or not response.get('choices'):
                logger.error("No response from LLM")
                return None
            
            content = response['choices'][0]['message']['content']
            
            # Parse JSON response
            try:
                result = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                logger.debug(f"Raw LLM response: {content}")
                return None
            
            # Validate structure
            required_fields = ['should_notify_now', 'compact_push', 'full_message']
            for field in required_fields:
                if field not in result:
                    logger.error(f"Missing required field in LLM response: {field}")
                    return None
            
            # Process compact push with intelligent truncation
            compact_push = str(result['compact_push'])
            if len(compact_push) > 60:
                # Try to find natural break point (sentence end, comma, etc.)
                truncate_at = 57  # Leave room for "..."
                for break_char in ['.', '!', ',', ';']:
                    pos = compact_push.rfind(break_char, 0, truncate_at)
                    if pos > 30:  # Don't break too early
                        truncate_at = pos + 1
                        break
                compact_push = compact_push[:truncate_at] + "..."
            
            # Create decision object
            decision = NotificationDecision(
                should_notify=bool(result['should_notify_now']),
                compact_push=compact_push,
                full_message=str(result['full_message']),
                fresh_articles_count=len(fresh_articles),
                since_last_count=len(since_last_notification),
                previous_24h_count=len(previous_24_hours),
                time_since_last_notification=time_since_last,
                analysis_timestamp=datetime.now(timezone.utc),
                raw_llm_response=result
            )
            
            logger.info(f"LLM decision: {'NOTIFY' if decision.should_notify else 'SKIP'}")
            if decision.should_notify:
                logger.info(f"Push message: {decision.compact_push}")
            
            return decision
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return None
    
    def send_notifications_if_approved(self, 
                                     decision: NotificationDecision,
                                     slack_client=None,
                                     push_client=None) -> bool:
        """Send notifications based on decision and scheduling logic."""
        if not decision.should_notify:
            logger.info("LLM decided not to send notifications")
            return False
        
        try:
            # Determine urgency level (simple heuristic based on message content)
            urgency = "normal"
            urgent_keywords = ['פיגוע', 'רצח', 'מלחמה', 'טיל', 'חירום', 'דחוף']
            message_text = (decision.compact_push + " " + decision.full_message).lower()
            
            if any(keyword in message_text for keyword in urgent_keywords):
                urgency = "breaking"
            elif decision.fresh_articles_count >= 3:
                urgency = "high"
            
            # Apply scheduling logic
            send_now, scheduled_time = self.scheduler.get_notification_decision(urgency)
            
            if not send_now:
                logger.info(f"Notifications scheduled for: {scheduled_time}")
                # In a full implementation, we'd store this for later execution
                # For now, we'll skip scheduling and just log
                return False
            
            # Send notifications immediately
            sent_any = False
            
            # Send to Slack
            if slack_client:
                try:
                    # Send full message to Slack
                    success = slack_client.send_direct_message(decision.full_message)
                    if success:
                        logger.info("Successfully sent to Slack")
                        sent_any = True
                    else:
                        logger.error("Failed to send to Slack")
                except Exception as e:
                    logger.error(f"Slack sending failed: {e}")
            
            # Send push notification (would need proper push service)
            if push_client:
                try:
                    # Create a mock article with just the compact message for push notification
                    mock_articles = [{"title": decision.compact_push, "source": "", "published": datetime.now()}]
                    success = push_client.send_news_notification(mock_articles, None, "headlines")
                    if success:
                        logger.info("Successfully sent push notification")
                        sent_any = True
                    else:
                        logger.error("Failed to send push notification")
                except Exception as e:
                    logger.error(f"Push notification failed: {e}")
            
            # Update notification timestamp if any notification was sent
            if sent_any:
                self.state_manager.update_last_notification_timestamp()
                logger.info("Updated last notification timestamp")
            
            return sent_any
            
        except Exception as e:
            logger.error(f"Failed to send notifications: {e}")
            return False
    
    def process_news_for_notifications(self, 
                                     fresh_articles: List[Dict[str, Any]],
                                     slack_client=None,
                                     push_client=None) -> Optional[NotificationDecision]:
        """
        Complete workflow: prepare data, analyze with LLM, send if approved.
        
        Args:
            fresh_articles: Articles just scraped from RSS
            slack_client: Optional Slack client for sending
            push_client: Optional push notification client
            
        Returns:
            NotificationDecision with analysis results
        """
        try:
            # Step 1: Prepare 3-bucket data
            fresh, since_last, previous_24h, time_since = self.prepare_3_bucket_data(fresh_articles)
            
            # Step 2: Analyze with LLM
            decision = self.analyze_with_llm(fresh, since_last, previous_24h, time_since)
            if not decision:
                logger.error("LLM analysis failed")
                return None
            
            # Step 3: Send notifications if approved
            if decision.should_notify:
                sent = self.send_notifications_if_approved(decision, slack_client, push_client)
                logger.info(f"Notifications {'sent' if sent else 'scheduled/failed'}")
            
            return decision
            
        except Exception as e:
            logger.error(f"Smart notification process failed: {e}")
            return None


# Convenience function for easy integration
def create_smart_notifier(state_manager: StateManager, openai_client=None) -> SmartNotifier:
    """Create configured smart notifier instance."""
    return SmartNotifier(state_manager, openai_client)