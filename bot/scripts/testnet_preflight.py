#!/usr/bin/env python3
"""Testnet preflight checks for dYdX bot readiness."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class CheckResult:
    level: str  # PASS, WARN, FAIL
    title: str
    detail: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_environment() -> None:
    env_path = _project_root() / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _http_probe(
    base_url: str, paths: List[str], timeout: int = 10
) -> tuple[bool, str]:
    for path in paths:
        url = f"{base_url.rstrip('/')}{path}"
        try:
            request = Request(
                url, headers={"User-Agent": "dydx-preflight/1.0"})
            with urlopen(request, timeout=timeout) as response:
                if 200 <= response.status < 500:
                    return True, (
                        f"reachable via {url} (HTTP {response.status})"
                    )
        except HTTPError as exc:
            if exc.code in (401, 403, 404):
                return True, f"reachable via {url} (HTTP {exc.code})"
        except URLError:
            continue
        except OSError:
            continue
    return False, f"no reachable probe path under {base_url}"


def _is_placeholder(value: str) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return (
        "your_" in lowered
        or value.startswith("${")
        or value.endswith("_here")
        or lowered in {"changeme", "todo", "none"}
    )


def run_preflight(simulate_production: bool, strict: bool) -> int:
    results: List[CheckResult] = []
    root = _project_root()

    env_path = root / ".env"
    if env_path.exists():
        results.append(CheckResult(
            "PASS", "Environment file", f"Found {env_path}"))
    else:
        results.append(CheckResult(
            "FAIL", "Environment file", f"Missing {env_path}"))

    is_testnet = os.getenv("IS_TESTNET", "true").lower() == "true"
    if is_testnet:
        results.append(CheckResult("PASS", "Network mode", "IS_TESTNET=true"))
    else:
        results.append(
            CheckResult(
                "FAIL",
                "Network mode",
                "IS_TESTNET must be true for testnet validation",
            )
        )

    place_trades = os.getenv("BOT_PLACE_TRADES", "false").lower() == "true"
    wallet_addr = os.getenv("DYDX_TESTNET_ADDRESS", "")
    mnemonic = os.getenv("DYDX_TESTNET_MNEMONIC", "")

    if _is_placeholder(wallet_addr):
        level = "WARN" if place_trades else "PASS"
        detail = (
            "Not set or still placeholder "
            "(required when BOT_PLACE_TRADES=true)"
            if not place_trades
            else "Not set or still placeholder"
        )
        results.append(CheckResult(level, "Testnet wallet address", detail))
    else:
        results.append(CheckResult(
            "PASS", "Testnet wallet address", "Configured"))

    if _is_placeholder(mnemonic):
        level = "WARN" if place_trades else "PASS"
        detail = (
            "Not set or still placeholder "
            "(required when BOT_PLACE_TRADES=true)"
            if not place_trades
            else "Not set or still placeholder"
        )
        results.append(CheckResult(level, "Testnet mnemonic", detail))
    else:
        results.append(CheckResult("PASS", "Testnet mnemonic", "Configured"))

    indexer_endpoint = os.getenv(
        "INDEXER_ENDPOINT",
        (
            "https://indexer.v4testnet.dydx.exchange"
            if is_testnet
            else "https://indexer.dydx.trade"
        ),
    )
    reachable, detail = _http_probe(
        indexer_endpoint,
        ["/v4/perpetualMarkets", "/v4/markets", "/"],
    )
    results.append(
        CheckResult("PASS" if reachable else "FAIL",
                    "Indexer endpoint connectivity", detail)
    )

    manage_exits = os.getenv("BOT_MANAGE_EXITS", "false").lower() == "true"
    if place_trades and not manage_exits:
        results.append(
            CheckResult(
                "WARN",
                "Trade safety flags",
                (
                    "BOT_PLACE_TRADES=true while BOT_MANAGE_EXITS=false; "
                    "consider enabling exit management"
                ),
            )
        )
    else:
        results.append(CheckResult("PASS", "Trade safety flags",
                       "Entry/exit flags look coherent"))

    abort_all_positions = os.getenv(
        "BOT_ABORT_ALL_POSITIONS", "false").lower() == "true"
    if abort_all_positions:
        results.append(
            CheckResult(
                "WARN",
                "Emergency kill-switch mode",
                (
                    "BOT_ABORT_ALL_POSITIONS=true "
                    "(bot will attempt emergency close on startup)"
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                "PASS",
                "Emergency kill-switch mode",
                "BOT_ABORT_ALL_POSITIONS=false",
            )
        )

    cb_failures = os.getenv("CIRCUIT_BREAKER_CONSECUTIVE_FAILURES", "")
    max_drawdown = os.getenv("MAX_DRAWDOWN_PCT", "")
    if not cb_failures and not max_drawdown:
        results.append(
            CheckResult(
                "WARN",
                "Circuit-breaker readiness",
                (
                    "No CIRCUIT_BREAKER_CONSECUTIVE_FAILURES "
                    "or MAX_DRAWDOWN_PCT set"
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                "PASS",
                "Circuit-breaker readiness",
                (
                    "CIRCUIT_BREAKER_CONSECUTIVE_FAILURES="
                    f"{cb_failures or 'unset'}, "
                    "MAX_DRAWDOWN_PCT="
                    f"{max_drawdown or 'unset'}"
                ),
            )
        )

    if simulate_production:
        fee = float(os.getenv("BACKTEST_TRANSACTION_FEE", "0.0005"))
        slippage = float(os.getenv("BACKTEST_SLIPPAGE", "0.001"))
        risk_free = float(os.getenv("BACKTEST_RISK_FREE_RATE", "0.02"))

        if fee <= 0 or fee > 0.01:
            results.append(
                CheckResult(
                    "WARN",
                    "Production simulation fee",
                    (
                        f"transactionFee={fee} looks unusual "
                        "(expected 0 < fee <= 0.01)"
                    ),
                )
            )
        else:
            results.append(CheckResult(
                "PASS", "Production simulation fee", f"transactionFee={fee}"))

        if slippage < 0 or slippage > 0.05:
            results.append(
                CheckResult(
                    "WARN",
                    "Production simulation slippage",
                    (
                        f"slippage={slippage} looks unusual "
                        "(expected 0 <= slippage <= 0.05)"
                    ),
                )
            )
        else:
            results.append(
                CheckResult(
                    "PASS",
                    "Production simulation slippage",
                    f"slippage={slippage}",
                )
            )

        if risk_free < 0 or risk_free > 0.2:
            results.append(
                CheckResult(
                    "WARN",
                    "Production simulation risk-free rate",
                    (
                        f"riskFreeRate={risk_free} looks unusual "
                        "(expected 0 <= riskFreeRate <= 0.2)"
                    ),
                )
            )
        else:
            results.append(
                CheckResult(
                    "PASS",
                    "Production simulation risk-free rate",
                    f"riskFreeRate={risk_free}",
                )
            )

    fail_count = sum(1 for result in results if result.level == "FAIL")
    warn_count = sum(1 for result in results if result.level == "WARN")

    print("\n=== dYdX Testnet Preflight ===")
    for result in results:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[result.level]
        print(f"{icon} [{result.level}] {result.title}: {result.detail}")

    print("\nSummary:")
    print(f"  FAIL: {fail_count}")
    print(f"  WARN: {warn_count}")

    if fail_count > 0:
        return 1
    if strict and warn_count > 0:
        return 2
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run testnet preflight and production-simulation checks")
    parser.add_argument(
        "--simulate-production",
        action="store_true",
        help="Include production-like simulation parameter checks",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures",
    )
    return parser.parse_args()


def main() -> int:
    _load_environment()
    args = parse_args()
    return run_preflight(
        simulate_production=args.simulate_production,
        strict=args.strict,
    )


if __name__ == "__main__":
    sys.exit(main())
