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
    assert calls[-1]["reduce_only"] is True
