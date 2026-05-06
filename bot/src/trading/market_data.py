"""Market data retrieval and price construction for dYdX."""

import asyncio

import pandas as pd
from loguru import logger
from src.constants import RESOLUTION
from src.shared.utils import get_ISO_times

# Get relevant time periods for ISO from and to
ISO_TIMES = get_ISO_times()


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
    """Get recent candles for a market."""
    # Define output
    close_prices = []

    effective_resolution = (
        normalize_resolution(resolution) if resolution else DYDX_RESOLUTION
    )

    # Protect API
    await asyncio.sleep(0.2)

    # Get Prices from DYDX V4
    response = await asyncio.wait_for(
        client.indexer.markets.get_perpetual_market_candles(
            market=market, resolution=effective_resolution
        ),
        timeout=15.0,
    )

    # Candles
    candles = response

    # Structure data
    for candle in candles["candles"]:
        close_prices.append(candle["close"])

    # Construct and return close price series
    close_prices.reverse()
    return pd.Series(close_prices, dtype=float)


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
        await asyncio.sleep(0.2)

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
    """Get list of all perpetual markets."""
    return await asyncio.wait_for(
        client.indexer.markets.get_perpetual_markets(),
        timeout=15.0,
    )


async def construct_market_prices(client, selected_markets=None, resolution=None):
    """
    Construct a DataFrame of market prices for all tradeable markets.

    Args:
        client: dYdX client
        selected_markets: optional list of markets to include
        resolution: candle resolution override (e.g. '5MINS'); defaults to DYDX_RESOLUTION

    Returns:
        DataFrame with datetime index and market prices as columns
    """
    # Ensure only Testnet Assets are used

    # Declare variables
    tradeable_markets = []
    markets = await get_markets(client)
    selected = {
        str(market).strip()
        for market in (selected_markets or [])
        if str(market).strip()
    }

    # Find tradeable pairs
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

    # Set initial DataFrame
    close_prices = await get_candles_historical(
        client, tradeable_markets[0], resolution=resolution
    )
    df = pd.DataFrame(close_prices)
    df.set_index("datetime", inplace=True)

    # Append other prices to DataFrame
    # You can limit the amount to loop though here to save time in development
    for i, market in enumerate(tradeable_markets[0:]):
        logger.info(
            "Extracting prices for {} of {} tokens: {}",
            i + 1,
            len(tradeable_markets),
            market,
        )
        close_prices_add = await get_candles_historical(
            client, market, resolution=resolution
        )
        df_add = pd.DataFrame(close_prices_add)
        try:
            df_add.set_index("datetime", inplace=True)
            df = pd.merge(df, df_add, how="outer", on="datetime")
        except Exception as e:
            logger.exception("Failed to add market {} to price matrix! {}", market, e)

        del df_add

    # Check any columns with NaNs
    nans = df.columns[df.isna().any()].tolist()
    if len(nans) > 0:
        logger.warning("Dropping columns with NaNs: {}", nans)
        df.drop(columns=nans, inplace=True)

    # Return result
    return df
