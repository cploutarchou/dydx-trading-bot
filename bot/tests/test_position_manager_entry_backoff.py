"""Regression tests for entry failure cooldown in open_positions."""

import asyncio

import pandas as pd
from src.trading import position_manager


class _Pair:
    def __init__(self, payload):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


def test_open_positions_applies_pair_backoff_after_entry_exception(monkeypatch):
    position_manager._ENTRY_FAILURE_STATE.clear()

    now = {"value": 100.0}

    def _now():
        return now["value"]

    monkeypatch.setattr(position_manager, "_entry_backoff_now", _now)
    monkeypatch.setenv("ENTRY_FAILURE_BACKOFF_BASE_SECONDS", "60")
    monkeypatch.setenv("ENTRY_FAILURE_BACKOFF_MULTIPLIER", "2")

    monkeypatch.setattr(
        position_manager.pair_storage,
        "load_pairs",
        lambda: [
            _Pair(
                {
                    "base_market": "DOT-USD",
                    "quote_market": "CRO-USD",
                    "hedge_ratio": 0.03,
                    "half_life": 10,
                }
            )
        ],
    )

    async def fake_get_markets(_client):
        return {
            "markets": {
                "DOT-USD": {"tickSize": "0.001", "stepSize": "1", "oraclePrice": "1.2"},
                "CRO-USD": {
                    "tickSize": "0.00001",
                    "stepSize": "1",
                    "oraclePrice": "0.07",
                },
            }
        }

    async def fake_get_candles_recent(_client, market):
        if market == "DOT-USD":
            return pd.Series([1.2, 1.21, 1.22])
        return pd.Series([0.07, 0.068, 0.067])

    def fake_calculate_zscore(_spread):
        return pd.Series([2.0])

    async def fake_is_open_positions(_client, _market):
        return False

    async def fake_get_account(_client):
        return {"freeCollateral": "10000"}

    class FailingAgent:
        calls = 0

        def __init__(self, *_args, **_kwargs):
            pass

        async def open_trades(self):
            FailingAgent.calls += 1
            raise RuntimeError("simulated indexer lag")

    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(position_manager, "calculate_zscore", fake_calculate_zscore)
    monkeypatch.setattr(position_manager, "is_open_positions", fake_is_open_positions)
    monkeypatch.setattr(position_manager, "get_account", fake_get_account)
    monkeypatch.setattr(position_manager, "BotAgent", FailingAgent)

    asyncio.run(position_manager.open_positions(object()))
    assert FailingAgent.calls == 1

    # Same timestamp => cooldown should skip second attempt.
    asyncio.run(position_manager.open_positions(object()))
    assert FailingAgent.calls == 1

    pair_key = "DOT-USD|CRO-USD"
    assert pair_key in position_manager._ENTRY_FAILURE_STATE


