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

    async def fake_cancel_all_orders(_client, markets=None):
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


def _fake_verified_cancel_setup(monkeypatch, cancelled_ids):
    """Mock check/cancel so cancel_order_verified sees OPEN then CANCELED."""

    class _FakeWallet:
        address = "0xTest"

    class _FakeClient:
        wallet = _FakeWallet()

    status_calls: dict[str, int] = {}

    async def fake_check_order_status(_client, order_id):
        status_calls[order_id] = status_calls.get(order_id, 0) + 1
        # First read per order: OPEN (drives the cancel); after: CANCELED.
        return "CANCELED" if status_calls[order_id] > 1 else "OPEN"

    async def fake_cancel_order(_client, order_id):
        cancelled_ids.append(order_id)

    monkeypatch.setattr(account_manager, "check_order_status", fake_check_order_status)
    monkeypatch.setattr(account_manager, "cancel_order", fake_cancel_order)
    return _FakeClient()


def test_cancel_all_orders_handles_nested_indexer_payload(monkeypatch):
    """The indexer returns {"orders": [...]}; iteration must see order dicts."""
    cancelled_ids = []
    fake_client = _fake_verified_cancel_setup(monkeypatch, cancelled_ids)

    async def fake_get_orders(_client, *_args, **_kwargs):
        return {
            "orders": [
                {"id": "order-a", "ticker": "BTC-USD"},
                {"id": "order-b", "ticker": "ETH-USD"},
            ]
        }

    monkeypatch.setattr(
        account_manager, "_get_subaccount_orders_with_metrics", fake_get_orders
    )

    result = asyncio.run(account_manager.cancel_all_orders(fake_client))

    assert sorted(cancelled_ids) == ["order-a", "order-b"]
    assert sorted(result) == ["order-a", "order-b"]


def test_cancel_all_orders_raises_after_partial_cancel_failure(monkeypatch):
    """A failed individual cancel must surface, not silently continue."""

    cancelled_ids: list[str] = []
    fake_client = _fake_verified_cancel_setup(monkeypatch, cancelled_ids)

    async def fake_get_orders(_client, *_args, **_kwargs):
        return {
            "orders": [
                {"id": "order-a", "ticker": "BTC-USD"},
                {"id": "order-b", "ticker": "ETH-USD"},
            ]
        }

    real_cancel = account_manager.cancel_order

    async def fake_cancel_order(client, order_id):
        if order_id == "order-b":
            raise RuntimeError("node rejected cancel")
        await real_cancel(client, order_id)

    monkeypatch.setattr(
        account_manager, "_get_subaccount_orders_with_metrics", fake_get_orders
    )
    monkeypatch.setattr(account_manager, "cancel_order", fake_cancel_order)

    try:
        asyncio.run(account_manager.cancel_all_orders(fake_client))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "order-b" in str(exc)


def test_abort_all_positions_flattens_even_when_cancel_all_fails(monkeypatch, tmp_path):
    """Emergency abort must still flatten positions if cancel-all errored."""
    bot_agents_path = tmp_path / "bot_agents.json"
    bot_agents_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)

    async def failing_cancel_all_orders(_client, markets=None):
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

    async def fake_cancel_all_orders(_client, markets=None):
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


