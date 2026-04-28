"""Regression tests for emergency abort tracked-state cleanup."""

import asyncio
import json

from src.trading import account_manager, bot_agents_state


def test_abort_all_positions_clears_tracked_state_atomically(monkeypatch, tmp_path):
    bot_agents_path = tmp_path / "bot_agents.json"
    bot_agents_path.write_text(
        json.dumps(
            [
                {
                    "market_1": "BTC-USD",
                    "market_2": "ETH-USD",
                    "order_id_m1": "m1-entry",
                    "order_id_m2": "m2-entry",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)

    async def fake_cancel_all_orders(_client):
        return []

    async def fake_get_markets(_client):
        return {"markets": {"BTC-USD": {"tickSize": "0.1"}}}

    async def fake_get_open_positions(_client):
        return {
            "BTC-USD": {
                "market": "BTC-USD",
                "side": "LONG",
                "entryPrice": "100.0",
                "sumOpen": "0.25",
            }
        }

    close_orders = []

    async def fake_place_market_order(_client, market, side, size, price, reduce_only):
        close_orders.append(
            {
                "market": market,
                "side": side,
                "size": size,
                "price": price,
                "reduce_only": reduce_only,
            }
        )
        return {"id": "close-order"}, "close-order"

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(account_manager, "cancel_all_orders", fake_cancel_all_orders)
    monkeypatch.setattr(account_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(account_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(account_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(account_manager.asyncio, "sleep", fake_sleep)

    result = asyncio.run(account_manager.abort_all_positions(object()))

    assert result == [{"id": "close-order"}]
    assert close_orders == [
        {
            "market": "BTC-USD",
            "side": "SELL",
            "size": "0.25",
            "price": "30.0",
            "reduce_only": True,
        }
    ]
    assert json.loads(bot_agents_path.read_text(encoding="utf-8")) == []
