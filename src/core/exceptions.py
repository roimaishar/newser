#!/usr/bin/env python3
"""
Standardized exception hierarchy for the news aggregator.

Provides specific exception types for different error conditions with
proper error context and recovery suggestions.
"""

from typing import Optional, Dict, Any


class NewsAggregatorError(Exception):
    """Base exception for all news aggregator errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize base exception.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            context: Additional error context
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context
        }


# Source-related exceptions
class SourceError(NewsAggregatorError):
    """Base exception for news source errors."""
    pass


class SourceConnectionError(SourceError):
    """Failed to connect to news source."""
    
    def __init__(self, source_name: str, url: str, original_error: Exception):
        message = f"Failed to connect to {source_name} at {url}"
        context = {
            'source_name': source_name,
            'url': url,
            'original_error': str(original_error)
        }
        super().__init__(message, context=context)


class SourceParseError(SourceError):
    """Failed to parse content from news source."""
    
    def __init__(self, source_name: str, parse_stage: str, original_error: Exception):
        message = f"Failed to parse {parse_stage} from {source_name}"
        context = {
            'source_name': source_name,
            'parse_stage': parse_stage,
            'original_error': str(original_error)
        }
        super().__init__(message, context=context)


class SourceTimeoutError(SourceError):
    """Source request timed out."""
    
    def __init__(self, source_name: str, timeout_seconds: int):
        message = f"Timeout connecting to {source_name} after {timeout_seconds}s"
        context = {
            'source_name': source_name,
            'timeout_seconds': timeout_seconds
        }
        super().__init__(message, context=context)


# Database-related exceptions
class DatabaseError(NewsAggregatorError):
    """Base exception for database errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Failed to connect to database."""
    
    def __init__(self, connection_type: str, original_error: Exception):
        message = f"Failed to connect to database via {connection_type}"
        context = {
            'connection_type': connection_type,
            'original_error': str(original_error)
        }
        super().__init__(message, context=context)


class DatabaseOperationError(DatabaseError):
    """Database operation failed."""
    
    def __init__(self, operation: str, table: str, original_error: Exception):
        message = f"Database {operation} failed on table {table}"
        context = {
            'operation': operation,
            'table': table,
            'original_error': str(original_error)
        }
        super().__init__(message, context=context)


# Analysis-related exceptions
class AnalysisError(NewsAggregatorError):
    """Base exception for analysis errors."""
    pass


class AnalysisValidationError(AnalysisError):
    """Analysis input validation failed."""
    
    def __init__(self, validation_errors: list):
        message = f"Analysis validation failed: {len(validation_errors)} errors"
        context = {'validation_errors': validation_errors}
        super().__init__(message, context=context)


class AnalysisTimeoutError(AnalysisError):
    """Analysis operation timed out."""
    
    def __init__(self, analysis_type: str, timeout_seconds: int):
        message = f"{analysis_type} analysis timed out after {timeout_seconds}s"
        context = {
            'analysis_type': analysis_type,
            'timeout_seconds': timeout_seconds
        }
        super().__init__(message, context=context)


class LLMError(AnalysisError):
    """LLM/AI analysis error."""
    
    def __init__(self, provider: str, model: str, original_error: Exception):
        message = f"LLM error from {provider} ({model})"
        context = {
            'provider': provider,
            'model': model,
            'original_error': str(original_error)
        }
        super().__init__(message, context=context)


# Notification-related exceptions
class NotificationError(NewsAggregatorError):
    """Base exception for notification errors."""
    pass


class NotificationChannelError(NotificationError):
    """Notification channel unavailable or failed."""
    
    def __init__(self, channel: str, operation: str, original_error: Exception):
        message = f"Notification {operation} failed for channel {channel}"
        context = {
            'channel': channel,
            'operation': operation,
            'original_error': str(original_error)
        }
        super().__init__(message, context=context)


class NotificationRateLimitError(NotificationError):
    """Notification rate limit exceeded."""
    
    def __init__(self, channel: str, retry_after_seconds: Optional[int] = None):
        message = f"Rate limit exceeded for {channel}"
        if retry_after_seconds:
            message += f", retry after {retry_after_seconds}s"
        
        context = {
            'channel': channel,
            'retry_after_seconds': retry_after_seconds
        }
        super().__init__(message, context=context)


# Configuration-related exceptions
class ConfigurationError(NewsAggregatorError):
    """Configuration is invalid or missing."""
    
    def __init__(self, config_key: str, issue: str):
        message = f"Configuration error for {config_key}: {issue}"
        context = {
            'config_key': config_key,
            'issue': issue
        }
        super().__init__(message, context=context)


class MissingDependencyError(ConfigurationError):
    """Required dependency is missing."""
    
    def __init__(self, dependency_name: str, install_command: Optional[str] = None):
        message = f"Missing required dependency: {dependency_name}"
        if install_command:
            message += f" (install with: {install_command})"
        
        context = {
            'dependency_name': dependency_name,
            'install_command': install_command
        }
        super().__init__(message, context=context)


# Validation-related exceptions
class ValidationError(NewsAggregatorError):
    """Data validation failed."""
    
    def __init__(self, field: str, value: Any, expected: str):
        message = f"Validation failed for {field}: expected {expected}, got {type(value).__name__}"
        context = {
            'field': field,
            'value': str(value),
            'expected': expected,
            'actual_type': type(value).__name__
        }
        super().__init__(message, context=context)


# Recovery utilities
class ErrorRecovery:
    """Utilities for error recovery and retry logic."""
    
    @staticmethod
    def is_retryable_error(error: Exception) -> bool:
        """Check if an error is potentially retryable."""
        retryable_types = [
            SourceConnectionError,
            SourceTimeoutError,
            DatabaseConnectionError,
            NotificationChannelError,
            AnalysisTimeoutError
        ]
        return any(isinstance(error, error_type) for error_type in retryable_types)
    
    @staticmethod
    def get_retry_delay(error: Exception, attempt: int) -> int:
        """Get recommended retry delay in seconds."""
        if isinstance(error, NotificationRateLimitError):
            return error.context.get('retry_after_seconds', 60)
        
        # Exponential backoff: 2^attempt seconds, max 300s (5 minutes)
        return min(2 ** attempt, 300)
    
    @staticmethod
    def should_fallback(error: Exception) -> bool:
        """Check if we should try fallback mechanisms."""
        fallback_types = [
            DatabaseConnectionError,
            SourceConnectionError,
            LLMError
        ]
        return any(isinstance(error, error_type) for error_type in fallback_types)


# Legacy exception mapping for backward compatibility
# Maps old exception types to new ones for smooth migration
LEGACY_EXCEPTION_MAP = {
    'DatabaseError': DatabaseError,
    'SourceError': SourceError,
    'AnalysisError': AnalysisError,
    'NotificationError': NotificationError
}