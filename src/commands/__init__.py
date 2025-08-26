#!/usr/bin/env python3
"""
Smart command endpoints for the news aggregator.

This module provides a scalable command architecture where each major
functionality is handled by dedicated command classes.
"""

from typing import Dict, Type
from .base import BaseCommand
from .news import NewsCommand
from .state import StateCommand
from .data import DataCommand
from .integrations import IntegrationsCommand

# Command registry for easy extension
COMMANDS: Dict[str, Type[BaseCommand]] = {
    'news': NewsCommand,
    'state': StateCommand,
    'data': DataCommand,
    'integrations': IntegrationsCommand,
}

def get_command(command_name: str) -> BaseCommand:
    """Get a command instance by name."""
    if command_name not in COMMANDS:
        available = ', '.join(COMMANDS.keys())
        raise ValueError(f"Unknown command '{command_name}'. Available: {available}")
    
    command_class = COMMANDS[command_name]
    return command_class()

def list_commands() -> Dict[str, str]:
    """Get list of available commands with descriptions."""
    commands = {}
    for name, command_class in COMMANDS.items():
        commands[name] = getattr(command_class, '__doc__', 'No description available')
    return commands