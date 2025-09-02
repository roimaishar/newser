#!/usr/bin/env python3
"""
Dependency Injection Container

Provides a centralized way to manage dependencies and avoid scattered
instantiation throughout the codebase. Supports singleton and factory patterns.
"""

import logging
from typing import Any, Dict, Callable, TypeVar, Type, Optional
from functools import wraps
import threading

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Container:
    """Simple dependency injection container with lifecycle management."""
    
    def __init__(self):
        """Initialize empty container."""
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
    def register_singleton(self, service_name: str, factory: Callable[[], T]) -> None:
        """
        Register a service as singleton (created once, reused).
        
        Args:
            service_name: Unique name for the service
            factory: Function that creates the service instance
        """
        with self._lock:
            self._factories[service_name] = factory
            # Remove any existing instance to force recreation
            if service_name in self._singletons:
                del self._singletons[service_name]
    
    def register_factory(self, service_name: str, factory: Callable[[], T]) -> None:
        """
        Register a service as factory (new instance each time).
        
        Args:
            service_name: Unique name for the service
            factory: Function that creates service instances
        """
        with self._lock:
            self._factories[service_name] = factory
    
    def register_instance(self, service_name: str, instance: T) -> None:
        """
        Register an existing instance as singleton.
        
        Args:
            service_name: Unique name for the service
            instance: Pre-created service instance
        """
        with self._lock:
            self._singletons[service_name] = instance
    
    def get(self, service_name: str) -> Any:
        """
        Get service instance by name.
        
        Args:
            service_name: Name of the service to retrieve
            
        Returns:
            Service instance
            
        Raises:
            KeyError: If service is not registered
        """
        # Check for existing singleton first
        if service_name in self._singletons:
            return self._singletons[service_name]
            
        # Check if factory is registered
        if service_name not in self._factories:
            raise KeyError(f"Service '{service_name}' not registered")
        
        with self._lock:
            factory = self._factories[service_name]
            
            # Check if it should be singleton
            if hasattr(factory, '_is_singleton') and factory._is_singleton:
                # Double-check pattern for thread safety
                if service_name not in self._singletons:
                    instance = factory()
                    self._singletons[service_name] = instance
                    logger.debug(f"Created singleton instance for '{service_name}'")
                return self._singletons[service_name]
            else:
                # Factory - create new instance each time
                instance = factory()
                logger.debug(f"Created new instance for '{service_name}'")
                return instance
    
    def has(self, service_name: str) -> bool:
        """Check if service is registered."""
        return service_name in self._factories or service_name in self._singletons
    
    def clear(self) -> None:
        """Clear all registered services and instances."""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._singletons.clear()
    
    def reset_singleton(self, service_name: str) -> None:
        """Reset a singleton instance (will be recreated on next get())."""
        with self._lock:
            if service_name in self._singletons:
                del self._singletons[service_name]
                logger.debug(f"Reset singleton '{service_name}'")


def singleton(factory_func: Callable[[], T]) -> Callable[[], T]:
    """
    Decorator to mark a factory function as singleton.
    
    Usage:
        @singleton  
        def create_database():
            return DatabaseAdapter()
    """
    @wraps(factory_func)
    def wrapper():
        return factory_func()
    
    wrapper._is_singleton = True
    return wrapper


# Global container instance
_container: Optional[Container] = None
_container_lock = threading.Lock()


def get_container() -> Container:
    """Get global container instance (thread-safe singleton)."""
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = Container()
                _setup_default_services(_container)
    return _container


def reset_container() -> None:
    """Reset global container (useful for testing)."""
    global _container
    with _container_lock:
        if _container:
            _container.clear()
        _container = None


def _setup_default_services(container: Container) -> None:
    """Set up default service registrations with configuration injection."""
    
    @singleton
    def create_config():
        from core.config import get_config
        return get_config()
    
    @singleton
    def create_database():
        from core.database import get_database
        return get_database()
    
    @singleton 
    def create_security_validator():
        from core.security import SecurityValidator
        config = create_config()
        validator = SecurityValidator()
        # Inject configuration values
        validator.MAX_TITLE_LENGTH = config.app.max_title_length
        validator.MAX_SUMMARY_LENGTH = config.app.max_summary_length
        validator.MAX_URL_LENGTH = config.app.max_url_length
        return validator
    
    @singleton
    def create_feed_parser():
        from core.feed_parser import FeedParser
        config = create_config()
        return FeedParser(timeout=config.app.feed_timeout)
    
    def create_async_feed_parser():
        from core.async_feed_parser import AsyncFeedParser
        config = create_config()
        return AsyncFeedParser(
            timeout=config.app.feed_timeout,
            max_concurrent=config.app.max_concurrent_feeds,
            enable_cache=True
        )
        
    @singleton
    def create_state_manager():
        from core.state_manager import StateManager
        return StateManager()
    
    @singleton
    def create_data_manager():
        from core.data_manager import DataManager  
        return DataManager()
    
    @singleton
    def create_metrics_collector():
        from core.metrics_collector import MetricsCollector
        return MetricsCollector()
    
    def create_deduplicator():
        from core.deduplication import Deduplicator
        config = create_config()
        return Deduplicator(similarity_threshold=config.app.default_similarity_threshold)
    
    def create_openai_client():
        from integrations.openai_client import OpenAIClient
        config = create_config()
        if not config.has_openai():
            raise ValueError("OpenAI API key not configured")
        return OpenAIClient(api_key=config.integrations.openai_api_key)
    
    def create_slack_notifier():
        from core.notifications.channels.slack import SlackNotifier
        config = create_config()
        if not config.has_slack():
            raise ValueError("Slack configuration not found")
        return SlackNotifier()
    
    # Register services
    container.register_singleton('config', create_config)
    container.register_singleton('database', create_database)
    container.register_singleton('security_validator', create_security_validator)
    container.register_singleton('feed_parser', create_feed_parser)
    container.register_singleton('state_manager', create_state_manager)
    container.register_singleton('data_manager', create_data_manager) 
    container.register_singleton('metrics_collector', create_metrics_collector)
    
    # Non-singletons
    container.register_factory('deduplicator', create_deduplicator)
    container.register_factory('async_feed_parser', create_async_feed_parser)
    container.register_factory('openai_client', create_openai_client)
    container.register_factory('slack_notifier', create_slack_notifier)
    
    logger.debug("Default services registered in container")


# Convenience functions for common usage patterns

def get_config():
    """Get configuration instance from container."""
    return get_container().get('config')


def get_database():
    """Get database instance from container."""
    return get_container().get('database')


def get_security_validator():
    """Get security validator instance from container.""" 
    return get_container().get('security_validator')


def get_feed_parser():
    """Get feed parser instance from container."""
    return get_container().get('feed_parser')


def get_state_manager():
    """Get state manager instance from container."""
    return get_container().get('state_manager')


def get_data_manager():
    """Get data manager instance from container."""
    return get_container().get('data_manager')


def get_metrics_collector():
    """Get metrics collector instance from container."""
    return get_container().get('metrics_collector')


def create_deduplicator(similarity_threshold: float = 0.8):
    """Create new deduplicator instance with custom configuration."""
    from core.deduplication import Deduplicator
    return Deduplicator(similarity_threshold=similarity_threshold)


def create_openai_client():
    """Create new OpenAI client instance."""
    return get_container().get('openai_client')


def create_slack_notifier():
    """Create new Slack notifier instance."""
    return get_container().get('slack_notifier')


def create_async_feed_parser():
    """Create new async feed parser instance."""
    return get_container().get('async_feed_parser')