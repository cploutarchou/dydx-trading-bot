"""Entry-path tests for the cost + funding gate in position_manager.open_positions."""

import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest

from src.trading import arbitrage_runtime_config, position_manager
from src.trading.arbitrage_observability import reset_metrics, snapshot_metrics

GATE_REASONS = {"cost_inputs_invalid", "funding_same_side", "edge_lt_cost"}


class _Pair:
    def __init__(self, payload):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


def _pair(base, quote):
    return _Pair(
        {
            "base_market": base,
            "quote_market": quote,
            "hedge_ratio": 1.0,
            "half_life": 10,
        }
    )


def _market(price, funding_rate=None):
    market = {"tickSize": "0.001", "stepSize": "0.01", "oraclePrice": str(price)}
    if funding_rate is not None:
        market["nextFundingRate"] = funding_rate
    return market


class _Recorder:
    """Stands in for BotAgent and place_market_order: records, never trades."""

    def __init__(self):
        self.agents = []
        self.market_orders = 0

    def agent_class(self):
        recorder = self

        class _Agent:
            def __init__(self, *_args, **kwargs):
                recorder.agents.append((kwargs["market_1"], kwargs["market_2"]))

            async def open_trades(self):
                # Reaching execution is all these tests need; the failure is
                # handled by the entry backoff like any execution error.
                raise RuntimeError("test agent: execution reached")

        return _Agent

    async def place_market_order(self, *_args, **_kwargs):
        self.market_orders += 1
        raise AssertionError("no order may be placed in these tests")


@pytest.fixture
def entry_env(monkeypatch):
    """Minimal open_positions harness: z = +2 on every pair, sigma controlled."""
    position_manager._ENTRY_FAILURE_STATE.clear()
    reset_metrics()
    recorder = _Recorder()
    state = {
        "pairs": [_pair("AAA-USD", "BBB-USD")],
        "markets": {
            "AAA-USD": _market(50.0, "0"),
            "BBB-USD": _market(50.0, "0"),
        },
        "open_markets": set(),
        "spread_std": 0.5,
    }

    async def fake_get_markets(_client):
        return {"markets": state["markets"]}

    async def fake_get_candles_recent(_client, market):
        price = float(state["markets"][market]["oraclePrice"])
        return pd.Series([price, price, price])

    async def fake_is_open_positions(_client, market):
        return market in state["open_markets"]

    async def fake_get_account(_client):
        return {"freeCollateral": "10000"}

    async def allow_portfolio(*_args, **_kwargs):
        return SimpleNamespace(allowed=True, reasons=(), snapshot=None)

    monkeypatch.setattr(
        position_manager.pair_storage, "load_pairs", lambda: list(state["pairs"])
    )
    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(
        position_manager, "calculate_zscore", lambda _spread: pd.Series([2.0])
    )
    monkeypatch.setattr(
        position_manager, "calculate_spread_std", lambda _spread: state["spread_std"]
    )
    monkeypatch.setattr(position_manager, "is_open_positions", fake_is_open_positions)
    monkeypatch.setattr(position_manager, "get_account", fake_get_account)
    monkeypatch.setattr(
        position_manager, "check_portfolio_entry_guard", allow_portfolio
    )
    monkeypatch.setattr(position_manager, "BotAgent", recorder.agent_class())
    monkeypatch.setattr(
        position_manager, "place_market_order", recorder.place_market_order
    )
    monkeypatch.setattr(position_manager, "CLOSE_AT_ZSCORE_CROSS", True)
    monkeypatch.setattr(position_manager, "POSITION_TIMEOUT_HOURS", 72)
    state["recorder"] = recorder
    yield state
    position_manager._ENTRY_FAILURE_STATE.clear()
    reset_metrics()


def _enable_gate(monkeypatch, **settings):
    values = {
        "COST_GATE_ENABLED": True,
        "COST_GATE_EDGE_MULTIPLE": 2.5,
        "COST_GATE_TAKER_FEE": 0.0005,
        "COST_GATE_SLIPPAGE_BPS": 5.0,
        "FUNDING_SAME_SIDE_THRESHOLD": 0.00001,
    }
    values.update(settings)
    for key, value in values.items():
        monkeypatch.setitem(arbitrage_runtime_config._overrides, key, value)


def _gate_rejections():
    reasons = snapshot_metrics()["rejection_reasons"]
    return {
        reason: count for reason, count in reasons.items() if reason in GATE_REASONS
    }


def _run():
    asyncio.run(position_manager.open_positions(object()))


def test_gate_off_is_a_no_op(entry_env, monkeypatch):
    # No funding rate anywhere: with the gate off that must not matter, and
    # the gate must not even compute sigma.
    entry_env["markets"] = {"AAA-USD": _market(50.0), "BBB-USD": _market(50.0)}

    def _must_not_run(_spread):
        raise AssertionError("cost gate computed while disabled")

    monkeypatch.setattr(position_manager, "calculate_spread_std", _must_not_run)

    _run()

    assert entry_env["recorder"].agents == [("AAA-USD", "BBB-USD")]
    assert _gate_rejections() == {}


