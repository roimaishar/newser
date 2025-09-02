#!/usr/bin/env python3
"""
Notification channels for different delivery methods.

Supports Slack, email, push notifications, and other channels.
"""

from .slack import SlackNotifier

__all__ = ['SlackNotifier']