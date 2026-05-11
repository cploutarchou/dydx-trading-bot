import asyncio

import pandas as pd

from src.trading import position_manager


def test_cycle_candle_cache_avoids_duplicate_fetches_when_enabled(monkeypatch):
    calls = []

    async def fake_get_candles_recent(_client, market):
        calls.append(market)
        return pd.Series([1.0, 2.0, 3.0])

    monkeypatch.setattr(position_manager, "ARBITRAGE_IMPROVEMENTS_ENABLED", True)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)

    cache = {}
    first = asyncio.run(
        position_manager._get_recent_candles_for_cycle(object(), "BTC-USD", cache)
    )
    second = asyncio.run(
        position_manager._get_recent_candles_for_cycle(object(), "BTC-USD", cache)
    )

    assert calls == ["BTC-USD"]
    assert first.equals(second)


def test_cycle_candle_cache_preserves_legacy_fetch_path_when_disabled(monkeypatch):
    calls = []

    async def fake_get_candles_recent(_client, market):
        calls.append(market)
        return pd.Series([1.0, 2.0, 3.0])

    monkeypatch.setattr(position_manager, "ARBITRAGE_IMPROVEMENTS_ENABLED", False)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)

    cache = {}
    asyncio.run(position_manager._get_recent_candles_for_cycle(object(), "ETH-USD", cache))
    asyncio.run(position_manager._get_recent_candles_for_cycle(object(), "ETH-USD", cache))

    assert calls == ["ETH-USD", "ETH-USD"]
