#!/usr/bin/env python3
"""
Text sanitization utilities for Hebrew content processing.

Handles common issues with Hebrew text that can break JSON parsing,
including quote normalization and character encoding issues.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Hebrew quotation marks that can break JSON parsing
HEBREW_QUOTES_MAP = {
    "״": '"',  # Gershayim
    "׳": "'",  # Geresh
    "“": '"',  # Left double quotation mark
    "”": '"',  # Right double quotation mark
    "‘": "'",  # Left single quotation mark
    "’": "'",  # Right single quotation mark
}

HEBREW_QUOTES_TRANSLATION = str.maketrans(HEBREW_QUOTES_MAP)

def normalize_hebrew_quotes(text: str) -> str:
    """
    Normalize Hebrew quotation marks to ASCII equivalents.
    
    This prevents JSON parsing errors caused by Hebrew-specific
    quotation marks that can appear in news content.
    
    Args:
        text: Input text that may contain Hebrew quotes
        
    Returns:
        Text with normalized ASCII quotes
    """
    if not text:
        return text
    
    return text.translate(HEBREW_QUOTES_TRANSLATION)

def sanitize_json_string(text: str) -> str:
    """
    Sanitize text for safe JSON parsing.
    
    Combines quote normalization with other common fixes:
    - Normalize Hebrew quotes to ASCII
    - Escape internal quotes properly
    - Handle newlines and control characters
    
    Args:
        text: Raw text that will be part of JSON
        
    Returns:
        Sanitized text safe for JSON parsing
    """
    if not text:
        return text
    
    # Step 1: Normalize Hebrew quotes
    sanitized = normalize_hebrew_quotes(text)
    
    # Step 2: Escape backslashes first to avoid double escaping later
    sanitized = sanitized.replace('\\', '\\\\')
    
    # Step 3: Escape newlines and control characters
    sanitized = sanitized.replace('\n', '\\n')
    sanitized = sanitized.replace('\r', '\\r')
    sanitized = sanitized.replace('\t', '\\t')
    
    # Step 4: Escape unescaped double quotes
    sanitized = re.sub(r'(?<!\\)"', '\\"', sanitized)
    
    return sanitized

def preprocess_llm_response(raw_response: str) -> str:
    """
    Preprocess LLM response before JSON parsing.
    
    This is a safety net for cases where structured outputs
    aren't used or as a fallback mechanism.
    
    Args:
        raw_response: Raw response from LLM
        
    Returns:
        Preprocessed response ready for JSON parsing
    """
    if not raw_response:
        return raw_response
    
    # Normalize Hebrew quotes throughout the response
    processed = normalize_hebrew_quotes(raw_response)
    
    # Log if we made changes
    if processed != raw_response:
        logger.info("Normalized Hebrew quotes in LLM response")
        logger.debug(
            "Original length: %d, processed length: %d",
            len(raw_response),
            len(processed),
        )
    
    return processed
