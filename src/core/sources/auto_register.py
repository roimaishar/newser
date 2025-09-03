#!/usr/bin/env python3
"""
Auto-registration of all available news sources.

Import this module to automatically register all built-in sources.
"""

import logging
from .registry import register_source
from .rss.ynet import YnetSource
from .rss.walla import WallaSource
from .rss.globes import GlobesSource
from .rss.haaretz import HaaretzSource

logger = logging.getLogger(__name__)


def register_all_sources():
    """Register all built-in news sources."""
    sources_to_register = [
        (YnetSource, 'ynet'),
        (WallaSource, 'walla'),
        (GlobesSource, 'globes'),
        (HaaretzSource, 'haaretz'),
    ]
    
    for source_class, name in sources_to_register:
        try:
            register_source(source_class, name)
            logger.info(f"Registered source: {name}")
        except Exception as e:
            logger.error(f"Failed to register source {name}: {e}")


# Auto-register on import
register_all_sources()