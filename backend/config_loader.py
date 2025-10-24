"""
Configuration loader that reads from config.yaml for database and Redis settings.
Provides centralized configuration management for backend services.
"""

import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


class ConfigurationLoader:
    """Loads database and Redis configuration from config.yaml and environment variables."""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is not None:
            return

        try:
            from backend.app.config import config as load_config

            cfg = load_config()
            self._config = cfg
            logger.info("Configuration loaded from config.yaml")
        except ImportError:
            logger.warning(
                "Could not load config.yaml, using environment variables only"
            )
            self._config = None

    def get_database_config(self) -> Dict[str, str]:
        """Get database configuration from config.yaml or environment.

        Priority (IMPORTANT - Environment variables override config.yaml):
        1. Environment variables (DB_*) ← **HIGHEST PRIORITY**
        2. config.yaml (database section)
        3. Defaults

        This allows .env files to override config.yaml settings for deployment flexibility.

        Returns:
            Dictionary with database settings
        """
        # Check environment variables FIRST for the highest priority
        env_type = os.getenv("DB_TYPE")
        env_name = os.getenv("DB_NAME")
        env_user = os.getenv("DB_USER")
        env_password = os.getenv("DB_PASSWORD")
        env_host = os.getenv("DB_HOST")
        env_port = os.getenv("DB_PORT")
        env_pool_size = os.getenv("DB_POOL_SIZE")
        env_max_overflow = os.getenv("DB_MAX_OVERFLOW")
        env_timeout = os.getenv("DB_TIMEOUT")

        # Get config.yaml values as fallback
        config_type = None
        config_name = None
        config_user = None
        config_password = None
        config_host = None
        config_port = None
        config_pool_size = None
        config_max_overflow = None
        config_timeout = None

        if self._config and hasattr(self._config, "database"):
            cfg = self._config.database
            config_type = getattr(cfg, "type", None)
            config_name = getattr(cfg, "name", None)
            config_user = getattr(cfg, "user", None)
            config_password = getattr(cfg, "password", None)
            config_host = getattr(cfg, "host", None)
            config_port = getattr(cfg, "port", None)
            config_pool_size = getattr(cfg, "pool_size", None)
            config_max_overflow = getattr(cfg, "max_overflow", None)
            config_timeout = getattr(cfg, "timeout", None)

        # Environment variables override config.yaml, which override defaults
        return {
            "type": env_type or config_type or "sqlite",
            "name": env_name or config_name or "dydx_backtest.db",
            "user": env_user or config_user or "postgres",
            "password": env_password or config_password or "",
            "host": env_host or config_host or "localhost",
            "port": env_port or config_port or "5432",
            "pool_size": int(env_pool_size or config_pool_size or 5),
            "max_overflow": int(env_max_overflow or config_max_overflow or 10),
            "timeout": int(env_timeout or config_timeout or 30),
        }

    def get_redis_config(self) -> Dict:
        """Get Redis configuration from config.yaml or environment.

        Priority:
        1. config.yaml (redis section)
        2. Environment variables (REDIS_*)
        3. Defaults

        Returns:
            Dictionary with Redis settings
        """
        if self._config and hasattr(self._config, "redis"):
            cfg = self._config.redis
            return {
                "enabled": getattr(
                    cfg, "enabled", os.getenv("REDIS_ENABLED", "true").lower() == "true"
                ),
                "host": getattr(cfg, "host", os.getenv("REDIS_HOST", "localhost")),
                "port": int(getattr(cfg, "port", os.getenv("REDIS_PORT", "6379"))),
                "db": int(getattr(cfg, "db", os.getenv("REDIS_DB", "0"))),
                "password": getattr(cfg, "password", os.getenv("REDIS_PASSWORD", None)),
                "ssl": getattr(
                    cfg, "ssl", os.getenv("REDIS_SSL", "false").lower() == "true"
                ),
                "timeout": int(
                    getattr(cfg, "timeout", os.getenv("REDIS_TIMEOUT", "5"))
                ),
                "cache_ttl_seconds": int(
                    getattr(
                        cfg, "cache_ttl_seconds", os.getenv("REDIS_CACHE_TTL", "86400")
                    )
                ),
                "max_connections": int(
                    getattr(
                        cfg,
                        "max_connections",
                        os.getenv("REDIS_MAX_CONNECTIONS", "10"),
                    )
                ),
            }

        # Fallback to environment variables
        return {
            "enabled": os.getenv("REDIS_ENABLED", "true").lower() == "true",
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": int(os.getenv("REDIS_DB", "0")),
            "password": os.getenv("REDIS_PASSWORD", None),
            "ssl": os.getenv("REDIS_SSL", "false").lower() == "true",
            "timeout": int(os.getenv("REDIS_TIMEOUT", "5")),
            "cache_ttl_seconds": int(os.getenv("REDIS_CACHE_TTL", "86400")),
            "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
        }

    def get_all_config(self) -> Dict:
        """Get all backend configuration.

        Returns:
            Dictionary with all settings (database, redis, etc.)
        """
        return {
            "database": self.get_database_config(),
            "redis": self.get_redis_config(),
        }


# Singleton instance
_config_loader = ConfigurationLoader()


def get_config_loader() -> ConfigurationLoader:
    """Get configuration loader singleton."""
    return _config_loader
