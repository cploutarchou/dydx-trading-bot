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

    async def fake_get_order_fills(client, order_id, market=None):
        # No fills for the cancelled second leg -> clean "failed" outcome.
        return []

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)

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
        accept_failsafe_quote_price="5100",
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


def test_open_trades_emergency_closes_first_leg_when_second_leg_placement_raises(
    monkeypatch,
):
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
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )

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
        accept_failsafe_quote_price="5100",
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
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
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
        accept_failsafe_quote_price="5100",
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


def test_open_trades_treats_non_filled_emergency_close_as_success_when_position_closed(
    monkeypatch,
):
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
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.is_open_positions", fake_is_open_positions
    )
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
        accept_failsafe_quote_price="5100",
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
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
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
        accept_failsafe_quote_price="5100",
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


def test_check_order_status_treats_failed_as_failed(monkeypatch):
    """FAILED status should never be treated as live."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    statuses = ["FAILED"]

    async def fake_check_order_status(client, order_id):
        _ = client
        _ = order_id
        return statuses.pop(0)

    async def fake_get_order_fills(client, order_id, market=None):
        return []

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

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
        accept_failsafe_quote_price="5100",
        z_score=2.0,
        half_life=10,
        hedge_ratio=0.5,
    )

    result = asyncio.run(agent.check_order_status_by_id("order-1"))

    assert result == "failed"
    assert agent.order_dict["pair_status"] == "FAILED"


def test_check_order_status_treats_cancelled_variants_as_failed(monkeypatch):
    """Both canceled spellings and lowercase values should fail consistently."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    async def _fast_sleep(_seconds):
        return None

    for variant in (
        "CANCELED",
        "CANCELLED",
        "cancelled",
        "canceled",
        "BEST_EFFORT_CANCELED",
        "IB_CANCELED",
    ):
        statuses = [variant]

        async def fake_check_order_status(client, order_id):
            _ = client
            _ = order_id
            return statuses.pop(0)

        async def fake_get_order_fills(client, order_id, market=None):
            return []

        monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
        monkeypatch.setattr(
            "src.trading.bot_agent.check_order_status", fake_check_order_status
        )
        monkeypatch.setattr(
            "src.trading.bot_agent.get_order_fills", fake_get_order_fills
        )
        monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

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
            accept_failsafe_quote_price="5100",
            z_score=2.0,
            half_life=10,
            hedge_ratio=0.5,
        )

        result = asyncio.run(agent.check_order_status_by_id("order-1"))

        assert result == "failed"
        assert agent.order_dict["pair_status"] == "FAILED"


def test_check_order_status_cancels_non_filled_second_probe(monkeypatch):
    """Non-filled status after retry should cancel order and return error."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    statuses = ["open", "partially_filled"]
    cancelled = []

    async def fake_check_order_status(client, order_id):
        _ = client
        _ = order_id
        return statuses.pop(0)

    async def fake_cancel_order(client, order_id):
        _ = client
        cancelled.append(order_id)

    async def fake_cancel_order_verified(client, order_id, attempts=3):
        cancelled.append(order_id)
        return "CANCELED"

    async def fake_get_order_fills(client, order_id, market=None):
        return []

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr("src.trading.bot_agent.cancel_order", fake_cancel_order)
    monkeypatch.setattr(
        "src.trading.bot_agent.cancel_order_verified", fake_cancel_order_verified
    )
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

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
        accept_failsafe_quote_price="5100",
        z_score=2.0,
        half_life=10,
        hedge_ratio=0.5,
    )

    result = asyncio.run(agent.check_order_status_by_id("order-1"))

    assert result == "error"
    assert agent.order_dict["pair_status"] == "ERROR"
    assert cancelled == ["order-1"]


def _make_agent(**overrides):
    defaults = dict(
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
        accept_failsafe_quote_price="5100",
        z_score=2.0,
        half_life=10,
        hedge_ratio=0.5,
    )
    defaults.update(overrides)
    return BotAgent(**defaults)


def test_open_trades_cleans_up_when_first_leg_status_check_raises(monkeypatch):
    """A status-check exception after leg 1 filled must trigger cleanup, not escape."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    calls = []

    async def fake_place_market_order(client, market, side, size, price, reduce_only):
        calls.append({"market": market, "side": side, "reduce_only": reduce_only})
        return ({"ok": True}, f"order-{len(calls)}")

    async def fake_check_order_status(client, order_id):
        if order_id == "order-1":
            raise ConnectionError("indexer unreachable")
        return "FILLED"

    async def fake_get_order_fills(client, order_id, market=None):
        return []

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    agent = _make_agent()
    result = asyncio.run(agent.open_trades())

    assert result["pair_status"] == "ERROR"
    # Leg 2 was never placed; leg 1 was emergency-closed reduce-only.
    assert len(calls) == 2
    assert calls[-1]["market"] == "BTC-USD"
    assert calls[-1]["side"] == "SELL"
    assert calls[-1]["reduce_only"] is True
    assert result["order_id_m2"] == ""


