#!/usr/bin/env python3
"""
Database Data Manager for News Aggregation.

Manages data persistence using PostgreSQL database instead of JSON files.
Provides unified interface for storing articles, analyses, and metrics.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from core.database import DatabaseAdapter, get_database, DatabaseError

logger = logging.getLogger(__name__)


@dataclass
class RunRecord:
    """Represents a single execution run."""
    run_id: str
    timestamp: datetime
    hours_window: int
    command_used: str
    articles_scraped: int
    after_dedup: int
    success: bool
    processing_time: float = 0.0
    error_message: Optional[str] = None


@dataclass
class AnalysisRecord:
    """Represents an analysis result."""
    run_id: str
    timestamp: datetime
    analysis_type: str  # 'thematic' or 'updates'
    hebrew_result: Any  # Hebrew analysis result object
    articles_analyzed: int
    confidence: float
    processing_time: float


class DataManager:
    """Manages data persistence using PostgreSQL database."""
    
    def __init__(self, db: Optional[DatabaseAdapter] = None):
        """Initialize DataManager with database adapter."""
        self.db = db or get_database()
        logger.info("DataManager initialized with database adapter")
    
    def generate_run_id(self) -> str:
        """Generate unique run ID."""
        return str(uuid.uuid4())[:8]
    
    def store_run_record(self, run_record: RunRecord) -> None:
        """Store a run record in database."""
        try:
            metrics = {
                'articles_scraped': run_record.articles_scraped,
                'articles_after_dedup': run_record.after_dedup,
                'processing_time': run_record.processing_time,
                'success': run_record.success,
                'error_message': run_record.error_message
            }
            
            self.db.store_run_metrics(
                run_record.run_id,
                run_record.command_used,
                metrics
            )
            
            logger.info(f"Stored run record {run_record.run_id}")
            
        except DatabaseError as e:
            logger.error(f"Failed to store run record: {e}")
            raise
    
    def store_analysis_record(self, analysis_record: AnalysisRecord) -> None:
        """Store an analysis record in database."""
        try:
            analysis_id = self.db.store_analysis(
                analysis_record.run_id,
                analysis_record.hebrew_result
            )
            
            logger.info(f"Stored analysis record {analysis_id} for run {analysis_record.run_id}")
            
        except DatabaseError as e:
            logger.error(f"Failed to store analysis record: {e}")
            raise
            
    
    def get_recent_runs(self, days: int = 3) -> List[Dict[str, Any]]:
        """Get recent run metrics from the last N days."""
        try:
            # This would need a proper database query implementation
            # For now, return empty list - can be enhanced later
            logger.info(f"Getting recent runs for {days} days")
            return []
            
        except DatabaseError as e:
            logger.error(f"Failed to get recent runs: {e}")
            return []
    
    def cleanup_old_records(self) -> int:
        """Clean up old database records."""
        try:
            deleted_count = self.db.cleanup_old_records()
            logger.info(f"Cleaned up {deleted_count} old records")
            return deleted_count
            
        except DatabaseError as e:
            logger.error(f"Failed to cleanup old records: {e}")
            return 0
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get database health status."""
        try:
            return self.db.health_check()
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e)
            }
    
    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()