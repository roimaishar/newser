#!/usr/bin/env python3
"""
Deduplication package with strategy pattern implementation.

Provides flexible deduplication strategies that can be combined and configured.
"""

from .strategies import (
    DeduplicationStrategy,
    ExactUrlStrategy,
    SimilarUrlStrategy, 
    TitleSimilarityStrategy,
    ExactTitleStrategy,
    ContentHashStrategy,
    CompositeDeduplicationStrategy
)
from .deduplicator import StrategyBasedDeduplicator

# Re-export the backward compatibility wrapper
# Import it locally to avoid circular imports
import logging
from typing import List
from .deduplicator import StrategyBasedDeduplicator
from .strategies import TitleSimilarityStrategy

class Deduplicator:
    """
    Backward compatibility wrapper for the new strategy-based deduplication system.
    
    Maintains the same interface as the original Deduplicator while delegating
    to the new modular strategy-based implementation.
    """
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize deduplicator with backward compatibility.
        
        Args:
            similarity_threshold: Minimum similarity score (0-1) to consider articles as duplicates
        """
        self.similarity_threshold = similarity_threshold
        
        # Create strategy-based deduplicator with default strategies
        from .strategies import (
            ExactUrlStrategy, ContentHashStrategy, SimilarUrlStrategy, 
            ExactTitleStrategy, TitleSimilarityStrategy
        )
        
        title_strategy = TitleSimilarityStrategy(similarity_threshold)
        
        self._strategy_deduplicator = StrategyBasedDeduplicator(
            strategies=[
                ExactUrlStrategy(),
                ContentHashStrategy(), 
                SimilarUrlStrategy(),
                ExactTitleStrategy(),
                title_strategy
            ]
        )
    
    def deduplicate(self, articles):
        """
        Remove duplicate articles from the list.
        
        Delegates to strategy-based deduplicator for actual processing.
        
        Returns:
            List of unique articles, preserving the newest version of duplicates
        """
        return self._strategy_deduplicator.deduplicate_simple(articles)
    
    # Expose some methods for backward compatibility
    
    def calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles (for backward compatibility)."""
        title_strategy = TitleSimilarityStrategy(self.similarity_threshold)
        return title_strategy.calculate_similarity(title1, title2)
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison (for backward compatibility)."""
        title_strategy = TitleSimilarityStrategy()
        return title_strategy.normalize_text(text)
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL (for backward compatibility)."""
        from .strategies import ExactUrlStrategy
        url_strategy = ExactUrlStrategy()
        return url_strategy.normalize_url(url)

__all__ = [
    'DeduplicationStrategy',
    'ExactUrlStrategy',
    'SimilarUrlStrategy',
    'TitleSimilarityStrategy', 
    'ExactTitleStrategy',
    'ContentHashStrategy',
    'CompositeDeduplicationStrategy',
    'StrategyBasedDeduplicator',
    'Deduplicator'
]