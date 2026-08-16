"""Tests for account-level (portfolio) risk controls (``src/trading/portfolio_risk.py``).

The decision core is pure (same inputs → same decision); the wrapper is tested
with a fake client; and the ``position_manager.open_positions`` wiring is
verified at the seam (a denying guard must reject the entry with an audit
event and without constructing orders).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import src.trading.portfolio_risk as portfolio_risk
from src.trading.portfolio_risk import (
    PortfolioRiskLimits,
    PortfolioSnapshot,
    check_portfolio_entry_guard,
    evaluate_portfolio_entry,
)

_ALLOW_LIMITS = PortfolioRiskLimits(
    max_open_markets=20,
    max_margin_utilization_pct=60.0,
    min_free_collateral_usd=100.0,
    max_drawdown_pct=0.0,
)
_HEALTHY = PortfolioSnapshot(
    equity=10_000.0, free_collateral=9_000.0, open_market_count=4
)


# --------------------------------------------------------------------------- #
# Pure decision core
# --------------------------------------------------------------------------- #


def test_healthy_snapshot_allows_entry():
    decision = evaluate_portfolio_entry(
        _HEALTHY, _ALLOW_LIMITS, incremental_notional_usd=20.0
    )
    assert decision.allowed is True
    assert decision.reasons == ()
    assert decision.primary_reason == "allowed"
    # Determinism: same inputs, same decision.
    again = evaluate_portfolio_entry(
        _HEALTHY, _ALLOW_LIMITS, incremental_notional_usd=20.0
    )
    assert again == decision


def test_open_market_cap_at_limit_denies():
    snapshot = PortfolioSnapshot(
        equity=10_000.0, free_collateral=9_000.0, open_market_count=20
    )
    decision = evaluate_portfolio_entry(
        snapshot, _ALLOW_LIMITS, incremental_notional_usd=20.0
    )
    assert decision.allowed is False
    assert "portfolio_max_open_markets" in decision.reasons


def test_margin_utilization_at_limit_denies():
    # equity 1000, free 400 → 60% utilization (exactly at the cap → full).
    snapshot = PortfolioSnapshot(
        equity=1_000.0, free_collateral=400.0, open_market_count=1
    )
    decision = evaluate_portfolio_entry(
        snapshot, _ALLOW_LIMITS, incremental_notional_usd=20.0
    )
    assert decision.allowed is False
    assert "portfolio_margin_utilization" in decision.reasons


def test_free_collateral_floor_blocks_incremental_entry():
    # free 110, floor 100, new entry would consume 20 → projected 90 < 100.
    snapshot = PortfolioSnapshot(
        equity=1_000.0, free_collateral=110.0, open_market_count=1
    )
    decision = evaluate_portfolio_entry(
        snapshot, _ALLOW_LIMITS, incremental_notional_usd=20.0
    )
    assert decision.allowed is False
    assert "portfolio_free_collateral_floor" in decision.reasons


def test_missing_account_data_fails_closed():
    snapshot = PortfolioSnapshot(equity=None, free_collateral=None, open_market_count=2)
    decision = evaluate_portfolio_entry(
        snapshot, _ALLOW_LIMITS, incremental_notional_usd=20.0
    )
    assert decision.allowed is False
    assert "portfolio_data_unavailable" in decision.reasons


def test_non_positive_equity_fails_closed():
    snapshot = PortfolioSnapshot(equity=0.0, free_collateral=0.0, open_market_count=0)
    decision = evaluate_portfolio_entry(
        snapshot, _ALLOW_LIMITS, incremental_notional_usd=20.0
    )
    assert decision.allowed is False
    assert "portfolio_non_positive_equity" in decision.reasons


def test_zero_limits_disable_individual_checks():
    limits = PortfolioRiskLimits(
        max_open_markets=0,
        max_margin_utilization_pct=0.0,
        min_free_collateral_usd=0.0,
        max_drawdown_pct=0.0,
    )
    exhausted = PortfolioSnapshot(
        equity=1.0, free_collateral=0.0, open_market_count=999
    )
    decision = evaluate_portfolio_entry(
        exhausted, limits, incremental_notional_usd=1_000.0
    )
    assert decision.allowed is True


# --------------------------------------------------------------------------- #
# Wrapper (config + I/O seam)
# --------------------------------------------------------------------------- #


class _FakeClient:
    pass


def _patch_account(monkeypatch, *, equity, free_collateral, open_positions):
    async def _fake_get_account(client):
        return {"equity": equity, "freeCollateral": free_collateral}

    async def _fake_get_open_positions(client):
        return open_positions

    monkeypatch.setattr(portfolio_risk, "get_account", _fake_get_account)
    monkeypatch.setattr(portfolio_risk, "get_open_positions", _fake_get_open_positions)


def test_guard_disabled_short_circuits_without_exchange_reads(monkeypatch):
    async def _fail(_client):  # pragma: no cover - must not be called
        raise AssertionError("exchange must not be read while disabled")

    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", False)
    monkeypatch.setattr(portfolio_risk, "get_account", _fail)
    monkeypatch.setattr(portfolio_risk, "get_open_positions", _fail)

    decision = asyncio.run(
        check_portfolio_entry_guard(
            cast(Any, _FakeClient()), incremental_notional_usd=20.0
        )
    )
    assert decision.allowed is True
    assert decision.reasons == ("disabled",)


def test_guard_enabled_allows_healthy_account(monkeypatch):
    _patch_account(
        monkeypatch,
        equity="10000",
        free_collateral="9000",
        open_positions={"BTC-USD": {}, "ETH-USD": {}},
    )
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", True)

    decision = asyncio.run(
        check_portfolio_entry_guard(
            cast(Any, _FakeClient()), incremental_notional_usd=20.0
        )
    )
    assert decision.allowed is True
    assert decision.snapshot == PortfolioSnapshot(
        equity=10_000.0, free_collateral=9_000.0, open_market_count=2
    )


def test_guard_denies_overexposed_account(monkeypatch):
    _patch_account(
        monkeypatch,
        equity="1000",  # 75% utilized
        free_collateral="250",
        open_positions={f"MKT-{i}": {} for i in range(20)},
    )
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", True)

    decision = asyncio.run(
        check_portfolio_entry_guard(
            cast(Any, _FakeClient()), incremental_notional_usd=20.0
        )
    )
    assert decision.allowed is False
    assert "portfolio_max_open_markets" in decision.reasons
    assert "portfolio_margin_utilization" in decision.reasons


def test_guard_fails_closed_on_malformed_payload(monkeypatch):
    _patch_account(
        monkeypatch,
        equity="not-a-number",
        free_collateral=None,
        open_positions={},
    )
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", True)

    decision = asyncio.run(
        check_portfolio_entry_guard(
            cast(Any, _FakeClient()), incremental_notional_usd=20.0
        )
    )
    assert decision.allowed is False
    assert "portfolio_data_unavailable" in decision.reasons


def test_guard_propagates_transport_errors(monkeypatch):
    """Transport failures propagate like the neighboring collateral guards —
    the guard never silently trades blind."""

    async def _boom(_client):
        raise RuntimeError("indexer down")

    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", True)
    monkeypatch.setattr(portfolio_risk, "get_account", _boom)

    try:
        asyncio.run(
            check_portfolio_entry_guard(
                cast(Any, _FakeClient()), incremental_notional_usd=20.0
            )
        )
    except RuntimeError as exc:
        assert "indexer down" in str(exc)
    else:  # pragma: no cover - the assertion above must have raised
        raise AssertionError("transport error was swallowed")


# --------------------------------------------------------------------------- #
# position_manager wiring (seam-level)
# --------------------------------------------------------------------------- #


def test_open_positions_rejects_when_portfolio_guard_denies(monkeypatch):
    """A denying guard must record the rejection, persist the audit event, and
    stop the entry path without building any orders. Mirrors the harness from
    tests/test_position_manager_entry_backoff.py."""
    import pandas as pd

    import src.trading.position_manager as position_manager

    class _Pair:
        def __init__(self, payload):
            self._payload = payload

        def to_dict(self):
            return dict(self._payload)

    calls: dict[str, Any] = {}

    async def _denying_guard(client, *, incremental_notional_usd):
        calls["incremental"] = incremental_notional_usd
        return SimpleNamespace(
            allowed=False,
            reasons=("portfolio_max_open_markets",),
            primary_reason="portfolio_max_open_markets",
            snapshot=PortfolioSnapshot(
                equity=100.0, free_collateral=50.0, open_market_count=20
            ),
            limits=PortfolioRiskLimits(
                max_open_markets=20,
                max_margin_utilization_pct=60.0,
                min_free_collateral_usd=0.0,
                max_drawdown_pct=0.0,
            ),
            aggregate_totals=None,
        )

    rejections: list[str] = []
    events: list[tuple[str, Any]] = []

    monkeypatch.setattr(
        position_manager.pair_storage,
        "load_pairs",
        lambda: [
            _Pair(
                {
                    "base_market": "DOT-USD",
                    "quote_market": "CRO-USD",
                    "hedge_ratio": 0.03,
                    "half_life": 10,
                }
            )
        ],
    )

    async def _fake_get_markets(_client):
        return {
            "markets": {
                "DOT-USD": {"tickSize": "0.001", "stepSize": "1", "oraclePrice": "1.2"},
                "CRO-USD": {
                    "tickSize": "0.00001",
                    "stepSize": "1",
                    "oraclePrice": "0.07",
                },
            }
        }

    async def _fake_candles(_client, market):
        if market == "DOT-USD":
            return pd.Series([1.2, 1.21, 1.22])
        return pd.Series([0.07, 0.068, 0.067])

    def _fake_zscore(_spread):
        return pd.Series([2.0])

    async def _fake_is_open(_client, _market):
        return False

    async def _fake_get_account(_client):
        # Existing collateral guards must PASS so the denial provably comes
        # from the portfolio guard.
        return {"freeCollateral": "10000"}

    def _no_bot_agent(*_args, **_kwargs):
        raise AssertionError("no orders may be built after a portfolio denial")

    monkeypatch.setattr(position_manager, "get_markets", _fake_get_markets)
    monkeypatch.setattr(position_manager, "get_candles_recent", _fake_candles)
    monkeypatch.setattr(position_manager, "calculate_zscore", _fake_zscore)
    monkeypatch.setattr(position_manager, "is_open_positions", _fake_is_open)
    monkeypatch.setattr(position_manager, "get_account", _fake_get_account)
    monkeypatch.setattr(position_manager, "BotAgent", _no_bot_agent)
    monkeypatch.setattr(position_manager, "USD_PER_TRADE", 10.0)
    monkeypatch.setattr(position_manager, "check_portfolio_entry_guard", _denying_guard)
    monkeypatch.setattr(
        position_manager, "record_rejection", lambda reason: rejections.append(reason)
    )
    monkeypatch.setattr(
        position_manager,
        "persist_trade_activity_event",
        lambda event_type, message, severity="info", details=None: events.append(
            (event_type, details)
        ),
    )

    asyncio.run(position_manager.open_positions(cast(Any, _FakeClient())))

    assert calls["incremental"] == 20.0  # 2 × usd_per_trade (both legs)
    assert "portfolio_max_open_markets" in rejections
    assert events and events[0][0] == "trade_entry_rejected_portfolio_risk"
    assert events[0][1]["reasons"] == ["portfolio_max_open_markets"]
    assert events[0][1]["open_markets"] == 20
    assert events[0][1]["max_open_markets"] == 20


# --------------------------------------------------------------------------- #
# Account-wide drawdown (slice 3)
# --------------------------------------------------------------------------- #


def test_drawdown_at_cap_denies_entry():
    limits = PortfolioRiskLimits(
        max_open_markets=0,
        max_margin_utilization_pct=0.0,
        min_free_collateral_usd=0.0,
        max_drawdown_pct=20.0,
    )
    # peak 1000 → equity 800 = exactly 20% drawdown (at-limit = full).
    snapshot = PortfolioSnapshot(
        equity=800.0, free_collateral=800.0, open_market_count=0
    )
    decision = evaluate_portfolio_entry(
        snapshot, limits, incremental_notional_usd=1.0, peak_equity=1000.0
    )
    assert decision.allowed is False
    assert "portfolio_max_drawdown" in decision.reasons


def test_drawdown_below_peak_does_not_deny_and_new_high_ratchets():
    limits = PortfolioRiskLimits(
        max_open_markets=0,
        max_margin_utilization_pct=0.0,
        min_free_collateral_usd=0.0,
        max_drawdown_pct=20.0,
    )
    # equity above the stored peak → drawdown is negative → allowed.
    snapshot = PortfolioSnapshot(
        equity=1_200.0, free_collateral=1_200.0, open_market_count=0
    )
    decision = evaluate_portfolio_entry(
        snapshot, limits, incremental_notional_usd=1.0, peak_equity=1_000.0
    )
    assert decision.allowed is True


def test_missing_peak_skips_drawdown_check():
    """Redis unavailable → peak None → the drawdown check skips itself (the
    exchange-read controls still fail closed independently)."""
    limits = PortfolioRiskLimits(
        max_open_markets=0,
        max_margin_utilization_pct=0.0,
        min_free_collateral_usd=0.0,
        max_drawdown_pct=1.0,
    )
    snapshot = PortfolioSnapshot(equity=1.0, free_collateral=1.0, open_market_count=0)
    decision = evaluate_portfolio_entry(
        snapshot, limits, incremental_notional_usd=1.0, peak_equity=None
    )
    assert decision.allowed is True


class _FakePeakRedis:
    """In-memory stand-in for the async Redis client (get/set only)."""

    def __init__(self, *, values=None, fail=False):
        self.values = dict(values or {})
        self.fail = fail
        self.set_calls: list[tuple[str, str]] = []

    async def get(self, key):
        if self.fail:
            raise OSError("redis down")
        return self.values.get(key)

    async def set(self, key, value):
        if self.fail:
            raise OSError("redis down")
        self.set_calls.append((key, value))
        self.values[key] = value


def test_peak_store_ratchets_up_only():
    from src.trading.portfolio_risk import RedisPeakEquityStore

    fake = _FakePeakRedis(values={"bot:portfolio:peak_equity:addr-1": "1000.0"})
    store = RedisPeakEquityStore(url="redis://localhost:6379/0", client=fake)

    lower = asyncio.run(store.observe("addr-1", 900.0))
    assert lower == 1000.0  # peak does not fall
    assert fake.set_calls == []  # …and nothing is rewritten

    higher = asyncio.run(store.observe("addr-1", 1_100.0))
    assert higher == 1_100.0
    assert fake.set_calls == [("bot:portfolio:peak_equity:addr-1", "1100.0")]

    first = asyncio.run(store.observe("addr-2", 500.0))  # fresh address
    assert first == 500.0


def test_peak_store_never_raises():
    from src.trading.portfolio_risk import RedisPeakEquityStore

    store = RedisPeakEquityStore(
        url="redis://localhost:6379/0", client=_FakePeakRedis(fail=True)
    )
    assert asyncio.run(store.observe("addr-1", 100.0)) is None


def test_guard_observes_peak_and_denies_on_drawdown(monkeypatch):
    """The wrapper folds the live equity into the peak store (keyed by the
    resolved wallet address) and denies when the drawdown cap is exceeded."""
    _patch_account(
        monkeypatch,
        equity="800",
        free_collateral="780",
        open_positions={},
    )
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", True)
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_MAX_DRAWDOWN_PCT", 20.0)

    observed: list[tuple[str, float]] = []

    class _PeakStore:
        async def observe(self, address, equity):
            observed.append((address, equity))
            return 1_000.0  # → 20% drawdown

    monkeypatch.setattr(portfolio_risk, "get_peak_equity_store", lambda: _PeakStore())
    monkeypatch.setattr(
        portfolio_risk, "resolve_client_address_or_none", lambda _client: "addr-9"
    )

    decision = asyncio.run(
        check_portfolio_entry_guard(
            cast(Any, _FakeClient()), incremental_notional_usd=20.0
        )
    )
    assert observed == [("addr-9", 800.0)]
    assert decision.allowed is False
    assert "portfolio_max_drawdown" in decision.reasons


# --------------------------------------------------------------------------- #
# Multi-account aggregation (deployment-wide entry caps)
# --------------------------------------------------------------------------- #

from src.trading.portfolio_accounts import (  # noqa: E402
    AccountExposure,
    PortfolioAccountRef,
)
from src.trading.portfolio_risk import evaluate_aggregate_entry  # noqa: E402


def _agg_exposure(
    address: str,
    *,
    equity: float | None,
    free: float | None,
    open_markets: int,
    complete: bool = True,
) -> AccountExposure:
    return AccountExposure(
        address=address,
        network="testnet",
        equity=equity,
        free_collateral=free,
        open_market_count=open_markets,
        complete=complete,
    )


_AGG_LIMITS = PortfolioRiskLimits(
    max_open_markets=0,
    max_margin_utilization_pct=0.0,
    min_free_collateral_usd=0.0,
    max_drawdown_pct=0.0,
    aggregate_max_open_markets=10,
    aggregate_max_margin_utilization_pct=50.0,
)


def test_aggregate_open_market_cap_at_limit_denies():
    exposures = (
        _agg_exposure("0x1", equity=1000.0, free=900.0, open_markets=4),
        _agg_exposure("0x2", equity=500.0, free=100.0, open_markets=6),
    )
    decision = evaluate_aggregate_entry(exposures, _AGG_LIMITS)
    assert decision.allowed is False
    assert decision.reasons == ("portfolio_aggregate_max_open_markets",)
    assert decision.totals.total_open_markets == 10
    assert decision.totals.accounts == 2
    # Determinism: same inputs, same decision.
    assert evaluate_aggregate_entry(exposures, _AGG_LIMITS) == decision


def test_aggregate_margin_utilization_at_limit_denies():
    # Combined: equity 2000, free 1000 -> exactly 50% utilization (at-cap = full).
    exposures = (
        _agg_exposure("0x1", equity=1500.0, free=900.0, open_markets=1),
        _agg_exposure("0x2", equity=500.0, free=100.0, open_markets=1),
    )
    decision = evaluate_aggregate_entry(exposures, _AGG_LIMITS)
    assert decision.allowed is False
    assert "portfolio_aggregate_margin_utilization" in decision.reasons


def test_aggregate_checks_disabled_when_limits_are_zero():
    limits = PortfolioRiskLimits(
        max_open_markets=0,
        max_margin_utilization_pct=0.0,
        min_free_collateral_usd=0.0,
        max_drawdown_pct=0.0,
    )
    overloaded = (
        _agg_exposure("0x1", equity=1.0, free=0.0, open_markets=999),
        _agg_exposure("0x2", equity=None, free=None, open_markets=999, complete=False),
    )
    decision = evaluate_aggregate_entry(overloaded, limits)
    assert decision.allowed is True
    assert decision.reasons == ()


def test_aggregate_incomplete_accounts_excluded_from_sums_but_counted():
    exposures = (
        _agg_exposure("0x1", equity=1000.0, free=600.0, open_markets=2),
        _agg_exposure("0x2", equity=None, free=None, open_markets=3, complete=False),
    )
    decision = evaluate_aggregate_entry(exposures, _AGG_LIMITS)
    # Only complete equity counts: (1000-600)/1000 = 40% < 50% -> utilization OK.
    assert decision.totals.incomplete_accounts == 1
    assert decision.totals.total_equity == 1000.0
    # Open markets still count the incomplete account's readable positions: 5.
    assert decision.totals.total_open_markets == 5
    assert decision.allowed is True


def test_aggregate_zero_total_equity_skips_utilization_check():
    exposures = (
        _agg_exposure("0x1", equity=None, free=None, open_markets=0, complete=False),
    )
    decision = evaluate_aggregate_entry(exposures, _AGG_LIMITS)
    assert (
        decision.allowed is True
    )  # nothing computable; per-account guard still fails closed


def _patch_aggregate_seams(
    monkeypatch,
    *,
    refs,
    foreign_exposures,
    own_address="0xown",
):
    async def _fake_enumerate(**kwargs):
        return refs

    async def _fake_load(client, foreign_refs):
        _fake_load.calls.append(foreign_refs)
        return foreign_exposures

    _fake_load.calls = []
    monkeypatch.setattr(portfolio_risk, "enumerate_portfolio_accounts", _fake_enumerate)
    monkeypatch.setattr(portfolio_risk, "load_account_exposures_via_client", _fake_load)
    monkeypatch.setattr(
        portfolio_risk, "resolve_client_address_or_none", lambda _client: own_address
    )
    monkeypatch.setattr(portfolio_risk, "MARKET_DATA_MODE", "TESTNET")
    return _fake_load


def test_guard_skips_aggregation_when_limits_off(monkeypatch):
    """Default-off contract: no enumeration and no foreign exchange reads."""
    _patch_account(
        monkeypatch,
        equity="10000",
        free_collateral="9000",
        open_positions={},
    )
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", True)

    async def _fail(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError("enumeration must not run with aggregate limits off")

    monkeypatch.setattr(portfolio_risk, "enumerate_portfolio_accounts", _fail)

    decision = asyncio.run(
        check_portfolio_entry_guard(
            cast(Any, _FakeClient()), incremental_notional_usd=20.0
        )
    )
    assert decision.allowed is True
    assert decision.aggregate_totals is None


def test_guard_denies_on_aggregate_open_markets(monkeypatch):
    """Own account is healthy; the deployment-wide total is over the cap."""
    _patch_account(
        monkeypatch,
        equity="10000",
        free_collateral="9000",
        open_positions={"BTC-USD": {}},
    )
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", True)
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_MAX_OPEN_MARKETS", 20)
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS", 3)
    loader = _patch_aggregate_seams(
        monkeypatch,
        refs=(
            PortfolioAccountRef("0xown", "testnet"),
            PortfolioAccountRef("0xother", "testnet"),
            PortfolioAccountRef("0xmain", "mainnet"),  # different network: ignored
        ),
        foreign_exposures=(
            _agg_exposure("0xother", equity=500.0, free=250.0, open_markets=3),
        ),
    )

    decision = asyncio.run(
        check_portfolio_entry_guard(
            cast(Any, _FakeClient()), incremental_notional_usd=20.0
        )
    )
    # Only the same-network foreign account is read.
    assert [ref.address for ref in loader.calls[0]] == ["0xother"]
    assert decision.allowed is False
    assert "portfolio_aggregate_max_open_markets" in decision.reasons
    assert decision.aggregate_totals is not None
    assert decision.aggregate_totals.total_open_markets == 4  # 1 own + 3 foreign
    assert decision.aggregate_totals.accounts == 2
    # Snapshot (own account) is still attached for the audit trail.
    assert decision.snapshot is not None
    assert decision.snapshot.equity == 10_000.0


def test_guard_aggregate_transport_errors_propagate(monkeypatch):
    _patch_account(
        monkeypatch,
        equity="10000",
        free_collateral="9000",
        open_positions={},
    )
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", True)
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS", 50)

    async def _failing_load(client, foreign_refs):
        raise RuntimeError("foreign indexer read failed")

    async def _fake_enumerate(**kwargs):
        return (PortfolioAccountRef("0xother", "testnet"),)

    monkeypatch.setattr(portfolio_risk, "enumerate_portfolio_accounts", _fake_enumerate)
    monkeypatch.setattr(
        portfolio_risk, "load_account_exposures_via_client", _failing_load
    )
    monkeypatch.setattr(
        portfolio_risk, "resolve_client_address_or_none", lambda _client: "0xown"
    )
    monkeypatch.setattr(portfolio_risk, "MARKET_DATA_MODE", "TESTNET")

    try:
        asyncio.run(
            check_portfolio_entry_guard(
                cast(Any, _FakeClient()), incremental_notional_usd=20.0
            )
        )
    except RuntimeError as exc:
        assert "foreign indexer read failed" in str(exc)
    else:  # pragma: no cover - the assertion above must have raised
        raise AssertionError("aggregate transport error was swallowed")
