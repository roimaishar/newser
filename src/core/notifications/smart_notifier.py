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

from integrations.openai_client import OpenAIClient
from ..state_manager import StateManager
from .scheduler import NotificationScheduler, format_time_since_last_notification

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
    
    def __init__(
        self,
        state_manager: StateManager,
        openai_client: Optional[OpenAIClient] = None,
        scheduler: Optional[NotificationScheduler] = None,
    ) -> None:
        """Initialize smart notifier."""

        self.state_manager = state_manager
        self.openai_client = openai_client or OpenAIClient()
        self.scheduler = scheduler or NotificationScheduler()
    
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
        llm_logger = self._get_llm_logger()

        if llm_logger:
            try:
                llm_logger.log_notification_decision(
                    fresh_articles=fresh_articles,
                    since_last_articles=since_last_notification,
                    previous_24h_articles=previous_24_hours,
                    time_since_last=time_since_last,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log notification decision inputs: %s", exc)

        logger.info("Sending 3-bucket analysis to LLM")
        try:
            result = self.openai_client.analyze_notification_decision(
                fresh_articles,
                since_last_notification,
                previous_24_hours,
                time_since_last,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM structured analysis failed: %s", exc)
            return None

        if llm_logger:
            try:
                llm_logger.log_notification_decision(
                    fresh_articles=fresh_articles,
                    since_last_articles=since_last_notification,
                    previous_24h_articles=previous_24_hours,
                    time_since_last=time_since_last,
                    decision_response=json.dumps(result, ensure_ascii=False),
                    final_decision=result,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log notification decision response: %s", exc)

        required_fields = ["should_notify_now", "compact_push", "full_message"]
        for field in required_fields:
            if field not in result:
                logger.error("Missing required field in LLM response: %s", field)
                return None

        compact_push = str(result['compact_push'])
        if len(compact_push) > 60:
            truncate_at = 57
            for break_char in ['.', '!', ',', ';']:
                pos = compact_push.rfind(break_char, 0, truncate_at)
                if pos > 30:
                    truncate_at = pos + 1
                    break
            compact_push = compact_push[:truncate_at] + "..."

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
        
        logger.info("LLM decision: %s", "NOTIFY" if decision.should_notify else "SKIP")
        if decision.should_notify:
            logger.info("Push message: %s", decision.compact_push)

        return decision
    
    def send_notifications_if_approved(self, 
                                     decision: NotificationDecision,
                                     slack_client=None,
                                     push_client=None) -> bool:
        """Send notifications based on decision and scheduling logic."""
        if not decision.should_notify:
            logger.info("LLM decided not to send notifications")
            return False
        
        # Calculate urgency based on content and volume
        urgency = "normal"
        urgent_keywords = ["פיגוע", "רצח", "מלחמה", "טיל", "חירום", "דחוף", "הרוגים", "פצועים"]
        message_text = (decision.compact_push + " " + decision.full_message).lower()
        
        found_keywords = [kw for kw in urgent_keywords if kw in message_text]

        if found_keywords:
            urgency = "breaking"
        elif decision.fresh_articles_count >= 3:
            urgency = "high"
        
        # Get scheduling decision
        send_now, scheduled_time = self.scheduler.get_notification_decision(urgency)
        
        # Log urgency analysis
        llm_logger = self._get_llm_logger()
        if llm_logger:
            try:
                reasoning = ""
                if urgency == "breaking":
                    reasoning = f"Breaking keywords detected: {', '.join(found_keywords)}"
                elif urgency == "high":
                    reasoning = f"High volume: {decision.fresh_articles_count} fresh articles"
                else:
                    reasoning = "Normal news flow"
                
                llm_logger.log_urgency_analysis(
                    fresh_articles_count=decision.fresh_articles_count,
                    urgency_keywords=found_keywords,
                    calculated_urgency=urgency,
                    is_peak_hours=self.scheduler.is_peak_hours(),
                    is_quiet_hours=self.scheduler.is_quiet_hours(),
                    should_send_now=send_now,
                    scheduled_time=scheduled_time,
                    reasoning=reasoning
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log urgency analysis: %s", exc)

        if not send_now and scheduled_time:
            logger.info(
                "Notifications scheduled for: %s",
                scheduled_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            )
            self._schedule_notification_for_later(decision, scheduled_time, slack_client, push_client)
            return False
        if not send_now:
            logger.info("LLM approved notification but scheduler skipped (no slot)")
            return False

        sent_any = False

        if slack_client:
            try:
                if slack_client.send_direct_message(decision.full_message):
                    logger.info("Successfully sent to Slack")
                    sent_any = True
                else:
                    logger.error("Failed to send to Slack")
            except Exception as exc:  # noqa: BLE001
                logger.error("Slack sending failed: %s", exc)

        if push_client:
            try:
                mock_articles = [
                    {
                        "title": decision.compact_push,
                        "source": "",
                        "published": datetime.now(),
                    }
                ]
                if push_client.send_news_notification(mock_articles, None, "headlines"):
                    logger.info("Successfully sent push notification")
                    sent_any = True
                else:
                    logger.error("Failed to send push notification")
            except Exception as exc:  # noqa: BLE001
                logger.error("Push notification failed: %s", exc)

        llm_logger = self._get_llm_logger()
        if llm_logger:
            try:
                success_status: Dict[str, bool] = {}
                if slack_client:
                    success_status["slack"] = sent_any
                if push_client:
                    success_status["push"] = sent_any

                llm_logger.log_notifications_sent(
                    compact_push=decision.compact_push,
                    full_message=decision.full_message,
                    success_status=success_status,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log notification results: %s", exc)

        if sent_any:
            self.state_manager.update_last_notification_timestamp()
            logger.info("Updated last notification timestamp")

        return sent_any
    
    def _schedule_notification_for_later(self, decision: NotificationDecision, 
                                       scheduled_time: datetime, 
                                       slack_client=None, 
                                       push_client=None) -> None:
        """
        Store notification for later execution at scheduled time.
        
        In a production system, this would integrate with a job queue
        or scheduling system like Celery, APScheduler, or cloud functions.
        
        Args:
            decision: The notification decision to execute later
            scheduled_time: When to send the notification
            slack_client: Slack client for sending
            push_client: Push client for sending
        """
        try:
            # Store the scheduled notification in the state manager
            notification_data = {
                "scheduled_time": scheduled_time.isoformat(),
                "compact_push": decision.compact_push,
                "full_message": decision.full_message,
                "urgency": "normal",  # Could be extracted from decision
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            # In a real implementation, you'd store this in a database
            # and have a background worker check for due notifications
            logger.info("Stored scheduled notification: %s", notification_data)

            logger.info(
                "Notification scheduled for %s: %s",
                scheduled_time,
                decision.compact_push,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to schedule notification: %s", exc)
    
    def process_scheduled_notifications(self, slack_client=None, push_client=None) -> int:
        """
        Process any notifications that are due to be sent.
        
        This method would typically be called by a background worker
        or cron job to check for and send scheduled notifications.
        
        Args:
            slack_client: Slack client for sending
            push_client: Push client for sending
            
        Returns:
            Number of notifications sent
        """
        try:
            # In a real implementation, query database for due notifications
            # For now, this is a placeholder
            logger.info("Checking for scheduled notifications to send...")
            
            # This would typically:
            # 1. Query database for notifications where scheduled_time <= now
            # 2. Send each notification
            # 3. Mark as sent or delete from queue
            # 4. Handle failures with retry logic
            
            sent_count = 0
            logger.info("Processed %d scheduled notifications", sent_count)
            return sent_count

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to process scheduled notifications: %s", exc)
            return 0
    
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

            decision = self.analyze_with_llm(fresh, since_last, previous_24h, time_since)
            if not decision:
                logger.error("LLM analysis failed")
                return None

            if decision.should_notify:
                sent = self.send_notifications_if_approved(decision, slack_client, push_client)
                logger.info("Notifications %s", "sent" if sent else "scheduled/failed")

            return decision

        except Exception as exc:  # noqa: BLE001
            logger.error("Smart notification process failed: %s", exc)
            return None

    def _get_llm_logger(self):
        try:
            from ..llm_logger import get_llm_logger

            return get_llm_logger()
        except Exception:  # noqa: BLE001
            return None


# Convenience function for easy integration
def create_smart_notifier(state_manager: StateManager, openai_client=None) -> SmartNotifier:
    """Create configured smart notifier instance."""
    return SmartNotifier(state_manager, openai_client)