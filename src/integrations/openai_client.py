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
import requests
from datetime import datetime

from core.analysis.hebrew.prompts import NewsAnalysisPrompts

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
    """Client for OpenAI API integration."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key. If None, tries to get from environment.
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not provided and not found in OPENAI_API_KEY environment variable")
        
        self.base_url = "https://api.openai.com/v1"
        self.model = "gpt-4o-mini"  # Cost-effective model for text analysis
        self.max_tokens = 1000
        self.temperature = 0.3  # Lower temperature for more consistent analysis
        
        # Headers for API requests
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    def _make_api_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to OpenAI API."""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30, verify=True)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI API response: {e}")
            raise
    
    def analyze_headlines(self, articles: List[Dict[str, str]]) -> NewsAnalysis:
        """
        Analyze a collection of news headlines using OpenAI.
        
        Args:
            articles: List of articles with 'title', 'source', and optional 'summary'
            
        Returns:
            NewsAnalysis object with AI-generated insights
        """
        if not articles:
            return NewsAnalysis(
                summary="No articles to analyze",
                key_topics=[],
                sentiment="neutral",
                insights=[],
                article_count=0,
                analysis_timestamp=datetime.now()
            )
        
        # Generate analysis prompt using centralized prompts
        prompt = NewsAnalysisPrompts.get_analysis_prompt(articles, hours=24)

        # Make API request
        try:
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system", 
                        "content": NewsAnalysisPrompts.SYSTEM_PROMPT
                    },
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
            
            response = self._make_api_request("chat/completions", data)
            
            # Parse response
            content = response['choices'][0]['message']['content'].strip()
            
            # Try to extract JSON from response
            try:
                # Remove any markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                analysis_data = json.loads(content)
                
                return NewsAnalysis(
                    summary=analysis_data.get('summary', 'Analysis completed'),
                    key_topics=analysis_data.get('key_topics', []),
                    sentiment=analysis_data.get('sentiment', 'neutral'),
                    insights=analysis_data.get('insights', []),
                    article_count=len(articles),
                    analysis_timestamp=datetime.now()
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI analysis response as JSON: {e}")
                logger.debug(f"Raw response: {content}")
                
                # Fallback: create basic analysis
                return NewsAnalysis(
                    summary="AI analysis completed but response format was invalid",
                    key_topics=["news", "current events"],
                    sentiment="neutral",
                    insights=["Analysis response could not be parsed"],
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
            
            data = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0.3,
            }
            
            response = self._make_api_request("chat/completions", data)
            
            if response and "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"].strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Text analysis failed: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test OpenAI API connection."""
        try:
            data = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5
            }
            
            self._make_api_request("chat/completions", data)
            logger.info("OpenAI API connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"OpenAI API connection test failed: {e}")
            return False