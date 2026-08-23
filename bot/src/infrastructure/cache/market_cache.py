"""Redis-backed shared (L2) cache for frequently-accessed market data.

This module consolidates the previously ad-hoc, per-call Redis lookups spread
across ``src/trading/market_data.py`` into a single abstraction that follows the
project's storage-adapter conventions (ABC + concrete backend + no-op fallback,
``enabled`` flag, graceful degradation, ``health()``). It is the **L2 shared**
layer — fast in-process (L1) TTL caches still live next to their callers in
``market_data.py``; this layer exists so market data is consistent across
Uvicorn workers / replicas and survives a single-process restart.

Design contract
---------------
* The cache is an **optimization**, never a source of truth. Every method
  swallows transport/decoding errors and returns ``None`` (read) or no-ops
  (write) so a Redis outage can never break a market-data call. The broad
  ``except Exception`` blocks here are intentional isolation; this directory is
  excluded from the broad-catch ratchet (``tests/test_exception_handling_ratchet.py``).
* Values are stored as the **raw dYdX API response** (JSON). This keeps the
  wire format identical to the Celery Beat producer in
  ``src/infrastructure/workers/market_sync_tasks.py`` (which writes
  ``market:candles:{market}:{resolution}``), so the two interoperate. Callers
  own any ``pandas`` conversion on read.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from src.constants import (
    CANDLES_RECENT_CACHE_TTL_SECONDS,
    MARKET_DATA_CACHE_ENABLED,
    MARKET_DATA_CACHE_REDIS_URL,
    MARKET_DATA_CACHE_SOCKET_TIMEOUT_SECONDS,
    MARKETS_CACHE_TTL_SECONDS,
)
from src.shared.redis_env import redis_url

# Wire-format keys — the candles key MUST match the Celery Beat producer in
# ``market_sync_tasks.py`` so runtime reads consume Celery-written data.
_CANDLES_KEY = "market:candles:{market}:{resolution}"
_MARKETS_KEY = "market:markets"


class MarketDataCache(ABC):
    """Shared (L2) cache interface for frequently-accessed market data."""

    @abstractmethod
    async def get_candles(self, market: str, resolution: str) -> dict[str, Any] | None:
        """Return the cached raw candle response, or ``None`` on miss/unavailable."""

    @abstractmethod
    async def set_candles(
        self, market: str, resolution: str, payload: dict[str, Any], ttl_seconds: float
    ) -> None:
        """Best-effort write of the raw candle response."""

    @abstractmethod
    async def get_markets(self) -> dict[str, Any] | None:
        """Return the cached raw perpetual-markets response, or ``None``."""

    @abstractmethod
    async def set_markets(self, payload: dict[str, Any], ttl_seconds: float) -> None:
        """Best-effort write of the raw perpetual-markets response."""

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return ``{enabled, backend, healthy, error}`` for operators."""

    @abstractmethod
    async def aclose(self) -> None:
        """Release the underlying client (idempotent, best-effort)."""


class NoopMarketDataCache(MarketDataCache):
    """Fallback cache that performs no I/O (used when disabled or Redis absent)."""

    async def get_candles(self, market: str, resolution: str) -> dict[str, Any] | None:
        del market, resolution  # intentionally unused
        return None

    async def set_candles(
        self, market: str, resolution: str, payload: dict[str, Any], ttl_seconds: float
    ) -> None:
        del market, resolution, payload, ttl_seconds  # intentionally unused

    async def get_markets(self) -> dict[str, Any] | None:
        return None

    async def set_markets(self, payload: dict[str, Any], ttl_seconds: float) -> None:
        del payload, ttl_seconds  # intentionally unused

    async def health(self) -> dict[str, Any]:
        return {"enabled": False, "backend": "noop", "healthy": True, "error": None}

    async def aclose(self) -> None:
        return None


