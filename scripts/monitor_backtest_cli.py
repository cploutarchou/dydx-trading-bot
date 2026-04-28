#!/usr/bin/env python3
"""Launch and monitor a backtest through the HTTP API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timeout", "stale"}


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
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
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def parse_markets(raw: str) -> list[str]:
    markets = [item.strip() for item in raw.split(",") if item.strip()]
    seen: set[str] = set()
    unique: list[str] = []
    for market in markets:
        if market in seen:
            continue
        seen.add(market)
        unique.append(market)
    return unique


def format_float(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "0.00"


def get_run_id(payload: dict[str, Any]) -> str:
    data = unwrap(payload)
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError(f"launch response did not include run_id: {json.dumps(payload)[:500]}")
    return run_id


def fetch_market_sample(base_url: str, token: str | None, limit: int) -> list[str]:
    query = urlencode({"limit": max(2, limit)})
    payload = request_json("GET", f"{base_url}/api/v1/markets/perpetuals?{query}", token=token)
    data = unwrap(payload)
    markets = data.get("markets")
    if not isinstance(markets, list):
        return []
    return [str(market) for market in markets if str(market).strip()]


def print_status(run_id: str, status_payload: dict[str, Any]) -> str:
    data = unwrap(status_payload)
    status = str(data.get("status") or "unknown").lower()
    progress = data.get("progress_pct", data.get("progress", 0))
    current = data.get("current_pair") or data.get("current_task") or "-"
    trades = data.get("total_trades", 0)
    pnl = data.get("total_pnl", data.get("total_pnl_usd", 0))
    sharpe = data.get("sharpe_ratio", 0)
    updated = data.get("updated_at") or "-"
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(
        f"{now} run={run_id} status={status} progress={format_float(progress)}% "
        f"current={current} trades={trades} pnl={format_float(pnl)} "
        f"sharpe={format_float(sharpe)} updated={updated}",
        flush=True,
    )
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch and monitor a backtest")
    parser.add_argument("--base-url", default=os.getenv("BACKEND_URL", "http://localhost:8888"))
    parser.add_argument("--token", default=os.getenv("AUTH_TOKEN") or os.getenv("BACKEND_TOKEN"))
    parser.add_argument("--name", default="cli-status-smoke")
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2024-01-07")
    parser.add_argument("--markets", default="")
    parser.add_argument("--market-limit", type=int, default=3)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--resolution", default="1HOUR")
    parser.add_argument("--zscore-threshold", type=float, default=1.5)
    parser.add_argument("--stats-window", type=int, default=21)
    parser.add_argument("--usd-per-trade", type=float, default=10.0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    markets = parse_markets(args.markets)
    if not markets:
        markets = fetch_market_sample(base_url, args.token, args.market_limit)

    if len(markets) < 2:
        raise RuntimeError("provide at least two markets with --markets or use a reachable market endpoint")
    if len(markets) > 5:
        raise RuntimeError("use 2-5 markets for this CLI smoke test")

    payload = {
        "name": args.name,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "initial_balance": 1000,
        "max_pairs": len(markets),
        "pair_selection_mode": "input",
        "pairs": markets,
        "timeout_seconds": args.timeout_seconds,
        "trading_parameters": {
            "resolution": args.resolution,
            "zscore_threshold": args.zscore_threshold,
            "stats_window": args.stats_window,
            "usd_per_trade": args.usd_per_trade,
            "max_history_days": 45,
            "pair_selection_mode": "input",
        },
    }

    print(f"Launching backtest against {base_url} with markets={','.join(markets)}", flush=True)
    launch = request_json("POST", f"{base_url}/api/v1/backtests/run", token=args.token, payload=payload)
    run_id = get_run_id(launch)
    print(f"launched run_id={run_id}", flush=True)

    deadline = time.monotonic() + args.timeout_seconds + 30
    while True:
        status_payload = request_json("GET", f"{base_url}/api/v1/backtests/{run_id}/status", token=args.token)
        status = print_status(run_id, status_payload)
        if status in TERMINAL_STATUSES:
            details = request_json("GET", f"{base_url}/api/v1/backtests/{run_id}", token=args.token)
            print("final_details=" + json.dumps(unwrap(details), sort_keys=True)[:2000], flush=True)
            return 0 if status == "completed" else 2
        if time.monotonic() > deadline:
            raise RuntimeError(f"monitor timed out waiting for terminal status; last status={status}")
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