def test_open_trades_closes_both_legs_when_second_leg_status_check_raises(monkeypatch):
    """Unknown leg-2 state after a filled leg 1 must flatten BOTH legs."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    calls = []

    async def fake_place_market_order(client, market, side, size, price, reduce_only):
        calls.append(
            {
                "market": market,
                "side": side,
                "price": price,
                "reduce_only": reduce_only,
            }
        )
        return ({"ok": True}, f"order-{len(calls)}")

    async def fake_check_order_status(client, order_id):
        if order_id == "order-2":
            raise ConnectionError("indexer unreachable")
        return "FILLED"

    async def fake_get_order_fills(client, order_id, market=None):
        return []

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    agent = _make_agent()
    result = asyncio.run(agent.open_trades())

    assert result["pair_status"] == "ERROR"
    # Both legs received reduce-only closes.
    closes = [c for c in calls if c["reduce_only"]]
    assert {c["market"] for c in closes} == {"BTC-USD", "ETH-USD"}
    # Each leg is closed with its own market's fail-safe price: a market-1
    # price on market 2 is off-scale and leaves the leg open.
    assert {c["market"]: c["price"] for c in closes} == {
        "BTC-USD": "90000",
        "ETH-USD": "5100",
    }


def test_open_trades_closes_residual_on_first_leg_partial_fill(monkeypatch):
    """BEST_EFFORT_CANCELED with fills means a live residual that must be closed."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    calls = []

    async def fake_place_market_order(client, market, side, size, price, reduce_only):
        calls.append({"market": market, "side": side, "reduce_only": reduce_only})
        return ({"ok": True}, f"order-{len(calls)}")

    async def fake_check_order_status(client, order_id):
        if order_id == "order-1":
            return "BEST_EFFORT_CANCELED"
        return "FILLED"

    async def fake_get_order_fills(client, order_id, market=None):
        if order_id == "order-1":
            return [{"orderId": "order-1", "price": "99900", "size": "0.04"}]
        return []

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    agent = _make_agent()
    result = asyncio.run(agent.open_trades())

    assert result["pair_status"] == "ERROR"
    assert len(calls) == 2
    assert calls[-1]["market"] == "BTC-USD"
    assert calls[-1]["reduce_only"] is True
    assert result["order_id_m2"] == ""


