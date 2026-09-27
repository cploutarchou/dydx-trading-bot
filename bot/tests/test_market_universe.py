"""Market universe selection for the perpetual markets route."""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from src.api import server
from src.api.market_universe import (
    MarketRecord,
    market_universe_payload,
    normalize_market_records,
    select_market_universe,
)

RAW_MARKETS = {
    "BTC-USD": {
        "status": "ACTIVE",
        "volume24H": "2377823.0794",
        "openInterest": "191.6390",
        "oraclePrice": "84143.7",
        "nextFundingRate": "-0.00000027",
        "trades24H": 1346,
        "priceChange24H": "273.98913",
    },
    "ETH-USD": {
        "status": "ACTIVE",
        "volume24H": "900000.5",
        "openInterest": "10",
        "oraclePrice": "2000",
        "nextFundingRate": "0.00001",
        "trades24H": "400",
    },
    "SOL-USD": {
        "status": "ACTIVE",
        "volume24H": "1500000",
        "openInterest": "n/a",
        "oraclePrice": "150",
        "nextFundingRate": None,
        "trades24H": 90,
        "priceChange24H": "n/a",
    },
    "AAVE-USD": {
        "status": "FINAL_SETTLEMENT",
        "volume24H": "0",
        "openInterest": "0",
        "oraclePrice": "0",
        "nextFundingRate": "0",
        "trades24H": 0,
    },
    "NEW-USD": {"status": "ACTIVE"},
    "ODD-USD": "not a mapping",
    "": {"status": "ACTIVE", "volume24H": "5"},
}


def _record(ticker, status="ACTIVE", volume=None):
    return MarketRecord(
        ticker=ticker,
        status=status,
        volume_24h=volume,
        open_interest=None,
        open_interest_usd=None,
        next_funding_rate=None,
        oracle_price=None,
        trades_24h=None,
        price_change_24h=None,
    )


def test_normalize_parses_metrics_and_derives_usd_open_interest():
    records = {
        record.ticker: record for record in normalize_market_records(RAW_MARKETS)
    }

    assert set(records) == {
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "AAVE-USD",
        "NEW-USD",
        "ODD-USD",
    }
    btc = records["BTC-USD"]
    assert btc.status == "ACTIVE"
    assert btc.volume_24h == pytest.approx(2377823.0794)
    assert btc.open_interest_usd == pytest.approx(191.6390 * 84143.7)
    assert btc.next_funding_rate == pytest.approx(-0.00000027)
    assert btc.trades_24h == 1346
    # priceChange24H is passed through as the indexer gives it (a quote-currency
    # change, not a percentage).
    assert btc.price_change_24h == pytest.approx(273.98913)
    assert records["ETH-USD"].trades_24h == 400
    # Unparseable and missing metrics become None, never a guess.
    sol = records["SOL-USD"]
    assert sol.open_interest is None and sol.open_interest_usd is None
    assert sol.next_funding_rate is None
    assert sol.price_change_24h is None
    assert records["NEW-USD"].volume_24h is None
    assert records["NEW-USD"].price_change_24h is None
    assert records["ODD-USD"].status == "UNKNOWN"


def test_normalize_rejects_non_mapping_input():
    assert normalize_market_records(None) == []
    assert normalize_market_records(["BTC-USD"]) == []


def test_select_defaults_to_active_markets_by_volume_with_unknown_volume_last():
    selected = select_market_universe(normalize_market_records(RAW_MARKETS))

    assert [record.ticker for record in selected] == [
        "BTC-USD",
        "SOL-USD",
        "ETH-USD",
        "NEW-USD",
    ]


def test_select_can_include_settled_markets_and_caps_after_sorting():
    records = normalize_market_records(RAW_MARKETS)

    everything = select_market_universe(records, include_settled=True)
    assert [record.ticker for record in everything] == [
        "BTC-USD",
        "SOL-USD",
        "ETH-USD",
        "AAVE-USD",
        "NEW-USD",
        "ODD-USD",
    ]

    capped = select_market_universe(records, cap=2)
    assert [record.ticker for record in capped] == ["BTC-USD", "SOL-USD"]
    assert [r.ticker for r in select_market_universe(records, cap=0)] == [
        r.ticker for r in select_market_universe(records)
    ]


