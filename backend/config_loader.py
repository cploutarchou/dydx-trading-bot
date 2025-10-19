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
            from app.config import config as load_config

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

        Priority:
        1. config.yaml (database section)
        2. Environment variables (DB_*)
        3. Defaults

        Returns:
            Dictionary with database settings
        """
        if self._config and hasattr(self._config, "database"):
            cfg = self._config.database
            return {
                "type": getattr(cfg, "type", os.getenv("DB_TYPE", "sqlite")),
                "name": getattr(cfg, "name", os.getenv("DB_NAME", "dydx_backtest.db")),
                "user": getattr(cfg, "user", os.getenv("DB_USER", "postgres")),
                "password": getattr(cfg, "password", os.getenv("DB_PASSWORD", "")),
                "host": getattr(cfg, "host", os.getenv("DB_HOST", "localhost")),
                "port": getattr(cfg, "port", os.getenv("DB_PORT", "5432")),
                "pool_size": getattr(
                    cfg, "pool_size", int(os.getenv("DB_POOL_SIZE", "5"))
                ),
                "max_overflow": getattr(
                    cfg, "max_overflow", int(os.getenv("DB_MAX_OVERFLOW", "10"))
                ),
                "timeout": getattr(cfg, "timeout", int(os.getenv("DB_TIMEOUT", "30"))),
            }

        # Fallback to environment variables
        return {
            "type": os.getenv("DB_TYPE", "sqlite"),
            "name": os.getenv("DB_NAME", "dydx_backtest.db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "timeout": int(os.getenv("DB_TIMEOUT", "30")),
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
