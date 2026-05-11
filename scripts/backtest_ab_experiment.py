#!/usr/bin/env python3
"""Run backtest A/B experiments and compare results.

This helper is intended for safe operator experiments where you want to measure:
- strategy-input impact (recommended): pair_selection_mode / max_pairs
- optional runtime-flag impact (advanced): arbitrage runtime settings toggles

By default it only changes backtest request inputs and leaves runtime settings untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timeout", "stale"}


class ApiError(RuntimeError):
    """Raised when API calls fail."""


def _request_json(
    method: str,
    url: str,
    *,
    token: str | None,
    payload: dict[str, Any] | None = None,
    timeout: float = 45.0,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ApiError(f"{method} {url} failed: {exc.reason}") from exc


def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _parse_list(raw: str) -> list[str]:
    items = [item.strip() for item in (raw or "").split(",") if item.strip()]
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        token = item.upper()
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return unique


def _parse_runtime_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid runtime json: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("runtime json must decode to an object")
    return value


def _api_get_runtime_settings(base_url: str, token: str | None) -> dict[str, Any]:
    payload = _request_json(
        "GET",
        f"{base_url}/api/v1/settings/arbitrage-runtime",
        token=token,
    )
    return _unwrap(payload)


def _api_put_runtime_settings(
    base_url: str,
    token: str | None,
    settings: dict[str, Any],
) -> dict[str, Any]:
    payload = _request_json(
        "PUT",
        f"{base_url}/api/v1/settings/arbitrage-runtime",
        token=token,
        payload={"settings": settings},
    )
    return _unwrap(payload)


def _api_launch_backtest(
    base_url: str,
    token: str | None,
    payload: dict[str, Any],
) -> str:
    response = _request_json(
        "POST",
        f"{base_url}/api/v1/backtests/run",
        token=token,
        payload=payload,
        timeout=60.0,
    )
    data = _unwrap(response)
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ApiError(f"launch response missing run_id: {json.dumps(response)[:500]}")
    return run_id


def _api_backtest_status(base_url: str, token: str | None, run_id: str) -> dict[str, Any]:
    payload = _request_json(
        "GET",
        f"{base_url}/api/v1/backtests/{run_id}/status",
        token=token,
        timeout=45.0,
    )
    return _unwrap(payload)


def _wait_for_terminal_status(
    base_url: str,
    token: str | None,
    run_id: str,
    *,
    interval_seconds: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        status_payload = _api_backtest_status(base_url, token, run_id)
        status = str(status_payload.get("status") or "unknown").lower()
        progress = float(status_payload.get("progress_pct", status_payload.get("progress", 0)) or 0)
        pnl = status_payload.get("total_pnl", 0)
        trades = status_payload.get("total_trades", 0)
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(
            f"[{now}] run={run_id} status={status} progress={progress:.1f}% trades={trades} pnl={pnl}",
            flush=True,
        )

        if status in TERMINAL_STATUSES:
            return status_payload
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"Timed out waiting for run {run_id} terminal status; last={status}"
            )
        time.sleep(max(1.0, interval_seconds))


def _api_compare(
    base_url: str,
    token: str | None,
    run_ids: list[str],
    metrics: list[str],
) -> dict[str, Any]:
    payload = _request_json(
        "POST",
        f"{base_url}/api/v1/backtests/compare",
        token=token,
        payload={"run_ids": run_ids, "metrics": metrics},
        timeout=60.0,
    )
    return _unwrap(payload)


def _build_run_payload(
    *,
    name: str,
    start_date: str,
    end_date: str,
    selected_pairs: list[str],
    pair_selection_mode: str,
    max_pairs: int,
    initial_balance: float,
    timeout_seconds: float,
    zscore_threshold: float,
    stats_window: int,
    usd_per_trade: float,
) -> dict[str, Any]:
    return {
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
        "initial_balance": float(initial_balance),
        "max_pairs": int(max_pairs),
        "pair_selection_mode": str(pair_selection_mode),
        "selected_pairs": selected_pairs,
        "trading_parameters": {
            "zscore_threshold": float(zscore_threshold),
            "stats_window": int(stats_window),
            "usd_per_trade": float(usd_per_trade),
            "pair_selection_mode": str(pair_selection_mode),
        },
        "timeout_seconds": float(timeout_seconds),
    }


def _print_compare_summary(compare_payload: dict[str, Any]) -> None:
    print("\n=== A/B Comparison Summary ===", flush=True)
    summary = compare_payload.get("summary")
    runs = compare_payload.get("runs")
    if isinstance(runs, list):
        for run in runs:
            run_id = run.get("run_id")
            run_name = run.get("name")
            status = run.get("status")
            metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
            print(
                f"- run_id={run_id} name={run_name} status={status} "
                f"pnl={metrics.get('total_pnl')} sharpe={metrics.get('sharpe_ratio')} "
                f"win_rate={metrics.get('win_rate')} drawdown={metrics.get('max_drawdown_pct')}",
                flush=True,
            )

    if isinstance(summary, dict) and summary:
        print("\nMetric aggregates:", flush=True)
        for metric, stats in summary.items():
            if not isinstance(stats, dict):
                continue
            print(
                f"  {metric}: best={stats.get('best')} worst={stats.get('worst')} avg={stats.get('average')}",
                flush=True,
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run backtest A/B experiments")
    parser.add_argument("--base-url", default=os.getenv("BACKEND_URL", "http://localhost:8888"))
    parser.add_argument("--token", default=os.getenv("ADMIN_TOKEN") or os.getenv("AUTH_TOKEN") or os.getenv("BACKEND_TOKEN"))

    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument(
        "--selected-pairs",
        required=True,
        help="Comma-separated pair labels (example: BTC-USD/ETH-USD,SOL-USD/AVAX-USD)",
    )

    parser.add_argument("--experiment-name", default="ab-experiment")
    parser.add_argument("--initial-balance", type=float, default=1000.0)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--poll-interval", type=float, default=5.0)

    parser.add_argument("--pair-selection-mode-a", default="liquidity")
    parser.add_argument("--pair-selection-mode-b", default="cointegration")
    parser.add_argument("--max-pairs-a", type=int, default=0)
    parser.add_argument("--max-pairs-b", type=int, default=0)

    parser.add_argument("--zscore-threshold", type=float, default=1.5)
    parser.add_argument("--stats-window", type=int, default=21)
    parser.add_argument("--usd-per-trade", type=float, default=10.0)

    parser.add_argument(
        "--runtime-settings-a-json",
        default="",
        help="Optional JSON object to apply to /settings/arbitrage-runtime before run A",
    )
    parser.add_argument(
        "--runtime-settings-b-json",
        default="",
        help="Optional JSON object to apply to /settings/arbitrage-runtime before run B",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    base_url = args.base_url.rstrip("/")
    selected_pairs = _parse_list(args.selected_pairs)
    if len(selected_pairs) < 1:
        raise SystemExit("--selected-pairs must include at least one pair label")

    runtime_a = _parse_runtime_json(args.runtime_settings_a_json)
    runtime_b = _parse_runtime_json(args.runtime_settings_b_json)
    runtime_changes_requested = bool(runtime_a or runtime_b)

    if runtime_changes_requested and not args.token:
        raise SystemExit("token required when runtime settings overrides are used")

    original_runtime: dict[str, Any] | None = None
    run_a_id = ""
    run_b_id = ""

    try:
        if runtime_changes_requested:
            original_runtime = _api_get_runtime_settings(base_url, args.token)
            print("Captured original runtime settings.", flush=True)

        payload_a = _build_run_payload(
            name=f"{args.experiment_name}-A",
            start_date=args.start_date,
            end_date=args.end_date,
            selected_pairs=selected_pairs,
            pair_selection_mode=args.pair_selection_mode_a,
            max_pairs=args.max_pairs_a,
            initial_balance=args.initial_balance,
            timeout_seconds=args.timeout_seconds,
            zscore_threshold=args.zscore_threshold,
            stats_window=args.stats_window,
            usd_per_trade=args.usd_per_trade,
        )
        payload_b = _build_run_payload(
            name=f"{args.experiment_name}-B",
            start_date=args.start_date,
            end_date=args.end_date,
            selected_pairs=selected_pairs,
            pair_selection_mode=args.pair_selection_mode_b,
            max_pairs=args.max_pairs_b,
            initial_balance=args.initial_balance,
            timeout_seconds=args.timeout_seconds,
            zscore_threshold=args.zscore_threshold,
            stats_window=args.stats_window,
            usd_per_trade=args.usd_per_trade,
        )

        if runtime_a:
            applied_a = _api_put_runtime_settings(base_url, args.token, runtime_a)
            print(f"Applied runtime override A keys={sorted(applied_a.keys())}", flush=True)

        print("Launching run A...", flush=True)
        run_a_id = _api_launch_backtest(base_url, args.token, payload_a)
        status_a = _wait_for_terminal_status(
            base_url,
            args.token,
            run_a_id,
            interval_seconds=args.poll_interval,
            timeout_seconds=args.timeout_seconds + 120,
        )

        if runtime_b:
            applied_b = _api_put_runtime_settings(base_url, args.token, runtime_b)
            print(f"Applied runtime override B keys={sorted(applied_b.keys())}", flush=True)

        print("Launching run B...", flush=True)
        run_b_id = _api_launch_backtest(base_url, args.token, payload_b)
        status_b = _wait_for_terminal_status(
            base_url,
            args.token,
            run_b_id,
            interval_seconds=args.poll_interval,
            timeout_seconds=args.timeout_seconds + 120,
        )

        metrics = [
            "total_pnl",
            "win_rate",
            "sharpe_ratio",
            "max_drawdown_pct",
            "total_trades",
            "profit_factor",
        ]
        compare_payload = _api_compare(base_url, args.token, [run_a_id, run_b_id], metrics)
        _print_compare_summary(compare_payload)

        print(
            json.dumps(
                {
                    "run_a_id": run_a_id,
                    "run_b_id": run_b_id,
                    "status_a": status_a.get("status"),
                    "status_b": status_b.get("status"),
                    "compare": compare_payload,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )

        # Return non-zero if either run is not completed; still emit comparison when available.
        if str(status_a.get("status", "")).lower() != "completed":
            return 2
        if str(status_b.get("status", "")).lower() != "completed":
            return 2
        return 0

    finally:
        if runtime_changes_requested and original_runtime:
            try:
                _api_put_runtime_settings(base_url, args.token, original_runtime)
                print("Restored original runtime settings.", flush=True)
            except Exception as exc:  # pragma: no cover
                print(f"WARNING: failed to restore original runtime settings: {exc}", file=sys.stderr)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
