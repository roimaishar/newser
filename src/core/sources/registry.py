#!/usr/bin/env python3
"""
News source registry for dynamic source management.

Provides centralized registration and discovery of news sources.
"""

import logging
from typing import Dict, List, Type, Optional
from .base import NewsSource, SourceMetadata

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Registry for news sources with automatic discovery."""
    
    def __init__(self):
        """Initialize empty registry."""
        self._sources: Dict[str, Type[NewsSource]] = {}
        self._instances: Dict[str, NewsSource] = {}
        
    def register_source(self, source_class: Type[NewsSource], name: Optional[str] = None):
        """
        Register a news source class.
        
        Args:
            source_class: NewsSource subclass to register
            name: Optional custom name (uses class name if not provided)
        """
        if name is None:
            name = source_class.__name__.lower().replace('source', '')
        
        self._sources[name] = source_class
        logger.info(f"Registered news source: {name}")
    
    def get_source(self, name: str, config: Optional[dict] = None) -> NewsSource:
        """
        Get a news source instance.
        
        Args:
            name: Source name
            config: Configuration for the source
            
        Returns:
            NewsSource instance
            
        Raises:
            KeyError: If source not found
        """
        if name not in self._sources:
            available = list(self._sources.keys())
            raise KeyError(f"Source '{name}' not found. Available: {available}")
        
        # Create new instance each time to avoid shared state issues
        source_class = self._sources[name]
        return source_class(config)
    
    def get_all_sources(self, config: Optional[dict] = None) -> Dict[str, NewsSource]:
        """
        Get all registered source instances.
        
        Args:
            config: Default configuration for sources
            
        Returns:
            Dictionary mapping source names to instances
        """
        sources = {}
        for name in self._sources:
            try:
                sources[name] = self.get_source(name, config)
            except Exception as e:
                logger.error(f"Failed to initialize source {name}: {e}")
        
        return sources
    
    def list_available_sources(self) -> List[str]:
        """Get list of available source names."""
        return list(self._sources.keys())
    
    def get_sources_by_language(self, language: str) -> List[str]:
        """
        Get sources that support a specific language.
        
        Args:
            language: Language code (e.g., 'he', 'en')
            
        Returns:
            List of source names
        """
        matching_sources = []
        
        for name, source_class in self._sources.items():
            try:
                # Create temporary instance to get metadata
                instance = source_class()
                metadata = instance.get_metadata()
                if metadata.language == language:
                    matching_sources.append(name)
            except Exception as e:
                logger.warning(f"Failed to check language for source {name}: {e}")
        
        return matching_sources
    
    def get_sources_by_country(self, country: str) -> List[str]:
        """
        Get sources from a specific country.
        
        Args:
            country: Country code (e.g., 'IL', 'US')
            
        Returns:
            List of source names
        """
        matching_sources = []
        
        for name, source_class in self._sources.items():
            try:
                # Create temporary instance to get metadata
                instance = source_class()
                metadata = instance.get_metadata()
                if metadata.country == country:
                    matching_sources.append(name)
            except Exception as e:
                logger.warning(f"Failed to check country for source {name}: {e}")
        
        return matching_sources


# Global registry instance
_global_registry = SourceRegistry()


def register_source(source_class: Type[NewsSource], name: Optional[str] = None):
    """Register a source in the global registry."""
    _global_registry.register_source(source_class, name)


def get_source(name: str, config: Optional[dict] = None) -> NewsSource:
    """Get a source from the global registry."""
    return _global_registry.get_source(name, config)


def get_all_sources(config: Optional[dict] = None) -> Dict[str, NewsSource]:
    """Get all sources from the global registry."""
    return _global_registry.get_all_sources(config)


def list_available_sources() -> List[str]:
    """List available sources in the global registry."""
    return _global_registry.list_available_sources()


def get_sources_by_language(language: str) -> List[str]:
    """Get sources by language from the global registry."""
    return _global_registry.get_sources_by_language(language)


def get_sources_by_country(country: str) -> List[str]:
    """Get sources by country from the global registry."""
    return _global_registry.get_sources_by_country(country)