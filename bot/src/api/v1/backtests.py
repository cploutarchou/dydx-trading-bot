"""Backtest HTTP/WebSocket routes and their request-scoped support layer."""

from __future__ import annotations

import asyncio
import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, List, Mapping, Optional, Union

from fastapi import APIRouter, Depends, Query, Request, WebSocket
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from internal.domain.models import BacktestRun
from src.api.endpoint_timing import (
    endpoint_perf_headers as _endpoint_perf_headers,
    log_endpoint_timing as _log_endpoint_timing,
)
from src.api.responses import api_response
from src.api.v1.strategies import InMemoryStrategyStore
from src.api.websocket_server import WebSocketServer, manager
from src.infrastructure.database import db
from src.infrastructure.db_offload import run_db
from src.infrastructure.domain.models.auth_models import User
from src.infrastructure.domain.models_backtest import (
    BacktestConfigRequest,
    BacktestDetailResponse,
    BacktestListResponse,
    BacktestResponse,
)
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.use_cases.service_backtest import BacktestService
from src.middleware.auth_middleware import get_admin_user, get_current_active_user
from src.shared.time_utils import utc_now_iso
from src.shared.trading_validators import (
    ISO_DATE_PATTERN,
    normalize_market_list,
    validate_iso_date_range,
)
from src.trading.dydx_client import connect_dydx

CompatibilityNamespaceProvider = Callable[[], Mapping[str, Any]]
BacktestRateLimitProvider = Callable[[Request], None]
WebSocketAuthorizer = Callable[[WebSocket], Any]


def _unconfigured_rate_limit(_request: Request) -> None:
    raise RuntimeError("Backtest route rate limiter is not configured")


async def _unconfigured_websocket_authorizer(websocket: WebSocket) -> bool:
    await websocket.close(code=1011, reason="Backtest websocket auth unavailable")
    return False


_compatibility_namespace_provider: CompatibilityNamespaceProvider = globals
_backtest_rate_limit_provider: BacktestRateLimitProvider = _unconfigured_rate_limit
_websocket_authorizer: WebSocketAuthorizer = _unconfigured_websocket_authorizer


def configure_backtest_routes(
    *,
    compatibility_namespace_provider: CompatibilityNamespaceProvider,
    backtest_rate_limit_provider: BacktestRateLimitProvider,
    websocket_authorizer: WebSocketAuthorizer,
) -> None:
    """Connect the router to canonical server-owned compatibility dependencies."""

    global _compatibility_namespace_provider
    global _backtest_rate_limit_provider
    global _websocket_authorizer

    _compatibility_namespace_provider = compatibility_namespace_provider
    _backtest_rate_limit_provider = backtest_rate_limit_provider
    _websocket_authorizer = websocket_authorizer


def _compat(name: str, default: Any) -> Any:
    """Resolve monkeypatch-compatible server re-exports without a circular import."""
    return _compatibility_namespace_provider().get(name, default)


def _check_backtest_rate_limit(request: Request) -> None:
    return _backtest_rate_limit_provider(request)


async def _authorize_websocket_connection(websocket: WebSocket) -> bool:
    return bool(await _websocket_authorizer(websocket))


def _read_non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return max(0, int(default))
    try:
        return max(0, int(raw))
    except ValueError:
        return max(0, int(default))


def _read_non_negative_float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return max(0.0, float(default))
    try:
        return max(0.0, float(raw))
    except ValueError:
        return max(0.0, float(default))


MARKET_RESOLUTION_TIMEOUT_SECONDS = 10.0
_BACKTEST_ENDPOINT_CACHE_TTL_SECONDS = _read_non_negative_int_env(
    "BACKTEST_ENDPOINT_CACHE_TTL_SECONDS", 2
)
_BACKTEST_ENDPOINT_CACHE_MAX_ENTRIES = max(
    50,
    _read_non_negative_int_env("BACKTEST_ENDPOINT_CACHE_MAX_ENTRIES", 512),
)
_backtest_endpoint_cache: Dict[str, Dict[str, Any]] = {}
_backtest_endpoint_cache_lock = threading.Lock()
_strategy_resolution_metrics_lock = threading.Lock()
_strategy_resolution_path_keys = ("store", "history", "request", "not_found")
_strategy_resolution_metrics: Dict[str, Any] = {
    "counts": {key: 0 for key in _strategy_resolution_path_keys},
    "last_path": None,
    "last_updated_at": None,
}
_strategy_resolution_recent_paths: deque[str] = deque(
    maxlen=max(
        1,
        _read_non_negative_int_env("STRATEGY_RESOLUTION_ALERT_WINDOW_SIZE", 200),
    )
)


router = APIRouter()


def _cache_get(key: str) -> Optional[Any]:
    if _BACKTEST_ENDPOINT_CACHE_TTL_SECONDS <= 0:
        return None
    now = time.monotonic()
    with _backtest_endpoint_cache_lock:
        entry = _backtest_endpoint_cache.get(key)
        if not entry:
            return None
        if float(entry.get("expires_at", 0.0)) <= now:
            _backtest_endpoint_cache.pop(key, None)
            return None
        return entry.get("value")


def _cache_set(key: str, value: Any) -> None:
    if _BACKTEST_ENDPOINT_CACHE_TTL_SECONDS <= 0:
        return
    now = time.monotonic()
    expires_at = now + float(_BACKTEST_ENDPOINT_CACHE_TTL_SECONDS)
    with _backtest_endpoint_cache_lock:
        _backtest_endpoint_cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "updated_at": now,
        }

        if len(_backtest_endpoint_cache) <= _BACKTEST_ENDPOINT_CACHE_MAX_ENTRIES:
            return

        expired_keys = [
            cached_key
            for cached_key, cached_entry in _backtest_endpoint_cache.items()
            if float(cached_entry.get("expires_at", 0.0)) <= now
        ]
        for expired_key in expired_keys:
            _backtest_endpoint_cache.pop(expired_key, None)

        overflow = len(_backtest_endpoint_cache) - _BACKTEST_ENDPOINT_CACHE_MAX_ENTRIES
        if overflow <= 0:
            return

        oldest_keys = sorted(
            _backtest_endpoint_cache.items(),
            key=lambda item: float(item[1].get("updated_at", 0.0)),
        )
        for cached_key, _ in oldest_keys[:overflow]:
            _backtest_endpoint_cache.pop(cached_key, None)


def _build_backtest_analytics_summary(
    run_id: str, analytics: Dict[str, Any]
) -> Dict[str, Any]:
    trades = analytics.get("trades") if isinstance(analytics, dict) else None
    daily_pnl = analytics.get("daily_pnl") if isinstance(analytics, dict) else None
    position_snapshots = (
        analytics.get("position_snapshots") if isinstance(analytics, dict) else None
    )

    total_trades = int(analytics.get("total_trades", 0) or 0)
    if isinstance(trades, list) and total_trades <= 0:
        total_trades = len(trades)

    return {
        "run_id": run_id,
        "status": analytics.get("status"),
        "total_trades": total_trades,
        "winning_trades": int(analytics.get("winning_trades", 0) or 0),
        "losing_trades": int(analytics.get("losing_trades", 0) or 0),
        "win_rate": float(analytics.get("win_rate", 0.0) or 0.0),
        "total_pnl": float(analytics.get("total_pnl", 0.0) or 0.0),
        "total_pnl_usd": float(analytics.get("total_pnl_usd", 0.0) or 0.0),
        "sharpe_ratio": float(analytics.get("sharpe_ratio", 0.0) or 0.0),
        "max_drawdown": float(analytics.get("max_drawdown", 0.0) or 0.0),
        "profit_factor": float(analytics.get("profit_factor", 0.0) or 0.0),
        "daily_pnl_points": len(daily_pnl) if isinstance(daily_pnl, list) else 0,
        "position_snapshots_points": (
            len(position_snapshots) if isinstance(position_snapshots, list) else 0
        ),
        "updated_at": analytics.get("updated_at") or utc_now_iso(),
    }


