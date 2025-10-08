"""
Content service for managing full-text article fetching and storage.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json

from .fetcher import ContentFetcher
from ..adapters.supabase_api import SupabaseApiAdapter

logger = logging.getLogger(__name__)


class ContentService:
    """Service for fetching and storing full article content."""
    
    def __init__(self, supabase_api: SupabaseApiAdapter):
        """
        Initialize content service.
        
        Args:
            supabase_api: Supabase API instance for database operations
        """
        self.supabase_api = supabase_api
        self.fetcher = ContentFetcher()
    
    def get_articles_needing_content(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Get articles that need full content fetching.
        
        Args:
            limit: Maximum number of articles to return
            
        Returns:
            List of article dictionaries
        """
        try:
            # Query articles where fetch_status is 'pending' (includes NULL due to default)
            response = self.supabase_api.client.table('articles').select(
                'id, title, link, source, published_at, fetch_status'
            ).eq('fetch_status', 'pending').order('published_at', desc=True).limit(limit).execute()
            
            articles = response.data if response.data else []
            logger.info(f"Found {len(articles)} articles needing content fetch")
            return articles
            
        except Exception as e:
            logger.error(f"Failed to get articles needing content: {e}")
            return []
    
    def update_article_content(self, article_id: int, content_data: Dict[str, Any], status: str = 'fetched'):
        """
        Update article with fetched content.
        
        Args:
            article_id: Article ID to update
            content_data: Extracted content data
            status: Fetch status ('fetched', 'failed')
        """
        try:
            update_data = {
                'fetch_status': status,
                'full_text_fetched_at': datetime.now(timezone.utc).isoformat()
            }
            
            if status == 'fetched' and content_data.get('text'):
                update_data['full_text'] = content_data['text']
            
            response = self.supabase_api.client.table('articles').update(
                update_data
            ).eq('id', article_id).execute()
            
            if response.data:
                logger.debug(f"Updated article {article_id} with content (status: {status})")
            else:
                logger.warning(f"No rows updated for article {article_id}")
                
        except Exception as e:
            logger.error(f"Failed to update article {article_id}: {e}")
    
    def fetch_content_for_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Fetch full content for a list of articles.
        
        Args:
            articles: List of article dictionaries
            
        Returns:
            Dictionary with success/failure counts
        """
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for article in articles:
            article_id = article['id']
            url = article['link']
            source = article.get('source', 'unknown')
            
            # Skip non-supported sources for now
            if source.lower() not in ['ynet', 'walla']:
                logger.debug(f"Skipping unsupported source: {source}")
                results['skipped'] += 1
                continue
            
            logger.info(f"Fetching content for article {article_id}: {url}")
            
            try:
                # Fetch and extract content
                content_data = self.fetcher.fetch_and_extract(url)
                
                if content_data and content_data.get('text'):
                    # Store successful content
                    self.update_article_content(article_id, content_data, 'fetched')
                    results['success'] += 1
                    
                    logger.info(f"Successfully fetched content for article {article_id} "
                              f"({len(content_data['text'])} chars)")
                else:
                    # Mark as failed
                    self.update_article_content(article_id, {}, 'failed')
                    results['failed'] += 1
                    
                    logger.warning(f"Failed to extract content from {url}")
                    
            except Exception as e:
                logger.error(f"Error fetching content for article {article_id}: {e}")
                self.update_article_content(article_id, {}, 'failed')
                results['failed'] += 1
        
        logger.info(f"Content fetch completed: {results['success']} success, "
                   f"{results['failed']} failed, {results['skipped']} skipped")
        
        return results
    
    def fetch_pending_content(self, max_articles: int = 15) -> Dict[str, int]:
        """
        Fetch content for articles with pending status.
        
        Args:
            max_articles: Maximum number of articles to process
            
        Returns:
            Dictionary with processing results
        """
        articles = self.get_articles_needing_content(max_articles)
        
        if not articles:
            logger.info("No articles need content fetching")
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        return self.fetch_content_for_articles(articles)
    
    def get_articles_with_content(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent articles that have full content available.
        
        Args:
            hours: Hours back to look for articles
            limit: Maximum number of articles to return
            
        Returns:
            List of articles with full content
        """
        try:
            # Calculate time threshold
            from datetime import timedelta
            threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            response = self.supabase_api.client.table('articles').select(
                'id, title, link, source, summary, published_at, full_text, created_at'
            ).eq('fetch_status', 'fetched').gte(
                'published_at', threshold.isoformat()
            ).order('published_at', desc=True).limit(limit).execute()
            
            articles = response.data if response.data else []
            logger.info(f"Found {len(articles)} articles with full content from last {hours}h")
            return articles
            
        except Exception as e:
            logger.error(f"Failed to get articles with content: {e}")
            return []
    
    def reset_failed_articles(self, hours: int = 24):
        """
        Reset failed articles to pending status for retry.
        
        Args:
            hours: Reset articles failed within this many hours
        """
        try:
            from datetime import timedelta
            threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            response = self.supabase_api.client.table('articles').update({
                'fetch_status': 'pending',
                'full_text_fetched_at': None
            }).eq('fetch_status', 'failed').gte(
                'full_text_fetched_at', threshold.isoformat()
            ).execute()
            
            count = len(response.data) if response.data else 0
            logger.info(f"Reset {count} failed articles to pending status")
            
        except Exception as e:
            logger.error(f"Failed to reset failed articles: {e}")
