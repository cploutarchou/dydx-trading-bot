import asyncio
import types

from src.infrastructure.workers import market_sync_tasks


class _FakeRedis:
    def __init__(self):
        self.writes = []
        self.closed = False

    def set(self, key, value, ex=None):
        self.writes.append((key, value, ex))

    def close(self):
        self.closed = True


class _FakeMarkets:
    async def get_perpetual_markets(self):
        return {
            "markets": {
                "BTC-USD": {"status": "ACTIVE"},
                "ETH-USD": {"status": "ACTIVE"},
                "DOGE-USD": {"status": "PAUSED"},
            }
        }

    async def get_perpetual_market_candles(self, market, resolution, limit):
        return {
            "candles": [
                {
                    "market": market,
                    "resolution": resolution,
                    "limit": limit,
                    "close": "1.0",
                }
            ]
        }


class _FakeNode:
    async def close(self):
        return None


class _FakeClient:
    def __init__(self):
        self.indexer = types.SimpleNamespace(markets=_FakeMarkets())
        self.node = _FakeNode()


def test_sync_market_candles_disabled(monkeypatch):
    monkeypatch.setenv("MARKET_SYNC_ENABLED", "false")

    result = market_sync_tasks.sync_market_candles()

    assert result["status"] == "skipped"
    assert "MARKET_SYNC_ENABLED" in result["reason"]


def test_sync_market_candles_enabled_delegates_to_runner(monkeypatch):
    monkeypatch.setenv("MARKET_SYNC_ENABLED", "true")
    monkeypatch.setattr(
        market_sync_tasks,
        "_run_market_sync",
        lambda: {"status": "ok", "markets_synced": 2},
    )

    result = market_sync_tasks.sync_market_candles()

    assert result["status"] == "ok"
    assert result["markets_synced"] == 2


def test_sync_market_candles_async_writes_active_markets(monkeypatch):
    monkeypatch.setenv("MARKET_SYNC_ENABLED", "true")
    monkeypatch.setenv("MARKET_SYNC_RESOLUTION", "1HOUR")
    monkeypatch.setenv("MARKET_SYNC_CANDLE_LIMIT", "100")
    monkeypatch.setenv("MARKET_SYNC_REDIS_TTL_SECONDS", "30")
    monkeypatch.setenv("MARKET_SYNC_MAX_MARKETS", "10")
    monkeypatch.delenv("MARKET_SYNC_MARKETS", raising=False)

    fake_redis = _FakeRedis()
    monkeypatch.setattr(market_sync_tasks, "_get_redis_client", lambda: fake_redis)

    fake_dydx_module = types.ModuleType("src.trading.dydx_client")

    async def _fake_connect_dydx():
        return _FakeClient()

    fake_dydx_module.connect_dydx = _fake_connect_dydx
    monkeypatch.setitem(__import__("sys").modules, "src.trading.dydx_client", fake_dydx_module)

    result = asyncio.run(market_sync_tasks._sync_market_candles_async())

    assert result["status"] == "ok"
    assert result["markets_synced"] == 2
    assert result["markets_failed"] == 0
    assert len(fake_redis.writes) == 2
    assert all(write[0].startswith("market:candles:") for write in fake_redis.writes)
    assert all(write[2] == 30 for write in fake_redis.writes)
    assert fake_redis.closed is True
