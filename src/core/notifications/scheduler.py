#!/usr/bin/env python3
"""
Notification Scheduler - Handles timing logic for smart notifications.

Provides programmatic scheduling for notifications based on predefined time slots
and urgency levels, separate from LLM decision-making.
"""

import logging
from datetime import datetime, time, timezone
from typing import Optional, List, Tuple
import pytz

logger = logging.getLogger(__name__)

# Israel timezone
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

# Peak Hours - Normal news allowed (up to 7 stories)
PEAK_HOURS = [
    time(8, 0),    # 08:00 - Morning peak
    time(12, 0),   # 12:00 - Lunch peak
    time(18, 0),   # 18:00 - Evening peak
]

# Predefined notification time slots (Israel time)
NOTIFICATION_SLOTS = [
    time(7, 30),   # 07:30
    time(8, 0),    # 08:00 - PEAK
    time(9, 0),    # 09:00  
    time(12, 0),   # 12:00 - PEAK
    time(15, 0),   # 15:00
    time(18, 0),   # 18:00 - PEAK
    time(19, 0),   # 19:00
    time(21, 0),   # 21:00
    time(23, 0),   # 23:00
]

# Hours considered "quiet" (avoid non-urgent notifications)
QUIET_HOURS_START = time(23, 30)
QUIET_HOURS_END = time(7, 0)

# Max stories per notification
MAX_STORIES_NORMAL = 5
MAX_STORIES_PEAK = 7


