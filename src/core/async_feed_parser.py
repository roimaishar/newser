#!/usr/bin/env python3
"""
Async RSS Feed Parser

Provides asynchronous RSS feed fetching with parallel processing capabilities.
Significant performance improvement for fetching multiple feeds simultaneously.
Compatible with GitHub Actions free tier.
"""

import asyncio
import aiohttp
import feedparser
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import pytz
from dateutil import parser as date_parser
import hashlib
import time

from .feed_parser import Article
from .cache import get_rss_cache

logger = logging.getLogger(__name__)


class AsyncFeedParser:
    """Async RSS Feed parser with parallel fetching and caching."""
    
    # Default RSS feeds for Israeli news sites
    FEEDS = {
        'ynet': 'http://www.ynet.co.il/Integration/StoryRss2.xml',
        'walla': 'https://rss.walla.co.il/MainRss'
    }
    
    def __init__(self, 
                 timeout: int = 10,
                 max_concurrent: int = 5,
                 enable_cache: bool = True):
        """
        Initialize async feed parser.
        
        Args:
            timeout: Request timeout in seconds
            max_concurrent: Maximum concurrent requests
            enable_cache: Whether to use caching
        """
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.enable_cache = enable_cache
        
        # Set up timezone for Israel
        self.israel_tz = pytz.timezone('Asia/Jerusalem')
        
        # Initialize cache
        if self.enable_cache:
            self._cache = get_rss_cache()
        else:
            self._cache = None
        
        # Session will be created per async context
        self._session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; NewsAggregator/1.0)'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    async def fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """
        Fetch and parse RSS feed from URL asynchronously.
        
        Args:
            url: RSS feed URL
            
        Returns:
            Parsed feed or None if failed
        """
        if not self._session:
            raise RuntimeError("AsyncFeedParser must be used as async context manager")
        
        # Generate cache key
        cache_key = self._generate_cache_key(url)
        
        # Try to get from cache first
        if self._cache:
            cached_feed = self._cache.get(cache_key)
            if cached_feed is not None:
                logger.debug(f"Cache hit for feed: {url}")
                return cached_feed
            logger.debug(f"Cache miss for feed: {url}")
        
        try:
            logger.info(f"Fetching feed from: {url}")
            async with self._session.get(url) as response:
                response.raise_for_status()
                content = await response.read()
                
                # Parse the feed (feedparser is synchronous, but parsing is fast)
                feed = feedparser.parse(content)
                
                if feed.bozo:
                    logger.warning(f"Feed parsing warning for {url}: {feed.bozo_exception}")
                
                # Cache the result if caching is enabled
                if self._cache and feed:
                    ttl = self._get_feed_cache_ttl(url)
                    self._cache.set(cache_key, feed, ttl)
                    logger.debug(f"Cached feed {url} with TTL {ttl}s")
                
                return feed
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching feed {url}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching feed {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing feed {url}: {e}")
            return None
    
    async def fetch_all_feeds(self, 
                              feed_urls: Optional[Dict[str, str]] = None) -> Dict[str, Optional[feedparser.FeedParserDict]]:
        """
        Fetch multiple RSS feeds in parallel.
        
        Args:
            feed_urls: Dictionary of {source_name: url}. If None, uses default feeds.
            
        Returns:
            Dictionary of {source_name: parsed_feed}
        """
        if feed_urls is None:
            feed_urls = self.FEEDS
        
        logger.info(f"Fetching {len(feed_urls)} feeds in parallel")
        start_time = time.time()
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def fetch_with_semaphore(source_name: str, url: str):
            async with semaphore:
                feed = await self.fetch_feed(url)
                return source_name, feed
        
        # Create tasks for all feeds
        tasks = [
            fetch_with_semaphore(source_name, url)
            for source_name, url in feed_urls.items()
        ]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        feeds = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feed fetch failed: {result}")
                continue
            
            source_name, feed = result
            feeds[source_name] = feed
        
        duration = time.time() - start_time
        successful = sum(1 for feed in feeds.values() if feed is not None)
        logger.info(f"Fetched {successful}/{len(feed_urls)} feeds in {duration:.2f}s")
        
        return feeds
    
    def parse_feed_entries(self, feed: feedparser.FeedParserDict, source_name: str) -> List[Article]:
        """
        Parse entries from a feed into Article objects.
        
        Args:
            feed: Parsed RSS feed
            source_name: Name of the source (e.g., 'ynet', 'walla')
            
        Returns:
            List of Article objects
        """
        articles = []
        
        if not hasattr(feed, 'entries'):
            logger.warning(f"No entries found in feed for {source_name}")
            return articles
            
        logger.debug(f"Found {len(feed.entries)} entries in {source_name} feed")
        
        for entry in feed.entries:
            try:
                title = getattr(entry, 'title', 'No Title')
                link = getattr(entry, 'link', '')
                summary = getattr(entry, 'summary', '')
                
                # Parse published date
                published = self.parse_published_date(entry)
                
                article = Article(
                    title=title,
                    link=link,
                    source=source_name,
                    published=published,
                    summary=summary,
                    raw_published_str=getattr(entry, 'published', None),
                    id_hint=getattr(entry, 'id', None) or getattr(entry, 'guid', None)
                )
                
                articles.append(article)
                
            except Exception as e:
                logger.error(f"Error parsing entry from {source_name}: {e}")
                continue
        
        return articles
    
    async def get_recent_articles(self, 
                                  hours: int = 24,
                                  feed_urls: Optional[Dict[str, str]] = None) -> List[Article]:
        """
        Fetch articles from all configured feeds within the last N hours.
        
        Args:
            hours: Number of hours to look back
            feed_urls: Optional custom feed URLs
            
        Returns:
            List of recent articles
        """
        # Fetch all feeds in parallel
        feeds = await self.fetch_all_feeds(feed_urls)
        
        all_articles = []
        cutoff_time = datetime.now(self.israel_tz) - timedelta(hours=hours)
        
        logger.info(f"Processing articles since {cutoff_time}")
        
        # Process each feed
        for source_name, feed in feeds.items():
            if feed is None:
                logger.warning(f"Skipping failed feed: {source_name}")
                continue
            
            articles = self.parse_feed_entries(feed, source_name)
            
            # Filter by time
            recent_articles = [
                article for article in articles 
                if article.published and article.published >= cutoff_time
            ]
            
            logger.info(f"Found {len(recent_articles)} recent articles from {source_name}")
            all_articles.extend(recent_articles)
        
        # Sort by published date (newest first)
        all_articles.sort(
            key=lambda x: x.published or datetime.min.replace(tzinfo=self.israel_tz), 
            reverse=True
        )
        
        return all_articles
    
    def parse_published_date(self, entry: Dict) -> Optional[datetime]:
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
    
    def _generate_cache_key(self, url: str) -> str:
        """Generate cache key for feed URL."""
        return f"async_feed:{hashlib.md5(url.encode()).hexdigest()}"
    
    def _get_feed_cache_ttl(self, url: str) -> int:
        """Get appropriate cache TTL for different feeds."""
        if 'ynet.co.il' in url:
            return 600  # 10 minutes for Ynet (very active)
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


# Convenience function for synchronous usage
def fetch_feeds_async(hours: int = 24, 
                      feed_urls: Optional[Dict[str, str]] = None,
                      max_concurrent: int = 5,
                      timeout: int = 10,
                      enable_cache: bool = True) -> List[Article]:
    """
    Convenience function to fetch feeds asynchronously from synchronous code.
    
    Args:
        hours: Hours to look back for articles
        feed_urls: Optional custom feed URLs
        max_concurrent: Maximum concurrent requests
        timeout: Request timeout in seconds
        enable_cache: Whether to use caching
        
    Returns:
        List of articles
    """
    async def _fetch():
        async with AsyncFeedParser(
            timeout=timeout,
            max_concurrent=max_concurrent,
            enable_cache=enable_cache
        ) as parser:
            return await parser.get_recent_articles(hours, feed_urls)
    
    # Run in event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _fetch())
                return future.result()
        else:
            return loop.run_until_complete(_fetch())
    except RuntimeError:
        # No event loop, create new one
        return asyncio.run(_fetch())