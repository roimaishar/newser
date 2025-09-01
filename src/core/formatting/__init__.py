#!/usr/bin/env python3
"""
Formatting utilities for news display and notifications.

Handles all text formatting, templating, and display logic.
"""

from .display import format_article, format_hebrew_analysis, articles_to_dict
from .notifications import SmartFormatter

__all__ = ['format_article', 'format_hebrew_analysis', 'articles_to_dict', 'SmartFormatter']