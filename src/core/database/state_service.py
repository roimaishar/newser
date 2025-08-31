#!/usr/bin/env python3
"""
State Database Service

Handles all database operations related to known items and state management.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class StateService:
    """Service for state management database operations."""
    
    def __init__(self, connection_manager):
        """
        Initialize state service.
        
        Args:
            connection_manager: Database connection manager instance
        """
        self.connection_manager = connection_manager
    
    def get_known_items(self, item_type: str = 'article') -> List[str]:
        """
        Get list of known item hashes for novelty detection.
        
        Args:
            item_type: Type of items to retrieve
            
        Returns:
            List of item hashes
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT item_hash FROM known_items
                    WHERE item_type = %s
                    AND last_seen >= %s
                    ORDER BY last_seen DESC
                """, (
                    item_type,
                    datetime.now(timezone.utc) - timedelta(days=30)
                ))
                
                return [row['item_hash'] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get known items: {e}")
            raise
    
    def update_known_items(self, item_hashes: List[str], item_type: str = 'article') -> None:
        """
        Update known items with current timestamp.
        
        Args:
            item_hashes: List of item hashes to update/insert
            item_type: Type of items
        """
        if not item_hashes:
            return
        
        try:
            current_time = datetime.now(timezone.utc)
            
            with self.connection_manager.get_cursor() as cursor:
                for item_hash in item_hashes:
                    cursor.execute("""
                        INSERT INTO known_items (item_hash, item_type, last_seen, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (item_hash, item_type) 
                        DO UPDATE SET last_seen = EXCLUDED.last_seen
                    """, (item_hash, item_type, current_time, current_time))
                    
            logger.debug(f"Updated {len(item_hashes)} known items of type '{item_type}'")
            
        except Exception as e:
            logger.error(f"Failed to update known items: {e}")
            raise
    
    def add_known_item(self, item_hash: str, item_type: str = 'article') -> bool:
        """
        Add a single known item.
        
        Args:
            item_hash: Item hash
            item_type: Type of item
            
        Returns:
            True if added, False if already exists
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO known_items (item_hash, item_type, last_seen, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (item_hash, item_type) 
                    DO UPDATE SET last_seen = EXCLUDED.last_seen
                    RETURNING (xmax = 0) AS inserted
                """, (item_hash, item_type, current_time, current_time))
                
                result = cursor.fetchone()
                return result['inserted'] if result else False
                
        except Exception as e:
            logger.error(f"Failed to add known item: {e}")
            raise
    
    def is_known_item(self, item_hash: str, item_type: str = 'article') -> bool:
        """
        Check if an item is already known.
        
        Args:
            item_hash: Item hash to check
            item_type: Type of item
            
        Returns:
            True if item is known, False otherwise
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM known_items
                    WHERE item_hash = %s AND item_type = %s
                    AND last_seen >= %s
                    LIMIT 1
                """, (
                    item_hash, 
                    item_type,
                    datetime.now(timezone.utc) - timedelta(days=30)
                ))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Failed to check known item: {e}")
            raise
    
    def cleanup_old_known_items(self, days: int = 30) -> int:
        """
        Remove known items older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of items deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    DELETE FROM known_items
                    WHERE last_seen < %s
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} known items older than {days} days")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old known items: {e}")
            raise
    
    def get_state_stats(self) -> Dict[str, Any]:
        """
        Get state management statistics.
        
        Returns:
            Dictionary with state statistics
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                # Get overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_known_items,
                        COUNT(DISTINCT item_type) as item_types_count,
                        MIN(created_at) as oldest_item,
                        MAX(last_seen) as newest_update
                    FROM known_items
                """)
                
                stats = dict(cursor.fetchone())
                
                # Get breakdown by item type
                cursor.execute("""
                    SELECT item_type, COUNT(*) as count
                    FROM known_items
                    GROUP BY item_type
                    ORDER BY count DESC
                """)
                
                stats['item_types'] = {row['item_type']: row['count'] for row in cursor.fetchall()}
                
                # Get recent activity
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN last_seen >= NOW() - INTERVAL '24 hours' THEN 1 END) as active_24h,
                        COUNT(CASE WHEN last_seen >= NOW() - INTERVAL '7 days' THEN 1 END) as active_7d
                    FROM known_items
                """)
                
                activity_stats = dict(cursor.fetchone())
                stats.update(activity_stats)
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get state stats: {e}")
            raise
    
    def reset_known_items(self, item_type: str = None) -> int:
        """
        Reset known items (clear all or specific type).
        
        Args:
            item_type: Optional item type to reset. If None, resets all types.
            
        Returns:
            Number of items deleted
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                if item_type:
                    cursor.execute("DELETE FROM known_items WHERE item_type = %s", (item_type,))
                    logger.info(f"Reset known items for type '{item_type}'")
                else:
                    cursor.execute("DELETE FROM known_items")
                    logger.info("Reset all known items")
                
                deleted_count = cursor.rowcount
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to reset known items: {e}")
            raise