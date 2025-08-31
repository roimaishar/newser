#!/usr/bin/env python3
"""
Enhanced notification formatting for different channels.

Provides optimized message formats for push notifications, Slack, and other channels
with focus on readability and engagement for hourly news updates.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json

class NotificationFormatter:
    """Formats news content for different notification channels."""
    
    def __init__(self):
        self.max_push_chars = 120
        self.max_slack_articles = 5
    
    def format_push_notification(self, articles: List[Dict], hebrew_result=None, style: str = "headlines") -> str:
        """
        Format for mobile push notifications (iOS/Android).
        
        Args:
            articles: List of news articles
            hebrew_result: Hebrew analysis result
            style: Format style - 'headlines', 'topic', 'minimal', 'urgent'
        """
        if not articles:
            return "📰 אין חדשות חדשות"
        
        count = len(articles)
        time_str = datetime.now().strftime("%H:%M")
        
        if style == "headlines":
            # Direct headlines approach - maximize space for headlines
            top_headlines = []
            for article in articles[:3]:
                title = article.get('title', '')[:50]  # Longer titles since we removed other info
                if 'פיגוע' in title or 'רצח' in title:
                    top_headlines.append(f"🚨 {title}")
                else:
                    top_headlines.append(title)  # Remove 📰 emoji to save space
            return "\n".join(top_headlines)
        
        elif style == "topic":
            # Topic + count approach - remove time and sources to save space
            main_topic = "חדשות כלליות"
            if hebrew_result and hebrew_result.key_topics:
                main_topic = hebrew_result.key_topics[0]
            urgency = "🔥" if count >= 5 else "📊"
            return f"{urgency} {main_topic} ({count} כתבות)"
        
        elif style == "urgent":
            # Urgent news with key headlines - focus on main headline
            urgent_keywords = ['פיגוע', 'רצח', 'מלחמה', 'טיל']
            urgent_articles = [a for a in articles if any(kw in a.get('title', '') for kw in urgent_keywords)]
            
            if urgent_articles:
                title = urgent_articles[0].get('title', '')[:60]  # Longer title
                other_count = len(articles) - 1
                return f"🚨 {title}" + (f" (+{other_count})" if other_count > 0 else "")
            else:
                main_topic = hebrew_result.key_topics[0] if hebrew_result and hebrew_result.key_topics else 'עדכונים'
                return f"⚡ {main_topic} ({count} כתבות)"
        
        else:  # minimal
            # Single line focus - remove "חמות" to save space
            main_topic = hebrew_result.key_topics[0] if hebrew_result and hebrew_result.key_topics else "עדכונים"
            return f"⚡ {main_topic} ({count})"
    
    def format_slack_headlines_first(self, articles: List[Dict], hebrew_result=None) -> Dict[str, Any]:
        """
        Headlines-first professional format - all headlines visible, easy access to details.
        """
        if not articles:
            return {
                "text": "📰 אין חדשות חדשות בשעה האחרונה",
                "username": "NewsBot",
                "icon_emoji": ":newspaper:"
            }
        
        count = len(articles)
        time_str = datetime.now().strftime("%H:%M")
        
        # Create numbered headlines list
        headlines = []
        for i, article in enumerate(articles, 1):
            title = article.get('title', '')[:80]
            source = article.get('source', '').upper()
            headlines.append(f"{i}️⃣ {title} ({source})")
        
        headlines_text = "\n".join(headlines)
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📰 חדשות ישראל | {time_str} | {count} כתבות",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔥 כותרות עיקריות:*\n{headlines_text}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📊 ניתוח"},
                        "action_id": "show_analysis",
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🔗 קישורים"},
                        "action_id": "show_links"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📈 מגמות"},
                        "action_id": "show_trends"
                    }
                ]
            }
        ]
        
        return {
            "blocks": blocks,
            "username": "Israeli News",
            "icon_emoji": ":israel:"
        }
    
    def format_slack_executive(self, articles: List[Dict], hebrew_result=None) -> Dict[str, Any]:
        """
        Executive summary format with metrics and numbered headlines.
        """
        if not articles:
            return self.format_slack_headlines_first(articles, hebrew_result)
        
        count = len(articles)
        time_str = datetime.now().strftime("%H:%M")
        
        # Determine topic and urgency
        main_topic = "כללי"
        urgency_level = "בינונית"
        
        if hebrew_result and hebrew_result.key_topics:
            main_topic = hebrew_result.key_topics[0]
        
        # Check for urgent content
        urgent_keywords = ['פיגוע', 'רצח', 'מלחמה', 'טיל', 'פצוע', 'הרוג']
        has_urgent = any(any(kw in article.get('title', '') for kw in urgent_keywords) for article in articles)
        
        if has_urgent:
            urgency_level = "גבוהה"
        elif count >= 5:
            urgency_level = "גבוהה"
        elif count >= 3:
            urgency_level = "בינונית"
        else:
            urgency_level = "נמוכה"
        
        # Create numbered headlines
        headlines = []
        for i, article in enumerate(articles, 1):
            title = article.get('title', '')[:70]
            headlines.append(f"{i}️⃣ {title}")
        
        headlines_text = "\n".join(headlines)
        
        # Analysis summary
        analysis_summary = ""
        if hebrew_result and hebrew_result.summary:
            analysis_summary = hebrew_result.summary[:120] + "..."
        
        blocks = [
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*⏰ זמן:* {time_str}"},
                    {"type": "mrkdwn", "text": f"*📊 כתבות:* {count}"},
                    {"type": "mrkdwn", "text": f"*🎯 נושא:* {main_topic}"},
                    {"type": "mrkdwn", "text": f"*🔥 דחיפות:* {urgency_level}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*כותרות:*\n{headlines_text}"
                }
            }
        ]
        
        # Add analysis if available
        if analysis_summary:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"💡 *מסקנה:* {analysis_summary}"
                    }
                ]
            })
        
        return {
            "blocks": blocks,
            "username": "Israeli News Executive",
            "icon_emoji": ":israel:"
        }
    
    def format_slack_expandable(self, articles: List[Dict], hebrew_result=None) -> Dict[str, Any]:
        """
        Expandable format - compact view with expand button.
        """
        if not articles:
            return self.format_slack_headlines_first(articles, hebrew_result)
        
        count = len(articles)
        time_str = datetime.now().strftime("%H:%M")
        
        # Main topic
        main_topic = "עדכונים"
        if hebrew_result and hebrew_result.key_topics:
            main_topic = hebrew_result.key_topics[0]
        
        # Top 3 headlines
        top_headlines = []
        for article in articles[:3]:
            title = article.get('title', '')[:60]
            top_headlines.append(f"• {title}")
        
        headlines_text = "\n".join(top_headlines)
        
        # Show remaining count
        remaining_text = ""
        if count > 3:
            remaining_text = f"\n_+{count-3} כתבות נוספות_"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🇮🇱 *חדשות {time_str}* | {count} כתבות | {main_topic}\n\n*Top 3:*\n{headlines_text}{remaining_text}"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "הצג הכל"},
                    "action_id": "expand_all",
                    "style": "primary"
                }
            }
        ]
        
        return {
            "blocks": blocks,
            "username": "Israeli News",
            "icon_emoji": ":israel:"
        }
    
    def format_slack_digest(self, articles: List[Dict], hebrew_result=None) -> Dict[str, Any]:
        """
        Digest-style Slack format with structured layout.
        """
        if not articles:
            return self.format_slack_compact(articles, hebrew_result)
        
        count = len(articles)
        time_str = datetime.now().strftime("%d/%m %H:%M")
        
        # Header with key metrics
        confidence_bar = ""
        urgency_bar = ""
        impact_bar = ""
        
        if hebrew_result:
            conf = hebrew_result.confidence or 0.5
            conf_level = int(conf * 5)
            confidence_bar = "🔴" * conf_level + "⚪" * (5 - conf_level)
            
            # Determine urgency based on content
            urgency_level = 4 if count >= 5 else 3 if count >= 3 else 2
            urgency_bar = "🔴" * urgency_level + "⚪" * (5 - urgency_level)
            
            # Impact based on topics
            impact_level = 4 if any(word in str(hebrew_result.key_topics).lower() for word in ['ביטחון', 'פיגוע', 'מלחמה']) else 3
            impact_bar = "🔴" * impact_level + "⚪" * (5 - impact_level)
        
        # Main topic
        main_topic = "נושאים כלליים"
        if hebrew_result and hebrew_result.key_topics:
            main_topic = hebrew_result.key_topics[0]
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📬 דייג'סט חדשות - {time_str}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"┌─ *הנושא המרכזי* ─┐\n│ 🎯 {main_topic} │\n│ 📊 {count} כתבות חדשות │\n└─────────────────┘"
                }
            }
        ]
        
        # Add metrics if available
        if confidence_bar:
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*ודאות:* {confidence_bar}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*דחיפות:* {urgency_bar}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*השפעה:* {impact_bar}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*מקורות:* יינט, וואלה"
                    }
                ]
            })
        
        # Key insights
        if hebrew_result and hebrew_result.summary:
            insights = hebrew_result.summary.split('.')[:2]  # First 2 sentences
            insights_text = "• " + "\n• ".join([s.strip() for s in insights if s.strip()])
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔍 תובנות מרכזיות:*\n{insights_text}"
                }
            })
        
        # Action buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📰 כל הכתבות"
                    },
                    "action_id": "show_all_articles",
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📈 מגמות"
                    },
                    "action_id": "show_trends"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "⚙️ הגדרות"
                    },
                    "action_id": "notification_settings"
                }
            ]
        })
        
        return {
            "blocks": blocks,
            "username": "Israeli News Digest",
            "icon_emoji": ":newspaper:"
        }
    
    def format_slack_thread(self, articles: List[Dict], hebrew_result=None) -> List[Dict[str, Any]]:
        """
        Thread-based format - main message + replies.
        Returns list of messages for thread.
        """
        messages = []
        
        # Main message
        count = len(articles)
        time_str = datetime.now().strftime("%H:%M")
        
        main_topics = ""
        if hebrew_result and hebrew_result.key_topics:
            main_topics = " • ".join(hebrew_result.key_topics[:2])
        
        urgency = "גבוהה" if count >= 5 else "בינונית" if count >= 3 else "נמוכה"
        
        main_message = {
            "text": f"🚨 *חדשות ישראל* | {time_str} | {count} כתבות חדשות\n\n🔥 *הכי חם עכשיו:*\n{main_topics}\n\n💭 *המסקנה:* {hebrew_result.summary[:100] if hebrew_result else 'עדכונים שוטפים'}...\n📊 *רמת דאגה:* {urgency}\n\n👇 פרטים בתגובות",
            "username": "Israeli News",
            "icon_emoji": ":israel:"
        }
        messages.append(main_message)
        
        # Thread reply 1: Full analysis
        if hebrew_result:
            analysis_reply = {
                "text": f"🎯 *ניתוח מעמיק*\n\n{hebrew_result.summary}\n\n🏷️ *נושאים:* {', '.join(hebrew_result.key_topics) if hebrew_result.key_topics else 'כללי'}",
                "thread_ts": "main_message_ts"  # Will be replaced with actual timestamp
            }
            messages.append(analysis_reply)
        
        # Thread reply 2: Articles list
        articles_text = ""
        for i, article in enumerate(articles[:5], 1):
            title = article.get('title', '')[:80]
            source = article.get('source', '').upper()
            link = article.get('link', '')
            articles_text += f"{i}. *{title}* ({source})\n   {link}\n\n"
        
        articles_reply = {
            "text": f"📰 *רשימת כתבות*\n\n{articles_text}",
            "thread_ts": "main_message_ts"
        }
        messages.append(articles_reply)
        
        return messages
    
    def get_urgency_level(self, articles: List[Dict], hebrew_result=None) -> str:
        """Determine urgency level based on content."""
        count = len(articles)
        
        # Check for urgent keywords
        urgent_keywords = ['פיגוע', 'רצח', 'מלחמה', 'טיל', 'פצוע', 'הרוג']
        
        has_urgent_content = False
        if hebrew_result:
            content = str(hebrew_result.summary) + str(hebrew_result.key_topics)
            has_urgent_content = any(keyword in content for keyword in urgent_keywords)
        
        if has_urgent_content:
            return "critical"
        elif count >= 5:
            return "high"
        elif count >= 3:
            return "medium"
        else:
            return "low"