def test_open_trades_closes_both_legs_on_second_leg_partial_fill(monkeypatch):
    """A partially filled leg 2 must be closed along with the filled leg 1."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    calls = []

    async def fake_place_market_order(client, market, side, size, price, reduce_only):
        calls.append(
            {
                "market": market,
                "side": side,
                "price": price,
                "reduce_only": reduce_only,
            }
        )
        return ({"ok": True}, f"order-{len(calls)}")

    async def fake_check_order_status(client, order_id):
        if order_id == "order-2":
            return "BEST_EFFORT_CANCELED"
        return "FILLED"

    async def fake_get_order_fills(client, order_id, market=None):
        if order_id == "order-2":
            return [{"orderId": "order-2", "price": "2995", "size": "0.4"}]
        return []

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr(
        "src.trading.bot_agent.place_market_order", fake_place_market_order
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    agent = _make_agent()
    result = asyncio.run(agent.open_trades())

    assert result["pair_status"] == "ERROR"
    closes = [c for c in calls if c["reduce_only"]]
    assert {c["market"] for c in closes} == {"BTC-USD", "ETH-USD"}
    # Each leg is closed with its own market's fail-safe price: a market-1
    # price on market 2 is off-scale and leaves the leg open.
    assert {c["market"]: c["price"] for c in closes} == {
        "BTC-USD": "90000",
        "ETH-USD": "5100",
    }


def test_check_order_status_treats_unknown_fills_as_partial(monkeypatch):
    """If fills cannot be verified, a cancelled order must be treated as partially filled."""

    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    async def fake_check_order_status(client, order_id):
        return "CANCELED"

    async def fake_get_order_fills(client, order_id, market=None):
        raise ConnectionError("fills endpoint down")

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr("src.trading.bot_agent.get_order_fills", fake_get_order_fills)
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)

    agent = _make_agent()
    result = asyncio.run(agent.check_order_status_by_id("order-1"))

    assert result == "partial"
    assert agent.order_dict["pair_status"] == "PARTIAL"


# --- the emergency close loop must survive a failing attempt ------------------


def _wire_emergency_close(monkeypatch, *, place, status="FILLED", still_open=True):
    class DummyMessenger:
        def send_error_message(self, *args, **kwargs):
            return None

    async def fake_check_order_status(_client, _order_id):
        return status

    async def fake_is_open_positions(_client, _market):
        return still_open

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr("src.trading.bot_agent.TelegramMessenger", DummyMessenger)
    monkeypatch.setattr("src.trading.bot_agent.place_market_order", place)
    monkeypatch.setattr(
        "src.trading.bot_agent.check_order_status", fake_check_order_status
    )
    monkeypatch.setattr(
        "src.trading.bot_agent.is_open_positions", fake_is_open_positions
    )
    monkeypatch.setattr("src.trading.bot_agent.asyncio.sleep", _fast_sleep)


def test_emergency_close_retries_after_a_placement_exception(monkeypatch):
    attempts = []

    async def flaky_place(_client, market, side, size, price, reduce_only):
        attempts.append(market)
        if len(attempts) == 1:
            raise ConnectionError("node timeout")
        return ({"ok": True}, "close-2")

    _wire_emergency_close(monkeypatch, place=flaky_place)
    agent = _make_agent()

    order_id = asyncio.run(
        agent._emergency_close_leg(
            market="ETH-USD", side="SELL", size="1", price="5100"
        )
    )

    assert order_id == "close-2"
    assert attempts == ["ETH-USD", "ETH-USD"]


def test_emergency_close_raises_only_after_every_attempt_failed(monkeypatch):
    attempts = []

    async def always_failing_place(_client, market, side, size, price, reduce_only):
        attempts.append(market)
        raise ConnectionError("node timeout")

    _wire_emergency_close(monkeypatch, place=always_failing_place)
    agent = _make_agent()

    try:
        asyncio.run(
            agent._emergency_close_leg(
                market="ETH-USD", side="SELL", size="1", price="5100"
            )
        )
    except RuntimeError as exc:
        assert "ETH-USD" in str(exc)
    else:
        assert False, "an unclosed leg must raise"

    assert len(attempts) == 3


def test_emergency_close_escalates_when_no_close_order_could_be_placed(monkeypatch):
    """A flat reading is not trusted when nothing was ever sent (indexer lag)."""
    attempts = []

    async def failing_place(_client, market, side, size, price, reduce_only):
        attempts.append(market)
        raise ConnectionError("node timeout")

    _wire_emergency_close(monkeypatch, place=failing_place, still_open=False)
    agent = _make_agent()

    try:
        asyncio.run(
            agent._emergency_close_leg(
                market="ETH-USD", side="SELL", size="1", price="5100"
            )
        )
    except RuntimeError as exc:
        assert "ETH-USD" in str(exc)
    else:
        assert False, "no close order was placed; this must escalate"

    assert len(attempts) == 3


def test_emergency_close_accepts_flat_after_a_close_order_was_placed(monkeypatch):
    attempts = []

    async def place(_client, market, side, size, price, reduce_only):
        attempts.append(market)
        return ({"ok": True}, "close-1")

    _wire_emergency_close(monkeypatch, place=place, status="CANCELED", still_open=False)
    agent = _make_agent()

    order_id = asyncio.run(
        agent._emergency_close_leg(
            market="ETH-USD", side="SELL", size="1", price="5100"
        )
    )

    assert order_id == "close-1"
    assert len(attempts) == 1
