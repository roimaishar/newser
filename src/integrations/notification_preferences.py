#!/usr/bin/env python3
"""
User notification preferences management.

Handles user-specific notification settings, frequency controls, and format preferences.
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, time
from pathlib import Path

class NotificationPreferences:
    """Manages user notification preferences."""
    
    def __init__(self, config_file: str = "notification_preferences.json"):
        self.config_file = Path(config_file)
        self.preferences = self._load_preferences()
    
    def _load_preferences(self) -> Dict[str, Any]:
        """Load preferences from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Default preferences
        return {
            "push": {
                "enabled": True,
                "format": "topic",  # headlines, topic, urgent, minimal
                "frequency": "hourly",  # immediate, hourly, daily, breaking_only
                "quiet_hours": {"start": "22:00", "end": "07:00"},
                "urgency_threshold": 6  # 1-10 scale
            },
            "slack": {
                "enabled": True,
                "format": "headlines_first",  # headlines_first, executive, expandable
                "frequency": "hourly",
                "channel_override": None,
                "thread_replies": False
            },
            "topics": {
                "security": True,
                "politics": True,
                "economy": True,
                "international": True,
                "exclude_keywords": []
            },
            "delivery": {
                "max_per_hour": 5,
                "batch_similar": True,
                "retry_failed": True
            }
        }
    
    def save_preferences(self) -> bool:
        """Save preferences to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.preferences, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def get_push_preferences(self) -> Dict[str, Any]:
        """Get push notification preferences."""
        return self.preferences.get("push", {})
    
    def get_slack_preferences(self) -> Dict[str, Any]:
        """Get Slack notification preferences."""
        return self.preferences.get("slack", {})
    
    def should_send_now(self, urgency_score: int, channel: str = "push") -> bool:
        """Check if notification should be sent now."""
        prefs = self.preferences.get(channel, {})
        
        if not prefs.get("enabled", True):
            return False
        
        # Check urgency threshold
        threshold = prefs.get("urgency_threshold", 6)
        if urgency_score < threshold:
            return False
        
        # Check quiet hours
        if channel == "push" and not self._is_outside_quiet_hours(urgency_score):
            return False
        
        # Check frequency limits
        if not self._check_frequency_limit(channel):
            return False
        
        return True
    
    def _is_outside_quiet_hours(self, urgency_score: int) -> bool:
        """Check if current time is outside quiet hours."""
        quiet_hours = self.preferences["push"].get("quiet_hours", {})
        
        # Critical news overrides quiet hours
        if urgency_score >= 8:
            return True
        
        if not quiet_hours:
            return True
        
        try:
            start_time = time.fromisoformat(quiet_hours["start"])
            end_time = time.fromisoformat(quiet_hours["end"])
            current_time = datetime.now().time()
            
            if start_time <= end_time:
                # Same day quiet hours
                return not (start_time <= current_time <= end_time)
            else:
                # Overnight quiet hours
                return not (current_time >= start_time or current_time <= end_time)
        except Exception:
            return True
    
    def _check_frequency_limit(self, channel: str) -> bool:
        """Check if frequency limit allows sending."""
        # This would track actual sending history
        # For now, always allow
        return True
    
    def update_preference(self, path: str, value: Any) -> bool:
        """Update a specific preference."""
        try:
            keys = path.split('.')
            current = self.preferences
            
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            current[keys[-1]] = value
            return self.save_preferences()
        except Exception:
            return False
    
    def get_format_for_context(self, channel: str, urgency_score: int, article_count: int) -> str:
        """Get optimal format based on context."""
        prefs = self.preferences.get(channel, {})
        base_format = prefs.get("format", "topic" if channel == "push" else "headlines_first")
        
        # Override based on urgency
        if channel == "push":
            if urgency_score >= 8:
                return "urgent"
            elif urgency_score >= 6 and article_count <= 3:
                return "headlines"
            else:
                return base_format
        else:  # slack
            if urgency_score >= 8:
                return "headlines_first"
            elif article_count >= 7:
                return "expandable"
            else:
                return base_format
