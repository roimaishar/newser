#!/usr/bin/env python3
"""
Unified database connection management.

Provides single entry point for database connections with automatic fallback logic.
"""

import logging
import os
from typing import Optional, Union

from ..database import DatabaseError
from .supabase_api import SupabaseApiAdapter, SupabaseApiError
from .legacy_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)

# Global database instance
_db_instance = None


def get_database() -> Union[SupabaseApiAdapter, DatabaseAdapter]:
    """
    Get database connection with automatic fallback logic.
    
    Priority:
    1. Supabase REST API (preferred, works everywhere)
    2. Direct PostgreSQL (only if explicitly requested)
    
    Returns:
        Database adapter instance
        
    Raises:
        DatabaseError: If no connection method succeeds
    """
    global _db_instance
    if _db_instance is not None:
        return _db_instance
    
    # Check environment
    is_ci = os.getenv('CI') or os.getenv('GITHUB_ACTIONS')
    force_direct = os.getenv('USE_DIRECT_CONNECTION') == 'true'
    
    # Try Supabase API first (preferred)
    if not force_direct:
        try:
            logger.info("Using Supabase REST API (preferred mode)")
            _db_instance = SupabaseApiAdapter()
            return _db_instance
        except Exception as api_error:
            if is_ci:
                # In CI, don't fallback to direct connection
                logger.error(f"API connection failed in CI: {api_error}")
                raise DatabaseError(f"Database API connection failed: {api_error}")
            else:
                logger.warning(f"API adapter failed: {api_error}")
    
    # Try direct PostgreSQL connection (only if requested or API failed in dev)
    if force_direct or not is_ci:
        try:
            logger.info("Attempting direct PostgreSQL connection")
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Database connection timed out")
            
            # Set timeout for connection attempt
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(10)
            
            try:
                _db_instance = DatabaseAdapter()
                _db_instance.health_check()  # Test connection
                logger.info("Using direct PostgreSQL connection")
                return _db_instance
            finally:
                signal.alarm(0)  # Clear timeout
                
        except Exception as direct_error:
            logger.error(f"Direct connection failed: {direct_error}")
    
    # No connection method succeeded
    raise DatabaseError("No database connection method succeeded")


def close_database():
    """Close global database connection."""
    global _db_instance
    if _db_instance:
        if hasattr(_db_instance, 'close'):
            _db_instance.close()
        _db_instance = None


def reset_database_connection():
    """Force reset of database connection (useful for testing)."""
    close_database()
    # Next call to get_database() will create new connection