#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Interaction Logger

Logs all LLM interactions and notification outputs to a clear file for debugging.
Includes raw data, prompts, responses, and final notification content.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMLogger:
    """Logs LLM interactions and notification outputs to a clear debug file."""
    
    def __init__(self, log_file_path: str = "llm_debug.log"):
        """Initialize the LLM logger.
        
        Args:
            log_file_path: Path to the debug log file (relative to project root)
        """
        # Get project root (assuming we're in src/core/)
        project_root = Path(__file__).parent.parent.parent
        self.log_file_path = project_root / log_file_path
        
        # Clear previous run (overwrite as requested)
        self._clear_log()
        
    def _clear_log(self):
        """Clear the log file for a fresh start."""
        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write(f"=== LLM DEBUG LOG - {datetime.now().isoformat()} ===\n\n")
        except Exception as e:
            logger.error(f"Failed to clear LLM log file: {e}")
    
    def _write_section(self, title: str, content: str):
        """Write a section to the log file."""
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'=' * 80}\n")
                f.write(f"{title}\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"{content}\n")
        except Exception as e:
            logger.error(f"Failed to write to LLM log file: {e}")
    
    def log_raw_articles(self, articles: List[Dict[str, Any]], context: str = "Raw Articles"):
        """Log the raw articles data before processing."""
        content = f"Timestamp: {datetime.now().isoformat()}\n"
        content += f"Count: {len(articles)} articles\n\n"
        
        for i, article in enumerate(articles, 1):
            content += f"Article {i}:\n"
            content += f"  Title: {article.get('title', 'N/A')}\n"
            content += f"  Source: {article.get('source', 'N/A')}\n"
            content += f"  Published: {article.get('published', 'N/A')}\n"
            content += f"  Link: {article.get('link', 'N/A')}\n"
            if article.get('summary'):
                content += f"  Summary: {article.get('summary')[:200]}{'...' if len(article.get('summary', '')) > 200 else ''}\n"
            content += "\n"
        
        self._write_section(f"📰 {context}", content)
    
    def log_llm_interaction(self, 
                          system_prompt: str, 
                          user_prompt: str, 
                          response: str, 
                          token_usage: Dict[str, int],
                          analysis_type: str = "Unknown"):
        """Log complete LLM interaction."""
        content = f"Timestamp: {datetime.now().isoformat()}\n"
        content += f"Analysis Type: {analysis_type}\n"
        content += f"Token Usage: {token_usage.get('prompt_tokens', 0)} prompt + {token_usage.get('completion_tokens', 0)} completion = {token_usage.get('total_tokens', 0)} total\n\n"
        
        content += "SYSTEM PROMPT:\n"
        content += f"{system_prompt}\n\n"
        
        content += "USER PROMPT:\n"
        content += f"{user_prompt}\n\n"
        
        content += "LLM RESPONSE:\n"
        content += f"{response}\n"
        
        self._write_section(f"🤖 LLM INTERACTION ({analysis_type})", content)
    
    def log_parsed_analysis(self, parsed_data: Dict[str, Any], analysis_type: str = "Unknown"):
        """Log the parsed analysis results after JSON validation."""
        content = f"Timestamp: {datetime.now().isoformat()}\n"
        content += f"Analysis Type: {analysis_type}\n"
        content += f"Validation Status: {'✅ Success' if not parsed_data.get('_validation_error') else '❌ Failed (using fallback)'}\n\n"
        
        content += "PARSED ANALYSIS DATA:\n"
        content += json.dumps(parsed_data, indent=2, ensure_ascii=False)
        
        self._write_section(f"📊 PARSED ANALYSIS ({analysis_type})", content)
    
    def log_notification_decision(self, 
                                fresh_articles: List[Dict[str, Any]],
                                since_last_articles: List[Dict[str, Any]], 
                                previous_24h_articles: List[Dict[str, Any]],
                                time_since_last: str,
                                decision_response: Optional[str] = None,
                                final_decision: Optional[Dict[str, Any]] = None):
        """Log smart notification decision process."""
        content = f"Timestamp: {datetime.now().isoformat()}\n"
        content += f"Time Since Last Notification: {time_since_last}\n\n"
        
        content += f"FRESH ARTICLES ({len(fresh_articles)}):\n"
        for i, article in enumerate(fresh_articles, 1):
            content += f"  {i}. [{article.get('source', 'N/A')}] {article.get('title', 'N/A')}\n"
        
        content += f"\nSINCE LAST NOTIFICATION ({len(since_last_articles)}):\n"
        for i, article in enumerate(since_last_articles, 1):
            content += f"  {i}. [{article.get('source', 'N/A')}] {article.get('title', 'N/A')}\n"
        
        content += f"\nPREVIOUS 24H CONTEXT ({len(previous_24h_articles)}):\n"
        for i, article in enumerate(previous_24h_articles, 1):
            content += f"  {i}. [{article.get('source', 'N/A')}] {article.get('title', 'N/A')}\n"
        
        if decision_response:
            content += f"\nLLM DECISION RESPONSE:\n{decision_response}\n"
        
        if final_decision:
            content += f"\nFINAL DECISION:\n"
            content += json.dumps(final_decision, indent=2, ensure_ascii=False)
        
        self._write_section("🔔 NOTIFICATION DECISION PROCESS", content)
    
    def log_urgency_analysis(self,
                           fresh_articles_count: int,
                           urgency_keywords: List[str],
                           calculated_urgency: str,
                           is_peak_hours: bool,
                           is_quiet_hours: bool,
                           should_send_now: bool,
                           scheduled_time: Optional[datetime] = None,
                           reasoning: str = ""):
        """Log urgency calculation and scheduling decision."""
        content = f"Timestamp: {datetime.now().isoformat()}\n"
        content += f"Articles Analyzed: {fresh_articles_count}\n\n"
        
        content += "URGENCY SIGNALS:\n"
        if urgency_keywords:
            content += f"  Content Keywords: {', '.join(urgency_keywords)}\n"
        content += f"  Volume: {fresh_articles_count} articles\n"
        content += f"  Time Context: Peak={is_peak_hours}, Quiet={is_quiet_hours}\n\n"
        
        urgency_icon = {
            "breaking": "🚨",
            "high": "🔥",
            "normal": "📊",
            "low": "📌"
        }.get(calculated_urgency, "❓")
        
        content += f"CALCULATED URGENCY: {calculated_urgency.upper()} {urgency_icon}\n\n"
        
        content += "SCHEDULING DECISION:\n"
        content += f"  Should Notify: {'YES' if should_send_now else 'NO (scheduled)'}\n"
        content += f"  Send Timing: {'Immediate' if should_send_now else 'Scheduled'}\n"
        if scheduled_time:
            content += f"  Scheduled For: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        if reasoning:
            content += f"  Reasoning: {reasoning}\n"
        
        self._write_section("🎯 URGENCY ANALYSIS", content)
    
    def log_notifications_sent(self, 
                             compact_push: Optional[str] = None,
                             full_message: Optional[str] = None,
                             slack_payload: Optional[Dict[str, Any]] = None,
                             push_payload: Optional[Dict[str, Any]] = None,
                             success_status: Dict[str, bool] = None):
        """Log the final notification content that was sent."""
        content = f"Timestamp: {datetime.now().isoformat()}\n\n"
        
        if compact_push:
            content += f"COMPACT PUSH NOTIFICATION:\n"
            content += f"Text: {compact_push}\n"
            content += f"Length: {len(compact_push)} characters\n\n"
        
        if full_message:
            content += f"FULL MESSAGE CONTENT:\n"
            content += f"{full_message}\n\n"
        
        if slack_payload:
            content += f"SLACK PAYLOAD:\n"
            content += json.dumps(slack_payload, indent=2, ensure_ascii=False)
            content += "\n\n"
        
        if push_payload:
            content += f"PUSH PAYLOAD:\n"
            content += json.dumps(push_payload, indent=2, ensure_ascii=False)
            content += "\n\n"
        
        if success_status:
            content += f"DELIVERY STATUS:\n"
            for platform, success in success_status.items():
                status = "✅ Success" if success else "❌ Failed"
                content += f"  {platform}: {status}\n"
        
        self._write_section("📤 NOTIFICATIONS SENT", content)
    
    def log_error(self, error_type: str, error_message: str, context: str = ""):
        """Log errors that occur during processing."""
        content = f"Timestamp: {datetime.now().isoformat()}\n"
        content += f"Error Type: {error_type}\n"
        if context:
            content += f"Context: {context}\n"
        content += f"\nError Message:\n{error_message}\n"
        
        self._write_section("❌ ERROR", content)


# Global logger instance
_llm_logger = None

def get_llm_logger() -> LLMLogger:
    """Get the global LLM logger instance."""
    global _llm_logger
    if _llm_logger is None:
        _llm_logger = LLMLogger()
    return _llm_logger