#!/usr/bin/env python3
"""
News sources architecture for pluggable content aggregation.

Supports multiple source types: RSS feeds, APIs, social media, etc.
"""

from .registry import SourceRegistry, register_source, get_all_sources, get_source, list_available_sources
from .base import NewsSource, SourceError

# Import to trigger auto-registration
from . import auto_register

__all__ = [
    'SourceRegistry', 'register_source', 'get_all_sources', 'get_source', 
    'list_available_sources', 'NewsSource', 'SourceError'
]