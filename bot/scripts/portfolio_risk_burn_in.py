#!/usr/bin/env python3
"""Phase B burn-in harness for the account-level portfolio risk guard.

Runs repeated live evaluations of the guard decision against every distinct
subaccount configured in ``bot_instances`` — the same public per-address
indexer reads the monitoring endpoint uses (no signing credentials) — with
the exact production limits, and fails on anything that would cause a FALSE
denial or an unstable data path once the guard is enabled by default:

* a transport/DB error in any cycle fails the burn-in (the guard fails closed
  on the entry path, so a flaky data path means denied entries);
* ``portfolio_data_unavailable`` / incomplete-account observations fail the
  burn-in (the data path produced something the evaluator had to reject);
* genuine limit denials (``portfolio_max_open_markets``, ``portfolio_margin_
  utilization``, drawdown, notional/bucket caps, ``portfolio_aggregate_*``)
  are REPORTED, not failed — the guard doing its job on an over-limit account
  is correct behavior; the operator decides whether to raise the limit.

Evidence: ``--json-out PATH`` writes the full per-cycle log plus the summary
(this file is the Phase B flip evidence). Exit codes: 0 = clean burn-in,
1 = burn-in failed (see the summary), 2 = usage/config error.

Environment: run through the repo env (``load_repo_env`` is called in
``main()`` before any project import, mirroring the canonical entrypoints —
imports are function-scoped so importing this module from tests has no env
side effects).

Usage:
    .venv/bin/python scripts/portfolio_risk_burn_in.py \
        --cycles 20 --interval-seconds 5 \
        --json-out bot_states/portfolio_risk_burn_in.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from loguru import logger

# Data-unavailable reason codes that indicate a data-path problem (a denial
# the operator did not configure) rather than a configured limit being hit.
_DATA_PATH_REASONS = frozenset({"portfolio_data_unavailable"})


def limits_from_config(config: dict) -> Any:
    """Rebuild :class:`PortfolioRiskLimits` from ``portfolio_risk_config()``.

    Using the operator-facing snapshot keeps the burn-in on public seams and
    doubles as a consistency check that the reported config is evaluable.
    """
    from src.trading.portfolio_risk import (
        CorrelationBucket,
        PortfolioRiskLimits,
    )

    raw = config.get("limits", {})
    buckets = tuple(
        CorrelationBucket(
            name=bucket["name"],
            markets=frozenset(bucket.get("markets", ())),
            max_notional_pct_of_equity=float(bucket["max_notional_pct_of_equity"]),
        )
        for bucket in config.get("correlation_buckets", ())
        if bucket.get("name") and bucket.get("max_notional_pct_of_equity", 0) > 0
    )
    return PortfolioRiskLimits(
        max_open_markets=int(raw.get("max_open_markets", 0)),
        max_margin_utilization_pct=float(raw.get("max_margin_utilization_pct", 0.0)),
        min_free_collateral_usd=float(raw.get("min_free_collateral_usd", 0.0)),
        max_drawdown_pct=float(raw.get("max_drawdown_pct", 0.0)),
        aggregate_max_open_markets=int(raw.get("aggregate_max_open_markets", 0)),
        aggregate_max_margin_utilization_pct=float(
            raw.get("aggregate_max_margin_utilization_pct", 0.0)
        ),
        max_notional_per_market_usd=float(raw.get("max_notional_per_market_usd", 0.0)),
        max_total_notional_pct=float(raw.get("max_total_notional_pct", 0.0)),
        max_daily_loss_pct=float(raw.get("max_daily_loss_pct", 0.0)),
        correlation_buckets=buckets,
    )


def snapshot_from_exposure(exposure: Any) -> Any:
    """Map a public :class:`AccountExposure` onto the guard's snapshot type."""
    from src.trading.portfolio_risk import PortfolioSnapshot

    return PortfolioSnapshot(
        equity=exposure.equity,
        free_collateral=exposure.free_collateral,
        open_market_count=exposure.open_market_count,
        per_market_notional_usd=dict(exposure.per_market_notional_usd),
        unparsed_position_count=exposure.unparsed_position_count,
    )


