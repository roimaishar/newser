#!/usr/bin/env python3
"""
Deduplication Strategies

Provides different strategies for detecting duplicate articles using the Strategy pattern.
Each strategy focuses on a specific aspect of duplicate detection.
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import List, Set, Optional, Tuple
from difflib import SequenceMatcher
import unicodedata
from urllib.parse import urlparse

from core.feed_parser import Article

logger = logging.getLogger(__name__)


class DeduplicationStrategy(ABC):
    """Abstract base class for deduplication strategies."""
    
    @abstractmethod
    def is_duplicate(self, article1: Article, article2: Article) -> bool:
        """
        Check if two articles are duplicates according to this strategy.
        
        Args:
            article1: First article to compare
            article2: Second article to compare
            
        Returns:
            True if articles are considered duplicates, False otherwise
        """
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """
        Get priority of this strategy (lower number = higher priority).
        
        Returns:
            Priority value (0-100, where 0 is highest priority)
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get human-readable name of this strategy."""
        pass


class ExactUrlStrategy(DeduplicationStrategy):
    """Strategy for detecting exact URL duplicates (highest priority)."""
    
    def __init__(self):
        """Initialize exact URL strategy."""
        self.tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
            'fbclid', 'gclid', 'ref', 'source'
        }
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL by removing tracking parameters and fragments."""
        if not url:
            return ""
            
        # Remove fragment
        url = url.split('#')[0]
        
        # Remove tracking parameters
        if '?' in url:
            base_url, params = url.split('?', 1)
            param_pairs = params.split('&')
            
            clean_params = []
            for param in param_pairs:
                if '=' in param:
                    key = param.split('=')[0].lower()
                    if key not in self.tracking_params:
                        clean_params.append(param)
                        
            if clean_params:
                url = base_url + '?' + '&'.join(clean_params)
            else:
                url = base_url
                
        return url.lower().strip()
    
    def is_duplicate(self, article1: Article, article2: Article) -> bool:
        """Check if articles have identical normalized URLs."""
        url1 = self.normalize_url(article1.link)
        url2 = self.normalize_url(article2.link)
        
        if not url1 or not url2:
            return False
            
        return url1 == url2
    
    def get_priority(self) -> int:
        """Highest priority strategy."""
        return 0
    
    def get_name(self) -> str:
        """Get strategy name."""
        return "Exact URL"


class SimilarUrlStrategy(DeduplicationStrategy):
    """Strategy for detecting similar URLs (same domain, similar path)."""
    
    def __init__(self, path_similarity_threshold: float = 0.9):
        """
        Initialize similar URL strategy.
        
        Args:
            path_similarity_threshold: Minimum path similarity to consider URLs similar
        """
        self.path_similarity_threshold = path_similarity_threshold
        self.exact_url_strategy = ExactUrlStrategy()
    
    def is_duplicate(self, article1: Article, article2: Article) -> bool:
        """Check if articles have similar URLs (same domain, similar path)."""
        # Skip if exact URLs (handled by ExactUrlStrategy)
        if self.exact_url_strategy.is_duplicate(article1, article2):
            return False
            
        try:
            url1 = self.exact_url_strategy.normalize_url(article1.link)
            url2 = self.exact_url_strategy.normalize_url(article2.link)
            
            if not url1 or not url2:
                return False
            
            parsed1 = urlparse(url1)
            parsed2 = urlparse(url2)
            
            # Must be same domain
            if parsed1.netloc != parsed2.netloc:
                return False
                
            # Check path similarity
            path_similarity = SequenceMatcher(None, parsed1.path, parsed2.path).ratio()
            return path_similarity >= self.path_similarity_threshold
            
        except Exception as e:
            logger.debug(f"Error in similar URL comparison: {e}")
            return False
    
    def get_priority(self) -> int:
        """High priority, after exact URL."""
        return 10
    
    def get_name(self) -> str:
        """Get strategy name."""
        return "Similar URL"


class TitleSimilarityStrategy(DeduplicationStrategy):
    """Strategy for detecting duplicates based on title similarity."""
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize title similarity strategy.
        
        Args:
            similarity_threshold: Minimum similarity to consider titles duplicates
        """
        self.similarity_threshold = similarity_threshold
        
        # Common stop words for normalization
        self.stop_words = {
            # Hebrew
            'של', 'את', 'על', 'אל', 'מן', 'בן', 'כל', 'לא', 'או', 'גם', 'רק', 'עם', 'אך', 'כי',
            'זה', 'זו', 'הוא', 'היא', 'הם', 'הן', 'אני', 'אתה', 'אתם', 'אתן', 'אנחנו',
            # English  
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'among', 'this', 'that', 'these', 'those'
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
            
        # Normalize Unicode characters (helpful for Hebrew)
        text = unicodedata.normalize('NFKD', text)
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation, keep letters, digits, spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_keywords(self, title: str) -> Set[str]:
        """Extract meaningful keywords from title."""
        normalized = self.normalize_text(title)
        words = set(normalized.split())
        
        # Remove stop words and short words
        keywords = {word for word in words - self.stop_words if len(word) > 2}
        
        return keywords
    
    def calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles."""
        if not title1 or not title2:
            return 0.0
            
        # Method 1: Direct text similarity
        norm1 = self.normalize_text(title1)
        norm2 = self.normalize_text(title2)
        
        if norm1 == norm2:
            return 1.0
            
        text_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Method 2: Keyword overlap similarity  
        keywords1 = self.extract_keywords(title1)
        keywords2 = self.extract_keywords(title2)
        
        if not keywords1 or not keywords2:
            keyword_similarity = 0.0
        else:
            intersection = keywords1.intersection(keywords2)
            union = keywords1.union(keywords2)
            keyword_similarity = len(intersection) / len(union) if union else 0.0
        
        # Combine methods (weighted average)
        combined_similarity = (text_similarity * 0.6) + (keyword_similarity * 0.4)
        
        return combined_similarity
    
    def is_duplicate(self, article1: Article, article2: Article) -> bool:
        """Check if articles have similar titles."""
        similarity = self.calculate_similarity(article1.title, article2.title)
        return similarity >= self.similarity_threshold
    
    def get_priority(self) -> int:
        """Lower priority than URL-based strategies."""
        return 20
    
    def get_name(self) -> str:
        """Get strategy name."""
        return "Title Similarity"


