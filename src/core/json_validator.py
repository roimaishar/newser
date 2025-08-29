#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON Schema Validation for Hebrew News Analysis.

Validates LLM output against expected schemas with fallback mechanisms.
"""

import json
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


class JSONValidationError(Exception):
    """Custom exception for JSON validation failures."""
    pass


class HebrewAnalysisValidator:
    """Validates Hebrew news analysis JSON output with fallbacks."""
    
    @staticmethod
    def validate_and_parse(raw_output: str, analysis_type: str = "updates") -> Dict[str, Any]:
        """
        Validate and parse LLM JSON output with fallback mechanisms.
        
        Args:
            raw_output: Raw string output from LLM
            analysis_type: Type of analysis ("updates" or "thematic")
            
        Returns:
            Validated and cleaned JSON dict
            
        Raises:
            JSONValidationError: If validation fails completely
        """
        # Step 1: Extract JSON from potentially mixed output
        json_str = HebrewAnalysisValidator._extract_json(raw_output)
        
        # Step 2: Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            # Attempt repair
            data = HebrewAnalysisValidator._repair_json(json_str)
        
        # Step 3: Validate schema
        if analysis_type == "updates":
            return HebrewAnalysisValidator._validate_updates_schema(data)
        else:
            return HebrewAnalysisValidator._validate_thematic_schema(data)
    
    @staticmethod
    def _extract_json(raw_output: str) -> str:
        """Extract JSON from mixed text output."""
        if not raw_output.strip():
            raise JSONValidationError("Empty output")
        
        # Look for JSON block
        start_markers = ['{', '```json\n{', '```\n{']
        end_markers = ['}', '}\n```', '}```']
        
        for start_marker in start_markers:
            start_idx = raw_output.find(start_marker)
            if start_idx != -1:
                # Find matching end
                for end_marker in end_markers:
                    end_idx = raw_output.rfind(end_marker)
                    if end_idx > start_idx:
                        json_str = raw_output[start_idx:end_idx + len(end_marker.rstrip('`\n'))]
                        # Clean up markdown artifacts
                        json_str = json_str.replace('```json', '').replace('```', '').strip()
                        return json_str
        
        # Fallback: assume entire output is JSON
        return raw_output.strip()
    
    @staticmethod
    def _repair_json(broken_json: str) -> Dict[str, Any]:
        """Attempt to repair common JSON syntax errors."""
        logger.warning("Attempting JSON repair")
        
        # Common fixes
        repaired = broken_json
        
        # Fix trailing commas
        repaired = repaired.replace(',}', '}').replace(',]', ']')
        
        # Fix missing quotes around keys (basic cases)
        import re
        repaired = re.sub(r'(\w+):', r'"\1":', repaired)
        
        # Fix Hebrew text escaping issues
        repaired = repaired.replace('\n', '\\n').replace('\r', '\\r')
        
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            # Final fallback: return minimal valid structure
            logger.error("JSON repair failed, returning fallback structure")
            return {
                "has_new": False,
                "items": [],
                "bulletins_he": "שגיאה בעיבוד התגובה מהמודל",
                "_validation_error": True
            }
    
    @staticmethod
    def _validate_updates_schema(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate updates analysis schema."""
        required_fields = ["has_new", "items"]
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                if field == "has_new":
                    data[field] = False
                elif field == "items":
                    data[field] = []
        
        # Validate items structure
        if not isinstance(data["items"], list):
            logger.warning("Items field is not a list, converting")
            data["items"] = []
        
        # Validate each item
        validated_items = []
        for item in data["items"]:
            if isinstance(item, dict):
                validated_item = HebrewAnalysisValidator._validate_item_schema(item)
                validated_items.append(validated_item)
        
        data["items"] = validated_items
        
        # Ensure bulletins_he exists
        if "bulletins_he" not in data:
            data["bulletins_he"] = ""
        
        return data
    
    @staticmethod
    def _validate_thematic_schema(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate thematic analysis schema."""
        required_fields = ["mobile_headline", "story_behind_story"]
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                data[field] = ""
        
        return data
    
    @staticmethod
    def _validate_item_schema(item: Dict[str, Any]) -> Dict[str, Any]:
        """Validate individual news item schema."""
        required_fields = {
            "event_id": "",
            "status": "unknown",
            "lede_he": "",
            "significance_he": "",
            "confidence": 0.0
        }
        
        for field, default in required_fields.items():
            if field not in item:
                item[field] = default
        
        # Validate confidence is numeric
        try:
            item["confidence"] = float(item["confidence"])
        except (ValueError, TypeError):
            item["confidence"] = 0.0
        
        # Ensure lists are lists
        for list_field in ["what_changed_he", "evidence"]:
            if list_field in item and not isinstance(item[list_field], list):
                item[list_field] = []
        
        return item


def validate_hebrew_analysis(raw_output: str, analysis_type: str = "updates") -> Dict[str, Any]:
    """
    Convenience function for validating Hebrew analysis output.
    
    Args:
        raw_output: Raw LLM output string
        analysis_type: Type of analysis ("updates" or "thematic")
        
    Returns:
        Validated JSON dict
    """
    return HebrewAnalysisValidator.validate_and_parse(raw_output, analysis_type)
