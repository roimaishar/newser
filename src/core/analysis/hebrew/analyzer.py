#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebrew News Analyzer with Novelty Detection.

High-level orchestrator that combines:
- Article parsing from RSS feeds
- State management for known events
- Hebrew-first AI analysis with OpenAI
- Novelty detection and update filtering
"""

import json
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ...models.article import Article
from ...models.analysis import HebrewAnalysisResult
from ...state_manager import StateManager, KnownItem
from .prompts import NewsAnalysisPrompts
from ...json_validator import validate_hebrew_analysis

logger = logging.getLogger(__name__)


class HebrewNewsAnalyzer:
    """
    High-level Hebrew news analyzer with state management and novelty detection.
    
    Orchestrates the entire Hebrew analysis pipeline:
    1. Load known events from state
    2. Run appropriate AI analysis (thematic or updates)
    3. Update state with new/updated events
    4. Return structured Hebrew results
    """
    
    def __init__(self, 
                 state_manager: StateManager,
                 openai_client = None):
        """
        Initialize Hebrew analyzer.
        
        Args:
            state_manager: State manager for persistent storage
            openai_client: OpenAI client (creates new one if None)
        """
        self.state_manager = state_manager
        self.openai_client = openai_client
        
        if self.openai_client is None:
            # Import here to avoid circular imports
            from integrations.openai_client import OpenAIClient
            self.openai_client = OpenAIClient()
        
    def analyze_articles_thematic(self, articles: List[Article], hours: int = 24) -> HebrewAnalysisResult:
        """
        Perform thematic Hebrew analysis without novelty detection.
        
        Good for: General overviews, daily summaries, getting started.
        
        Args:
            articles: List of articles to analyze
            hours: Time window for context
            
        Returns:
            HebrewAnalysisResult with thematic analysis
        """
        if not articles:
            return HebrewAnalysisResult(
                has_new_content=False,
                analysis_type="thematic",
                summary="לא נמצאו כתבות לניתוח",
                key_topics=[],
                sentiment="ניטרלי",
                insights=[],
                new_events=[],
                updated_events=[],
                bulletins="",
                articles_analyzed=0,
                confidence=1.0,
                analysis_timestamp=datetime.now()
            )
        
        try:
            # Convert articles to dicts for prompt processing
            article_dicts = [article.to_dict() for article in articles]
            
            # Generate Hebrew analysis prompt
            prompt = NewsAnalysisPrompts.get_analysis_prompt(article_dicts, hours=hours)
            
            # Make API request
            data = {
                "model": self.openai_client.model,
                "messages": [
                    {"role": "system", "content": NewsAnalysisPrompts.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.openai_client.max_tokens,
                "temperature": self.openai_client.temperature
            }
            
            response = self.openai_client._make_api_request("chat/completions", data)
            content = response['choices'][0]['message']['content'].strip()
            
            # Parse Hebrew JSON response
            analysis_data = self._parse_ai_response(content)
            
            # Extract journalism-focused analysis
            mobile_headline = analysis_data.get('mobile_headline', 'עדכון חדשות')
            story_behind = analysis_data.get('story_behind_story', 'ניתוח הושלם') 
            connection_threads = analysis_data.get('connection_threads', [])
            reader_impact = analysis_data.get('reader_impact', '')
            trend_signal = analysis_data.get('trend_signal', '')
            
            # Create mobile-first summary combining headline and story
            summary = f"{mobile_headline}"
            if story_behind:
                summary += f" • {story_behind}"
            
            # Build bulletins for mobile display
            bulletins = mobile_headline
            if reader_impact:
                bulletins += f"\n💡 {reader_impact}"
            
            return HebrewAnalysisResult(
                has_new_content=True,
                analysis_type="thematic",
                summary=summary,
                key_topics=connection_threads,  # Use connection threads as topics
                sentiment='ניטרלי',  # Focus on analysis, not sentiment
                insights=[reader_impact, trend_signal] if reader_impact or trend_signal else [],
                new_events=[],
                updated_events=[],
                bulletins=bulletins,
                articles_analyzed=len(articles),
                confidence=0.8,
                analysis_timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Hebrew thematic analysis failed: {e}")
            # Re-raise the exception instead of returning fallback
            raise RuntimeError(f"LLM thematic analysis failed: {str(e)}") from e
    
    def analyze_articles_with_novelty(self, articles: List[Article], hours: int = 12) -> HebrewAnalysisResult:
        """
        Perform Hebrew analysis with novelty detection against known events.
        
        Good for: Incremental updates, filtering out noise, focusing on new info.
        
        Args:
            articles: List of articles to analyze
            hours: Time window for context
            
        Returns:
            HebrewAnalysisResult with novelty-filtered analysis
        """
        if not articles:
            return HebrewAnalysisResult(
                has_new_content=False,
                analysis_type="updates",
                summary="לא נמצאו כתבות חדשות לניתוח",
                key_topics=[],
                sentiment="ניטרלי",
                insights=[],
                new_events=[],
                updated_events=[],
                bulletins="",
                articles_analyzed=0,
                confidence=1.0,
                analysis_timestamp=datetime.now()
            )
        
        try:
            # Get known events for comparison
            known_events = self.state_manager.get_known_events()
            known_items_dicts = [
                {
                    "event_id": event.event_id,
                    "baseline": event.baseline,
                    "last_update": event.last_update.strftime("%Y-%m-%d %H:%M"),
                    "key_facts": event.key_facts
                }
                for event in known_events
            ]
            
            # Convert articles to dicts
            article_dicts = [article.to_dict() for article in articles]
            
            # Generate novelty detection prompt
            prompt = NewsAnalysisPrompts.get_update_prompt(
                article_dicts, known_items_dicts, hours=hours
            )
            
            # Make API request
            data = {
                "model": self.openai_client.model,
                "messages": [
                    {"role": "system", "content": NewsAnalysisPrompts.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.openai_client.max_tokens * 2,  # Longer prompt needs more tokens
                "temperature": self.openai_client.temperature
            }
            
            response = self.openai_client._make_api_request("chat/completions", data)
            content = response['choices'][0]['message']['content'].strip()
            
            # Parse and validate novelty analysis response
            analysis_data = validate_hebrew_analysis(content, "updates")
            
            # Extract results
            has_new = analysis_data.get('has_new', False)
            items = analysis_data.get('new_or_updated_items', analysis_data.get('items', []))
            bulletins = analysis_data.get('bulletins_he', '')
            
            # Separate new vs updated events
            new_events = [item for item in items if item.get('status') == 'חדש']
            updated_events = [item for item in items if item.get('status') == 'עדכון']
            
            # Update state with new/updated events
            self._update_state_from_analysis(new_events + updated_events)
            
            # Create summary from bulletins or items
            summary = bulletins
            if not summary and items:
                summary = f"זוהו {len(new_events)} אירועים חדשים ו-{len(updated_events)} עדכונים"
            elif not summary:
                summary = "לא זוהו עדכונים משמעותיים"
            
            return HebrewAnalysisResult(
                has_new_content=has_new,
                analysis_type="updates",
                summary=summary,
                key_topics=self._extract_topics_from_items(items),
                sentiment=self._analyze_sentiment_from_items(items),
                insights=self._extract_insights_from_items(items),
                new_events=new_events,
                updated_events=updated_events,
                bulletins=bulletins,
                articles_analyzed=len(articles),
                confidence=self._calculate_confidence_from_items(items),
                analysis_timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Hebrew novelty analysis failed: {e}")
            # Re-raise the exception instead of returning fallback
            raise RuntimeError(f"LLM novelty analysis failed: {str(e)}") from e
    
    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """Parse AI response, handling common JSON formatting issues."""
        try:
            # Clean up markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Raw response: {content}")
            # Re-raise the exception instead of returning fallback
            raise RuntimeError(f"LLM returned invalid JSON: {str(e)}") from e
    
    def _update_state_from_analysis(self, items: List[Dict[str, Any]]) -> None:
        """Update state manager with new/updated events from analysis."""
        events_to_update = []
        
        for item in items:
            event_id = item.get('event_id', '')
            if not event_id:
                continue
                
            # Create hash for database storage
            event_hash = hashlib.sha256(event_id.encode('utf-8')).hexdigest()
            events_to_update.append(event_hash)
        
        if events_to_update:
            self.state_manager.update_known_items(events_to_update, item_type='event')
            logger.info(f"Updated state with {len(events_to_update)} events")
    
    def _extract_topics_from_items(self, items: List[Dict[str, Any]]) -> List[str]:
        """Extract key topics from analysis items."""
        topics = set()
        for item in items:
            lede = item.get('lede_he', '')
            # Simple keyword extraction from Hebrew ledes
            if 'ממשלה' in lede or 'פוליטיקה' in lede:
                topics.add('פוליטיקה')
            if 'ביטחון' in lede or 'צבא' in lede or 'חמאס' in lede:
                topics.add('ביטחון')
            if 'משא ומתן' in lede or 'הסכם' in lede:
                topics.add('דיפלומטיה')
            if 'כלכלה' in lede or 'תקציב' in lede:
                topics.add('כלכלה')
        
        return list(topics) if topics else ['חדשות']
    
    def _analyze_sentiment_from_items(self, items: List[Dict[str, Any]]) -> str:
        """Analyze overall sentiment from analysis items."""
        if not items:
            return 'ניטרלי'
        
        # Simple heuristic based on keywords in Hebrew content
        negative_keywords = ['משבר', 'תקיפה', 'מלחמה', 'נפגעים', 'קונפליקט']
        positive_keywords = ['הסכם', 'שלום', 'הישג', 'פתרון', 'שיתוף פעולה']
        
        negative_count = 0
        positive_count = 0
        
        for item in items:
            text = item.get('lede_he', '') + ' ' + item.get('significance_he', '')
            text_lower = text.lower()
            
            for keyword in negative_keywords:
                if keyword in text_lower:
                    negative_count += 1
            
            for keyword in positive_keywords:
                if keyword in text_lower:
                    positive_count += 1
        
        if positive_count > negative_count:
            return 'חיובי'
        elif negative_count > positive_count:
            return 'שלילי'
        else:
            return 'ניטרלי'
    
    def _extract_insights_from_items(self, items: List[Dict[str, Any]]) -> List[str]:
        """Extract key insights from analysis items."""
        insights = []
        
        if not items:
            return ['לא זוהו עדכונים משמעותיים']
        
        new_count = sum(1 for item in items if item.get('status') == 'חדש')
        update_count = sum(1 for item in items if item.get('status') == 'עדכון')
        
        if new_count > 0:
            insights.append(f'{new_count} אירועים חדשים זוהו')
        
        if update_count > 0:
            insights.append(f'{update_count} עדכונים לאירועים קיימים')
        
        # Add significance-based insights
        high_significance_items = [
            item for item in items 
            if item.get('confidence', 0) > 0.8
        ]
        
        if high_significance_items:
            insights.append(f'{len(high_significance_items)} דיווחים בעלי ודאות גבוהה')
        
        return insights or ['ניתוח הושלם ללא תובנות מיוחדות']
    
    def _calculate_confidence_from_items(self, items: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence from analysis items."""
        if not items:
            return 0.0
        
        confidences = [item.get('confidence', 0.5) for item in items]
        return sum(confidences) / len(confidences)