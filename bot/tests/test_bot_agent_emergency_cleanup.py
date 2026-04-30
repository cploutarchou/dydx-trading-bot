"""Regression tests for BotAgent emergency cleanup behavior."""

import asyncio

from src.trading.bot_agent import BotAgent


def test_open_trades_returns_error_dict_after_second_leg_failure(monkeypatch):
    """If second leg fails, bot should emergency-close first leg and return error dict."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    async def fake_place_market_order(
            client,
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
        if len(calls) == 1:
            return ({"ok": True}, "m1-order")
        if len(calls) == 2:
            return ({"ok": True}, "m2-order")
        return ({"ok": True}, "m1-close-order")

    async def fake_check_order_status(client, order_id):
        status_map = {
            "m1-order": "FILLED",
            "m2-order": "CANCELED",
            "m1-close-order": "FILLED",
        }
        return status_map[order_id]

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr("src.trading.bot_agent.place_market_order", fake_place_market_order)
    monkeypatch.setattr("src.trading.bot_agent.check_order_status", fake_check_order_status)

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    calls = []
    agent = BotAgent(
        client=object(),
        market_1="BTC-USD",
        market_2="ETH-USD",
        base_side="BUY",
        base_size="0.1",
        base_price="100000",
        quote_side="SELL",
        quote_size="1",
        quote_price="3000",
        accept_failsafe_base_price="90000",
        z_score=2.0,
        half_life=10,
        hedge_ratio=0.5,
    )

    result = asyncio.run(agent.open_trades())

    assert isinstance(result, dict)
    assert result["pair_status"] == "ERROR"
    assert result["order_id_m1"] == "m1-order"
    assert result["order_id_m2"] == "m2-order"

    # Ensure emergency cleanup (reduce_only=True) was attempted for first market
    assert len(calls) == 3
    assert calls[-1]["market"] == "BTC-USD"
    assert calls[-1]["side"] == "SELL"
    assert calls[-1]["reduce_only"] is True


def test_open_trades_emergency_closes_first_leg_when_second_leg_placement_raises(monkeypatch):
    """If second leg placement raises after first fill, first leg must be reduced-only closed."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    async def fake_place_market_order(
            client,
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
        if len(calls) == 1:
            return ({"ok": True}, "m1-order")
        if len(calls) == 2:
            raise RuntimeError("exchange rejected second leg")
        return ({"ok": True}, "m1-close-order")

    async def fake_check_order_status(client, order_id):
        status_map = {
            "m1-order": "FILLED",
            "m1-close-order": "FILLED",
        }
        return status_map[order_id]

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr("src.trading.bot_agent.place_market_order", fake_place_market_order)
    monkeypatch.setattr("src.trading.bot_agent.check_order_status", fake_check_order_status)

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    calls = []
    agent = BotAgent(
        client=object(),
        market_1="BTC-USD",
        market_2="ETH-USD",
        base_side="BUY",
        base_size="0.1",
        base_price="100000",
        quote_side="SELL",
        quote_size="1",
        quote_price="3000",
        accept_failsafe_base_price="90000",
        z_score=2.0,
        half_life=10,
        hedge_ratio=0.5,
    )

    result = asyncio.run(agent.open_trades())

    assert result["pair_status"] == "ERROR"
    assert result["order_id_m1"] == "m1-order"
    assert result["order_id_m2"] == ""
    assert len(calls) == 3
    assert calls[-1]["market"] == "BTC-USD"
    assert calls[-1]["side"] == "SELL"
    assert calls[-1]["reduce_only"] is True


