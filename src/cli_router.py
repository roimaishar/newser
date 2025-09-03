#!/usr/bin/env python3
"""
Smart CLI Router for the News Aggregator.

Modern modular command architecture for news aggregation.
"""

import argparse
import logging
import sys
from typing import Optional, List

# Load environment variables first
import core.env_loader  # Auto-loads .env file

from commands import get_command, list_commands, COMMANDS

logger = logging.getLogger(__name__)


class CLIRouter:
    """
    Modern CLI router for news aggregation commands.
    
    Command structure:
    - python run.py news fetch --hours 6 --verbose  
    - python run.py news analyze --hours 6 --slack
    - python run.py state stats
    - python run.py data cleanup --days 30
    """
    
    def __init__(self):
        """Initialize CLI router."""
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser."""
        parser = argparse.ArgumentParser(
            description="Israeli News Aggregator with Hebrew Analysis",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._get_examples_text()
        )
        
        # Add subparsers for new command structure
        subparsers = parser.add_subparsers(
            dest='command',
            help='Available commands',
            metavar='{command}'
        )
        
        # Create subparsers for each command
        self._add_news_parser(subparsers)
        self._add_state_parser(subparsers)
        self._add_data_parser(subparsers)
        self._add_integrations_parser(subparsers)
        self._add_health_parser(subparsers)
        
        
        return parser
    
    def _add_news_parser(self, subparsers):
        """Add news command parser."""
        news_parser = subparsers.add_parser(
            'news',
            help='News fetching, analysis, and summary operations'
        )
        
        news_subparsers = news_parser.add_subparsers(
            dest='subcommand',
            help='News operations',
            metavar='{fetch,analyze,summary}'
        )
        
        # Fetch subcommand
        fetch_parser = news_subparsers.add_parser('fetch', help='Fetch and analyze news articles from RSS feeds')
        fetch_parser.add_argument('--hours', type=int, default=1, help='Hours to look back (default: 1 for GitHub Actions)')
        fetch_parser.add_argument('--sources', nargs='+', choices=['ynet', 'walla', 'globes', 'haaretz', 'all'], default=['all'], help='News sources to fetch from (default: all)')
        fetch_parser.add_argument('--similarity', type=float, default=0.8, help='Similarity threshold for deduplication (default: 0.8)')
        fetch_parser.add_argument('--no-dedupe', action='store_true', help='Skip deduplication')
        fetch_parser.add_argument('--no-analysis', action='store_true', help='Skip Hebrew AI analysis (analysis is now default)')
        fetch_parser.add_argument('--updates-only', action='store_true', help='Show only new/updated content')
        fetch_parser.add_argument('--no-slack', action='store_true', help='Skip Slack notifications (Slack is default for GitHub Actions)')
        fetch_parser.add_argument('--async', dest='async_fetch', action='store_true', help='Use async RSS fetching for better performance')
        fetch_parser.add_argument('--verbose', action='store_true', help='Verbose output')
        
        # Analyze subcommand
        analyze_parser = news_subparsers.add_parser('analyze', help='Analyze articles with Hebrew AI analysis')
        analyze_parser.add_argument('--hours', type=int, default=1, help='Hours to look back (default: 1 for GitHub Actions)')
        analyze_parser.add_argument('--sources', nargs='+', choices=['ynet', 'walla', 'globes', 'haaretz', 'all'], default=['all'], help='News sources to fetch from (default: all)')
        analyze_parser.add_argument('--similarity', type=float, default=0.8, help='Similarity threshold for deduplication (default: 0.8)')
        analyze_parser.add_argument('--no-dedupe', action='store_true', help='Skip deduplication')
        analyze_parser.add_argument('--async', dest='async_fetch', action='store_true', help='Use async RSS fetching for better performance')
        analyze_parser.add_argument('--updates-only', action='store_true', help='Show only new/updated content')
        analyze_parser.add_argument('--no-slack', action='store_true', help='Skip Slack notifications (Slack is default for GitHub Actions)')
        analyze_parser.add_argument('--state-file', default=None, help='[DEPRECATED] State now stored in database')
        analyze_parser.add_argument('--verbose', action='store_true', help='Verbose output')
        
        # Summary subcommand
        summary_parser = news_subparsers.add_parser('summary', help='Show summary of recent news activity')
        summary_parser.add_argument('--days', type=int, default=3, help='Days to include in summary (default: 3)')
    
    def _add_state_parser(self, subparsers):
        """Add state command parser."""
        state_parser = subparsers.add_parser(
            'state',
            help='State management operations'
        )
        
        state_subparsers = state_parser.add_subparsers(
            dest='subcommand',
            help='State operations',
            metavar='{stats,cleanup,reset}'
        )
        
        # Stats subcommand
        stats_parser = state_subparsers.add_parser('stats', help='Show state statistics')
        stats_parser.add_argument('--state-file', default=None, help='[DEPRECATED] State now stored in database')
        
        # Cleanup subcommand
        cleanup_parser = state_subparsers.add_parser('cleanup', help='Clean up old events')
        cleanup_parser.add_argument('--days', type=int, default=30, help='Remove events older than N days (default: 30)')
        cleanup_parser.add_argument('--state-file', default=None, help='[DEPRECATED] State now stored in database')
        
        # Reset subcommand
        reset_parser = state_subparsers.add_parser('reset', help='Reset state (clear all known events)')
        reset_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
        reset_parser.add_argument('--state-file', default=None, help='[DEPRECATED] State now stored in database')
    
    def _add_data_parser(self, subparsers):
        """Add data command parser."""
        data_parser = subparsers.add_parser(
            'data',
            help='Data management operations'
        )
        
        data_subparsers = data_parser.add_subparsers(
            dest='subcommand',
            help='Data operations',
            metavar='{stats,cleanup,export,recent}'
        )
        
        # Stats subcommand
        stats_parser = data_subparsers.add_parser('stats', help='Show data storage statistics')
        
        # Cleanup subcommand
        cleanup_parser = data_subparsers.add_parser('cleanup', help='Clean up old data files')
        cleanup_parser.add_argument('--days', type=int, default=30, help='Remove files older than N days (default: 30)')
        
        # Export subcommand
        export_parser = data_subparsers.add_parser('export', help='Export data to different formats')
        export_parser.add_argument('--format', choices=['csv', 'json'], default='json', help='Export format')
        export_parser.add_argument('--days', type=int, default=7, help='Days to include (default: 7)')
        
        # Recent subcommand
        recent_parser = data_subparsers.add_parser('recent', help='Show recent data activity')
        recent_parser.add_argument('--days', type=int, default=3, help='Days to show (default: 3)')
        recent_parser.add_argument('--type', choices=['articles', 'analyses'], default='articles', help='Data type to show')
        recent_parser.add_argument('--verbose', action='store_true', help='Show detailed information')
    
    def _add_integrations_parser(self, subparsers):
        """Add integrations command parser."""
        integrations_parser = subparsers.add_parser(
            'integrations',
            help='External integration management'
        )
        
        integrations_subparsers = integrations_parser.add_subparsers(
            dest='subcommand',
            help='Integration operations',
            metavar='{test,slack,openai,status}'
        )
        
        # Test subcommand
        test_parser = integrations_subparsers.add_parser('test', help='Test all integrations')
        
        # Slack subcommand
        slack_parser = integrations_subparsers.add_parser('slack', help='Slack integration management')
        slack_parser.add_argument('--action', choices=['test', 'send'], default='test', help='Action to perform')
        slack_parser.add_argument('--message', help='Message to send (for send action)')
        
        # OpenAI subcommand
        openai_parser = integrations_subparsers.add_parser('openai', help='OpenAI integration management')
        openai_parser.add_argument('--action', choices=['test', 'analyze'], default='test', help='Action to perform')
        openai_parser.add_argument('--text', help='Text to analyze (for analyze action)')
        
        # Status subcommand
        status_parser = integrations_subparsers.add_parser('status', help='Show integration status')
    
    def _add_health_parser(self, subparsers):
        """Add health command parser."""
        health_parser = subparsers.add_parser(
            'health',
            help='System health monitoring and diagnostics'
        )
        
        health_subparsers = health_parser.add_subparsers(
            dest='subcommand',
            help='Health operations',
            metavar='{check,database,integrations}'
        )
        
        # General health check
        check_parser = health_subparsers.add_parser('check', help='Run comprehensive health check')
        
        # Database health check
        database_parser = health_subparsers.add_parser('database', help='Check database health')
        
        # Integrations health check
        integrations_parser = health_subparsers.add_parser('integrations', help='Check integration health')
        integrations_parser.add_argument('--test', action='store_true', help='Test actual connections')
    
    def _get_examples_text(self) -> str:
        """Get examples text for help."""
        return """
