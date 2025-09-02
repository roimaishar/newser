#!/usr/bin/env python3
"""
Hebrew analysis pipeline stage.

Integrates Hebrew news analysis into the analysis pipeline architecture.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

from ..pipeline import AnalysisStage
from ...models.article import Article
from .analyzer import HebrewNewsAnalyzer

logger = logging.getLogger(__name__)


class HebrewAnalysisStage(AnalysisStage):
    """Analysis stage for Hebrew content analysis."""
    
    def __init__(self, state_manager, openai_client=None, config: Dict[str, Any] = None):
        """
        Initialize Hebrew analysis stage.
        
        Args:
            state_manager: State manager for persistent storage
            openai_client: OpenAI client (creates new one if None)
            config: Stage configuration
        """
        super().__init__(config)
        self.state_manager = state_manager
        self.openai_client = openai_client
        self._analyzer = None
    
    @property
    def analyzer(self) -> HebrewNewsAnalyzer:
        """Lazy-initialize Hebrew analyzer."""
        if self._analyzer is None:
            self._analyzer = HebrewNewsAnalyzer(
                state_manager=self.state_manager,
                openai_client=self.openai_client
            )
        return self._analyzer
    
    def get_dependencies(self) -> List[str]:
        """Hebrew analysis can depend on deduplication."""
        return ['DeduplicationStage'] if self.config.get('require_dedup', False) else []
    
    def can_process(self, articles: List[Article], context: Dict[str, Any]) -> bool:
        """Check if Hebrew analysis can be performed."""
        # Use deduplicated articles if available, otherwise use original
        source_articles = context.get('deduplicated_articles', articles)
        return len(source_articles) > 0
    
    def process(self, articles: List[Article], context: Dict[str, Any]) -> Dict[str, Any]:
        """Run Hebrew analysis on articles."""
        # Use deduplicated articles if available
        source_articles = context.get('deduplicated_articles', articles)
        
        if not source_articles:
            logger.warning("No articles available for Hebrew analysis")
            return {
                'hebrew_analysis': None,
                'hebrew_analysis_success': False,
                'hebrew_analysis_error': 'No articles to analyze'
            }
        
        # Determine analysis mode from config
        analysis_mode = self.config.get('mode', 'thematic')  # 'thematic' or 'updates'
        hours = context.get('hours_window', self.config.get('hours', 24))
        
        try:
            logger.info(f"Running Hebrew analysis in {analysis_mode} mode on {len(source_articles)} articles")
            
            if analysis_mode == 'updates':
                result = self.analyzer.analyze_articles_with_novelty(source_articles, hours=hours)
            else:
                result = self.analyzer.analyze_articles_thematic(source_articles, hours=hours)
            
            logger.info(f"Hebrew analysis completed successfully (confidence: {result.confidence:.2f})")
            
            return {
                'hebrew_analysis': result,
                'hebrew_analysis_success': True,
                'hebrew_analysis_mode': analysis_mode,
                'hebrew_confidence': result.confidence,
                'hebrew_has_new_content': result.has_new_content,
                'hebrew_articles_analyzed': result.articles_analyzed
            }
            
        except Exception as e:
            logger.error(f"Hebrew analysis failed: {e}", exc_info=True)
            return {
                'hebrew_analysis': None,
                'hebrew_analysis_success': False,
                'hebrew_analysis_error': str(e)
            }


class HebrewValidationStage(AnalysisStage):
    """Validates articles for Hebrew content suitability."""
    
    def get_dependencies(self) -> List[str]:
        """Run after basic validation."""
        return ['ValidationStage']
    
    def process(self, articles: List[Article], context: Dict[str, Any]) -> Dict[str, Any]:
        """Filter articles suitable for Hebrew analysis."""
        source_articles = context.get('valid_articles', articles)
        
        hebrew_suitable = []
        filtered_count = 0
        
        for article in source_articles:
            if self._is_hebrew_suitable(article):
                hebrew_suitable.append(article)
            else:
                filtered_count += 1
        
        logger.info(f"Hebrew validation: {len(hebrew_suitable)}/{len(source_articles)} articles suitable")
        
        return {
            'hebrew_suitable_articles': hebrew_suitable,
            'hebrew_filtered_count': filtered_count,
            'hebrew_suitability_rate': len(hebrew_suitable) / len(source_articles) if source_articles else 0
        }
    
    def _is_hebrew_suitable(self, article: Article) -> bool:
        """Check if article is suitable for Hebrew analysis."""
        # Check if source is Hebrew
        hebrew_sources = {'ynet', 'walla', 'maariv', 'haaretz', 'jpost'}
        if article.source.lower() not in hebrew_sources:
            return False
        
        # Check for Hebrew characters in title
        if not any('\u0590' <= char <= '\u05FF' for char in article.title):
            return False
        
        # Basic content quality checks
        if len(article.title.strip()) < 10:
            return False
        
        return True