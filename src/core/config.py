#!/usr/bin/env python3
"""
Centralized Configuration Manager

Provides a single source of truth for all application configuration,
including environment variables, defaults, and validation.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    supabase_url: str
    supabase_db_password: str
    supabase_anon_key: Optional[str] = None
    supabase_service_key: Optional[str] = None
    connection_timeout: int = 30
    max_retries: int = 3


@dataclass  
class IntegrationConfig:
    """External integration configuration."""
    openai_api_key: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    slack_bot_token: Optional[str] = None
    # Push notification configs
    onesignal_api_key: Optional[str] = None
    onesignal_app_id: Optional[str] = None
    firebase_server_key: Optional[str] = None


@dataclass
class ApplicationConfig:
    """Core application configuration."""
    # RSS feed settings
    feed_timeout: int = 10
    feed_user_agent: str = "Mozilla/5.0 (compatible; NewsAggregator/1.0)"
    max_concurrent_feeds: int = 5
    
    # Processing settings
    default_hours_window: int = 24
    default_similarity_threshold: float = 0.8
    max_articles_per_run: int = 1000
    
    # Cache settings (in-memory only)
    feed_cache_ttl_seconds: int = 900  # 15 minutes
    analysis_cache_ttl_seconds: int = 3600  # 1 hour
    
    # Security settings
    max_title_length: int = 500
    max_summary_length: int = 2000
    max_url_length: int = 2048
    
    # Logging
    log_level: str = "INFO"
    verbose_logging: bool = False


@dataclass
class Config:
    """Master configuration container."""
    database: DatabaseConfig
    integrations: IntegrationConfig
    app: ApplicationConfig
    
    # Environment info
    environment: str = field(default_factory=lambda: os.getenv('ENVIRONMENT', 'development'))
    is_ci: bool = field(default_factory=lambda: bool(os.getenv('CI') or os.getenv('GITHUB_ACTIONS')))
    
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() in ['dev', 'development', 'local']
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() in ['prod', 'production']
    
    def has_openai(self) -> bool:
        """Check if OpenAI integration is available."""
        return bool(self.integrations.openai_api_key)
    
    def has_slack(self) -> bool:
        """Check if Slack integration is available."""
        return bool(self.integrations.slack_webhook_url or self.integrations.slack_bot_token)


class ConfigManager:
    """Manages application configuration with validation and environment loading."""
    
    def __init__(self, env_file_path: str = ".env"):
        """
        Initialize configuration manager.
        
        Args:
            env_file_path: Path to .env file relative to project root
        """
        self._config: Optional[Config] = None
        self._env_file_path = env_file_path
        self._load_environment()
    
    def _load_environment(self) -> None:
        """Load environment variables from .env file."""
        # Find project root (where .env should be)
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent  # Go up to project root
        env_path = project_root / self._env_file_path
        
        if env_path.exists():
            self._load_env_file(env_path)
        else:
            logger.debug(f"No .env file found at {env_path}")
    
    def _load_env_file(self, env_path: Path) -> None:
        """Load variables from .env file."""
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
    
    def get_config(self, force_reload: bool = False) -> Config:
        """
        Get application configuration.
        
        Args:
            force_reload: Force reloading configuration from environment
            
        Returns:
            Complete configuration object
        """
        if self._config is None or force_reload:
            self._config = self._build_config()
        return self._config
    
    def _build_config(self) -> Config:
        """Build configuration from environment variables."""
        
        # Database configuration (required)
        database_config = DatabaseConfig(
            supabase_url=self._get_required_env('SUPABASE_URL'),
            supabase_db_password=self._get_required_env('SUPABASE_DB_PASSWORD'),
            supabase_anon_key=os.getenv('SUPABASE_ANON_KEY'),
            supabase_service_key=os.getenv('SUPABASE_SERVICE_KEY'),
            connection_timeout=int(os.getenv('DB_CONNECTION_TIMEOUT', '30')),
            max_retries=int(os.getenv('DB_MAX_RETRIES', '3'))
        )
        
        # Integration configuration (optional)
        integration_config = IntegrationConfig(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            slack_webhook_url=os.getenv('SLACK_WEBHOOK_URL'),
            slack_bot_token=os.getenv('SLACK_BOT_TOKEN'),
            onesignal_api_key=os.getenv('ONESIGNAL_API_KEY'),
            onesignal_app_id=os.getenv('ONESIGNAL_APP_ID'),
            firebase_server_key=os.getenv('FIREBASE_SERVER_KEY')
        )
        
        # Application configuration
        app_config = ApplicationConfig(
            feed_timeout=int(os.getenv('FEED_TIMEOUT', '10')),
            feed_user_agent=os.getenv('FEED_USER_AGENT', 'Mozilla/5.0 (compatible; NewsAggregator/1.0)'),
            max_concurrent_feeds=int(os.getenv('MAX_CONCURRENT_FEEDS', '5')),
            default_hours_window=int(os.getenv('DEFAULT_HOURS_WINDOW', '24')),
            default_similarity_threshold=float(os.getenv('DEFAULT_SIMILARITY_THRESHOLD', '0.8')),
            max_articles_per_run=int(os.getenv('MAX_ARTICLES_PER_RUN', '1000')),
            feed_cache_ttl_seconds=int(os.getenv('FEED_CACHE_TTL', '900')),
            analysis_cache_ttl_seconds=int(os.getenv('ANALYSIS_CACHE_TTL', '3600')),
            max_title_length=int(os.getenv('MAX_TITLE_LENGTH', '500')),
            max_summary_length=int(os.getenv('MAX_SUMMARY_LENGTH', '2000')),
            max_url_length=int(os.getenv('MAX_URL_LENGTH', '2048')),
            log_level=os.getenv('LOG_LEVEL', 'INFO').upper(),
            verbose_logging=os.getenv('VERBOSE_LOGGING', 'false').lower() == 'true'
        )
        
        config = Config(
            database=database_config,
            integrations=integration_config,
            app=app_config
        )
        
        self._validate_config(config)
        return config
    
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    def _validate_config(self, config: Config) -> None:
        """Validate configuration values."""
        errors = []
        
        # Validate database URL format
        if not config.database.supabase_url.startswith('https://'):
            errors.append("SUPABASE_URL must start with https://")
        
        if not config.database.supabase_url.endswith('.supabase.co'):
            errors.append("SUPABASE_URL must end with .supabase.co")
        
        # Validate numeric ranges
        if config.app.default_similarity_threshold < 0 or config.app.default_similarity_threshold > 1:
            errors.append("DEFAULT_SIMILARITY_THRESHOLD must be between 0 and 1")
        
        if config.app.feed_timeout < 1:
            errors.append("FEED_TIMEOUT must be at least 1 second")
        
        if config.app.max_concurrent_feeds < 1 or config.app.max_concurrent_feeds > 20:
            errors.append("MAX_CONCURRENT_FEEDS must be between 1 and 20")
        
        if config.app.max_articles_per_run < 1:
            errors.append("MAX_ARTICLES_PER_RUN must be at least 1")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if config.app.log_level not in valid_log_levels:
            errors.append(f"LOG_LEVEL must be one of: {', '.join(valid_log_levels)}")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        
        logger.info("Configuration validation passed")
    
    def get_database_connection_string(self) -> str:
        """Get PostgreSQL connection string for Supabase."""
        config = self.get_config()
        
        # Extract host from URL
        url = config.database.supabase_url
        if not url.startswith('https://'):
            raise ValueError(f"Invalid Supabase URL format: {url}")
        
        host = url.replace('https://', '')
        password = config.database.supabase_db_password
        
        # Use connection pooling port 6543 for better reliability
        return f"postgresql://postgres:{password}@{host}:6543/postgres?sslmode=require"
    
    def update_logging(self) -> None:
        """Configure logging based on current configuration."""
        config = self.get_config()
        
        # Set log level
        numeric_level = getattr(logging, config.app.log_level)
        logging.getLogger().setLevel(numeric_level)
        
        # Configure format
        if config.app.verbose_logging:
            format_str = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        else:
            format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Update existing handlers
        for handler in logging.getLogger().handlers:
            handler.setLevel(numeric_level)
            formatter = logging.Formatter(format_str, datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
    
    def get_integration_status(self) -> Dict[str, bool]:
        """Get status of all integrations."""
        config = self.get_config()
        return {
            'openai': config.has_openai(),
            'slack_webhook': bool(config.integrations.slack_webhook_url),
            'slack_bot': bool(config.integrations.slack_bot_token),
            'onesignal': bool(config.integrations.onesignal_api_key and config.integrations.onesignal_app_id),
            'firebase': bool(config.integrations.firebase_server_key)
        }


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> Config:
    """Get application configuration."""
    return get_config_manager().get_config()


def reset_config() -> None:
    """Reset configuration manager (useful for testing)."""
    global _config_manager
    _config_manager = None