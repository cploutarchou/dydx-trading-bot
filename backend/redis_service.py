"""
Redis cache service for backtest results and application caching.
Provides connection management, health checks, and cache operations.
"""

import json
import logging
import os
from typing import Optional

import redis

logger = logging.getLogger(__name__)


class RedisService:
    """Redis cache service with connection pooling and error handling."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
        timeout: int = 5,
        max_connections: int = 10,
        enabled: bool = True,
    ):
        """Initialize Redis service.

        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number
            password: Redis password (if required)
            ssl: Whether to use SSL connection
            timeout: Connection timeout in seconds
            max_connections: Maximum connections in pool
            enabled: Whether Redis is enabled
        """
        self.enabled = enabled
        self.host = host
        self.port = port
        self.db = db
        self.timeout = timeout
        self.ssl = ssl

        self._client: Optional[redis.Redis] = None
        self._pool: Optional[redis.ConnectionPool] = None

        if self.enabled:
            try:
                self._pool = redis.ConnectionPool(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    ssl=ssl,
                    socket_connect_timeout=timeout,
                    max_connections=max_connections,
                    decode_responses=True,  # Auto-decode responses to strings
                )
                self._client = redis.Redis(connection_pool=self._pool)

                # Test connection
                self._client.ping()
                logger.info(f"Redis connected successfully: {host}:{port}/{db}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.enabled = False
                self._client = None
                self._pool = None

    def check_connection(self) -> dict:
        """Check Redis connection status and return health info.

        Returns:
            dict: Connection status with details
        """
        if not self.enabled or self._client is None:
            return {
                "connected": False,
                "enabled": self.enabled,
                "message": "Redis is disabled or not initialized",
            }

        try:
            info = self._client.info()
            return {
                "connected": True,
                "enabled": True,
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "redis_version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
                "total_system_memory_mb": round(
                    info.get("total_system_memory", 0) / 1024 / 1024, 2
                ),
                "operations_per_sec": info.get("instantaneous_ops_per_sec", 0),
            }
        except Exception as e:
            logger.error(f"Redis connection check failed: {e}")
            return {
                "connected": False,
                "enabled": True,
                "message": str(e),
            }

    def get(self, key: str) -> Optional[str]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if not self.enabled or self._client is None:
            return None

        try:
            return self._client.get(key)
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value from cache.

        Args:
            key: Cache key

        Returns:
            Parsed JSON or None
        """
        value = self.get(key)
        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON for key {key}")
            return None

    def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (None = no expiry)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or self._client is None:
            return False

        try:
            if ttl_seconds:
                self._client.setex(key, ttl_seconds, value)
            else:
                self._client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    def set_json(
        self, key: str, value: dict, ttl_seconds: Optional[int] = None
    ) -> bool:
        """Set JSON value in cache.

        Args:
            key: Cache key
            value: Dictionary to cache as JSON
            ttl_seconds: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            json_str = json.dumps(value)
            return self.set(key, json_str, ttl_seconds)
        except json.JSONEncodeError:
            logger.error(f"Failed to encode JSON for key {key}")
            return False

    def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or self._client is None:
            return False

        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        if not self.enabled or self._client is None:
            return False

        try:
            return bool(self._client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False

    def expire(self, key: str, ttl_seconds: int) -> bool:
        """Set expiration on key.

        Args:
            key: Cache key
            ttl_seconds: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or self._client is None:
            return False

        try:
            return bool(self._client.expire(key, ttl_seconds))
        except Exception as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    def flush_all(self) -> bool:
        """Flush all data from Redis (DANGEROUS - use carefully).

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or self._client is None:
            return False

        try:
            self._client.flushdb()
            logger.warning("Redis database flushed")
            return True
        except Exception as e:
            logger.error(f"Redis flush error: {e}")
            return False

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            dict: Cache statistics
        """
        if not self.enabled or self._client is None:
            return {"enabled": False}

        try:
            info = self._client.info()
            keys_count = self._client.dbsize()

            return {
                "enabled": True,
                "total_keys": keys_count,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": round(
                    info.get("keyspace_hits", 0)
                    / max(
                        info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1),
                        1,
                    ),
                    4,
                ),
                "evictions": info.get("evicted_keys", 0),
                "memory_used_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}

    def close(self):
        """Close Redis connection pool."""
        if self._pool:
            self._pool.disconnect()
            logger.info("Redis connection pool closed")

    def __del__(self):
        """Ensure cleanup on deletion."""
        self.close()


# Global Redis instance (lazy-loaded)
_redis_service: Optional[RedisService] = None


def get_redis_service() -> RedisService:
    """Get or create Redis service instance.

    Loads configuration from config.yaml or environment variables with this priority:
    1. config.yaml (redis section)
    2. Environment variables (REDIS_*)
    3. Built-in defaults

    Returns:
        RedisService: Singleton Redis service instance
    """
    global _redis_service

    if _redis_service is None:
        try:
            # Try to load from config.yaml first
            from backend.config_loader import get_config_loader

            config_loader = get_config_loader()
            redis_config = config_loader.get_redis_config()
        except ImportError:
            # Fallback to direct environment variables
            redis_config = {
                "enabled": os.getenv("REDIS_ENABLED", "true").lower() == "true",
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", "6379")),
                "db": int(os.getenv("REDIS_DB", "0")),
                "password": os.getenv("REDIS_PASSWORD", None),
                "ssl": os.getenv("REDIS_SSL", "false").lower() == "true",
                "timeout": int(os.getenv("REDIS_TIMEOUT", "5")),
                "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
            }

        _redis_service = RedisService(
            host=redis_config["host"],
            port=redis_config["port"],
            db=redis_config["db"],
            password=redis_config["password"],
            ssl=redis_config["ssl"],
            timeout=redis_config["timeout"],
            max_connections=redis_config["max_connections"],
            enabled=redis_config["enabled"],
        )

    return _redis_service
