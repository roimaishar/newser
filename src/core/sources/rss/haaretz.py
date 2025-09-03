#!/usr/bin/env python3
"""
Haaretz news source implementation.

Provides Haaretz-specific RSS feed parsing with focus on politics and investigative journalism.
"""

import logging
from typing import List, Dict, Any
from ..base import RSSSource, SourceMetadata

logger = logging.getLogger(__name__)


class HaaretzSource(RSSSource):
    """Haaretz news source with Hebrew political and investigative content."""
    
    # Haaretz RSS feeds (updated URLs)
    FEED_URLS = {
        'main': 'https://www.haaretz.co.il/news/rss/',
        'breaking': 'https://www.haaretz.co.il/news/breaking-news/rss/',
        'politics': 'https://www.haaretz.co.il/news/politics/rss/',
        'opinion': 'https://www.haaretz.co.il/opinions/rss/',
        'english': 'https://www.haaretz.com/rss/'
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize Haaretz source."""
        config = config or {}
        # Use main Hebrew feed as primary
        super().__init__(
            feed_url=self.FEED_URLS['main'],
            config=config
        )
        
        # Include additional feeds if configured
        self.include_all_feeds = config.get('include_all_feeds', False)
        self.include_english = config.get('include_english', False)
    
    def get_metadata(self) -> SourceMetadata:
        """Get Haaretz source metadata."""
        return SourceMetadata(
            name='haaretz',
            display_name='הארץ',
            language='he',
            country='IL',
            update_frequency_minutes=20,
            reliability_score=0.88,
            categories=['politics', 'opinion', 'world', 'investigative']
        )
    
    def get_feed_urls(self) -> List[str]:
        """Get RSS feed URLs for Haaretz."""
        urls = []
        
        if self.include_all_feeds:
            # Include all Hebrew feeds
            urls.extend([
                self.FEED_URLS['main'],
                self.FEED_URLS['breaking'],
                self.FEED_URLS['politics'],
                self.FEED_URLS['opinion']
            ])
            
            # Add English if configured
            if self.include_english:
                urls.append(self.FEED_URLS['english'])
        else:
            # Just main Hebrew feed by default
            urls = [self.FEED_URLS['main']]
        
        return urls
    
    def fetch_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch recent articles from Haaretz."""
        from .parser import RSSParser
        
        parser = RSSParser(
            timeout=self.timeout,
            enable_cache=self.config.get('enable_cache', True)
        )
        
        # Determine which feeds to use
        if self.include_all_feeds:
            feed_urls = {}
            for category, url in self.FEED_URLS.items():
                if category == 'english' and not self.include_english:
                    continue
                feed_urls[f'haaretz_{category}'] = url
        else:
            feed_urls = {'haaretz': self.feed_url}
        
        articles = parser.get_recent_articles(feed_urls, hours)
        
        # Apply Haaretz-specific processing
        processed_articles = []
        for article in articles:
            processed_article = self._process_haaretz_article(article)
            processed_articles.append(processed_article)
        
        return processed_articles
    
    def _process_haaretz_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Haaretz-specific processing to article."""
        # Clean Haaretz-specific title patterns
        title = article.get('title', '')
        title = self._clean_haaretz_title(title)
        article['title'] = title
        
        # Detect language
        source_name = article.get('source', '')
        is_english = 'english' in source_name
        
        # Add Haaretz-specific metadata
        article['source_metadata'] = {
            'publisher': 'Haaretz',
            'category': self._detect_haaretz_category(title, source_name),
            'is_premium': self._detect_premium_content(title),
            'language': 'en' if is_english else 'he',
            'original_source': source_name
        }
        
        # Normalize source name (remove category suffix if present)
        if article.get('source', '').startswith('haaretz_'):
            article['source'] = 'haaretz'
        
        return article
    
    def _clean_haaretz_title(self, title: str) -> str:
        """Clean Haaretz-specific title patterns."""
        # Remove common Haaretz prefixes/suffixes
        prefixes_to_remove = [
            'דעה | ',
            'מאמר דעה: ',
            'ניתוח: ',
            'בלעדי: ',
            'חדשות: ',
        ]
        
        suffixes_to_remove = [
            ' - הארץ',
            ' | הארץ',
            ' – Haaretz',
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
    
    def _detect_haaretz_category(self, title: str, source_name: str) -> str:
        """Detect article category from source name and title content."""
        # Use source name if available
        if 'politics' in source_name:
            return 'politics'
        elif 'opinion' in source_name:
            return 'opinion'
        elif 'world' in source_name:
            return 'world'
        elif 'english' in source_name:
            return 'international'
        
        # Fallback to title analysis
        title_lower = title.lower()
        
        # Politics keywords
        politics_keywords = ['כנסת', 'ממשלה', 'בחירות', 'מפלגה', 'שר', 'ראש הממשלה']
        if any(keyword in title_lower for keyword in politics_keywords):
            return 'politics'
        
        # Opinion indicators
        opinion_keywords = ['דעה', 'מאמר', 'ניתוח', 'טור']
        if any(keyword in title_lower for keyword in opinion_keywords):
            return 'opinion'
        
        return 'general'
    
    def _detect_premium_content(self, title: str) -> bool:
        """Detect if content requires premium subscription."""
        premium_indicators = ['מנויים', 'premium', 'בלעדי למנויים']
        title_lower = title.lower()
        return any(indicator in title_lower for indicator in premium_indicators)
    
    def health_check(self) -> Dict[str, Any]:
        """Check Haaretz RSS feed health."""
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