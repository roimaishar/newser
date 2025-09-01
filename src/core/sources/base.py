#!/usr/bin/env python3
"""
Base classes for news sources.

Defines abstract interfaces for pluggable news source architecture.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


class SourceError(Exception):
    """Exception raised by news source operations."""
    pass


@dataclass
class SourceMetadata:
    """Metadata about a news source."""
    name: str
    display_name: str
    language: str
    country: str
    update_frequency_minutes: int
    reliability_score: float  # 0.0-1.0
    categories: List[str]
    
    def __post_init__(self):
        """Validate metadata."""
        if not 0.0 <= self.reliability_score <= 1.0:
            raise ValueError("reliability_score must be between 0.0 and 1.0")


class NewsSource(ABC):
    """
    Abstract base class for all news sources.
    
    Implementations must provide methods to fetch articles and metadata.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize news source.
        
        Args:
            config: Source-specific configuration
        """
        self.config = config or {}
        self._metadata = None
    
    @abstractmethod
    def fetch_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch recent articles from this source.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of article dictionaries with standardized format
            
        Raises:
            SourceError: If fetching fails
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> SourceMetadata:
        """
        Get metadata about this news source.
        
        Returns:
            SourceMetadata object
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Check if source is available and working.
        
        Returns:
            Health status dictionary
        """
        pass
    
    def get_cache_ttl(self) -> int:
        """Get appropriate cache TTL for this source in seconds."""
        metadata = self.get_metadata()
        return metadata.update_frequency_minutes * 60 // 2  # Half the update frequency
    
    def normalize_article(self, raw_article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize raw article data to standard format.
        
        Args:
            raw_article: Source-specific article data
            
        Returns:
            Standardized article dictionary
        """
        return {
            'title': self._extract_title(raw_article),
            'link': self._extract_link(raw_article),
            'source': self.get_metadata().name,
            'published': self._extract_published_date(raw_article),
            'summary': self._extract_summary(raw_article),
            'content': self._extract_content(raw_article),
            'author': self._extract_author(raw_article),
            'categories': self._extract_categories(raw_article),
            'raw_data': raw_article  # Keep original for debugging
        }
    
    def _extract_title(self, raw_article: Dict[str, Any]) -> str:
        """Extract title from raw article data."""
        return raw_article.get('title', '').strip()
    
    def _extract_link(self, raw_article: Dict[str, Any]) -> str:
        """Extract link from raw article data."""
        return raw_article.get('link', '').strip()
    
    def _extract_published_date(self, raw_article: Dict[str, Any]) -> Optional[datetime]:
        """Extract published date from raw article data."""
        # Default implementation - sources can override
        published = raw_article.get('published')
        if isinstance(published, datetime):
            return published
        return None
    
    def _extract_summary(self, raw_article: Dict[str, Any]) -> str:
        """Extract summary from raw article data."""
        return raw_article.get('summary', '').strip()
    
    def _extract_content(self, raw_article: Dict[str, Any]) -> str:
        """Extract full content from raw article data."""
        return raw_article.get('content', '').strip()
    
    def _extract_author(self, raw_article: Dict[str, Any]) -> Optional[str]:
        """Extract author from raw article data."""
        author = raw_article.get('author', '').strip()
        return author if author else None
    
    def _extract_categories(self, raw_article: Dict[str, Any]) -> List[str]:
        """Extract categories from raw article data."""
        categories = raw_article.get('categories', [])
        if isinstance(categories, str):
            return [categories]
        return list(categories) if categories else []


class RSSSource(NewsSource):
    """
    Base class for RSS-based news sources.
    
    Provides common RSS functionality while allowing source-specific customization.
    """
    
    def __init__(self, feed_url: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize RSS source.
        
        Args:
            feed_url: RSS feed URL
            config: Source-specific configuration
        """
        super().__init__(config)
        self.feed_url = feed_url
        self.timeout = config.get('timeout', 10) if config else 10
    
    @abstractmethod
    def get_feed_urls(self) -> List[str]:
        """
        Get list of RSS feed URLs for this source.
        
        Returns:
            List of feed URLs
        """
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """Check RSS feed availability."""
        try:
            import requests
            response = requests.head(self.feed_url, timeout=self.timeout)
            return {
                'available': response.status_code == 200,
                'status_code': response.status_code,
                'response_time_ms': response.elapsed.total_seconds() * 1000
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }