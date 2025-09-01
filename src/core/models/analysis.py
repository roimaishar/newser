#!/usr/bin/env python3
"""
Analysis result data models.

Contains data structures for AI analysis results and metrics.
"""

from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class HebrewAnalysisResult:
    """Results from Hebrew news analysis with novelty detection."""
    has_new_content: bool
    analysis_type: str  # "thematic" or "updates"
    
    # Core analysis
    summary: str
    key_topics: List[str]
    sentiment: str
    insights: List[str]
    
    # Novelty detection (for updates mode)
    new_events: List[Dict[str, Any]]
    updated_events: List[Dict[str, Any]]
    bulletins: str
    
    # Metadata
    articles_analyzed: int
    confidence: float
    analysis_timestamp: datetime
    
    def __post_init__(self):
        """Validate and clean data."""
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.summary = self.summary.strip()
        self.bulletins = self.bulletins.strip()


@dataclass
class AnalysisRecord:
    """Represents an analysis result stored in database."""
    run_id: str
    timestamp: datetime
    analysis_type: str  # 'thematic' or 'updates'
    hebrew_result: HebrewAnalysisResult
    articles_analyzed: int
    confidence: float
    processing_time: float