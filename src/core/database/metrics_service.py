#!/usr/bin/env python3
"""
Metrics Database Service

Handles all database operations related to run metrics and performance tracking.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for metrics-related database operations."""
    
    def __init__(self, connection_manager):
        """
        Initialize metrics service.
        
        Args:
            connection_manager: Database connection manager instance
        """
        self.connection_manager = connection_manager
    
    def store_run_metrics(self, run_id: str, command: str, metrics: Dict[str, Any]) -> int:
        """
        Store run metrics in database.
        
        Args:
            run_id: Unique run identifier
            command: Command that was executed
            metrics: Dictionary of metrics
            
        Returns:
            Metrics record ID
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO run_metrics (
                        run_id, command_used, articles_scraped, articles_after_dedup,
                        processing_time_seconds, success, error_message, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    run_id,
                    command,
                    metrics.get('articles_scraped', 0),
                    metrics.get('articles_after_dedup', 0),
                    metrics.get('processing_time', 0),
                    metrics.get('success', True),
                    metrics.get('error_message'),
                    datetime.now(timezone.utc)
                ))
                
                result = cursor.fetchone()
                metrics_id = result['id']
                logger.debug(f"Stored run metrics with ID {metrics_id}")
                return metrics_id
                
        except Exception as e:
            logger.error(f"Failed to store run metrics: {e}")
            raise
    
    def get_recent_runs(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent run metrics.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of run metrics dictionaries
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        id, run_id, command_used, articles_scraped, articles_after_dedup,
                        processing_time_seconds, success, error_message, timestamp
                    FROM run_metrics
                    WHERE timestamp >= %s
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (datetime.now(timezone.utc) - timedelta(days=days),))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get recent runs: {e}")
            raise
    
    def get_run_metrics_by_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get run metrics by run ID.
        
        Args:
            run_id: Run identifier
            
        Returns:
            Run metrics dictionary or None if not found
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        id, run_id, command_used, articles_scraped, articles_after_dedup,
                        processing_time_seconds, success, error_message, timestamp
                    FROM run_metrics
                    WHERE run_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (run_id,))
                
                result = cursor.fetchone()
                return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"Failed to get run metrics by ID: {e}")
            raise
    
    def get_performance_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get performance statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with performance statistics
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                # Get basic performance stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_runs,
                        COUNT(CASE WHEN success THEN 1 END) as successful_runs,
                        COUNT(CASE WHEN NOT success THEN 1 END) as failed_runs,
                        AVG(processing_time_seconds) as avg_processing_time,
                        MAX(processing_time_seconds) as max_processing_time,
                        MIN(processing_time_seconds) as min_processing_time,
                        AVG(articles_scraped) as avg_articles_scraped,
                        AVG(articles_after_dedup) as avg_articles_after_dedup,
                        MIN(timestamp) as period_start,
                        MAX(timestamp) as period_end
                    FROM run_metrics
                    WHERE timestamp >= %s
                """, (datetime.now(timezone.utc) - timedelta(days=days),))
                
                stats = dict(cursor.fetchone())
                
                # Calculate success rate
                if stats['total_runs'] > 0:
                    stats['success_rate'] = stats['successful_runs'] / stats['total_runs']
                else:
                    stats['success_rate'] = 0.0
                
                # Get command breakdown
                cursor.execute("""
                    SELECT command_used, COUNT(*) as count, AVG(processing_time_seconds) as avg_time
                    FROM run_metrics
                    WHERE timestamp >= %s
                    GROUP BY command_used
                    ORDER BY count DESC
                """, (datetime.now(timezone.utc) - timedelta(days=days),))
                
                stats['commands'] = {
                    row['command_used']: {
                        'count': row['count'],
                        'avg_time': float(row['avg_time']) if row['avg_time'] else 0.0
                    }
                    for row in cursor.fetchall()
                }
                
                # Get hourly distribution
                cursor.execute("""
                    SELECT 
                        EXTRACT(hour FROM timestamp) as hour,
                        COUNT(*) as count
                    FROM run_metrics
                    WHERE timestamp >= %s
                    GROUP BY EXTRACT(hour FROM timestamp)
                    ORDER BY hour
                """, (datetime.now(timezone.utc) - timedelta(days=days),))
                
                stats['hourly_distribution'] = {
                    int(row['hour']): row['count']
                    for row in cursor.fetchall()
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            raise
    
    def get_error_summary(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get summary of errors from recent runs.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of error summaries
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        error_message,
                        command_used,
                        COUNT(*) as occurrence_count,
                        MAX(timestamp) as last_occurrence
                    FROM run_metrics
                    WHERE timestamp >= %s
                    AND NOT success
                    AND error_message IS NOT NULL
                    GROUP BY error_message, command_used
                    ORDER BY occurrence_count DESC, last_occurrence DESC
                """, (datetime.now(timezone.utc) - timedelta(days=days),))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get error summary: {e}")
            raise
    
    def cleanup_old_metrics(self, days: int = 90) -> int:
        """
        Remove metrics older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of metrics records deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    DELETE FROM run_metrics
                    WHERE timestamp < %s
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} metrics records older than {days} days")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")
            raise