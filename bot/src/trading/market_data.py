"""Market data retrieval and price construction for dYdX."""

import asyncio
import importlib.util
import os
import time
from typing import Any

import pandas as pd
from loguru import logger
from src.constants import (
    CANDLE_FETCH_CONCURRENCY,
    CANDLES_RECENT_CACHE_TTL_SECONDS,
    DYDX_API_THROTTLE_SECONDS,
    MARKETS_CACHE_TTL_SECONDS,
    RESOLUTION,
)
from src.shared.utils import get_ISO_times
from src.trading.arbitrage_observability import increment_metric

# Get relevant time periods for ISO from and to
ISO_TIMES = get_ISO_times()

# ── Module-level caches ───────────────────────────────────────────────────────

_markets_cache: dict = {"data": None, "expires": 0.0}
# key: (market, resolution) → {"data": pd.Series, "expires": float}
_candles_recent_cache: dict = {}

# ── Token-bucket rate limiter (aiolimiter) ────────────────────────────────────
# Defaults: 5 requests per 1-second window (configurable via env vars).
# Falls back to legacy asyncio.sleep throttle if aiolimiter is not installed.
_DYDX_RATE_LIMIT_RPS = float(os.getenv("DYDX_RATE_LIMIT_RPS", "5"))
_DYDX_RATE_LIMIT_WINDOW = float(os.getenv("DYDX_RATE_LIMIT_WINDOW", "1.0"))
_rate_limiter = None  # type: ignore[assignment]

if importlib.util.find_spec("aiolimiter") is not None:
    try:
        from aiolimiter import AsyncLimiter  # type: ignore[import]

        _rate_limiter = AsyncLimiter(
            max_rate=_DYDX_RATE_LIMIT_RPS,
            time_period=_DYDX_RATE_LIMIT_WINDOW,
        )
    except Exception:
        _rate_limiter = None


async def _throttle_api_call() -> None:
    """Acquire one slot from the token-bucket rate limiter, or fall back to sleep."""
    if _rate_limiter is not None:
        async with _rate_limiter:
            return
    if DYDX_API_THROTTLE_SECONDS > 0:
        await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)


