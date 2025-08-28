#!/usr/bin/env python3
"""
Database adapter for Supabase PostgreSQL storage.

Provides unified interface for all database operations, replacing JSON file storage.
"""

import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
import psycopg
from psycopg.rows import dict_row
import os

from core.feed_parser import Article

# Try to import API adapter as fallback
try:
    from .supabase_adapter import get_api_database, SupabaseApiAdapter, SupabaseApiError
    HAS_API_ADAPTER = True
except ImportError:
    HAS_API_ADAPTER = False

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class DatabaseAdapter:
    """Unified database adapter for all storage operations."""
    
    def __init__(self, connection_string: str = None):
        """
        Initialize database adapter.
        
        Args:
            connection_string: PostgreSQL connection string. If None, uses environment.
        """
        self.connection_string = connection_string or self._get_connection_string()
        self.connection = None
        self._connect()
    
    def _get_connection_string(self) -> str:
        """Build connection string from environment variables."""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url:
            raise DatabaseError("SUPABASE_URL environment variable not set")
        
        # Extract components from Supabase URL
        # Format: https://project-id.supabase.co
        if not supabase_url.startswith('https://'):
            raise DatabaseError(f"Invalid Supabase URL format: {supabase_url}")
        
        host = supabase_url.replace('https://', '')
        
        # Build PostgreSQL connection string for Supabase
        # Use connection pooling port 6543 for better reliability
        return f"postgresql://postgres.[password]@{host}:6543/postgres?sslmode=require"
    
    def _connect(self):
        """Establish database connection."""
        try:
            # For Supabase, we need to use the service key for direct DB access
            db_password = os.getenv('SUPABASE_DB_PASSWORD')
            if not db_password:
                raise DatabaseError("SUPABASE_DB_PASSWORD environment variable not set")
            
            # Replace placeholder password
            connection_string = self.connection_string.replace('[password]', db_password)
            
            self.connection = psycopg.connect(
                connection_string,
                row_factory=dict_row,
                autocommit=True
            )
            logger.info("Database connection established")
            
        except psycopg.Error as e:
            raise DatabaseError(f"Failed to connect to database: {e}")
    
    def _get_connection(self):
        """Get database connection with error handling."""
        try:
            return psycopg.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                dbname=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                sslmode='require',
                row_factory=dict_row
            )
        except psycopg.Error:
            self._connect()
    
    def ensure_connection(self):
        """Ensure database connection is active."""
        try:
            if not self.connection or self.connection.closed:
                self._connect()
            else:
                # Test connection
                with self.connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
        except psycopg.Error:
            self._connect()
    
    def close(self):
        """Close database connection."""
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.debug("Database connection closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # Article Operations
    
    def store_articles(self, articles: List[Article]) -> int:
        """
        Store articles in database with deduplication.
        
        Args:
            articles: List of Article objects
            
        Returns:
            Number of new articles stored
        """
        self.ensure_connection()
        stored_count = 0
        
        try:
            with self.connection.cursor() as cursor:
                for article in articles:
                    content_hash = self._generate_content_hash(article)
                    
                    # Insert with ON CONFLICT to handle duplicates
                    cursor.execute("""
                        INSERT INTO articles (title, link, source, summary, published_at, content_hash)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (content_hash) DO NOTHING
                        RETURNING id
                    """, (
                        article.title,
                        article.link,
                        article.source,
                        article.summary,
                        article.published,
                        content_hash
                    ))
                    
                    if cursor.fetchone():
                        stored_count += 1
                        
            logger.info(f"Stored {stored_count} new articles")
            return stored_count
            
        except psycopg.Error as e:
            raise DatabaseError(f"Failed to store articles: {e}")
    
    def get_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get articles from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of article dictionaries
        """
        self.ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT title, link, source, summary, published_at, content_hash, created_at
                    FROM articles
                    WHERE created_at >= NOW() - INTERVAL '%s hours'
                    ORDER BY published_at DESC
                """, (hours,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except psycopg.Error as e:
            raise DatabaseError(f"Failed to get recent articles: {e}")
    
    # Analysis Operations
    
    def store_analysis(self, run_id: str, analysis_result) -> int:
        """
        Store analysis result in database.
        
        Args:
            run_id: Unique run identifier
            analysis_result: Hebrew analysis result object
            
        Returns:
            Analysis ID
        """
        self.ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO analyses (
                        run_id, analysis_type, summary, key_topics, bulletins,
                        confidence, articles_analyzed, has_new_content, analysis_timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    run_id,
                    analysis_result.analysis_type,
                    analysis_result.summary,
                    analysis_result.key_topics,
                    analysis_result.bulletins,
                    analysis_result.confidence,
                    analysis_result.articles_analyzed,
                    analysis_result.has_new_content,
                    analysis_result.analysis_timestamp
                ))
                
                result = cursor.fetchone()
                analysis_id = result['id']
                logger.info(f"Stored analysis with ID {analysis_id}")
                return analysis_id
                
        except psycopg.Error as e:
            logger.error(f"Failed to store analysis: {e}")
            raise DatabaseError(f"Failed to store analysis: {e}")
    
    # Known Items (State Management)
    
    def get_known_items(self, item_type: str = 'article') -> List[str]:
        """
        Get list of known item hashes for novelty detection.
        
        Args:
            item_type: Type of items to retrieve
            
        Returns:
            List of item hashes
        """
        self.ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT item_hash FROM known_items
                    WHERE item_type = %s
                    AND last_seen >= NOW() - INTERVAL '30 days'
                """, (item_type,))
                
                return [row['item_hash'] for row in cursor.fetchall()]
                
        except psycopg.Error as e:
            logger.error(f"Failed to get known items: {e}")
            raise DatabaseError(f"Failed to get known items: {e}")
    
    def update_known_items(self, item_hashes: List[str], item_type: str = 'article'):
        """
        Update known items with current timestamp.
        
        Args:
            item_hashes: List of item hashes to update/insert
            item_type: Type of items
        """
        self.ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                for item_hash in item_hashes:
                    cursor.execute("""
                        INSERT INTO known_items (item_hash, item_type, last_seen)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (item_hash) 
                        DO UPDATE SET last_seen = EXCLUDED.last_seen
                    """, (item_hash, item_type, datetime.now(timezone.utc)))
                    
            logger.debug(f"Updated {len(item_hashes)} known items")
            
        except psycopg.Error as e:
            raise DatabaseError(f"Failed to update known items: {e}")
    
    # Metrics Operations
    
    def store_run_metrics(self, run_id: str, command: str, metrics: Dict[str, Any]):
        """
        Store run metrics in database.
        
        Args:
            run_id: Unique run identifier
            command: Command that was executed
            metrics: Dictionary of metrics
        """
        self.ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO run_metrics (
                        run_id, command_used, articles_scraped, articles_after_dedup,
                        processing_time_seconds, success, error_message
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    run_id,
                    command,
                    metrics.get('articles_scraped', 0),
                    metrics.get('articles_after_dedup', 0),
                    metrics.get('processing_time', 0),
                    metrics.get('success', True),
                    metrics.get('error_message')
                ))
                
        except psycopg.Error as e:
            logger.error(f"Failed to store run metrics: {e}")
            raise DatabaseError(f"Failed to store run metrics: {e}")
    
    # Cleanup Operations
    
    def cleanup_old_records(self) -> int:
        """
        Clean up old records using database function.
        
        Returns:
            Number of records deleted
        """
        self.ensure_connection()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT cleanup_old_records()")
                result = cursor.fetchone()
                deleted_count = result[0] if result else 0
                logger.info(f"Cleaned up {deleted_count} old records")
                return deleted_count
                
        except psycopg.Error as e:
            logger.error(f"Failed to cleanup old records: {e}")
            raise DatabaseError(f"Failed to cleanup old records: {e}")
    
    # Health Check
    
    def health_check(self) -> Dict[str, Any]:
        """Check database connection and return status info."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Test basic connectivity
                cursor.execute("SELECT 1")
                
                # Get table row counts
                tables = {}
                for table in ['articles', 'analyses', 'known_items', 'run_metrics']:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        tables[table] = count
                    except Exception as e:
                        logger.warning(f"Could not count rows in {table}: {e}")
                        tables[table] = "unknown"
                
                return {
                    'connected': True,
                    'tables': tables,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'connected': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def emergency_cleanup(self, max_records_per_table: int = 1000) -> Dict[str, int]:
        """Emergency cleanup if database gets too large."""
        deleted_counts = {}
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Clean old articles (keep newest)
                cursor.execute("""
                    DELETE FROM articles 
                    WHERE id NOT IN (
                        SELECT id FROM articles 
                        ORDER BY published_date DESC 
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
                
                conn.commit()
                logger.info(f"Emergency cleanup completed: {deleted_counts}")
                
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
            raise DatabaseError(f"Emergency cleanup failed: {e}")
        
        return deleted_counts
    
    def recover_from_error(self) -> bool:
        """Attempt to recover from database errors."""
        try:
            # Test connection
            health = self.health_check()
            if health['connected']:
                logger.info("Database connection recovered successfully")
                return True
            
            # Try reconnecting with fresh connection
            if hasattr(self, '_connection'):
                delattr(self, '_connection')
            
            # Test again
            health = self.health_check()
            if health['connected']:
                logger.info("Database reconnected successfully")
                return True
            
            logger.error("Database recovery failed")
            return False
            
        except Exception as e:
            logger.error(f"Database recovery attempt failed: {e}")
            return False

    def _generate_content_hash(self, article: Article) -> str:
        """Generate unique hash for article content."""
        content = f"{article.title}|{article.link}|{article.source}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

# ... (rest of the code remains the same)
_db_adapter = None


def get_database():
    """Get global database adapter instance with automatic fallback."""
    global _db_adapter
    if _db_adapter is None:
        # Force API-only mode in CI environments (GitHub Actions, etc.)
        import os
        is_ci = os.getenv('CI') or os.getenv('GITHUB_ACTIONS')
        
        if HAS_API_ADAPTER and (is_ci or not _should_try_direct_connection()):
            try:
                logger.info("Using Supabase REST API (CI environment or API-preferred mode)")
                _db_adapter = get_api_database()
                return _db_adapter
            except Exception as api_error:
                if is_ci:
                    # In CI, don't fallback to direct connection - it will timeout
                    logger.error(f"API connection failed in CI environment: {api_error}")
                    raise DatabaseError(f"Database API connection failed in CI: {api_error}")
                else:
                    logger.warning(f"API adapter failed: {api_error}, trying direct connection")
        
        if not is_ci:
            try:
                # Try direct PostgreSQL connection only in non-CI environments
                logger.info("Attempting direct PostgreSQL connection")
                _db_adapter = DatabaseAdapter()
                _db_adapter.health_check()
                logger.info("Using direct PostgreSQL connection")
            except Exception as e:
                if HAS_API_ADAPTER:
                    logger.error(f"Both API and direct connection failed")
                    raise DatabaseError(f"No database connection available: {e}")
                else:
                    logger.error("Direct DB connection failed and no API adapter")
                    raise DatabaseError(f"No database connection available: {e}")
        else:
            # This shouldn't happen if API adapter worked above
            raise DatabaseError("No database connection available in CI environment")
    
    return _db_adapter


def _should_try_direct_connection() -> bool:
    """Determine if direct PostgreSQL connection should be attempted."""
    import os
    # Skip direct connection if we're in a restricted network environment
    return not (os.getenv('CI') or os.getenv('GITHUB_ACTIONS') or os.getenv('FORCE_API_MODE'))


def close_database():
    """Close global database connection."""
    global _db_adapter
    if _db_adapter:
        _db_adapter.close()
        _db_adapter = None
