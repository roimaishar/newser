#!/usr/bin/env python3
"""
Notification testing and management commands.

Provides commands to test different notification formats and manage
notification preferences for the news aggregation system.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from .base import BaseCommand
from ..core.notifications.channels.slack import SlackNotifier
from ..integrations.push_notifier import PushNotifier
from ..integrations.notification_formatter import NotificationFormatter
from ..core.data_manager import DataManager

logger = logging.getLogger(__name__)

class NotificationCommand(BaseCommand):
    """Command for testing and managing notifications."""
    
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.formatter = NotificationFormatter()
    
    def get_parser(self, subparsers):
        """Set up argument parser for notification commands."""
        parser = subparsers.add_parser('notification', help='Test and manage notifications')
        
        # Subcommands
        notification_subparsers = parser.add_subparsers(dest='notification_action', help='Notification actions')
        
        # Test Slack formats
        slack_parser = notification_subparsers.add_parser('test-slack', help='Test Slack notification formats')
        slack_parser.add_argument('--format', choices=['compact', 'digest', 'thread', 'original'], 
                                default='compact', help='Slack format style')
        slack_parser.add_argument('--hours', type=int, default=1, help='Hours of news to fetch for testing')
        
        # Test push notifications
        push_parser = notification_subparsers.add_parser('test-push', help='Test push notification formats')
        push_parser.add_argument('--style', choices=['breaking', 'summary', 'minimal'], 
                               default='breaking', help='Push notification style')
        push_parser.add_argument('--provider', choices=['onesignal', 'firebase'], 
                               default='onesignal', help='Push notification provider')
        push_parser.add_argument('--hours', type=int, default=1, help='Hours of news to fetch for testing')
        
        # Compare formats
        compare_parser = notification_subparsers.add_parser('compare', help='Compare notification formats')
        compare_parser.add_argument('--hours', type=int, default=1, help='Hours of news to fetch')
        
        # Show examples
        examples_parser = notification_subparsers.add_parser('examples', help='Show format examples')
        examples_parser.add_argument('--type', choices=['push', 'slack', 'all'], 
                                   default='all', help='Type of examples to show')
        
        return parser
    
    def execute(self, args) -> int:
        """Execute notification command."""
        try:
            if args.notification_action == 'test-slack':
                return self.test_slack_formats(args)
            elif args.notification_action == 'test-push':
                return self.test_push_formats(args)
            elif args.notification_action == 'compare':
                return self.compare_formats(args)
            elif args.notification_action == 'examples':
                return self.show_examples(args)
            else:
                print("❌ Unknown notification action. Use --help for options.")
                return 1
                
        except Exception as e:
            logger.error(f"Notification command error: {e}")
            print(f"❌ Error: {e}")
            return 1
    
    def test_slack_formats(self, args) -> int:
        """Test different Slack notification formats."""
        print(f"🧪 Testing Slack format: {args.format}")
        
        try:
            # Get recent articles for testing
            articles = self._get_test_articles(args.hours)
            hebrew_result = self._get_test_analysis()
            
            if not articles:
                print("⚠️  No articles found for testing. Using mock data.")
                articles = self._get_mock_articles()
                hebrew_result = self._get_mock_analysis()
            
            # Initialize Slack notifier
            slack = SlackNotifier()
            
            # Test the specified format
            print(f"\n📤 Sending {args.format} format to Slack...")
            success = slack.send_news_summary(articles, format_style=args.format, hebrew_result=hebrew_result)
            
            if success:
                print(f"✅ {args.format.title()} format sent successfully!")
                
                # Show preview of what was sent
                if args.format == "compact":
                    preview = slack.formatter.format_slack_compact(articles, hebrew_result)
                elif args.format == "digest":
                    preview = slack.formatter.format_slack_digest(articles, hebrew_result)
                else:
                    preview = {"text": f"Format: {args.format}"}
                
                print(f"\n📋 Preview sent:")
                print(f"Articles: {len(articles)}")
                print(f"Format: {args.format}")
                if hebrew_result:
                    print(f"Analysis: {hebrew_result.summary[:100]}...")
                
            else:
                print(f"❌ Failed to send {args.format} format")
                return 1
                
        except Exception as e:
            print(f"❌ Slack test failed: {e}")
            return 1
        
        return 0
    
    def test_push_formats(self, args) -> int:
        """Test push notification formats."""
        print(f"🧪 Testing push format: {args.style} via {args.provider}")
        
        try:
            # Get recent articles for testing
            articles = self._get_test_articles(args.hours)
            hebrew_result = self._get_test_analysis()
            
            if not articles:
                print("⚠️  No articles found for testing. Using mock data.")
                articles = self._get_mock_articles()
                hebrew_result = self._get_mock_analysis()
            
            # Show what the push notification would look like
            push_message = self.formatter.format_push_notification(articles, hebrew_result, args.style)
            
            print(f"\n📱 Push Notification Preview ({args.style} style):")
            print("=" * 50)
            print(push_message)
            print("=" * 50)
            print(f"Length: {len(push_message)} characters")
            
            # Test actual sending if configured
            try:
                push_notifier = PushNotifier(provider=args.provider)
                if push_notifier._is_configured():
                    print(f"\n📤 Sending test notification via {args.provider}...")
                    success = push_notifier.send_test_notification(push_message)
                    if success:
                        print("✅ Push notification sent successfully!")
                    else:
                        print("❌ Failed to send push notification")
                else:
                    print(f"⚠️  {args.provider.title()} not configured. Showing preview only.")
            except Exception as e:
                print(f"⚠️  Push service error: {e}")
                
        except Exception as e:
            print(f"❌ Push test failed: {e}")
            return 1
        
        return 0
    
    def compare_formats(self, args) -> int:
        """Compare different notification formats side by side."""
        print("📊 Comparing notification formats...")
        
        try:
            articles = self._get_test_articles(args.hours)
            hebrew_result = self._get_test_analysis()
            
            if not articles:
                articles = self._get_mock_articles()
                hebrew_result = self._get_mock_analysis()
            
            print(f"\n📰 Using {len(articles)} articles for comparison\n")
            
            # Push notification formats
            print("📱 PUSH NOTIFICATION FORMATS")
            print("=" * 60)
            
            for style in ['breaking', 'summary', 'minimal']:
                message = self.formatter.format_push_notification(articles, hebrew_result, style)
                print(f"\n🔹 {style.upper()} ({len(message)} chars):")
                print("-" * 40)
                print(message)
            
            # Slack formats preview
            print(f"\n\n💬 SLACK FORMATS")
            print("=" * 60)
            
            formats = {
                'compact': 'Compact - Single block with key info',
                'digest': 'Digest - Structured with metrics',
                'original': 'Original - Full detailed format'
            }
            
            for format_name, description in formats.items():
                print(f"\n🔹 {format_name.upper()}: {description}")
                print("-" * 40)
                
                if format_name == 'compact':
                    preview = self.formatter.format_slack_compact(articles, hebrew_result)
                elif format_name == 'digest':
                    preview = self.formatter.format_slack_digest(articles, hebrew_result)
                else:
                    preview = {"text": "Original detailed format with full article list"}
                
                # Show key characteristics
                block_count = len(preview.get('blocks', []))
                print(f"Blocks: {block_count}")
                if 'blocks' in preview and preview['blocks']:
                    first_block = preview['blocks'][0]
                    if 'text' in first_block:
                        preview_text = first_block['text'].get('text', '')[:100]
                        print(f"Preview: {preview_text}...")
            
            print(f"\n💡 Recommendations:")
            print(f"• Push: Use 'breaking' for urgent news, 'summary' for regular updates")
            print(f"• Slack: Use 'compact' for hourly updates, 'digest' for daily summaries")
            
        except Exception as e:
            print(f"❌ Comparison failed: {e}")
            return 1
        
        return 0
    
    def show_examples(self, args) -> int:
        """Show example notifications."""
        print("📚 Notification Format Examples")
        
        # Mock data for examples
        mock_articles = self._get_mock_articles()
        mock_analysis = self._get_mock_analysis()
        
        if args.type in ['push', 'all']:
            print(f"\n📱 PUSH NOTIFICATION EXAMPLES")
            print("=" * 50)
            
            styles = ['breaking', 'summary', 'minimal']
            for style in styles:
                message = self.formatter.format_push_notification(mock_articles, mock_analysis, style)
                print(f"\n🔹 {style.upper()} Style:")
                print(f"   {message}")
                print(f"   Length: {len(message)} chars")
        
        if args.type in ['slack', 'all']:
            print(f"\n💬 SLACK FORMAT EXAMPLES")
            print("=" * 50)
            
            print(f"\n🔹 COMPACT Format:")
            print("   • Single block with summary")
            print("   • Top 3 headlines")
            print("   • Action buttons if >3 articles")
            print("   • Best for: Hourly updates")
            
            print(f"\n🔹 DIGEST Format:")
            print("   • Structured header with metrics")
            print("   • Confidence/urgency/impact bars")
            print("   • Key insights")
            print("   • Multiple action buttons")
            print("   • Best for: Daily summaries")
            
            print(f"\n🔹 THREAD Format:")
            print("   • Main message with overview")
            print("   • Separate thread replies for details")
            print("   • Analysis in thread")
            print("   • Article list in thread")
            print("   • Best for: Detailed discussions")
        
        return 0
    
    def _get_test_articles(self, hours: int) -> List[Dict[str, Any]]:
        """Get recent articles for testing."""
        try:
            from_time = datetime.now() - timedelta(hours=hours)
            return self.data_manager.get_recent_articles(hours)
        except Exception:
            return []
    
    def _get_test_analysis(self):
        """Get recent analysis for testing."""
        try:
            analyses = self.data_manager.get_recent_analyses(hours=24)
            if analyses:
                # Convert dict to object-like structure
                class MockAnalysis:
                    def __init__(self, data):
                        self.summary = data.get('summary', '')
                        self.key_topics = data.get('key_topics', [])
                        self.bulletins = data.get('bulletins', '')
                        self.confidence = data.get('confidence', 0.8)
                        self.analysis_type = data.get('analysis_type', 'thematic')
                        self.has_new_content = True
                
                return MockAnalysis(analyses[0])
        except Exception:
            pass
        return None
    
    def _get_mock_articles(self) -> List[Dict[str, Any]]:
        """Get mock articles for testing."""
        return [
            {
                'title': 'פיגוע בירושלים - 3 פצועים',
                'source': 'ynet',
                'link': 'https://example.com/1',
                'published': datetime.now() - timedelta(minutes=30)
            },
            {
                'title': 'ממשלת ישראל מאשרת תקציב ביטחון',
                'source': 'walla',
                'link': 'https://example.com/2',
                'published': datetime.now() - timedelta(minutes=45)
            },
            {
                'title': 'הפגנות בתל אביב נגד הרפורמה',
                'source': 'ynet',
                'link': 'https://example.com/3',
                'published': datetime.now() - timedelta(hours=1)
            }
        ]
    
    def _get_mock_analysis(self):
        """Get mock analysis for testing."""
        class MockAnalysis:
            def __init__(self):
                self.summary = "המצב הביטחוני מתדרדר עם פיגועים חדשים בירושלים. הממשלה מגיבה בהגדלת התקציב הביטחוני בעוד המחאות נמשכות."
                self.key_topics = ["ביטחון פנים", "תקציב ביטחון", "מחאות"]
                self.bulletins = "עדכון חם: 3 פצועים בפיגוע ירושלים"
                self.confidence = 0.85
                self.analysis_type = "thematic"
                self.has_new_content = True
        
        return MockAnalysis()
