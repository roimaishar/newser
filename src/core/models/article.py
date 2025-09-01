#!/usr/bin/env python3
"""
Article data model.

Represents a news article with metadata and analysis fields.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass


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
        # Handle published date parsing
        published = data.get('published')
        if isinstance(published, str):
            try:
                from dateutil import parser as date_parser
                published = date_parser.parse(published)
            except Exception:
                published = None
        
        return cls(
            title=data.get('title', ''),
            link=data.get('link', ''),
            source=data.get('source', ''),
            published=published,
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