def test_gate_on_accepts_a_covered_edge_and_reaches_execution(entry_env, monkeypatch):
    _enable_gate(monkeypatch)

    _run()

    assert entry_env["recorder"].agents == [("AAA-USD", "BBB-USD")]
    assert _gate_rejections() == {}


def test_gate_on_rejects_edge_lt_cost_without_any_order_call(entry_env, monkeypatch):
    _enable_gate(monkeypatch)
    entry_env["spread_std"] = 1e-6

    async def _must_not_load():
        raise AssertionError("position cap consulted after a gate rejection")

    monkeypatch.setattr(position_manager, "load_tracked_positions", _must_not_load)

    _run()

    assert entry_env["recorder"].agents == []
    assert entry_env["recorder"].market_orders == 0
    assert _gate_rejections() == {"edge_lt_cost": 1.0}
    assert snapshot_metrics()["counters"]["opportunities_rejected_total"] == 1.0


def test_missing_next_funding_rate_rejects_cost_inputs_invalid(entry_env, monkeypatch):
    _enable_gate(monkeypatch)
    entry_env["markets"]["BBB-USD"] = _market(50.0)  # no nextFundingRate

    _run()

    assert entry_env["recorder"].agents == []
    assert _gate_rejections() == {"cost_inputs_invalid": 1.0}


def test_unparseable_next_funding_rate_rejects_cost_inputs_invalid(
    entry_env, monkeypatch
):
    _enable_gate(monkeypatch)
    entry_env["markets"]["AAA-USD"] = _market(50.0, "n/a")

    _run()

    assert entry_env["recorder"].agents == []
    assert _gate_rejections() == {"cost_inputs_invalid": 1.0}


def test_both_legs_paying_funding_rejects_funding_same_side(entry_env, monkeypatch):
    _enable_gate(monkeypatch)
    # z > 0 sells market 1 and buys market 2: the long leg (BBB) pays at a
    # positive rate and the short leg (AAA) pays at a negative rate.
    entry_env["markets"]["AAA-USD"] = _market(50.0, "-0.0001")
    entry_env["markets"]["BBB-USD"] = _market(50.0, "0.0001")

    _run()

    assert entry_env["recorder"].agents == []
    assert _gate_rejections() == {"funding_same_side": 1.0}


def test_zscore_exit_disabled_fails_closed(entry_env, monkeypatch):
    _enable_gate(monkeypatch)
    monkeypatch.setattr(position_manager, "CLOSE_AT_ZSCORE_CROSS", False)

    _run()

    assert entry_env["recorder"].agents == []
    assert _gate_rejections() == {"cost_inputs_invalid": 1.0}


def test_already_open_pairs_are_not_counted_by_the_gate(entry_env, monkeypatch):
    _enable_gate(monkeypatch)
    entry_env["open_markets"] = {"AAA-USD"}

    def _must_not_run(**_kwargs):
        raise AssertionError("gate evaluated for a pair that is already open")

    monkeypatch.setattr(position_manager, "_live_entry_cost_decision", _must_not_run)

    _run()

    assert entry_env["recorder"].agents == []
    assert _gate_rejections() == {}
    assert snapshot_metrics()["rejection_reasons"] == {"market_already_open": 1.0}


def test_a_rejected_pair_does_not_stop_the_scan(entry_env, monkeypatch):
    _enable_gate(monkeypatch)
    entry_env["pairs"] = [_pair("AAA-USD", "BBB-USD"), _pair("CCC-USD", "DDD-USD")]
    entry_env["markets"]["AAA-USD"] = _market(50.0)  # rejected: no funding rate
    entry_env["markets"]["CCC-USD"] = _market(50.0, "0")
    entry_env["markets"]["DDD-USD"] = _market(50.0, "0")

    _run()

    assert entry_env["recorder"].agents == [("CCC-USD", "DDD-USD")]
    assert _gate_rejections() == {"cost_inputs_invalid": 1.0}


def test_settings_are_read_once_per_cycle(entry_env, monkeypatch):
    _enable_gate(monkeypatch)
    entry_env["pairs"] = [_pair("AAA-USD", "BBB-USD"), _pair("CCC-USD", "DDD-USD")]
    entry_env["markets"]["CCC-USD"] = _market(50.0, "0")
    entry_env["markets"]["DDD-USD"] = _market(50.0, "0")
    calls = {"count": 0}
    real = position_manager.get_runtime_settings

    def _counting():
        calls["count"] += 1
        return real()

    monkeypatch.setattr(position_manager, "get_runtime_settings", _counting)

    _run()

    assert calls["count"] == 1
    assert len(entry_env["recorder"].agents) == 2
