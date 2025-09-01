#!/usr/bin/env python3
"""
Database adapters for different connection methods.

Provides unified interface to different database backends and connection methods.
"""

from .supabase_api import SupabaseApiAdapter, SupabaseApiError
from .legacy_adapter import DatabaseAdapter
from .connection import get_database, close_database, reset_database_connection

__all__ = [
    'SupabaseApiAdapter', 'SupabaseApiError', 'DatabaseAdapter',
    'get_database', 'close_database', 'reset_database_connection'
]