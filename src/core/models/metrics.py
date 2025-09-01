#!/usr/bin/env python3
"""
Metrics and performance data models.

Contains data structures for tracking run metrics and performance data.
"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class RunRecord:
    """Represents a single execution run."""
    run_id: str
    timestamp: datetime
    hours_window: int
    command_used: str
    articles_scraped: int
    after_dedup: int
    success: bool
    processing_time: float = 0.0
    error_message: Optional[str] = None