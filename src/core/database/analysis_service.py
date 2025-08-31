#!/usr/bin/env python3
"""
Analysis Database Service

Handles all database operations related to Hebrew analysis results.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for analysis-related database operations."""
    
    def __init__(self, connection_manager):
        """
        Initialize analysis service.
        
        Args:
            connection_manager: Database connection manager instance
        """
        self.connection_manager = connection_manager
    
    def store_analysis(self, run_id: str, analysis_result) -> int:
        """
        Store analysis result in database.
        
        Args:
            run_id: Unique run identifier
            analysis_result: Hebrew analysis result object
            
        Returns:
            Analysis ID
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO analyses (
                        run_id, analysis_type, summary, key_topics, bulletins,
                        confidence, articles_analyzed, has_new_content, 
                        analysis_timestamp, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    run_id,
                    analysis_result.analysis_type,
                    analysis_result.summary,
                    analysis_result.key_topics or [],
                    analysis_result.bulletins,
                    analysis_result.confidence,
                    analysis_result.articles_analyzed,
                    analysis_result.has_new_content,
                    analysis_result.analysis_timestamp,
                    datetime.now(timezone.utc)
                ))
                
                result = cursor.fetchone()
                analysis_id = result['id']
                logger.info(f"Stored analysis with ID {analysis_id}")
                return analysis_id
                
        except Exception as e:
            logger.error(f"Failed to store analysis: {e}")
            raise
    
    def get_recent_analyses(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent analysis results.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of analysis dictionaries
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        id, run_id, analysis_type, summary, key_topics,
                        bulletins, confidence, articles_analyzed, has_new_content,
                        analysis_timestamp, created_at
                    FROM analyses
                    WHERE created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT 100
                """, (datetime.now(timezone.utc) - timedelta(days=days),))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get recent analyses: {e}")
            raise
    
    def get_analysis_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get analysis result by run ID.
        
        Args:
            run_id: Run identifier
            
        Returns:
            Analysis dictionary or None if not found
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        id, run_id, analysis_type, summary, key_topics,
                        bulletins, confidence, articles_analyzed, has_new_content,
                        analysis_timestamp, created_at
                    FROM analyses
                    WHERE run_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (run_id,))
                
                result = cursor.fetchone()
                return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"Failed to get analysis by run ID: {e}")
            raise
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """
        Get analysis statistics.
        
        Returns:
            Dictionary with analysis statistics
        """
        try:
            with self.connection_manager.get_cursor() as cursor:
                # Get basic counts
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_analyses,
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as analyses_24h,
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as analyses_7d,
                        AVG(confidence) as avg_confidence,
                        AVG(articles_analyzed) as avg_articles_analyzed,
                        MIN(created_at) as oldest_analysis,
                        MAX(created_at) as newest_analysis
                    FROM analyses
                """)
                
                stats = dict(cursor.fetchone())
                
                # Get analysis type breakdown
                cursor.execute("""
                    SELECT analysis_type, COUNT(*) as count
                    FROM analyses
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY analysis_type
                    ORDER BY count DESC
                """)
                
                stats['analysis_types_7d'] = {row['analysis_type']: row['count'] for row in cursor.fetchall()}
                
                # Get confidence distribution
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN confidence >= 0.8 THEN 1 END) as high_confidence,
                        COUNT(CASE WHEN confidence >= 0.5 AND confidence < 0.8 THEN 1 END) as medium_confidence,
                        COUNT(CASE WHEN confidence < 0.5 THEN 1 END) as low_confidence
                    FROM analyses
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                """)
                
                confidence_stats = dict(cursor.fetchone())
                stats.update(confidence_stats)
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get analysis stats: {e}")
            raise
    
    def cleanup_old_analyses(self, days: int = 30) -> int:
        """
        Remove analyses older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of analyses deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        try:
            with self.connection_manager.get_cursor() as cursor:
                cursor.execute("""
                    DELETE FROM analyses
                    WHERE created_at < %s
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} analyses older than {days} days")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old analyses: {e}")
            raise