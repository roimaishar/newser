#!/usr/bin/env python3
"""
Analysis pipeline orchestration.

Provides framework for running multiple analysis stages on news articles
with pluggable analyzers and processing steps.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Type
from datetime import datetime
import logging

from ..models.article import Article
from ..models.analysis import HebrewAnalysisResult

logger = logging.getLogger(__name__)


class AnalysisStage(ABC):
    """Abstract base class for analysis pipeline stages."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize analysis stage.
        
        Args:
            config: Stage-specific configuration
        """
        self.config = config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def process(self, articles: List[Article], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process articles through this analysis stage.
        
        Args:
            articles: List of articles to analyze
            context: Shared context from previous stages
            
        Returns:
            Results dictionary to be merged into context
        """
        pass
    
    def can_process(self, articles: List[Article], context: Dict[str, Any]) -> bool:
        """
        Check if this stage can process the given articles.
        
        Args:
            articles: Articles to check
            context: Current context
            
        Returns:
            True if stage can process, False otherwise
        """
        return True
    
    def get_dependencies(self) -> List[str]:
        """
        Get list of stage names this stage depends on.
        
        Returns:
            List of stage names that must run before this one
        """
        return []


class AnalysisPipeline:
    """
    Analysis pipeline that orchestrates multiple analysis stages.
    
    Supports dependency resolution, error handling, and parallel execution.
    """
    
    def __init__(self):
        """Initialize empty pipeline."""
        self.stages: Dict[str, AnalysisStage] = {}
        self.stage_order: List[str] = []
    
    def add_stage(self, stage: AnalysisStage, name: Optional[str] = None) -> 'AnalysisPipeline':
        """
        Add an analysis stage to the pipeline.
        
        Args:
            stage: Analysis stage to add
            name: Optional custom name (uses class name if not provided)
            
        Returns:
            Self for method chaining
        """
        stage_name = name or stage.__class__.__name__
        self.stages[stage_name] = stage
        
        # Rebuild stage order with dependency resolution
        self._resolve_stage_order()
        
        logger.info(f"Added analysis stage: {stage_name}")
        return self
    
    def remove_stage(self, name: str) -> 'AnalysisPipeline':
        """
        Remove a stage from the pipeline.
        
        Args:
            name: Name of stage to remove
            
        Returns:
            Self for method chaining
        """
        if name in self.stages:
            del self.stages[name]
            self._resolve_stage_order()
            logger.info(f"Removed analysis stage: {name}")
        
        return self
    
    def run(self, articles: List[Article], initial_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run the analysis pipeline on articles.
        
        Args:
            articles: Articles to analyze
            initial_context: Initial context for pipeline
            
        Returns:
            Final analysis results
        """
        if not articles:
            logger.warning("No articles provided to analysis pipeline")
            return {}
        
        context = initial_context or {}
        context['pipeline_start_time'] = datetime.now()
        context['articles_count'] = len(articles)
        
        logger.info(f"Starting analysis pipeline with {len(articles)} articles")
        
        for stage_name in self.stage_order:
            stage = self.stages[stage_name]
            
            if not stage.can_process(articles, context):
                logger.info(f"Skipping stage {stage_name} - cannot process current articles")
                continue
            
            try:
                logger.debug(f"Running analysis stage: {stage_name}")
                stage_start = datetime.now()
                
                stage_results = stage.process(articles, context)
                
                # Merge results into context
                if stage_results:
                    context.update(stage_results)
                
                # Track timing
                stage_duration = (datetime.now() - stage_start).total_seconds()
                context[f'{stage_name}_duration'] = stage_duration
                
                logger.info(f"Completed stage {stage_name} in {stage_duration:.2f}s")
                
            except Exception as e:
                logger.error(f"Stage {stage_name} failed: {e}", exc_info=True)
                context[f'{stage_name}_error'] = str(e)
                
                # Continue with other stages unless this is a critical failure
                if self._is_critical_stage(stage_name):
                    raise
        
        # Add pipeline completion metadata
        pipeline_duration = (datetime.now() - context['pipeline_start_time']).total_seconds()
        context['pipeline_duration'] = pipeline_duration
        context['pipeline_completed'] = True
        
        logger.info(f"Analysis pipeline completed in {pipeline_duration:.2f}s")
        return context
    
    def get_stage_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all stages in the pipeline.
        
        Returns:
            Dictionary with stage information
        """
        info = {}
        for name, stage in self.stages.items():
            info[name] = {
                'class': stage.__class__.__name__,
                'dependencies': stage.get_dependencies(),
                'config': stage.config,
                'order': self.stage_order.index(name) if name in self.stage_order else -1
            }
        
        return info
    
    def _resolve_stage_order(self):
        """Resolve stage execution order based on dependencies."""
        # Simple topological sort
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(stage_name: str):
            if stage_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {stage_name}")
            
            if stage_name in visited:
                return
            
            temp_visited.add(stage_name)
            
            # Visit dependencies first
            stage = self.stages.get(stage_name)
            if stage:
                for dep in stage.get_dependencies():
                    if dep in self.stages:
                        visit(dep)
                    else:
                        logger.warning(f"Dependency {dep} not found for stage {stage_name}")
            
            temp_visited.remove(stage_name)
            visited.add(stage_name)
            order.append(stage_name)
        
        # Visit all stages
        for stage_name in self.stages:
            if stage_name not in visited:
                visit(stage_name)
        
        self.stage_order = order
        logger.debug(f"Resolved stage order: {self.stage_order}")
    
    def _is_critical_stage(self, stage_name: str) -> bool:
        """Check if a stage is critical (failure should stop pipeline)."""
        # For now, no stages are critical - pipeline continues on errors
        # This can be made configurable per stage in the future
        return False


# Pre-built stage implementations

class ValidationStage(AnalysisStage):
    """Validates articles before analysis."""
    
    def process(self, articles: List[Article], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate articles and filter invalid ones."""
        valid_articles = []
        validation_errors = []
        
        for article in articles:
            errors = self._validate_article(article)
            if errors:
                validation_errors.extend(errors)
            else:
                valid_articles.append(article)
        
        logger.info(f"Validated {len(valid_articles)}/{len(articles)} articles")
        
        return {
            'valid_articles': valid_articles,
            'validation_errors': validation_errors,
            'articles_validated': len(articles),
            'articles_valid': len(valid_articles)
        }
    
    def _validate_article(self, article: Article) -> List[str]:
        """Validate a single article."""
        errors = []
        
        if not article.title or not article.title.strip():
            errors.append("Missing title")
        
        if not article.link or not article.link.strip():
            errors.append("Missing link")
        
        if not article.source or not article.source.strip():
            errors.append("Missing source")
        
        return errors


class DeduplicationStage(AnalysisStage):
    """Removes duplicate articles."""
    
    def get_dependencies(self) -> List[str]:
        """Depends on validation."""
        return ['ValidationStage']
    
    def process(self, articles: List[Article], context: Dict[str, Any]) -> Dict[str, Any]:
        """Remove duplicate articles."""
        # Use validated articles if available
        source_articles = context.get('valid_articles', articles)
        
        # Simple deduplication by link
        seen_links = set()
        deduplicated = []
        
        for article in source_articles:
            if article.link not in seen_links:
                seen_links.add(article.link)
                deduplicated.append(article)
        
        duplicates_removed = len(source_articles) - len(deduplicated)
        logger.info(f"Removed {duplicates_removed} duplicate articles")
        
        return {
            'deduplicated_articles': deduplicated,
            'duplicates_removed': duplicates_removed,
            'articles_after_dedup': len(deduplicated)
        }