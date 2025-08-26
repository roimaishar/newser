#!/usr/bin/env python3
"""
Data command endpoints for managing stored articles, analyses, and metrics.
"""

import logging
from argparse import Namespace
from typing import List

from .base import BaseCommand

logger = logging.getLogger(__name__)


class DataCommand(BaseCommand):
    """Handle data management operations."""
    
    def execute(self, subcommand: str, args: Namespace) -> int:
        """Execute data subcommand."""
        try:
            if subcommand == "stats":
                return self.stats(args)
            elif subcommand == "cleanup":
                return self.cleanup(args)
            elif subcommand == "export":
                return self.export(args)
            elif subcommand == "recent":
                return self.recent(args)
            else:
                available = ", ".join(self.get_available_subcommands())
                self.logger.error(f"Unknown subcommand '{subcommand}'. Available: {available}")
                return 1
                
        except Exception as e:
            return self.handle_error(e, f"data {subcommand}")
    
    def stats(self, args: Namespace) -> int:
        """Show data storage statistics."""
        try:
            # Get storage statistics
            storage_stats = self.data_manager.get_storage_stats()
            
            print(f"\n=== Data Storage Statistics ===")
            print(f"📁 Total files: {storage_stats['total_files']}")
            print(f"💾 Total size: {storage_stats['total_size_bytes'] / 1024 / 1024:.2f} MB")
            
            for data_type, type_stats in storage_stats['by_type'].items():
                print(f"\n📊 {data_type.title()}:")
                print(f"   • Files: {type_stats['files']}")
                print(f"   • Size: {type_stats['size_bytes'] / 1024:.1f} KB")
                
                if type_stats['date_range']['oldest']:
                    print(f"   • Date range: {type_stats['date_range']['oldest']} to {type_stats['date_range']['newest']}")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "data stats")
    
    def cleanup(self, args: Namespace) -> int:
        """Clean up old data files."""
        try:
            days = getattr(args, 'days', 30)
            
            print(f"🧹 Cleaning up data files older than {days} days...")
            
            # Perform cleanup
            removed_counts = self.data_manager.cleanup_old_data(older_than_days=days)
            
            total_removed = sum(removed_counts.values())
            
            if total_removed > 0:
                print(f"✅ Cleanup completed:")
                for data_type, count in removed_counts.items():
                    if count > 0:
                        print(f"   • {data_type}: {count} files removed")
            else:
                print("✅ No old files found to clean up")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "data cleanup")
    
    def export(self, args: Namespace) -> int:
        """Export data to different formats."""
        try:
            # Future implementation for CSV/JSON exports
            print("📤 Export functionality coming soon...")
            print("Will support:")
            print("  • CSV export of articles and analyses")
            print("  • JSON export with filtering")
            print("  • Metrics dashboard export")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "data export")
    
    def recent(self, args: Namespace) -> int:
        """Show recent data activity."""
        try:
            days = getattr(args, 'days', 3)
            data_type = getattr(args, 'type', 'articles')
            
            if data_type not in ['articles', 'analyses']:
                self.logger.error(f"Invalid data type '{data_type}'. Use 'articles' or 'analyses'")
                return 1
            
            # Get recent runs
            recent_runs = self.data_manager.get_recent_runs(days=days, data_type=data_type)
            
            print(f"\n=== Recent {data_type.title()} - Last {days} Days ===")
            
            if not recent_runs:
                print(f"No {data_type} found in the last {days} days")
                return 0
            
            print(f"📊 Total entries: {len(recent_runs)}")
            
            # Show recent entries
            for i, run in enumerate(recent_runs[:10]):  # Show last 10
                timestamp = run.timestamp.strftime("%m-%d %H:%M")
                
                if data_type == 'articles':
                    print(f"[{timestamp}] Run {run.run_id}: {run.after_dedup} articles ({run.hours_window}h window)")
                    if getattr(args, 'verbose', False):
                        status = "✅" if run.success else "❌"
                        print(f"    {status} Command: {run.command_used}")
                else:  # analyses
                    conf = f"{run.confidence:.1f}" if run.confidence else "N/A"
                    print(f"[{timestamp}] Analysis {run.run_id}: {run.analysis_type} (confidence: {conf})")
                    if getattr(args, 'verbose', False):
                        print(f"    Articles analyzed: {run.articles_analyzed}")
                        print(f"    Processing time: {run.processing_time:.2f}s")
            
            if len(recent_runs) > 10:
                print(f"\n... and {len(recent_runs) - 10} more entries")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "data recent")