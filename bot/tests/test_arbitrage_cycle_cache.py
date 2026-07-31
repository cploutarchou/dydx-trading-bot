import asyncio

import pandas as pd

from src.trading import position_manager


def test_cycle_candle_cache_avoids_duplicate_fetches_when_enabled(monkeypatch):
    calls = []

    async def fake_get_candles_recent(_client, market):
        calls.append(market)
        return pd.Series([1.0, 2.0, 3.0])

    monkeypatch.setattr(
        position_manager, "is_arbitrage_improvements_enabled", lambda: True
    )
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

    monkeypatch.setattr(
        position_manager, "is_arbitrage_improvements_enabled", lambda: False
    )
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)

    cache = {}
    asyncio.run(
        position_manager._get_recent_candles_for_cycle(object(), "ETH-USD", cache)
    )
    asyncio.run(
        position_manager._get_recent_candles_for_cycle(object(), "ETH-USD", cache)
    )

    assert calls == ["ETH-USD", "ETH-USD"]


def test_resolve_leg_open_state_uses_snapshot_when_enabled(monkeypatch):
    async def fake_get_open_positions(_client):
        return {"BTC-USD": {"side": "LONG"}}

    async def should_not_call(_client, _market):
        raise AssertionError("legacy is_open_positions should not be called")

    monkeypatch.setattr(
        position_manager, "is_arbitrage_improvements_enabled", lambda: True
    )
    monkeypatch.setattr(position_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(position_manager, "is_open_positions", should_not_call)

    is_base_open, is_quote_open = asyncio.run(
        position_manager._resolve_leg_open_state(
            object(),
            base_market="BTC-USD",
            quote_market="ETH-USD",
            scan_cycle_id="cycle-1",
        )
    )

    assert is_base_open is True
    assert is_quote_open is False


def test_resolve_leg_open_state_falls_back_on_snapshot_error(monkeypatch):
    async def fake_get_open_positions(_client):
        raise RuntimeError("snapshot failure")

    calls = []

    async def fake_is_open_positions(_client, market):
        calls.append(market)
        return market == "ETH-USD"

    monkeypatch.setattr(
        position_manager, "is_arbitrage_improvements_enabled", lambda: True
    )
    monkeypatch.setattr(position_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(position_manager, "is_open_positions", fake_is_open_positions)

    is_base_open, is_quote_open = asyncio.run(
        position_manager._resolve_leg_open_state(
            object(),
            base_market="BTC-USD",
            quote_market="ETH-USD",
            scan_cycle_id="cycle-2",
        )
    )

    assert calls == ["BTC-USD", "ETH-USD"]
    assert is_base_open is False
    assert is_quote_open is True