Examples:
  # Default GitHub Actions mode (1 hour, Slack enabled, AI analysis)
  python run.py news fetch
  python run.py news analyze
  
  # Manual runs with custom settings
  python run.py news fetch --hours 6 --verbose --no-slack  # Local testing
  python run.py news fetch --hours 24 --async              # Longer timeframe
  python run.py news fetch --no-analysis                   # Skip AI analysis
  
  # Other commands
  python run.py state stats
  python run.py data cleanup --days 30
  python run.py integrations test
  python run.py health check
  
"""
    
    def route_command(self, args: Optional[List[str]] = None) -> int:
        """
        Route command to appropriate handler.
        
        Args:
            args: Command line arguments (uses sys.argv if None)
            
        Returns:
            Exit code
        """
        try:
            if args is None:
                args = sys.argv[1:]
            
            parsed_args = self.parser.parse_args(args)
            
            # Handle command structure
            if not parsed_args.command:
                self.parser.print_help()
                return 1
                
            return self._handle_command(parsed_args)
            
        except SystemExit as e:
            # argparse calls sys.exit() on error or help
            return e.code if e.code is not None else 0
        except Exception as e:
            logger.error(f"CLI routing error: {e}", exc_info=True)
            return 1
    
    
    def _handle_command(self, args: argparse.Namespace) -> int:
        """Handle command structure."""
        logger.debug(f"Handling command: {args.command}")
        
        if args.command not in COMMANDS:
            available = ', '.join(COMMANDS.keys())
            logger.error(f"Unknown command '{args.command}'. Available: {available}")
            return 1
        
        # Get subcommand
        subcommand = getattr(args, 'subcommand', None)
        if not subcommand:
            logger.error(f"No subcommand specified for '{args.command}'")
            self.parser.parse_args([args.command, '--help'])  # Show help
            return 1
        
        # Execute command
        try:
            command = get_command(args.command)
            return command.execute(subcommand, args)
        except Exception as e:
            logger.error(f"Error executing {args.command} {subcommand}: {e}", exc_info=True)
            return 1


def main(args: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point.
    
    Args:
        args: Command line arguments (uses sys.argv if None)
        
    Returns:
        Exit code
    """
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and use router
    router = CLIRouter()
    return router.route_command(args)


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)