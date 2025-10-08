"""
Content fetcher service for extracting full article text.
Implements polite crawling with rate limiting and backoff.
"""

import time
import random
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ContentFetcher:
    """Polite content fetcher that respects rate limits and robots.txt."""
    
    def __init__(self, 
                 base_delay: tuple = (6, 10),
                 max_retries: int = 3,
                 timeout: int = 20,
                 user_agent: str = "NewserBot/1.0 (+https://github.com/roimaishar/newser)"):
        """
        Initialize content fetcher.
        
        Args:
            base_delay: (min, max) seconds between requests
            max_retries: Maximum retry attempts for failed requests
            timeout: Request timeout in seconds
            user_agent: User-Agent string for requests
        """
        self.base_delay = base_delay
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Configure session with polite headers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "he,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        
        # Rate limiting state
        self.last_request_time = 0
        self.backoff_until = 0
        self.consecutive_failures = 0
        
    def _wait_politely(self):
        """Implement polite delays between requests."""
        current_time = time.time()
        
        # Check if we're in backoff period
        if current_time < self.backoff_until:
            wait_time = self.backoff_until - current_time
            logger.info(f"In backoff period, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            
        # Ensure minimum delay since last request
        time_since_last = current_time - self.last_request_time
        min_delay = random.uniform(*self.base_delay)
        
        if time_since_last < min_delay:
            wait_time = min_delay - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            
        self.last_request_time = time.time()
    
    def _handle_rate_limit(self, status_code: int):
        """Handle rate limiting responses with exponential backoff."""
        if status_code in (429, 403):
            self.consecutive_failures += 1
            backoff_time = min(600, 60 * (2 ** self.consecutive_failures))  # Max 10 minutes
            self.backoff_until = time.time() + backoff_time
            
            logger.warning(f"Rate limited (HTTP {status_code}), backing off for {backoff_time}s")
            raise requests.exceptions.RequestException(f"Rate limited: HTTP {status_code}")
        elif status_code >= 500:
            # Server error - shorter backoff
            self.consecutive_failures += 1
            backoff_time = min(300, 30 * self.consecutive_failures)  # Max 5 minutes
            self.backoff_until = time.time() + backoff_time
            
            logger.warning(f"Server error (HTTP {status_code}), backing off for {backoff_time}s")
            raise requests.exceptions.RequestException(f"Server error: HTTP {status_code}")
    
    def fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL with polite crawling.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                self._wait_politely()
                
                logger.debug(f"Fetching {url} (attempt {attempt + 1}/{self.max_retries})")
                
                response = self.session.get(url, timeout=self.timeout)
                
                # Handle rate limiting
                if response.status_code in (429, 403) or response.status_code >= 500:
                    self._handle_rate_limit(response.status_code)
                    continue
                    
                response.raise_for_status()
                
                # Success - reset failure counter
                self.consecutive_failures = 0
                
                logger.debug(f"Successfully fetched {url} ({len(response.text)} chars)")
                return response.text
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed for {url}: {e}")
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
                    return None
                    
                # Exponential backoff for retries
                retry_delay = 2 ** attempt
                time.sleep(retry_delay)
                
        return None
    
    def extract_text_simple(self, html: str, url: str) -> Dict[str, Any]:
        """
        Simple text extraction using BeautifulSoup (fallback method).
        
        Args:
            html: HTML content
            url: Source URL
            
        Returns:
            Dictionary with extracted content
        """
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Try to find article content (common selectors for news sites)
            content_selectors = [
                'article',
                '.article-content',
                '.article-body', 
                '.content',
                '.post-content',
                '[data-article-body]'
            ]
            
            article_text = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    article_text = content_elem.get_text(strip=True)
                    break
            
            # Fallback to body text
            if not article_text:
                article_text = soup.get_text(strip=True)
            
            # Get title
            title_elem = soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            return {
                'text': article_text,
                'title': title,
                'url': url,
                'extraction_method': 'beautifulsoup',
                'extracted_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Text extraction failed for {url}: {e}")
            return {
                'text': '',
                'title': '',
                'url': url,
                'extraction_method': 'failed',
                'error': str(e),
                'extracted_at': datetime.now(timezone.utc).isoformat()
            }
    
    def extract_text_trafilatura(self, html: str, url: str) -> Dict[str, Any]:
        """
        Advanced text extraction using trafilatura (preferred method).
        
        Args:
            html: HTML content
            url: Source URL
            
        Returns:
            Dictionary with extracted content
        """
        try:
            import trafilatura
            
            # Extract with metadata
            result = trafilatura.extract(
                html,
                url=url,
                output_format='json',
                with_metadata=True,
                include_comments=False,
                include_tables=True
            )
            
            if result:
                import json
                data = json.loads(result)
                return {
                    'text': data.get('text', ''),
                    'title': data.get('title', ''),
                    'url': url,
                    'extraction_method': 'trafilatura',
                    'extracted_at': datetime.now(timezone.utc).isoformat(),
                    'metadata': {
                        'author': data.get('author'),
                        'date': data.get('date'),
                        'description': data.get('description'),
                        'sitename': data.get('sitename')
                    }
                }
            else:
                # Fallback to simple extraction
                logger.warning(f"Trafilatura extraction failed for {url}, using fallback")
                return self.extract_text_simple(html, url)
                
        except ImportError:
            logger.warning("Trafilatura not available, using BeautifulSoup fallback")
            return self.extract_text_simple(html, url)
        except Exception as e:
            logger.error(f"Trafilatura extraction failed for {url}: {e}")
            return self.extract_text_simple(html, url)
    
    def fetch_and_extract(self, url: str, use_trafilatura: bool = True) -> Optional[Dict[str, Any]]:
        """
        Fetch URL and extract text content.
        
        Args:
            url: URL to fetch and extract
            use_trafilatura: Whether to use trafilatura (if available)
            
        Returns:
            Extracted content dictionary or None if failed
        """
        html = self.fetch_html(url)
        if not html:
            return None
            
        if use_trafilatura:
            return self.extract_text_trafilatura(html, url)
        else:
            return self.extract_text_simple(html, url)
    
    def fetch_multiple(self, urls: List[str], max_items: int = 15) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs with rate limiting.
        
        Args:
            urls: List of URLs to fetch
            max_items: Maximum number of items to fetch per batch
            
        Returns:
            List of extracted content dictionaries
        """
        results = []
        
        for i, url in enumerate(urls[:max_items]):
            logger.info(f"Fetching {i+1}/{min(len(urls), max_items)}: {url}")
            
            content = self.fetch_and_extract(url)
            if content:
                results.append(content)
            else:
                logger.warning(f"Failed to fetch content from {url}")
                
        logger.info(f"Successfully fetched {len(results)}/{min(len(urls), max_items)} articles")
        return results
