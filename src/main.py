#!/usr/bin/env python3
"""
News Aggregator - Main Entry Point

Fetches and deduplicates news from Israeli news sources (Ynet, Walla).
"""

import logging
import sys
from datetime import datetime
from typing import List
import argparse

# Load environment variables from .env file
from core.env_loader import load_env_file, get_env_var
from core.feed_parser import FeedParser, Article
from core.deduplication import Deduplicator
from core.security import SecurityValidator
from core.state_manager import StateManager
from core.hebrew_analyzer import HebrewNewsAnalyzer, HebrewAnalysisResult
from integrations.openai_client import OpenAIClient, NewsAnalysis
from integrations.slack_notifier import SlackNotifier

def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

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

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Israeli News Aggregator')
    parser.add_argument('--hours', type=int, default=24, 
                       help='Hours to look back for articles (default: 24)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--no-dedupe', action='store_true',
                       help='Skip deduplication step')
    parser.add_argument('--similarity', type=float, default=0.8,
                       help='Similarity threshold for deduplication (0-1, default: 0.8)')
    parser.add_argument('--slack', action='store_true',
                       help='Send results to Slack (requires SLACK_WEBHOOK_URL)')
    parser.add_argument('--test-integrations', action='store_true',
                       help='Test OpenAI and Slack integrations')
    
    # Hebrew analysis options
    parser.add_argument('--hebrew', action='store_true',
                       help='Enable Hebrew-first analysis with novelty detection')
    parser.add_argument('--updates-only', action='store_true',
                       help='Show only new/updated items (requires --hebrew)')
    parser.add_argument('--state-file', type=str, default='data/known_items.json',
                       help='Path to state file for known events (default: data/known_items.json)')
    parser.add_argument('--reset-state', action='store_true',
                       help='Reset known events state (requires --hebrew)')
    parser.add_argument('--state-stats', action='store_true',
                       help='Show state statistics and exit')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Test integrations if requested
        if args.test_integrations:
            logger.info("Testing integrations...")
            
            # Test OpenAI
            try:
                openai_client = OpenAIClient()
                if openai_client.test_connection():
                    print("✅ OpenAI API connection successful")
                else:
                    print("❌ OpenAI API connection failed")
            except Exception as e:
                print(f"❌ OpenAI setup failed: {e}")
            
            # Test Slack
            try:
                slack_client = SlackNotifier()
                if slack_client.test_connection():
                    print("✅ Slack webhook connection successful")
                else:
                    print("❌ Slack webhook connection failed")
            except Exception as e:
                print(f"❌ Slack setup failed: {e}")
            
            return 0
        
        # State management for Hebrew mode
        if args.hebrew or args.state_stats or args.reset_state:
            state_manager = StateManager(state_file=args.state_file)
            
            # Show state statistics and exit
            if args.state_stats:
                stats = state_manager.get_stats()
                print("\n=== State Statistics ===")
                print(f"📊 Total known events: {stats['total_events']}")
                print(f"🕐 Last update: {stats['last_update']}")
                print(f"📅 Oldest event: {stats['oldest_event_date'] or 'None'}")
                print(f"🔄 Newest update: {stats['newest_update_date'] or 'None'}")
                print(f"🗑️ Cleanup threshold: {stats['cleanup_threshold_days']} days")
                print(f"📄 State file size: {stats['state_file_size_bytes']} bytes")
                return 0
            
            # Reset state if requested
            if args.reset_state:
                state_manager.reset_state()
                print("✅ State reset to empty")
                return 0
        
        logger.info("Starting news aggregation...")
        
        # Initialize components
        security_validator = SecurityValidator()
        feed_parser = FeedParser()
        
        # Initialize Hebrew analyzer if needed
        hebrew_analyzer = None
        if args.hebrew:
            try:
                openai_client = OpenAIClient()
                hebrew_analyzer = HebrewNewsAnalyzer(state_manager, openai_client)
                logger.info("Hebrew analyzer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Hebrew analyzer: {e}")
                if args.updates_only:
                    print("❌ Hebrew mode required for --updates-only")
                    return 1
        
        # Get recent articles
        logger.info(f"Fetching articles from last {args.hours} hours")
        articles = feed_parser.get_recent_articles(hours=args.hours)
        
        if not articles:
            logger.warning("No articles found")
            return 1
            
        logger.info(f"Found {len(articles)} articles")
        
        # Apply security validation to articles
        secure_articles = []
        for article in articles:
            if security_validator.validate_url(article.link):
                article.title = security_validator.sanitize_title(article.title)
                article.summary = security_validator.sanitize_summary(article.summary or "")
                secure_articles.append(article)
            else:
                logger.warning(f"Blocked article with invalid URL: {article.link}")
        
        articles = secure_articles
        logger.info(f"After security validation: {len(articles)} articles")
        
        # Deduplicate if requested
        if not args.no_dedupe:
            deduplicator = Deduplicator(similarity_threshold=args.similarity)
            articles = deduplicator.deduplicate(articles)
            logger.info(f"After deduplication: {len(articles)} articles")
        
        # Hebrew Analysis
        hebrew_result = None
        
        if args.hebrew and hebrew_analyzer:
            try:
                logger.info("Running Hebrew analysis...")
                
                if args.updates_only:
                    # Novelty-aware analysis (only new/updated content)
                    hebrew_result = hebrew_analyzer.analyze_articles_with_novelty(articles, hours=args.hours)
                    logger.info("Hebrew novelty analysis completed")
                else:
                    # Thematic analysis (general overview)
                    hebrew_result = hebrew_analyzer.analyze_articles_thematic(articles, hours=args.hours)
                    logger.info("Hebrew thematic analysis completed")
                    
            except Exception as e:
                logger.error(f"Hebrew analysis failed: {e}")
        
        
        # Send to Slack if requested
        if args.slack:
            try:
                logger.info("Sending to Slack...")
                slack_client = SlackNotifier()
                article_dicts = articles_to_dict(articles)
                
                analysis_dict = None
                
                # Send with Hebrew result
                success = slack_client.send_news_summary(
                    article_dicts, 
                    analysis_dict, 
                    hebrew_result=hebrew_result
                )
                if success:
                    logger.info("Successfully sent to Slack")
                else:
                    logger.error("Failed to send to Slack")
            except Exception as e:
                logger.error(f"Slack notification failed: {e}")
        
        # Display results based on mode
        if args.hebrew and hebrew_result:
            # Hebrew mode output
            mode_name = "עדכונים בלבד" if args.updates_only else "ניתוח כללי"
            print(f"\n=== חדשות ישראל - {args.hours} שעות אחרונות ===")
            print(f"🕐 נוצר ב: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📰 כתבות: {len(articles)} | 🎯 מצב: {mode_name}")
            
            # Show Hebrew analysis
            print(format_hebrew_analysis(hebrew_result))
            
            # In updates-only mode, don't show all articles if no new content
            if args.updates_only and not hebrew_result.has_new_content:
                print("📝 אין עדכונים חדשים לתצוגה")
            elif not args.updates_only or hebrew_result.has_new_content:
                # Show article list
                if articles:
                    print(f"\n=== רשימת כתבות ===")
                    for article in articles:
                        print(format_article(article))
                else:
                    print("לא נמצאו כתבות בטווח הזמן המבוקש")
        
        elif not args.hebrew:
            # Basic output mode (no Hebrew analysis)
            print(f"\n=== Israeli News Headlines - Last {args.hours} Hours ===")
            print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Total articles: {len(articles)}\n")
            
            if articles:
                for article in articles:
                    print(format_article(article))
            else:
                print("No articles found in the specified time range.")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=args.verbose)
        return 1

if __name__ == "__main__":
    sys.exit(main())