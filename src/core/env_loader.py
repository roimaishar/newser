#!/usr/bin/env python3
"""
Environment variable loader with .env file support.

Safely loads environment variables from .env file if present.
"""

import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_env_file(env_file_path: str = ".env") -> None:
    """
    Load environment variables from .env file if it exists.
    
    Args:
        env_file_path: Path to .env file (default: ".env" in project root)
    """
    # Find project root (where .env should be)
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent  # Go up to project root
    env_path = project_root / env_file_path
    
    if not env_path.exists():
        logger.debug(f"No .env file found at {env_path}")
        return
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        loaded_count = 0
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Parse KEY=VALUE format
            if '=' not in line:
                logger.warning(f"Invalid .env format at line {line_num}: {line}")
                continue
                
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            
            # Only set if not already in environment (env vars take precedence)
            if key not in os.environ:
                os.environ[key] = value
                loaded_count += 1
                logger.debug(f"Loaded {key} from .env")
            else:
                logger.debug(f"Skipped {key} (already in environment)")
        
        logger.info(f"Loaded {loaded_count} variables from {env_path}")
        
    except Exception as e:
        logger.error(f"Error loading .env file {env_path}: {e}")

def get_env_var(key: str, default: str = None, required: bool = False) -> str:
    """
    Get environment variable with optional default and required validation.
    
    Args:
        key: Environment variable name
        default: Default value if not found
        required: Whether the variable is required
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If required variable is missing
    """
    value = os.environ.get(key, default)
    
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set")
    
    return value

def validate_database_config() -> bool:
    """
    Validate that required database configuration is present.
    
    Returns:
        True if valid configuration found
        
    Raises:
        ValueError: If required configuration is missing
    """
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_DB_PASSWORD'
    ]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        raise ValueError(f"Missing required database environment variables: {', '.join(missing)}")
    
    # Validate URL format
    supabase_url = os.environ.get('SUPABASE_URL', '')
    if not supabase_url.startswith('https://') or not supabase_url.endswith('.supabase.co'):
        raise ValueError(f"Invalid SUPABASE_URL format. Expected: https://your-project.supabase.co")
    
    logger.info("Database configuration validated successfully")
    return True

def get_database_config() -> dict:
    """
    Get database configuration from environment variables.
    
    Returns:
        Dictionary with database configuration
    """
    return {
        'supabase_url': get_env_var('SUPABASE_URL', required=True),
        'supabase_password': get_env_var('SUPABASE_DB_PASSWORD', required=True),
        'supabase_anon_key': get_env_var('SUPABASE_ANON_KEY')  # Optional for direct DB access
    }

# Auto-load .env file when module is imported
load_env_file()