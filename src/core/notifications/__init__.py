#!/usr/bin/env python3
"""
Notification system for news alerts and updates.

Provides unified interface for different notification channels and
smart notification scheduling.
"""

from .smart_notifier import SmartNotifier, create_smart_notifier
from .scheduler import NotificationScheduler
from .channels.slack import SlackNotifier

__all__ = [
    'SmartNotifier', 'create_smart_notifier',
    'NotificationScheduler', 'SlackNotifier'
]