#!/usr/bin/env python3
"""
News Aggregator - Legacy Entry Point (Backward Compatibility)

This module provides backward compatibility for the original main.py interface.
New code should use the cli_router.py system directly.

Fetches and deduplicates news from Israeli news sources (Ynet, Walla).
"""

import logging
import sys
import warnings
from typing import List

# Import formatters from the new location for backward compatibility
from core.formatters import format_article, articles_to_dict, format_hebrew_analysis

# Import CLI router for delegation
from cli_router import CLIRouter

def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration (legacy compatibility)."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# These functions are now imported from core.formatters for backward compatibility
# format_article, articles_to_dict, format_hebrew_analysis

def _convert_legacy_args_to_new_format(args):
    """
    Convert legacy command-line arguments to new CLI router format.
    
    Maps the old main.py argument structure to the new command structure:
    - Basic fetch: args -> ['news', 'fetch', ...]
    - With Hebrew analysis: args + --hebrew -> ['news', 'analyze', ...]
    - State operations: args + --state-stats -> ['state', 'stats']
    """
    new_args = []
    
    # Handle special state operations first
    if getattr(args, 'state_stats', False):
        return ['state', 'stats']
    elif getattr(args, 'reset_state', False):
        new_args = ['state', 'reset']
        if getattr(args, 'force', False):
            new_args.append('--force')
        return new_args
    elif getattr(args, 'test_integrations', False):
        return ['integrations', 'test']
    
    # Handle news operations
    if getattr(args, 'hebrew', False):
        # Hebrew mode = news analyze (legacy compatibility)
        new_args = ['news', 'analyze']
        if getattr(args, 'updates_only', False):
            new_args.append('--updates-only')
    else:
        # Basic mode = news fetch (now includes analysis by default)
        new_args = ['news', 'fetch']
    
    # Add common arguments
    if hasattr(args, 'hours'):
        new_args.extend(['--hours', str(args.hours)])
    if getattr(args, 'verbose', False):
        new_args.append('--verbose')
    if getattr(args, 'no_dedupe', False):
        new_args.append('--no-dedupe')
    if hasattr(args, 'similarity'):
        new_args.extend(['--similarity', str(args.similarity)])
    if getattr(args, 'slack', False):
        new_args.append('--slack')
    
    return new_args

def main():
    """
    Legacy main function for backward compatibility.
    
    This function maintains the old command-line interface while delegating
    to the new CLI router system. It translates old arguments to new format.
    
    DEPRECATED: New code should use cli_router.main() directly.
    """
    warnings.warn(
        "main.py is deprecated. Use 'python run.py' with the new command structure. "
        "See CLAUDE.md for updated usage examples.",
        DeprecationWarning,
        stacklevel=2
    )
    
    import argparse
    
    # Create parser that matches the old interface
    parser = argparse.ArgumentParser(description='Israeli News Aggregator (Legacy Mode)')
    parser.add_argument('--hours', type=int, default=24, 
                       help='Hours to look back for articles (default: 24)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--no-dedupe', action='store_true',
                       help='Skip deduplication step')
    parser.add_argument('--similarity', type=float, default=0.8,
                       help='Similarity threshold for deduplication (0-1, default: 0.8)')
    parser.add_argument('--slack', action='store_true',
                       help='Send results to Slack (requires SLACK_WEBHOOK_URL)')
    parser.add_argument('--test-integrations', action='store_true',
                       help='Test OpenAI and Slack integrations')
    
    # Hebrew analysis options
    parser.add_argument('--hebrew', action='store_true',
                       help='Enable Hebrew-first analysis with novelty detection')
    parser.add_argument('--updates-only', action='store_true',
                       help='Show only new/updated items (requires --hebrew)')
    # Legacy argument for backward compatibility (now uses database)
    parser.add_argument('--state-file', type=str, default=None,
                       help='[DEPRECATED] State now stored in database')
    parser.add_argument('--reset-state', action='store_true',
                       help='Reset known events state (requires --hebrew)')
    parser.add_argument('--state-stats', action='store_true',
                       help='Show state statistics and exit')
    
    args = parser.parse_args()
    
    # Set up logging for legacy compatibility
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    logger.info("Using legacy main.py interface - consider migrating to new CLI structure")
    
    try:
        # Convert legacy arguments to new CLI router format
        new_args = _convert_legacy_args_to_new_format(args)
        
        # Delegate to CLI router
        router = CLIRouter()
        return router.route_command(new_args)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Legacy interface error: {e}", exc_info=args.verbose)
        return 1

if __name__ == "__main__":
    sys.exit(main())