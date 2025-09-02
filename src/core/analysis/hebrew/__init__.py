#!/usr/bin/env python3
"""
Hebrew news analysis module.

Provides Hebrew-specific analysis capabilities including AI-powered
content analysis and novelty detection.
"""

from .analyzer import HebrewNewsAnalyzer
from .prompts import NewsAnalysisPrompts, SYSTEM_PROMPT, get_analysis_prompt, get_update_prompt, get_notification_prompt

__all__ = [
    'HebrewNewsAnalyzer', 'NewsAnalysisPrompts', 'SYSTEM_PROMPT',
    'get_analysis_prompt', 'get_update_prompt', 'get_notification_prompt'
]