async def run_burn_in_cycle(
    refs: Sequence[Any],
    limits: Any,
    *,
    incremental_notional_usd: float,
    load_exposures: Callable[..., Any],
    peak_store: Any,
) -> dict:
    """One evaluation cycle: live exposures → per-account + aggregate decisions."""
    from src.trading.portfolio_risk import (
        evaluate_aggregate_entry,
        evaluate_portfolio_entry,
    )

    exposures = await load_exposures(tuple(refs))
    accounts: list[dict] = []
    for exposure in exposures:
        peak_equity: float | None = None
        daily_peak_equity: float | None = None
        peak_state = "skipped"
        if exposure.equity is not None:
            peak_equity = await peak_store.observe(exposure.address, exposure.equity)
            peak_state = "observed" if peak_equity is not None else "unavailable"
            if limits.max_daily_loss_pct > 0:
                daily_peak_equity = await peak_store.observe_daily(
                    exposure.address, exposure.equity
                )
        decision = evaluate_portfolio_entry(
            snapshot_from_exposure(exposure),
            limits,
            incremental_notional_usd=incremental_notional_usd,
            peak_equity=peak_equity,
            daily_peak_equity=daily_peak_equity,
        )
        accounts.append(
            {
                "address": exposure.address,
                "network": exposure.network,
                "equity": exposure.equity,
                "free_collateral": exposure.free_collateral,
                "open_markets": exposure.open_market_count,
                "total_notional_usd": round(
                    sum(exposure.per_market_notional_usd.values()), 2
                ),
                "unparsed_positions": exposure.unparsed_position_count,
                "complete": exposure.complete,
                "read_error": exposure.error,
                "peak_equity_state": peak_state,
                "allowed": decision.allowed,
                "reasons": list(decision.reasons),
            }
        )

    aggregates: dict[str, dict] = {}
    if (
        limits.aggregate_max_open_markets > 0
        or limits.aggregate_max_margin_utilization_pct > 0
    ):
        for network in sorted({exposure.network for exposure in exposures}):
            network_exposures = tuple(
                exposure for exposure in exposures if exposure.network == network
            )
            evaluation = evaluate_aggregate_entry(network_exposures, limits)
            totals = evaluation.totals
            aggregates[network] = {
                "accounts": totals.accounts,
                "incomplete_accounts": totals.incomplete_accounts,
                "total_equity": totals.total_equity,
                "total_free_collateral": totals.total_free_collateral,
                "total_open_markets": totals.total_open_markets,
                "margin_utilization_pct": totals.margin_utilization_pct,
                "allowed": evaluation.allowed,
                "reasons": list(evaluation.reasons),
            }
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "accounts": accounts,
        "aggregates": aggregates,
        "cycle_error": None,
    }


async def run_burn_in(
    refs: Sequence[Any],
    limits: Any,
    *,
    cycles: int,
    interval_seconds: float,
    incremental_notional_usd: float,
    load_exposures: Callable[..., Any] | None = None,
    peak_store: Any | None = None,
) -> tuple[list[dict], dict]:
    """Run ``cycles`` evaluation cycles and summarize them.

    ``load_exposures``/``peak_store`` are injection seams for tests; production
    resolves them in :func:`main`. A cycle that raises is recorded as failed
    and the run continues — the flakiness RATE is itself burn-in evidence.
    """
    from src.trading.portfolio_accounts import load_account_exposures_http
    from src.trading.portfolio_risk import get_peak_equity_store

    loader = load_exposures or load_account_exposures_http
    store = peak_store or get_peak_equity_store()
    records: list[dict] = []
    for index in range(cycles):
        try:
            record = await run_burn_in_cycle(
                refs,
                limits,
                incremental_notional_usd=incremental_notional_usd,
                load_exposures=loader,
                peak_store=store,
            )
        except Exception as exc:  # burn-in evidence: capture, keep cycling
            logger.exception("burn-in cycle {} failed", index + 1)
            record = {
                "at": datetime.now(timezone.utc).isoformat(),
                "accounts": [],
                "aggregates": {},
                "cycle_error": f"{type(exc).__name__}: {exc}",
            }
        record["cycle"] = index + 1
        records.append(record)
        if index + 1 < cycles and interval_seconds > 0:
            await asyncio.sleep(interval_seconds)
    return records, summarize_burn_in(records)


def summarize_burn_in(records: list[dict]) -> dict:
    """Pure pass/fail summary over the cycle records.

    Fails on cycle errors and data-path denials only — configured-limit
    denials (per-account AND aggregate) are correct guard behavior and are
    reported as tallies.
    """
    cycles_run = len(records)
    cycles_failed = sum(1 for record in records if record.get("cycle_error"))
    accounts: dict[tuple[str, str], dict] = {}
    data_unavailable_events = 0
    limit_denial_events = 0
    last_reasons: dict[tuple[str, str], tuple[str, ...]] = {}
    decision_changes = 0
    for record in records:
        for aggregate in record.get("aggregates", {}).values():
            if not aggregate["allowed"]:
                limit_denial_events += 1
        for account in record.get("accounts", ()):
            key = (account["network"], account["address"])
            entry = accounts.setdefault(
                key,
                {
                    "allowed_cycles": 0,
                    "denied_cycles": 0,
                    "reasons_seen": [],
                    "read_errors": 0,
                    "data_unavailable_cycles": 0,
                },
            )
            reasons = tuple(account["reasons"])
            if account.get("read_error"):
                entry["read_errors"] += 1
            if account["allowed"]:
                entry["allowed_cycles"] += 1
            else:
                entry["denied_cycles"] += 1
                if _DATA_PATH_REASONS.intersection(reasons):
                    entry["data_unavailable_cycles"] += 1
                    data_unavailable_events += 1
                else:
                    limit_denial_events += 1
            for reason in reasons:
                if reason not in entry["reasons_seen"]:
                    entry["reasons_seen"].append(reason)
            if key in last_reasons and last_reasons[key] != reasons:
                decision_changes += 1
            last_reasons[key] = reasons

    passed = cycles_run > 0 and cycles_failed == 0 and data_unavailable_events == 0
    return {
        "cycles_run": cycles_run,
        "cycles_failed": cycles_failed,
        "data_unavailable_events": data_unavailable_events,
        "limit_denial_events": limit_denial_events,
        "decision_changes": decision_changes,
        "accounts": [
            {"network": network, "address": address, **stats}
            for (network, address), stats in sorted(accounts.items())
        ],
        "passed": passed,
    }


