#!/usr/bin/env python3
"""
Base command class for the modular command architecture.

Provides common functionality and interface that all commands inherit.
Uses dependency injection for better testability and maintainability.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from argparse import Namespace
from core.container import get_container

logger = logging.getLogger(__name__)


class BaseCommand(ABC):
    """
    Base class for all smart command endpoints.
    
    Provides common infrastructure like data management, metrics collection,
    and error handling that all commands can use. Uses dependency injection
    container for managing service instances.
    """
    
    def __init__(self, container=None):
        """
        Initialize base command with dependency injection container.
        
        Args:
            container: Optional container instance. If None, uses global container.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self._container = container or get_container()
    
    @property
    def config(self):
        """Get configuration from container."""
        return self._container.get('config')
    
    @property
    def data_manager(self):
        """Get data manager from container."""
        return self._container.get('data_manager')
    
    @property
    def metrics(self):
        """Get metrics collector from container."""
        return self._container.get('metrics_collector')
    
    @property
    def database(self):
        """Get database instance from container."""
        return self._container.get('database')
    
    @property
    def security_validator(self):
        """Get security validator from container."""
        return self._container.get('security_validator')
    
    @property
    def feed_parser(self):
        """Get feed parser from container."""
        return self._container.get('feed_parser')
    
    @property
    def state_manager(self):
        """Get state manager from container."""
        return self._container.get('state_manager')
    
    def create_deduplicator(self, similarity_threshold: float = 0.8):
        """Create new deduplicator instance with custom configuration."""
        from core.deduplication import Deduplicator
        return Deduplicator(similarity_threshold=similarity_threshold)
    
    def create_openai_client(self):
        """Create new OpenAI client instance."""
        return self._container.get('openai_client')
    
    def create_slack_notifier(self):
        """Create new Slack notifier instance."""
        return self._container.get('slack_notifier')
    
    @abstractmethod
    def execute(self, subcommand: str, args: Namespace) -> int:
        """
        Execute the command with given subcommand and arguments.
        
        Args:
            subcommand: The specific action to perform
            args: Parsed command line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        pass
    
    def get_available_subcommands(self) -> List[str]:
        """
        Get list of available subcommands for this command.
        
        Returns:
            List of subcommand names
        """
        # Default implementation looks for methods that don't start with _
        methods = []
        for attr_name in dir(self):
            if not attr_name.startswith('_') and callable(getattr(self, attr_name)):
                # Skip inherited methods from base class
                if attr_name not in ['execute', 'get_available_subcommands', 'handle_error']:
                    methods.append(attr_name)
        return methods
    
    def handle_error(self, error: Exception, context: str = "") -> int:
        """
        Standard error handling for commands.
        
        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
            
        Returns:
            Appropriate exit code
        """
        error_msg = f"{context}: {error}" if context else str(error)
        self.logger.error(error_msg, exc_info=True)
        
        # Map common exceptions to exit codes
        if isinstance(error, KeyboardInterrupt):
            self.logger.info("Command interrupted by user")
            return 130
        elif isinstance(error, FileNotFoundError):
            return 2
        elif isinstance(error, PermissionError):
            return 13
        elif isinstance(error, ValueError):
            return 22
        else:
            return 1
    
    def validate_args(self, args: Namespace, required_args: List[str] = None) -> bool:
        """
        Validate that required arguments are present.
        
        Args:
            args: Parsed arguments
            required_args: List of required argument names
            
        Returns:
            True if valid, False otherwise
        """
        if not required_args:
            return True
            
        missing = []
        for arg_name in required_args:
            if not hasattr(args, arg_name) or getattr(args, arg_name) is None:
                missing.append(arg_name)
        
        if missing:
            self.logger.error(f"Missing required arguments: {', '.join(missing)}")
            return False
            
        return True