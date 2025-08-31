#!/usr/bin/env python3
"""
Formatting utilities for news display and analysis results.

Extracted from main.py to eliminate circular imports and improve modularity.
"""

from datetime import datetime
from typing import List
from core.feed_parser import Article
from core.hebrew_analyzer import HebrewAnalysisResult


def format_article(article: Article) -> str:
    """Format a single article for display."""
    timestamp = ""
    if article.published:
        timestamp = article.published.strftime("%Y-%m-%d %H:%M")
    
    return f"[{timestamp}] [{article.source.upper()}] {article.title}\n    {article.link}\n"


def articles_to_dict(articles: List[Article]) -> List[dict]:
    """Convert Article objects to dictionaries for API integration."""
    return [article.to_dict() for article in articles]


def format_hebrew_analysis(result: HebrewAnalysisResult) -> str:
    """Format Hebrew analysis results for display."""
    if not result.has_new_content:
        return f"\n=== ניתוח בעברית ===\n{result.summary}\n"
    
    lines = [
        "\n=== ניתוח בעברית ===",
        f"📊 סוג ניתוח: {result.analysis_type}",
        f"📰 כתבות שנותחו: {result.articles_analyzed}",
        f"🎯 רמת ודאות: {result.confidence:.1f}",
        "",
        "💡 סיכום:",
        f"  {result.summary}",
    ]
    
    if result.key_topics:
        lines.extend([
            "",
            "🏷️ נושאים עיקריים:",
            f"  {', '.join(result.key_topics)}"
        ])
    
    if result.sentiment != "ניטרלי":
        lines.extend([
            "",
            f"😊 סנטימנט: {result.sentiment}"
        ])
    
    if result.insights:
        lines.extend([
            "",
            "🔍 תובנות:"
        ])
        for insight in result.insights:
            lines.append(f"  • {insight}")
    
    if result.bulletins:
        lines.extend([
            "",
            "📢 עדכונים:",
            f"  {result.bulletins}"
        ])
    
    if result.new_events:
        lines.extend([
            "",
            f"🆕 אירועים חדשים ({len(result.new_events)}):"
        ])
        for event in result.new_events[:3]:  # Show top 3
            lines.append(f"  • {event.get('lede_he', 'אירוע חדש')}")
    
    if result.updated_events:
        lines.extend([
            "",
            f"🔄 עדכונים לאירועים ({len(result.updated_events)}):"
        ])
        for event in result.updated_events[:3]:  # Show top 3
            lines.append(f"  • {event.get('lede_he', 'עדכון')}")
    
    lines.append("=" * 50)
    return "\n".join(lines)