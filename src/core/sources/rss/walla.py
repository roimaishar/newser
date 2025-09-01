#!/usr/bin/env python3
"""
Walla news source implementation.

Provides Walla-specific RSS feed parsing and customization.
"""

import logging
from typing import List, Dict, Any
from ..base import RSSSource, SourceMetadata

logger = logging.getLogger(__name__)


class WallaSource(RSSSource):
    """Walla news source with Hebrew content support."""
    
    # Walla RSS feeds
    FEED_URLS = {
        'main': 'https://rss.walla.co.il/MainRss',
        'news': 'https://rss.walla.co.il/news.xml',
        'politics': 'https://rss.walla.co.il/politics.xml',
        'economy': 'https://rss.walla.co.il/economy.xml'
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize Walla source."""
        config = config or {}
        # Use main RSS as primary feed
        super().__init__(
            feed_url=self.FEED_URLS['main'],
            config=config
        )
        
        # Include additional feeds if configured
        self.include_all_feeds = config.get('include_all_feeds', False)
    
    def get_metadata(self) -> SourceMetadata:
        """Get Walla source metadata."""
        return SourceMetadata(
            name='walla',
            display_name='וואלה!',
            language='he',
            country='IL',
            update_frequency_minutes=20,
            reliability_score=0.80,
            categories=['news', 'politics', 'economy', 'lifestyle']
        )
    
    def get_feed_urls(self) -> List[str]:
        """Get RSS feed URLs for Walla."""
        if self.include_all_feeds:
            return list(self.FEED_URLS.values())
        else:
            # Just main feed by default
            return [self.FEED_URLS['main']]
    
    def fetch_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch recent articles from Walla."""
        from .parser import RSSParser
        
        parser = RSSParser(
            timeout=self.timeout,
            enable_cache=self.config.get('enable_cache', True)
        )
        
        # Determine which feeds to use
        if self.include_all_feeds:
            feed_urls = {f'walla_{category}': url for category, url in self.FEED_URLS.items()}
        else:
            feed_urls = {'walla': self.feed_url}
        
        articles = parser.get_recent_articles(feed_urls, hours)
        
        # Apply Walla-specific processing
        processed_articles = []
        for article in articles:
            processed_article = self._process_walla_article(article)
            processed_articles.append(processed_article)
        
        return processed_articles
    
    def _process_walla_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Walla-specific processing to article."""
        # Clean Walla-specific title patterns
        title = article.get('title', '')
        title = self._clean_walla_title(title)
        article['title'] = title
        
        # Add Walla-specific metadata
        article['source_metadata'] = {
            'publisher': 'וואלה!',
            'is_sponsored': 'פרסומת' in title or 'ממומן' in title,
            'original_source': article.get('source', 'walla')
        }
        
        # Normalize source name (remove category suffix if present)
        if article.get('source', '').startswith('walla_'):
            article['source'] = 'walla'
        
        return article
    
    def _clean_walla_title(self, title: str) -> str:
        """Clean Walla-specific title patterns."""
        # Remove common Walla prefixes/suffixes
        prefixes_to_remove = [
            'וואלה!: ',
            'בלעדי ב-walla!: ',
            'דעה: ',
            'ספורט: ',
        ]
        
        suffixes_to_remove = [
            ' - וואלה!',
            ' | וואלה!'
        ]
        
        cleaned_title = title
        
        # Remove prefixes
        for prefix in prefixes_to_remove:
            if cleaned_title.startswith(prefix):
                cleaned_title = cleaned_title[len(prefix):]
        
        # Remove suffixes
        for suffix in suffixes_to_remove:
            if cleaned_title.endswith(suffix):
                cleaned_title = cleaned_title[:-len(suffix)]
        
        return cleaned_title.strip()
    
    def health_check(self) -> Dict[str, Any]:
        """Check Walla RSS feed health."""
        health_results = {}
        
        for category, url in self.FEED_URLS.items():
            try:
                import requests
                response = requests.head(url, timeout=self.timeout)
                health_results[f'feed_{category}'] = {
                    'available': response.status_code == 200,
                    'status_code': response.status_code,
                    'response_time_ms': response.elapsed.total_seconds() * 1000
                }
            except Exception as e:
                health_results[f'feed_{category}'] = {
                    'available': False,
                    'error': str(e)
                }
        
        # Overall health
        all_available = all(
            result.get('available', False) 
            for result in health_results.values()
        )
        
        health_results['overall'] = {
            'available': all_available,
            'feeds_checked': len(self.FEED_URLS),
            'feeds_available': sum(1 for r in health_results.values() if r.get('available', False))
        }
        
        return health_results