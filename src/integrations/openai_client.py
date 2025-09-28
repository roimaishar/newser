#!/usr/bin/env python3
"""
OpenAI integration for news analysis and summarization.

Provides AI-powered analysis of news articles including:
- Summarization of multiple articles
- Topic extraction and categorization
- Sentiment analysis
- Key insights generation
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from openai import OpenAI
from core.analysis.hebrew.prompts import NewsAnalysisPrompts
from core.schemas import get_schema_by_type

logger = logging.getLogger(__name__)

@dataclass
class NewsAnalysis:
    """Results from AI analysis of news articles."""
    summary: str
    key_topics: List[str]
    sentiment: str  # positive, negative, neutral
    insights: List[str]
    article_count: int
    analysis_timestamp: datetime

class OpenAIClient:
    """Client for OpenAI API integration with structured outputs."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key. If None, tries to get from environment.
        """
        api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key not provided and not found in OPENAI_API_KEY environment variable")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"
        self.max_tokens = 2500
        self.temperature = 0.3  # Lower temperature for more consistent analysis
        
    def _make_structured_request(self, messages: List[Dict[str, str]], schema: Dict[str, Any], analysis_type: str = "unknown") -> Dict[str, Any]:
        """Make a structured request to OpenAI API with JSON schema enforcement."""
        
        # Log the API call for debugging
        logger.info(f"Making OpenAI structured API call for {analysis_type}")
        
        # Log the actual prompt being sent to LLM
        logger.info(f"=== LLM INPUT PROMPT (Messages: {len(messages)}) ===")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # Truncate very long content for readability
            if len(content) > 1000:
                content_preview = content[:500] + "\n...\n" + content[-500:]
            else:
                content_preview = content
            logger.info(f"Message {i+1} [{role.upper()}]:\n{content_preview}")
        logger.info("=== END LLM INPUT ===")
        
        try:
            # Use structured outputs with JSON schema
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": f"{analysis_type}_response",
                        "schema": schema,
                        "strict": True
                    }
                }
            )
            
            # Detect truncated responses early
            finish_reason = getattr(response.choices[0], "finish_reason", None)
            if finish_reason == "length":
                logger.error(
                    "OpenAI response for %s was truncated due to max_tokens=%s. Consider increasing the limit.",
                    analysis_type,
                    self.max_tokens,
                )
                raise ValueError("OpenAI response truncated (finish_reason=length)")
            
            # Convert to dict for compatibility
            result = {
                "choices": [{
                    "message": {
                        "content": response.choices[0].message.content,
                        "role": response.choices[0].message.role
                    }
                }],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
            # Log the actual response from LLM
            response_content = result['choices'][0]['message']['content']
            logger.info(f"=== LLM OUTPUT RESPONSE ===")
            logger.info(f"{response_content}")
            logger.info("=== END LLM OUTPUT ===")
            
            # Log successful response with token usage
            usage = result.get('usage', {})
            prompt_tokens = usage.get('prompt_tokens', 'unknown')
            completion_tokens = usage.get('completion_tokens', 'unknown') 
            total_tokens = usage.get('total_tokens', 'unknown')
            logger.info(f"OpenAI API call successful - tokens: {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total")
            
            # Log to debug file
            try:
                from core.llm_logger import get_llm_logger
                llm_logger = get_llm_logger()
                
                # Extract system and user prompts
                system_prompt = ""
                user_prompt = ""
                
                for msg in messages:
                    if msg.get('role') == 'system':
                        system_prompt = msg.get('content', '')
                    elif msg.get('role') == 'user':
                        user_prompt = msg.get('content', '')
                
                llm_logger.log_llm_interaction(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt, 
                    response=response_content,
                    token_usage=usage,
                    analysis_type=analysis_type
                )
            except Exception as e:
                logger.error(f"Failed to log LLM interaction to debug file: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI structured API request failed: {e}")
            raise
    
    def analyze_thematic(self, articles: List[Dict[str, str]], hours: int = 24) -> Dict[str, Any]:
        """
        Perform thematic analysis using structured outputs.
        
        Args:
            articles: List of articles to analyze
            hours: Time window for context
            
        Returns:
            Structured thematic analysis results
        """
        if not articles:
            return {
                "mobile_headline": "לא נמצאו כתבות לניתוח",
                "story_behind_story": "אין תוכן זמין לניתוח",
                "connection_threads": [],
                "reader_impact": "",
                "trend_signal": ""
            }
        
        # Generate analysis prompt using centralized prompts
        prompt = NewsAnalysisPrompts.get_analysis_prompt(articles, hours=hours)
        
        messages = [
            {"role": "system", "content": NewsAnalysisPrompts.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        # Get schema and make structured request
        schema = get_schema_by_type("thematic")
        response = self._make_structured_request(messages, schema, "thematic_analysis")
        
        # Parse JSON response (guaranteed to be valid due to structured output)
        content = response['choices'][0]['message']['content']
        return json.loads(content)
    
    def _validate_and_fix_schema(self, response_data: Dict[str, Any], hours: int) -> Dict[str, Any]:
        """Validate and fix schema violations in LLM response."""
        
        # Ensure time_window_hours is present
        if "time_window_hours" not in response_data:
            response_data["time_window_hours"] = hours
            logger.info(f"Added missing time_window_hours: {hours}")
        
        # Strict validation - fail on critical errors
        valid_statuses = {"new", "update", "duplicate"}
        for i, item in enumerate(response_data.get("items", [])):
            # Check status
            status = item.get("status")
            if status not in valid_statuses:
                raise ValueError(f"Item {i+1}: Invalid status '{status}' - must be English: {valid_statuses}")
            
            # Check date format in event_id and lede_he
            event_id = item.get("event_id", "")
            lede_he = item.get("lede_he", "")
            
            # Event ID should start with 2025-09-28 (current date)
            if not event_id.startswith("2025-09-28"):
                raise ValueError(f"Item {i+1}: Invalid date in event_id '{event_id}' - must start with 2025-09-28")
                
            # Lede should start with 2025-09-28
            if not lede_he.startswith("2025-09-28"):
                raise ValueError(f"Item {i+1}: Invalid date in lede_he '{lede_he}' - must start with 2025-09-28")
        
        # Ensure bulletins_he exists
        if "bulletins_he" not in response_data:
            response_data["bulletins_he"] = "אין עדכונים"
            logger.info("Added missing bulletins_he field")
        
        return response_data
    
    def analyze_novelty(self, articles: List[Dict[str, str]], known_events: List[Dict[str, Any]], hours: int = 12) -> Dict[str, Any]:
        """
        Perform novelty detection analysis using structured outputs.
        
        Args:
            articles: List of articles to analyze
            known_events: List of known events for comparison
            hours: Time window for context
            
        Returns:
            Structured novelty analysis results
        """
        if not articles:
            return {
                "has_new": False,
                "items": [],
                "bulletins_he": "לא נמצאו כתבות חדשות לניתוח"
            }
        
        # Generate novelty detection prompt
        from core.analysis.hebrew.prompts import NewsAnalysisPrompts
        prompt = NewsAnalysisPrompts.get_update_prompt(articles, known_events, hours=hours)
        
        messages = [
            {"role": "system", "content": NewsAnalysisPrompts.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        # Get schema and make structured request
        schema = get_schema_by_type("novelty")
        response = self._make_structured_request(messages, schema, "novelty_detection")
        
        # Parse and validate JSON response
        content = response['choices'][0]['message']['content']
        parsed_response = json.loads(content)
        
        # Apply schema fixes
        validated_response = self._validate_and_fix_schema(parsed_response, hours)
        
        return validated_response
    
    def analyze_notification_decision(self, fresh_articles: List[Dict[str, Any]], 
                                   since_last: List[Dict[str, Any]], 
                                   previous_24h: List[Dict[str, Any]], 
                                   time_since_last: str) -> Dict[str, Any]:
        """
        Analyze whether to send notifications using structured outputs.
        
        Args:
            fresh_articles: Recently scraped articles
            since_last: Articles since last notification
            previous_24h: Articles from previous 24 hours
            time_since_last: Time since last notification
            
        Returns:
            Structured notification decision
        """
        from core.analysis.hebrew.prompts import get_notification_prompt
        prompt = get_notification_prompt(fresh_articles, since_last, previous_24h, time_since_last)
        
        messages = [
            {"role": "system", "content": "אתה עורך חדשות מקצועי שמחליט על התראות חכמות."},
            {"role": "user", "content": prompt}
        ]
        
        # Get schema and make structured request
        schema = get_schema_by_type("notification")
        response = self._make_structured_request(messages, schema, "notification_decision")
        
        # Parse JSON response (guaranteed to be valid due to structured output)
        content = response['choices'][0]['message']['content']
        return json.loads(content)
    
    def analyze_headlines(self, articles: List[Dict[str, str]]) -> NewsAnalysis:
        """
        Legacy method for backward compatibility.
        
        Args:
            articles: List of articles with 'title', 'source', and optional 'summary'
            
        Returns:
            NewsAnalysis object with AI-generated insights
        """
        try:
            # Use new structured thematic analysis
            analysis_data = self.analyze_thematic(articles)
            
            return NewsAnalysis(
                summary=analysis_data.get('mobile_headline', 'Analysis completed'),
                key_topics=analysis_data.get('connection_threads', []),
                sentiment="neutral",  # Thematic analysis doesn't focus on sentiment
                insights=[analysis_data.get('reader_impact', ''), analysis_data.get('trend_signal', '')],
                article_count=len(articles),
                analysis_timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}")
            return NewsAnalysis(
                summary="Analysis failed due to technical error",
                key_topics=[],
                sentiment="neutral", 
                insights=[f"Error: {str(e)}"],
                article_count=len(articles),
                analysis_timestamp=datetime.now()
            )
    
    def generate_summary_report(self, analysis: NewsAnalysis) -> str:
        """
        Generate a formatted summary report from analysis results.
        
        Args:
            analysis: NewsAnalysis object
            
        Returns:
            Formatted text report
        """
        report_lines = [
            "=" * 60,
            "AI NEWS ANALYSIS REPORT",
            "=" * 60,
            f"Generated: {analysis.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Articles analyzed: {analysis.article_count}",
            "",
            "SUMMARY:",
            f"{analysis.summary}",
            "",
            "KEY TOPICS:",
        ]
        
        for topic in analysis.key_topics:
            report_lines.append(f"• {topic}")
        
        report_lines.extend([
            "",
            f"SENTIMENT: {analysis.sentiment.upper()}",
            "",
            "KEY INSIGHTS:",
        ])
        
        for insight in analysis.insights:
            report_lines.append(f"• {insight}")
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def analyze_text(self, title: str, text: str) -> Optional[str]:
        """
        Analyze a text with OpenAI for integration testing.
        
        Args:
            title: Title/topic for the analysis
            text: Text to analyze
            
        Returns:
            Analysis result or None if failed
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful text analyst. Provide a brief analysis of the given text."
                },
                {
                    "role": "user", 
                    "content": f"Topic: {title}\n\nText: {text}\n\nPlease provide a brief analysis:"
                }
            ]
            
            # Use regular completion for simple text analysis
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=200,
                temperature=0.3
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Text analysis failed: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test OpenAI API connection."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            if response and response.choices:
                logger.info("OpenAI API connection test successful")
                return True
            else:
                logger.error("OpenAI API connection test failed: no response")
                return False
            
        except Exception as e:
            logger.error(f"OpenAI API connection test failed: {e}")
            return False
    
    def chat_completion(self, messages: List[Dict[str, str]], max_tokens: int = None, temperature: float = None) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility with smart notifier.
        
        Args:
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Response dict in legacy format
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature
            )
            
            # Convert to legacy format
            return {
                "choices": [{
                    "message": {
                        "content": response.choices[0].message.content,
                        "role": response.choices[0].message.role
                    }
                }],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            raise