"""Market data retrieval and price construction for dYdX."""

import asyncio
import time

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

# Get relevant time periods for ISO from and to
ISO_TIMES = get_ISO_times()

# ── Module-level caches ───────────────────────────────────────────────────────

_markets_cache: dict = {"data": None, "expires": 0.0}
# key: (market, resolution) → {"data": pd.Series, "expires": float}
_candles_recent_cache: dict = {}


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


async def get_candles_recent(client, market, resolution=None):
    """Get recent candles for a market, with a 30-second in-process cache."""
    effective_resolution = (
        normalize_resolution(resolution) if resolution else DYDX_RESOLUTION
    )

    cache_key = (market, effective_resolution)
    now = time.monotonic()

    # Return cached data if still fresh
    if CANDLES_RECENT_CACHE_TTL_SECONDS > 0:
        cached = _candles_recent_cache.get(cache_key)
        if cached is not None and now < cached["expires"]:
            return cached["data"]

    # Protect API rate limits
    if DYDX_API_THROTTLE_SECONDS > 0:
        await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)

    # Get Prices from DYDX V4
    response = await asyncio.wait_for(
        client.indexer.markets.get_perpetual_market_candles(
            market=market, resolution=effective_resolution
        ),
        timeout=15.0,
    )

    close_prices = []
    for candle in response["candles"]:
        close_prices.append(candle["close"])
    close_prices.reverse()
    result = pd.Series(close_prices, dtype=float)

    # Store in cache, bounding size to 200 entries
    if CANDLES_RECENT_CACHE_TTL_SECONDS > 0:
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
        if DYDX_API_THROTTLE_SECONDS > 0:
            await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)

        response = await asyncio.wait_for(
            client.indexer.markets.get_perpetual_market_candles(
                market=market,
                resolution=effective_resolution,
                from_iso=from_iso,
                to_iso=to_iso,
                limit=100,
            ),
            timeout=15.0,
        )

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
        return _markets_cache["data"]

    result = await asyncio.wait_for(
        client.indexer.markets.get_perpetual_markets(),
        timeout=15.0,
    )
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
        if isinstance(item, Exception):
            logger.warning(
                "Skipping market {} – candle fetch failed: {}",
                tradeable_markets[i],
                item,
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
