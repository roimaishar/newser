import logging
import pytest

from core.text_sanitizer import normalize_hebrew_quotes, sanitize_json_string, preprocess_llm_response


def test_normalize_hebrew_quotes():
    """Test Hebrew quote normalization."""
    text_with_hebrew_quotes = 'צה״ל אמר: ״הפעולה הסתיימה״ ו׳זה טוב׳'
    normalized = normalize_hebrew_quotes(text_with_hebrew_quotes)
    
    assert '״' not in normalized
    assert '׳' not in normalized
    assert '"' in normalized
    assert "'" in normalized
    assert 'צה"ל אמר: "הפעולה הסתיימה" ו\'זה טוב\'' == normalized


def test_sanitize_json_string():
    """Test JSON string sanitization."""
    problematic_text = 'Line 1\nLine 2\tTabbed\r\nWith "quotes" and \\backslash'
    sanitized = sanitize_json_string(problematic_text)
    
    assert '\\n' in sanitized
    assert '\\t' in sanitized
    assert '\\r' in sanitized
    assert '\\"' in sanitized
    assert '\\\\' in sanitized
    # Should not contain unescaped problematic characters
    assert '\n' not in sanitized
    assert '\t' not in sanitized
    assert '\r' not in sanitized


def test_preprocess_llm_response_logs_changes(caplog):
    """Test that preprocessing logs when changes are made."""
    caplog.set_level(logging.INFO, logger="core.text_sanitizer")
    response_with_hebrew_quotes = '{"message": "צה״ל דיווח"}'
    
    processed = preprocess_llm_response(response_with_hebrew_quotes)
    
    assert processed != response_with_hebrew_quotes
    assert '"' in processed
    assert '״' not in processed
    assert "Normalized Hebrew quotes in LLM response" in caplog.text


def test_preprocess_llm_response_no_changes_no_log(caplog):
    """Test that preprocessing doesn't log when no changes are made."""
    caplog.set_level(logging.INFO, logger="core.text_sanitizer")
    clean_response = '{"message": "Regular text with no Hebrew quotes"}'
    
    processed = preprocess_llm_response(clean_response)
    
    assert processed == clean_response
    assert "Normalized Hebrew quotes" not in caplog.text


@pytest.mark.parametrize("input_text,expected_chars", [
    ("״", '"'),
    ("׳", "'"),
    ("“", '"'),
    ("”", '"'),
    ("‘", "'"),
    ("’", "'"),
])
def test_individual_quote_mappings(input_text, expected_chars):
    """Test each Hebrew quote mapping individually."""
    result = normalize_hebrew_quotes(input_text)
    assert result == expected_chars


def test_empty_and_none_inputs():
    """Test handling of empty and None inputs."""
    assert normalize_hebrew_quotes("") == ""
    assert normalize_hebrew_quotes(None) is None
    assert sanitize_json_string("") == ""
    assert sanitize_json_string(None) is None
    assert preprocess_llm_response("") == ""
    assert preprocess_llm_response(None) is None
