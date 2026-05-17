#!/usr/bin/env python3
"""Run production-profile backtest simulation against bot API and compare results."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple


@dataclass
class BacktestRun:
    name: str
    run_id: str


def _request_json(
        url: str, method: str = "GET", data: Optional[dict] = None, token: Optional[str] = None
) -> Tuple[int, dict]:
    payload = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if data is not None:
        payload = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url=url, data=payload, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        parsed: Dict[str, Any]
        try:
            parsed = json.loads(raw) if raw else {"message": str(exc)}
        except json.JSONDecodeError:
            parsed = {"message": raw or str(exc)}
        return exc.code, parsed


def login(base_url: str, username: str, password: str) -> str:
    status, body = _request_json(
        f"{base_url}/auth/login",
        method="POST",
        data={"username": username, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"Login failed ({status}): {body}")

    data = body.get("data", {})
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access token returned")
    return token


def create_backtest(
        base_url: str,
        token: Optional[str],
        config: dict,
) -> BacktestRun:
    status, body = _request_json(
        f"{base_url}/api/v1/backtests",
        method="POST",
        data=config,
        token=token,
    )
    if status != 200:
        raise RuntimeError(f"Create backtest failed ({status}): {body}")

    data = body.get("data", {})
    run_id = data.get("run_id") or data.get("id")
    if not run_id:
        raise RuntimeError(f"Backtest response missing run_id: {body}")

    return BacktestRun(name=config["name"], run_id=str(run_id))


def wait_for_completion(
        base_url: str,
        token: Optional[str],
        run: BacktestRun,
        timeout_seconds: int,
        poll_seconds: int,
) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status, body = _request_json(
            f"{base_url}/api/v1/backtests/{run.run_id}/status",
            token=token,
        )
        if status != 200:
            raise RuntimeError(f"Status check failed for {run.run_id} ({status}): {body}")

        data = body.get("data", {})
        state = str(data.get("status", "")).lower()
        progress = data.get("progress_pct", 0)
        print(f"[{run.name}] status={state} progress={progress}%")

        if state in {"completed", "failed", "cancelled"}:
            return data

        time.sleep(poll_seconds)

    raise TimeoutError(f"Timed out waiting for backtest {run.run_id}")


def get_details(base_url: str, token: Optional[str], run_id: str) -> dict:
    status, body = _request_json(f"{base_url}/api/v1/backtests/{run_id}", token=token)
    if status != 200:
        raise RuntimeError(f"Details fetch failed for {run_id} ({status}): {body}")
    return body.get("data", {})


def _metric_value(payload: dict, key: str):
    if key in payload:
        return payload.get(key)
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        return metrics.get(key)
    return None


def compare_runs(baseline: dict, production: dict) -> None:
    keys = [
        "total_pnl",
        "win_rate",
        "sharpe_ratio",
        "max_drawdown_pct",
        "total_trades",
    ]

    print("\n=== Production-Profile Comparison ===")
    for key in keys:
        b = _metric_value(baseline, key)
        p = _metric_value(production, key)
        print(f"{key:>18}: baseline={b} | production_profile={p}")

    print("\nInterpretation:")
    print("- If production_profile has materially worse drawdown or Sharpe, hold deployment.")
    print("- If PnL is similar but trade count spikes, review slippage/liquidity assumptions.")


def default_dates() -> Tuple[str, str]:
    end = date.today() - timedelta(days=7)
    start = end - timedelta(days=30)
    return start.isoformat(), end.isoformat()


def parse_args() -> argparse.Namespace:
    start, end = default_dates()
    bypass_auth_default = os.getenv("API_BYPASS_AUTH", "false").lower() == "true"
    parser = argparse.ArgumentParser(
        description="Run production-profile simulation against bot backtest API"
    )
    parser.add_argument("--base-url", default="http://localhost:8889")
    parser.add_argument("--username", default=os.getenv("BOT_API_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("BOT_API_PASSWORD", ""))
    parser.add_argument("--start-date", default=start)
    parser.add_argument("--end-date", default=end)
    parser.add_argument("--max-pairs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument(
        "--skip-auth",
        action="store_true",
        default=bypass_auth_default,
        help="Skip login and call API without Bearer token (dev only)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    token: Optional[str] = None
    if args.skip_auth:
        print("Skipping auth (API_BYPASS_AUTH mode)")
    else:
        if not args.password:
            raise RuntimeError("BOT_API_PASSWORD or --password is required when auth is enabled")
        print("Logging in to bot API...")
        token = login(args.base_url, args.username, args.password)

    pair_universe = [
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "DOGE-USD",
        "AVAX-USD",
    ]
    pairs = pair_universe[: max(1, args.max_pairs)]

    baseline_cfg = {
        "name": "baseline-simulation",
        "description": "Baseline profile",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "initial_balance": 1000.0,
        "trading_parameters": {
            "zscore_threshold": 1.5,
            "usd_per_trade": 10.0,
            "stats_window": 21,
            "close_at_zscore_cross": True,
        },
        "pairs": pairs,
    }

    production_profile_cfg = {
        "name": "production-profile-simulation",
        "description": "Production-like profile",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "initial_balance": 1000.0,
        "trading_parameters": {
            "zscore_threshold": 1.5,
            "usd_per_trade": 10.0,
            "stats_window": 21,
            "close_at_zscore_cross": True,
            "transaction_fee": 0.0005,
            "slippage": 0.001,
            "risk_free_rate": 0.02,
            "max_drawdown_pct": 15.0,
            "max_positions": 5,
        },
        "pairs": pairs,
    }

    print("Creating baseline backtest...")
    baseline = create_backtest(args.base_url, token, baseline_cfg)
    print(f"Baseline run_id: {baseline.run_id}")

    print("Creating production-profile backtest...")
    production = create_backtest(args.base_url, token, production_profile_cfg)
    print(f"Production-profile run_id: {production.run_id}")

    baseline_status = wait_for_completion(
        args.base_url,
        token,
        baseline,
        timeout_seconds=args.timeout,
        poll_seconds=args.poll_seconds,
    )
    production_status = wait_for_completion(
        args.base_url,
        token,
        production,
        timeout_seconds=args.timeout,
        poll_seconds=args.poll_seconds,
    )

    if str(baseline_status.get("status", "")).lower() != "completed":
        raise RuntimeError(f"Baseline run did not complete successfully: {baseline_status}")
    if str(production_status.get("status", "")).lower() != "completed":
        raise RuntimeError(
            f"Production profile run did not complete successfully: {production_status}"
        )

    baseline_details = get_details(args.base_url, token, baseline.run_id)
    production_details = get_details(args.base_url, token, production.run_id)

    compare_runs(baseline_details, production_details)
    print("\nSimulation completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # keep explicit failure signal for CI
        print(f"ERROR: {exc}")
        raise SystemExit(1)
