#!/usr/bin/env python3
"""
Article Database Service

Handles all database operations related to news articles.
"""

import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from core.feed_parser import Article

logger = logging.getLogger(__name__)


class ArticleService:
    """Service for article-related database operations."""
    
    def __init__(self, connection_manager):
        """
        Initialize article service.
        
        Args:
            connection_manager: Database connection manager instance
        """
        self.connection_manager = connection_manager
    
    def store_articles(self, articles: List[Article]) -> int:
        """
        Store articles in database with deduplication.
        
        Args:
            articles: List of Article objects
            
        Returns:
            Number of new articles stored
        """
        if not articles:
            return 0
        
        stored_count = 0
        
        try:
            with self.connection_manager.get_cursor() as cursor:
                for article in articles:
                    content_hash = self._generate_content_hash(article)
                    
                    # Insert with ON CONFLICT to handle duplicates
                    cursor.execute("""
                        INSERT INTO articles (title, link, source, summary, published_at, content_hash, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (content_hash) DO NOTHING
                        RETURNING id
                    """, (
                        article.title,
                        article.link,
                        article.source,
                        article.summary,
                        article.published,
                        content_hash,
                        datetime.now(timezone.utc)
                    ))
                    
                    if cursor.fetchone():
                        stored_count += 1
                        
            logger.info(f"Stored {stored_count} new articles out of {len(articles)} provided")
            return stored_count
            
        except Exception as e:
            logger.error(f"Failed to store articles: {e}")
            raise
    
    def get_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get articles from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of article dictionaries
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT title, link, source, summary, published_at, content_hash, created_at
                    FROM articles
                    WHERE created_at >= %s
                    ORDER BY published_at DESC NULLS LAST, created_at DESC
                    LIMIT 1000
                """, (datetime.now(timezone.utc) - timedelta(hours=hours),))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get recent articles: {e}")
            raise
    
    def get_articles_by_timeframe(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        Get articles within a specific timeframe.
        
        Args:
            start_time: Start of timeframe
            end_time: End of timeframe
            
        Returns:
            List of article dictionaries
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT title, link, source, summary, published_at, content_hash, created_at
                    FROM articles
                    WHERE created_at BETWEEN %s AND %s
                    ORDER BY published_at DESC NULLS LAST, created_at DESC
                """, (start_time, end_time))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get articles by timeframe: {e}")
            raise
    
    def get_articles_count(self, hours: Optional[int] = None) -> int:
        """
        Get count of articles, optionally within last N hours.
        
        Args:
            hours: Optional hours to look back, if None counts all articles
            
        Returns:
            Number of articles
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                if hours is not None:
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM articles
                        WHERE created_at >= %s
                    """, (datetime.now(timezone.utc) - timedelta(hours=hours),))
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM articles")
                
                result = cursor.fetchone()
                return result['count'] if result else 0
                
        except Exception as e:
            logger.error(f"Failed to get articles count: {e}")
            raise
    
    def cleanup_old_articles(self, days: int = 30) -> int:
        """
        Remove articles older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of articles deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    DELETE FROM articles
                    WHERE created_at < %s
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} articles older than {days} days")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old articles: {e}")
            raise
    
    def get_article_stats(self) -> Dict[str, Any]:
        """
        Get article statistics.
        
        Returns:
            Dictionary with article statistics
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                # Get basic counts
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_articles,
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as articles_24h,
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as articles_7d,
                        MIN(created_at) as oldest_article,
                        MAX(created_at) as newest_article
                    FROM articles
                """)
                
                stats = dict(cursor.fetchone())
                
                # Get source breakdown
                cursor.execute("""
                    SELECT source, COUNT(*) as count
                    FROM articles
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY source
                    ORDER BY count DESC
                """)
                
                stats['sources_7d'] = {row['source']: row['count'] for row in cursor.fetchall()}
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get article stats: {e}")
            raise
    
    def _generate_content_hash(self, article: Article) -> str:
        """Generate unique hash for article content."""
        content = f"{article.title}|{article.link}|{article.source}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()