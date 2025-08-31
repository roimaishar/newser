#!/usr/bin/env python3
"""
Strategy-Based Deduplicator

Main deduplicator class that uses the strategy pattern for flexible
duplicate detection with configurable strategies and detailed reporting.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pytz

from core.feed_parser import Article
from .strategies import CompositeDeduplicationStrategy, DeduplicationStrategy

logger = logging.getLogger(__name__)


class DeduplicationResult:
    """Results from deduplication process with detailed metrics."""
    
    def __init__(self):
        """Initialize empty deduplication result."""
        self.original_count = 0
        self.unique_count = 0
        self.duplicates_found = 0
        self.strategy_stats = {}  # strategy_name -> count
        self.processing_time = 0.0
        self.duplicate_pairs = []  # List of (article1, article2, strategy_name) tuples
    
    @property
    def duplicate_rate(self) -> float:
        """Calculate duplicate rate as percentage."""
        if self.original_count == 0:
            return 0.0
        return (self.duplicates_found / self.original_count) * 100
    
    def add_duplicate(self, article1: Article, article2: Article, strategy_name: str):
        """Record a duplicate detection."""
        self.duplicates_found += 1
        self.strategy_stats[strategy_name] = self.strategy_stats.get(strategy_name, 0) + 1
        self.duplicate_pairs.append((article1, article2, strategy_name))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            'original_count': self.original_count,
            'unique_count': self.unique_count,
            'duplicates_found': self.duplicates_found,
            'duplicate_rate': self.duplicate_rate,
            'strategy_stats': self.strategy_stats,
            'processing_time': self.processing_time
        }


class StrategyBasedDeduplicator:
    """
    Enhanced deduplicator using the strategy pattern.
    
    Provides configurable deduplication with detailed reporting and metrics.
    """
    
    def __init__(self, 
                 strategies: Optional[List[DeduplicationStrategy]] = None,
                 preserve_newest: bool = True):
        """
        Initialize strategy-based deduplicator.
        
        Args:
            strategies: List of strategies to use. If None, uses defaults.
            preserve_newest: Whether to keep newest article in duplicate groups
        """
        self.composite_strategy = CompositeDeduplicationStrategy(strategies)
        self.preserve_newest = preserve_newest
    
    def deduplicate(self, articles: List[Article]) -> Tuple[List[Article], DeduplicationResult]:
        """
        Remove duplicate articles using configured strategies.
        
        Args:
            articles: List of articles to deduplicate
            
        Returns:
            Tuple of (unique_articles, deduplication_result)
        """
        start_time = datetime.now()
        result = DeduplicationResult()
        result.original_count = len(articles)
        
        if not articles:
            return [], result
            
        logger.info(f"Deduplicating {len(articles)} articles using {len(self.composite_strategy.strategies)} strategies")
        
        # Sort articles by publication date if preserving newest
        if self.preserve_newest:
            sorted_articles = sorted(
                articles,
                key=lambda x: x.published or datetime.min.replace(tzinfo=pytz.UTC),
                reverse=True  # Newest first
            )
        else:
            sorted_articles = articles[:]
        
        unique_articles = []
        processed_count = 0
        
        for article in sorted_articles:
            processed_count += 1
            is_duplicate = False
            
            # Check against all unique articles found so far
            for existing_article in unique_articles:
                is_dup, strategy_name = self.composite_strategy.is_duplicate(article, existing_article)
                
                if is_dup:
                    is_duplicate = True
                    result.add_duplicate(article, existing_article, strategy_name)
                    logger.debug(f"Duplicate found by {strategy_name}: {article.title[:50]}...")
                    break
            
            if not is_duplicate:
                unique_articles.append(article)
            
            # Log progress for large datasets
            if processed_count % 100 == 0:
                logger.debug(f"Processed {processed_count}/{len(sorted_articles)} articles")
        
        result.unique_count = len(unique_articles)
        result.processing_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Deduplication completed: {result.original_count} → {result.unique_count} "
                   f"({result.duplicate_rate:.1f}% duplicates) in {result.processing_time:.2f}s")
        
        # Log strategy effectiveness
        for strategy_name, count in result.strategy_stats.items():
            logger.info(f"  {strategy_name}: {count} duplicates found")
        
        return unique_articles, result
    
    def deduplicate_simple(self, articles: List[Article]) -> List[Article]:
        """
        Simple deduplication that only returns unique articles.
        
        For backward compatibility with existing code.
        
        Args:
            articles: List of articles to deduplicate
            
        Returns:
            List of unique articles
        """
        unique_articles, _ = self.deduplicate(articles)
        return unique_articles
    
    def add_strategy(self, strategy: DeduplicationStrategy) -> None:
        """Add a new deduplication strategy."""
        self.composite_strategy.add_strategy(strategy)
    
    def remove_strategy(self, strategy_name: str) -> bool:
        """Remove a deduplication strategy by name."""
        return self.composite_strategy.remove_strategy(strategy_name)
    
    def get_strategy_names(self) -> List[str]:
        """Get names of all active strategies."""
        return self.composite_strategy.get_strategy_names()
    
    def benchmark_strategies(self, articles: List[Article]) -> Dict[str, Dict[str, Any]]:
        """
        Benchmark individual strategies against the article set.
        
        Args:
            articles: Articles to test strategies against
            
        Returns:
            Dictionary with benchmark results for each strategy
        """
        if len(articles) < 2:
            return {}
        
        logger.info(f"Benchmarking {len(self.composite_strategy.strategies)} strategies on {len(articles)} articles")
        
        benchmark_results = {}
        
        for strategy in self.composite_strategy.strategies:
            start_time = datetime.now()
            duplicates_found = 0
            comparisons = 0
            
            # Test strategy on all article pairs
            for i in range(len(articles)):
                for j in range(i + 1, len(articles)):
                    comparisons += 1
                    try:
                        if strategy.is_duplicate(articles[i], articles[j]):
                            duplicates_found += 1
                    except Exception as e:
                        logger.warning(f"Strategy {strategy.get_name()} failed on comparison: {e}")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            benchmark_results[strategy.get_name()] = {
                'duplicates_found': duplicates_found,
                'comparisons': comparisons,
                'processing_time': processing_time,
                'comparisons_per_second': comparisons / processing_time if processing_time > 0 else 0,
                'priority': strategy.get_priority()
            }
        
        return benchmark_results