import asyncio
import json
from types import SimpleNamespace

from src.trading import realtime_data_service


class _FakeRedis:
    def __init__(self, payloads):
        self.payloads = payloads
        self.closed = False

    def get(self, key):
        return self.payloads.get(key)

    def close(self):
        self.closed = True


class _FakeMarketRepo:
    def __init__(self, rows):
        self.rows = rows
        self.upserts = []

    def get_all_market_data(self, _bot_instance_id):
        return self.rows

    def upsert_market_data(self, **kwargs):
        self.upserts.append(kwargs)


class _FakeUow:
    def __init__(self, market_rows):
        self.market_data = _FakeMarketRepo(market_rows)


def test_extract_latest_close_uses_newest_started_at():
    payload = {
        "candles": [
            {"startedAt": "2026-05-16T10:00:00Z", "close": "101.5"},
            {"startedAt": "2026-05-16T10:10:00Z", "close": "103.25"},
            {"startedAt": "2026-05-16T09:50:00Z", "close": "99.8"},
        ]
    }

    value = realtime_data_service.RealTimeDataService._extract_latest_close(payload)

    assert value == 103.25


def test_update_market_data_applies_cached_price_and_broadcasts(monkeypatch):
    service = realtime_data_service.RealTimeDataService()
    service.market_sync_resolution = "1HOUR"

    btc_payload = json.dumps(
        {
            "candles": [
                {"startedAt": "2026-05-16T10:00:00Z", "close": "102.0"},
                {"startedAt": "2026-05-16T10:10:00Z", "close": "105.0"},
            ]
        }
    )
    redis_client = _FakeRedis({"market:candles:BTC-USD:1HOUR": btc_payload})
    monkeypatch.setattr(service, "_get_redis_client", lambda: redis_client)

    broadcasts = []

    async def _fake_broadcast(bot_instance_id, payload):
        broadcasts.append((bot_instance_id, payload))

    monkeypatch.setattr(realtime_data_service, "broadcast_market_update", _fake_broadcast)

    market_rows = [
        SimpleNamespace(
            symbol="BTC-USD",
            current_price=100.0,
            bid_price=None,
            ask_price=None,
            volume_24h=None,
            volatility_24h=None,
            rsi=None,
            macd=None,
            moving_avg_20=None,
            moving_avg_50=None,
            funding_rate=None,
        ),
        SimpleNamespace(
            symbol="ETH-USD",
            current_price=200.0,
            bid_price=None,
            ask_price=None,
            volume_24h=None,
            volatility_24h=None,
            rsi=None,
            macd=None,
            moving_avg_20=None,
            moving_avg_50=None,
            funding_rate=None,
        ),
    ]
    uow = _FakeUow(market_rows)

    asyncio.run(service._update_market_data(7, uow))

    assert len(uow.market_data.upserts) == 1
    assert uow.market_data.upserts[0]["symbol"] == "BTC-USD"
    assert uow.market_data.upserts[0]["current_price"] == 105.0
    assert market_rows[0].current_price == 105.0
    assert market_rows[1].current_price == 200.0

    assert len(broadcasts) == 2
    first_payload = broadcasts[0][1]
    assert first_payload["symbol"] == "BTC-USD"
    assert first_payload["current_price"] == 105.0
    assert redis_client.closed is True
