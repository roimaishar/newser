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

import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

from ...models.article import Article
from ...models.analysis import HebrewAnalysisResult
from ...state_manager import StateManager

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
    
    def __init__(self, state_manager: StateManager, openai_client: Optional['OpenAIClient'] = None) -> None:
        """Initialize Hebrew analyzer with structured OpenAI client."""
        self.state_manager = state_manager
        if openai_client is None:
            from integrations.openai_client import OpenAIClient
            self.openai_client = OpenAIClient()
        else:
            self.openai_client = openai_client
        
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
        
        # Enhance articles with full content from database
        article_dicts = self._enhance_articles_with_content([article.to_dict() for article in articles])
        llm_logger = self._get_llm_logger()

        if llm_logger:
            try:
                llm_logger.log_raw_articles(article_dicts, f"Thematic Analysis Input ({len(articles)} articles)")
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log raw articles: %s", exc)

        analysis_data = self.openai_client.analyze_thematic(article_dicts, hours=hours)

        if llm_logger:
            try:
                llm_logger.log_parsed_analysis(analysis_data, "thematic_analysis")
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log parsed analysis: %s", exc)

        mobile_headline = analysis_data.get("mobile_headline", "עדכון חדשות")
        story_behind = analysis_data.get("story_behind_story", "")
        connection_threads = analysis_data.get("connection_threads", []) or []
        reader_impact = analysis_data.get("reader_impact", "")
        trend_signal = analysis_data.get("trend_signal", "")

        summary_parts = [mobile_headline]
        if story_behind:
            summary_parts.append(story_behind)
        summary = " • ".join(part for part in summary_parts if part)

        bulletins_lines = [mobile_headline]
        if reader_impact:
            bulletins_lines.append(f"💡 {reader_impact}")
        bulletins = "\n".join(bulletins_lines)

        insights: List[str] = []
        if reader_impact:
            insights.append(reader_impact)
        if trend_signal:
            insights.append(trend_signal)

        return HebrewAnalysisResult(
            has_new_content=bool(connection_threads or insights),
            analysis_type="thematic",
            summary=summary,
            key_topics=connection_threads or ["חדשות"],
            sentiment="ניטרלי",
            insights=insights,
            new_events=[],
            updated_events=[],
            bulletins=bulletins,
            articles_analyzed=len(articles),
            confidence=0.8,
            analysis_timestamp=datetime.now(),
        )
    
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
        
        known_events = self.state_manager.get_known_events()
        known_items = [
            {
                "event_id": event.event_id,
                "baseline": event.baseline,
                "last_update": event.last_update.strftime("%Y-%m-%d %H:%M"),
                "key_facts": event.key_facts,
            }
            for event in known_events
        ]

        # Enhance articles with full content from database
        article_dicts = self._enhance_articles_with_content([article.to_dict() for article in articles])
        llm_logger = self._get_llm_logger()

        if llm_logger:
            try:
                llm_logger.log_raw_articles(
                    article_dicts,
                    f"Novelty Analysis Input ({len(articles)} articles, {len(known_events)} known events)",
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log raw articles: %s", exc)

        analysis_data = self.openai_client.analyze_novelty(article_dicts, known_items, hours=hours)

        if llm_logger:
            try:
                llm_logger.log_parsed_analysis(analysis_data, "novelty_detection")
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log parsed analysis: %s", exc)

        has_new = analysis_data.get("has_new", False)
        items = analysis_data.get("items", []) or []
        bulletins = analysis_data.get("bulletins_he", "")

        new_events = [item for item in items if item.get("status") == "חדש"]
        updated_events = [item for item in items if item.get("status") == "עדכון"]

        self._update_state_from_analysis(new_events + updated_events)

        if not bulletins:
            if items:
                bulletins = (
                    f"זוהו {len(new_events)} אירועים חדשים ו-{len(updated_events)} עדכונים"
                )
            else:
                bulletins = "לא זוהו עדכונים משמעותיים"

        return HebrewAnalysisResult(
            has_new_content=has_new,
            analysis_type="updates",
            summary=bulletins,
            key_topics=self._extract_topics_from_items(items),
            sentiment=self._analyze_sentiment_from_items(items),
            insights=self._extract_insights_from_items(items),
            new_events=new_events,
            updated_events=updated_events,
            bulletins=bulletins,
            articles_analyzed=len(articles),
            confidence=self._calculate_confidence_from_items(items),
            analysis_timestamp=datetime.now(),
        )
    
    def _get_llm_logger(self):
        try:
            from ...llm_logger import get_llm_logger

            return get_llm_logger()
        except Exception:  # noqa: BLE001
            return None
    
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
            self.state_manager.update_known_items(events_to_update, item_type="event")
            logger.info("Updated state with %d events", len(events_to_update))
    
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
    
    def _enhance_articles_with_content(self, article_dicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enhance article dictionaries with full content from database.
        
        Args:
            article_dicts: List of article dictionaries
            
        Returns:
            Enhanced article dictionaries with full_text when available
        """
        try:
            # Get article links for database lookup
            article_links = [article.get('link') for article in article_dicts if article.get('link')]
            
            if not article_links:
                return article_dicts
            
            # Query database for articles with full content
            # Use the database adapter from state manager
            db_adapter = getattr(self.state_manager, 'db', None)
            if not db_adapter:
                logger.warning("No database adapter available for content enhancement")
                return article_dicts
                
            response = db_adapter.client.table('articles').select(
                'link, full_text'
            ).in_('link', article_links).eq('fetch_status', 'fetched').execute()
            
            # Create lookup map
            content_map = {}
            if response.data:
                for row in response.data:
                    if row.get('full_text'):
                        content_map[row['link']] = row['full_text']
            
            # Enhance articles with full content
            enhanced_articles = []
            for article in article_dicts:
                enhanced_article = article.copy()
                link = article.get('link')
                if link and link in content_map:
                    enhanced_article['full_text'] = content_map[link]
                    logger.debug(f"Enhanced article with full content: {link}")
                enhanced_articles.append(enhanced_article)
            
            content_count = len([a for a in enhanced_articles if a.get('full_text')])
            logger.info(f"Enhanced {content_count}/{len(article_dicts)} articles with full content")
            
            return enhanced_articles
            
        except Exception as e:
            logger.warning(f"Failed to enhance articles with content: {e}")
            return article_dicts