#!/usr/bin/env python3
"""
Database Connection Manager

Handles database connections with proper lifecycle management,
connection pooling, and error recovery.
"""

import logging
import psycopg
from psycopg.rows import dict_row
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class ConnectionManager:
    """Manages database connections with error handling and recovery."""
    
    def __init__(self, config):
        """
        Initialize connection manager with configuration.
        
        Args:
            config: Database configuration object
        """
        self.config = config
        self.connection: Optional[psycopg.Connection] = None
        self._connect()
    
    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from configuration."""
        url = self.config.supabase_url
        password = self.config.supabase_db_password
        
        if not url.startswith('https://'):
            raise DatabaseError(f"Invalid Supabase URL format: {url}")
        
        # Extract host from URL  
        host = url.replace('https://', '')
        
        # Use connection pooling port 6543 for better reliability
        return f"postgresql://postgres:{password}@{host}:6543/postgres?sslmode=require"
    
    def _connect(self) -> None:
        """Establish database connection."""
        try:
            connection_string = self._build_connection_string()
            
            self.connection = psycopg.connect(
                connection_string,
                row_factory=dict_row,
                autocommit=True,
                connect_timeout=self.config.connection_timeout
            )
            logger.debug("Database connection established")
            
        except psycopg.Error as e:
            raise DatabaseError(f"Failed to connect to database: {e}")
    
    def ensure_connection(self) -> None:
        """Ensure database connection is active, reconnect if needed."""
        try:
            if not self.connection or self.connection.closed:
                self._connect()
            else:
                # Test connection with a simple query
                with self.connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
        except psycopg.Error:
            logger.warning("Connection test failed, reconnecting...")
            self._connect()
    
    def get_connection(self) -> psycopg.Connection:
        """
        Get active database connection.
        
        Returns:
            Active database connection
            
        Raises:
            DatabaseError: If connection cannot be established
        """
        self.ensure_connection()
        return self.connection
    
    @contextmanager
    def get_cursor(self):
        """
        Get database cursor as context manager.
        
        Yields:
            Database cursor
        """
        self.ensure_connection()
        with self.connection.cursor() as cursor:
            yield cursor
    
    @contextmanager 
    def transaction(self):
        """
        Execute operations in a database transaction.
        
        Yields:
            Database cursor within transaction
        """
        connection = self.get_connection()
        # Temporarily disable autocommit for transaction
        connection.autocommit = False
        
        try:
            with connection.cursor() as cursor:
                yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.autocommit = True
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.debug("Database connection closed")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on database connection.
        
        Returns:
            Health status information
        """
        try:
            self.ensure_connection()
            
            with self.get_cursor() as cursor:
                # Test basic connectivity
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                
                # Get database version
                cursor.execute("SELECT version() as version")
                version_info = cursor.fetchone()
                
                return {
                    'connected': True,
                    'test_query': result['test'] == 1,
                    'version': version_info['version'],
                    'connection_info': {
                        'autocommit': self.connection.autocommit,
                        'closed': self.connection.closed,
                        'status': str(self.connection.info.transaction_status)
                    }
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'connected': False,
                'error': str(e)
            }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()