class NotificationScheduler:
    """Handles notification timing decisions separate from LLM content decisions."""
    
    def __init__(self, timezone_str: str = "Asia/Jerusalem"):
        """Initialize scheduler with timezone."""
        self.tz = pytz.timezone(timezone_str)
    
    def get_current_israel_time(self) -> datetime:
        """Get current time in Israel timezone."""
        return datetime.now(self.tz)
    
    def is_quiet_hours(self, check_time: Optional[datetime] = None) -> bool:
        """Check if current time is during quiet hours (23:30-07:00)."""
        if check_time is None:
            check_time = self.get_current_israel_time()
        
        current_time = check_time.time()
        
        # Handle overnight quiet period
        if QUIET_HOURS_START <= time(23, 59):  # Before midnight
            return current_time >= QUIET_HOURS_START or current_time <= QUIET_HOURS_END
        else:  # Shouldn't happen with our times, but handle gracefully
            return QUIET_HOURS_START <= current_time <= QUIET_HOURS_END
    
    def is_peak_hours(self, check_time: Optional[datetime] = None) -> bool:
        """Check if current time is during peak hours (8 AM, 12 PM, 6 PM)."""
        if check_time is None:
            check_time = self.get_current_israel_time()
        
        current_time = check_time.time()
        
        # Check if within 30 minutes of any peak hour
        for peak_time in PEAK_HOURS:
            # Create time window: peak_time ± 30 minutes
            peak_hour = peak_time.hour
            peak_minute = peak_time.minute
            
            # Check if current time is within the peak window
            if current_time.hour == peak_hour:
                return True
            # Also check 30 minutes before
            elif current_time.hour == peak_hour - 1 and current_time.minute >= 30:
                return True
            # And 30 minutes after
            elif current_time.hour == peak_hour + 1 and current_time.minute < 30:
                return True
        
        return False
    
    def get_max_stories_for_time(self, check_time: Optional[datetime] = None) -> int:
        """Get maximum stories allowed for current time."""
        if self.is_peak_hours(check_time):
            return MAX_STORIES_PEAK
        else:
            return MAX_STORIES_NORMAL
    
    def get_next_notification_slot(self, from_time: Optional[datetime] = None) -> datetime:
        """Get the next scheduled notification slot."""
        if from_time is None:
            from_time = self.get_current_israel_time()
        
        # Ensure we're working in Israel time
        if from_time.tzinfo != self.tz:
            from_time = from_time.astimezone(self.tz)
        
        current_time = from_time.time()
        current_date = from_time.date()
        
        # Find next slot today
        for slot_time in NOTIFICATION_SLOTS:
            if slot_time > current_time:
                return datetime.combine(current_date, slot_time, tzinfo=self.tz)
        
        # No more slots today, return first slot tomorrow
        next_day = datetime.combine(current_date, NOTIFICATION_SLOTS[0], tzinfo=self.tz)
        return next_day.replace(day=next_day.day + 1)
    
    def should_send_immediately(self, urgency_level: str = "normal") -> bool:
        """
        Decide if notification should be sent immediately based on urgency and time.
        
        Rules:
        - Breaking: Always immediate (24/7)
        - High/Urgent: Immediate during business hours (7 AM - 11 PM)
        - Normal: Only during peak hours (8 AM, 12 PM, 6 PM)
        - Low: Never immediate, always scheduled
        
        Args:
            urgency_level: "breaking", "high", "normal", "low"
        """
        current_time = self.get_current_israel_time()
        is_quiet = self.is_quiet_hours(current_time)
        is_peak = self.is_peak_hours(current_time)
        
        if urgency_level == "breaking":
            # Breaking news always sends immediately (24/7)
            return True
        elif urgency_level == "high":
            # High priority sends during business hours (not quiet hours)
            return not is_quiet
        elif urgency_level == "normal":
            # Normal priority ONLY during peak hours
            return is_peak and not is_quiet
        elif urgency_level == "low":
            # Low priority never sends immediately
            return False
        else:
            # Unknown urgency, be conservative - treat as high
            return not is_quiet
    
    def get_notification_decision(self, urgency_level: str = "normal") -> Tuple[bool, Optional[datetime]]:
        """
        Get complete notification timing decision.
        
        Returns:
            (should_send_now, scheduled_time)
            - If should_send_now=True, send immediately 
            - If should_send_now=False and scheduled_time is set, schedule for that time
            - If both False/None, don't send notification
        """
        if self.should_send_immediately(urgency_level):
            return True, None
        else:
            next_slot = self.get_next_notification_slot()
            return False, next_slot
    
    def format_time_since(self, since_time: datetime) -> str:
        """Format time difference in English for LLM context."""
        if since_time is None:
            return "no data"

        now = datetime.now(timezone.utc)
        if since_time.tzinfo is None:
            since_time = since_time.replace(tzinfo=timezone.utc)

        diff = now - since_time

        if diff.days > 0:
            days = diff.days
            unit = "day" if days == 1 else "days"
            return f"{days} {unit}"

        if diff.seconds >= 3600:
            hours = diff.seconds // 3600
            unit = "hour" if hours == 1 else "hours"
            return f"{hours} {unit}"

        if diff.seconds >= 60:
            minutes = diff.seconds // 60
            unit = "minute" if minutes == 1 else "minutes"
            return f"{minutes} {unit}"

        return "less than a minute"
    
    def get_stats(self) -> dict:
        """Get scheduler statistics for monitoring."""
        current_time = self.get_current_israel_time()
        next_slot = self.get_next_notification_slot()
        
        return {
            "current_israel_time": current_time.isoformat(),
            "is_quiet_hours": self.is_quiet_hours(),
            "is_peak_hours": self.is_peak_hours(),
            "max_stories_now": self.get_max_stories_for_time(),
            "next_notification_slot": next_slot.isoformat(),
            "notification_slots_count": len(NOTIFICATION_SLOTS),
            "peak_hours_count": len(PEAK_HOURS),
            "timezone": str(self.tz)
        }


# Convenience functions for easy use
def get_scheduler() -> NotificationScheduler:
    """Get default notification scheduler instance."""
    return NotificationScheduler()

def should_notify_now(urgency: str = "normal") -> bool:
    """Quick check if should send notification immediately."""
    scheduler = get_scheduler()
    send_now, _ = scheduler.get_notification_decision(urgency)
    return send_now

def format_time_since_last_notification(last_time: Optional[datetime]) -> str:
    """Format time since last notification for LLM."""
    scheduler = get_scheduler()
    return scheduler.format_time_since(last_time)