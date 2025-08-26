#!/usr/bin/env python3
"""
Test script for Slack integration
"""

import sys
import os
sys.path.insert(0, 'src')

# Load .env file before importing other modules
from core.env_loader import load_env_file
load_env_file()

from integrations.slack_notifier import SlackNotifier
from datetime import datetime

def test_slack_connection():
    """Test basic Slack connectivity"""
    try:
        slack = SlackNotifier()
        success = slack.test_connection()
        
        if success:
            print("✅ Slack connection successful!")
            return True
        else:
            print("❌ Slack connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Slack setup error: {e}")
        return False

def test_mobile_notification():
    """Test mobile-optimized notification"""
    try:
        slack = SlackNotifier()
        
        # Sample articles for testing
        sample_articles = [
            {
                'title': 'דיווח: ישראל שוקלת הסכם נוסף עם לבנון',
                'link': 'https://www.ynet.co.il/news/article/test1',
                'source': 'ynet',
                'published': datetime.now()
            },
            {
                'title': 'עדכון מזג האוויר: גשם צפוי בצפון',
                'link': 'https://www.walla.co.il/news/test2',
                'source': 'walla', 
                'published': datetime.now()
            },
            {
                'title': 'הכנסת מצביעה על חוק חדש היום',
                'link': 'https://www.ynet.co.il/news/article/test3',
                'source': 'ynet',
                'published': datetime.now()
            }
        ]
        
        # Create mock Hebrew result
        class MockHebrewResult:
            def __init__(self):
                self.has_new_content = True
                self.summary = "שלושה עדכונים עיקריים: הסכם עם לבנון, מזג אוויר סוער, והצבעה בכנסת"
                self.bulletins = "עדכון חשוב: ישראל מתקדמת בהסכמים דיפלומטיים"
                self.analysis_type = "updates"
                self.confidence = 0.85
                self.key_topics = ["דיפלומטיה", "מזג אוויר", "כנסת"]
        
        hebrew_result = MockHebrewResult()
        
        print("📱 Sending mobile-optimized test notification...")
        success = slack.send_news_summary(
            sample_articles, 
            hebrew_result=hebrew_result
        )
        
        if success:
            print("✅ Mobile notification sent successfully!")
            print("💡 Check your Slack for the test message")
        else:
            print("❌ Failed to send mobile notification")
            
        return success
        
    except Exception as e:
        print(f"❌ Mobile notification test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Slack Integration\n")
    
    # Test basic connection
    print("1. Testing connection...")
    if not test_slack_connection():
        sys.exit(1)
    
    print("\n2. Testing mobile notification...")
    test_mobile_notification()
    
    print(f"\n✨ Test completed! Check your Slack channel.")