def _print_summary(summary: dict, records: list[dict]) -> None:
    print(
        f"burn-in: {summary['cycles_run']} cycles, "
        f"{summary['cycles_failed']} failed, "
        f"{summary['data_unavailable_events']} data-unavailable events, "
        f"{summary['limit_denial_events']} limit denials, "
        f"{summary['decision_changes']} decision changes"
    )
    for account in summary["accounts"]:
        print(
            f"  {account['network']:8s} {account['address']}: "
            f"allowed={account['allowed_cycles']} denied={account['denied_cycles']} "
            f"reasons={account['reasons_seen'] or ['-']} "
            f"read_errors={account['read_errors']}"
        )
    for record in records:
        if record.get("cycle_error"):
            print(f"  cycle {record['cycle']} error: {record['cycle_error']}")
    print(f"burn-in result: {'PASS' if summary['passed'] else 'FAIL'}")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase B burn-in for the portfolio risk guard: repeated live "
            "evaluations of the production limits against every configured "
            "subaccount (public indexer reads)."
        )
    )
    parser.add_argument(
        "--cycles", type=int, default=20, help="evaluation cycles (default 20)"
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=5.0,
        help="sleep between cycles (default 5)",
    )
    parser.add_argument(
        "--incremental-notional-usd",
        type=float,
        default=100.0,
        help="notional a hypothetical new pair entry would consume (default 100)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="write the full cycle log + summary to this JSON file (flip evidence)",
    )
    return parser.parse_args(argv)


def write_evidence(
    path: Path,
    *,
    config: dict,
    subaccounts: Sequence[dict],
    records: list[dict],
    summary: dict,
    cycles: int,
    interval_seconds: float,
    incremental_notional_usd: float,
) -> None:
    """Persist the full burn-in log + summary as the Phase B flip evidence."""
    payload = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cycles": cycles,
        "interval_seconds": interval_seconds,
        "incremental_notional_usd": incremental_notional_usd,
        "config": config,
        "subaccounts": list(subaccounts),
        "records": records,
        "summary": summary,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    # Running this file puts scripts/ (not the bot root) on sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    # Mandatory: load structured config BEFORE importing project modules
    # (AGENTS.md rule 1). Imports below are function-scoped so this module
    # stays importable by tests without env side effects.
    from src.shared.env_loader import load_repo_env

    load_repo_env(__file__)

    from src.trading.portfolio_accounts import enumerate_portfolio_accounts
    from src.trading.portfolio_risk import portfolio_risk_config

    async def _run() -> int:
        refs = await enumerate_portfolio_accounts()
        if not refs:
            print(
                "burn-in: no subaccounts configured in bot_instances — "
                "seed at least one row (address under config.credentials) first",
                file=sys.stderr,
            )
            return 2
        config = portfolio_risk_config()
        limits = limits_from_config(config)
        print(
            f"burn-in: {len(refs)} subaccount(s), guard enabled="
            f"{config['enabled']}, limits={config['limits']}"
        )
        records, summary = await run_burn_in(
            refs,
            limits,
            cycles=args.cycles,
            interval_seconds=args.interval_seconds,
            incremental_notional_usd=args.incremental_notional_usd,
        )
        _print_summary(summary, records)
        if args.json_out is not None:
            write_evidence(
                args.json_out,
                config=config,
                subaccounts=[
                    {"address": ref.address, "network": ref.network} for ref in refs
                ],
                records=records,
                summary=summary,
                cycles=args.cycles,
                interval_seconds=args.interval_seconds,
                incremental_notional_usd=args.incremental_notional_usd,
            )
            print(f"burn-in evidence written to {args.json_out}")
        return 0 if summary["passed"] else 1

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