class BacktestRunRequestCompat(BaseModel):
    """Frontend-compatible backtest run request."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "strategy_id": 1,
                "name": "Q1 ranked opportunities",
                "max_pairs": 10,
                "pair_selection_mode": "cointegration",
                "pairs": ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD"],
                "trading_parameters": {
                    "zscore_threshold": 1.5,
                    "stats_window": 21,
                    "usd_per_trade": 10.0,
                    "pair_selection_mode": "cointegration",
                },
            }
        }
    )

    start_date: str = Field(..., pattern=ISO_DATE_PATTERN)
    end_date: str = Field(..., pattern=ISO_DATE_PATTERN)
    strategy_id: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    initial_balance: float = Field(default=1000.0, gt=0.0)
    timeout_seconds: Optional[float] = Field(default=None, gt=0.0)
    # 0 means "all available markets" (no cap)
    max_pairs: int = Field(default=0, ge=0, le=1000)
    pair_selection_mode: Optional[str] = Field(default=None, max_length=64)
    trading_parameters: Optional[Dict[str, Any]] = None
    pairs: Optional[List[str]] = None
    selected_pairs: Optional[List[str]] = None
    strategy_payload_snapshot: Optional[Dict[str, Any]] = None
    bot_id: Optional[str] = Field(default=None, max_length=128)
    source: Optional[str] = Field(default=None, max_length=64)
    environment: Optional[str] = Field(default=None, max_length=32)
    requested_by_user_id: Optional[int] = Field(default=None, ge=1)
    source_strategy_version: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("pairs", "selected_pairs", mode="before")
    @classmethod
    def _normalize_pair_lists(cls, value: Any) -> Any:
        if value is None:
            return None
        return normalize_market_list(value)

    @model_validator(mode="after")
    def _validate_date_range(self) -> "BacktestRunRequestCompat":
        validate_iso_date_range(self.start_date, self.end_date)
        return self


def _normalize_string_list(values: Optional[List[str]]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = str(value or "").strip().upper()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _markets_from_selected_pair_labels(
    selected_pairs: Optional[List[str]],
) -> List[str]:
    markets: List[str] = []
    seen: set[str] = set()
    for pair_label in _normalize_string_list(selected_pairs):
        parts = [
            segment.strip().upper()
            for segment in pair_label.split("/")
            if segment.strip()
        ]
        candidates = parts if len(parts) >= 2 else [pair_label]
        for market in candidates:
            if market in seen:
                continue
            seen.add(market)
            markets.append(market)
    return markets


def _build_selected_pair_labels(markets: List[str]) -> List[str]:
    labels: List[str] = []
    for idx, left in enumerate(markets):
        for right in markets[idx + 1 :]:
            labels.append(f"{left}/{right}")
    return labels


class BacktestCreateStrategyRequest(BaseModel):
    """Create a strategy from an existing backtest."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    config: Dict[str, Any] = Field(default_factory=dict)


class BacktestMetadataRequest(BaseModel):
    """Attach or merge structured metadata into a persisted backtest run."""

    metadata: Dict[str, Any]
    merge: bool = True


class BacktestComparisonRequest(BaseModel):
    """Compare multiple backtest runs with advanced analytics."""

    run_ids: List[str] = Field(..., min_length=2)
    metrics: Optional[List[str]] = None

    @field_validator("run_ids", mode="before")
    @classmethod
    def _normalize_run_ids(cls, value: Any) -> Any:
        if value is None:
            return value
        return normalize_market_list(value)


def _normalize_requested_pair_cap(raw_cap: Any) -> Optional[int]:
    """Normalize max_pairs semantics.

    Returns:
      - None: no cap (scan all resolved markets)
      - int > 0: cap number of markets considered before pair-combination
    """
    try:
        cap = int(raw_cap)
    except (TypeError, ValueError):
        return None
    return cap if cap > 0 else None