def _get_recent_candles_from_redis(market: str, resolution: str):
    """Best-effort shared-cache lookup for recent candles.

    Returns parsed payload or ``None`` when unavailable.
    """
    try:
        import json as _json
        import os as _os

        import redis as _redis

        _rc = _redis.from_url(
            _os.getenv("CELERY_BROKER_URL")
            or _os.getenv("REDIS_URL")
            or "redis://localhost:6379/0",
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        _redis_val = _rc.get(f"market:candles:{market}:{resolution}")
        _rc.close()
        if isinstance(_redis_val, (str, bytes, bytearray)) and _redis_val:
            return _json.loads(_redis_val)
    except Exception:
        return None
    return None


# ── Circuit breaker (pybreaker) ───────────────────────────────────────────────
# Opens after DYDX_CIRCUIT_FAIL_MAX consecutive failures within
# DYDX_CIRCUIT_RESET_TIMEOUT seconds; transitions to half-open after the reset
# timeout, then closes on the first success.  Falls back to a no-op wrapper
# when pybreaker is not installed.
_CIRCUIT_FAIL_MAX = int(os.getenv("DYDX_CIRCUIT_FAIL_MAX", "3"))
_CIRCUIT_RESET_TIMEOUT = int(os.getenv("DYDX_CIRCUIT_RESET_TIMEOUT", "30"))
_dydx_circuit_breaker: Any = None

if importlib.util.find_spec("pybreaker") is not None:
    try:
        import pybreaker as _pybreaker  # type: ignore[import]

        class _CircuitBreakerListener(_pybreaker.CircuitBreakerListener):  # type: ignore[misc]
            def state_change(self, cb, old_state, new_state):  # type: ignore[override]
                if new_state.name == "open":
                    logger.critical(
                        "dydx_circuit_breaker_open fail_max={} recent_failures={}",
                        _CIRCUIT_FAIL_MAX,
                        cb.fail_counter,
                    )
                elif new_state.name == "closed":
                    logger.info("dydx_circuit_breaker_closed")
                elif new_state.name == "half-open":
                    logger.info("dydx_circuit_breaker_half_open")

        _dydx_circuit_breaker = _pybreaker.CircuitBreaker(
            fail_max=_CIRCUIT_FAIL_MAX,
            reset_timeout=_CIRCUIT_RESET_TIMEOUT,
            listeners=[_CircuitBreakerListener()],
            name="dydx_api",
        )
    except Exception:
        _dydx_circuit_breaker = None


async def _circuit_call(coro_factory):
    """Run *coro_factory()* guarded by the dYdX circuit breaker.

    Falls back to direct execution when pybreaker is not installed.
    Raises ``pybreaker.CircuitBreakerError`` when the circuit is open so callers
    can return cached data instead of failing.
    """
    if _dydx_circuit_breaker is None:
        return await coro_factory()
    return await _dydx_circuit_breaker.call_async(coro_factory)


def normalize_resolution(resolution):
    """Return a dYdX candle resolution enum while accepting older app aliases."""
    raw = str(resolution or "1HOUR").strip().upper()
    mapping = {
        "M1": "1MIN",
        "1M": "1MIN",
        "1MIN": "1MIN",
        "1MINUTE": "1MIN",
        "1MINUTES": "1MIN",
        "M5": "5MINS",
        "5M": "5MINS",
        "5MIN": "5MINS",
        "5MINS": "5MINS",
        "5MINUTE": "5MINS",
        "5MINUTES": "5MINS",
        "M15": "15MINS",
        "15M": "15MINS",
        "15MIN": "15MINS",
        "15MINS": "15MINS",
        "15MINUTE": "15MINS",
        "15MINUTES": "15MINS",
        "M30": "30MINS",
        "30M": "30MINS",
        "30MIN": "30MINS",
        "30MINS": "30MINS",
        "30MINUTE": "30MINS",
        "30MINUTES": "30MINS",
        "H1": "1HOUR",
        "1H": "1HOUR",
        "1HR": "1HOUR",
        "1HOUR": "1HOUR",
        "1HOURS": "1HOUR",
        "H4": "4HOURS",
        "4H": "4HOURS",
        "4HR": "4HOURS",
        "4HOUR": "4HOURS",
        "4HOURS": "4HOURS",
        "D1": "1DAY",
        "1D": "1DAY",
        "1DAY": "1DAY",
        "1DAYS": "1DAY",
    }
    return mapping.get(raw, "1HOUR")


DYDX_RESOLUTION = normalize_resolution(RESOLUTION)


def _candle_fetch_logger(*, market: str, resolution: str, timeframe: str, kind: str):
    """Return a logger pre-bound with candle fetch dimensions for Loki filtering."""
    return logger.bind(
        market=str(market),
        resolution=str(resolution),
        timeframe=str(timeframe),
        fetch_type=str(kind),
    )


async def get_candles_recent(client, market, resolution=None):
    """Get recent candles for a market, with a 30-second in-process cache."""
    effective_resolution = (
        normalize_resolution(resolution) if resolution else DYDX_RESOLUTION
    )
    cache_enabled = CANDLES_RECENT_CACHE_TTL_SECONDS > 0 and resolution is None

    cache_key = (market, effective_resolution)
    now = time.monotonic()

    # Return cached data if still fresh
    if cache_enabled:
        cached = _candles_recent_cache.get(cache_key)
        if cached is not None and now < cached["expires"]:
            increment_metric("cache_hits_total")
            increment_metric("exchange_api_calls_saved_total")
            return cached["data"]
    increment_metric("cache_misses_total")

    # Check shared Redis cache (written by the Celery Beat market sync task)
    if cache_enabled:
        _redis_data = _get_recent_candles_from_redis(market, effective_resolution)
        if _redis_data is not None:
            _candles_recent_cache[cache_key] = {
                "data": _redis_data,
                "expires": now + CANDLES_RECENT_CACHE_TTL_SECONDS,
            }
            increment_metric("cache_hits_total")
            increment_metric("exchange_api_calls_saved_total")
            return _redis_data

    # Protect API rate limits
    await _throttle_api_call()
    increment_metric("exchange_api_calls_total")

    # Get Prices from DYDX V4 (guarded by circuit breaker)
    _fetch_start = time.monotonic()
    _fetch_logger = _candle_fetch_logger(
        market=market,
        resolution=effective_resolution,
        timeframe="recent",
        kind="recent",
    )
    try:
        response = await _circuit_call(
            lambda: asyncio.wait_for(
                client.indexer.markets.get_perpetual_market_candles(
                    market=market, resolution=effective_resolution
                ),
                timeout=15.0,
            )
        )
    except Exception as _exc:
        increment_metric("provider_errors_total")
        _latency_ms = (time.monotonic() - _fetch_start) * 1000.0
        _fetch_logger.warning(
            "candle_fetch_error latency_ms={:.1f} error={}",
            _latency_ms,
            _exc,
        )
        raise
    else:
        _latency_ms = (time.monotonic() - _fetch_start) * 1000.0
        _fetch_logger.debug("candle_fetch_ok latency_ms={:.1f}", _latency_ms)

    close_prices = []
    for candle in response["candles"]:
        close_prices.append(candle["close"])
    close_prices.reverse()
    result = pd.Series(close_prices, dtype=float)

    # Store in cache, bounding size to 200 entries
    if cache_enabled:
        _candles_recent_cache[cache_key] = {
            "data": result,
            "expires": now + CANDLES_RECENT_CACHE_TTL_SECONDS,
        }
        if len(_candles_recent_cache) > 200:
            oldest = min(
                _candles_recent_cache.keys(),
                key=lambda k: _candles_recent_cache[k]["expires"],
            )
            _candles_recent_cache.pop(oldest, None)

    return result


async def get_candles_historical(client, market, resolution=None):
    """Get historical candles for a market across timeframes."""
    # Define output
    close_prices = []

    effective_resolution = (
        normalize_resolution(resolution) if resolution else DYDX_RESOLUTION
    )
    # Refresh time windows each call so long-running processes use current timestamps
    iso_times = get_ISO_times()

    # Extract historical price data for each timeframe
    for timeframe in iso_times.keys():

        # Confirm times needed — format_time now emits clean UTC Z strings
        tf_obj = iso_times[timeframe]
        from_iso = tf_obj["from_iso"]
        to_iso = tf_obj["to_iso"]

        # Protect rate limits
        await _throttle_api_call()

        _fetch_start = time.monotonic()
        _fetch_logger = _candle_fetch_logger(
            market=market,
            resolution=effective_resolution,
            timeframe=timeframe,
            kind="historical",
        )
        try:
            response = await _circuit_call(
                lambda: asyncio.wait_for(
                    client.indexer.markets.get_perpetual_market_candles(
                        market=market,
                        resolution=effective_resolution,
                        from_iso=from_iso,
                        to_iso=to_iso,
                        limit=100,
                    ),
                    timeout=15.0,
                )
            )
        except Exception as _exc:
            _latency_ms = (time.monotonic() - _fetch_start) * 1000.0
            _fetch_logger.warning(
                "candle_fetch_error latency_ms={:.1f} error={}",
                _latency_ms,
                _exc,
            )
            raise
        else:
            _latency_ms = (time.monotonic() - _fetch_start) * 1000.0
            _fetch_logger.debug("candle_fetch_ok latency_ms={:.1f}", _latency_ms)

        candles = response

        # Structure data
        for candle in candles["candles"]:
            close_prices.append(
                {"datetime": candle["startedAt"], market: candle["close"]}
            )

    # Construct and return DataFrame
    close_prices.reverse()
    return close_prices


async def get_markets(client):
    """Get list of all perpetual markets, with a 60-second in-process cache."""
    global _markets_cache
    now = time.monotonic()
    if (
        MARKETS_CACHE_TTL_SECONDS > 0
        and _markets_cache["data"] is not None
        and now < _markets_cache["expires"]
    ):
        increment_metric("cache_hits_total")
        increment_metric("exchange_api_calls_saved_total")
        return _markets_cache["data"]
    increment_metric("cache_misses_total")

    try:
        increment_metric("exchange_api_calls_total")
        result = await asyncio.wait_for(
            client.indexer.markets.get_perpetual_markets(),
            timeout=15.0,
        )
    except Exception:
        increment_metric("provider_errors_total")
        raise
    if MARKETS_CACHE_TTL_SECONDS > 0:
        _markets_cache = {"data": result, "expires": now + MARKETS_CACHE_TTL_SECONDS}
    return result


async def construct_market_prices(client, selected_markets=None, resolution=None):
    """
    Construct a DataFrame of market prices for all tradeable markets.

    Candle fetches run concurrently (bounded by CANDLE_FETCH_CONCURRENCY) so
    50-market runs finish in ~10 s instead of 30+ s of sequential sleep.

    Args:
        client: dYdX client
        selected_markets: optional list of markets to include
        resolution: candle resolution override (e.g. '5MINS'); defaults to DYDX_RESOLUTION

    Returns:
        DataFrame with datetime index and market prices as columns
    """
    markets = await get_markets(client)
    selected = {
        str(market).strip()
        for market in (selected_markets or [])
        if str(market).strip()
    }

    if not selected:
        logger.warning(
            "construct_market_prices: no selected_markets configured — "
            "falling back to ALL active markets on the exchange. "
            "This is usually unintentional; set selectedMarkets in the instance config."
        )

    # Find tradeable pairs
    tradeable_markets = []
    for market in markets["markets"].keys():
        market_info = markets["markets"][market]
        if selected and market not in selected:
            continue
        if market_info["status"] == "ACTIVE":
            tradeable_markets.append(market)

    if selected and len(tradeable_markets) < 2:
        raise ValueError(
            "Selected market universe must include at least two active dYdX perpetual markets"
        )

    # Parallel fetch with bounded concurrency
    sem = asyncio.Semaphore(CANDLE_FETCH_CONCURRENCY)

    async def fetch_one(market):
        async with sem:
            logger.info(
                "Fetching candles for {} (concurrency cap={})",
                market,
                CANDLE_FETCH_CONCURRENCY,
            )
            return market, await get_candles_historical(
                client, market, resolution=resolution
            )

    results = await asyncio.gather(
        *[fetch_one(m) for m in tradeable_markets], return_exceptions=True
    )

    # Build DataFrame from gathered results
    df: pd.DataFrame | None = None
    for i, item in enumerate(results):
        if isinstance(item, BaseException):
            logger.warning(
                "Skipping market {} – candle fetch failed: {}",
                tradeable_markets[i],
                item,
            )
            continue
        if not isinstance(item, tuple) or len(item) != 2:
            logger.warning(
                "Skipping market {} – unexpected candle fetch payload type={}",
                tradeable_markets[i],
                type(item).__name__,
            )
            continue
        market, close_prices = item
        if not close_prices:
            continue
        df_add = pd.DataFrame(close_prices)
        try:
            df_add.set_index("datetime", inplace=True)
            if df is None:
                df = df_add
            else:
                df = pd.merge(df, df_add, how="outer", on="datetime")
        except Exception as e:
            logger.exception("Failed to add market {} to price matrix: {}", market, e)

    if df is None:
        df = pd.DataFrame()

    # Drop columns with NaNs
    nans = df.columns[df.isna().any()].tolist()
    if nans:
        logger.warning("Dropping columns with NaNs: {}", nans)
        df.drop(columns=nans, inplace=True)

    return df
