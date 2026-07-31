"""Hardening tests pinning the exit-confirmation contract.

These complement ``test_position_manager_exit_safety.py`` (which exercises the
full ``manage_trade_exits`` flow) by locking the lower-level
``_confirm_exchange_flat_after_close`` invariants directly, so a future change
cannot silently weaken closure safety:

  * Exchange-flat state (``get_open_positions``) is the authoritative close
    signal. Fill data never overrides a still-open position.
  * ``get_order_fills`` is telemetry-only and is collected solely after the
    polling budget is exhausted (never on early flat confirmation).
  * A ``get_order_fills`` failure is swallowed and never crashes the
    confirmation path or blocks the timeout summary.

No production code is changed by this file; it only pins existing behavior.
"""

import asyncio

from src.trading import position_manager


def _position() -> dict:
    return {
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "order_m1_size": "0.1",
        "order_m2_size": "1.0",
    }


_CLOSE_ORDER_IDS = {"market_1": "close-m1", "market_2": "close-m2"}


def _install_confirm_runtime(
    monkeypatch,
    *,
    open_positions,
    fills=None,
    fill_error=None,
):
    """Stub the exchange calls used by ``_confirm_exchange_flat_after_close``."""
    open_iter = list(open_positions)
    idx = {"i": 0}

    async def fake_get_open_positions(_client):
        i = min(idx["i"], len(open_iter) - 1)
        idx["i"] += 1
        return open_iter[i]

    fills_calls: list = []
    fills_map = dict(fills or {})

    async def fake_get_order_fills(_client, order_id, market=None):
        fills_calls.append((order_id, market))
        if fill_error is not None:
            raise fill_error
        return fills_map.get(order_id, [])

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(position_manager, "get_open_positions", fake_get_open_positions)
    monkeypatch.setattr(position_manager, "get_order_fills", fake_get_order_fills)
    monkeypatch.setattr(position_manager.asyncio, "sleep", fake_sleep)
    monkeypatch.setenv("BOT_EXIT_CONFIRM_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("BOT_EXIT_CONFIRM_DELAY_SECONDS", "0.01")
    return fills_calls


def test_flat_confirmed_short_circuits_without_fetching_fills(monkeypatch):
    """Early flat confirmation must not trigger any ``get_order_fills`` calls."""
    fills_calls = _install_confirm_runtime(
        monkeypatch,
        open_positions=[{}, {}],  # flat from the first poll
        fills={"close-m1": ["f1"], "close-m2": ["f2"]},
    )

    state = asyncio.run(
        position_manager._confirm_exchange_flat_after_close(
            object(),
            position=_position(),
            close_order_ids=_CLOSE_ORDER_IDS,
        )
    )

    assert state["flat_confirmed"] is True
    assert state["pair_status"] == "CLOSE_CONFIRMED"
    assert fills_calls == []  # telemetry branch never reached


def test_open_position_blocks_confirmation_even_with_fill_data(monkeypatch):
    """Exchange-flat is authoritative: fills must not override still-open exposure."""
    open_both = {
        "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
        "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
    }
    _install_confirm_runtime(
        monkeypatch,
        open_positions=[open_both, open_both, open_both],  # never flat
        fills={"close-m1": ["f1", "f2"], "close-m2": ["f3"]},  # fills present
    )

    state = asyncio.run(
        position_manager._confirm_exchange_flat_after_close(
            object(),
            position=_position(),
            close_order_ids=_CLOSE_ORDER_IDS,
        )
    )

    assert state["flat_confirmed"] is False
    assert state["timed_out"] is True
    # Fills were collected for telemetry but did NOT flip the verdict.
    assert state["fill_counts"] == {"market_1": 2, "market_2": 1}


def test_get_order_fills_failure_does_not_break_confirmation_summary(monkeypatch):
    """A fill-fetch failure must be swallowed; the timeout summary still returns."""
    open_both = {
        "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
        "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
    }
    _install_confirm_runtime(
        monkeypatch,
        open_positions=[open_both, open_both, open_both],
        fill_error=RuntimeError("indexer unavailable"),
    )

    state = asyncio.run(
        position_manager._confirm_exchange_flat_after_close(
            object(),
            position=_position(),
            close_order_ids=_CLOSE_ORDER_IDS,
        )
    )

    assert state["flat_confirmed"] is False
    assert state["timed_out"] is True
    # Both fill lookups raised, so no counts were recorded.
    assert state["fill_counts"] == {}


def test_partial_fill_is_not_treated_as_confirmed(monkeypatch):
    """A partially-closed leg must not be reported as flat-confirmed."""
    full = {
        "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.1"},
        "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
    }
    partial = {
        "BTC-USD": {"market": "BTC-USD", "side": "LONG", "sumOpen": "0.04"},
        "ETH-USD": {"market": "ETH-USD", "side": "SHORT", "sumOpen": "1.0"},
    }
    _install_confirm_runtime(
        monkeypatch,
        open_positions=[full, partial, partial],
    )

    state = asyncio.run(
        position_manager._confirm_exchange_flat_after_close(
            object(),
            position=_position(),
            close_order_ids=_CLOSE_ORDER_IDS,
        )
    )

    assert state["flat_confirmed"] is False
    assert state["pair_status"] == "PARTIALLY_CLOSED"
