"""
Command for fetching full article content.
"""

import logging
from typing import Dict, Any

from ..core.content.service import ContentService
from ..core.adapters.supabase_api import SupabaseAPI

logger = logging.getLogger(__name__)


class FetchContentCommand:
    """Command for fetching full article content."""
    
    def __init__(self):
        self.supabase_api = SupabaseAPI()
        self.content_service = ContentService(self.supabase_api)
    
    def execute(self, args) -> Dict[str, Any]:
        """
        Execute content fetching command.
        
        Args:
            args: Command arguments
            
        Returns:
            Dictionary with execution results
        """
        try:
            if args.reset_failed:
                logger.info("Resetting failed articles to pending status")
                self.content_service.reset_failed_articles(hours=args.reset_hours)
            
            if args.max_articles > 0:
                logger.info(f"Fetching content for up to {args.max_articles} articles")
                results = self.content_service.fetch_pending_content(args.max_articles)
                
                logger.info(f"Content fetch completed: {results}")
                return {
                    'success': True,
                    'results': results,
                    'message': f"Processed {sum(results.values())} articles"
                }
            else:
                return {
                    'success': True,
                    'results': {'success': 0, 'failed': 0, 'skipped': 0},
                    'message': "No articles processed (max_articles=0)"
                }
                
        except Exception as e:
            logger.error(f"Content fetch command failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f"Command failed: {e}"
            }
    
    @staticmethod
    def add_arguments(parser):
        """Add command-specific arguments to parser."""
        parser.add_argument(
            '--max-articles',
            type=int,
            default=15,
            help='Maximum number of articles to fetch content for (default: 15)'
        )
        parser.add_argument(
            '--reset-failed',
            action='store_true',
            help='Reset failed articles to pending status before fetching'
        )
        parser.add_argument(
            '--reset-hours',
            type=int,
            default=24,
            help='Reset failed articles from last N hours (default: 24)'
        )
