#!/usr/bin/env python3
"""
Slack integration for sending news notifications.

Provides functionality to send formatted news reports and alerts to Slack channels
via webhooks or the Slack API.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import requests

from .notification_formatter import NotificationFormatter

logger = logging.getLogger(__name__)

class SlackNotifier:
    """Handles sending notifications to Slack."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack notifier.
        
        Args:
            webhook_url: Slack webhook URL. If None, tries to get from environment.
        """
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("Slack webhook URL not provided and not found in SLACK_WEBHOOK_URL environment variable")
        
        self.timeout = 10
        self.max_message_length = 4000  # Slack's limit is ~40000 chars, but keep it reasonable
        self.formatter = NotificationFormatter()
    
    def send_message(self, text: str, channel: Optional[str] = None, username: str = "NewsBot") -> bool:
        """
        Send a simple text message to Slack.
        
        Args:
            text: Message text
            channel: Optional channel override
            username: Bot username for the message
            
        Returns:
            True if sent successfully, False otherwise
        """
        if len(text) > self.max_message_length:
            text = text[:self.max_message_length - 3] + "..."
            
        payload = {
            "text": text,
            "username": username,
            "icon_emoji": ":newspaper:"
        }
        
        if channel:
            payload["channel"] = channel
        
        return self._send_webhook_message(payload)
    
    def send_news_summary(self, articles: List[Dict[str, Any]], analysis: Optional[Dict[str, Any]] = None, hebrew_result=None, format_style: str = "headlines_first") -> bool:
        """
        Send a formatted news summary to Slack with enhanced formatting options.
        
        Args:
            articles: List of news articles
            analysis: Optional (unused, kept for compatibility)
            hebrew_result: Optional Hebrew analysis result
            format_style: Format style - 'compact', 'digest', 'thread', 'original'
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not articles:
            return self.send_message("📰 אין חדשות חדשות בשעה האחרונה")
        
        # Use enhanced formatting based on style
        if format_style == "headlines_first":
            payload = self.formatter.format_slack_headlines_first(articles, hebrew_result)
        elif format_style == "executive":
            payload = self.formatter.format_slack_executive(articles, hebrew_result)
        elif format_style == "expandable":
            payload = self.formatter.format_slack_expandable(articles, hebrew_result)
        elif format_style == "digest":
            payload = self.formatter.format_slack_digest(articles, hebrew_result)
        elif format_style == "thread":
            # For thread format, send main message first, then replies
            messages = self.formatter.format_slack_thread(articles, hebrew_result)
            if messages:
                # Send main message first
                main_success = self._send_webhook_message(messages[0])
                # Note: Thread replies would need message timestamp from first response
                # This is a limitation of webhooks - would need Slack API for full threading
                return main_success
            return False
        else:
            # Fall back to original format
            return self._send_original_format(articles, hebrew_result)
        
        return self._send_webhook_message(payload)
    
    def _send_original_format(self, articles: List[Dict[str, Any]], hebrew_result=None) -> bool:
        """Original format for backward compatibility."""
        # Create formatted message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        blocks = []
        
        # Choose header based on analysis type
        if hebrew_result:
            mode_text = "עדכונים בלבד" if hebrew_result.analysis_type == "updates" else "ניתוח כללי"
            header_text = f"🇮🇱 חדשות ישראל - {len(articles)} כתבות"
            analysis_text = f"📊 {mode_text} | 🎯 ודאות: {hebrew_result.confidence:.1f}"
        else:
            header_text = f"🇮🇱 Israeli News Update - {len(articles)} Articles"
            analysis_text = f"📅 {timestamp} | Sources: Ynet, Walla"
        
        # Header
        header_block = {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header_text,
                "emoji": True
            }
        }
        blocks.append(header_block)
        
        # Timestamp and analysis info
        context_block = {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": analysis_text
                }
            ]
        }
        blocks.append(context_block)
        
        # Analysis section (Hebrew or English)
        if hebrew_result and hebrew_result.has_new_content:
            analysis_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🤖 ניתוח בעברית*\n{hebrew_result.summary}"
                }
            }
            blocks.append(analysis_block)
            
            if hebrew_result.key_topics:
                topics_text = ", ".join(hebrew_result.key_topics)
                topics_block = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🏷️ נושאים עיקריים:* {topics_text}"
                    }
                }
                blocks.append(topics_block)
                
            if hebrew_result.bulletins:
                bulletins_block = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*📢 עדכונים:*\n{hebrew_result.bulletins}"
                    }
                }
                blocks.append(bulletins_block)
        
        # Add divider
        blocks.append({"type": "divider"})
        
        # Top articles (limit to 5 for compact view)
        top_articles = articles[:5]
        
        for i, article in enumerate(top_articles, 1):
            title = article.get('title', 'No Title')[:80]  # Shorter titles
            link = article.get('link', '')
            source = article.get('source', '').upper()
            published = article.get('published')
            
            # Format timestamp
            time_str = ""
            if published:
                if hasattr(published, 'strftime'):
                    time_str = published.strftime("%H:%M")
                else:
                    time_str = str(published)[:5]  # Fallback
            
            # Create article block
            article_text = f"*{i}. {title}*"
            if time_str:
                article_text += f"\n🕐 {time_str} | 📰 {source}"
            else:
                article_text += f"\n📰 {source}"
            
            if link:
                article_text += f"\n<{link}|קרא עוד>"
            
            article_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": article_text
                }
            }
            blocks.append(article_block)
        
        # Footer if there are more articles
        if len(articles) > 5:
            footer_block = {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_... ועוד {len(articles) - 5} כתבות_"
                    }
                ]
            }
            blocks.append(footer_block)
        
        payload = {
            "blocks": blocks,
            "username": "Israeli News Bot",
            "icon_emoji": ":israel:"
        }
        
        return self._send_webhook_message(payload)
    
    def send_alert(self, message: str, severity: str = "info") -> bool:
        """
        Send an alert message to Slack with appropriate formatting.
        
        Args:
            message: Alert message
            severity: Alert severity (info, warning, error, critical)
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Choose emoji and color based on severity
        emoji_map = {
            "info": ":information_source:",
            "warning": ":warning:",
            "error": ":x:",
            "critical": ":rotating_light:"
        }
        
        color_map = {
            "info": "#36a64f",     # Green
            "warning": "#ff9900",   # Orange  
            "error": "#ff0000",     # Red
            "critical": "#8B0000"   # Dark red
        }
        
        emoji = emoji_map.get(severity, ":information_source:")
        color = color_map.get(severity, "#36a64f")
        
        payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{emoji} *Alert - {severity.upper()}*\n{message}"
                            }
                        }
                    ]
                }
            ],
            "username": "News Alert Bot",
            "icon_emoji": ":rotating_light:"
        }
        
        return self._send_webhook_message(payload)
    
    def _send_webhook_message(self, payload: Dict[str, Any]) -> bool:
        """
        Send a message via Slack webhook.
        
        Args:
            payload: Slack message payload
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout,
                verify=True,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info("Slack message sent successfully")
                return True
            else:
                logger.error(f"Slack webhook failed with status {response.status_code}: {response.text}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Slack message: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test Slack webhook connection."""
        test_message = {
            "text": f"🧪 Test message from News Aggregator - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "username": "NewsBot Test",
            "icon_emoji": ":test_tube:"
        }
        
        success = self._send_webhook_message(test_message)
        
        if success:
            logger.info("Slack connection test successful")
        else:
            logger.error("Slack connection test failed")
            
        return success
    
    def send_simple_message(self, text: str, channel: Optional[str] = None) -> bool:
        """
        Alias for send_message for consistency with integration commands.
        
        Args:
            text: Message text
            channel: Optional channel override
            
        Returns:
            True if sent successfully, False otherwise
        """
        return self.send_message(text, channel)
    
    def send_direct_message(self, message: str, username: str = "Smart News Bot") -> bool:
        """
        Send a direct message (for smart notification system).
        
        Args:
            message: Message text (can be LLM-generated full message with markdown)
            username: Bot username
            
        Returns:
            True if sent successfully, False otherwise
        """
        if len(message) > self.max_message_length:
            message = message[:self.max_message_length - 3] + "..."
        
        # Check if message has structured format (with ** markdown)
        if "**עובדות עיקריות:**" in message:
            # Create structured Slack blocks for better formatting
            sections = message.split("**הקשר ומשמעות:**")
            facts_section = sections[0].replace("📰 **עובדות עיקריות:**", "").strip()
            context_section = sections[1].strip() if len(sections) > 1 else ""
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📰 חדשות מיידיות",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*עובדות עיקריות:*\n{facts_section}"
                    }
                }
            ]
            
            if context_section:
                blocks.append({
                    "type": "section", 
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*הקשר ומשמעות:*\n{context_section}"
                    }
                })
            
            payload = {
                "blocks": blocks,
                "username": username,
                "icon_emoji": ":newspaper:"
            }
        else:
            # Fallback to simple text format
            payload = {
                "text": message,
                "username": username,
                "icon_emoji": ":newspaper:",
                "mrkdwn": True  # Enable markdown formatting
            }
        
        return self._send_webhook_message(payload)