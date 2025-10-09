#!/usr/bin/env python3
"""
Centralized JSON schemas for OpenAI structured outputs.

Contains all JSON schemas used for LLM responses to ensure consistency
and enable structured output validation.
"""

from typing import Dict, Any

# Schema for thematic analysis (general news overview)
THEMATIC_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "mobile_headline": {
            "type": "string",
            "description": "כותרת מותאמת לנייד (עד 60 תווים)"
        },
        "story_behind_story": {
            "type": "string", 
            "description": "הסיפור מאחורי הסיפור - הקשר עמוק"
        },
        "connection_threads": {
            "type": "array",
            "items": {"type": "string"},
            "description": "חוטים מקשרים בין הסיפורים"
        },
        "reader_impact": {
            "type": "string",
            "description": "השפעה על הקורא הישראלי"
        },
        "trend_signal": {
            "type": "string",
            "description": "אות מגמה עתידית"
        }
    },
    "required": ["mobile_headline", "story_behind_story", "connection_threads", "reader_impact", "trend_signal"],
    "additionalProperties": False
}

# Schema for thematic analysis WITH notification decision
THEMATIC_WITH_NOTIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "mobile_headline": {
            "type": "string",
            "description": "כותרת מותאמת לנייד (עד 60 תווים)"
        },
        "story_behind_story": {
            "type": "string", 
            "description": "הסיפור מאחורי הסיפור - הקשר עמוק"
        },
        "connection_threads": {
            "type": "array",
            "items": {"type": "string"},
            "description": "חוטים מקשרים בין הסיפורים"
        },
        "reader_impact": {
            "type": "string",
            "description": "השפעה על הקורא הישראלי"
        },
        "trend_signal": {
            "type": "string",
            "description": "אות מגמה עתידית"
        },
        "notification": {
            "type": "object",
            "description": "החלטת התראה",
            "properties": {
                "should_notify_now": {
                    "type": "boolean",
                    "description": "האם לשלוח התראה כעת"
                },
                "compact_push": {
                    "type": "string",
                    "description": "הודעת פוש קצרה (עד 60 תווים) - בעברית בלבד"
                },
                "full_message": {
                    "type": "string",
                    "description": "הודעה מלאה לסלאק - בעברית בלבד"
                },
                "reasoning": {
                    "type": "string",
                    "description": "נימוק להחלטה"
                },
                "urgency_level": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "breaking"],
                    "description": "רמת דחיפות"
                }
            },
            "required": ["should_notify_now", "compact_push", "full_message", "reasoning", "urgency_level"],
            "additionalProperties": False
        }
    },
    "required": ["mobile_headline", "story_behind_story", "connection_threads", "reader_impact", "trend_signal", "notification"],
    "additionalProperties": False
}

# Schema for novelty detection analysis (updates vs known events)
NOVELTY_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "has_new": {
            "type": "boolean",
            "description": "האם יש תוכן חדש או עדכונים משמעותיים"
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "מזהה ייחודי לאירוע"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["new", "update", "duplicate"],
                        "description": "Event status in English"
                    },
                    "lede_he": {
                        "type": "string",
                        "description": "לידה בעברית - תקציר קצר"
                    },
                    "significance_he": {
                        "type": "string",
                        "description": "משמעות האירוע בעברית"
                    },
                    "what_changed_he": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "מה השתנה מהמידע הקודם"
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "ראיות מהכתבות החדשות"
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "רמת ביטחון בניתוח"
                    }
                },
                "required": ["event_id", "status", "lede_he", "significance_he", "what_changed_he", "evidence", "confidence"],
                "additionalProperties": False
            }
        },
        "bulletins_he": {
            "type": "string",
            "description": "עדכונים מרוכזים בעברית"
        }
    },
    "required": ["has_new", "items", "bulletins_he"],
    "additionalProperties": False
}

# Schema for notification decisions
NOTIFICATION_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "should_notify_now": {
            "type": "boolean",
            "description": "האם לשלוח התראה כעת"
        },
        "compact_push": {
            "type": "string",
            "description": "הודעת פוש קצרה (עד 60 תווים)"
        },
        "full_message": {
            "type": "string",
            "description": "הודעה מלאה לסלאק"
        },
        "reasoning": {
            "type": "string",
            "description": "נימוק להחלטה"
        },
        "urgency_level": {
            "type": "string",
            "enum": ["low", "normal", "high", "breaking"],
            "description": "רמת דחיפות"
        }
    },
    "required": ["should_notify_now", "compact_push", "full_message", "reasoning", "urgency_level"],
    "additionalProperties": False
}

def get_schema_by_type(analysis_type: str) -> Dict[str, Any]:
    """
    Get JSON schema by analysis type.
    
    Args:
        analysis_type: Type of analysis ("thematic", "thematic_with_notification", "novelty", "notification")
        
    Returns:
        JSON schema dictionary
        
    Raises:
        ValueError: If analysis_type is not recognized
    """
    schemas = {
        "thematic": THEMATIC_ANALYSIS_SCHEMA,
        "thematic_with_notification": THEMATIC_WITH_NOTIFICATION_SCHEMA,
        "novelty": NOVELTY_ANALYSIS_SCHEMA,
        "updates": NOVELTY_ANALYSIS_SCHEMA,  # Alias for novelty
        "notification": NOTIFICATION_DECISION_SCHEMA
    }
    
    if analysis_type not in schemas:
        raise ValueError(f"Unknown analysis type: {analysis_type}")
    
    return schemas[analysis_type]
