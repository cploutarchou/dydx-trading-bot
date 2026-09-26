"""Market-history fetching for backtests.

Extracted from :mod:`src.infrastructure.use_cases.service_backtest` (Phase 3 of the
backtest-service decomposition). Paged candle fetch from the dYdX indexer with retry
+ exponential backoff (honoring ``Retry-After``), per-window deadline awareness,
and per-market telemetry (attempts, retries, backoff, recent failures).

The fetcher was an instance method whose only ``self`` usage was calling sibling
pure helpers (env parsing, deadline arithmetic, ISO formatting, retry/backoff),
so it converts cleanly to a module-level async function. ``BacktestService`` keeps
thin delegating methods only for the helpers called from elsewhere in the service
(``_remaining_seconds``, ``_describe_exception``, ``_env_positive_int/_float``,
``_normalize_resolution``); the fetcher itself and its history-specific helpers live
entirely here. ``_attach_history_fetch_summary`` stays on the service because it
couples to the runtime-control/task-context codec (Phase 5 territory), and calls
``_history_fetch_summary`` here.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# History-fetch tuning. Overridable per-call via the env vars read in the helpers below.
_HISTORY_REQUEST_TIMEOUT_SECONDS = 20.0
_HISTORY_MIN_INTERVAL_SECONDS = 0.15
_HISTORY_MAX_RETRIES = 6
_HISTORY_RETRY_BASE_SECONDS = 1.5
_HISTORY_RETRY_MAX_SECONDS = 20.0
_HISTORY_TELEMETRY_RECENT_FAILURES_LIMIT = 5
# A close this many times above (or below) the median of its neighbours is a
# bad print, not a market move: thin books print trades far from the market
# for a single bar. Real moves persist, so they shift the median with them.
_BAD_PRINT_RATIO = 3.0
_BAD_PRINT_NEIGHBOURS = 5


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw in (None, ""):
        return max(1, int(default))
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return max(1, int(default))


def _env_positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw in (None, ""):
        return max(0.1, float(default))
    try:
        return max(0.1, float(raw))
    except (TypeError, ValueError):
        return max(0.1, float(default))


def _drop_bad_prints(history: Dict[str, float]) -> tuple[Dict[str, float], int]:
    """Drop single-bar prints far from their neighbours; return (clean, dropped).

    A close is a bad print when it is off by _BAD_PRINT_RATIO from the median
    of the bars before it AND from the median of the bars after it. A real
    step change agrees with one side, so it is kept.
    """

    def _median(values: list[float]) -> float:
        ordered = sorted(values)
        return ordered[len(ordered) // 2]

    def _far(price: float, reference: float) -> bool:
        return reference > 0 and (
            price > reference * _BAD_PRINT_RATIO or price < reference / _BAD_PRINT_RATIO
        )

    items = sorted(history.items(), key=lambda kv: kv[0])
    closes = [price for _, price in items]
    clean: Dict[str, float] = {}
    dropped = 0
    for index, (ts, price) in enumerate(items):
        if price <= 0:
            dropped += 1
            continue
        before = [
            p for p in closes[max(0, index - _BAD_PRINT_NEIGHBOURS) : index] if p > 0
        ]
        after = [
            p for p in closes[index + 1 : index + 1 + _BAD_PRINT_NEIGHBOURS] if p > 0
        ]
        sides = [_far(price, _median(side)) for side in (before, after) if side]
        if sides and all(sides):
            dropped += 1
            continue
        clean[ts] = price
    return clean, dropped


def _remaining_seconds(deadline_monotonic: float) -> float:
    return max(0.0, deadline_monotonic - time.monotonic())


def _describe_exception(exc: BaseException) -> str:
    text = str(exc).strip()
    if text:
        return text
    return repr(exc)


def _extract_retry_after_seconds(exc: BaseException) -> Optional[float]:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        parsed = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _normalize_resolution(resolution: str) -> str:
    raw = str(resolution or "1HOUR").strip().upper()
    mapping = {
        "M1": "1MIN",
        "1M": "1MIN",
        "1MIN": "1MIN",
        "1MINUTE": "1MIN",
        "1MINUTES": "1MIN",
        "M5": "5MINS",
        "5M": "5MINS",
        "5MIN": "5MINS",
        "5MINS": "5MINS",
        "5MINUTE": "5MINS",
        "5MINUTES": "5MINS",
        "M15": "15MINS",
        "15M": "15MINS",
        "15MIN": "15MINS",
        "15MINS": "15MINS",
        "15MINUTE": "15MINS",
        "15MINUTES": "15MINS",
        "M30": "30MINS",
        "30M": "30MINS",
        "30MIN": "30MINS",
        "30MINS": "30MINS",
        "30MINUTE": "30MINS",
        "30MINUTES": "30MINS",
        "H1": "1HOUR",
        "1H": "1HOUR",
        "1HR": "1HOUR",
        "1HOUR": "1HOUR",
        "1HOURS": "1HOUR",
        "H4": "4HOURS",
        "4H": "4HOURS",
        "4HR": "4HOURS",
        "4HOUR": "4HOURS",
        "4HOURS": "4HOURS",
        "D1": "1DAY",
        "1D": "1DAY",
        "1DAY": "1DAY",
        "1DAYS": "1DAY",
    }
    return mapping.get(raw, "1HOUR")


def _resolution_to_minutes(resolution: str) -> int:
    raw = _normalize_resolution(resolution)
    mapping = {
        "1MIN": 1,
        "5MINS": 5,
        "15MINS": 15,
        "30MINS": 30,
        "1HOUR": 60,
        "4HOURS": 240,
        "1DAY": 1440,
    }
    if raw in mapping:
        return mapping[raw]
    return 60


def _to_iso(dt: datetime) -> str:
    utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return utc.isoformat().replace("+00:00", "Z")


def _history_retry_delay_seconds(
    attempt_index: int,
    exc: BaseException,
) -> float:
    retry_after = _extract_retry_after_seconds(exc)
    if retry_after is not None:
        base_delay = retry_after
    else:
        configured_base = _env_positive_float(
            "BACKTEST_HISTORY_RETRY_BASE_SECONDS",
            _HISTORY_RETRY_BASE_SECONDS,
        )
        max_delay = _env_positive_float(
            "BACKTEST_HISTORY_RETRY_MAX_SECONDS",
            _HISTORY_RETRY_MAX_SECONDS,
        )
        base_delay = min(max_delay, configured_base * (2**attempt_index))

    jitter = random.uniform(0.0, max(0.1, base_delay * 0.25))
    return base_delay + jitter


def _history_fetch_summary(
    history_telemetry: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    markets_summary: Dict[str, Any] = {}
    total_windows = 0
    total_retries = 0
    total_attempts = 0
    total_backoff_seconds = 0.0
    total_failed_windows = 0
    total_bad_prints = 0

    for market, metrics in sorted(history_telemetry.items()):
        windows = int(metrics.get("windows") or 0)
        retries = int(metrics.get("retries") or 0)
        attempts = int(metrics.get("attempts") or 0)
        failed_windows = int(metrics.get("failed_windows") or 0)
        backoff_seconds = float(metrics.get("backoff_seconds") or 0.0)
        timeout_errors = int(metrics.get("timeout_errors") or 0)
        http_errors = int(metrics.get("http_errors") or 0)
        max_attempts_per_window = int(metrics.get("max_attempts_per_window") or 0)
        bad_prints = int(metrics.get("bad_prints_dropped") or 0)
        total_bad_prints += bad_prints

        total_windows += windows
        total_retries += retries
        total_attempts += attempts
        total_backoff_seconds += backoff_seconds
        total_failed_windows += failed_windows

        markets_summary[market] = {
            "windows": windows,
            "attempts": attempts,
            "retries": retries,
            "failed_windows": failed_windows,
            "timeout_errors": timeout_errors,
            "http_errors": http_errors,
            "backoff_seconds": round(backoff_seconds, 3),
            "avg_backoff_per_retry_seconds": (
                round(
                    backoff_seconds / retries,
                    3,
                )
                if retries > 0
                else 0.0
            ),
            "avg_attempts_per_window": (
                round(attempts / windows, 3) if windows > 0 else 0.0
            ),
            "max_attempts_per_window": max_attempts_per_window,
            "bad_prints_dropped": bad_prints,
            "recent_failures": list(metrics.get("recent_failures") or []),
        }

    return {
        "version": 1,
        "markets_count": len(markets_summary),
        "total_windows": total_windows,
        "total_attempts": total_attempts,
        "total_retries": total_retries,
        "total_failed_windows": total_failed_windows,
        "total_backoff_seconds": round(total_backoff_seconds, 3),
        "total_bad_prints_dropped": total_bad_prints,
        "avg_backoff_per_retry_seconds": (
            round(
                total_backoff_seconds / total_retries,
                3,
            )
            if total_retries > 0
            else 0.0
        ),
        "markets": markets_summary,
    }


async def _fetch_market_history(
    client: Any,
    market: str,
    start_dt: datetime,
    end_dt: datetime,
    resolution: str,
    deadline_monotonic: Optional[float] = None,
    history_telemetry: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, float]:
    step_minutes = _resolution_to_minutes(resolution)
    max_candles = 100
    chunk = timedelta(minutes=step_minutes * 90)
    cursor = start_dt
    merged: Dict[str, float] = {}
    last_request_started = 0.0

    while cursor < end_dt:
        if (
            deadline_monotonic is not None
            and _remaining_seconds(deadline_monotonic) <= 0
        ):
            raise TimeoutError(f"Backtest timed out while loading history for {market}")

        window_end = min(end_dt, cursor + chunk)
        request_timeout = _env_positive_float(
            "BACKTEST_HISTORY_REQUEST_TIMEOUT_SECONDS",
            _HISTORY_REQUEST_TIMEOUT_SECONDS,
        )
        if deadline_monotonic is not None:
            request_timeout = min(
                request_timeout,
                max(0.001, _remaining_seconds(deadline_monotonic)),
            )
        min_interval_seconds = _env_positive_float(
            "BACKTEST_HISTORY_MIN_INTERVAL_SECONDS",
            _HISTORY_MIN_INTERVAL_SECONDS,
        )
        max_retries = _env_positive_int(
            "BACKTEST_HISTORY_MAX_RETRIES",
            _HISTORY_MAX_RETRIES,
        )

        response: Dict[str, Any] | None = None
        last_error: Optional[BaseException] = None
        window_retries = 0
        window_attempts = 0
        window_backoff_seconds = 0.0
        for attempt in range(max_retries):
            window_attempts += 1
            if min_interval_seconds > 0 and last_request_started > 0:
                since_last_request = time.monotonic() - last_request_started
                pace_wait = max(0.0, min_interval_seconds - since_last_request)
                if pace_wait > 0:
                    if deadline_monotonic is not None:
                        pace_wait = min(
                            pace_wait,
                            max(0.0, _remaining_seconds(deadline_monotonic)),
                        )
                    if pace_wait > 0:
                        await asyncio.sleep(pace_wait)

            last_request_started = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    client.indexer.markets.get_perpetual_market_candles(
                        market=market,
                        resolution=resolution,
                        from_iso=_to_iso(cursor),
                        to_iso=_to_iso(window_end),
                        limit=max_candles,
                    ),
                    timeout=request_timeout,
                )
                break
            except (asyncio.TimeoutError, httpx.HTTPError) as exc:
                last_error = exc
                if attempt >= max_retries - 1:
                    break

                wait = _history_retry_delay_seconds(attempt, exc)
                if deadline_monotonic is not None:
                    wait = min(
                        wait,
                        max(0.0, _remaining_seconds(deadline_monotonic)),
                    )

                logger.warning(
                    "Candle fetch transient failure for %s window %s→%s "
                    "(attempt %d/%d), retrying in %.2fs: %s",
                    market,
                    _to_iso(cursor),
                    _to_iso(window_end),
                    attempt + 1,
                    max_retries,
                    wait,
                    _describe_exception(exc),
                )

                window_retries += 1
                window_backoff_seconds += max(0.0, wait)
                if wait > 0:
                    await asyncio.sleep(wait)

        if history_telemetry is not None:
            market_telemetry = history_telemetry.setdefault(
                market,
                {
                    "windows": 0,
                    "attempts": 0,
                    "retries": 0,
                    "failed_windows": 0,
                    "timeout_errors": 0,
                    "http_errors": 0,
                    "backoff_seconds": 0.0,
                    "max_attempts_per_window": 0,
                    "recent_failures": [],
                },
            )
            market_telemetry["attempts"] = int(
                market_telemetry.get("attempts") or 0
            ) + int(window_attempts)
            market_telemetry["retries"] = int(
                market_telemetry.get("retries") or 0
            ) + int(window_retries)
            market_telemetry["backoff_seconds"] = float(
                market_telemetry.get("backoff_seconds") or 0.0
            ) + float(window_backoff_seconds)
            market_telemetry["max_attempts_per_window"] = max(
                int(market_telemetry.get("max_attempts_per_window") or 0),
                int(window_attempts),
            )

        if response is None:
            if history_telemetry is not None:
                failed_telemetry = history_telemetry.get(market)
                if failed_telemetry is not None:
                    failed_telemetry["failed_windows"] = (
                        int(failed_telemetry.get("failed_windows") or 0) + 1
                    )
                    if isinstance(last_error, asyncio.TimeoutError):
                        market_telemetry["timeout_errors"] = (
                            int(market_telemetry.get("timeout_errors") or 0) + 1
                        )
                    elif isinstance(last_error, httpx.HTTPError):
                        market_telemetry["http_errors"] = (
                            int(market_telemetry.get("http_errors") or 0) + 1
                        )

                    failures = list(market_telemetry.get("recent_failures") or [])
                    failures.append(
                        {
                            "window_from": _to_iso(cursor),
                            "window_to": _to_iso(window_end),
                            "error": (
                                _describe_exception(last_error)
                                if last_error is not None
                                else "unknown transport failure"
                            ),
                        }
                    )
                    limit = _env_positive_int(
                        "BACKTEST_HISTORY_TELEMETRY_RECENT_FAILURES_LIMIT",
                        _HISTORY_TELEMETRY_RECENT_FAILURES_LIMIT,
                    )
                    market_telemetry["recent_failures"] = failures[-limit:]

            error_summary = (
                _describe_exception(last_error)
                if last_error is not None
                else "unknown transport failure"
            )
            raise TimeoutError(
                f"Candle fetch failed for {market} after {max_retries} attempts "
                f"for {_to_iso(cursor)} to {_to_iso(window_end)}: {error_summary}"
            ) from last_error

        if history_telemetry is not None:
            windows_telemetry = history_telemetry.get(market)
            if windows_telemetry is not None:
                windows_telemetry["windows"] = (
                    int(windows_telemetry.get("windows") or 0) + 1
                )

        if not isinstance(response, dict):
            response = {}

        for candle in response.get("candles", []):
            ts = candle.get("startedAt")
            close = candle.get("close")
            if ts is None or close is None:
                continue
            try:
                merged[str(ts)] = float(close)
            except (TypeError, ValueError):
                continue

        next_cursor = window_end + timedelta(minutes=step_minutes)
        if next_cursor <= cursor:
            raise RuntimeError(f"Backtest history cursor stalled for {market}")
        cursor = next_cursor

    clean, dropped = _drop_bad_prints(merged)
    if history_telemetry is not None and dropped:
        market_telemetry = history_telemetry.setdefault(market, {})
        market_telemetry["bad_prints_dropped"] = (
            int(market_telemetry.get("bad_prints_dropped") or 0) + dropped
        )
    return clean