def _read_positive_int_env(name: str, default: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return max(0, int(default))
    try:
        parsed = int(raw)
    except ValueError:
        logger.warning("Invalid {}='{}'; using default {}", name, raw, default)
        return max(0, int(default))
    return max(0, parsed)


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _request_snapshot_fallback_enabled() -> bool:
    """Whether strategy_payload_snapshot request fallback is allowed.

    Strict mode is opt-in: when
    BACKTEST_DISABLE_REQUEST_SNAPSHOT_FALLBACK_IN_PRODUCTION=true and
    ENVIRONMENT=production, fallback to request snapshot is disabled.
    """
    strict_disable_in_prod = _read_bool_env(
        "BACKTEST_DISABLE_REQUEST_SNAPSHOT_FALLBACK_IN_PRODUCTION",
        False,
    )
    is_production = os.getenv("ENVIRONMENT", "development").strip().lower() in {
        "production",
        "prod",
    }
    return not (strict_disable_in_prod and is_production)


def _record_strategy_resolution_path(path: str) -> None:
    with _strategy_resolution_metrics_lock:
        counts = _strategy_resolution_metrics.setdefault("counts", {})
        counts[path] = int(counts.get(path, 0) or 0) + 1
        _strategy_resolution_recent_paths.append(path)
        _strategy_resolution_metrics["last_path"] = path
        _strategy_resolution_metrics["last_updated_at"] = utc_now_iso()


def _strategy_resolution_metrics_snapshot() -> Dict[str, Any]:
    with _strategy_resolution_metrics_lock:
        counts = dict(_strategy_resolution_metrics.get("counts", {}))
        recent_paths = list(_strategy_resolution_recent_paths)
        recent_total = len(recent_paths)
        recent_counts: Dict[str, int] = {
            key: 0 for key in _strategy_resolution_path_keys
        }
        for path in recent_paths:
            recent_counts[path] = int(recent_counts.get(path, 0) or 0) + 1

        request_ratio_recent = (
            float(recent_counts.get("request", 0)) / float(recent_total)
            if recent_total > 0
            else 0.0
        )
        request_ratio_alert_threshold = _read_non_negative_float_env(
            "STRATEGY_RESOLUTION_REQUEST_RATIO_ALERT_THRESHOLD",
            0.05,
        )
        request_ratio_alert_min_runs = max(
            1,
            _read_non_negative_int_env(
                "STRATEGY_RESOLUTION_REQUEST_RATIO_ALERT_MIN_RUNS",
                20,
            ),
        )
        request_ratio_alert_triggered = (
            recent_total >= request_ratio_alert_min_runs
            and request_ratio_recent > request_ratio_alert_threshold
        )

        return {
            "counts": counts,
            "total": int(sum(int(v or 0) for v in counts.values())),
            "last_path": _strategy_resolution_metrics.get("last_path"),
            "last_updated_at": _strategy_resolution_metrics.get("last_updated_at"),
            "window": {
                "size": int(_strategy_resolution_recent_paths.maxlen or recent_total),
                "total": recent_total,
                "counts": recent_counts,
            },
            "alerts": {
                "request_ratio_recent": request_ratio_recent,
                "request_ratio_alert_threshold": request_ratio_alert_threshold,
                "request_ratio_alert_min_runs": request_ratio_alert_min_runs,
                "request_ratio_alert_triggered": request_ratio_alert_triggered,
            },
            "request_snapshot_fallback_enabled": _request_snapshot_fallback_enabled(),
            "strict_disable_in_production": _read_bool_env(
                "BACKTEST_DISABLE_REQUEST_SNAPSHOT_FALLBACK_IN_PRODUCTION",
                False,
            ),
        }


def _reset_strategy_resolution_metrics() -> Dict[str, Any]:
    with _strategy_resolution_metrics_lock:
        _strategy_resolution_metrics["counts"] = {
            key: 0 for key in _strategy_resolution_path_keys
        }
        _strategy_resolution_metrics["last_path"] = None
        _strategy_resolution_metrics["last_updated_at"] = utc_now_iso()
        _strategy_resolution_recent_paths.clear()
    return _strategy_resolution_metrics_snapshot()


def _strategy_resolution_metrics_prometheus() -> str:
    snapshot = _strategy_resolution_metrics_snapshot()
    counts = dict(snapshot.get("counts", {}))
    window = dict(snapshot.get("window", {}))
    window_counts = dict(window.get("counts", {}))
    alerts = dict(snapshot.get("alerts", {}))

    lines: List[str] = []
    lines.append(
        "# HELP bot_strategy_resolution_total Total strategy-resolution decisions by path"
    )
    lines.append("# TYPE bot_strategy_resolution_total counter")
    for path in _strategy_resolution_path_keys:
        lines.append(
            f'bot_strategy_resolution_total{{path="{path}"}} {int(counts.get(path, 0) or 0)}'
        )

    lines.append(
        "# HELP bot_strategy_resolution_window_total Strategy-resolution decisions in the recent alert window"
    )
    lines.append("# TYPE bot_strategy_resolution_window_total gauge")
    lines.append(
        f"bot_strategy_resolution_window_total {int(window.get('total', 0) or 0)}"
    )

    lines.append(
        "# HELP bot_strategy_resolution_window_ratio Ratio per path in the recent alert window"
    )
    lines.append("# TYPE bot_strategy_resolution_window_ratio gauge")
    window_total = int(window.get("total", 0) or 0)
    for path in _strategy_resolution_path_keys:
        ratio = (
            float(window_counts.get(path, 0) or 0) / float(window_total)
            if window_total > 0
            else 0.0
        )
        lines.append(
            f'bot_strategy_resolution_window_ratio{{path="{path}"}} {ratio:.6f}'
        )

    lines.append(
        "# HELP bot_strategy_resolution_request_ratio_recent Request-fallback ratio in recent window"
    )
    lines.append("# TYPE bot_strategy_resolution_request_ratio_recent gauge")
    lines.append(
        f"bot_strategy_resolution_request_ratio_recent {float(alerts.get('request_ratio_recent', 0.0) or 0.0):.6f}"
    )

    lines.append(
        "# HELP bot_strategy_resolution_request_ratio_alert_triggered Whether request-fallback ratio alert is triggered"
    )
    lines.append("# TYPE bot_strategy_resolution_request_ratio_alert_triggered gauge")
    lines.append(
        "bot_strategy_resolution_request_ratio_alert_triggered {}".format(
            1 if bool(alerts.get("request_ratio_alert_triggered", False)) else 0
        )
    )

    alert_triggered = bool(alerts.get("request_ratio_alert_triggered", False))
    alert_reason = "request_ratio_exceeded" if alert_triggered else "none"
    alert_severity = "warning" if alert_triggered else "ok"
    lines.append(
        "# HELP bot_strategy_resolution_alert_summary Single-line summary for strategy-resolution alert state"
    )
    lines.append("# TYPE bot_strategy_resolution_alert_summary gauge")
    lines.append(
        'bot_strategy_resolution_alert_summary{alert="request_ratio",severity="%s",reason="%s"} %d'
        % (alert_severity, alert_reason, 1 if alert_triggered else 0)
    )

    lines.append(
        "# HELP bot_strategy_resolution_request_snapshot_fallback_enabled Whether request snapshot fallback is enabled"
    )
    lines.append(
        "# TYPE bot_strategy_resolution_request_snapshot_fallback_enabled gauge"
    )
    lines.append(
        "bot_strategy_resolution_request_snapshot_fallback_enabled {}".format(
            1 if bool(snapshot.get("request_snapshot_fallback_enabled", False)) else 0
        )
    )

    return "\n".join(lines) + "\n"


def _backtest_admission_limit_snapshot() -> Dict[str, int]:
    max_active = _read_positive_int_env("BACKTEST_MAX_ACTIVE_RUNS_GLOBAL", 10)
    max_queue_depth = _read_positive_int_env("BACKTEST_MAX_QUEUE_DEPTH", max_active)
    max_in_process = _read_positive_int_env(
        "BACKTEST_MAX_IN_PROCESS_BACKTEST_JOBS", max_active
    )
    retry_after_seconds = _read_positive_int_env(
        "BACKTEST_ADMISSION_RETRY_AFTER_SECONDS", 15
    )
    return {
        "max_active_runs_global": max_active,
        "max_queue_depth": max_queue_depth,
        "max_in_process_jobs": max_in_process,
        "retry_after_seconds": retry_after_seconds,
    }


def _check_backtest_admission(service: BacktestService) -> Optional[JSONResponse]:
    if not hasattr(service, "get_runtime_health"):
        return None

    limits = _backtest_admission_limit_snapshot()
    runtime_health = service.get_runtime_health()
    queue_depth = int(runtime_health.get("queue_depth", 0) or 0)
    active_jobs = int(runtime_health.get("active_jobs", 0) or 0)
    persistence_overloaded = bool(
        runtime_health.get("persistence_pool_overloaded", False)
    )
    block_on_persistence_overload = _read_bool_env(
        "BACKTEST_BLOCK_ON_PERSISTENCE_OVERLOAD",
        True,
    )

    blocked_reason = ""
    if block_on_persistence_overload and persistence_overloaded:
        blocked_reason = "persistence_pool_overload"
    elif (
        limits["max_active_runs_global"] > 0
        and queue_depth >= limits["max_active_runs_global"]
    ):
        blocked_reason = "global_active_limit_reached"
    elif limits["max_queue_depth"] > 0 and queue_depth >= limits["max_queue_depth"]:
        blocked_reason = "queue_depth_limit_reached"
    elif (
        limits["max_in_process_jobs"] > 0
        and active_jobs >= limits["max_in_process_jobs"]
    ):
        blocked_reason = "in_process_limit_reached"

    if not blocked_reason:
        return None

    if blocked_reason == "persistence_pool_overload":
        message = (
            "Backtest capacity is temporarily saturated due to runtime overload. "
            "Please retry shortly; no additional runs can be accepted right now."
        )
    else:
        message = (
            "Backtest capacity is temporarily saturated. "
            "Please retry shortly or reduce concurrent runs."
        )

    response = api_response(
        success=False,
        status_code=429,
        message=message,
        data={
            "error": "backtest_capacity_reached",
            "reason": blocked_reason,
            "cannot_accept_new_runs": True,
            "runtime_health": runtime_health,
            "limits": limits,
        },
    )
    response.headers["Retry-After"] = str(max(1, limits["retry_after_seconds"]))
    return response


def _backtest_capacity_snapshot(runtime_health: Dict[str, Any]) -> Dict[str, Any]:
    limits = _backtest_admission_limit_snapshot()
    return {
        "queue_depth": int(runtime_health.get("queue_depth", 0) or 0),
        "active_jobs": int(runtime_health.get("active_jobs", 0) or 0),
        "total_runs": int(runtime_health.get("total_runs", 0) or 0),
        "persistence_pool_overloaded": bool(
            runtime_health.get("persistence_pool_overloaded", False)
        ),
        "persistence_pool_overload_events_recent": int(
            runtime_health.get("persistence_pool_overload_events_recent", 0) or 0
        ),
        "progress_updates_persisted": int(
            runtime_health.get("progress_updates_persisted", 0) or 0
        ),
        "progress_updates_skipped": int(
            runtime_health.get("progress_updates_skipped", 0) or 0
        ),
        "progress_skip_ratio": float(
            runtime_health.get("progress_skip_ratio", 0.0) or 0.0
        ),
        "max_active_runs_global": limits["max_active_runs_global"],
        "max_queue_depth": limits["max_queue_depth"],
        "max_in_process_jobs": limits["max_in_process_jobs"],
        "retry_after_seconds": limits["retry_after_seconds"],
        "stale_heartbeat_seconds": _read_positive_int_env(
            "BACKTEST_STALE_HEARTBEAT_SECONDS",
            int(BacktestService._STALE_BACKTEST_HEARTBEAT_SECONDS),
        ),
        "max_active_runs_per_user": _read_positive_int_env(
            "BACKTEST_MAX_ACTIVE_RUNS_PER_USER",
            0,
        ),
    }


async def _resolve_backtest_markets(
    explicit_markets: Optional[List[str]],
    selected_pairs: Optional[List[str]],
    max_pairs: Any,
) -> List[str]:
    """Resolve the exact user-selected market universe for an execution request."""
    cap = _normalize_requested_pair_cap(max_pairs)

    normalized = _normalize_string_list(explicit_markets)
    if not normalized:
        normalized = _markets_from_selected_pair_labels(selected_pairs)

    if cap is not None and explicit_markets:
        normalized = normalized[:cap]

    if len(normalized) < 2:
        raise ValueError(
            "SELECTED_PAIRS_MISSING: at least two selected pairs are required"
        )

    available: set[str] = set()
    client = None
    try:
        client = await asyncio.wait_for(
            connect_dydx(),
            timeout=MARKET_RESOLUTION_TIMEOUT_SECONDS,
        )
        payload = await asyncio.wait_for(
            client.indexer.markets.get_perpetual_markets(),
            timeout=MARKET_RESOLUTION_TIMEOUT_SECONDS,
        )
        raw_map = payload.get("markets", {}) if isinstance(payload, dict) else {}
        if isinstance(raw_map, dict):
            available = {
                str(k).strip().upper() for k in raw_map.keys() if str(k).strip()
            }
    except Exception as err:
        raise ValueError(f"MARKET_RESOLUTION_FAILED: {err}") from err
    finally:
        if client is not None:
            try:
                await client.node.close()
            except Exception:
                pass

    invalid = [market for market in normalized if market not in available]
    if not available:
        raise ValueError("MARKET_RESOLUTION_FAILED: no dYdX perpetual markets returned")
    if invalid:
        raise ValueError(
            "SELECTED_PAIRS_INVALID: unsupported selected pairs " + ", ".join(invalid)
        )

    return normalized


def _strategy_to_backtest_request(
    strategy: Dict[str, Any],
    request: BacktestRunRequestCompat,
    pairs: List[str],
    selected_pair_labels: List[str],
) -> BacktestConfigRequest:
    strategy_defaults = {
        "zscore_threshold": strategy.get("zscore_threshold", 1.5),
        "stats_window": strategy.get("stats_window", 21),
        "max_half_life": strategy.get("max_half_life", 24),
        "usd_per_trade": strategy.get("usd_per_trade", 10.0),
        "usd_min_collateral": strategy.get("usd_min_collateral", 100.0),
        "close_at_zscore_cross": strategy.get("close_at_zscore_cross", True),
        "find_cointegrated_pairs": strategy.get("find_cointegrated_pairs", True),
        "manage_exits": strategy.get("manage_exits", True),
        "place_trades": strategy.get("place_trades", True),
        "abort_all_positions": strategy.get("abort_all_positions", False),
        "max_positions": strategy.get("max_positions", 5),
        "max_drawdown_pct": strategy.get("max_drawdown_pct", 15.0),
        "stop_loss_pct": strategy.get("stop_loss_pct", 2.0),
        "take_profit_pct": strategy.get("take_profit_pct", 5.0),
        "trailing_stop_pct": strategy.get("trailing_stop_pct", 1.0),
        "rebalance_interval_hours": strategy.get("rebalance_interval_hours", 24),
        "position_timeout_hours": strategy.get("position_timeout_hours", 72),
        "transaction_fee": strategy.get("transaction_fee", 0.0005),
        "slippage": strategy.get("slippage", 0.001),
        "risk_free_rate": strategy.get("risk_free_rate", 0.02),
        "benchmark_symbol": strategy.get("benchmark_symbol", "BTC-USD"),
        "max_history_days": strategy.get("max_history_days", 90),
        "resolution": strategy.get(
            "resolution",
            strategy.get("candle_resolution", "1HOUR"),
        ),
        "candle_resolution": strategy.get(
            "candle_resolution",
            strategy.get("resolution", "1HOUR"),
        ),
    }
    request_trading_parameters = dict(request.trading_parameters or {})
    selected_mode = str(
        request.pair_selection_mode
        or request_trading_parameters.get("pair_selection_mode")
        or strategy.get("pair_selection_mode", "liquidity")
    )
    trading_parameters = {
        **strategy_defaults,
        **request_trading_parameters,
    }
    trading_parameters["pair_selection_mode"] = selected_mode
    if (
        "resolution" not in trading_parameters
        and "candle_resolution" in trading_parameters
    ):
        trading_parameters["resolution"] = trading_parameters["candle_resolution"]
    if (
        "candle_resolution" not in trading_parameters
        and "resolution" in trading_parameters
    ):
        trading_parameters["candle_resolution"] = trading_parameters["resolution"]
    trading_parameters.setdefault("max_pairs", int(request.max_pairs))

    requested_initial_balance = float(request.initial_balance or 0.0)
    initial_balance = (
        requested_initial_balance
        if requested_initial_balance > 0
        else float(
            strategy.get(
                "starting_balance",
                strategy.get("initial_amount", 1000.0),
            )
        )
    )

    return BacktestConfigRequest(
        name=request.name or f"{strategy['name']} Backtest",
        description=request.description or strategy.get("description", ""),
        start_date=request.start_date,
        end_date=request.end_date,
        initial_balance=initial_balance,
        strategy_id=request.strategy_id,
        pair_selection_mode=selected_mode,
        max_pairs=int(request.max_pairs),
        trading_parameters=trading_parameters,
        pairs=pairs,
        selected_pairs=selected_pair_labels,
        strategy_payload_snapshot=dict(strategy),
        bot_id=request.bot_id,
        source=request.source,
        environment=request.environment,
        requested_by_user_id=request.requested_by_user_id,
        source_strategy_version=request.source_strategy_version,
        timeout_seconds=request.timeout_seconds,
        metadata=dict(request.metadata or {}),
    )


def _manual_backtest_request(
    request: BacktestRunRequestCompat,
    pairs: List[str],
    selected_pair_labels: List[str],
) -> BacktestConfigRequest:
    request_trading_parameters = dict(request.trading_parameters or {})
    selected_mode = str(
        request.pair_selection_mode
        or request_trading_parameters.get("pair_selection_mode")
        or "liquidity"
    )
    trading_parameters = {
        **(
            request_trading_parameters
            or {
                "zscore_threshold": 1.5,
                "stats_window": 21,
                "usd_per_trade": 10.0,
                "close_at_zscore_cross": True,
            }
        ),
        "pair_selection_mode": selected_mode,
        "max_pairs": int(request.max_pairs),
    }
    if (
        "resolution" not in trading_parameters
        and "candle_resolution" in trading_parameters
    ):
        trading_parameters["resolution"] = trading_parameters["candle_resolution"]
    if (
        "candle_resolution" not in trading_parameters
        and "resolution" in trading_parameters
    ):
        trading_parameters["candle_resolution"] = trading_parameters["resolution"]

    return BacktestConfigRequest(
        name=request.name or "manual-backtest",
        description=request.description or "Manual backtest run",
        start_date=request.start_date,
        end_date=request.end_date,
        initial_balance=request.initial_balance,
        timeout_seconds=request.timeout_seconds,
        strategy_id=request.strategy_id,
        pair_selection_mode=selected_mode,
        max_pairs=int(request.max_pairs),
        trading_parameters=trading_parameters,
        pairs=pairs,
        selected_pairs=selected_pair_labels,
        strategy_payload_snapshot=dict(request.strategy_payload_snapshot or {}),
        bot_id=request.bot_id,
        source=request.source,
        environment=request.environment,
        requested_by_user_id=request.requested_by_user_id,
        source_strategy_version=request.source_strategy_version,
        metadata=dict(request.metadata or {}),
    )


def _resolve_strategy_backtest_request(
    request: BacktestRunRequestCompat,
    pairs: List[str],
    selected_pair_labels: List[str],
    endpoint: str,
) -> Union[BacktestConfigRequest, JSONResponse]:
    def _strategy_snapshot_from_backtest_history(
        strategy_id: int,
        *,
        limit: int = 100,
    ) -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            rows = (
                session.query(BacktestRun.request_json, BacktestRun.run_id)
                .order_by(BacktestRun.updated_at.desc())
                .limit(max(1, int(limit)))
                .all()
            )
            for request_json, run_id in rows:
                if not isinstance(request_json, dict):
                    continue

                candidate = request_json.get("strategy_payload_snapshot")
                if not isinstance(candidate, dict):
                    continue

                candidate_id = candidate.get("id", request_json.get("strategy_id"))
                if candidate_id is None:
                    continue
                try:
                    if int(candidate_id) != int(strategy_id):
                        continue
                except (TypeError, ValueError):
                    continue

                resolved = dict(candidate)
                resolved.setdefault("id", int(strategy_id))
                _record_strategy_resolution_path("history")
                logger.info(
                    "strategy_resolved_from_backtest_history strategy_id={} endpoint={} run_id={}",
                    strategy_id,
                    endpoint,
                    run_id,
                )
                return resolved
            return None
        except Exception as history_error:
            logger.warning(
                "strategy_history_lookup_failed strategy_id={} endpoint={} error={}",
                strategy_id,
                endpoint,
                history_error,
            )
            return None
        finally:
            session.close()

    fallback_snapshot = dict(request.strategy_payload_snapshot or {})
    if request.strategy_id is None:
        if not fallback_snapshot and not request.trading_parameters:
            return api_response(
                success=False,
                message=(
                    "STRATEGY_PAYLOAD_MISSING: one-off backtests require "
                    "a strategy_payload_snapshot or trading_parameters"
                ),
                data={"error": "STRATEGY_PAYLOAD_MISSING"},
                status_code=422,
            )
        return _manual_backtest_request(request, pairs, selected_pair_labels)

    strategy: Optional[Dict[str, Any]] = None
    lookup_error: Optional[Exception] = None
    try:
        strategy = InMemoryStrategyStore.get(request.strategy_id)
    except Exception as exc:
        lookup_error = exc

    if strategy:
        _record_strategy_resolution_path("store")

    if not strategy and lookup_error is None:
        strategy = _strategy_snapshot_from_backtest_history(request.strategy_id)

    if not strategy and fallback_snapshot and _request_snapshot_fallback_enabled():
        fallback_snapshot.setdefault("id", request.strategy_id)
        _record_strategy_resolution_path("request")
        if lookup_error is not None:
            logger.info(
                "strategy_lookup_failed strategy_id={} endpoint={} error={} using_request_snapshot=true",
                request.strategy_id,
                endpoint,
                lookup_error,
            )
        else:
            logger.info(
                "strategy_not_found strategy_id={} endpoint={} using_request_snapshot=true",
                request.strategy_id,
                endpoint,
            )
        strategy = fallback_snapshot

    if lookup_error is not None and not strategy:
        logger.warning(
            "strategy_lookup_failed strategy_id={} endpoint={} error={}",
            request.strategy_id,
            endpoint,
            lookup_error,
        )

    if not strategy:
        if fallback_snapshot and not _request_snapshot_fallback_enabled():
            logger.warning(
                "strategy_request_snapshot_fallback_disabled strategy_id={} endpoint={} environment={} strict_disable_in_production=true",
                request.strategy_id,
                endpoint,
                os.getenv("ENVIRONMENT", "development"),
            )
        _record_strategy_resolution_path("not_found")
        logger.warning(
            "strategy_not_found strategy_id={} endpoint={}",
            request.strategy_id,
            endpoint,
        )
        return api_response(
            success=False,
            message=f"STRATEGY_NOT_FOUND: strategy_id={request.strategy_id}",
            data={
                "error": "STRATEGY_NOT_FOUND",
                "strategy_id": request.strategy_id,
            },
            status_code=404,
        )

    strategy = dict(strategy)
    strategy.setdefault("id", request.strategy_id)
    return _strategy_to_backtest_request(
        strategy,
        request,
        pairs,
        selected_pair_labels,
    )


async def _broadcast_backtest_progress(
    run_id: str, progress: float, current_pair: str, eta: int
) -> None:
    progress_message = {
        "type": "backtest_progress",
        "timestamp": utc_now_iso(),
        "run_id": run_id,
        "progress_pct": progress,
        "progress": progress,
        "current_pair": current_pair,
        "eta_seconds": eta,
    }
    log_message = {
        "type": "backtest_log",
        "timestamp": utc_now_iso(),
        "run_id": run_id,
        "level": "info",
        "message": (
            "Backtest completed"
            if current_pair == "complete"
            else f"Scanning: {current_pair}"
        ),
        "current_pair": current_pair,
        "current_task": "complete" if current_pair == "complete" else "running",
    }
    try:
        await manager.broadcast_to_bot(f"backtest-{run_id}", progress_message)
        await manager.broadcast_to_bot(f"backtest-{run_id}", log_message)
    except Exception as exc:
        logger.warning(
            "backtest_websocket_publish_failed run_id={} progress={} error_type={} error_repr={!r}",
            run_id,
            progress,
            type(exc).__name__,
            exc,
        )
    logger.debug(
        f"Backtest {run_id} progress: {progress:.1f}% ({current_pair}), ETA: {eta}s"
    )


@router.websocket("/api/v1/backtests/{run_id}/live")
async def websocket_backtest_progress(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for live backtest progress updates."""
    if not await _authorize_websocket_connection(websocket):
        return
    await WebSocketServer.handle_connection(websocket, f"backtest-{run_id}")


@router.websocket("/ws/backtests/{run_id}")
async def websocket_backtest_progress_alias(websocket: WebSocket, run_id: str):
    """Alias websocket channel for backend integrations consuming backtest runtime events."""
    if not await _authorize_websocket_connection(websocket):
        return
    await WebSocketServer.handle_connection(websocket, f"backtest-{run_id}")


def get_backtest_service():
    """Dependency to get backtest service"""
    db_session = db.get_session()
    repository = BacktestRepository(db_session)
    # Ensure repository has access to session for service operations
    repository.db = db_session  # type: ignore[attr-defined]
    service = BacktestService(repository)
    return service


def close_backtest_service(service: Optional[BacktestService]) -> None:
    """Release the SQLAlchemy session used by a request-scoped backtest service."""
    if service is None:
        return

    session = getattr(service, "session", None)
    if session is None:
        repository = getattr(service, "repository", None)
        session = getattr(repository, "session", None)

    if session is None:
        return

    try:
        session.close()
    except Exception as exc:
        logger.warning(f"Failed to close backtest service session: {exc}")


@contextmanager
def backtest_service_scope() -> Generator["BacktestService", None, None]:
    """Provide a request-scoped backtest service and always release its DB session."""
    service = _compat("get_backtest_service", get_backtest_service)()
    try:
        yield service
    finally:
        close_backtest_service(service)


def _run_with_backtest_service(operation):
    """Execute sync backtest-service work with request-scoped session cleanup."""
    service = _compat("get_backtest_service", get_backtest_service)()
    try:
        return operation(service)
    finally:
        close_backtest_service(service)


def _list_backtests_sync(
    limit: int,
    offset: int,
    status: Optional[str],
    days: Optional[int],
):
    return _run_with_backtest_service(
        lambda service: service.list_backtest_runs(
            limit=limit,
            offset=offset,
            status_filter=status,
            days_filter=days,
        )
    )


def _get_backtest_details_sync(run_id: str):
    return _run_with_backtest_service(
        lambda service: service.get_backtest_details(run_id)
    )


def _get_backtest_status_sync(run_id: str):
    return _run_with_backtest_service(
        lambda service: service.get_backtest_status(run_id)
    )


def _get_backtest_trades_sync(
    run_id: str,
    limit: int,
    offset: int,
    winning_only: bool,
):
    return _run_with_backtest_service(
        lambda service: service.get_backtest_trades(
            run_id=run_id,
            limit=limit,
            offset=offset,
            winning_only=winning_only,
        )
    )


def _get_backtest_analytics_sync(run_id: str):
    return _run_with_backtest_service(
        lambda service: service.get_comprehensive_analytics(run_id)
    )


def _get_position_snapshots_sync(
    run_id: str,
    limit: int,
    offset: int,
    market_pair: Optional[str],
):
    return _run_with_backtest_service(
        lambda service: service.get_position_snapshots(
            run_id=run_id,
            limit=limit,
            offset=offset,
            market_pair=market_pair,
        )
    )


def _get_backtest_summary_stats_sync(days: int):
    return _run_with_backtest_service(lambda service: service.get_summary_stats(days))


def _get_backtest_runtime_health_sync():
    return _run_with_backtest_service(lambda service: service.get_runtime_health())


def _compare_backtests_sync(run_ids: List[str], metrics: List[str]):
    return _run_with_backtest_service(
        lambda service: service.compare_backtests(run_ids, metrics)
    )


def _get_advanced_performance_metrics_sync(run_id: str, benchmark: str):
    return _run_with_backtest_service(
        lambda service: service.get_advanced_performance_metrics(run_id, benchmark)
    )


def _get_live_progress_sync(run_id: str):
    return _run_with_backtest_service(lambda service: service.get_live_progress(run_id))


@router.post("/api/v1/backtests", response_model=BacktestResponse)
async def create_backtest(
    request: Union[BacktestConfigRequest, BacktestRunRequestCompat],
    _rate: None = Depends(_check_backtest_rate_limit),
    current_user: User = Depends(get_current_active_user),
):
    """Create and start a new backtest"""
    del current_user
    try:
        if isinstance(request, BacktestRunRequestCompat):
            resolved_pairs = await _compat(
                "_resolve_backtest_markets", _resolve_backtest_markets
            )(
                request.pairs,
                request.selected_pairs,
                request.max_pairs,
            )
            selected_pair_labels = _normalize_string_list(request.selected_pairs)
            if not selected_pair_labels:
                selected_pair_labels = _build_selected_pair_labels(resolved_pairs)
            normalized_request = _compat(
                "_resolve_strategy_backtest_request", _resolve_strategy_backtest_request
            )(
                request,
                resolved_pairs,
                selected_pair_labels,
                "/api/v1/backtests",
            )
            if isinstance(normalized_request, JSONResponse):
                return normalized_request
        else:
            normalized_request = request

        with _compat("backtest_service_scope", backtest_service_scope)() as service:
            blocked = _check_backtest_admission(service)
            if blocked is not None:
                return blocked
            result = await service.create_and_run_backtest(
                normalized_request, _broadcast_backtest_progress
            )

        return api_response(
            success=True,
            data=result.model_dump(),
            message=f"Backtest '{normalized_request.name}' created and started",
        )

    except ValueError as e:
        error_code = str(e).split(":", 1)[0].strip()
        status_code = (
            422
            if error_code
            in {
                "SELECTED_PAIRS_MISSING",
                "SELECTED_PAIRS_INVALID",
                "MARKET_RESOLUTION_FAILED",
                "STRATEGY_PAYLOAD_MISSING",
            }
            else 400
        )
        return api_response(
            success=False,
            message=f"Validation error: {str(e)}",
            data={"error": error_code},
            status_code=status_code,
        )


@router.post("/api/v1/backtests/run")
async def run_backtest_compat(
    request: BacktestRunRequestCompat,
    _rate: None = Depends(_check_backtest_rate_limit),
    current_user: User = Depends(get_current_active_user),
):
    """Frontend-compatible backtest execution route."""
    del current_user
    try:
        resolved_pairs = await _compat(
            "_resolve_backtest_markets", _resolve_backtest_markets
        )(
            request.pairs,
            request.selected_pairs,
            request.max_pairs,
        )
        selected_pair_labels = _normalize_string_list(request.selected_pairs)
        if not selected_pair_labels:
            selected_pair_labels = _build_selected_pair_labels(resolved_pairs)
        backtest_request = _compat(
            "_resolve_strategy_backtest_request", _resolve_strategy_backtest_request
        )(
            request,
            resolved_pairs,
            selected_pair_labels,
            "/api/v1/backtests/run",
        )
        if isinstance(backtest_request, JSONResponse):
            return backtest_request

        if request.strategy_id is not None:
            logger.info(
                "strategy_linked_to_backtest strategy_id={} selected_pairs={}",
                request.strategy_id,
                selected_pair_labels,
            )

        with _compat("backtest_service_scope", backtest_service_scope)() as service:
            blocked = _check_backtest_admission(service)
            if blocked is not None:
                return blocked
            result = await service.create_and_run_backtest(
                backtest_request, _broadcast_backtest_progress
            )
        payload = result.model_dump()
        payload["progress"] = float(payload.get("progress_pct", 0.0))
        payload["count"] = 1
        return api_response(
            success=True,
            data=payload,
            message=f"Backtest '{result.name}' started",
        )
    except ValueError as e:
        error_code = str(e).split(":", 1)[0].strip()
        status_code = (
            422
            if error_code
            in {
                "SELECTED_PAIRS_MISSING",
                "SELECTED_PAIRS_INVALID",
                "MARKET_RESOLUTION_FAILED",
                "STRATEGY_PAYLOAD_MISSING",
            }
            else 400
        )
        return api_response(
            success=False,
            message=f"Validation error: {str(e)}",
            data={"error": error_code},
            status_code=status_code,
        )
    except Exception as e:
        logger.error(f"Error running compatibility backtest: {e}")
        return api_response(
            success=False,
            message="BOT_EXECUTION_FAILED: Internal server error",
            data={"error": "BOT_EXECUTION_FAILED"},
            status_code=500,
        )


@router.get("/api/v1/backtests", response_model=BacktestListResponse)
async def list_backtests(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    days: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
):
    """List backtest runs with filtering"""
    del current_user
    try:
        result = await run_db(
            _compat("_list_backtests_sync", _list_backtests_sync),
            limit,
            offset,
            status,
            days,
        )
        payload = result.model_dump()
        payload["backtests"] = payload.get("runs", [])
        payload["count"] = len(payload["backtests"])

        return api_response(
            success=True,
            data=payload,
            message=f"Retrieved {len(result.runs)} backtest runs",
        )

    except Exception as e:
        logger.error(f"Error listing backtests: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.get("/api/v1/backtests/interrupted")
async def list_interrupted_backtests(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
):
    """Ops visibility for interrupted/orphaned persisted backtest runs."""
    del current_user
    return _compat(
        "_list_interrupted_backtests_response", _list_interrupted_backtests_response
    )(limit=limit)


def _list_interrupted_backtests_response(limit: int):
    """Shared response builder for interrupted backtest visibility routes."""
    try:
        with _compat("backtest_service_scope", backtest_service_scope)() as service:
            report = service.list_interrupted_runs_for_ops(limit=limit)
        report["count"] = int(report.get("orphaned_count", 0)) + int(
            report.get("interrupted_count", 0)
        )
        return api_response(
            success=True,
            data=report,
            message="Retrieved interrupted backtest reconciliation report",
        )
    except Exception as e:
        logger.error(f"Error listing interrupted backtests: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.post("/api/v1/backtests/interrupted/reconcile")
async def reconcile_interrupted_backtests(
    dry_run: bool = True,
    current_user: User = Depends(get_current_active_user),
):
    """Explicitly reconcile persisted orphaned in-progress runs."""
    del current_user
    return _compat(
        "_reconcile_interrupted_backtests_response",
        _reconcile_interrupted_backtests_response,
    )(dry_run=dry_run)


def _reconcile_interrupted_backtests_response(dry_run: bool):
    """Shared response builder for interrupted backtest reconcile routes."""
    with _compat("backtest_service_scope", backtest_service_scope)() as service:
        report = service.reconcile_interrupted_runs(dry_run=dry_run)
    report["count"] = int(report.get("candidate_count", 0))
    message = (
        "Dry-run completed for interrupted backtest reconciliation"
        if dry_run
        else "Interrupted backtest reconciliation completed"
    )
    return api_response(
        success=True,
        data=report,
        message=message,
    )


def _repair_backtest_request_response(run_id: str, dry_run: bool):
    """Shared response builder for request repair routes."""
    with _compat("backtest_service_scope", backtest_service_scope)() as service:
        report = service.repair_backtest_request(run_id, dry_run=dry_run)
    if report is None:
        return api_response(
            success=False,
            message=f"Backtest '{run_id}' not found",
            status_code=404,
        )

    message = (
        f"Dry-run completed for backtest '{run_id}' request repair"
        if dry_run
        else f"Backtest '{run_id}' request payload repaired"
    )
    return api_response(success=True, data=report, message=message)


@router.get("/api/v1/admin/backtests/interrupted")
async def list_interrupted_backtests_admin(
    limit: int = 50,
    current_user: User = Depends(get_admin_user),
):
    """Admin-scoped alias for interrupted/orphaned persisted backtest visibility."""
    _ = current_user
    return _compat(
        "_list_interrupted_backtests_response", _list_interrupted_backtests_response
    )(limit=limit)


@router.post("/api/v1/admin/backtests/interrupted/reconcile")
async def reconcile_interrupted_backtests_admin(
    dry_run: bool = True,
    current_user: User = Depends(get_admin_user),
):
    """Admin-scoped alias for explicit interrupted backtest reconciliation."""
    _ = current_user
    return _compat(
        "_reconcile_interrupted_backtests_response",
        _reconcile_interrupted_backtests_response,
    )(dry_run=dry_run)


@router.post("/api/v1/admin/backtests/{run_id}/repair-request")
async def repair_backtest_request_admin(
    run_id: str,
    dry_run: bool = True,
    current_user: User = Depends(get_admin_user),
):
    """Admin-scoped repair for legacy backtests missing request payloads."""
    _ = current_user
    return _compat(
        "_repair_backtest_request_response", _repair_backtest_request_response
    )(run_id=run_id, dry_run=dry_run)


@router.get("/api/v1/backtests/{run_id}", response_model=BacktestDetailResponse)
async def get_backtest_details(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get detailed backtest results"""
    del current_user
    result = await run_db(_get_backtest_details_sync, run_id)
    if not result:
        return api_response(
            success=False,
            message=f"Backtest run '{run_id}' not found",
            status_code=404,
        )

    return api_response(
        success=True,
        data=result.model_dump(),
        message=f"Retrieved details for backtest '{run_id}'",
    )


@router.get("/api/v1/backtests/{run_id}/status")
async def get_backtest_status(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get current backtest status and progress"""
    del current_user
    result = await run_db(_get_backtest_status_sync, run_id)
    if not result:
        return api_response(
            success=False,
            message=f"Backtest run '{run_id}' not found",
            status_code=404,
        )

    payload = result.model_dump()
    payload["progress"] = float(payload.get("progress_pct", 0.0))
    payload["count"] = 1
    payload["websocket_send_metrics"] = manager.get_backtest_send_failure_metrics(
        run_id
    )

    return api_response(
        success=True,
        data=payload,
        message=f"Retrieved status for backtest '{run_id}'",
    )


@router.post("/api/v1/backtests/{run_id}/metadata")
async def update_backtest_metadata(
    run_id: str,
    payload: BacktestMetadataRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Attach or merge structured metadata into a persisted backtest run."""
    del current_user
    with _compat("backtest_service_scope", backtest_service_scope)() as service:
        result = service.update_backtest_metadata(
            run_id,
            payload.metadata,
            merge=payload.merge,
        )

    if result is None:
        return api_response(
            success=False,
            message=f"Backtest run '{run_id}' not found",
            status_code=404,
        )

    return api_response(
        success=True,
        data=result,
        message=f"Updated metadata for backtest '{run_id}'",
    )


@router.get("/api/v1/backtests/{run_id}/websocket-metrics")
async def get_backtest_websocket_metrics(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get per-run websocket send-failure metrics for reconnect-thrashing alerting."""
    del current_user
    status = await run_db(_get_backtest_status_sync, run_id)
    if status is None:
        return api_response(
            success=False,
            message=f"Backtest run '{run_id}' not found",
            status_code=404,
        )

    metrics = manager.get_backtest_send_failure_metrics(run_id)
    return api_response(
        success=True,
        data={
            "run_id": run_id,
            "status": status.status,
            "metrics": metrics,
        },
        message=f"Retrieved websocket metrics for backtest '{run_id}'",
    )


@router.post("/api/v1/backtests/{run_id}/create-strategy")
async def create_strategy_from_backtest(
    run_id: str,
    request: BacktestCreateStrategyRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Create a strategy snapshot from an existing backtest."""
    del current_user
    with _compat("backtest_service_scope", backtest_service_scope)() as service:
        details = service.get_backtest_details(run_id)
    if not details:
        return api_response(
            success=False,
            message=f"Backtest '{run_id}' not found",
            status_code=404,
        )

    payload = {
        "name": request.name,
        "description": request.description,
        **request.config,
        "is_public": False,
    }
    strategy = InMemoryStrategyStore.create(payload)
    return api_response(
        success=True,
        data={
            **strategy,
            "source_backtest_run_id": run_id,
        },
        message="Strategy created from backtest",
    )


@router.get("/api/v1/backtests/{run_id}/trades")
async def get_backtest_trades(
    run_id: str,
    limit: int = 100,
    offset: int = 0,
    winning_only: bool = False,
    current_user: User = Depends(get_current_active_user),
):
    """Get trades for specific backtest run"""
    del current_user
    try:
        started_at = time.perf_counter()
        cache_key = f"backtest:trades:{run_id}:limit={limit}:offset={offset}:winning_only={winning_only}"
        trades_payload = _cache_get(cache_key)
        cache_hit = trades_payload is not None
        if not cache_hit:
            trades = await run_db(
                _get_backtest_trades_sync,
                run_id,
                limit,
                offset,
                winning_only,
            )
            trades_payload = [trade.model_dump() for trade in trades]
            _cache_set(cache_key, trades_payload)

        _log_endpoint_timing(
            "/api/v1/backtests/{run_id}/trades",
            started_at,
            trades_payload,
            cache_hit=cache_hit,
            payload_items=(
                len(trades_payload) if isinstance(trades_payload, list) else None
            ),
            extra={
                "run_id": run_id,
                "limit": limit,
                "offset": offset,
                "winning_only": winning_only,
            },
        )

        return api_response(
            success=True,
            data={
                "run_id": run_id,
                "trades": trades_payload,
                "total": len(trades_payload),
                "count": len(trades_payload),
            },
            message=f"Retrieved {len(trades_payload)} trades for backtest '{run_id}'",
            headers=_endpoint_perf_headers(started_at, cache_hit=cache_hit),
        )

    except Exception as e:
        logger.error(f"Error getting backtest trades: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.get("/api/v1/backtests/{run_id}/logs")
async def get_backtest_logs(
    run_id: str,
    tail: int = Query(default=1000, ge=1, le=10000),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve detailed execution logs for a specific backtest run."""
    del current_user
    log_file = os.path.join("bot_states", f"backtest_{run_id}.log")
    if not os.path.exists(log_file):
        return api_response(
            success=False,
            message=f"Execution logs for backtest '{run_id}' not found. Note: logs are only available for runs that used Celery workers.",
            data={"run_id": run_id, "logs": []},
            status_code=404,
        )

    try:

        def _read_logs():
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                # Efficiently read the last N lines for large log files.
                lines = f.readlines()
                return [line.rstrip() for line in lines[-tail:]]

        log_lines = _read_logs()
        return api_response(
            success=True,
            data={
                "run_id": run_id,
                "logs": log_lines,
                "count": len(log_lines),
                "tail": tail,
            },
            message=f"Retrieved {len(log_lines)} log lines for backtest '{run_id}'",
        )
    except Exception as e:
        logger.error(f"Error reading backtest logs for {run_id}: {e}")
        return api_response(
            success=False,
            message=f"Failed to read logs: {str(e)}",
            status_code=500,
        )


@router.post("/api/v1/backtests/{run_id}/cancel")
async def cancel_backtest(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Cancel running backtest"""
    del current_user
    with _compat("backtest_service_scope", backtest_service_scope)() as service:
        success = service.cancel_backtest(run_id)
    if not success:
        return api_response(
            success=False,
            message=f"Backtest '{run_id}' not found or not running",
            status_code=404,
        )

    return api_response(
        success=True, message=f"Backtest '{run_id}' cancelled successfully"
    )


@router.post("/api/v1/backtests/{run_id}/pause")
async def pause_backtest(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Request a cooperative pause for a running backtest."""
    del current_user
    with _compat("backtest_service_scope", backtest_service_scope)() as service:
        result = service.pause_backtest(run_id)
    if not result:
        return api_response(
            success=False,
            message=f"Backtest '{run_id}' not found or cannot be paused",
            status_code=404,
        )

    return api_response(
        success=True,
        data=result,
        message=f"Backtest '{run_id}' pause requested",
    )


@router.post("/api/v1/backtests/{run_id}/resume")
async def resume_backtest(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Resume a paused backtest."""
    del current_user
    with _compat("backtest_service_scope", backtest_service_scope)() as service:
        result = service.resume_backtest(run_id)
    if not result:
        return api_response(
            success=False,
            message=f"Backtest '{run_id}' not found or cannot be resumed",
            status_code=404,
        )

    return api_response(
        success=True,
        data=result,
        message=f"Backtest '{run_id}' resume requested",
    )


@router.post("/api/v1/backtests/{run_id}/restart")
async def restart_backtest(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Cancel the current run if needed and start a fresh run from the same request."""
    del current_user
    try:
        with _compat("backtest_service_scope", backtest_service_scope)() as service:
            status = service.get_backtest_status(run_id)
            if status is None:
                return api_response(
                    success=False,
                    message=f"Backtest '{run_id}' not found",
                    status_code=404,
                )
            if not bool(getattr(status, "request_available", False)):
                return api_response(
                    success=False,
                    message=(
                        f"Backtest '{run_id}' original request payload is unavailable; "
                        "repair the request payload before restart"
                    ),
                    data={"error": "missing_original_request_payload"},
                    status_code=409,
                )
            result = await service.restart_backtest(
                run_id, _broadcast_backtest_progress
            )
        if not result:
            return api_response(
                success=False,
                message=f"Backtest '{run_id}' not found or cannot be restarted",
                status_code=404,
            )

        return api_response(
            success=True,
            data=result,
            message=f"Backtest '{run_id}' restarted as '{result['new_run_id']}'",
        )

    except Exception as e:
        logger.error(f"Error restarting backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.post("/api/v1/backtests/{run_id}/retry")
async def retry_backtest(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Start a fresh run from the same request payload."""
    del current_user
    try:
        with _compat("backtest_service_scope", backtest_service_scope)() as service:
            status = service.get_backtest_status(run_id)
            if status is None:
                return api_response(
                    success=False,
                    message=f"Backtest '{run_id}' not found",
                    status_code=404,
                )
            if not bool(getattr(status, "request_available", False)):
                return api_response(
                    success=False,
                    message=(
                        f"Backtest '{run_id}' original request payload is unavailable; "
                        "repair the request payload before retry"
                    ),
                    data={"error": "missing_original_request_payload"},
                    status_code=409,
                )
            result = await service.retry_backtest(run_id, _broadcast_backtest_progress)
        if not result:
            return api_response(
                success=False,
                message=f"Backtest '{run_id}' not found or cannot be retried",
                status_code=404,
            )

        return api_response(
            success=True,
            data=result,
            message=f"Backtest '{run_id}' retried as '{result['new_run_id']}'",
        )

    except Exception as e:
        logger.error(f"Error retrying backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.delete("/api/v1/backtests/{run_id}")
async def delete_backtest(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete backtest run and all associated data"""
    del current_user
    with _compat("backtest_service_scope", backtest_service_scope)() as service:
        success = service.delete_backtest(run_id)
    if not success:
        return api_response(
            success=False, message=f"Backtest '{run_id}' not found", status_code=404
        )

    return api_response(
        success=True, message=f"Backtest '{run_id}' deleted successfully"
    )


@router.get("/api/v1/backtests/stats/summary")
async def get_backtest_summary_stats(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
):
    """Get backtest system summary statistics"""
    del current_user
    stats = await run_db(_get_backtest_summary_stats_sync, days)

    return api_response(
        success=True,
        data=stats,
        message=f"Retrieved backtest statistics for last {days} days",
    )


@router.get("/api/v1/backtests/{run_id}/analytics")
async def get_backtest_analytics(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get comprehensive analytics for a backtest run"""
    del current_user
    try:
        started_at = time.perf_counter()
        cache_key = f"backtest:analytics:full:{run_id}"
        analytics = _cache_get(cache_key)
        cache_hit = analytics is not None
        if not cache_hit:
            analytics = await run_db(_get_backtest_analytics_sync, run_id)
            if analytics:
                _cache_set(cache_key, analytics)
        if not analytics:
            return api_response(
                success=False,
                message=f"Backtest run '{run_id}' not found",
                status_code=404,
                headers=_endpoint_perf_headers(started_at, cache_hit=cache_hit),
            )

        trades = analytics.get("trades") if isinstance(analytics, dict) else None
        daily_pnl = analytics.get("daily_pnl") if isinstance(analytics, dict) else None
        snapshots = (
            analytics.get("position_snapshots") if isinstance(analytics, dict) else None
        )
        _log_endpoint_timing(
            "/api/v1/backtests/{run_id}/analytics",
            started_at,
            analytics,
            cache_hit=cache_hit,
            payload_items=(len(trades) if isinstance(trades, list) else None),
            extra={
                "run_id": run_id,
                "daily_pnl_points": (
                    len(daily_pnl) if isinstance(daily_pnl, list) else 0
                ),
                "position_snapshots_points": (
                    len(snapshots) if isinstance(snapshots, list) else 0
                ),
            },
        )

        return api_response(
            success=True,
            data=analytics,  # Already a dict
            message=f"Retrieved analytics for backtest '{run_id}'",
            headers=_endpoint_perf_headers(started_at, cache_hit=cache_hit),
        )

    except Exception as e:
        logger.error(f"Error getting backtest analytics: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.get("/api/v1/backtests/{run_id}/analytics/summary")
async def get_backtest_analytics_summary(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get compact analytics summary for high-frequency dashboard surfaces."""
    del current_user
    try:
        started_at = time.perf_counter()
        summary_cache_key = f"backtest:analytics:summary:{run_id}"
        summary = _cache_get(summary_cache_key)
        cache_hit = summary is not None

        if not cache_hit:
            full_cache_key = f"backtest:analytics:full:{run_id}"
            analytics = _cache_get(full_cache_key)
            if analytics is None:
                analytics = await run_db(_get_backtest_analytics_sync, run_id)
                if analytics:
                    _cache_set(full_cache_key, analytics)

            if not analytics:
                return api_response(
                    success=False,
                    message=f"Backtest run '{run_id}' not found",
                    status_code=404,
                    headers=_endpoint_perf_headers(started_at, cache_hit=False),
                )

            summary = _build_backtest_analytics_summary(run_id, analytics)
            _cache_set(summary_cache_key, summary)

        _log_endpoint_timing(
            "/api/v1/backtests/{run_id}/analytics/summary",
            started_at,
            summary,
            cache_hit=cache_hit,
            payload_items=1,
            extra={"run_id": run_id},
        )

        return api_response(
            success=True,
            data=summary,
            message=f"Retrieved analytics summary for backtest '{run_id}'",
            headers=_endpoint_perf_headers(started_at, cache_hit=cache_hit),
        )
    except Exception as e:
        logger.error(f"Error getting backtest analytics summary: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.get("/api/v1/backtests/{run_id}/position-snapshots")
async def get_position_snapshots(
    run_id: str,
    limit: int = 100,
    offset: int = 0,
    market_pair: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """Get position snapshots for real-time backtest tracking"""
    del current_user
    try:
        snapshots = await run_db(
            _get_position_snapshots_sync,
            run_id,
            limit,
            offset,
            market_pair,
        )

        return api_response(
            success=True,
            data={
                "run_id": run_id,
                "snapshots": snapshots,
                "position_snapshots": snapshots,
                "total": len(snapshots),
                "count": len(snapshots),
            },
            message=f"Retrieved {len(snapshots)} position snapshots for '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting position snapshots: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.post("/api/v1/backtests/compare")
async def compare_backtests(
    request: BacktestComparisonRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Compare multiple backtest runs with advanced analytics"""
    del current_user
    try:
        run_ids = request.run_ids
        metrics = request.metrics or (["total_return_pct", "sharpe_ratio", "win_rate"])

        comparison = await run_db(_compare_backtests_sync, run_ids, metrics)

        return api_response(
            success=True,
            data=comparison,  # Already a dict
            message=f"Compared {len(run_ids)} backtest runs",
        )

    except Exception as e:
        logger.error(f"Error comparing backtests: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.get("/api/v1/backtests/sync-health")
async def backtest_sync_health(
    metrics_only: bool = False,
    current_user: User = Depends(get_current_active_user),
):
    """Backend sync visibility endpoint for run orchestration health."""
    del current_user
    try:
        metrics_snapshot = _strategy_resolution_metrics_snapshot()
        if metrics_only:
            return api_response(
                success=True,
                data={
                    "status": "ok",
                    "strategy_resolution_metrics": metrics_snapshot,
                },
                message="Backtest sync health metrics retrieved",
            )

        runtime_health = await run_db(_get_backtest_runtime_health_sync)
        return api_response(
            success=True,
            data={
                "status": "ok",
                **runtime_health,
                "strategy_resolution_metrics": metrics_snapshot,
            },
            message="Backtest sync health retrieved",
        )
    except Exception as e:
        logger.error(f"Error getting backtest sync health: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.get("/api/v1/backtests/{run_id}/dydx-validation")
async def validate_against_dydx_data(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Validate backtest results against real dYdX market data"""
    del current_user
    try:
        with _compat("backtest_service_scope", backtest_service_scope)() as service:
            validation_result = await service.validate_against_dydx_data(run_id)  # type: ignore[attr-defined]
        if not validation_result:
            return api_response(
                success=False,
                message=f"Could not validate backtest '{run_id}' against dYdX data",
                status_code=404,
            )

        return api_response(
            success=True,
            data=validation_result,
            message=f"Validated backtest '{run_id}' against dYdX historical data",
        )

    except Exception as e:
        logger.error(f"Error validating against dYdX data: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.get("/api/v1/backtests/{run_id}/performance-metrics")
async def get_advanced_performance_metrics(
    run_id: str,
    benchmark: str = "BTC-USD",
    current_user: User = Depends(get_current_active_user),
):
    """Get advanced performance metrics with market benchmarking"""
    del current_user
    try:
        metrics = await run_db(
            _get_advanced_performance_metrics_sync,
            run_id,
            benchmark,
        )
        if not metrics:
            return api_response(
                success=False,
                message=f"Could not calculate metrics for backtest '{run_id}'",
                status_code=404,
            )

        return api_response(
            success=True,
            data=metrics,
            message=f"Retrieved advanced performance metrics for '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@router.get("/api/v1/backtests/{run_id}/live-progress")
async def get_live_progress(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get real-time backtest progress with current positions"""
    del current_user
    progress = await run_db(_get_live_progress_sync, run_id)
    if not progress:
        return api_response(
            success=False,
            message=f"Backtest run '{run_id}' not found",
            status_code=404,
        )

    return api_response(
        success=True,
        data=progress,
        message=f"Retrieved live progress for backtest '{run_id}'",
    )


__all__ = [
    "router",
    "configure_backtest_routes",
    "BacktestComparisonRequest",
    "BacktestCreateStrategyRequest",
    "BacktestMetadataRequest",
    "BacktestRunRequestCompat",
    "_backtest_admission_limit_snapshot",
    "_backtest_capacity_snapshot",
    "_broadcast_backtest_progress",
    "_build_backtest_analytics_summary",
    "_build_selected_pair_labels",
    "_cache_get",
    "_cache_set",
    "_check_backtest_admission",
    "_compare_backtests_sync",
    "_get_advanced_performance_metrics_sync",
    "_get_backtest_analytics_sync",
    "_get_backtest_details_sync",
    "_get_backtest_runtime_health_sync",
    "_get_backtest_status_sync",
    "_get_backtest_summary_stats_sync",
    "_get_backtest_trades_sync",
    "_get_live_progress_sync",
    "_get_position_snapshots_sync",
    "_list_backtests_sync",
    "_list_interrupted_backtests_response",
    "_manual_backtest_request",
    "_markets_from_selected_pair_labels",
    "_normalize_requested_pair_cap",
    "_normalize_string_list",
    "_read_bool_env",
    "_read_positive_int_env",
    "_reconcile_interrupted_backtests_response",
    "_record_strategy_resolution_path",
    "_repair_backtest_request_response",
    "_request_snapshot_fallback_enabled",
    "_reset_strategy_resolution_metrics",
    "_resolve_backtest_markets",
    "_resolve_strategy_backtest_request",
    "_run_with_backtest_service",
    "_strategy_resolution_metrics_prometheus",
    "_strategy_resolution_metrics_snapshot",
    "_strategy_to_backtest_request",
    "backtest_service_scope",
    "backtest_sync_health",
    "cancel_backtest",
    "close_backtest_service",
    "compare_backtests",
    "create_backtest",
    "create_strategy_from_backtest",
    "delete_backtest",
    "get_advanced_performance_metrics",
    "get_backtest_analytics",
    "get_backtest_analytics_summary",
    "get_backtest_details",
    "get_backtest_logs",
    "get_backtest_service",
    "get_backtest_status",
    "get_backtest_summary_stats",
    "get_backtest_trades",
    "get_backtest_websocket_metrics",
    "get_live_progress",
    "get_position_snapshots",
    "list_backtests",
    "list_interrupted_backtests",
    "list_interrupted_backtests_admin",
    "pause_backtest",
    "reconcile_interrupted_backtests",
    "reconcile_interrupted_backtests_admin",
    "repair_backtest_request_admin",
    "restart_backtest",
    "resume_backtest",
    "retry_backtest",
    "run_backtest_compat",
    "update_backtest_metadata",
    "validate_against_dydx_data",
    "websocket_backtest_progress",
    "websocket_backtest_progress_alias",
    "_backtest_endpoint_cache",
    "_strategy_resolution_metrics",
    "_strategy_resolution_metrics_lock",
    "_strategy_resolution_recent_paths",
]
