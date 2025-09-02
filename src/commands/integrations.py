#!/usr/bin/env python3
"""
Integrations command endpoints for managing external service connections.
"""

import logging
from argparse import Namespace
from typing import List

from .base import BaseCommand

logger = logging.getLogger(__name__)


class IntegrationsCommand(BaseCommand):
    """Handle external integration operations."""
    
    def execute(self, subcommand: str, args: Namespace) -> int:
        """Execute integrations subcommand."""
        try:
            if subcommand == "test":
                return self.test(args)
            elif subcommand == "slack":
                return self.slack(args)
            elif subcommand == "openai":
                return self.openai(args)
            elif subcommand == "status":
                return self.status(args)
            else:
                available = ", ".join(self.get_available_subcommands())
                self.logger.error(f"Unknown subcommand '{subcommand}'. Available: {available}")
                return 1
                
        except Exception as e:
            return self.handle_error(e, f"integrations {subcommand}")
    
    def test(self, args: Namespace) -> int:
        """Test all integrations."""
        try:
            print("🔍 Testing integrations...")
            
            # Test OpenAI
            openai_status = self._test_openai()
            
            # Test Slack
            slack_status = self._test_slack()
            
            print(f"\n=== Integration Test Results ===")
            print(f"🤖 OpenAI API: {'✅ Connected' if openai_status else '❌ Failed'}")
            print(f"💬 Slack API: {'✅ Connected' if slack_status else '❌ Failed'}")
            
            if openai_status and slack_status:
                print("✅ All integrations working")
                return 0
            else:
                print("⚠️  Some integrations failed - check configuration")
                return 1
            
        except Exception as e:
            return self.handle_error(e, "integrations test")
    
    def slack(self, args: Namespace) -> int:
        """Test or manage Slack integration."""
        try:
            action = getattr(args, 'action', 'test')
            
            if action == 'test':
                print("🔍 Testing Slack connection...")
                success = self._test_slack()
                
                if success:
                    print("✅ Slack integration working")
                    return 0
                else:
                    print("❌ Slack integration failed")
                    return 1
                    
            elif action == 'send':
                # Send a test message
                message = getattr(args, 'message', 'Test message from newser CLI')
                return self._send_test_slack_message(message)
                
            else:
                self.logger.error(f"Unknown slack action '{action}'. Use 'test' or 'send'")
                return 1
            
        except Exception as e:
            return self.handle_error(e, "integrations slack")
    
    def openai(self, args: Namespace) -> int:
        """Test or manage OpenAI integration."""
        try:
            action = getattr(args, 'action', 'test')
            
            if action == 'test':
                print("🔍 Testing OpenAI connection...")
                success = self._test_openai()
                
                if success:
                    print("✅ OpenAI integration working")
                    return 0
                else:
                    print("❌ OpenAI integration failed")
                    return 1
                    
            elif action == 'analyze':
                # Test analysis with sample text
                sample_text = getattr(args, 'text', 'זהו טקסט לדוגמה לבדיקת הניתוח העברי')
                return self._test_openai_analysis(sample_text)
                
            else:
                self.logger.error(f"Unknown openai action '{action}'. Use 'test' or 'analyze'")
                return 1
            
        except Exception as e:
            return self.handle_error(e, "integrations openai")
    
    def status(self, args: Namespace) -> int:
        """Show status of all integrations."""
        try:
            print("📊 Integration Status:")
            
            # Check environment variables
            import os
            
            openai_key = bool(os.getenv('OPENAI_API_KEY'))
            slack_token = bool(os.getenv('SLACK_BOT_TOKEN'))
            slack_channel = bool(os.getenv('SLACK_CHANNEL_ID'))
            
            print(f"🔑 Environment Variables:")
            print(f"   • OPENAI_API_KEY: {'✅ Set' if openai_key else '❌ Missing'}")
            print(f"   • SLACK_BOT_TOKEN: {'✅ Set' if slack_token else '❌ Missing'}")
            print(f"   • SLACK_CHANNEL_ID: {'✅ Set' if slack_channel else '❌ Missing'}")
            
            # Test connections if keys are available
            if openai_key or slack_token:
                print(f"\n🔍 Connection Tests:")
                
                if openai_key:
                    openai_status = self._test_openai()
                    print(f"   • OpenAI API: {'✅ Connected' if openai_status else '❌ Failed'}")
                
                if slack_token:
                    slack_status = self._test_slack()
                    print(f"   • Slack API: {'✅ Connected' if slack_status else '❌ Failed'}")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "integrations status")
    
    def _test_openai(self) -> bool:
        """Test OpenAI connection."""
        try:
            from integrations.openai_client import OpenAIClient
            client = OpenAIClient()
            
            # Simple test call
            response = client.analyze_text("Test connection", "Simple test for connectivity")
            return response is not None
            
        except ImportError:
            self.logger.warning("OpenAI client not available")
            return False
        except Exception as e:
            self.logger.warning(f"OpenAI test failed: {e}")
            return False
    
    def _test_slack(self) -> bool:
        """Test Slack connection."""
        try:
            from core.notifications.channels.slack import SlackNotifier
            client = SlackNotifier()
            
            # Test connection (without sending message)
            return client.test_connection()
            
        except ImportError:
            self.logger.warning("Slack client not available")
            return False
        except Exception as e:
            self.logger.warning(f"Slack test failed: {e}")
            return False
    
    def _send_test_slack_message(self, message: str) -> int:
        """Send a test message to Slack."""
        try:
            from core.notifications.channels.slack import SlackNotifier
            client = SlackNotifier()
            
            success = client.send_simple_message(f"🧪 Test: {message}")
            
            if success:
                print(f"✅ Test message sent to Slack: {message}")
                return 0
            else:
                print("❌ Failed to send test message")
                return 1
                
        except Exception as e:
            self.logger.error(f"Error sending test message: {e}")
            return 1
    
    def _test_openai_analysis(self, text: str) -> int:
        """Test OpenAI analysis with sample text."""
        try:
            from integrations.openai_client import OpenAIClient
            client = OpenAIClient()
            
            print(f"🧠 Testing OpenAI analysis with: {text}")
            response = client.analyze_text("Test analysis", text)
            
            if response:
                print(f"✅ Analysis result: {response[:200]}...")
                return 0
            else:
                print("❌ Analysis returned empty result")
                return 1
                
        except Exception as e:
            self.logger.error(f"Error in OpenAI analysis test: {e}")
            return 1