def test_open_positions_clears_backoff_after_success(monkeypatch):
    position_manager._ENTRY_FAILURE_STATE.clear()

    now = {"value": 200.0}

    def _now():
        return now["value"]

    monkeypatch.setattr(position_manager, "_entry_backoff_now", _now)
    monkeypatch.setenv("ENTRY_FAILURE_BACKOFF_BASE_SECONDS", "5")

    monkeypatch.setattr(
        position_manager.pair_storage,
        "load_pairs",
        lambda: [
            _Pair(
                {
                    "base_market": "XLM-USD",
                    "quote_market": "ZEN-USD",
                    "hedge_ratio": 0.04,
                    "half_life": 12,
                }
            )
        ],
    )

    async def fake_get_markets(_client):
        return {
            "markets": {
                "XLM-USD": {
                    "tickSize": "0.0001",
                    "stepSize": "1",
                    "oraclePrice": "0.16",
                },
                "ZEN-USD": {"tickSize": "0.001", "stepSize": "1", "oraclePrice": "5.7"},
            }
        }

    async def fake_get_candles_recent(_client, market):
        if market == "XLM-USD":
            return pd.Series([0.16, 0.1605, 0.161])
        return pd.Series([5.7, 5.72, 5.74])

    def fake_calculate_zscore(_spread):
        return pd.Series([2.1])

    async def fake_is_open_positions(_client, _market):
        return False

    async def fake_get_account(_client):
        return {"freeCollateral": "10000"}

    class FlakyThenSuccessAgent:
        calls = 0

        def __init__(self, *_args, **_kwargs):
            pass

        async def open_trades(self):
            FlakyThenSuccessAgent.calls += 1
            if FlakyThenSuccessAgent.calls == 1:
                raise RuntimeError("temporary failure")
            return {
                "pair_status": "LIVE",
                "market_1": "XLM-USD",
                "market_2": "ZEN-USD",
                "order_m1_side": "BUY",
                "order_m2_side": "SELL",
                "order_m1_size": "60",
                "order_m2_size": "1",
                "order_id_m1": "m1",
                "order_id_m2": "m2",
                "z_score": 2.1,
                "hedge_ratio": 0.04,
                "half_life": 12,
            }

    async def _no_op_append(_payload):
        return None

    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(position_manager, "calculate_zscore", fake_calculate_zscore)
    monkeypatch.setattr(position_manager, "is_open_positions", fake_is_open_positions)
    monkeypatch.setattr(position_manager, "get_account", fake_get_account)
    monkeypatch.setattr(position_manager, "BotAgent", FlakyThenSuccessAgent)
    monkeypatch.setattr(position_manager, "append_tracked_position", _no_op_append)
    monkeypatch.setattr(
        position_manager, "persist_live_trade_opened", lambda _payload: None
    )

    asyncio.run(position_manager.open_positions(object()))
    pair_key = "XLM-USD|ZEN-USD"
    assert pair_key in position_manager._ENTRY_FAILURE_STATE

    # Advance beyond cooldown and run again; success should clear state.
    now["value"] += 10.0
    asyncio.run(position_manager.open_positions(object()))
    assert pair_key not in position_manager._ENTRY_FAILURE_STATE


def test_open_positions_enforces_max_positions(monkeypatch):
    position_manager._ENTRY_FAILURE_STATE.clear()
    monkeypatch.setattr(position_manager, "MAX_POSITIONS", 1)

    monkeypatch.setattr(
        position_manager.pair_storage,
        "load_pairs",
        lambda: [
            _Pair(
                {
                    "base_market": "LINK-USD",
                    "quote_market": "ATOM-USD",
                    "hedge_ratio": 0.1,
                    "half_life": 12,
                }
            )
        ],
    )

    async def fake_get_markets(_client):
        return {
            "markets": {
                "LINK-USD": {
                    "tickSize": "0.001",
                    "stepSize": "1",
                    "oraclePrice": "10.0",
                },
                "ATOM-USD": {
                    "tickSize": "0.001",
                    "stepSize": "1",
                    "oraclePrice": "8.0",
                },
            }
        }

    async def fake_get_candles_recent(_client, market):
        if market == "LINK-USD":
            return pd.Series([10.0, 10.1, 10.2])
        return pd.Series([8.0, 7.9, 7.8])

    def fake_calculate_zscore(_spread):
        return pd.Series([2.0])

    async def fake_is_open_positions(_client, _market):
        return False

    async def fake_load_tracked_positions():
        return [{"market_1": "BTC-USD", "market_2": "ETH-USD"}]

    class ShouldNotOpenAgent:
        def __init__(self, *_args, **_kwargs):  # pragma: no cover - safety assertion
            raise AssertionError(
                "BotAgent should not be constructed when max_positions is reached"
            )

    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(position_manager, "calculate_zscore", fake_calculate_zscore)
    monkeypatch.setattr(position_manager, "is_open_positions", fake_is_open_positions)
    monkeypatch.setattr(
        position_manager, "load_tracked_positions", fake_load_tracked_positions
    )
    monkeypatch.setattr(position_manager, "BotAgent", ShouldNotOpenAgent)

    asyncio.run(position_manager.open_positions(object()))
