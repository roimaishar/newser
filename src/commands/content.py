"""
Content command for managing full article content fetching.
"""

import logging
from typing import Dict, Any

from .base import BaseCommand
from core.content.service import ContentService
from core.adapters.supabase_api import SupabaseApiAdapter

logger = logging.getLogger(__name__)


class ContentCommand(BaseCommand):
    """Content management command for full article text fetching."""
    
    def __init__(self):
        """Initialize content command."""
        super().__init__()
        self.supabase_api = SupabaseApiAdapter()
        self.content_service = ContentService(self.supabase_api)
    
    def execute(self, subcommand: str, args) -> int:
        """
        Execute content subcommand.
        
        Args:
            subcommand: The subcommand to execute
            args: Parsed command arguments
            
        Returns:
            Exit code
        """
        try:
            if subcommand == 'fetch':
                return self._handle_fetch(args)
            elif subcommand == 'status':
                return self._handle_status(args)
            elif subcommand == 'reset':
                return self._handle_reset(args)
            else:
                logger.error(f"Unknown content subcommand: {subcommand}")
                return 1
                
        except Exception as e:
            logger.error(f"Content command failed: {e}")
            return 1
    
    def _handle_fetch(self, args) -> int:
        """Handle content fetch subcommand."""
        try:
            logger.info("Starting content fetch operation")
            
            # Reset failed articles if requested
            if args.reset_failed:
                logger.info(f"Resetting failed articles from last {args.reset_hours} hours")
                self.content_service.reset_failed_articles(hours=args.reset_hours)
            
            # Fetch content for pending articles
            logger.info(f"Fetching content for up to {args.max_articles} articles")
            results = self.content_service.fetch_pending_content(args.max_articles)
            
            # Report results
            total_processed = sum(results.values())
            logger.info(f"Content fetch completed:")
            logger.info(f"  Success: {results['success']}")
            logger.info(f"  Failed: {results['failed']}")
            logger.info(f"  Skipped: {results['skipped']}")
            logger.info(f"  Total processed: {total_processed}")
            
            if results['success'] > 0:
                logger.info("✅ Content fetch successful")
                return 0
            elif total_processed == 0:
                logger.info("ℹ️ No articles needed content fetching")
                return 0
            else:
                logger.warning("⚠️ Content fetch completed with some failures")
                return 0  # Don't fail the command for partial failures
                
        except Exception as e:
            logger.error(f"Content fetch failed: {e}")
            return 1
    
    def _handle_status(self, args) -> int:
        """Handle content status subcommand."""
        try:
            logger.info(f"Checking content status for last {args.hours} hours")
            
            # Get articles needing content
            pending_articles = self.content_service.get_articles_needing_content(limit=100)
            
            # Get articles with content
            articles_with_content = self.content_service.get_articles_with_content(
                hours=args.hours, limit=100
            )
            
            # Get status counts from database
            response = self.supabase_api.client.table('articles').select(
                'fetch_status', count='exact'
            ).execute()
            
            status_counts = {}
            if response.data:
                for row in response.data:
                    status = row.get('fetch_status') or 'pending'
                    status_counts[status] = status_counts.get(status, 0) + 1
            
            # Report status
            logger.info("📊 Content Fetch Status:")
            logger.info(f"  Pending: {len(pending_articles)} articles")
            logger.info(f"  With content (last {args.hours}h): {len(articles_with_content)} articles")
            
            if status_counts:
                logger.info("📈 Overall Status Breakdown:")
                for status, count in status_counts.items():
                    logger.info(f"  {status.capitalize()}: {count}")
            
            return 0
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return 1
    
    def _handle_reset(self, args) -> int:
        """Handle content reset subcommand."""
        try:
            if not args.force:
                response = input(f"Reset content fetch status for articles from last {args.hours} hours? (y/N): ")
                if response.lower() not in ['y', 'yes']:
                    logger.info("Reset cancelled")
                    return 0
            
            logger.info(f"Resetting content fetch status for last {args.hours} hours")
            self.content_service.reset_failed_articles(hours=args.hours)
            
            logger.info("✅ Content fetch status reset completed")
            return 0
            
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            return 1
