#!/usr/bin/env python3
"""
Supabase REST API Database Adapter.

Alternative to direct PostgreSQL connection for networks that block port 5432/6543.
Uses Supabase REST API over HTTPS.
"""

import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict

from supabase import create_client, Client

from core.feed_parser import Article
from core.env_loader import get_env_var

logger = logging.getLogger(__name__)


class SupabaseApiError(Exception):
    """Custom exception for Supabase API operations."""
    pass


class SupabaseApiAdapter:
    """
    Database adapter using Supabase REST API.
    
    Alternative to direct PostgreSQL connection for restricted networks.
    """
    
    def __init__(self):
        """Initialize Supabase API client."""
        self.client = self._create_client()
        logger.info("Supabase API adapter initialized")
    
    def _create_client(self) -> Client:
        """Create and configure Supabase client."""
        supabase_url = get_env_var('SUPABASE_URL', required=True)
        
        # Try service key first (for full permissions), fallback to anon key
        supabase_key = get_env_var('SUPABASE_SERVICE_KEY') or get_env_var('SUPABASE_ANON_KEY', required=True)
        
        if not supabase_key:
            raise SupabaseApiError("Neither SUPABASE_SERVICE_KEY nor SUPABASE_ANON_KEY found")
        
        client = create_client(supabase_url, supabase_key)
        return client
    
    # Article Operations
    
    def store_articles(self, articles: List[Article]) -> int:
        """
        Store articles using Supabase API.
        
        Args:
            articles: List of articles to store
            
        Returns:
            Number of articles stored
        """
        if not articles:
            return 0
        
        stored_count = 0
        
        try:
            for article in articles:
                content_hash = self._generate_content_hash(article)
                
                # Check if article already exists
                existing = (self.client.table('articles')
                          .select('id')
                          .eq('content_hash', content_hash)
                          .execute())
                
                if existing.data:
                    continue  # Skip duplicate
                
                # Insert new article
                article_data = {
                    'title': article.title,
                    'link': article.link,
                    'source': article.source,
                    'summary': article.summary,
                    'published_at': article.published.isoformat() if article.published else None,
                    'content_hash': content_hash
                }
                
                result = (self.client.table('articles')
                         .insert(article_data)
                         .execute())
                
                if result.data:
                    stored_count += 1
            
            logger.info(f"Stored {stored_count} new articles via API")
            return stored_count
            
        except Exception as e:
            logger.error(f"Failed to store articles via API: {e}")
            raise SupabaseApiError(f"Failed to store articles: {e}")
    
    def get_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent articles using API."""
        try:
            # Calculate timestamp for filtering
            from_time = (datetime.now(timezone.utc).replace(microsecond=0) - 
                        timedelta(hours=hours)).isoformat()
            
            result = (self.client.table('articles')
                     .select('*')
                     .gte('created_at', from_time)
                     .order('published_at', desc=True)
                     .execute())
            
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get recent articles via API: {e}")
            raise SupabaseApiError(f"Failed to get recent articles: {e}")
    
    # Known Items Operations
    
    def get_known_items(self, item_type: str = 'article') -> List[str]:
        """Get known items using API."""
        try:
            # Get items from last 30 days
            from_time = (datetime.now(timezone.utc).replace(microsecond=0) - 
                        timedelta(days=30)).isoformat()
            
            result = (self.client.table('known_items')
                     .select('item_hash')
                     .eq('item_type', item_type)
                     .gte('last_seen', from_time)
                     .execute())
            
            return [item['item_hash'] for item in result.data]
            
        except Exception as e:
            logger.error(f"Failed to get known items via API: {e}")
            raise SupabaseApiError(f"Failed to get known items: {e}")
    
    def update_known_items(self, item_hashes: List[str], item_type: str = 'article'):
        """Update known items using API."""
        try:
            for item_hash in item_hashes:
                # Use upsert functionality
                item_data = {
                    'item_hash': item_hash,
                    'item_type': item_type,
                    'last_seen': datetime.now(timezone.utc).isoformat()
                }
                
                # Check if exists
                existing = (self.client.table('known_items')
                          .select('id')
                          .eq('item_hash', item_hash)
                          .execute())
                
                if existing.data:
                    # Update existing
                    (self.client.table('known_items')
                     .update({'last_seen': item_data['last_seen']})
                     .eq('item_hash', item_hash)
                     .execute())
                else:
                    # Insert new
                    (self.client.table('known_items')
                     .insert(item_data)
                     .execute())
            
            logger.debug(f"Updated {len(item_hashes)} known items via API")
            
        except Exception as e:
            logger.error(f"Failed to update known items via API: {e}")
            raise SupabaseApiError(f"Failed to update known items: {e}")
    
    # Analysis Operations
    
    def store_analysis(self, run_id: str, analysis_result) -> int:
        """Store analysis result using API."""
        try:
            analysis_data = {
                'run_id': run_id,
                'analysis_type': analysis_result.analysis_type,
                'summary': analysis_result.summary,
                'key_topics': analysis_result.key_topics,
                'bulletins': analysis_result.bulletins,
                'confidence': float(analysis_result.confidence) if analysis_result.confidence else None,
                'articles_analyzed': analysis_result.articles_analyzed,
                'has_new_content': analysis_result.has_new_content,
                'analysis_timestamp': analysis_result.analysis_timestamp.isoformat()
            }
            
            result = (self.client.table('analyses')
                     .insert(analysis_data)
                     .execute())
            
            if result.data:
                analysis_id = result.data[0]['id']
                logger.info(f"Stored analysis with ID {analysis_id} via API")
                return analysis_id
            else:
                raise SupabaseApiError("No data returned from analysis insert")
                
        except Exception as e:
            logger.error(f"Failed to store analysis via API: {e}")
            raise SupabaseApiError(f"Failed to store analysis: {e}")
    
    def get_recent_analyses(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent analyses using API."""
        try:
            from_time = (datetime.now(timezone.utc).replace(microsecond=0) - 
                        timedelta(hours=hours)).isoformat()
            
            result = (self.client.table('analyses')
                     .select('*')
                     .gte('analysis_timestamp', from_time)
                     .order('analysis_timestamp', desc=True)
                     .execute())
            
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get recent analyses via API: {e}")
            raise SupabaseApiError(f"Failed to get recent analyses: {e}")
    
    # Metrics Operations
    
    def store_run_metrics(self, run_id: str, command: str, metrics: Dict[str, Any]):
        """Store run metrics using API."""
        try:
            metrics_data = {
                'run_id': run_id,
                'command_used': command,
                'articles_scraped': metrics.get('articles_scraped', 0),
                'articles_after_dedup': metrics.get('articles_after_dedup', 0),
                'processing_time_seconds': float(metrics.get('processing_time', 0)),
                'success': metrics.get('success', True),
                'error_message': metrics.get('error_message')
            }
            
            result = (self.client.table('run_metrics')
                     .insert(metrics_data)
                     .execute())
            
            logger.debug(f"Stored run metrics for {run_id} via API")
            
        except Exception as e:
            logger.error(f"Failed to store run metrics via API: {e}")
            raise SupabaseApiError(f"Failed to store run metrics: {e}")
    
    # Cleanup Operations
    
    def cleanup_old_records(self) -> int:
        """Cleanup old records using API (simplified)."""
        try:
            deleted_count = 0
            
            # Delete old articles (90+ days)
            old_date = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            result = (self.client.table('articles')
                     .delete()
                     .lt('created_at', old_date)
                     .execute())
            
            logger.info(f"Cleaned up old records via API")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup via API: {e}")
            return 0
    
    # Health Check
    
    def health_check(self) -> Dict[str, Any]:
        """Check API connection health."""
        try:
            # Test connection with simple query
            result = (self.client.table('articles')
                     .select('id')
                     .limit(1)
                     .execute())
            
            # Get table counts
            tables = {}
            for table in ['articles', 'analyses', 'known_items', 'run_metrics']:
                try:
                    count_result = (self.client.table(table)
                                  .select('id')
                                  .execute())
                    tables[table] = len(count_result.data) if count_result.data else 0
                except Exception as e:
                    logger.warning(f"Could not count rows in {table}: {e}")
                    tables[table] = "unknown"
            
            return {
                'connected': True,
                'method': 'REST API',
                'tables': tables,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return {
                'connected': False,
                'method': 'REST API',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _generate_content_hash(self, article: Article) -> str:
        """Generate unique hash for article content."""
        content = f"{article.title}|{article.link}|{article.source}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


# Global instance
_api_adapter = None


def get_api_database() -> SupabaseApiAdapter:
    """Get global Supabase API adapter instance."""
    global _api_adapter
    if _api_adapter is None:
        _api_adapter = SupabaseApiAdapter()
    return _api_adapter
