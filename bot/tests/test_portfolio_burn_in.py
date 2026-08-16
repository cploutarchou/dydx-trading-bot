"""Tests for the Phase B burn-in harness (``scripts/portfolio_risk_burn_in.py``).

The harness drives the guard's PURE decision core against live public
subaccount reads; here everything external is injected (loader, peak store),
so the suite pins the pass/fail semantics that make the burn-in meaningful:

* healthy accounts → PASS (no false denials),
* data-path problems (incomplete reads, cycle exceptions) → FAIL,
* genuine limit denials (per-account AND aggregate) → reported, still PASS,
* evidence JSON round-trips what an operator needs to audit the flip.

The script module is imported via importlib (scripts/ is not a package) and
must stay import-safe: module import performs no repo-env loading (that
happens inside ``main()``, per AGENTS.md rule 1).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.trading.portfolio_accounts import AccountExposure, PortfolioAccountRef
from src.trading.portfolio_risk import PortfolioRiskLimits

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "portfolio_risk_burn_in.py"
)
_spec = importlib.util.spec_from_file_location("portfolio_risk_burn_in", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
burn_in = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(burn_in)


_DEFAULT_LIMITS = PortfolioRiskLimits(
    max_open_markets=20,
    max_margin_utilization_pct=60.0,
    min_free_collateral_usd=0.0,
    max_drawdown_pct=0.0,
)


class _FakePeakStore:
    def __init__(self) -> None:
        self.observed: list[tuple[str, float]] = []
        self.daily_observed: list[tuple[str, float]] = []

    async def observe(self, address, equity):
        self.observed.append((address, equity))
        return equity

    async def observe_daily(self, address, equity):
        self.daily_observed.append((address, equity))
        return equity


def _loader_returning(*exposures):
    async def _load(refs):
        del refs
        return tuple(exposures)

    return _load


def _healthy_exposure(address="0xabc", network="testnet") -> AccountExposure:
    return AccountExposure(
        address=address,
        network=network,
        equity=10_000.0,
        free_collateral=9_000.0,
        open_market_count=3,
        complete=True,
        per_market_notional_usd={"BTC-USD": 100.0},
    )


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def test_limits_from_config_round_trips_every_control():
    config = {
        "enabled": True,
        "limits": {
            "max_open_markets": 20,
            "max_margin_utilization_pct": 60.0,
            "min_free_collateral_usd": 100.0,
            "max_drawdown_pct": 15.0,
            "aggregate_max_open_markets": 30,
            "aggregate_max_margin_utilization_pct": 70.0,
            "max_notional_per_market_usd": 5000.0,
            "max_total_notional_pct": 200.0,
            "max_daily_loss_pct": 5.0,
        },
        "correlation_buckets": [
            {
                "name": "majors",
                "markets": ["BTC-USD", "ETH-USD"],
                "max_notional_pct_of_equity": 50.0,
            },
            # Non-positive caps and nameless entries are skipped, not fatal.
            {"name": "bad", "markets": ["X-USD"], "max_notional_pct_of_equity": 0},
            {"name": "", "markets": ["Y-USD"], "max_notional_pct_of_equity": 10},
        ],
    }
    limits = burn_in.limits_from_config(config)
    assert limits.max_open_markets == 20
    assert limits.max_margin_utilization_pct == 60.0
    assert limits.min_free_collateral_usd == 100.0
    assert limits.max_drawdown_pct == 15.0
    assert limits.aggregate_max_open_markets == 30
    assert limits.aggregate_max_margin_utilization_pct == 70.0
    assert limits.max_notional_per_market_usd == 5000.0
    assert limits.max_total_notional_pct == 200.0
    assert limits.max_daily_loss_pct == 5.0
    assert len(limits.correlation_buckets) == 1
    assert limits.correlation_buckets[0].name == "majors"
    assert limits.correlation_buckets[0].markets == frozenset({"BTC-USD", "ETH-USD"})


def test_snapshot_from_exposure_maps_all_fields():
    exposure = AccountExposure(
        address="0x1",
        network="testnet",
        equity=100.0,
        free_collateral=50.0,
        open_market_count=2,
        complete=True,
        per_market_notional_usd={"BTC-USD": 10.0},
        unparsed_position_count=1,
    )
    snapshot = burn_in.snapshot_from_exposure(exposure)
    assert snapshot.equity == 100.0
    assert snapshot.free_collateral == 50.0
    assert snapshot.open_market_count == 2
    assert snapshot.per_market_notional_usd == {"BTC-USD": 10.0}
    assert snapshot.unparsed_position_count == 1


# --------------------------------------------------------------------------- #
# Cycle + run semantics
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_run_burn_in_allows_healthy_account():
    peak_store = _FakePeakStore()
    records, summary = await burn_in.run_burn_in(
        (PortfolioAccountRef(address="0xabc", network="testnet"),),
        _DEFAULT_LIMITS,
        cycles=3,
        interval_seconds=0,
        incremental_notional_usd=100.0,
        load_exposures=_loader_returning(_healthy_exposure()),
        peak_store=peak_store,
    )
    assert summary["passed"] is True
    assert summary["cycles_failed"] == 0
    assert summary["data_unavailable_events"] == 0
    account = summary["accounts"][0]
    assert account["address"] == "0xabc"
    assert account["allowed_cycles"] == 3
    assert account["denied_cycles"] == 0
    # The peak ratchet is observed on every cycle with equity present, and the
    # daily key is only touched when the daily-loss control is configured.
    assert len(peak_store.observed) == 3
    assert peak_store.daily_observed == []
    assert records[0]["accounts"][0]["peak_equity_state"] == "observed"
    assert records[0]["accounts"][0]["allowed"] is True


@pytest.mark.asyncio
async def test_run_burn_in_fails_on_data_unavailable():
    incomplete = AccountExposure(
        address="0xabc",
        network="testnet",
        equity=None,
        free_collateral=None,
        open_market_count=0,
        complete=False,
        error="ReadError",
    )
    records, summary = await burn_in.run_burn_in(
        (PortfolioAccountRef(address="0xabc", network="testnet"),),
        _DEFAULT_LIMITS,
        cycles=2,
        interval_seconds=0,
        incremental_notional_usd=100.0,
        load_exposures=_loader_returning(incomplete),
        peak_store=_FakePeakStore(),
    )
    # A read the evaluator must reject is exactly the false-denial class the
    # burn-in exists to catch.
    assert summary["passed"] is False
    assert summary["data_unavailable_events"] == 2
    account = summary["accounts"][0]
    assert account["denied_cycles"] == 2
    assert "portfolio_data_unavailable" in account["reasons_seen"]
    assert account["read_errors"] == 2
    assert records[0]["accounts"][0]["read_error"] == "ReadError"
    # No equity -> the peak store is never touched.
    assert records[0]["accounts"][0]["peak_equity_state"] == "skipped"


@pytest.mark.asyncio
async def test_run_burn_in_reports_limit_denial_without_failing():
    over_limit = AccountExposure(
        address="0xabc",
        network="testnet",
        equity=10_000.0,
        free_collateral=1_000.0,  # 90% utilization > 60% cap
        open_market_count=25,  # > 20-market cap
        complete=True,
    )
    records, summary = await burn_in.run_burn_in(
        (PortfolioAccountRef(address="0xabc", network="testnet"),),
        _DEFAULT_LIMITS,
        cycles=2,
        interval_seconds=0,
        incremental_notional_usd=100.0,
        load_exposures=_loader_returning(over_limit),
        peak_store=_FakePeakStore(),
    )
    # The guard denying an over-limit account is correct behavior, not a
    # burn-in failure.
    assert summary["passed"] is True
    assert summary["limit_denial_events"] == 2
    assert summary["data_unavailable_events"] == 0
    assert "portfolio_max_open_markets" in summary["accounts"][0]["reasons_seen"]
    assert "portfolio_margin_utilization" in summary["accounts"][0]["reasons_seen"]
    assert records[0]["accounts"][0]["allowed"] is False


@pytest.mark.asyncio
async def test_run_burn_in_records_cycle_errors_and_fails():
    async def _exploding_loader(refs):
        del refs
        raise RuntimeError("indexer down")

    records, summary = await burn_in.run_burn_in(
        (PortfolioAccountRef(address="0xabc", network="testnet"),),
        _DEFAULT_LIMITS,
        cycles=3,
        interval_seconds=0,
        incremental_notional_usd=100.0,
        load_exposures=_exploding_loader,
        peak_store=_FakePeakStore(),
    )
    assert summary["cycles_failed"] == 3
    assert summary["passed"] is False
    assert all("RuntimeError" in (record["cycle_error"] or "") for record in records)
    assert summary["accounts"] == []


@pytest.mark.asyncio
async def test_run_burn_in_evaluates_aggregate_when_configured():
    aggregate_limits = PortfolioRiskLimits(
        max_open_markets=0,
        max_margin_utilization_pct=0.0,
        min_free_collateral_usd=0.0,
        max_drawdown_pct=0.0,
        aggregate_max_open_markets=3,
    )
    refs = (
        PortfolioAccountRef(address="0x1", network="testnet"),
        PortfolioAccountRef(address="0x2", network="testnet"),
        PortfolioAccountRef(address="0x9", network="mainnet"),
    )
    exposures = (
        _healthy_exposure("0x1"),
        AccountExposure(
            address="0x2",
            network="testnet",
            equity=5_000.0,
            free_collateral=5_000.0,
            open_market_count=2,
            complete=True,
        ),
        # Mainnet account stays clearly UNDER the cap so only the testnet
        # aggregate denies (at-limit counts as full, so 3 would also trip).
        AccountExposure(
            address="0x9",
            network="mainnet",
            equity=5_000.0,
            free_collateral=5_000.0,
            open_market_count=1,
            complete=True,
        ),
    )
    records, summary = await burn_in.run_burn_in(
        refs,
        aggregate_limits,
        cycles=1,
        interval_seconds=0,
        incremental_notional_usd=100.0,
        load_exposures=_loader_returning(*exposures),
        peak_store=_FakePeakStore(),
    )
    aggregate = records[0]["aggregates"]["testnet"]
    assert aggregate["total_open_markets"] == 5  # 3 + 2, above the cap of 3
    assert aggregate["allowed"] is False
    assert aggregate["reasons"] == ["portfolio_aggregate_max_open_markets"]
    # Per-account decisions stay allowed (each account is inside per-account
    # limits — all disabled here); the aggregate denial is the guard signal.
    assert summary["passed"] is True
    assert summary["limit_denial_events"] == 1
    assert summary["data_unavailable_events"] == 0


@pytest.mark.asyncio
async def test_run_burn_in_counts_decision_changes():
    healthy = _healthy_exposure()

    async def _loader(refs):
        del refs
        return (healthy,)

    _, summary = await burn_in.run_burn_in(
        (PortfolioAccountRef(address="0xabc", network="testnet"),),
        _DEFAULT_LIMITS,
        cycles=3,
        interval_seconds=0,
        incremental_notional_usd=100.0,
        load_exposures=_loader,
        peak_store=_FakePeakStore(),
    )
    assert summary["decision_changes"] == 0  # stable account, stable decision

    flip_state = {"over": False}

    async def _flipping_loader(refs):
        del refs
        if flip_state["over"]:
            return (
                AccountExposure(
                    address="0xabc",
                    network="testnet",
                    equity=10_000.0,
                    free_collateral=1_000.0,
                    open_market_count=3,
                    complete=True,
                ),
            )
        return (healthy,)

    records = [
        # Simulate a mid-run account change by alternating the loader.
        await burn_in.run_burn_in_cycle(
            (PortfolioAccountRef(address="0xabc", network="testnet"),),
            _DEFAULT_LIMITS,
            incremental_notional_usd=100.0,
            load_exposures=_flipping_loader,
            peak_store=_FakePeakStore(),
        )
    ]
    flip_state["over"] = True
    records.append(
        await burn_in.run_burn_in_cycle(
            (PortfolioAccountRef(address="0xabc", network="testnet"),),
            _DEFAULT_LIMITS,
            incremental_notional_usd=100.0,
            load_exposures=_flipping_loader,
            peak_store=_FakePeakStore(),
        )
    )
    changed = burn_in.summarize_burn_in(records)
    assert changed["decision_changes"] == 1


def test_summarize_empty_records_fails_closed():
    summary = burn_in.summarize_burn_in([])
    assert summary["cycles_run"] == 0
    assert summary["passed"] is False  # zero evidence is not a clean burn-in


def test_write_evidence_round_trips(tmp_path):
    records, summary = [
        {
            "cycle": 1,
            "at": "2026-08-17T00:00:00+00:00",
            "accounts": [
                {
                    "address": "0xabc",
                    "network": "testnet",
                    "equity": 1.0,
                    "free_collateral": 1.0,
                    "open_markets": 0,
                    "total_notional_usd": 0.0,
                    "unparsed_positions": 0,
                    "complete": True,
                    "read_error": None,
                    "peak_equity_state": "observed",
                    "allowed": True,
                    "reasons": [],
                }
            ],
            "aggregates": {},
            "cycle_error": None,
        }
    ], {"passed": True, "cycles_run": 1}
    out = tmp_path / "nested" / "evidence.json"
    burn_in.write_evidence(
        out,
        config={"enabled": True, "limits": {}},
        subaccounts=[{"address": "0xabc", "network": "testnet"}],
        records=records,
        summary=summary,
        cycles=1,
        interval_seconds=0.0,
        incremental_notional_usd=100.0,
    )
    payload = json.loads(out.read_text())
    assert payload["config"]["enabled"] is True
    assert payload["records"][0]["accounts"][0]["address"] == "0xabc"
    assert payload["summary"]["passed"] is True
    assert payload["subaccounts"] == [{"address": "0xabc", "network": "testnet"}]