def test_select_breaks_volume_ties_by_ticker():
    records = [_record("ZZZ-USD", volume=10.0), _record("AAA-USD", volume=10.0)]

    assert [r.ticker for r in select_market_universe(records)] == ["AAA-USD", "ZZZ-USD"]


def test_payload_reports_totals_and_echoes_the_selection():
    payload = market_universe_payload(
        normalize_market_records(RAW_MARKETS),
        include_settled=False,
        cap=3,
        source="dydx",
    )

    assert payload["markets"] == ["BTC-USD", "SOL-USD", "ETH-USD"]
    assert [d["ticker"] for d in payload["market_details"]] == payload["markets"]
    assert payload["market_details"][0]["volume_24h"] == pytest.approx(2377823.0794)
    assert payload["market_details"][0]["price_change_24h"] == pytest.approx(273.98913)
    assert payload["market_details"][1]["price_change_24h"] is None
    assert payload["count"] == 3
    assert payload["source"] == "dydx"
    assert payload["include_settled"] is False
    assert payload["active_total"] == 4
    assert payload["inactive_total"] == 2


# --- route -----------------------------------------------------------------


class _FakeClient:
    def __init__(self, raw):
        self._raw = raw

        async def get_perpetual_markets():
            return {"markets": raw}

        self.indexer = SimpleNamespace(
            markets=SimpleNamespace(get_perpetual_markets=get_perpetual_markets)
        )


@pytest.fixture
def markets_route(monkeypatch):
    server._markets_cache.clear()
    calls = {"count": 0}

    async def fake_connect():
        calls["count"] += 1
        return _FakeClient(RAW_MARKETS)

    monkeypatch.setattr(server, "connect_dydx", fake_connect)
    yield calls
    server._markets_cache.clear()


def _call(**kwargs):
    response = asyncio.run(server.list_perpetual_markets(**kwargs))
    return response.status_code, dict(response.headers), json.loads(response.body)


def test_route_serves_active_markets_by_volume_and_then_the_cache(markets_route):
    status, headers, body = _call(limit=0, include_settled=False)

    assert status == 200
    assert body["data"]["markets"] == ["BTC-USD", "SOL-USD", "ETH-USD", "NEW-USD"]
    assert body["data"]["source"] == "dydx"
    assert body["data"]["active_total"] == 4
    assert body["data"]["market_details"][0]["price_change_24h"] == pytest.approx(
        273.98913
    )
    assert "x-cache-hit" not in headers

    status, headers, body = _call(limit=2, include_settled=True)

    assert status == 200
    assert headers.get("x-cache-hit") == "1"
    assert body["data"]["source"] == "cache"
    assert body["data"]["markets"] == ["BTC-USD", "SOL-USD"]
    assert body["data"]["include_settled"] is True
    assert markets_route["count"] == 1


def test_route_falls_back_to_the_stale_cache_with_the_same_selection(
    markets_route, monkeypatch
):
    _call(limit=0, include_settled=False)
    with server._markets_cache_lock:
        server._markets_cache["last"]["expires_at"] = time.monotonic() - 10

    async def failing_connect():
        raise RuntimeError("indexer down")

    monkeypatch.setattr(server, "connect_dydx", failing_connect)

    status, headers, body = _call(limit=0, include_settled=False)

    assert status == 200
    assert headers.get("x-cache-stale") == "1"
    assert body["data"]["source"] == "cache_stale"
    assert body["data"]["markets"] == ["BTC-USD", "SOL-USD", "ETH-USD", "NEW-USD"]


def test_route_fails_closed_without_live_data_or_cache(monkeypatch):
    server._markets_cache.clear()

    async def failing_connect():
        raise RuntimeError("indexer down")

    monkeypatch.setattr(server, "connect_dydx", failing_connect)

    status, _headers, body = _call(limit=0, include_settled=False)

    assert status == 503
    assert body["success"] is False
    server._markets_cache.clear()