def test_open_trades_reconciles_entry_prices_from_weighted_fills(monkeypatch):
    """Successful live entries should persist actual weighted fill prices."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    async def fake_place_market_order(
            client,
            market,
            side,
            size,
            price,
            reduce_only,
    ):
        calls.append({"market": market, "side": side, "size": size, "price": price})
        if market == "BTC-USD":
            return ({"ok": True}, "m1-order")
        return ({"ok": True}, "m2-order")

    async def fake_check_order_status(client, order_id):
        return "FILLED"

    async def fake_get_order(client, order_id):
        orders = {
            "m1-order": {
                "ticker": "BTC-USD",
                "side": "BUY",
                "size": "0.2",
                "price": "100000",
            },
            "m2-order": {
                "ticker": "ETH-USD",
                "side": "SELL",
                "size": "1.5",
                "price": "3000",
            },
        }
        return orders[order_id]

    async def fake_get_order_fills(client, order_id, market=None):
        fills = {
            "m1-order": [
                {"orderId": "m1-order", "price": "99900", "size": "0.1"},
                {"orderId": "m1-order", "price": "100100", "size": "0.1"},
            ],
            "m2-order": [
                {"orderId": "m2-order", "price": "2995", "size": "1.0"},
                {"orderId": "m2-order", "price": "3005", "size": "0.5"},
            ],
        }
        return fills[order_id]

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr("src.trading.bot_agent.place_market_order", fake_place_market_order)
    monkeypatch.setattr("src.trading.bot_agent.check_order_status", fake_check_order_status)
    monkeypatch.setattr("src.trading.bot_agent.get_order", fake_get_order)
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    calls = []
    agent = BotAgent(
        client=object(),
        market_1="BTC-USD",
        market_2="ETH-USD",
        base_side="BUY",
        base_size="0.1",
        base_price="101000",
        quote_side="SELL",
        quote_size="1",
        quote_price="2900",
        accept_failsafe_base_price="90000",
        z_score=2.0,
        half_life=10,
        hedge_ratio=0.5,
    )

    result = asyncio.run(agent.open_trades())

    assert result["pair_status"] == "LIVE"
    assert result["order_m1_price"] == "100000.0"
    assert result["order_m1_price_source"] == "fills"
    assert result["order_m1_fill_count"] == 2
    assert result["order_m2_price"] == "2998.3333333333335"
    assert result["order_m2_price_source"] == "fills"
    assert result["order_m1_size"] == "0.2"
    assert result["order_m2_size"] == "1.5"


def test_open_trades_treats_non_filled_emergency_close_as_success_when_position_closed(monkeypatch):
    """If emergency close status is non-FILLED but market position is already closed, do not raise."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    calls = []

    async def fake_place_market_order(
            client,
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
        if len(calls) == 1:
            return ({"ok": True}, "m1-order")
        if len(calls) == 2:
            raise RuntimeError("exchange rejected second leg")
        return ({"ok": True}, "m1-close-order")

    async def fake_check_order_status(client, order_id):
        if order_id == "m1-order":
            return "FILLED"
        return "OPEN"

    async def fake_is_open_positions(client, market):
        _ = client
        _ = market
        return False

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr("src.trading.bot_agent.place_market_order", fake_place_market_order)
    monkeypatch.setattr("src.trading.bot_agent.check_order_status", fake_check_order_status)
    monkeypatch.setattr("src.trading.bot_agent.is_open_positions", fake_is_open_positions)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    agent = BotAgent(
        client=object(),
        market_1="IMX-USD",
        market_2="ETH-USD",
        base_side="BUY",
        base_size="10",
        base_price="1.0",
        quote_side="SELL",
        quote_size="1",
        quote_price="3000",
        accept_failsafe_base_price="0.9",
        z_score=2.0,
        half_life=10,
        hedge_ratio=0.5,
    )

    result = asyncio.run(agent.open_trades())

    assert result["pair_status"] == "ERROR"
    assert result["comments"].startswith("Market 2 ETH-USD")
    assert calls[-1]["market"] == "IMX-USD"
    assert calls[-1]["reduce_only"] is True


def test_open_trades_emergency_failure_raises_json_telemetry(monkeypatch):
    """Emergency closure failures should include parseable telemetry in the raised error."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    calls = []

    async def fake_place_market_order(
            client,
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
        if len(calls) == 1:
            return ({"ok": True}, "m1-order")
        if len(calls) == 2:
            raise RuntimeError("exchange rejected second leg")
        raise RuntimeError("close order id lookup failed")

    async def fake_check_order_status(client, order_id):
        return "FILLED"

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr("src.trading.bot_agent.place_market_order", fake_place_market_order)
    monkeypatch.setattr("src.trading.bot_agent.check_order_status", fake_check_order_status)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    agent = BotAgent(
        client=object(),
        market_1="IMX-USD",
        market_2="MET-USD",
        base_side="BUY",
        base_size="60",
        base_price="0.166",
        quote_side="SELL",
        quote_size="64",
        quote_price="0.1541",
        accept_failsafe_base_price="0.1",
        z_score=-1.5,
        half_life=10,
        hedge_ratio=0.03,
    )

    try:
        asyncio.run(agent.open_trades())
        assert False, "Expected open_trades to raise RuntimeError"
    except RuntimeError as exc:
        text = str(exc)
        assert "Unexpected emergency closure error for IMX-USD" in text
        assert "telemetry={" in text
        assert '"cleanup_status":"failed"' in text
