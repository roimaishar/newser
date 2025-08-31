#!/usr/bin/env python3
"""
Health check command for monitoring system status.

Provides comprehensive health checks for database, integrations, and system components.
"""

import logging
from argparse import Namespace
from typing import Dict, Any

from .base import BaseCommand
from core.database import get_database, DatabaseError
from core.env_loader import validate_database_config
from core.cache import get_cache_stats, clear_all_caches
from integrations.openai_client import OpenAIClient
from integrations.slack_notifier import SlackNotifier

logger = logging.getLogger(__name__)


class HealthCommand(BaseCommand):
    """Handle system health monitoring and diagnostics."""
    
    def execute(self, subcommand: str, args: Namespace) -> int:
        """Execute health subcommand."""
        try:
            if subcommand == "check":
                return self.check(args)
            elif subcommand == "database":
                return self.database(args)
            elif subcommand == "integrations":
                return self.integrations(args)
            else:
                available = ", ".join(self.get_available_subcommands())
                self.logger.error(f"Unknown subcommand '{subcommand}'. Available: {available}")
                return 1
                
        except Exception as e:
            return self.handle_error(e, f"health {subcommand}")
    
    def check(self, args: Namespace) -> int:
        """Run comprehensive health check."""
        print("🏥 System Health Check")
        print("=" * 50)
        
        overall_healthy = True
        
        # Database health
        print("\n📊 Database Status:")
        try:
            db = get_database()
            health = db.health_check()
            
            if health.get('connected'):
                print("  ✅ Database connection: OK")
                
                tables = health.get('tables', {})
                for table, count in tables.items():
                    print(f"  📋 {table}: {count} records")
            else:
                print("  ❌ Database connection: FAILED")
                print(f"     Error: {health.get('error', 'Unknown error')}")
                overall_healthy = False
                
        except Exception as e:
            print(f"  ❌ Database check failed: {e}")
            overall_healthy = False
        
        # Configuration validation
        print("\n⚙️  Configuration:")
        try:
            validate_database_config()
            print("  ✅ Database configuration: OK")
        except Exception as e:
            print(f"  ❌ Database configuration: {e}")
            overall_healthy = False
        
        # Integration status
        print("\n🔌 Integration Status:")
        
        # OpenAI check
        try:
            openai_client = OpenAIClient()
            print("  ✅ OpenAI configuration: OK")
        except Exception as e:
            print(f"  ❌ OpenAI configuration: {e}")
            overall_healthy = False
        
        # Slack check
        try:
            slack_client = SlackNotifier()
            print("  ✅ Slack configuration: OK")
        except Exception as e:
            print(f"  ❌ Slack configuration: {e}")
            overall_healthy = False
        
        # Cache status
        print("\n💾 Cache Status:")
        try:
            cache_stats = get_cache_stats()
            if cache_stats:
                for cache_name, stats in cache_stats.items():
                    hit_rate = stats.get('hit_rate', 0)
                    entries = stats.get('entries', 0)
                    print(f"  📊 {cache_name.title()} Cache: {entries} entries, {hit_rate:.1f}% hit rate")
                print("  ✅ Cache system: OK")
            else:
                print("  ℹ️  No cache instances active")
        except Exception as e:
            print(f"  ⚠️  Cache check failed: {e}")
            # Don't mark as unhealthy since cache is not critical
        
        # Async Feed Parser check
        print("\n⚡ Async RSS Fetching:")
        try:
            from core.async_feed_parser import AsyncFeedParser
            print("  ✅ Async RSS parser available")
            print("  ℹ️  Use --async flag with news commands for parallel fetching")
        except ImportError as e:
            print(f"  ❌ Async RSS parser not available: {e}")
            overall_healthy = False
        
        # Summary
        print("\n" + "=" * 50)
        if overall_healthy:
            print("✅ Overall Status: HEALTHY")
            return 0
        else:
            print("❌ Overall Status: UNHEALTHY")
            return 1
    
    def database(self, args: Namespace) -> int:
        """Check database health specifically."""
        print("📊 Database Health Check")
        print("=" * 30)
        
        try:
            # Configuration check
            validate_database_config()
            print("✅ Database configuration valid")
            
            # Connection test
            db = get_database()
            health = db.health_check()
            
            if health.get('connected'):
                print("✅ Database connection successful")
                
                # Table statistics
                tables = health.get('tables', {})
                if tables:
                    print("\n📋 Table Statistics:")
                    for table, count in tables.items():
                        print(f"  • {table}: {count:,} records")
                
                # Test a simple query
                known_items = db.get_known_items()
                print(f"\n🔍 Known items: {len(known_items)} hashes")
                
                return 0
            else:
                print(f"❌ Database connection failed: {health.get('error')}")
                return 1
                
        except DatabaseError as e:
            print(f"❌ Database error: {e}")
            return 1
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return 1
    
    def integrations(self, args: Namespace) -> int:
        """Test external integrations."""
        print("🔌 Integration Health Check")
        print("=" * 35)
        
        success_count = 0
        total_count = 0
        
        # Test OpenAI
        print("\n🤖 OpenAI Integration:")
        total_count += 1
        try:
            openai_client = OpenAIClient()
            # Try a simple test (without making actual API call)
            print("  ✅ OpenAI client initialized successfully")
            print("  ℹ️  API key configured and valid format")
            success_count += 1
        except Exception as e:
            print(f"  ❌ OpenAI integration failed: {e}")
        
        # Test Slack
        print("\n📱 Slack Integration:")
        total_count += 1
        try:
            slack_client = SlackNotifier()
            
            # Test connection (if --test flag provided)
            if getattr(args, 'test', False):
                print("  🧪 Testing Slack webhook...")
                if slack_client.test_connection():
                    print("  ✅ Slack webhook test successful")
                    success_count += 1
                else:
                    print("  ❌ Slack webhook test failed")
            else:
                print("  ✅ Slack client initialized successfully")
                print("  ℹ️  Use --test flag to test webhook")
                success_count += 1
                
        except Exception as e:
            print(f"  ❌ Slack integration failed: {e}")
        
        # Summary
        print(f"\n📊 Integration Summary: {success_count}/{total_count} healthy")
        
        if success_count == total_count:
            print("✅ All integrations healthy")
            return 0
        else:
            print("⚠️  Some integrations have issues")
            return 1