class RedisMarketDataCache(MarketDataCache):
    """Redis-backed shared cache backed by a single persistent async client.

    The client is built lazily and cheaply (``from_url`` defers the actual
    connection to the first command), so constructing this object never raises
    even when Redis is unreachable. Per-command failures are isolated so the
    cache can never break a market-data call.
    """

    def __init__(
        self,
        *,
        url: str,
        ttl_candles: float,
        ttl_markets: float,
        socket_timeout: float = 1.0,
        connect_timeout: float = 1.0,
        client: Any | None = None,
    ) -> None:
        self._url = url
        self._ttl_candles = float(ttl_candles)
        self._ttl_markets = float(ttl_markets)
        self._socket_timeout = float(socket_timeout)
        self._connect_timeout = float(connect_timeout)
        # ``client`` is an injection seam for tests; production leaves it None
        # and the real client is built on first use.
        self._client: Any | None = client
        self._build_error: str | None = None

    # ── internal helpers ────────────────────────────────────────────────────
    @staticmethod
    def _candles_key(market: str, resolution: str) -> str:
        return _CANDLES_KEY.format(market=market, resolution=resolution)

    def _ensure_client(self) -> Any | None:
        """Return the async Redis client, building it on first use.

        Returns ``None`` (recording a build error) if ``redis.asyncio`` is
        unavailable or the client cannot be constructed.
        """
        if self._client is not None:
            return self._client
        try:  # pragma: no cover - optional dependency / config path
            import redis.asyncio as aioredis
        except Exception as exc:  # noqa: BLE001 - optional dep, degrade to noop
            self._build_error = f"redis.asyncio unavailable: {exc!r}"
            return None
        try:  # pragma: no cover - connection is deferred to first command
            self._client = aioredis.from_url(  # type: ignore[no-untyped-call]
                self._url,
                decode_responses=True,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._connect_timeout,
            )
        except Exception as exc:  # noqa: BLE001 - bad URL/env, degrade to noop
            self._build_error = f"redis client build failed: {exc!r}"
            self._client = None
        return self._client

    @staticmethod
    def _decode(raw: Any) -> dict[str, Any] | None:
        """JSON-decode a cached payload, returning ``None`` on any failure."""
        if not isinstance(raw, (str, bytes, bytearray)) or not raw:
            return None
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    # ── public API ──────────────────────────────────────────────────────────
    async def get_candles(self, market: str, resolution: str) -> dict[str, Any] | None:
        client = self._ensure_client()
        if client is None:
            return None
        try:  # pragma: no cover - requires a live Redis to exercise the command
            raw = await client.get(self._candles_key(market, resolution))
        except Exception as exc:  # noqa: BLE001 - cache miss on any failure
            logger.debug(
                "market_cache_get_candles_failed market={} resolution={} error={!r}",
                market,
                resolution,
                exc,
            )
            return None
        return self._decode(raw)

    async def set_candles(
        self, market: str, resolution: str, payload: dict[str, Any], ttl_seconds: float
    ) -> None:
        client = self._ensure_client()
        if client is None or ttl_seconds <= 0:
            return
        try:  # pragma: no cover - requires a live Redis to exercise the command
            await client.set(
                self._candles_key(market, resolution),
                json.dumps(payload),
                ex=int(ttl_seconds),
            )
        except Exception as exc:  # noqa: BLE001 - best-effort write
            logger.debug(
                "market_cache_set_candles_failed market={} resolution={} error={!r}",
                market,
                resolution,
                exc,
            )

    async def get_markets(self) -> dict[str, Any] | None:
        client = self._ensure_client()
        if client is None:
            return None
        try:  # pragma: no cover - requires a live Redis to exercise the command
            raw = await client.get(_MARKETS_KEY)
        except Exception as exc:  # noqa: BLE001 - cache miss on any failure
            logger.debug("market_cache_get_markets_failed error={!r}", exc)
            return None
        return self._decode(raw)

    async def set_markets(self, payload: dict[str, Any], ttl_seconds: float) -> None:
        client = self._ensure_client()
        if client is None or ttl_seconds <= 0:
            return
        try:  # pragma: no cover - requires a live Redis to exercise the command
            await client.set(_MARKETS_KEY, json.dumps(payload), ex=int(ttl_seconds))
        except Exception as exc:  # noqa: BLE001 - best-effort write
            logger.debug("market_cache_set_markets_failed error={!r}", exc)

    async def health(self) -> dict[str, Any]:
        client = self._ensure_client()
        if client is None:
            return {
                "enabled": True,
                "backend": "redis",
                "healthy": False,
                "error": self._build_error or "client not built",
            }
        try:  # pragma: no cover - requires a live Redis to exercise the command
            await client.ping()
            return {"enabled": True, "backend": "redis", "healthy": True, "error": None}
        except Exception as exc:  # noqa: BLE001 - report unhealthy, do not raise
            return {
                "enabled": True,
                "backend": "redis",
                "healthy": False,
                "error": str(exc),
            }

    async def aclose(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        try:  # pragma: no cover - shutdown path
            await client.aclose()
        except Exception:  # noqa: BLE001 - best-effort shutdown
            return


def _build_market_data_cache() -> MarketDataCache:
    """Construct the L2 cache from configuration, degrading to Noop as needed."""
    if not MARKET_DATA_CACHE_ENABLED:
        return NoopMarketDataCache()
    url = MARKET_DATA_CACHE_REDIS_URL or redis_url(prefer_celery_broker=True)
    if not url:
        return NoopMarketDataCache()
    return RedisMarketDataCache(
        url=url,
        ttl_candles=CANDLES_RECENT_CACHE_TTL_SECONDS,
        ttl_markets=MARKETS_CACHE_TTL_SECONDS,
        socket_timeout=MARKET_DATA_CACHE_SOCKET_TIMEOUT_SECONDS,
    )


# Module-level singleton — built on first access. Tests reset it via
# ``reset_market_data_cache()`` or replace it by monkeypatching the accessor.
_market_data_cache: MarketDataCache | None = None


def get_market_data_cache() -> MarketDataCache:
    """Return the process-wide L2 market-data cache (lazy singleton)."""
    global _market_data_cache
    if _market_data_cache is None:
        _market_data_cache = _build_market_data_cache()
    return _market_data_cache


def reset_market_data_cache() -> None:
    """Drop the cached singleton (tests / forced reconfiguration)."""
    global _market_data_cache
    _market_data_cache = None
