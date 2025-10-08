#!/usr/bin/env python3
"""
Al Jazeera Arabic news source implementation.
"""

import logging
from typing import List, Dict, Any
from ..base import RSSSource, SourceMetadata

logger = logging.getLogger(__name__)


class AlJazeeraSource(RSSSource):
    """Al Jazeera Arabic news source."""
    
    FEED_URLS = {
        'all': 'https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9',
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize Al Jazeera source."""
        config = config or {}
        super().__init__(
            feed_url=self.FEED_URLS['all'],
            config=config
        )
    
    def get_metadata(self) -> SourceMetadata:
        """Get Al Jazeera source metadata."""
        return SourceMetadata(
            name='aljazeera',
            display_name='Al Jazeera Arabic',
            language='ar',
            country='QA',
            update_frequency_minutes=15,
            reliability_score=0.80,
            categories=['news', 'politics', 'middle_east']
        )
    
    def get_feed_urls(self) -> List[str]:
        """Get RSS feed URLs."""
        return [self.FEED_URLS['all']]
    
    def fetch_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch recent articles from Al Jazeera."""
        from .parser import RSSParser
        
        parser = RSSParser(
            timeout=self.timeout,
            enable_cache=self.config.get('enable_cache', True)
        )
        
        feed_urls = {'aljazeera': self.feed_url}
        articles = parser.get_recent_articles(feed_urls, hours)
        
        # Apply Al Jazeera-specific processing
        processed_articles = []
        for article in articles:
            processed_article = self._process_article(article)
            if processed_article:
                processed_articles.append(processed_article)
        
        return processed_articles
    
    def _process_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Al Jazeera-specific processing."""
        # Add metadata
        article['source_metadata'] = {
            'publisher': 'Al Jazeera Media Network',
            'language': 'ar',
            'requires_translation': True,
            'original_source': 'aljazeera'
        }
        
        # Mark language
        article['language'] = 'ar'
        article['original_language'] = 'ar'
        
        return article
