#!/usr/bin/env python3
"""
Enhanced cache manager with multiple strategies and warming.

Provides centralized cache management with different eviction policies
and cache warming capabilities.
"""

import logging
from typing import Any, Dict, Optional, Callable, List
from enum import Enum
from datetime import datetime, timedelta

from ..cache import InMemoryCache  # Use existing cache implementation

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache strategy types."""
    MEMORY_ONLY = "memory_only"
    PERSISTENT = "persistent"  # Future: Redis, file-based, etc.
    HYBRID = "hybrid"         # Future: Memory + persistent fallback


class CacheManager:
    """
    Centralized cache manager with multiple cache instances and strategies.
    
    Manages different cache regions for different types of data
    (RSS feeds, analysis results, etc.)
    """
    
    def __init__(self, default_ttl: int = 3600):
        """
        Initialize cache manager.
        
        Args:
            default_ttl: Default TTL in seconds
        """
        self.default_ttl = default_ttl
        self.caches: Dict[str, InMemoryCache] = {}
        self.cache_configs: Dict[str, Dict[str, Any]] = {}
        
        # Initialize default cache regions
        self._setup_default_caches()
    
    def _setup_default_caches(self):
        """Setup default cache regions."""
        # RSS feed cache - short TTL, frequent updates
        self.register_cache('rss_feeds', {
            'max_size': 100,
            'default_ttl': 600,  # 10 minutes
            'cleanup_interval': 300  # 5 minutes
        })
        
        # Analysis results cache - longer TTL, expensive to compute
        self.register_cache('analysis_results', {
            'max_size': 50,
            'default_ttl': 3600,  # 1 hour
            'cleanup_interval': 1800  # 30 minutes
        })
        
        # Source metadata cache - very long TTL, rarely changes
        self.register_cache('source_metadata', {
            'max_size': 20,
            'default_ttl': 86400,  # 24 hours
            'cleanup_interval': 3600  # 1 hour
        })
        
        # Database query cache - medium TTL for expensive queries
        self.register_cache('database_queries', {
            'max_size': 200,
            'default_ttl': 1800,  # 30 minutes
            'cleanup_interval': 900  # 15 minutes
        })
    
    def register_cache(self, region: str, config: Dict[str, Any]):
        """
        Register a new cache region.
        
        Args:
            region: Cache region name
            config: Cache configuration
        """
        self.cache_configs[region] = config
        self.caches[region] = InMemoryCache(
            max_entries=config.get('max_size', 100),
            cleanup_interval=config.get('cleanup_interval', 300),
            default_ttl=config.get('default_ttl', self.default_ttl)
        )
        
        logger.info(f"Registered cache region: {region}")
    
    def get_cache(self, region: str = 'default') -> InMemoryCache:
        """
        Get cache instance for a region.
        
        Args:
            region: Cache region name
            
        Returns:
            Cache instance
        """
        if region not in self.caches:
            # Create default cache for unknown regions
            self.register_cache(region, {
                'max_size': 100,
                'default_ttl': self.default_ttl,
                'cleanup_interval': 300
            })
        
        return self.caches[region]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, region: str = 'default'):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses region default if None)
            region: Cache region
        """
        cache = self.get_cache(region)
        
        if ttl is None:
            ttl = self.cache_configs.get(region, {}).get('default_ttl', self.default_ttl)
        
        cache.set(key, value, ttl)
    
    def get(self, key: str, region: str = 'default') -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            region: Cache region
            
        Returns:
            Cached value or None if not found/expired
        """
        cache = self.get_cache(region)
        return cache.get(key)
    
    def get_or_set(
        self, 
        key: str, 
        factory: Callable[[], Any], 
        ttl: Optional[int] = None, 
        region: str = 'default'
    ) -> Any:
        """
        Get value from cache or compute and cache it.
        
        Args:
            key: Cache key
            factory: Function to compute value if not in cache
            ttl: TTL in seconds
            region: Cache region
            
        Returns:
            Cached or computed value
        """
        value = self.get(key, region)
        
        if value is None:
            value = factory()
            self.set(key, value, ttl, region)
        
        return value
    
    def invalidate(self, key: str, region: str = 'default'):
        """
        Invalidate cache entry.
        
        Args:
            key: Cache key to invalidate
            region: Cache region
        """
        cache = self.get_cache(region)
        cache.delete(key)
    
    def invalidate_pattern(self, pattern: str, region: str = 'default'):
        """
        Invalidate cache entries matching pattern.
        
        Args:
            pattern: Pattern to match (simple wildcard support)
            region: Cache region
        """
        cache = self.get_cache(region)
        
        # Simple pattern matching for now
        if '*' in pattern:
            prefix = pattern.replace('*', '')
            keys_to_delete = []
            
            for key in cache._cache.keys():
                if key.startswith(prefix):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                cache.delete(key)
        else:
            cache.delete(pattern)
    
    def clear_region(self, region: str):
        """
        Clear all entries in a cache region.
        
        Args:
            region: Cache region to clear
        """
        if region in self.caches:
            self.caches[region].clear()
    
    def clear_all(self):
        """Clear all cache regions."""
        for cache in self.caches.values():
            cache.clear()
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all cache regions.
        
        Returns:
            Dictionary with stats for each region
        """
        stats = {}
        
        for region, cache in self.caches.items():
            cache_stats = cache.get_stats()
            config = self.cache_configs.get(region, {})
            
            stats[region] = {
                **cache_stats,
                'config': config,
                'hit_rate': (
                    cache_stats['hits'] / max(cache_stats['requests'], 1) 
                    if cache_stats['requests'] > 0 else 0
                ),
                'utilization': (
                    cache_stats['size'] / config.get('max_size', 100)
                    if config.get('max_size') else 0
                )
            }
        
        return stats
    
    def optimize_caches(self):
        """
        Optimize cache configurations based on usage patterns.
        
        Analyzes hit rates and access patterns to suggest optimizations.
        """
        stats = self.get_stats()
        optimizations = []
        
        for region, region_stats in stats.items():
            hit_rate = region_stats['hit_rate']
            utilization = region_stats['utilization']
            
            # Suggest optimizations based on patterns
            if hit_rate < 0.3 and utilization > 0.8:
                optimizations.append({
                    'region': region,
                    'issue': 'Low hit rate with high utilization',
                    'suggestion': 'Consider increasing TTL or cache size'
                })
            
            elif hit_rate > 0.8 and utilization < 0.3:
                optimizations.append({
                    'region': region,
                    'issue': 'High hit rate with low utilization',
                    'suggestion': 'Consider decreasing cache size'
                })
            
            elif hit_rate < 0.1:
                optimizations.append({
                    'region': region,
                    'issue': 'Very low hit rate',
                    'suggestion': 'Consider disabling cache or adjusting TTL'
                })
        
        if optimizations:
            logger.info(f"Cache optimization suggestions: {len(optimizations)} found")
            for opt in optimizations:
                logger.info(f"Region {opt['region']}: {opt['suggestion']}")
        
        return optimizations


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def reset_cache_manager():
    """Reset global cache manager (for testing)."""
    global _cache_manager
    _cache_manager = None