class ExactTitleStrategy(DeduplicationStrategy):
    """Strategy for detecting exact title matches (after normalization)."""
    
    def __init__(self):
        """Initialize exact title strategy."""
        self.title_strategy = TitleSimilarityStrategy()
    
    def is_duplicate(self, article1: Article, article2: Article) -> bool:
        """Check if articles have identical normalized titles."""
        norm1 = self.title_strategy.normalize_text(article1.title)
        norm2 = self.title_strategy.normalize_text(article2.title)
        
        return norm1 and norm2 and norm1 == norm2
    
    def get_priority(self) -> int:
        """Higher priority than similarity-based title matching."""
        return 15
    
    def get_name(self) -> str:
        """Get strategy name."""
        return "Exact Title"


class ContentHashStrategy(DeduplicationStrategy):
    """Strategy for detecting duplicates using content hash (title + link + source)."""
    
    def generate_content_hash(self, article: Article) -> str:
        """Generate content hash for article."""
        import hashlib
        content = f"{article.title}|{article.link}|{article.source}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def is_duplicate(self, article1: Article, article2: Article) -> bool:
        """Check if articles have identical content hashes."""
        hash1 = self.generate_content_hash(article1)
        hash2 = self.generate_content_hash(article2)
        return hash1 == hash2
    
    def get_priority(self) -> int:
        """Very high priority - exact match."""
        return 5
    
    def get_name(self) -> str:
        """Get strategy name."""
        return "Content Hash"


class CompositeDeduplicationStrategy:
    """
    Composite strategy that combines multiple deduplication strategies.
    
    Strategies are applied in priority order (lowest number first).
    """
    
    def __init__(self, strategies: Optional[List[DeduplicationStrategy]] = None):
        """
        Initialize composite strategy.
        
        Args:
            strategies: List of strategies to use. If None, uses default set.
        """
        if strategies is None:
            strategies = self._get_default_strategies()
        
        # Sort strategies by priority
        self.strategies = sorted(strategies, key=lambda s: s.get_priority())
        
        logger.info(f"Initialized deduplication with {len(self.strategies)} strategies: "
                   f"{[s.get_name() for s in self.strategies]}")
    
    def _get_default_strategies(self) -> List[DeduplicationStrategy]:
        """Get default set of deduplication strategies."""
        return [
            ExactUrlStrategy(),
            ContentHashStrategy(),
            SimilarUrlStrategy(),
            ExactTitleStrategy(),
            TitleSimilarityStrategy()
        ]
    
    def is_duplicate(self, article1: Article, article2: Article) -> Tuple[bool, Optional[str]]:
        """
        Check if two articles are duplicates using any strategy.
        
        Args:
            article1: First article
            article2: Second article
            
        Returns:
            Tuple of (is_duplicate, strategy_name)
        """
        for strategy in self.strategies:
            try:
                if strategy.is_duplicate(article1, article2):
                    return True, strategy.get_name()
            except Exception as e:
                logger.warning(f"Strategy '{strategy.get_name()}' failed: {e}")
                continue
        
        return False, None
    
    def add_strategy(self, strategy: DeduplicationStrategy) -> None:
        """Add a new strategy to the composite."""
        self.strategies.append(strategy)
        self.strategies.sort(key=lambda s: s.get_priority())
        logger.info(f"Added strategy: {strategy.get_name()}")
    
    def remove_strategy(self, strategy_name: str) -> bool:
        """
        Remove a strategy by name.
        
        Args:
            strategy_name: Name of strategy to remove
            
        Returns:
            True if strategy was removed, False if not found
        """
        for i, strategy in enumerate(self.strategies):
            if strategy.get_name() == strategy_name:
                del self.strategies[i]
                logger.info(f"Removed strategy: {strategy_name}")
                return True
        return False
    
    def get_strategy_names(self) -> List[str]:
        """Get names of all registered strategies in priority order."""
        return [strategy.get_name() for strategy in self.strategies]