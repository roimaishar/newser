#!/usr/bin/env python3
"""
BBC Arabic news source implementation.
"""

import logging
from typing import List, Dict, Any
from ..base import RSSSource, SourceMetadata

logger = logging.getLogger(__name__)


class BBCArabicSource(RSSSource):
    """BBC Arabic news source."""
    
    FEED_URLS = {
        'all': 'https://feeds.bbci.co.uk/arabic/rss.xml',
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize BBC Arabic source."""
        config = config or {}
        super().__init__(
            feed_url=self.FEED_URLS['all'],
            config=config
        )
    
    def get_metadata(self) -> SourceMetadata:
        """Get BBC Arabic source metadata."""
        return SourceMetadata(
            name='bbc_arabic',
            display_name='BBC Arabic',
            language='ar',
            country='GB',
            update_frequency_minutes=30,
            reliability_score=0.90,
            categories=['news', 'international', 'middle_east']
        )
    
    def get_feed_urls(self) -> List[str]:
        """Get RSS feed URLs."""
        return [self.FEED_URLS['all']]
    
    def fetch_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch recent articles from BBC Arabic."""
        from .parser import RSSParser
        
        parser = RSSParser(
            timeout=self.timeout,
            enable_cache=self.config.get('enable_cache', True)
        )
        
        feed_urls = {'bbc_arabic': self.feed_url}
        articles = parser.get_recent_articles(feed_urls, hours)
        
        # Apply BBC Arabic-specific processing
        processed_articles = []
        for article in articles:
            processed_article = self._process_article(article)
            if processed_article:
                processed_articles.append(processed_article)
        
        return processed_articles
    
    def _process_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Apply BBC Arabic-specific processing."""
        # Add metadata
        article['source_metadata'] = {
            'publisher': 'BBC',
            'language': 'ar',
            'requires_translation': True,
            'original_source': 'bbc_arabic'
        }
        
        # Mark language
        article['language'] = 'ar'
        article['original_language'] = 'ar'
        
        return article
