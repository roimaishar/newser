#!/usr/bin/env python3
"""
Database adapter for Supabase PostgreSQL storage.

Provides unified interface for all database operations using modular services.
Maintains backward compatibility with the original DatabaseAdapter interface.
"""

import logging
import os
from typing import Optional

from .database.database_facade import DatabaseFacade
from .database import DatabaseError

# Try to import API adapter as fallback
try:
    from .supabase_adapter import get_api_database, SupabaseApiAdapter, SupabaseApiError
    HAS_API_ADAPTER = True
except ImportError:
    HAS_API_ADAPTER = False

logger = logging.getLogger(__name__)


class DatabaseAdapter:
    """
    Backward compatibility wrapper for the new modular database architecture.
    
    Delegates all operations to the DatabaseFacade while maintaining the
    same interface as the original DatabaseAdapter.
    """
    
    def __init__(self, config=None):
        """
        Initialize database adapter.
        
        Args:
            config: Configuration object. If None, gets from container.
        """
        if config is None:
            from core.container import get_config
            config = get_config()
        
        self._facade = DatabaseFacade(config)
    
    # Delegate all methods to the facade
    
    def store_articles(self, articles):
        """Store articles in database with deduplication."""
        return self._facade.store_articles(articles)
    
    def get_recent_articles(self, hours: int = 24):
        """Get articles from the last N hours."""
        return self._facade.get_recent_articles(hours)
    
    def store_analysis(self, run_id: str, analysis_result):
        """Store analysis result in database."""
        return self._facade.store_analysis(run_id, analysis_result)
    
    def get_known_items(self, item_type: str = 'article'):
        """Get list of known item hashes for novelty detection."""
        return self._facade.get_known_items(item_type)
    
    def update_known_items(self, item_hashes, item_type: str = 'article'):
        """Update known items with current timestamp."""
        return self._facade.update_known_items(item_hashes, item_type)
    
    def store_run_metrics(self, run_id: str, command: str, metrics):
        """Store run metrics in database."""
        return self._facade.store_run_metrics(run_id, command, metrics)
    
    def cleanup_old_records(self):
        """Clean up old records."""
        return self._facade.cleanup_old_records()
    
    def health_check(self):
        """Check database connection and return status info."""
        return self._facade.health_check()
    
    def emergency_cleanup(self, max_records_per_table: int = 1000):
        """Emergency cleanup if database gets too large."""
        return self._facade.emergency_cleanup(max_records_per_table)
    
    def recover_from_error(self):
        """Attempt to recover from database errors."""
        return self._facade.recover_from_error()
    
    def close(self):
        """Close database connection."""
        self._facade.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# ... (rest of the code remains the same)
_db_adapter = None


def get_database():
    """Get global database adapter instance with automatic fallback."""
    global _db_adapter
    if _db_adapter is None:
        # Force API-only mode in CI environments (GitHub Actions, etc.)
        import os
        is_ci = os.getenv('CI') or os.getenv('GITHUB_ACTIONS')
        
        # Try API first (preferred method)
        if HAS_API_ADAPTER:
            try:
                logger.info("Using Supabase REST API (preferred mode)")
                _db_adapter = get_api_database()
                return _db_adapter
            except Exception as api_error:
                if is_ci or not _should_try_direct_connection():
                    # In CI or when direct connection not requested, don't fallback
                    logger.error(f"API connection failed: {api_error}")
                    raise DatabaseError(f"Database API connection failed: {api_error}")
                else:
                    logger.warning(f"API adapter failed: {api_error}, trying direct connection")
        
        # Only try direct connection if explicitly requested
        if _should_try_direct_connection():
            try:
                # Try direct PostgreSQL connection only in non-CI environments
                logger.info("Attempting direct PostgreSQL connection")
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Database connection timed out")
                
                # Set a 10-second timeout for connection
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(10)
                
                try:
                    _db_adapter = DatabaseAdapter()
                    _db_adapter.health_check()
                    logger.info("Using direct PostgreSQL connection")
                finally:
                    signal.alarm(0)  # Disable timeout
            except Exception as e:
                logger.error(f"Direct connection failed: {e}")
                raise DatabaseError(f"No database connection available: {e}")
        else:
            # No connection method available or requested
            if HAS_API_ADAPTER:
                raise DatabaseError("API connection failed and direct connection not requested")
            else:
                raise DatabaseError("No database connection methods available")
    
    return _db_adapter


def _should_try_direct_connection() -> bool:
    """Determine if direct PostgreSQL connection should be attempted."""
    import os
    # Prefer API mode by default - only try direct connection if explicitly requested
    # This avoids connection timeouts and is more reliable
    return os.getenv('USE_DIRECT_CONNECTION') == 'true'


def close_database():
    """Close global database connection."""
    global _db_adapter
    if _db_adapter:
        _db_adapter.close()
        _db_adapter = None
