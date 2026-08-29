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


def test_cancel_all_orders_handles_nested_indexer_payload(monkeypatch):
    """The indexer returns {"orders": [...]}; iteration must see order dicts."""
    cancelled_ids = []

    class _FakeWallet:
        address = "0xTest"

    class _FakeClient:
        wallet = _FakeWallet()

    async def fake_get_orders(_client, *_args, **_kwargs):
        return {
            "orders": [
                {"id": "order-a", "ticker": "BTC-USD"},
                {"id": "order-b", "ticker": "ETH-USD"},
            ]
        }

    async def fake_cancel_order(_client, order_id):
        cancelled_ids.append(order_id)

    monkeypatch.setattr(
        account_manager, "_get_subaccount_orders_with_metrics", fake_get_orders
    )
    monkeypatch.setattr(account_manager, "cancel_order", fake_cancel_order)

    result = asyncio.run(account_manager.cancel_all_orders(_FakeClient()))

    assert sorted(cancelled_ids) == ["order-a", "order-b"]
    assert sorted(result) == ["order-a", "order-b"]


def test_cancel_all_orders_raises_after_partial_cancel_failure(monkeypatch):
    """A failed individual cancel must surface, not silently continue."""

    class _FakeWallet:
        address = "0xTest"

    class _FakeClient:
        wallet = _FakeWallet()

    async def fake_get_orders(_client, *_args, **_kwargs):
        return {
            "orders": [
                {"id": "order-a", "ticker": "BTC-USD"},
                {"id": "order-b", "ticker": "ETH-USD"},
            ]
        }

    async def fake_cancel_order(_client, order_id):
        if order_id == "order-b":
            raise RuntimeError("node rejected cancel")

    monkeypatch.setattr(
        account_manager, "_get_subaccount_orders_with_metrics", fake_get_orders
    )
    monkeypatch.setattr(account_manager, "cancel_order", fake_cancel_order)

    try:
        asyncio.run(account_manager.cancel_all_orders(_FakeClient()))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "order-b" in str(exc)


def test_abort_all_positions_flattens_even_when_cancel_all_fails(monkeypatch, tmp_path):
    """Emergency abort must still flatten positions if cancel-all errored."""
    bot_agents_path = tmp_path / "bot_agents.json"
    bot_agents_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)

    async def failing_cancel_all_orders(_client):
        raise RuntimeError("cancel-all degraded")

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
        close_orders.append({"market": market, "reduce_only": reduce_only})
        return {"id": "close-order"}, "close-order"

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(account_manager, "cancel_all_orders", failing_cancel_all_orders)
    monkeypatch.setattr(account_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(account_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(account_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(account_manager.asyncio, "sleep", fake_sleep)

    try:
        asyncio.run(account_manager.abort_all_positions(object()))
        assert False, "expected RuntimeError after best-effort cleanup"
    except RuntimeError as exc:
        assert "cancel-all degraded" in str(exc)

    # The position was still flattened and tracked state cleared.
    assert len(close_orders) == 1
    assert close_orders[0]["market"] == "BTC-USD"
    assert json.loads(bot_agents_path.read_text(encoding="utf-8")) == []


def test_abort_all_positions_isolates_single_position_close_failure(
    monkeypatch, tmp_path
):
    """One failed close must not skip the remaining position closes."""
    bot_agents_path = tmp_path / "bot_agents.json"
    bot_agents_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)

    async def fake_cancel_all_orders(_client):
        return []

    async def fake_get_markets(_client):
        return {
            "markets": {
                "BTC-USD": {"tickSize": "0.1"},
                "ETH-USD": {"tickSize": "0.01"},
            }
        }

    async def fake_get_open_positions(_client):
        return {
            "BTC-USD": {
                "market": "BTC-USD",
                "side": "LONG",
                "entryPrice": "100.0",
                "sumOpen": "0.25",
            },
            "ETH-USD": {
                "market": "ETH-USD",
                "side": "SHORT",
                "entryPrice": "2000.0",
                "sumOpen": "1.5",
            },
        }

    close_orders = []

    async def fake_place_market_order(_client, market, side, size, price, reduce_only):
        if market == "BTC-USD":
            raise RuntimeError("close rejected")
        close_orders.append({"market": market})
        return {"id": f"close-{market}"}, f"close-{market}"

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(account_manager, "cancel_all_orders", fake_cancel_all_orders)
    monkeypatch.setattr(account_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(account_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(account_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(account_manager.asyncio, "sleep", fake_sleep)

    try:
        asyncio.run(account_manager.abort_all_positions(object()))
        assert False, "expected RuntimeError after best-effort cleanup"
    except RuntimeError as exc:
        assert "BTC-USD" in str(exc)

    # The second position was still closed.
    assert close_orders == [{"market": "ETH-USD"}]
