"""Regression tests for paired-position exit safety."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

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


def test_manage_trade_exits_keeps_orphan_state_when_second_leg_close_fails(
    monkeypatch, tmp_path
):
    """If leg 1 closes and leg 2 fails, preserve the orphaned state for recovery."""

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
    assert len(eth_calls) == 3
    assert all(call["reduce_only"] is True for call in eth_calls)
    remaining = json.loads(bot_agents_path.read_text(encoding="utf-8"))
    assert remaining[0]["pair_status"] == "ORPHANED_EXIT_FAILED"
    assert remaining[0]["orphaned_market"] == "ETH-USD"


def _tracked_live_position():
    opened_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    return {
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "order_id_m1": "m1-entry",
        "order_id_m2": "m2-entry",
        "order_m1_size": "0.1",
        "order_m2_size": "1.0",
        "order_m1_side": "BUY",
        "order_m2_side": "SELL",
        "order_m1_price": "100.0",
        "order_m2_price": "100.0",
        "order_time_m1": opened_at,
        "order_time_m2": opened_at,
        "z_score": -1.5,
        "hedge_ratio": 1.0,
        "pair_status": "LIVE",
    }


def _install_exit_test_runtime(monkeypatch, tmp_path, open_positions_sequence):
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
        json.dumps([_tracked_live_position()]),
        encoding="utf-8",
    )
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)
    monkeypatch.setattr(position_manager, "BOT_AGENTS_PATH", bot_agents_path)
    monkeypatch.setattr(position_manager, "TelegramMessenger", DummyMessenger)
    monkeypatch.setenv("BOT_EXIT_CONFIRM_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("BOT_EXIT_CONFIRM_DELAY_SECONDS", "0.1")

    call_index = {"value": 0}

    async def fake_get_open_positions(_client):
        index = min(call_index["value"], len(open_positions_sequence) - 1)
        call_index["value"] += 1
        return open_positions_sequence[index]

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

    async def fake_place_market_order(
        _client,
        market,
        side,
        size,
        price,
        reduce_only,
    ):
        return {"id": f"close-{market}"}, f"close-{market}"

    async def fake_get_order_fills(*_args, **_kwargs):
        return []

    monkeypatch.setattr(position_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(position_manager, "get_order", fake_get_order)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "calculate_zscore", fake_calculate_zscore)
    monkeypatch.setattr(position_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(position_manager, "get_order_fills", fake_get_order_fills)
    monkeypatch.setattr(position_manager.asyncio, "sleep", fake_sleep)

    return bot_agents_path, DummyMessenger


def test_manage_trade_exits_does_not_mark_closed_without_flat_confirmation(
    monkeypatch, tmp_path
):
    open_sequence = [
        {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        },
        {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        },
        {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        },
    ]
    bot_agents_path, _messenger_cls = _install_exit_test_runtime(
        monkeypatch, tmp_path, open_sequence
    )

    persisted = []
    monkeypatch.setattr(
        position_manager,
        "persist_live_trade_closed",
        lambda *_args, **_kwargs: persisted.append("closed"),
    )

    asyncio.run(position_manager.manage_trade_exits(object()))

    remaining = json.loads(bot_agents_path.read_text(encoding="utf-8"))
    assert persisted == []
    assert len(remaining) == 1
    assert remaining[0]["pair_status"] == "CLOSING"
    assert remaining[0]["timed_out"] is True


def test_manage_trade_exits_marks_close_confirmed_only_after_flat_exchange_state(
    monkeypatch, tmp_path
):
    open_sequence = [
        {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        },
        {},
    ]
    bot_agents_path, _messenger_cls = _install_exit_test_runtime(
        monkeypatch, tmp_path, open_sequence
    )

    persisted = []
    monkeypatch.setattr(
        position_manager,
        "persist_live_trade_closed",
        lambda *_args, **_kwargs: persisted.append("closed") or "trade-1",
    )

    asyncio.run(position_manager.manage_trade_exits(object()))

    assert persisted == ["closed"]
    assert json.loads(bot_agents_path.read_text(encoding="utf-8")) == []


def test_manage_trade_exits_persists_partial_close_state(monkeypatch, tmp_path):
    open_sequence = [
        {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        },
        {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.05"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "0.5"},
        },
        {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.05"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "0.5"},
        },
    ]
    bot_agents_path, _messenger_cls = _install_exit_test_runtime(
        monkeypatch, tmp_path, open_sequence
    )

    persisted = []
    monkeypatch.setattr(
        position_manager,
        "persist_live_trade_closed",
        lambda *_args, **_kwargs: persisted.append("closed"),
    )

    asyncio.run(position_manager.manage_trade_exits(object()))

    remaining = json.loads(bot_agents_path.read_text(encoding="utf-8"))
    assert persisted == []
    assert remaining[0]["pair_status"] == "PARTIALLY_CLOSED"


def test_manage_trade_exits_marks_orphan_when_second_leg_close_fails(
    monkeypatch, tmp_path
):
    open_sequence = [
        {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        }
    ]
    bot_agents_path, _messenger_cls = _install_exit_test_runtime(
        monkeypatch, tmp_path, open_sequence
    )

    async def fake_place_market_order(
        _client,
        market,
        side,
        size,
        price,
        reduce_only,
    ):
        if market == "BTC-USD":
            return {"id": "close-BTC-USD"}, "close-BTC-USD"
        raise RuntimeError("exchange rejected second leg")

    persisted = []
    monkeypatch.setattr(position_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(
        position_manager,
        "persist_live_trade_closed",
        lambda *_args, **_kwargs: persisted.append("closed"),
    )

    asyncio.run(position_manager.manage_trade_exits(object()))

    remaining = json.loads(bot_agents_path.read_text(encoding="utf-8"))
    assert persisted == []
    assert remaining[0]["pair_status"] == "ORPHANED_EXIT_FAILED"
    assert remaining[0]["orphaned_market"] == "ETH-USD"


def test_manage_trade_exits_isolates_poisoned_position(monkeypatch, tmp_path):
    """A position whose order records are unreadable must not block exits for others."""

    class DummyMessenger:
        def __init__(self):
            self.errors = []
            self.closed = []

        def send_trade_closed_message(self, trade_info, reason):
            self.closed.append((trade_info, reason))

        def send_error_message(self, *args, **kwargs):
            self.errors.append((args, kwargs))

    messenger = DummyMessenger()

    def make_position(m1, m2, id1, id2):
        return {
            "market_1": m1,
            "market_2": m2,
            "order_id_m1": id1,
            "order_id_m2": id2,
            "order_m1_size": "0.1",
            "order_m2_size": "1.0",
            "order_m1_side": "BUY",
            "order_m2_side": "SELL",
            "z_score": -1.5,
            "hedge_ratio": 1.0,
            "pair_status": "LIVE",
        }

    bot_agents_path = tmp_path / "bot_agents.json"
    bot_agents_path.write_text(
        json.dumps(
            [
                make_position("POISON-USD", "ETH-USD", "bad-m1", "bad-m2"),
                make_position("BTC-USD", "ETH-USD", "good-m1", "good-m2"),
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)
    monkeypatch.setattr(position_manager, "BOT_AGENTS_PATH", bot_agents_path)
    monkeypatch.setattr(position_manager, "TelegramMessenger", lambda: messenger)

    async def fake_get_open_positions(_client):
        return {
            "POISON-USD": {"market": "POISON-USD", "side": "LONG", "sumOpen": "0.1"},
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        }

    async def fake_get_order(_client, order_id):
        if order_id.startswith("bad"):
            raise ConnectionError("indexer 500")
        orders = {
            "good-m1": {"ticker": "BTC-USD", "size": "0.1", "side": "BUY"},
            "good-m2": {"ticker": "ETH-USD", "size": "1.0", "side": "SELL"},
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

    closes = []

    async def fake_place_market_order(_client, market, side, size, price, reduce_only):
        closes.append({"market": market, "reduce_only": reduce_only})
        return {"id": f"close-{market}"}, f"close-{market}"

    monkeypatch.setattr(position_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(position_manager, "get_order", fake_get_order)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "calculate_zscore", fake_calculate_zscore)
    monkeypatch.setattr(position_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(position_manager.asyncio, "sleep", fake_sleep)

    asyncio.run(position_manager.manage_trade_exits(object()))

    # The healthy BTC/ETH pair was still exit-managed (both legs closed).
    closed_markets = {c["market"] for c in closes}
    assert {"BTC-USD", "ETH-USD"} <= closed_markets
    # The poisoned position stays tracked and raised a critical alert.
    remaining = json.loads(bot_agents_path.read_text(encoding="utf-8"))
    poison = [p for p in remaining if p["market_1"] == "POISON-USD"]
    assert len(poison) == 1
    assert poison[0]["last_exit_error"]
    assert any(kwargs.get("is_critical") for _args, kwargs in messenger.errors)


def test_manage_trade_exits_persists_fills_vwap_not_accept_price(monkeypatch, tmp_path):
    """Recorded exit prices must be execution prices (fills VWAP), not the
    ±5% accept-band prices used at submission (audit F8)."""

    class DummyMessenger:
        def send_trade_closed_message(self, trade_info, reason):
            pass

        def send_error_message(self, *args, **kwargs):
            pass

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
    monkeypatch.setattr(position_manager, "TelegramMessenger", lambda: DummyMessenger())

    open_positions_calls = []

    async def fake_get_open_positions(_client):
        # First call (matching) reports the pair open; every later call
        # (post-close confirmation) reports flat.
        open_positions_calls.append(1)
        if len(open_positions_calls) > 1:
            return {}
        return {
            "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
            "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
        }

    async def fake_get_order(_client, order_id):
        orders = {
            "m1-entry": {"ticker": "BTC-USD", "size": "0.1", "side": "BUY"},
            "m2-entry": {"ticker": "ETH-USD", "size": "1.0", "side": "SELL"},
            "close-BTC-USD": {"ticker": "BTC-USD", "size": "0.1", "side": "SELL"},
            "close-ETH-USD": {"ticker": "ETH-USD", "size": "1.0", "side": "BUY"},
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

    async def fake_place_market_order(_client, market, side, size, price, reduce_only):
        # Record the ACCEPT price the order was submitted with.
        accepts[market] = price
        return {"id": f"close-{market}"}, f"close-{market}"

    async def fake_get_order_fills(_client, order_id, market=None):
        if order_id == "close-BTC-USD":
            return [
                {"orderId": order_id, "price": "99900", "size": "0.06"},
                {"orderId": order_id, "price": "100100", "size": "0.04"},
            ]
        return [{"orderId": order_id, "price": "2990", "size": "1.0"}]

    persisted = {}

    def fake_persist_live_trade_closed(position, exit_price1, exit_price2, **kwargs):
        persisted["exit_price1"] = exit_price1
        persisted["exit_price2"] = exit_price2
        return "trade-1"

    accepts = {}

    monkeypatch.setattr(position_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(position_manager, "get_order", fake_get_order)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "calculate_zscore", fake_calculate_zscore)
    monkeypatch.setattr(position_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(position_manager, "get_order_fills", fake_get_order_fills)
    monkeypatch.setattr(
        position_manager, "persist_live_trade_closed", fake_persist_live_trade_closed
    )
    monkeypatch.setattr(position_manager.asyncio, "sleep", fake_sleep)

    asyncio.run(position_manager.manage_trade_exits(object()))

    # Flat exchange state => close confirmed => persistence ran with VWAPs.
    assert persisted, "expected persist_live_trade_closed to run"
    # BTC VWAP = (99900*0.06 + 100100*0.04) / 0.10 = 99980.0
    assert float(persisted["exit_price1"]) == pytest.approx(99980.0)
    # ETH single fill at 2990 — NOT the ±5% accept price.
    assert float(persisted["exit_price2"]) == pytest.approx(2990.0)
    # Neither leg recorded its ±5% accept-band submission price.
    assert float(persisted["exit_price1"]) != pytest.approx(float(accepts["BTC-USD"]))
    assert float(persisted["exit_price2"]) != pytest.approx(float(accepts["ETH-USD"]))
