#!/usr/bin/env python3
"""
Unified database connection module.

Replaces the old scattered database connection logic with the new adapter system.
"""

# Import the new unified connection system
from .adapters.connection import get_database, close_database, reset_database_connection
from .database import DatabaseError

# Export the same interface as before for backward compatibility
__all__ = ['get_database', 'close_database', 'reset_database_connection', 'DatabaseError']