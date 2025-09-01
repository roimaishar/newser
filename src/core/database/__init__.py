#!/usr/bin/env python3
"""
Database package for news aggregator.

Provides modular database services with proper separation of concerns.
"""

from .connection_manager import ConnectionManager, DatabaseError
from .article_service import ArticleService
from .analysis_service import AnalysisService
from .state_service import StateService
from .metrics_service import MetricsService
from .database_facade import DatabaseFacade

# Re-export items from the new adapter system
from ..adapters.connection import get_database
from ..adapters.legacy_adapter import DatabaseAdapter

__all__ = [
    'ConnectionManager',
    'DatabaseError', 
    'ArticleService',
    'AnalysisService',
    'StateService',
    'MetricsService',
    'DatabaseFacade',
    'get_database',
    'DatabaseAdapter'
]