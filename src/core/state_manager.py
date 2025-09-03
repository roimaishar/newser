#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State Management for News Aggregation with Database Storage.

Handles persistent storage of known news events and analysis state using
PostgreSQL database instead of JSON files. Enables novelty detection
and incremental updates with better performance and reliability.
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.database import get_database, DatabaseAdapter, DatabaseError

logger = logging.getLogger(__name__)


@dataclass
class KnownItem:
    """Represents a known item for novelty detection (simplified for database storage)."""
    item_hash: str
    item_type: str  # 'article', 'event', etc.
    last_seen: datetime
    created_at: datetime


class StateManager:
    """
    Manages persistent application state with database storage.
    
    Features:
    - Database-backed storage for reliability
    - Automatic cleanup of old items
    - Hash-based novelty detection
    - Thread-safe operations via database
    """
    
    def __init__(self, db: Optional[DatabaseAdapter] = None, 
                 cleanup_threshold_days: int = 60):
        """
        Initialize state manager with database adapter.
        
        Args:
            db: Database adapter (uses global if None)
            cleanup_threshold_days: Remove items older than this many days
        """
        self.db = db or get_database()
        self.cleanup_threshold_days = cleanup_threshold_days
        logger.info("StateManager initialized with database storage")
    
    
    def get_known_items(self, item_type: str = 'article') -> List[str]:
        """Get list of known item hashes for novelty detection."""
        try:
            return self.db.get_known_items(item_type)
        except DatabaseError as e:
            logger.error(f"Failed to get known items: {e}")
            return []
    
    def update_known_items(self, item_hashes: List[str], item_type: str = 'article') -> None:
        """Update known items with current timestamp."""
        try:
            self.db.update_known_items(item_hashes, item_type)
            logger.debug(f"Updated {len(item_hashes)} known items of type {item_type}")
        except DatabaseError as e:
            logger.error(f"Failed to update known items: {e}")
    
    def add_item_hash(self, item_hash: str, item_type: str = 'article') -> None:
        """Add single item hash to known items."""
        self.update_known_items([item_hash], item_type)
    
    def cleanup_old_items(self, threshold_days: Optional[int] = None) -> int:
        """Remove items older than threshold via database cleanup."""
        try:
            # Database cleanup function handles this automatically
            deleted_count = self.db.cleanup_old_records()
            logger.info(f"Cleaned up old items via database function")
            return deleted_count
        except DatabaseError as e:
            logger.error(f"Failed to cleanup old items: {e}")
            return 0
    
    def reset_state(self) -> None:
        """Reset known items (removes all from database)."""
        try:
            # This would require a specific database operation
            # For now, just log the intention
            logger.warning("Reset state called - this would clear all known items from database")
            logger.warning("Manual database truncation required for known_items table")
        except Exception as e:
            logger.error(f"Failed to reset state: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get state statistics for monitoring."""
        try:
            known_items = self.get_known_items()
            health = self.db.health_check()
            
            return {
                "total_known_items": len(known_items),
                "cleanup_threshold_days": self.cleanup_threshold_days,
                "database_status": health.get('status', 'unknown'),
                "database_connected": health.get('connected', False),
                "last_checked": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "total_known_items": 0,
                "cleanup_threshold_days": self.cleanup_threshold_days,
                "database_status": "error",
                "error": str(e)
            }
    
    @staticmethod
    def generate_content_hash(title: str, link: str = "", source: str = "") -> str:
        """
        Generate stable content hash from article metadata.
        
        Args:
            title: Article title
            link: Article URL
            source: News source name
            
        Returns:
            SHA-256 hash string
        """
        # Create composite string for hashing
        composite = f"{title}|{link}|{source}"
        
        # Generate SHA-256 hash
        hash_obj = hashlib.sha256(composite.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def is_item_known(self, item_hash: str, item_type: str = 'article') -> bool:
        """Check if an item is already known."""
        known_hashes = self.get_known_items(item_type)
        return item_hash in known_hashes
    
    def get_last_notification_timestamp(self) -> Optional[datetime]:
        """Get the timestamp of the last notification sent."""
        try:
            # Use known_items mechanism with special type for notification state
            notification_hashes = self.db.get_known_items('notification_timestamp')
            if not notification_hashes:
                return None
            
            # The "hash" is actually a timestamp string for this special type
            # Get the most recent one
            timestamps = []
            for hash_str in notification_hashes:
                try:
                    timestamp = datetime.fromisoformat(hash_str.replace('Z', '+00:00'))
                    timestamps.append(timestamp)
                except Exception:
                    continue
            
            return max(timestamps) if timestamps else None
            
        except Exception as e:
            logger.error(f"Failed to get last notification timestamp: {e}")
            return None
    
    def update_last_notification_timestamp(self, timestamp: Optional[datetime] = None) -> None:
        """Update the last notification timestamp."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        try:
            # Store as ISO string in the known_items system
            timestamp_str = timestamp.isoformat()
            self.db.update_known_items([timestamp_str], 'notification_timestamp')
            logger.info(f"Updated last notification timestamp to {timestamp_str}")
            
        except Exception as e:
            logger.error(f"Failed to update notification timestamp: {e}")
    
    def get_known_events(self) -> List[Any]:
        """
        Get known events for novelty analysis.
        
        Returns empty list for now - this can be enhanced later to store
        event-specific data if needed for advanced novelty detection.
        """
        # For now, return empty list since we don't store complex event structures
        # The novelty analysis will work without prior events (treats everything as new)
        return []
    
    def get_articles_since_timestamp(self, since_timestamp: datetime, hours_limit: int = 24) -> List[Dict[str, Any]]:
        """Get articles from database since a specific timestamp, within hours limit."""
        try:
            # Get recent articles from database
            all_recent = self.db.get_recent_articles(hours_limit)
            
            # Filter to only those after the timestamp
            filtered = []
            for article in all_recent:
                # Convert article timestamp for comparison
                article_time = None
                if hasattr(article, 'created_at'):
                    article_time = article.created_at
                elif isinstance(article, dict) and 'created_at' in article:
                    article_time = article['created_at']
                elif hasattr(article, 'published_date'):
                    article_time = article.published_date
                elif isinstance(article, dict) and 'published_date' in article:
                    article_time = article['published_date']
                
                if article_time and article_time > since_timestamp:
                    # Convert to dict if needed
                    if hasattr(article, 'to_dict'):
                        filtered.append(article.to_dict())
                    elif isinstance(article, dict):
                        filtered.append(article)
            
            return filtered
            
        except Exception as e:
            logger.error(f"Failed to get articles since timestamp: {e}")
            return []