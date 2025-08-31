#!/usr/bin/env python3
"""
In-Memory Caching System

Provides lightweight in-memory caching with TTL (Time-To-Live) support.
Designed for GitHub Actions free tier compatibility (no external dependencies).
"""

import logging
import threading
import time
from typing import Any, Dict, Optional, Set, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    ttl_seconds: int
    access_count: int = 0
    last_accessed: float = 0.0
    
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() > (self.created_at + self.ttl_seconds)
    
    def access(self) -> Any:
        """Mark entry as accessed and return value."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value
    
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.created_at


class InMemoryCache:
    """
    Thread-safe in-memory cache with TTL support.
    
    Features:
    - TTL (Time-To-Live) expiration
    - Thread-safe operations
    - Automatic cleanup of expired entries
    - Memory usage tracking
    - LRU eviction when size limits are reached
    """
    
    def __init__(self, 
                 default_ttl: int = 900,  # 15 minutes
                 max_entries: int = 1000,
                 cleanup_interval: int = 300):  # 5 minutes
        """
        Initialize in-memory cache.
        
        Args:
            default_ttl: Default TTL in seconds
            max_entries: Maximum number of entries before LRU eviction
            cleanup_interval: Interval between cleanup runs in seconds
        """
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self.cleanup_interval = cleanup_interval
        
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0,
            'cleanups': 0
        }
        
        logger.debug(f"Initialized cache with TTL={default_ttl}s, max_entries={max_entries}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found or expired
            
        Returns:
            Cached value or default
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats['misses'] += 1
                return default
            
            if entry.is_expired():
                del self._cache[key]
                self._stats['misses'] += 1
                logger.debug(f"Cache key expired: {key}")
                return default
            
            self._stats['hits'] += 1
            return entry.access()
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl
        
        with self._lock:
            # Create new entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl
            )
            
            self._cache[key] = entry
            self._stats['sets'] += 1
            
            # Check if we need to evict entries
            if len(self._cache) > self.max_entries:
                self._evict_lru()
            
            # Periodic cleanup
            self._maybe_cleanup()
            
            logger.debug(f"Cached key: {key} (TTL: {ttl}s)")
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Deleted cache key: {key}")
                return True
            return False
    
    def has(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        with self._lock:
            entry = self._cache.get(key)
            return entry is not None and not entry.is_expired()
    
    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.debug(f"Cleared {count} cache entries")
    
    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        Get value from cache or set it using factory function.
        
        Args:
            key: Cache key
            factory: Function to call if key not found
            ttl: TTL in seconds (uses default if None)
            
        Returns:
            Cached or newly created value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        # Generate new value and cache it
        new_value = factory()
        self.set(key, new_value, ttl)
        return new_value
    
    def _evict_lru(self) -> None:
        """Evict least recently used entries."""
        if len(self._cache) <= self.max_entries:
            return
        
        # Sort by last_accessed (oldest first)
        entries_by_access = sorted(
            self._cache.values(),
            key=lambda e: e.last_accessed or e.created_at
        )
        
        # Remove oldest entries
        evict_count = len(self._cache) - self.max_entries + 10  # Remove a few extra
        for entry in entries_by_access[:evict_count]:
            if entry.key in self._cache:
                del self._cache[entry.key]
                self._stats['evictions'] += 1
        
        logger.debug(f"Evicted {evict_count} LRU entries")
    
    def _maybe_cleanup(self) -> None:
        """Run cleanup if interval has passed."""
        current_time = time.time()
        if current_time - self._last_cleanup >= self.cleanup_interval:
            self.cleanup()
    
    def cleanup(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            self._last_cleanup = current_time
            self._stats['cleanups'] += 1
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'entries': len(self._cache),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': hit_rate,
                'sets': self._stats['sets'],
                'evictions': self._stats['evictions'],
                'cleanups': self._stats['cleanups'],
                'max_entries': self.max_entries,
                'default_ttl': self.default_ttl
            }
    
    def get_keys(self) -> Set[str]:
        """Get all cache keys."""
        with self._lock:
            return set(self._cache.keys())
    
    def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a cache entry."""
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            
            return {
                'key': entry.key,
                'age_seconds': entry.age_seconds(),
                'ttl_seconds': entry.ttl_seconds,
                'is_expired': entry.is_expired(),
                'access_count': entry.access_count,
                'last_accessed': entry.last_accessed,
                'created_at': entry.created_at
            }


# Global cache instances for different use cases
_rss_cache: Optional[InMemoryCache] = None
_analysis_cache: Optional[InMemoryCache] = None
_general_cache: Optional[InMemoryCache] = None


def get_rss_cache() -> InMemoryCache:
    """Get RSS feed cache instance."""
    global _rss_cache
    if _rss_cache is None:
        _rss_cache = InMemoryCache(
            default_ttl=900,  # 15 minutes
            max_entries=100,  # RSS feeds are relatively few
            cleanup_interval=300
        )
    return _rss_cache


def get_analysis_cache() -> InMemoryCache:
    """Get analysis results cache instance.""" 
    global _analysis_cache
    if _analysis_cache is None:
        _analysis_cache = InMemoryCache(
            default_ttl=3600,  # 1 hour
            max_entries=500,
            cleanup_interval=600
        )
    return _analysis_cache


def get_general_cache() -> InMemoryCache:
    """Get general purpose cache instance."""
    global _general_cache
    if _general_cache is None:
        _general_cache = InMemoryCache(
            default_ttl=1800,  # 30 minutes
            max_entries=1000,
            cleanup_interval=300
        )
    return _general_cache


def clear_all_caches() -> None:
    """Clear all cache instances."""
    for cache in [_rss_cache, _analysis_cache, _general_cache]:
        if cache:
            cache.clear()
    logger.info("Cleared all cache instances")


def get_cache_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics from all cache instances."""
    stats = {}
    
    if _rss_cache:
        stats['rss'] = _rss_cache.get_stats()
    
    if _analysis_cache:
        stats['analysis'] = _analysis_cache.get_stats()
    
    if _general_cache:
        stats['general'] = _general_cache.get_stats()
    
    return stats