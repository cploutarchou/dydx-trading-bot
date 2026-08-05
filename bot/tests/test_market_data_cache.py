import asyncio
import time

import pandas as pd

from src.infrastructure.cache import (
    NoopMarketDataCache,
    RedisMarketDataCache,
    get_market_data_cache,
    reset_market_data_cache,
)
from src.infrastructure.cache import market_cache as market_cache_module
from src.trading import market_data

# ── Existing fakes for the dYdX client ────────────────────────────────────────


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
    def __init__(self, response=None):
        self.calls = 0
        self.response = response or {
            "candles": [
                {"close": "1.0"},
                {"close": "2.0"},
                {"close": "3.0"},
            ]
        }

    async def get_perpetual_market_candles(self, market, resolution):
        self.calls += 1
        return self.response


class _FakeCandleClient:
    def __init__(self, candles_api):
        self.indexer = _FakeIndexer(candles_api)


# ── Fakes for the cache layer ─────────────────────────────────────────────────


class _FakeAsyncRedis:
    """In-memory stand-in for ``redis.asyncio.Redis`` used by unit tests."""

    def __init__(self, *, fail_get=False, fail_set=False, fail_ping=False):
        self.store: dict[str, str] = {}
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.fail_ping = fail_ping
        self.get_calls = 0
        self.set_calls: list[tuple] = []

    async def get(self, key):
        self.get_calls += 1
        if self.fail_get:
            raise RuntimeError("get boom")
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        if self.fail_set:
            raise RuntimeError("set boom")
        self.store[key] = value
        self.set_calls.append((key, value, ex))

    async def ping(self):
        if self.fail_ping:
            raise RuntimeError("ping boom")
        return True

    async def aclose(self):
        return None


class _RecordingCache:
    """Minimal ``MarketDataCache`` double that records writes and serves reads."""

    def __init__(self, *, candles=None, markets=None):
        self._candles = candles
        self._markets = markets
        self.set_candles_calls: list[tuple] = []
        self.set_markets_calls: list[tuple] = []

    async def get_candles(self, market, resolution):
        del market, resolution
        return self._candles

    async def set_candles(self, market, resolution, payload, ttl_seconds):
        self.set_candles_calls.append((market, resolution, payload, ttl_seconds))

    async def get_markets(self):
        return self._markets

    async def set_markets(self, payload, ttl_seconds):
        self.set_markets_calls.append((payload, ttl_seconds))


def _patch_noop_cache(monkeypatch):
    """Force ``market_data`` to use a no-op L2 cache (pure L1 behavior)."""
    monkeypatch.setattr(
        market_data, "get_market_data_cache", lambda: NoopMarketDataCache()
    )


# ── L1 in-process cache behavior (preserved by the refactor) ──────────────────


def test_get_markets_uses_ttl_cache_when_enabled(monkeypatch):
    markets_api = _FakeMarketsAPI()
    client = _FakeClient(markets_api)

    monkeypatch.setattr(market_data, "MARKETS_CACHE_TTL_SECONDS", 60.0)
    monkeypatch.setattr(market_data, "_markets_cache", {"data": None, "expires": 0.0})
    _patch_noop_cache(monkeypatch)

    first = asyncio.run(market_data.get_markets(client))
    second = asyncio.run(market_data.get_markets(client))

    assert first == second
    assert markets_api.calls == 1


def test_get_markets_cache_can_be_disabled(monkeypatch):
    markets_api = _FakeMarketsAPI()
    client = _FakeClient(markets_api)

    monkeypatch.setattr(market_data, "MARKETS_CACHE_TTL_SECONDS", 0.0)
    monkeypatch.setattr(market_data, "_markets_cache", {"data": None, "expires": 0.0})
    _patch_noop_cache(monkeypatch)

    asyncio.run(market_data.get_markets(client))
    asyncio.run(market_data.get_markets(client))

    assert markets_api.calls == 2


