#!/usr/bin/env python3
"""
Parameter sweep: grid-search over zscore_threshold × stats_window × usd_per_trade
and rank results by Sharpe ratio.

Usage:
    python scripts/parameter_sweep.py [--base-url URL] [--skip-auth]
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import product
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# HTTP helpers (no external deps)
# ---------------------------------------------------------------------------


def _request_json(
        url: str,
        method: str = "GET",
        data: Optional[dict] = None,
        token: Optional[str] = None,
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
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
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
    token = (body.get("data") or {}).get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token in response")
    return token


# ---------------------------------------------------------------------------
# Backtest helpers
# ---------------------------------------------------------------------------


@dataclass
class SweepResult:
    label: str
    params: Dict[str, Any]
    run_id: str
    sharpe_ratio: Optional[float] = None
    total_pnl: Optional[float] = None
    win_rate: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    total_trades: Optional[int] = None
    error: Optional[str] = None


def _metric(payload: dict, key: str) -> Any:
    if key in payload:
        return payload[key]
    return (payload.get("metrics") or {}).get(key)


def create_run(base_url: str, token: Optional[str], cfg: dict) -> str:
    status, body = _request_json(
        f"{base_url}/api/v1/backtests", method="POST", data=cfg, token=token
    )
    if status != 200:
        raise RuntimeError(f"Create failed ({status}): {body}")
    data = body.get("data", {})
    run_id = data.get("run_id") or data.get("id")
    if not run_id:
        raise RuntimeError(f"Missing run_id in response: {body}")
    return str(run_id)


def poll_until_done(
        base_url: str,
        token: Optional[str],
        run_id: str,
        label: str,
        timeout: int = 600,
        poll: int = 8,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, body = _request_json(f"{base_url}/api/v1/backtests/{run_id}/status", token=token)
        if status != 200:
            raise RuntimeError(f"Status check failed ({status}): {body}")
        data = body.get("data", {})
        state = str(data.get("status", "")).lower()
        pct = data.get("progress_pct", 0)
        print(f"  [{label}] {state} {pct:.0f}%")
        if state in {"completed", "failed", "cancelled"}:
            return data
        time.sleep(poll)
    raise TimeoutError(f"Timeout waiting for {run_id}")


def fetch_details(base_url: str, token: Optional[str], run_id: str) -> dict:
    status, body = _request_json(f"{base_url}/api/v1/backtests/{run_id}", token=token)
    if status != 200:
        raise RuntimeError(f"Details fetch failed ({status}): {body}")
    return body.get("data", {})


# ---------------------------------------------------------------------------
# Sweep grid
# ---------------------------------------------------------------------------

PARAM_GRID = {
    "zscore_threshold": [1.0, 1.25, 1.5, 1.75, 2.0],
    "stats_window": [14, 21, 30],
    "usd_per_trade": [10.0, 25.0],
}

BASE_PARAMS = {
    "close_at_zscore_cross": True,
    "transaction_fee": 0.0005,
    "slippage": 0.001,
    "risk_free_rate": 0.02,
    "max_positions": 5,
}

PAIR_UNIVERSE = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "AVAX-USD"]


def build_configs(start: str, end: str, max_pairs: int) -> List[Tuple[str, dict, dict]]:
    """Return list of (label, params, api_cfg) tuples."""
    pairs = PAIR_UNIVERSE[: max(1, max_pairs)]
    configs = []
    for z, w, u in product(
            PARAM_GRID["zscore_threshold"],
            PARAM_GRID["stats_window"],
            PARAM_GRID["usd_per_trade"],
    ):
        label = f"Z={z} W={w} U=${u}"
        params = {**BASE_PARAMS, "zscore_threshold": z, "stats_window": w, "usd_per_trade": u}
        cfg = {
            "name": f"sweep_z{z}_w{w}_u{u}",
            "description": label,
            "start_date": start,
            "end_date": end,
            "initial_balance": 1000.0,
            "trading_parameters": params,
            "pairs": pairs,
        }
        configs.append((label, params, cfg))
    return configs


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_table(results: List[SweepResult]) -> None:
    ok = [r for r in results if r.error is None]
    ok.sort(key=lambda r: (r.sharpe_ratio or -999), reverse=True)

    col_w = [32, 8, 8, 6, 10, 8]
    headers = ["Label", "Sharpe", "PnL", "WinR%", "Drawdown%", "Trades"]
    sep = "  ".join("-" * w for w in col_w)

    print("\n" + "=" * 80)
    print("  PARAMETER SWEEP RESULTS  (ranked by Sharpe ratio)")
    print("=" * 80)
    print("  ".join(h.ljust(w) for h, w in zip(headers, col_w)))
    print(sep)
    for r in ok:
        wr = f"{(r.win_rate or 0) * 100:.1f}" if r.win_rate is not None else "—"
        row = [
            r.label,
            f"{r.sharpe_ratio:.3f}" if r.sharpe_ratio is not None else "—",
            f"{r.total_pnl:.1f}" if r.total_pnl is not None else "—",
            wr,
            f"{r.max_drawdown_pct:.1f}" if r.max_drawdown_pct is not None else "—",
            str(r.total_trades or "—"),
        ]
        print("  ".join(str(v).ljust(w) for v, w in zip(row, col_w)))
    print(sep)

    if ok:
        best = ok[0]
        print(f"\n🏆  Best params: {best.label}")
        print(f"    zscore_threshold = {best.params['zscore_threshold']}")
        print(f"    stats_window     = {best.params['stats_window']}")
        print(f"    usd_per_trade    = {best.params['usd_per_trade']}")
        print(
            f"    Sharpe={best.sharpe_ratio:.3f}  PnL={best.total_pnl:.1f}"
            f"  Drawdown={best.max_drawdown_pct:.1f}%  Trades={best.total_trades}"
        )

    failed = [r for r in results if r.error]
    if failed:
        print(f"\n⚠️  {len(failed)} run(s) failed:")
        for r in failed:
            print(f"  [{r.label}] {r.error}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def default_dates() -> Tuple[str, str]:
    end = date.today() - timedelta(days=7)
    start = end - timedelta(days=30)
    return start.isoformat(), end.isoformat()


def parse_args() -> argparse.Namespace:
    start, end = default_dates()
    bypass = os.getenv("API_BYPASS_AUTH", "false").lower() == "true"
    p = argparse.ArgumentParser(description="Parameter sweep for dYdX bot strategy")
    p.add_argument("--base-url", default="http://localhost:8889")
    p.add_argument("--username", default=os.getenv("BOT_API_USERNAME", "admin"))
    p.add_argument("--password", default=os.getenv("BOT_API_PASSWORD", ""))
    p.add_argument("--start-date", default=start)
    p.add_argument("--end-date", default=end)
    p.add_argument("--max-pairs", type=int, default=3)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--poll-seconds", type=int, default=8)
    p.add_argument("--skip-auth", action="store_true", default=bypass)
    p.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="How many backtests to submit before starting to poll",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    token: Optional[str] = None
    if args.skip_auth:
        print("Auth skipped (API_BYPASS_AUTH mode)")
    else:
        if not args.password:
            raise RuntimeError("BOT_API_PASSWORD or --password is required when auth is enabled")
        print("Logging in...")
        token = login(args.base_url, args.username, args.password)

    configs = build_configs(args.start_date, args.end_date, args.max_pairs)
    total = len(configs)
    print(f"\nParameter grid: {total} combinations")
    print(f"  zscore_threshold : {PARAM_GRID['zscore_threshold']}")
    print(f"  stats_window     : {PARAM_GRID['stats_window']}")
    print(f"  usd_per_trade    : {PARAM_GRID['usd_per_trade']}")
    print(f"Date range : {args.start_date} → {args.end_date}")
    print(f"Pairs      : {PAIR_UNIVERSE[:args.max_pairs]}\n")

    results: List[SweepResult] = []

    # Submit in batches of --concurrency, then poll each batch
    batch_size = args.concurrency
    batches = [configs[i: i + batch_size] for i in range(0, total, batch_size)]

    for batch_idx, batch in enumerate(batches):
        print(f"--- Batch {batch_idx + 1}/{len(batches)} ({len(batch)} runs) ---")

        # Submit
        submitted: List[SweepResult] = []
        for label, params, cfg in batch:
            try:
                run_id = create_run(args.base_url, token, cfg)
                print(f"  ↑ submitted [{label}] → {run_id}")
                submitted.append(SweepResult(label=label, params=params, run_id=run_id))
            except Exception as exc:
                print(f"  ✗ submit failed [{label}]: {exc}")
                submitted.append(SweepResult(label=label, params=params, run_id="", error=str(exc)))

        # Poll
        for sr in submitted:
            if sr.error or not sr.run_id:
                results.append(sr)
                continue
            try:
                state = poll_until_done(
                    args.base_url,
                    token,
                    sr.run_id,
                    sr.label,
                    timeout=args.timeout,
                    poll=args.poll_seconds,
                )
                if str(state.get("status", "")).lower() != "completed":
                    sr.error = f"non-completed state: {state.get('status')}"
                    results.append(sr)
                    continue
                details = fetch_details(args.base_url, token, sr.run_id)
                sr.sharpe_ratio = _metric(details, "sharpe_ratio")
                sr.total_pnl = _metric(details, "total_pnl")
                sr.win_rate = _metric(details, "win_rate")
                sr.max_drawdown_pct = _metric(details, "max_drawdown_pct")
                sr.total_trades = _metric(details, "total_trades")
                results.append(sr)
                print(f"  ✓ [{sr.label}] Sharpe={sr.sharpe_ratio}  PnL={sr.total_pnl}")
            except Exception as exc:
                sr.error = str(exc)
                results.append(sr)
                print(f"  ✗ [{sr.label}] {exc}")

    print_table(results)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
