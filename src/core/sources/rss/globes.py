#!/usr/bin/env python3
"""
Globes news source implementation.

Provides Globes-specific RSS feed parsing with focus on economic and business news.
"""

import logging
from typing import List, Dict, Any
from ..base import RSSSource, SourceMetadata

logger = logging.getLogger(__name__)


class GlobesSource(RSSSource):
    """Globes news source with Hebrew economic content focus."""
    
    # Globes RSS feeds
    FEED_URLS = {
        'main': 'https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=585',
        'technology': 'https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=586',
        'finance': 'https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=588',
        'real_estate': 'https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=590'
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize Globes source."""
        config = config or {}
        # Use main feed as primary
        super().__init__(
            feed_url=self.FEED_URLS['main'],
            config=config
        )
        
        # Include additional feeds if configured
        self.include_all_feeds = config.get('include_all_feeds', False)
    
    def get_metadata(self) -> SourceMetadata:
        """Get Globes source metadata."""
        return SourceMetadata(
            name='globes',
            display_name='גלובס',
            language='he',
            country='IL',
            update_frequency_minutes=30,
            reliability_score=0.82,
            categories=['economy', 'finance', 'technology', 'real_estate']
        )
    
    def get_feed_urls(self) -> List[str]:
        """Get RSS feed URLs for Globes."""
        if self.include_all_feeds:
            return list(self.FEED_URLS.values())
        else:
            # Just main economic news by default
            return [self.FEED_URLS['main']]
    
    def fetch_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch recent articles from Globes."""
        from .parser import RSSParser
        
        parser = RSSParser(
            timeout=self.timeout,
            enable_cache=self.config.get('enable_cache', True)
        )
        
        # Determine which feeds to use
        if self.include_all_feeds:
            feed_urls = {f'globes_{category}': url for category, url in self.FEED_URLS.items()}
        else:
            feed_urls = {'globes': self.feed_url}
        
        articles = parser.get_recent_articles(feed_urls, hours)
        
        # Apply Globes-specific processing
        processed_articles = []
        for article in articles:
            processed_article = self._process_globes_article(article)
            processed_articles.append(processed_article)
        
        return processed_articles
    
    def _process_globes_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Globes-specific processing to article."""
        # Clean Globes-specific title patterns
        title = article.get('title', '')
        title = self._clean_globes_title(title)
        article['title'] = title
        
        # Add Globes-specific metadata
        article['source_metadata'] = {
            'publisher': 'Globes',
            'category': self._detect_globes_category(title),
            'is_economic': True,
            'original_source': article.get('source', 'globes')
        }
        
        # Normalize source name (remove category suffix if present)
        if article.get('source', '').startswith('globes_'):
            article['source'] = 'globes'
        
        return article
    
    def _clean_globes_title(self, title: str) -> str:
        """Clean Globes-specific title patterns."""
        # Remove common Globes prefixes/suffixes
        prefixes_to_remove = [
            'בלעדי: ',
            'דיווח: ',
            'ניתוח: ',
            'עדכון שוק ההון: ',
        ]
        
        suffixes_to_remove = [
            ' - גלובס',
            ' | גלובס',
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
    
    def _detect_globes_category(self, title: str) -> str:
        """Detect article category from title content."""
        title_lower = title.lower()
        
        # Technology keywords
        tech_keywords = ['הייטק', 'טכנולוגיה', 'סטארט-אפ', 'יוניקורן', 'פינטק', 'קריפטו']
        if any(keyword in title_lower for keyword in tech_keywords):
            return 'technology'
        
        # Real estate keywords
        real_estate_keywords = ['נדלן', 'דירות', 'בנייה', 'פרויקט', 'מגורים']
        if any(keyword in title_lower for keyword in real_estate_keywords):
            return 'real_estate'
        
        # Finance keywords
        finance_keywords = ['בורסה', 'מניות', 'שקל', 'דולר', 'ריבית', 'בנק']
        if any(keyword in title_lower for keyword in finance_keywords):
            return 'finance'
        
        return 'economy'
    
    def health_check(self) -> Dict[str, Any]:
        """Check Globes RSS feed health."""
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