def test_abort_all_positions_scoped_to_tracked_markets(monkeypatch, tmp_path):
    """Scoped abort: only the tracked markets are cancelled and closed."""
    bot_agents_path = tmp_path / "bot_agents.json"
    bot_agents_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)

    class _FakeWallet:
        address = "0xTest"

    class _FakeClient:
        wallet = _FakeWallet()

    async def fake_cancel_all(_client, markets=None):
        cancelled_scopes.append(sorted(markets or []))
        return []

    async def fake_get_markets(_client):
        return {
            "markets": {
                "BTC-USD": {"tickSize": "0.1"},
                "ETH-USD": {"tickSize": "0.01"},
                "OTHER-USD": {"tickSize": "0.001"},
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
            "OTHER-USD": {
                "market": "OTHER-USD",
                "side": "SHORT",
                "entryPrice": "5.0",
                "sumOpen": "10.0",
            },
        }

    closes = []

    async def fake_place_market_order(_client, market, side, size, price, reduce_only):
        closes.append(market)
        return {"id": f"close-{market}"}, f"close-{market}"

    async def fake_sleep(_seconds):
        return None

    cancelled_scopes = []
    monkeypatch.setattr(account_manager, "cancel_all_orders", fake_cancel_all)
    monkeypatch.setattr(account_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(account_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(account_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(account_manager.asyncio, "sleep", fake_sleep)

    result = asyncio.run(
        account_manager.abort_all_positions(_FakeClient(), markets=["BTC-USD"])
    )

    # Cancels were scoped to the tracked market.
    assert cancelled_scopes == [["BTC-USD"]]
    # Only the tracked market's position was closed; OTHER-USD untouched.
    assert closes == ["BTC-USD"]
    assert len(result) == 1


def _abort_harness(monkeypatch, tmp_path, *, positions=None, fetch_error=None):
    """Wire abort_all_positions to fakes; returns (tracked_path, calls)."""
    bot_agents_path = tmp_path / "bot_agents.json"
    bot_agents_path.write_text(
        json.dumps([{"market_1": "BTC-USD", "market_2": "ETH-USD"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", bot_agents_path)
    calls = {"cancel": [], "close": [], "fetch": 0}

    async def fake_cancel_all_orders(_client, markets=None):
        calls["cancel"].append(markets)
        return []

    async def fake_get_markets(_client):
        return {
            "markets": {
                "BTC-USD": {"tickSize": "0.1"},
                "ETH-USD": {"tickSize": "0.1"},
            }
        }

    async def fake_get_open_positions(_client):
        calls["fetch"] += 1
        if fetch_error is not None:
            raise fetch_error
        return positions or {}

    async def fake_place_market_order(_client, market, side, size, price, reduce_only):
        calls["close"].append(market)
        return {"id": f"close-{market}"}, f"close-{market}"

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(account_manager, "cancel_all_orders", fake_cancel_all_orders)
    monkeypatch.setattr(account_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(account_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(account_manager, "place_market_order", fake_place_market_order)
    monkeypatch.setattr(account_manager.asyncio, "sleep", fake_sleep)
    return bot_agents_path, calls


_OPEN_BTC = {
    "BTC-USD": {
        "market": "BTC-USD",
        "side": "LONG",
        "entryPrice": "100.0",
        "sumOpen": "0.25",
    }
}


def test_abort_with_empty_scope_touches_nothing(monkeypatch, tmp_path):
    """An instance tracking no markets must not fall back to the whole subaccount."""
    tracked_path, calls = _abort_harness(monkeypatch, tmp_path, positions=_OPEN_BTC)

    result = asyncio.run(account_manager.abort_all_positions(object(), markets=[]))

    assert result == []
    assert calls == {"cancel": [], "close": [], "fetch": 0}
    assert json.loads(tracked_path.read_text(encoding="utf-8")) != []


def test_abort_with_blank_only_scope_touches_nothing(monkeypatch, tmp_path):
    _, calls = _abort_harness(monkeypatch, tmp_path, positions=_OPEN_BTC)

    result = asyncio.run(
        account_manager.abort_all_positions(object(), markets=["", " "])
    )

    assert result == []
    assert calls["close"] == []


def test_abort_without_scope_keeps_whole_subaccount_semantics(monkeypatch, tmp_path):
    tracked_path, calls = _abort_harness(monkeypatch, tmp_path, positions=_OPEN_BTC)

    asyncio.run(account_manager.abort_all_positions(object()))

    assert calls["close"] == ["BTC-USD"]
    assert json.loads(tracked_path.read_text(encoding="utf-8")) == []


def test_cancel_all_orders_with_empty_scope_cancels_nothing(monkeypatch):
    async def fail_lookup(*_args, **_kwargs):
        raise AssertionError("order lookup must not run for an empty scope")

    monkeypatch.setattr(
        account_manager, "_get_subaccount_orders_with_metrics", fail_lookup
    )

    assert asyncio.run(account_manager.cancel_all_orders(object(), markets=[])) == []


def test_abort_fails_closed_when_position_fetch_fails(monkeypatch, tmp_path):
    tracked_path, calls = _abort_harness(
        monkeypatch, tmp_path, fetch_error=RuntimeError("indexer 503")
    )
    before = tracked_path.read_text(encoding="utf-8")

    try:
        asyncio.run(account_manager.abort_all_positions(object()))
    except RuntimeError as exc:
        assert "get_open_positions" in str(exc)
        assert "indexer 503" in str(exc)
    else:
        assert False, "a failed position fetch must not report a clean abort"

    assert calls["close"] == []
    assert tracked_path.read_text(encoding="utf-8") == before


def test_abort_keeps_tracked_state_when_a_close_fails(monkeypatch, tmp_path):
    tracked_path, _ = _abort_harness(monkeypatch, tmp_path, positions=_OPEN_BTC)
    before = tracked_path.read_text(encoding="utf-8")

    async def failing_place_market_order(*_args, **_kwargs):
        raise RuntimeError("sequence mismatch")

    monkeypatch.setattr(
        account_manager, "place_market_order", failing_place_market_order
    )

    try:
        asyncio.run(account_manager.abort_all_positions(object()))
    except RuntimeError as exc:
        assert "BTC-USD" in str(exc)
    else:
        assert False, "expected RuntimeError after a failed close"

    assert tracked_path.read_text(encoding="utf-8") == before
