#!/usr/bin/env python3
"""
RSS Feed Parser for News Aggregation

Handles parsing of RSS feeds from Israeli news sites (Ynet, Walla) with proper
Hebrew text handling and timezone conversion to Asia/Jerusalem.
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import pytz
from dateutil import parser as date_parser
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Article:
    """
    Represents a single news article with Hebrew analysis support.
    
    Enhanced to support both original content and Hebrew analysis results.
    """
    title: str
    link: str
    source: str
    published: Optional[datetime] = None
    summary: str = ""
    
    # Hebrew analysis fields (populated by AI analysis)
    hebrew_summary: str = ""
    event_id: str = ""
    significance: str = ""
    confidence: float = 0.0
    
    # Metadata
    raw_published_str: Optional[str] = None
    id_hint: Optional[str] = None
    
    def __post_init__(self):
        """Clean and validate data after initialization."""
        self.title = self.title.strip()
        self.link = self.link.strip()
        self.summary = self.summary.strip()
        self.hebrew_summary = self.hebrew_summary.strip()
        self.source = self.source.strip()
        
        # Ensure confidence is in valid range
        self.confidence = max(0.0, min(1.0, self.confidence))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API integration and JSON serialization."""
        return {
            'title': self.title,
            'link': self.link,
            'source': self.source,
            'published': self.published.isoformat() if self.published else None,
            'summary': self.summary,
            'hebrew_summary': self.hebrew_summary,
            'event_id': self.event_id,
            'significance': self.significance,
            'confidence': self.confidence,
            'raw_published_str': self.raw_published_str,
            'id_hint': self.id_hint
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Article':
        """Create Article from dictionary."""
        return cls(
            title=data.get('title', ''),
            link=data.get('link', ''),
            source=data.get('source', ''),
            published=data.get('published'),
            summary=data.get('summary', ''),
            hebrew_summary=data.get('hebrew_summary', ''),
            event_id=data.get('event_id', ''),
            significance=data.get('significance', ''),
            confidence=data.get('confidence', 0.0),
            raw_published_str=data.get('raw_published_str'),
            id_hint=data.get('id_hint')
        )
    
    def __repr__(self):
        return f"Article(title='{self.title[:50]}...', source='{self.source}', event_id='{self.event_id}')"

class FeedParser:
    """RSS Feed parser with Hebrew text support and timezone handling."""
    
    # Default RSS feeds for Israeli news sites
    FEEDS = {
        'ynet': 'http://www.ynet.co.il/Integration/StoryRss2.xml',
        'walla': 'https://rss.walla.co.il/MainRss'
    }
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; NewsAggregator/1.0)'
        })
        
        # Set up timezone for Israel
        self.israel_tz = pytz.timezone('Asia/Jerusalem')
        
    def fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """Fetch and parse RSS feed from URL."""
        try:
            logger.info(f"Fetching feed from: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse the feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"Feed parsing warning for {url}: {feed.bozo_exception}")
                
            return feed
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch feed {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing feed {url}: {e}")
            return None
    
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
    
    def parse_feed_entries(self, feed: feedparser.FeedParserDict, source_name: str) -> List[Article]:
        """Parse entries from a feed into Article objects."""
        articles = []
        
        if not hasattr(feed, 'entries'):
            logger.warning(f"No entries found in feed for {source_name}")
            return articles
            
        logger.info(f"Found {len(feed.entries)} entries in {source_name} feed")
        
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
    
    def get_recent_articles(self, hours: int = 24) -> List[Article]:
        """Fetch articles from all configured feeds within the last N hours."""
        all_articles = []
        
        # Calculate cutoff time
        now = datetime.now(self.israel_tz)
        cutoff_time = now - timedelta(hours=hours)
        
        logger.info(f"Fetching articles since {cutoff_time}")
        
        for source_name, feed_url in self.FEEDS.items():
            feed = self.fetch_feed(feed_url)
            if feed:
                articles = self.parse_feed_entries(feed, source_name)
                
                # Filter by time
                recent_articles = [
                    article for article in articles 
                    if article.published and article.published >= cutoff_time
                ]
                
                logger.info(f"Found {len(recent_articles)} recent articles from {source_name}")
                all_articles.extend(recent_articles)
        
        # Sort by published date (newest first)
        all_articles.sort(key=lambda x: x.published or datetime.min.replace(tzinfo=self.israel_tz), 
                         reverse=True)
        
        return all_articles
    
    def get_feed_info(self, source_name: str) -> Dict:
        """Get feed metadata information."""
        if source_name not in self.FEEDS:
            raise ValueError(f"Unknown source: {source_name}")
            
        feed = self.fetch_feed(self.FEEDS[source_name])
        if not feed:
            return {}
            
        return {
            'title': getattr(feed.feed, 'title', ''),
            'description': getattr(feed.feed, 'description', ''),
            'link': getattr(feed.feed, 'link', ''),
            'updated': getattr(feed.feed, 'updated', ''),
            'entries_count': len(getattr(feed, 'entries', []))
        }