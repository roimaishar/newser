#!/usr/bin/env python3
"""
Generic RSS parser for news sources.

Extracted from feed_parser.py to be more modular and reusable.
"""

import feedparser
import requests
import pytz
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from typing import List, Dict, Any, Optional
import logging
import hashlib

logger = logging.getLogger(__name__)


class RSSParser:
    """Generic RSS feed parser with caching and timezone handling."""
    
    def __init__(self, timeout: int = 10, enable_cache: bool = True):
        """
        Initialize RSS parser.
        
        Args:
            timeout: Request timeout in seconds
            enable_cache: Whether to enable caching
        """
        self.timeout = timeout
        self.enable_cache = enable_cache
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; NewsAggregator/1.0)'
        })
        
        # Set up timezone for Israel
        self.israel_tz = pytz.timezone('Asia/Jerusalem')
        
        # Initialize cache if enabled
        if self.enable_cache:
            from ...cache import get_rss_cache
            self._cache = get_rss_cache()
        else:
            self._cache = None
    
    def fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """
        Fetch and parse RSS feed from URL with caching support.
        
        Args:
            url: RSS feed URL
            
        Returns:
            Parsed feed object or None if failed
        """
        # Generate cache key
        cache_key = self._generate_cache_key(url)
        
        # Try cache first
        if self._cache:
            cached_feed = self._cache.get(cache_key)
            if cached_feed is not None:
                logger.debug(f"Cache hit for feed: {url}")
                return cached_feed
            logger.debug(f"Cache miss for feed: {url}")
        
        try:
            logger.info(f"Fetching feed from: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse the feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"Feed parsing warning for {url}: {feed.bozo_exception}")
            
            # Cache the result
            if self._cache and feed:
                ttl = self._get_feed_cache_ttl(url)
                self._cache.set(cache_key, feed, ttl)
                logger.debug(f"Cached feed {url} with TTL {ttl}s")
            
            return feed
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch feed {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing feed {url}: {e}")
            return None
    
    def parse_entries(self, feed: feedparser.FeedParserDict, source_name: str) -> List[Dict[str, Any]]:
        """
        Parse entries from a feed into standardized article dictionaries.
        
        Args:
            feed: Parsed feed object
            source_name: Name of the news source
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        if not hasattr(feed, 'entries'):
            logger.warning(f"No entries found in feed for {source_name}")
            return articles
        
        logger.info(f"Found {len(feed.entries)} entries in {source_name} feed")
        
        for entry in feed.entries:
            try:
                article = {
                    'title': getattr(entry, 'title', 'No Title'),
                    'link': getattr(entry, 'link', ''),
                    'source': source_name,
                    'summary': getattr(entry, 'summary', ''),
                    'published': self._parse_published_date(entry),
                    'raw_published_str': getattr(entry, 'published', None),
                    'id_hint': getattr(entry, 'id', None) or getattr(entry, 'guid', None),
                    'author': getattr(entry, 'author', ''),
                    'categories': self._extract_categories(entry)
                }
                
                articles.append(article)
                
            except Exception as e:
                logger.error(f"Error parsing entry from {source_name}: {e}")
                continue
        
        return articles
    
    def get_recent_articles(self, feed_urls: Dict[str, str], hours: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch recent articles from multiple RSS feeds.
        
        Args:
            feed_urls: Dictionary mapping source names to feed URLs
            hours: Number of hours to look back
            
        Returns:
            List of recent articles
        """
        all_articles = []
        
        # Calculate cutoff time
        now = datetime.now(self.israel_tz)
        cutoff_time = now - timedelta(hours=hours)
        
        logger.info(f"Fetching articles since {cutoff_time}")
        
        for source_name, feed_url in feed_urls.items():
            feed = self.fetch_feed(feed_url)
            if feed:
                articles = self.parse_entries(feed, source_name)
                
                # Filter by time
                recent_articles = [
                    article for article in articles 
                    if article['published'] and article['published'] >= cutoff_time
                ]
                
                logger.info(f"Found {len(recent_articles)} recent articles from {source_name}")
                all_articles.extend(recent_articles)
        
        # Sort by published date (newest first)
        all_articles.sort(
            key=lambda x: x['published'] or datetime.min.replace(tzinfo=self.israel_tz), 
            reverse=True
        )
        
        return all_articles
    
    def _parse_published_date(self, entry: Dict) -> Optional[datetime]:
        """Parse published date from feed entry with timezone conversion."""
        date_fields = ['published', 'updated', 'created']
        
        for field in date_fields:
            if hasattr(entry, field):
                date_str = getattr(entry, field, None)
                if date_str:
                    try:
                        # Parse the date
                        dt = date_parser.parse(date_str)
                        
                        # Convert to Israel timezone
                        if dt.tzinfo is None:
                            # Assume UTC if no timezone info
                            dt = pytz.utc.localize(dt)
                        
                        return dt.astimezone(self.israel_tz)
                        
                    except Exception as e:
                        logger.debug(f"Failed to parse date '{date_str}': {e}")
                        continue
        
        # Try published_parsed if available
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                dt = datetime(*entry.published_parsed[:6])
                dt = pytz.utc.localize(dt)
                return dt.astimezone(self.israel_tz)
            except Exception as e:
                logger.debug(f"Failed to parse published_parsed: {e}")
        
        return None
    
    def _extract_categories(self, entry: Dict) -> List[str]:
        """Extract categories from feed entry."""
        categories = []
        
        # Try tags first
        if hasattr(entry, 'tags'):
            for tag in entry.tags:
                if hasattr(tag, 'term'):
                    categories.append(tag.term)
        
        # Try category field
        if hasattr(entry, 'category'):
            categories.append(entry.category)
        
        return categories
    
    def _generate_cache_key(self, url: str) -> str:
        """Generate cache key for feed URL."""
        return f"feed:{hashlib.md5(url.encode()).hexdigest()}"
    
    def _get_feed_cache_ttl(self, url: str) -> int:
        """Get appropriate cache TTL for different feeds."""
        # Israeli news sites update frequently
        if 'ynet.co.il' in url:
            return 600  # 10 minutes for Ynet
        elif 'walla.co.il' in url:
            return 900  # 15 minutes for Walla
        else:
            return 1200  # 20 minutes for other feeds
    
    def clear_cache(self) -> None:
        """Clear RSS feed cache."""
        if self._cache:
            self._cache.clear()
            logger.info("Cleared RSS feed cache")
    
    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics."""
        if self._cache:
            return self._cache.get_stats()
        return None