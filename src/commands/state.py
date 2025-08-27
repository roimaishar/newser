#!/usr/bin/env python3
"""
State command endpoints for managing known items and system state.
"""

import logging
from argparse import Namespace
from typing import List

from .base import BaseCommand
from core.state_manager import StateManager

logger = logging.getLogger(__name__)


class StateCommand(BaseCommand):
    """Handle state management operations."""
    
    def execute(self, subcommand: str, args: Namespace) -> int:
        """Execute state subcommand."""
        try:
            if subcommand == "stats":
                return self.stats(args)
            elif subcommand == "cleanup":
                return self.cleanup(args)
            elif subcommand == "reset":
                return self.reset(args)
            else:
                available = ", ".join(self.get_available_subcommands())
                self.logger.error(f"Unknown subcommand '{subcommand}'. Available: {available}")
                return 1
                
        except Exception as e:
            return self.handle_error(e, f"state {subcommand}")
    
    def stats(self, args: Namespace) -> int:
        """Show statistics about known items state."""
        try:
            state_manager = StateManager()
            
            # Get state statistics
            stats = state_manager.get_stats()
            
            print(f"\n=== State Statistics ===")
            print(f"📊 Database connection: {'✅ Connected' if stats.get('database_healthy') else '❌ Disconnected'}")
            print(f"📊 Total known events: {stats['total_events']}")
            
            if stats.get('oldest_event_date'):
                print(f"🕐 Oldest event: {stats['oldest_event_date']}")
            if stats.get('newest_update_date'):
                print(f"🕐 Newest event: {stats['newest_update_date']}")
                
            if stats.get('events_by_source'):
                print(f"📈 Events by source:")
                for source, count in stats['events_by_source'].items():
                    print(f"  • {source}: {count}")
            
            if stats['recent_events']:
                print(f"\n=== Recent Events (Last 10) ===")
                for event in stats['recent_events']:
                    print(f"[{event.timestamp.strftime('%m-%d %H:%M')}] {event.source}: {event.title[:60]}...")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "state stats")
    
    def cleanup(self, args: Namespace) -> int:
        """Clean up old events from state."""
        try:
            days = getattr(args, 'days', 30)
            state_manager = StateManager()
            
            print(f"🧹 Cleaning up events older than {days} days...")
            
            # Get stats before cleanup
            before_stats = state_manager.get_stats()
            
            # Perform cleanup
            removed_count = state_manager.cleanup_old_events(days=days)
            
            # Get stats after cleanup
            after_stats = state_manager.get_stats()
            
            print(f"✅ Cleanup completed:")
            print(f"   • Removed: {removed_count} events")
            print(f"   • Before: {before_stats['total_events']} events")
            print(f"   • After: {after_stats['total_events']} events")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "state cleanup")
    
    def reset(self, args: Namespace) -> int:
        """Reset state (clear all known events)."""
        try:
            # Confirm destructive action
            if not getattr(args, 'force', False):
                print(f"⚠️  This will delete all known events from the database")
                confirm = input("Are you sure? (yes/no): ").lower().strip()
                if confirm != 'yes':
                    print("❌ Reset cancelled")
                    return 0
            
            state_manager = StateManager()
            
            # Get stats before reset
            before_stats = state_manager.get_stats()
            
            # Reset state
            state_manager.reset_state()
            
            print(f"✅ State reset completed:")
            print(f"   • Removed: {before_stats['total_events']} events")
            print(f"   • Database: cleared")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "state reset")