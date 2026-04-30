"""Regression tests for paired-position exit safety."""

import asyncio
import json

import pandas as pd
from src.trading import bot_agents_state, position_manager


def test_trade_opened_notification_maps_bot_agent_order_dict_keys():
    payload = position_manager._build_trade_opened_notification(
        {
            "market_1": "BTC-USD",
            "market_2": "ETH-USD",
            "order_m1_side": "SELL",
            "order_m2_side": "BUY",
            "order_m1_size": "0.2",
            "order_m2_size": "3.0",
            "order_id_m1": "base-order",
            "order_id_m2": "quote-order",
            "z_score": 2.4,
            "hedge_ratio": 0.72,
            "half_life": 11,
        }
    )

    assert payload == {
        "pair": "BTC-USD / ETH-USD",
        "base_market": "BTC-USD",
        "quote_market": "ETH-USD",
        "base_side": "SELL",
        "quote_side": "BUY",
        "base_size": "0.2",
        "quote_size": "3.0",
        "z_score": 2.4,
        "hedge_ratio": 0.72,
        "half_life": 11,
        "market_1_order_id": "base-order",
        "market_2_order_id": "quote-order",
    }


def test_trade_opened_notification_uses_fallback_context_when_payload_is_sparse():
    payload = position_manager._build_trade_opened_notification(
        {
            "z_score": -2.245,
            "hedge_ratio": -0.2032,
        },
        fallback_base_market="BCH-USD",
        fallback_quote_market="MET-USD",
        fallback_base_side="BUY",
        fallback_quote_side="SELL",
        fallback_base_size="0.02",
        fallback_quote_size="60",
        fallback_z_score=-2.245,
        fallback_hedge_ratio=-0.2032,
    )

    assert payload["pair"] == "BCH-USD / MET-USD"
    assert payload["base_market"] == "BCH-USD"
    assert payload["quote_market"] == "MET-USD"
    assert payload["base_side"] == "BUY"
    assert payload["quote_side"] == "SELL"
    assert payload["base_size"] == "0.02"
    assert payload["quote_size"] == "60"
    assert payload["z_score"] == -2.245
    assert payload["hedge_ratio"] == -0.2032


def test_manage_trade_exits_retries_second_leg_after_partial_close(monkeypatch, tmp_path):
    """If leg 1 closes and leg 2 fails, retry leg 2 instead of leaving exposure."""

    class DummyMessenger:
        def __init__(self):
            self.closed = []
            self.errors = []

        def send_trade_closed_message(self, trade_info, reason):
            self.closed.append((trade_info, reason))

        def send_error_message(self, *args, **kwargs):
            self.errors.append((args, kwargs))

    bot_agents_path = tmp_path / "bot_agents.json"
    bot_agents_path.write_text(
        json.dumps(
            [
                {
                    "market_1": "BTC-USD",
                    "market_2": "ETH-USD",
                    "order_id_m1": "m1-entry",
                    "order_id_m2": "m2-entry",
                    "order_m1_size": "0.1",
                    "order_m2_size": "1.0",
                    "order_m1_side": "BUY",
                    "order_m2_side": "SELL",
                    "z_score": -1.5,
                    "hedge_ratio": 1.0,
                    "pair_status": "LIVE",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)
    monkeypatch.setattr(position_manager, "BOT_AGENTS_PATH", bot_agents_path)
    monkeypatch.setattr(position_manager, "TelegramMessenger", DummyMessenger)

    async def fake_get_open_positions(_client):
        return {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        }

    async def fake_get_order(_client, order_id):
        orders = {
            "m1-entry": {"ticker": "BTC-USD", "size": "0.1", "side": "BUY"},
            "m2-entry": {"ticker": "ETH-USD", "size": "1.0", "side": "SELL"},
        }
        return orders[order_id]

    async def fake_get_candles_recent(_client, _market):
        return pd.Series([100.0, 101.0, 102.0])

    async def fake_get_markets(_client):
        return {
            "markets": {
                "BTC-USD": {"tickSize": "0.1"},
                "ETH-USD": {"tickSize": "0.01"},
            }
        }

    async def fake_sleep(_seconds):
        return None

    def fake_calculate_zscore(_spread):
        return pd.Series([2.0])

    calls = []

    async def fake_place_market_order(
            _client,
            market,
            side,
            size,
            price,
            reduce_only,
    ):
        calls.append(
            {
                "market": market,
                "side": side,
                "size": size,
                "price": price,
                "reduce_only": reduce_only,
            }
        )
        if market == "BTC-USD":
            return {"id": "close-m1"}, "close-m1"
        if len([call for call in calls if call["market"] == "ETH-USD"]) <= 3:
            raise RuntimeError("temporary ETH close failure")
        return {"id": "close-m2"}, "close-m2"

    monkeypatch.setattr(position_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(position_manager, "get_order", fake_get_order)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "calculate_zscore", fake_calculate_zscore)
    monkeypatch.setattr(position_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(position_manager.asyncio, "sleep", fake_sleep)

    asyncio.run(position_manager.manage_trade_exits(object()))

    assert calls[0]["market"] == "BTC-USD"
    assert calls[0]["reduce_only"] is True
    eth_calls = [call for call in calls if call["market"] == "ETH-USD"]
    assert len(eth_calls) == 4
    assert all(call["reduce_only"] is True for call in eth_calls)
    assert json.loads(bot_agents_path.read_text(encoding="utf-8")) == []
