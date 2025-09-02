#!/usr/bin/env python3
"""
News command endpoints for fetching, analyzing, and managing news content.
"""

import logging
from argparse import Namespace
from typing import List
from datetime import datetime

from .base import BaseCommand
from core.models.article import Article
from core.analysis.hebrew.analyzer import HebrewNewsAnalyzer
from core.models.metrics import RunRecord
from core.models.analysis import AnalysisRecord

logger = logging.getLogger(__name__)


class NewsCommand(BaseCommand):
    """Handle news fetching, analysis, and distribution operations."""
    
    def execute(self, subcommand: str, args: Namespace) -> int:
        """Execute news subcommand."""
        try:
            if subcommand == "fetch":
                return self.fetch(args)
            elif subcommand == "analyze":
                return self.analyze(args)
            elif subcommand == "summary":
                return self.summary(args)
            else:
                available = ", ".join(self.get_available_subcommands())
                self.logger.error(f"Unknown subcommand '{subcommand}'. Available: {available}")
                return 1
                
        except Exception as e:
            return self.handle_error(e, f"news {subcommand}")
    
    def fetch(self, args: Namespace) -> int:
        """Fetch news articles from RSS feeds."""
        run_id = self.data_manager.generate_run_id()
        
        # Start metrics tracking
        self.metrics.start_run(run_id, f"news fetch --hours {args.hours}")
        
        try:
            # Get components from container
            security_validator = self.security_validator
            
            # Fetch articles (async or sync)
            with self.metrics.time_operation("rss_fetch"):
                if getattr(args, 'async_fetch', False):
                    # Use async RSS fetching
                    from core.async_feed_parser import fetch_feeds_async
                    articles = fetch_feeds_async(
                        hours=args.hours,
                        timeout=self.config.app.feed_timeout,
                        max_concurrent=self.config.app.max_concurrent_feeds
                    )
                else:
                    # Use standard sync RSS fetching
                    feed_parser = self.feed_parser
                    articles = feed_parser.get_recent_articles(hours=args.hours)
                
                self.metrics.record_stat("articles_scraped", len(articles))
            
            if not articles:
                print("No articles found in the specified time range.")
                self.metrics.end_run(success=True)
                return 0
            
            # Security validation
            with self.metrics.time_operation("security_validation"):
                secure_articles = []
                for article in articles:
                    if security_validator.validate_url(article.link):
                        article.title = security_validator.sanitize_title(article.title)
                        article.summary = security_validator.sanitize_summary(article.summary or "")
                        secure_articles.append(article)
                    else:
                        self.logger.warning(f"Blocked article with invalid URL: {article.link}")
                
                articles = secure_articles
            
            # Deduplication
            if not getattr(args, 'no_dedupe', False):
                with self.metrics.time_operation("deduplication"):
                    similarity = getattr(args, 'similarity', 0.8)
                    if similarity is None:
                        similarity = 0.8
                    deduplicator = self.create_deduplicator(similarity_threshold=similarity)
                    articles = deduplicator.deduplicate(articles)
                    self.metrics.record_stat("articles_after_dedup", len(articles))
            else:
                self.metrics.record_stat("articles_after_dedup", len(articles))
            
            # Store articles in database
            stored_count = self.database.store_articles(articles)
            logger.info(f"Stored {stored_count} new articles in database")
            
            # Hebrew analysis (now default unless --no-analysis flag is used)
            hebrew_result = None
            if not getattr(args, 'no_analysis', False) and articles:
                state_manager = self.state_manager
                
                with self.metrics.time_operation("hebrew_analysis"):
                    try:
                        openai_client = self.create_openai_client()
                        hebrew_analyzer = HebrewNewsAnalyzer(state_manager, openai_client)
                        
                        if getattr(args, 'updates_only', False):
                            hebrew_result = hebrew_analyzer.analyze_articles_with_novelty(articles, hours=args.hours)
                        else:
                            hebrew_result = hebrew_analyzer.analyze_articles_thematic(articles, hours=args.hours)
                        
                        self.metrics.record_stat("analysis_completed", True)
                        logger.info("Hebrew analysis completed successfully")
                        
                    except Exception as e:
                        self.logger.warning(f"Hebrew analysis failed (continuing without it): {e}")
                        hebrew_result = None
                        self.metrics.record_stat("analysis_completed", False)
            
            # Smart Notification System (new 3-bucket approach) - default enabled unless --no-slack
            if not getattr(args, 'no_slack', False) and articles:
                with self.metrics.time_operation("smart_notification"):
                    try:
                        from core.notifications.smart_notifier import create_smart_notifier
                        
                        # Create smart notifier
                        smart_notifier = create_smart_notifier(
                            state_manager=self.state_manager,
                            openai_client=self.create_openai_client()
                        )
                        
                        # Convert articles to dicts for processing
                        article_dicts = [article.to_dict() for article in articles]
                        
                        # Get Slack client for sending
                        slack_client = self.create_slack_notifier()
                        
                        # Process with smart notification system
                        decision = smart_notifier.process_news_for_notifications(
                            fresh_articles=article_dicts,
                            slack_client=slack_client,
                            push_client=None  # No push client integration yet
                        )
                        
                        if decision:
                            self.metrics.record_stat("smart_notification_decision", decision.should_notify)
                            self.metrics.record_stat("notification_fresh_count", decision.fresh_articles_count)
                            self.metrics.record_stat("notification_since_last_count", decision.since_last_count)
                            
                            if decision.should_notify:
                                self.logger.info(f"Smart notification approved: {decision.compact_push}")
                            else:
                                self.logger.info("Smart notification system decided to skip notification")
                        else:
                            self.logger.error("Smart notification analysis failed")
                            self.metrics.record_stat("smart_notification_decision", False)
                            
                    except Exception as e:
                        self.logger.error(f"Smart notification failed: {e}")
                        self.metrics.record_stat("smart_notification_decision", False)
                        
                        # Fallback to old notification system
                        try:
                            slack_client = self.create_slack_notifier()
                            article_dicts = [article.to_dict() for article in articles]
                            
                            success = slack_client.send_news_summary(
                                article_dicts, 
                                hebrew_result=hebrew_result
                            )
                            self.metrics.record_stat("slack_sent", success)
                            
                        except Exception as fallback_e:
                            self.logger.error(f"Fallback notification also failed: {fallback_e}")
            
            # Store analysis record if we have results
            if hebrew_result:
                processing_time = sum(getattr(op, 'duration', 0) for op in getattr(self.metrics, '_current_operations', []) 
                                    if "analysis" in getattr(op, 'operation', ''))
                
                analysis_record = AnalysisRecord(
                    run_id=run_id,
                    timestamp=hebrew_result.analysis_timestamp,
                    analysis_type=hebrew_result.analysis_type,
                    hebrew_result=hebrew_result,
                    articles_analyzed=hebrew_result.articles_analyzed,
                    confidence=hebrew_result.confidence,
                    processing_time=processing_time
                )
                self.data_manager.store_analysis_record(analysis_record)
            
            # Store run record with metrics
            processing_time = self.metrics.get_total_time() if hasattr(self.metrics, 'get_total_time') else 0
            run_record = RunRecord(
                run_id=run_id,
                timestamp=datetime.fromtimestamp(self.metrics._run_start_time),
                hours_window=args.hours,
                command_used=f"news fetch --hours {args.hours}",
                articles_scraped=self.metrics._run_stats.get('articles_scraped', len(articles)),
                after_dedup=len(articles),
                success=True,
                processing_time=processing_time
            )
            self.data_manager.store_run_record(run_record)
            
            # Display results (now includes Hebrew analysis if available)
            if hebrew_result:
                self._display_hebrew_analysis(articles, hebrew_result, args)
            else:
                self._display_articles(articles, args.hours)
            
            self.metrics.end_run(success=True)
            return 0
            
        except Exception as e:
            self.metrics.end_run(success=False)
            raise
    
    def analyze(self, args: Namespace) -> int:
        """Analyze recent articles with Hebrew AI analysis."""
        run_id = self.data_manager.generate_run_id()
        
        # Start metrics tracking
        command_str = f"news analyze --hours {args.hours}"
        if getattr(args, 'updates_only', False):
            command_str += " --updates-only"
        if not getattr(args, 'no_slack', False):
            command_str += " --slack"
            
        self.metrics.start_run(run_id, command_str)
        
        try:
            # First fetch articles (reuse fetch logic)
            articles = self._fetch_and_process_articles(args)
            
            # Store articles in database
            stored_count = self.database.store_articles(articles)
            logger.info(f"Stored {stored_count} new articles in database")
            
            if not articles:
                print("No articles found for analysis.")
                self.metrics.end_run(success=True)
                return 0
            
            # Initialize Hebrew analyzer with state manager from container
            state_manager = self.state_manager
            
            with self.metrics.time_operation("hebrew_analysis"):
                try:
                    openai_client = self.create_openai_client()
                    hebrew_analyzer = HebrewNewsAnalyzer(state_manager, openai_client)
                    
                    if getattr(args, 'updates_only', False):
                        hebrew_result = hebrew_analyzer.analyze_articles_with_novelty(articles, hours=args.hours)
                    else:
                        hebrew_result = hebrew_analyzer.analyze_articles_thematic(articles, hours=args.hours)
                    
                    self.metrics.record_stat("analysis_completed", True)
                    
                except Exception as e:
                    self.logger.error(f"Hebrew analysis failed: {e}")
                    hebrew_result = None
                    self.metrics.record_stat("analysis_completed", False)
            
            # Send to Slack (default enabled unless --no-slack)
            if not getattr(args, 'no_slack', False) and hebrew_result:
                with self.metrics.time_operation("slack_notification"):
                    try:
                        slack_client = self.create_slack_notifier()
                        article_dicts = [article.to_dict() for article in articles]
                        
                        success = slack_client.send_news_summary(
                            article_dicts, 
                            hebrew_result=hebrew_result
                        )
                        
                        self.metrics.record_stat("slack_sent", success)
                        if success:
                            self.logger.info("Successfully sent to Slack")
                        else:
                            self.logger.error("Failed to send to Slack")
                            
                    except Exception as e:
                        self.logger.error(f"Slack notification failed: {e}")
                        self.metrics.record_stat("slack_sent", False)
            
            # Store analysis record and final run metrics
            if hebrew_result:
                processing_time = sum(getattr(op, 'duration', 0) for op in getattr(self.metrics, '_current_operations', []) 
                                    if "analysis" in getattr(op, 'operation', ''))
                
                analysis_record = AnalysisRecord(
                    run_id=run_id,
                    timestamp=hebrew_result.analysis_timestamp,
                    analysis_type=hebrew_result.analysis_type,
                    hebrew_result=hebrew_result,
                    articles_analyzed=hebrew_result.articles_analyzed,
                    confidence=hebrew_result.confidence,
                    processing_time=processing_time
                )
                self.data_manager.store_analysis_record(analysis_record)
            
            # Store final run record with complete metrics
            total_time = self.metrics.get_total_time() if hasattr(self.metrics, 'get_total_time') else 0
            run_record = RunRecord(
                run_id=run_id,
                timestamp=datetime.fromtimestamp(self.metrics._run_start_time),
                hours_window=args.hours,
                command_used=command_str,
                articles_scraped=self.metrics._run_stats.get('articles_scraped', len(articles)),
                after_dedup=len(articles),
                success=True,
                processing_time=total_time
            )
            self.data_manager.store_run_record(run_record)
            
            # Display results
            self._display_hebrew_analysis(articles, hebrew_result, args)
            
            self.metrics.end_run(success=True)
            return 0
            
        except Exception as e:
            self.metrics.end_run(success=False)
            raise
    
    def summary(self, args: Namespace) -> int:
        """Show summary of recent news activity."""
        try:
            days = getattr(args, 'days', 3)
            
            # Get recent runs and analyses
            recent_runs = self.data_manager.get_recent_runs(days=days, data_type="articles")
            recent_analyses = self.data_manager.get_recent_runs(days=days, data_type="analyses")
            
            print(f"\n=== News Activity Summary - Last {days} Days ===")
            print(f"📊 Total Runs: {len(recent_runs)}")
            print(f"🧠 Analyses Completed: {len(recent_analyses)}")
            
            if recent_runs:
                total_articles = sum(run.after_dedup for run in recent_runs)
                avg_articles = total_articles / len(recent_runs)
                print(f"📰 Total Articles Processed: {total_articles}")
                print(f"📈 Average Articles per Run: {avg_articles:.1f}")
                
                # Show recent runs
                print(f"\n=== Recent Runs ===")
                for run in recent_runs[:5]:  # Show last 5
                    timestamp = run.timestamp.strftime("%m-%d %H:%M")
                    status = "✅" if run.success else "❌"
                    print(f"{status} {timestamp} | {run.after_dedup} articles | {run.hours_window}h window")
            
            if recent_analyses:
                print(f"\n=== Recent Analyses ===")
                for analysis in recent_analyses[:5]:  # Show last 5
                    timestamp = analysis.timestamp.strftime("%m-%d %H:%M")
                    conf = f"{analysis.confidence:.1f}" if analysis.confidence else "N/A"
                    print(f"🧠 {timestamp} | {analysis.analysis_type} | confidence: {conf}")
            
            return 0
            
        except Exception as e:
            return self.handle_error(e, "news summary")
    
    def _fetch_and_process_articles(self, args: Namespace) -> List[Article]:
        """Helper method to fetch and process articles."""
        security_validator = self.security_validator
        
        # Fetch articles (async or sync)
        with self.metrics.time_operation("rss_fetch"):
            if getattr(args, 'async_fetch', False):
                # Use async RSS fetching
                from core.async_feed_parser import fetch_feeds_async
                articles = fetch_feeds_async(
                    hours=args.hours,
                    timeout=self.config.app.feed_timeout,
                    max_concurrent=self.config.app.max_concurrent_feeds
                )
            else:
                # Use standard sync RSS fetching
                feed_parser = self.feed_parser
                articles = feed_parser.get_recent_articles(hours=args.hours)
            
            self.metrics.record_stat("articles_scraped", len(articles))
        
        if not articles:
            return []
        
        # Security validation
        with self.metrics.time_operation("security_validation"):
            secure_articles = []
            for article in articles:
                if security_validator.validate_url(article.link):
                    article.title = security_validator.sanitize_title(article.title)
                    article.summary = security_validator.sanitize_summary(article.summary or "")
                    secure_articles.append(article)
                else:
                    self.logger.warning(f"Blocked article with invalid URL: {article.link}")
            
            articles = secure_articles
            self.logger.info(f"After security validation: {len(articles)} articles")
        
        # Deduplication
        if not getattr(args, 'no_dedupe', False):
            with self.metrics.time_operation("deduplication"):
                similarity = getattr(args, 'similarity', 0.8)
                if similarity is None:
                    similarity = 0.8
                deduplicator = self.create_deduplicator(similarity_threshold=similarity)
                articles = deduplicator.deduplicate(articles)
                self.metrics.record_stat("articles_after_dedup", len(articles))
                self.logger.info(f"After deduplication: {len(articles)} articles")
        else:
            self.metrics.record_stat("articles_after_dedup", len(articles))
        
        return articles
    
    def _display_articles(self, articles: List[Article], hours: int):
        """Display articles in a formatted way."""
        print(f"\n=== Israeli News Headlines - Last {hours} Hours ===")
        print(f"Generated at: {self.metrics._run_start_time}")
        print(f"Total articles: {len(articles)}\n")
        
        if articles:
            for article in articles:
                timestamp = ""
                if article.published:
                    timestamp = article.published.strftime("%Y-%m-%d %H:%M")
                
                print(f"[{timestamp}] [{article.source.upper()}] {article.title}")
                print(f"    {article.link}\n")
        else:
            print("No articles found in the specified time range.")
    
    def _display_hebrew_analysis(self, articles: List[Article], hebrew_result, args: Namespace):
        """Display Hebrew analysis results."""
        if not hebrew_result:
            print("Analysis failed - no results to display.")
            return
        
        # Display Hebrew analysis
        mode_name = "עדכונים בלבד" if getattr(args, 'updates_only', False) else "ניתוח כללי"
        print(f"\n=== חדשות ישראל - {args.hours} שעות אחרונות ===")
        print(f"🕐 נוצר ב: {hebrew_result.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📰 כתבות: {len(articles)} | 🎯 מצב: {mode_name}")
        
        # Show Hebrew analysis
        from core.formatting import format_hebrew_analysis
        print(format_hebrew_analysis(hebrew_result))
        
        # In updates-only mode, don't show all articles if no new content
        if getattr(args, 'updates_only', False) and not hebrew_result.has_new_content:
            print("📝 אין עדכונים חדשים לתצוגה")
        elif not getattr(args, 'updates_only', False) or hebrew_result.has_new_content:
            # Show article list
            if articles:
                print(f"\n=== רשימת כתבות ===")
                for article in articles:
                    timestamp = ""
                    if article.published:
                        timestamp = article.published.strftime("%Y-%m-%d %H:%M")
                    
                    print(f"[{timestamp}] [{article.source.upper()}] {article.title}")
                    print(f"    {article.link}\n")
            else:
                print("לא נמצאו כתבות בטווח הזמן המבוקש")