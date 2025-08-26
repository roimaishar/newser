#!/usr/bin/env python3
"""
Deduplication module for news articles

Handles deduplication of news articles based on title similarity and URL matching.
Uses multiple strategies to identify duplicate content.
"""

import re
from typing import List, Set, Dict
from difflib import SequenceMatcher
import unicodedata
import logging
import datetime
import pytz
from .feed_parser import Article

logger = logging.getLogger(__name__)

class Deduplicator:
    """Handles deduplication of news articles."""
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize deduplicator.
        
        Args:
            similarity_threshold: Minimum similarity score (0-1) to consider articles as duplicates
        """
        self.similarity_threshold = similarity_threshold
        
        # Common Hebrew and English stop words for title normalization
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
        """
        Normalize text for comparison by:
        - Converting to lowercase
        - Removing punctuation and special characters
        - Normalizing Unicode characters
        - Removing extra whitespace
        """
        if not text:
            return ""
            
        # Normalize Unicode characters (helpful for Hebrew text)
        text = unicodedata.normalize('NFKD', text)
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation and special characters, keep only letters, digits, and spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_keywords(self, title: str) -> Set[str]:
        """Extract meaningful keywords from title by removing stop words."""
        normalized = self.normalize_text(title)
        words = set(normalized.split())
        
        # Remove stop words
        keywords = words - self.stop_words
        
        # Filter out very short words (likely not meaningful)
        keywords = {word for word in keywords if len(word) > 2}
        
        return keywords
    
    def calculate_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles using multiple methods.
        Returns a score between 0 and 1.
        """
        # Handle None titles
        if title1 is None or title2 is None:
            logger.warning(f"None title encountered: title1={title1}, title2={title2}")
            return 0.0
            
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
        
        # Combine both methods (weighted average)
        combined_similarity = (text_similarity * 0.6) + (keyword_similarity * 0.4)
        
        return combined_similarity
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize URL by removing tracking parameters and fragments.
        """
        if not url:
            return ""
            
        # Remove common tracking parameters
        tracking_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
            'fbclid', 'gclid', 'ref', 'source'
        ]
        
        # Simple URL cleaning - remove fragment and common tracking params
        url = url.split('#')[0]  # Remove fragment
        
        if '?' in url:
            base_url, params = url.split('?', 1)
            param_pairs = params.split('&')
            
            # Filter out tracking parameters
            clean_params = []
            for param in param_pairs:
                if '=' in param:
                    key = param.split('=')[0].lower()
                    if key not in tracking_params:
                        clean_params.append(param)
                        
            if clean_params:
                url = base_url + '?' + '&'.join(clean_params)
            else:
                url = base_url
                
        return url.lower().strip()
    
    def are_urls_similar(self, url1: str, url2: str) -> bool:
        """Check if two URLs point to the same article."""
        norm_url1 = self.normalize_url(url1)
        norm_url2 = self.normalize_url(url2)
        
        if norm_url1 == norm_url2:
            return True
            
        # Check if URLs are similar (same domain and similar path)
        try:
            from urllib.parse import urlparse
            
            parsed1 = urlparse(norm_url1)
            parsed2 = urlparse(norm_url2)
            
            # Same domain
            if parsed1.netloc != parsed2.netloc:
                return False
                
            # Similar paths (allow for slight variations)
            path_similarity = SequenceMatcher(None, parsed1.path, parsed2.path).ratio()
            return path_similarity > 0.9
            
        except Exception as e:
            logger.debug(f"Error comparing URLs: {e}")
            return False
    
    def deduplicate(self, articles: List[Article]) -> List[Article]:
        """
        Remove duplicate articles from the list.
        
        Returns:
            List of unique articles, preserving the newest version of duplicates
        """
        if not articles:
            return []
            
        logger.info(f"Deduplicating {len(articles)} articles")
        
        unique_articles = []
        seen_urls = set()
        processed_titles = []
        
        # Sort by publication date (newest first) to keep the most recent version
        sorted_articles = sorted(
            articles, 
            key=lambda x: x.published or datetime.min.replace(tzinfo=pytz.UTC), 
            reverse=True
        )
        
        for article in sorted_articles:
            is_duplicate = False
            
            # Check URL-based duplicates first (most reliable)
            normalized_url = self.normalize_url(article.link)
            if normalized_url and normalized_url in seen_urls:
                is_duplicate = True
                logger.debug(f"Duplicate URL found: {article.title[:50]}...")
            elif normalized_url:
                # Check for similar URLs
                for existing_article in unique_articles:
                    if self.are_urls_similar(article.link, existing_article.link):
                        is_duplicate = True
                        logger.debug(f"Similar URL found: {article.title[:50]}...")
                        break
            
            # If not a URL duplicate, check title similarity
            if not is_duplicate:
                for existing_article in unique_articles:
                    similarity = self.calculate_similarity(article.title, existing_article.title)
                    if similarity is not None and similarity >= self.similarity_threshold:
                        is_duplicate = True
                        logger.debug(f"Similar title found (similarity: {similarity:.2f}): {article.title[:50]}...")
                        break
            
            if not is_duplicate:
                unique_articles.append(article)
                if normalized_url:
                    seen_urls.add(normalized_url)
                    
        removed_count = len(articles) - len(unique_articles)
        logger.info(f"Removed {removed_count} duplicate articles, {len(unique_articles)} unique articles remaining")
        
        return unique_articles