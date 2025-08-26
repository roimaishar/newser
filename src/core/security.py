#!/usr/bin/env python3
"""
Security utilities for news aggregation.

Provides input validation, sanitization, and security measures for handling
external RSS feeds and user inputs safely.
"""

import re
import html
import urllib.parse
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class SecurityValidator:
    """Handles security validation and sanitization."""
    
    # Maximum allowed lengths to prevent DoS attacks
    MAX_TITLE_LENGTH = 500
    MAX_SUMMARY_LENGTH = 2000
    MAX_URL_LENGTH = 2048
    
    # Allowed URL schemes
    ALLOWED_SCHEMES = {'http', 'https'}
    
    # Trusted domains for RSS feeds
    TRUSTED_DOMAINS = {
        'ynet.co.il',
        'www.ynet.co.il', 
        'rss.walla.co.il',
        'news.walla.co.il',
        'walla.co.il'
    }
    
    # Patterns for detecting potentially malicious content
    SUSPICIOUS_PATTERNS = [
        r'<script[\s\S]*?</script>',  # Script tags
        r'javascript:',               # JavaScript URLs
        r'data:',                    # Data URLs
        r'vbscript:',               # VBScript URLs
        r'on\w+\s*=',              # Event handlers (onclick, onload, etc.)
    ]
    
    def __init__(self):
        self.suspicious_regex = re.compile('|'.join(self.SUSPICIOUS_PATTERNS), re.IGNORECASE)
    
    def validate_url(self, url: str) -> bool:
        """
        Validate that a URL is safe and from a trusted source.
        
        Returns:
            True if URL is valid and safe, False otherwise
        """
        if not url or len(url) > self.MAX_URL_LENGTH:
            return False
            
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Check scheme
            if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
                logger.warning(f"Blocked URL with invalid scheme: {parsed.scheme}")
                return False
            
            # Check domain
            domain = parsed.netloc.lower()
            if domain not in self.TRUSTED_DOMAINS:
                logger.warning(f"Blocked URL from untrusted domain: {domain}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error parsing URL {url}: {e}")
            return False
    
    def sanitize_text(self, text: str, max_length: int = None) -> str:
        """
        Sanitize text content by removing HTML tags and suspicious content.
        
        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length (uses default if None)
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
            
        # Set default max length
        if max_length is None:
            max_length = self.MAX_SUMMARY_LENGTH
            
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length] + "..."
            logger.warning(f"Truncated text longer than {max_length} characters")
        
        # Unescape HTML entities first
        text = html.unescape(text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Check for suspicious patterns
        if self.suspicious_regex.search(text):
            logger.warning("Detected suspicious content in text, cleaning...")
            text = self.suspicious_regex.sub('[REMOVED]', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def sanitize_title(self, title: str) -> str:
        """Sanitize article title."""
        return self.sanitize_text(title, self.MAX_TITLE_LENGTH)
    
    def sanitize_summary(self, summary: str) -> str:
        """Sanitize article summary."""
        return self.sanitize_text(summary, self.MAX_SUMMARY_LENGTH)
    
    def validate_feed_response(self, response_content: bytes, url: str) -> bool:
        """
        Validate RSS feed response for basic security checks.
        
        Args:
            response_content: Raw response content
            url: Feed URL for logging
            
        Returns:
            True if response appears safe, False otherwise
        """
        if not response_content:
            return False
            
        # Check response size (prevent DoS)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(response_content) > max_size:
            logger.error(f"Feed response too large ({len(response_content)} bytes) from {url}")
            return False
        
        try:
            # Try to decode as text for basic validation
            text_content = response_content.decode('utf-8', errors='ignore')
            
            # Check for XML declaration or RSS/feed tags
            has_xml = any(marker in text_content[:1000].lower() for marker in [
                '<?xml', '<rss', '<feed', '<channel'
            ])
            
            if not has_xml:
                logger.warning(f"Response from {url} doesn't appear to be valid XML/RSS")
                return False
                
            # Check for obviously malicious content in the beginning
            start_content = text_content[:5000].lower()
            if any(pattern in start_content for pattern in ['<script', 'javascript:', 'vbscript:']):
                logger.error(f"Detected suspicious content in feed from {url}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating feed response from {url}: {e}")
            return False
    
    def rate_limit_check(self, requests_count: int, time_window: int = 300) -> bool:
        """
        Basic rate limiting check.
        
        Args:
            requests_count: Number of requests in time window
            time_window: Time window in seconds (default: 5 minutes)
            
        Returns:
            True if within limits, False if rate limited
        """
        # Allow reasonable number of requests per time window
        max_requests = 30  # 30 requests per 5 minutes
        
        if requests_count > max_requests:
            logger.warning(f"Rate limit exceeded: {requests_count} requests in {time_window}s")
            return False
            
        return True

class SecureFeedConfig:
    """Secure configuration for RSS feeds."""
    
    def __init__(self):
        self.validator = SecurityValidator()
        
        # Default secure feeds
        self.feeds = {
            'ynet': {
                'name': 'Ynet',
                'url': 'http://www.ynet.co.il/Integration/StoryRss2.xml',
                'verified': True
            },
            'walla': {
                'name': 'Walla',
                'url': 'https://rss.walla.co.il/MainRss',
                'verified': True
            }
        }
    
    def validate_feed_config(self, feed_name: str, feed_url: str) -> bool:
        """Validate a feed configuration is secure."""
        return self.validator.validate_url(feed_url)
    
    def get_verified_feeds(self) -> dict:
        """Get only verified, secure feeds."""
        return {k: v for k, v in self.feeds.items() if v.get('verified', False)}
    
    def add_feed(self, name: str, url: str) -> bool:
        """Add a new feed if it passes security validation."""
        if self.validate_feed_config(name, url):
            self.feeds[name] = {
                'name': name,
                'url': url,
                'verified': True
            }
            logger.info(f"Added verified feed: {name}")
            return True
        else:
            logger.error(f"Failed to add feed {name}: security validation failed")
            return False