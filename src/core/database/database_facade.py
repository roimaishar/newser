#!/usr/bin/env python3
"""
Database Facade

Provides a unified interface that maintains backward compatibility 
with the original DatabaseAdapter while using the new modular services.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .connection_manager import ConnectionManager, DatabaseError
from .article_service import ArticleService  
from .analysis_service import AnalysisService
from .state_service import StateService
from .metrics_service import MetricsService

logger = logging.getLogger(__name__)


class DatabaseFacade:
    """
    Unified database interface using modular services.
    
    Maintains backward compatibility with the original DatabaseAdapter
    while providing a cleaner internal architecture.
    """
    
    def __init__(self, config):
        """
        Initialize database facade with configuration.
        
        Args:
            config: Database configuration object
        """
        self.config = config
        self.connection_manager = ConnectionManager(config.database)
        
        # Initialize services
        self.articles = ArticleService(self.connection_manager)
        self.analyses = AnalysisService(self.connection_manager)
        self.state = StateService(self.connection_manager)
        self.metrics = MetricsService(self.connection_manager)
    
    # Article Operations (backward compatibility)
    
    def store_articles(self, articles: List) -> int:
        """Store articles in database with deduplication."""
        return self.articles.store_articles(articles)
    
    def get_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get articles from the last N hours."""
        return self.articles.get_recent_articles(hours)
    
    # Analysis Operations (backward compatibility)
    
    def store_analysis(self, run_id: str, analysis_result) -> int:
        """Store analysis result in database."""
        return self.analyses.store_analysis(run_id, analysis_result)
    
    # Known Items / State Operations (backward compatibility)
    
    def get_known_items(self, item_type: str = 'article') -> List[str]:
        """Get list of known item hashes for novelty detection."""
        return self.state.get_known_items(item_type)
    
    def update_known_items(self, item_hashes: List[str], item_type: str = 'article'):
        """Update known items with current timestamp."""
        return self.state.update_known_items(item_hashes, item_type)
    
    # Metrics Operations (backward compatibility)
    
    def store_run_metrics(self, run_id: str, command: str, metrics: Dict[str, Any]):
        """Store run metrics in database."""
        return self.metrics.store_run_metrics(run_id, command, metrics)
    
    # Cleanup Operations (backward compatibility)
    
    def cleanup_old_records(self) -> int:
        """
        Clean up old records using individual service cleanup methods.
        
        Returns:
            Total number of records deleted
        """
        total_deleted = 0
        
        try:
            # Cleanup old articles (30 days)
            total_deleted += self.articles.cleanup_old_articles(30)
            
            # Cleanup old analyses (30 days)  
            total_deleted += self.analyses.cleanup_old_analyses(30)
            
            # Cleanup old known items (30 days)
            total_deleted += self.state.cleanup_old_known_items(30)
            
            # Cleanup old metrics (90 days - keep longer for trend analysis)
            total_deleted += self.metrics.cleanup_old_metrics(90)
            
            logger.info(f"Total cleanup: deleted {total_deleted} old records")
            return total_deleted
            
        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")
            raise
    
    # Health Check (backward compatibility)
    
    def health_check(self) -> Dict[str, Any]:
        """Check database connection and return comprehensive status info."""
        try:
            # Get basic connection health
            health_info = self.connection_manager.health_check()
            
            if not health_info.get('connected', False):
                return health_info
            
            # Get table row counts and additional stats
            tables_info = {}
            
            # Article stats
            try:
                article_stats = self.articles.get_article_stats()
                tables_info['articles'] = {
                    'count': article_stats.get('total_articles', 0),
                    'recent_24h': article_stats.get('articles_24h', 0)
                }
            except Exception as e:
                logger.warning(f"Could not get article stats: {e}")
                tables_info['articles'] = {'error': str(e)}
            
            # Analysis stats
            try:
                analysis_stats = self.analyses.get_analysis_stats()
                tables_info['analyses'] = {
                    'count': analysis_stats.get('total_analyses', 0),
                    'recent_24h': analysis_stats.get('analyses_24h', 0)
                }
            except Exception as e:
                logger.warning(f"Could not get analysis stats: {e}")
                tables_info['analyses'] = {'error': str(e)}
            
            # State stats
            try:
                state_stats = self.state.get_state_stats()
                tables_info['known_items'] = {
                    'count': state_stats.get('total_known_items', 0),
                    'types': state_stats.get('item_types', {})
                }
            except Exception as e:
                logger.warning(f"Could not get state stats: {e}")
                tables_info['known_items'] = {'error': str(e)}
            
            # Metrics stats
            try:
                recent_runs = self.metrics.get_recent_runs(days=1)
                tables_info['run_metrics'] = {
                    'count': len(recent_runs),
                    'recent_24h': len(recent_runs)
                }
            except Exception as e:
                logger.warning(f"Could not get metrics stats: {e}")
                tables_info['run_metrics'] = {'error': str(e)}
            
            # Combine health info
            health_info.update({
                'tables': tables_info,
                'services_status': {
                    'articles': 'healthy',
                    'analyses': 'healthy', 
                    'state': 'healthy',
                    'metrics': 'healthy'
                }
            })
            
            return health_info
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'connected': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    # Emergency Operations (backward compatibility)
    
    def emergency_cleanup(self, max_records_per_table: int = 1000) -> Dict[str, int]:
        """Emergency cleanup if database gets too large."""
        deleted_counts = {}
        
        try:
            with self.connection_manager.transaction() as cursor:
                # Clean old articles (keep newest)
                cursor.execute("""
                    DELETE FROM articles 
                    WHERE id NOT IN (
                        SELECT id FROM articles 
                        ORDER BY published_at DESC NULLS LAST, created_at DESC 
                        LIMIT %s
                    )
                """, (max_records_per_table,))
                deleted_counts['articles'] = cursor.rowcount
                
                # Clean old analyses (keep newest)
                cursor.execute("""
                    DELETE FROM analyses 
                    WHERE id NOT IN (
                        SELECT id FROM analyses 
                        ORDER BY created_at DESC 
                        LIMIT %s
                    )
                """, (max_records_per_table,))
                deleted_counts['analyses'] = cursor.rowcount
                
                # Clean old run metrics (keep newest)
                cursor.execute("""
                    DELETE FROM run_metrics 
                    WHERE id NOT IN (
                        SELECT id FROM run_metrics 
                        ORDER BY timestamp DESC 
                        LIMIT %s
                    )
                """, (max_records_per_table,))
                deleted_counts['run_metrics'] = cursor.rowcount
                
                # Clean old known items (keep more active ones)
                cursor.execute("""
                    DELETE FROM known_items 
                    WHERE id NOT IN (
                        SELECT id FROM known_items 
                        ORDER BY last_seen DESC 
                        LIMIT %s
                    )
                """, (max_records_per_table * 2,))  # Keep more known items
                deleted_counts['known_items'] = cursor.rowcount
                
            logger.info(f"Emergency cleanup completed: {deleted_counts}")
            return deleted_counts
            
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
            raise DatabaseError(f"Emergency cleanup failed: {e}")
    
    def recover_from_error(self) -> bool:
        """Attempt to recover from database errors."""
        try:
            # Test connection through connection manager
            health = self.health_check()
            if health.get('connected', False):
                logger.info("Database connection recovered successfully")
                return True
            
            logger.error("Database recovery failed")
            return False
            
        except Exception as e:
            logger.error(f"Database recovery attempt failed: {e}")
            return False
    
    # Connection Management
    
    def close(self):
        """Close database connection."""
        self.connection_manager.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()