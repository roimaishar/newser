#!/usr/bin/env python3
"""
Legacy compatibility module.

Provides backward compatibility imports for moved modules to ease migration.
This module should be removed after all code is updated to use new locations.
"""

import warnings
from typing import Any

# Hebrew analyzer compatibility
try:
    from .analysis.hebrew.analyzer import HebrewNewsAnalyzer
    from .models.analysis import HebrewAnalysisResult
except ImportError:
    HebrewNewsAnalyzer = None
    HebrewAnalysisResult = None

# Notification compatibility
try:
    from .notifications.smart_notifier import SmartNotifier, create_smart_notifier
    from .notifications.scheduler import NotificationScheduler
    from .notifications.channels.slack import SlackNotifier
except ImportError:
    SmartNotifier = None
    create_smart_notifier = None
    NotificationScheduler = None
    SlackNotifier = None

# Database compatibility
try:
    from .adapters.connection import get_database, close_database
    from .adapters.legacy_adapter import DatabaseAdapter
    from .exceptions import DatabaseError
except ImportError:
    get_database = None
    close_database = None
    DatabaseAdapter = None
    DatabaseError = None

# Models compatibility
try:
    from .models.article import Article
    from .models.analysis import AnalysisRecord
    from .models.metrics import RunRecord
except ImportError:
    Article = None
    AnalysisRecord = None
    RunRecord = None


def _warn_legacy_import(old_module: str, new_module: str):
    """Issue deprecation warning for legacy imports."""
    warnings.warn(
        f"Importing from {old_module} is deprecated. "
        f"Please update to: from {new_module}",
        DeprecationWarning,
        stacklevel=3
    )


def get_legacy_hebrew_analyzer(*args, **kwargs) -> Any:
    """Legacy compatibility for HebrewNewsAnalyzer."""
    _warn_legacy_import("core.hebrew_analyzer", "core.analysis.hebrew.analyzer")
    if HebrewNewsAnalyzer is None:
        raise ImportError("Hebrew analyzer not available")
    return HebrewNewsAnalyzer(*args, **kwargs)


def get_legacy_smart_notifier(*args, **kwargs) -> Any:
    """Legacy compatibility for SmartNotifier."""
    _warn_legacy_import("core.smart_notifier", "core.notifications.smart_notifier")
    if create_smart_notifier is None:
        raise ImportError("Smart notifier not available")
    return create_smart_notifier(*args, **kwargs)


# Cleanup deprecated patterns
DEPRECATED_PATTERNS = [
    {
        'pattern': 'from core.hebrew_analyzer import',
        'replacement': 'from core.analysis.hebrew.analyzer import',
        'reason': 'Hebrew analyzer moved to analysis pipeline'
    },
    {
        'pattern': 'from core.smart_notifier import',
        'replacement': 'from core.notifications.smart_notifier import',
        'reason': 'Smart notifier moved to notifications module'
    },
    {
        'pattern': 'from core.formatters import',
        'replacement': 'from core.formatting import',
        'reason': 'Formatters consolidated into formatting module'
    },
    {
        'pattern': 'from core.database_adapter import',
        'replacement': 'from core.adapters.connection import',
        'reason': 'Database adapters moved to adapters module'
    }
]


def check_deprecated_imports(file_path: str) -> list:
    """
    Check file for deprecated import patterns.
    
    Args:
        file_path: Path to Python file to check
        
    Returns:
        List of deprecated patterns found
    """
    deprecated_found = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for pattern in DEPRECATED_PATTERNS:
            if pattern['pattern'] in content:
                deprecated_found.append({
                    'file': file_path,
                    'pattern': pattern['pattern'],
                    'replacement': pattern['replacement'],
                    'reason': pattern['reason']
                })
    
    except Exception:
        pass  # Ignore file read errors
    
    return deprecated_found


def get_migration_guide() -> str:
    """Get migration guide for updating imports."""
    guide = "# Import Migration Guide\n\n"
    guide += "The following imports have been moved in the modular architecture refactoring:\n\n"
    
    for i, pattern in enumerate(DEPRECATED_PATTERNS, 1):
        guide += f"{i}. **{pattern['pattern']}**\n"
        guide += f"   → `{pattern['replacement']}`\n"
        guide += f"   *Reason: {pattern['reason']}*\n\n"
    
    guide += "\n## Automated Migration\n\n"
    guide += "You can use search and replace to update imports:\n\n"
    
    for pattern in DEPRECATED_PATTERNS:
        guide += f"```bash\n"
        guide += f"find src -name '*.py' -exec sed -i 's/{pattern['pattern']}/{pattern['replacement']}/g' {{}} \\;\n"
        guide += f"```\n\n"
    
    return guide