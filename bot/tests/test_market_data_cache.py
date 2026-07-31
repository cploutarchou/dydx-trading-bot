import asyncio
import os

import pandas as pd
from src.trading import market_data


class _FakeMarketsAPI:
    def __init__(self):
        self.calls = 0

    async def get_perpetual_markets(self):
        self.calls += 1
        return {"markets": {"BTC-USD": {"status": "ACTIVE"}}}


class _FakeIndexer:
    def __init__(self, markets_api):
        self.markets = markets_api


class _FakeClient:
    def __init__(self, markets_api):
        self.indexer = _FakeIndexer(markets_api)


class _FakeCandlesAPI:
    def __init__(self):
        self.calls = 0

    async def get_perpetual_market_candles(self, market, resolution):
        self.calls += 1
        return {
            "candles": [
                {"close": "1.0"},
                {"close": "2.0"},
                {"close": "3.0"},
            ]
        }


class _FakeCandleClient:
    def __init__(self, candles_api):
        self.indexer = _FakeIndexer(candles_api)


def test_get_markets_uses_ttl_cache_when_enabled(monkeypatch):
    markets_api = _FakeMarketsAPI()
    client = _FakeClient(markets_api)

    monkeypatch.setattr(market_data, "MARKETS_CACHE_TTL_SECONDS", 60.0)
    monkeypatch.setattr(market_data, "_markets_cache", {"data": None, "expires": 0.0})

    first = asyncio.run(market_data.get_markets(client))
    second = asyncio.run(market_data.get_markets(client))

    assert first == second
    assert markets_api.calls == 1


def test_get_markets_cache_can_be_disabled(monkeypatch):
    markets_api = _FakeMarketsAPI()
    client = _FakeClient(markets_api)

    monkeypatch.setattr(market_data, "MARKETS_CACHE_TTL_SECONDS", 0.0)
    monkeypatch.setattr(market_data, "_markets_cache", {"data": None, "expires": 0.0})

    asyncio.run(market_data.get_markets(client))
    asyncio.run(market_data.get_markets(client))

    assert markets_api.calls == 2


def test_get_candles_recent_uses_in_process_cache(monkeypatch):
    candles_api = _FakeCandlesAPI()
    client = _FakeCandleClient(candles_api)

    monkeypatch.setattr(market_data, "CANDLES_RECENT_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(market_data, "_candles_recent_cache", {})
    monkeypatch.setattr(market_data, "_get_recent_candles_from_redis", lambda *_: None)
    monkeypatch.setattr(market_data, "_throttle_api_call", lambda: asyncio.sleep(0))

    first = asyncio.run(market_data.get_candles_recent(client, "BTC-USD"))
    second = asyncio.run(market_data.get_candles_recent(client, "BTC-USD"))

    assert candles_api.calls == 1
    assert isinstance(first, pd.Series)
    assert isinstance(second, pd.Series)
    assert first.equals(second)


def test_get_candles_recent_bypasses_cache_for_explicit_resolution(monkeypatch):
    candles_api = _FakeCandlesAPI()
    client = _FakeCandleClient(candles_api)

    monkeypatch.setattr(market_data, "CANDLES_RECENT_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(market_data, "_candles_recent_cache", {})
    monkeypatch.setattr(market_data, "_get_recent_candles_from_redis", lambda *_: None)
    monkeypatch.setattr(market_data, "_throttle_api_call", lambda: asyncio.sleep(0))

    asyncio.run(market_data.get_candles_recent(client, "BTC-USD", resolution="5MINS"))
    asyncio.run(market_data.get_candles_recent(client, "BTC-USD", resolution="5MINS"))

    assert candles_api.calls == 2


def test_get_candles_recent_cache_is_bounded(monkeypatch):
    candles_api = _FakeCandlesAPI()
    client = _FakeCandleClient(candles_api)

    prefilled = {
        (f"MKT-{i}", "1HOUR"): {"data": pd.Series([1.0]), "expires": float(i)}
        for i in range(200)
    }

    monkeypatch.setattr(market_data, "CANDLES_RECENT_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(market_data, "_candles_recent_cache", prefilled)
    monkeypatch.setattr(market_data, "_get_recent_candles_from_redis", lambda *_: None)
    monkeypatch.setattr(market_data, "_throttle_api_call", lambda: asyncio.sleep(0))

    asyncio.run(market_data.get_candles_recent(client, "NEW-MARKET"))

    assert len(market_data._candles_recent_cache) == 200
    assert ("MKT-0", "1HOUR") not in market_data._candles_recent_cache
    assert (
        "NEW-MARKET",
        market_data.DYDX_RESOLUTION,
    ) in market_data._candles_recent_cache


def test_rate_limiter_per_event_loop_behavior():
    """Test that rate limiter is created per event loop to avoid reuse warnings."""

    async def test_in_new_event_loop():
        # This should create a new limiter for this event loop
        limiter = market_data._get_event_loop_limiter()
        if market_data._rate_limiter_key is not None:
            # If aiolimiter is available, we should get a limiter
            assert limiter is not None
        return limiter

    async def test_in_another_event_loop():
        # This should create a different limiter for the different event loop
        limiter = market_data._get_event_loop_limiter()
        if market_data._rate_limiter_key is not None:
            assert limiter is not None
        return limiter

    # Run in different event loops
    import asyncio

    loop1 = asyncio.new_event_loop()
    loop2 = asyncio.new_event_loop()

    try:
        limiter1 = loop1.run_until_complete(test_in_new_event_loop())
        limiter2 = loop2.run_until_complete(test_in_another_event_loop())

        # If both limiters exist, they should be different instances (different event loops)
        if limiter1 is not None and limiter2 is not None:
            assert (
                limiter1 is not limiter2
            ), "Limiters should be different for different event loops"
    finally:
        loop1.close()
        loop2.close()


def test_rate_limiter_fallback_when_aiolimiter_unavailable(monkeypatch):
    """Test that throttling falls back to sleep when aiolimiter is not available."""
    import os

    # Mock aiolimiter to be unavailable
    monkeypatch.setattr(market_data, "_rate_limiter_key", None)

    async def test_throttle_fallback():
        # This should not raise and should use sleep fallback
        await market_data._throttle_api_call()
        return True

    result = asyncio.run(test_throttle_fallback())
    assert result is True
