#!/usr/bin/env python3
"""
Ynet news source implementation.

Provides Ynet-specific RSS feed parsing and customization.
"""

import logging
from typing import List, Dict, Any
from ..base import RSSSource, SourceMetadata

logger = logging.getLogger(__name__)


class YnetSource(RSSSource):
    """Ynet news source with Hebrew content support."""
    
    # Ynet RSS feeds
    FEED_URLS = {
        'breaking': 'http://www.ynet.co.il/Integration/StoryRss2.xml',
        'news': 'https://www.ynet.co.il/Integration/StoryRss1854.xml',
        'politics': 'https://www.ynet.co.il/Integration/StoryRss1863.xml',
        'economy': 'https://www.ynet.co.il/Integration/StoryRss1861.xml'
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize Ynet source."""
        config = config or {}
        # Use breaking news as primary feed
        super().__init__(
            feed_url=self.FEED_URLS['breaking'],
            config=config
        )
        
        # Include additional feeds if configured
        self.include_all_feeds = config.get('include_all_feeds', False)
    
    def get_metadata(self) -> SourceMetadata:
        """Get Ynet source metadata."""
        return SourceMetadata(
            name='ynet',
            display_name='Ynet',
            language='he',
            country='IL',
            update_frequency_minutes=15,
            reliability_score=0.85,
            categories=['news', 'politics', 'economy', 'breaking']
        )
    
    def get_feed_urls(self) -> List[str]:
        """Get RSS feed URLs for Ynet."""
        if self.include_all_feeds:
            return list(self.FEED_URLS.values())
        else:
            # Just breaking news by default
            return [self.FEED_URLS['breaking']]
    
    def fetch_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch recent articles from Ynet."""
        from .parser import RSSParser
        
        parser = RSSParser(
            timeout=self.timeout,
            enable_cache=self.config.get('enable_cache', True)
        )
        
        # Determine which feeds to use
        if self.include_all_feeds:
            feed_urls = {f'ynet_{category}': url for category, url in self.FEED_URLS.items()}
        else:
            feed_urls = {'ynet': self.feed_url}
        
        articles = parser.get_recent_articles(feed_urls, hours)
        
        # Apply Ynet-specific processing
        processed_articles = []
        for article in articles:
            processed_article = self._process_ynet_article(article)
            processed_articles.append(processed_article)
        
        return processed_articles
    
    def _process_ynet_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Ynet-specific processing to article."""
        # Clean Ynet-specific title patterns
        title = article.get('title', '')
        title = self._clean_ynet_title(title)
        article['title'] = title
        
        # Add Ynet-specific metadata
        article['source_metadata'] = {
            'publisher': 'Yedioth Ahronoth',
            'is_breaking': 'חדשות דקות' in title,
            'original_source': article.get('source', 'ynet')
        }
        
        # Normalize source name (remove category suffix if present)
        if article.get('source', '').startswith('ynet_'):
            article['source'] = 'ynet'
        
        return article
    
    def _clean_ynet_title(self, title: str) -> str:
        """Clean Ynet-specific title patterns."""
        # Remove common Ynet prefixes/suffixes
        prefixes_to_remove = [
            'חדשות דקות: ',
            'עדכון: ',
            'בלעדי: ',
        ]
        
        cleaned_title = title
        for prefix in prefixes_to_remove:
            if cleaned_title.startswith(prefix):
                cleaned_title = cleaned_title[len(prefix):]
        
        return cleaned_title.strip()
    
    def health_check(self) -> Dict[str, Any]:
        """Check Ynet RSS feed health."""
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