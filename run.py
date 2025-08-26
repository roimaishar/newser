#!/usr/bin/env python3
"""
Entry point for the news aggregator with smart CLI routing.
"""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli_router import main

if __name__ == "__main__":
    sys.exit(main())