def test_get_candles_recent_uses_in_process_cache(monkeypatch):
    candles_api = _FakeCandlesAPI()
    client = _FakeCandleClient(candles_api)

    monkeypatch.setattr(market_data, "CANDLES_RECENT_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(market_data, "_candles_recent_cache", {})
    _patch_noop_cache(monkeypatch)
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
    _patch_noop_cache(monkeypatch)
    monkeypatch.setattr(market_data, "_throttle_api_call", lambda: asyncio.sleep(0))

    asyncio.run(market_data.get_candles_recent(client, "BTC-USD", resolution="5MINS"))
    asyncio.run(market_data.get_candles_recent(client, "BTC-USD", resolution="5MINS"))

    assert candles_api.calls == 2


def test_get_candles_recent_cache_is_bounded(monkeypatch):
    candles_api = _FakeCandlesAPI()
    client = _FakeCandleClient(candles_api)

    # Fresh-but-ordered expires (MKT-0 oldest). Using a real ``time.monotonic()``
    # base keeps every entry newer than the cleanup age-cutoff
    # (``now - max_age_minutes*60``) regardless of host uptime; the original
    # ``float(i)`` base made the test pass only on freshly-booted hosts.
    base = time.monotonic()
    prefilled = {
        (f"MKT-{i}", "1HOUR"): {"data": pd.Series([1.0]), "expires": base + i}
        for i in range(200)
    }

    monkeypatch.setattr(market_data, "CANDLES_RECENT_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(market_data, "_candles_recent_cache", prefilled)
    _patch_noop_cache(monkeypatch)
    monkeypatch.setattr(market_data, "_throttle_api_call", lambda: asyncio.sleep(0))

    asyncio.run(market_data.get_candles_recent(client, "NEW-MARKET"))

    assert len(market_data._candles_recent_cache) == 200
    assert ("MKT-0", "1HOUR") not in market_data._candles_recent_cache
    assert (
        "NEW-MARKET",
        market_data.DYDX_RESOLUTION,
    ) in market_data._candles_recent_cache


# ── Regression: the dict-vs-Series bug on an L2 hit ───────────────────────────


def test_get_candles_recent_returns_series_on_l2_hit(monkeypatch):
    """An L2 hit must return a ``pd.Series`` (not the raw response dict)."""
    candles_api = _FakeCandlesAPI()
    client = _FakeCandleClient(candles_api)
    l2_payload = {"candles": [{"close": "1.0"}, {"close": "2.0"}, {"close": "3.0"}]}
    cache = _RecordingCache(candles=l2_payload)

    monkeypatch.setattr(market_data, "CANDLES_RECENT_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(market_data, "_candles_recent_cache", {})
    monkeypatch.setattr(market_data, "get_market_data_cache", lambda: cache)
    monkeypatch.setattr(market_data, "_throttle_api_call", lambda: asyncio.sleep(0))

    result = asyncio.run(market_data.get_candles_recent(client, "BTC-USD"))

    assert candles_api.calls == 0  # served from L2, API never hit
    assert isinstance(result, pd.Series)
    # closes are reversed by _closes_to_series
    assert list(result) == [3.0, 2.0, 1.0]
    # L1 was populated so the next call short-circuits without the API
    assert ("BTC-USD", market_data.DYDX_RESOLUTION) in market_data._candles_recent_cache


def test_get_candles_recent_read_through_writes_l2(monkeypatch):
    """A live API fetch writes the raw response into the shared L2 cache."""
    raw = {"candles": [{"close": "9.0"}, {"close": "8.0"}]}
    candles_api = _FakeCandlesAPI(response=raw)
    client = _FakeCandleClient(candles_api)
    cache = _RecordingCache()

    monkeypatch.setattr(market_data, "CANDLES_RECENT_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(market_data, "_candles_recent_cache", {})
    monkeypatch.setattr(market_data, "get_market_data_cache", lambda: cache)
    monkeypatch.setattr(market_data, "_throttle_api_call", lambda: asyncio.sleep(0))

    asyncio.run(market_data.get_candles_recent(client, "BTC-USD"))

    assert len(cache.set_candles_calls) == 1
    market, resolution, payload, ttl = cache.set_candles_calls[0]
    assert market == "BTC-USD"
    assert payload == raw  # raw API response, not the Series
    assert ttl == 30.0


def test_get_markets_l2_hit_skips_api(monkeypatch):
    markets_api = _FakeMarketsAPI()
    client = _FakeClient(markets_api)
    shared = {"markets": {"ETH-USD": {"status": "ACTIVE"}}}
    cache = _RecordingCache(markets=shared)

    monkeypatch.setattr(market_data, "MARKETS_CACHE_TTL_SECONDS", 60.0)
    monkeypatch.setattr(market_data, "_markets_cache", {"data": None, "expires": 0.0})
    monkeypatch.setattr(market_data, "get_market_data_cache", lambda: cache)

    result = asyncio.run(market_data.get_markets(client))

    assert result == shared
    assert markets_api.calls == 0  # served from L2


def test_get_markets_read_through_writes_l2(monkeypatch):
    markets_api = _FakeMarketsAPI()
    client = _FakeClient(markets_api)
    cache = _RecordingCache()

    monkeypatch.setattr(market_data, "MARKETS_CACHE_TTL_SECONDS", 60.0)
    monkeypatch.setattr(market_data, "_markets_cache", {"data": None, "expires": 0.0})
    monkeypatch.setattr(market_data, "get_market_data_cache", lambda: cache)

    asyncio.run(market_data.get_markets(client))

    assert len(cache.set_markets_calls) == 1
    payload, ttl = cache.set_markets_calls[0]
    assert payload == {"markets": {"BTC-USD": {"status": "ACTIVE"}}}
    assert ttl == 60.0


# ── Cache module unit tests ───────────────────────────────────────────────────


def test_redis_cache_candles_round_trip_and_key():
    fake = _FakeAsyncRedis()
    cache = RedisMarketDataCache(
        url="redis://localhost:6379/0", ttl_candles=30, ttl_markets=60, client=fake
    )
    payload = {"candles": [{"close": "1.0"}, {"close": "2.0"}]}

    asyncio.run(cache.set_candles("BTC-USD", "1HOUR", payload, 30))
    got = asyncio.run(cache.get_candles("BTC-USD", "1HOUR"))

    assert got == payload
    # Producer-compatible key (matches market_sync_tasks.py)
    assert fake.set_calls[0][0] == "market:candles:BTC-USD:1HOUR"
    assert fake.set_calls[0][2] == 30  # TTL passed through as ex=


def test_redis_cache_markets_round_trip_and_key():
    fake = _FakeAsyncRedis()
    cache = RedisMarketDataCache(
        url="redis://localhost:6379/0", ttl_candles=30, ttl_markets=60, client=fake
    )
    payload = {"markets": {"BTC-USD": {"status": "ACTIVE"}}}

    asyncio.run(cache.set_markets(payload, 60))
    got = asyncio.run(cache.get_markets())

    assert got == payload
    assert fake.set_calls[0][0] == "market:markets"


def test_redis_cache_get_swallows_errors():
    fake = _FakeAsyncRedis(fail_get=True)
    cache = RedisMarketDataCache(
        url="redis://localhost:6379/0", ttl_candles=30, ttl_markets=60, client=fake
    )
    assert asyncio.run(cache.get_candles("BTC-USD", "1HOUR")) is None
    assert asyncio.run(cache.get_markets()) is None


def test_redis_cache_set_swallows_errors():
    fake = _FakeAsyncRedis(fail_set=True)
    cache = RedisMarketDataCache(
        url="redis://localhost:6379/0", ttl_candles=30, ttl_markets=60, client=fake
    )
    # Must not raise
    asyncio.run(cache.set_candles("BTC-USD", "1HOUR", {"candles": []}, 30))
    asyncio.run(cache.set_markets({"markets": {}}, 60))
    assert fake.set_calls == []


def test_redis_cache_decode_garbage_returns_none():
    fake = _FakeAsyncRedis()
    fake.store["market:candles:BTC-USD:1HOUR"] = "not-json{"
    cache = RedisMarketDataCache(
        url="redis://localhost:6379/0", ttl_candles=30, ttl_markets=60, client=fake
    )
    assert asyncio.run(cache.get_candles("BTC-USD", "1HOUR")) is None


def test_redis_cache_health():
    healthy = RedisMarketDataCache(
        url="redis://localhost:6379/0",
        ttl_candles=30,
        ttl_markets=60,
        client=_FakeAsyncRedis(),
    )
    assert asyncio.run(healthy.health())["healthy"] is True

    sick = RedisMarketDataCache(
        url="redis://localhost:6379/0",
        ttl_candles=30,
        ttl_markets=60,
        client=_FakeAsyncRedis(fail_ping=True),
    )
    health = asyncio.run(sick.health())
    assert health["healthy"] is False
    assert health["error"]


def test_redis_cache_aclose_is_idempotent():
    cache = RedisMarketDataCache(
        url="redis://localhost:6379/0",
        ttl_candles=30,
        ttl_markets=60,
        client=_FakeAsyncRedis(),
    )
    asyncio.run(cache.aclose())
    asyncio.run(cache.aclose())  # second close must not raise


def test_noop_cache_is_inert():
    noop = NoopMarketDataCache()
    assert asyncio.run(noop.get_candles("BTC-USD", "1HOUR")) is None
    assert asyncio.run(noop.get_markets()) is None
    asyncio.run(noop.set_candles("BTC-USD", "1HOUR", {"candles": []}, 30))
    asyncio.run(noop.set_markets({"markets": {}}, 60))
    assert asyncio.run(noop.health()) == {
        "enabled": False,
        "backend": "noop",
        "healthy": True,
        "error": None,
    }


def test_factory_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(market_cache_module, "MARKET_DATA_CACHE_ENABLED", False)
    reset_market_data_cache()
    try:
        assert isinstance(get_market_data_cache(), NoopMarketDataCache)
    finally:
        reset_market_data_cache()


def test_factory_no_url_returns_noop(monkeypatch):
    monkeypatch.setattr(market_cache_module, "MARKET_DATA_CACHE_ENABLED", True)
    monkeypatch.setattr(market_cache_module, "MARKET_DATA_CACHE_REDIS_URL", "")
    # Force the URL resolver to yield nothing so the empty-URL guard fires.
    monkeypatch.setattr(market_cache_module, "redis_url", lambda **_kw: "")
    reset_market_data_cache()
    try:
        assert isinstance(get_market_data_cache(), NoopMarketDataCache)
    finally:
        reset_market_data_cache()


def test_factory_enabled_with_url_builds_redis(monkeypatch):
    monkeypatch.setattr(market_cache_module, "MARKET_DATA_CACHE_ENABLED", True)
    monkeypatch.setattr(
        market_cache_module, "MARKET_DATA_CACHE_REDIS_URL", "redis://localhost:6379/0"
    )
    reset_market_data_cache()
    try:
        assert isinstance(get_market_data_cache(), RedisMarketDataCache)
    finally:
        reset_market_data_cache()


# ── Rate limiter behavior (unchanged) ─────────────────────────────────────────


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

    # Mock aiolimiter to be unavailable
    monkeypatch.setattr(market_data, "_rate_limiter_key", None)

    async def test_throttle_fallback():
        # This should not raise and should use sleep fallback
        await market_data._throttle_api_call()
        return True

    result = asyncio.run(test_throttle_fallback())
    assert result is True
