"""
Bot API Server - FastAPI server for controlling multiple bot instances
"""

import asyncio
import contextvars
import json
import os
import re
import sys
import threading
import time
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Union
from uuid import uuid4

import httpx
import uvicorn
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from src.shared.env_loader import load_repo_env
from src.shared.redis_env import redis_url

# Load structured config BEFORE importing project modules that initialize config/database.
load_repo_env(__file__)

# Import authentication modules
from src.api.v1.auth import router as auth_router  # noqa: E402

# Import bot models and manager
from src.infrastructure.domain.bot_api_models import (  # noqa: E402
    BotCredentials,
    BotInstanceConfig,
    BotInstanceList,
    BotInstanceStatus,
    BotOperationResult,
    BotStatus,
    TradingParameters,
)
from src.infrastructure.domain.models.auth_models import User  # noqa: E402
from src.middleware.auth_middleware import (  # noqa: E402
    authenticate_bearer_token,
    current_environment_name,
    get_admin_user,
    get_current_active_user,
    is_auth_bypass_enabled,
    validate_auth_bypass_configuration,
)

try:
    from src.bot_instance_manager import bot_manager  # noqa: E402
except Exception as bot_manager_import_error:  # pragma: no cover
    logger.warning(
        "Bot instance manager unavailable at startup: {}", bot_manager_import_error
    )
    bot_manager = None

from internal.domain.models import BacktestRun, BotStatusEnum  # noqa: E402
from src.api.realtime_serializers import (  # noqa: E402
    serialize_market_core,
    serialize_realtime_position,
    serialize_stats_risk_fields,
)
from src.api.websocket_server import (  # noqa: E402
    WebSocketServer,
    broadcast_strategy_status,
    build_strategy_snapshot_message,
    manager,
)

# Import database utilities
from src.infrastructure.database import DatabaseConfig, db  # noqa: E402
from src.infrastructure.domain.cointegration_storage import pair_storage  # noqa: E402

# Import backtest modules
from src.infrastructure.domain.models_backtest import (  # noqa: E402
    BacktestConfigRequest,
    BacktestDetailResponse,
    BacktestListResponse,
    BacktestResponse,
)
from src.infrastructure.persistence.repository import UnitOfWork  # noqa: E402
from src.infrastructure.persistence.repository_backtest import (  # noqa: E402
    BacktestRepository,
)
from src.infrastructure.persistence.repository_realtime import (  # noqa: E402
    UnitOfWorkRealtime,
)
from src.infrastructure.use_cases.async_job_manager import (  # noqa: E402
    async_job_manager,
)
from src.infrastructure.use_cases.service_backtest import BacktestService  # noqa: E402
from src.infrastructure.workers.celery_monitor import (  # noqa: E402
    celery_health,
    get_celery_task,
    list_celery_queues,
    list_celery_tasks,
    list_celery_workers,
    retry_celery_task,
    revoke_celery_task,
)
from src.shared.logging_setup import setup_logging  # noqa: E402
from src.shared.live_risk_controls import (
    assert_supported_live_risk_controls,
)  # noqa: E402
from src.shared.credentials_cipher import (  # noqa: E402
    open_config_secrets,
    seal_config_secrets,
)
from src.shared.notifications import TelegramMessenger  # noqa: E402
from src.shared.time_utils import utc_now_iso  # noqa: E402
from src.trading.arbitrage_observability import snapshot_metrics  # noqa: E402
from src.trading.arbitrage_runtime_config import (  # noqa: E402
    get_feature_flags,
    get_runtime_settings,
    is_pair_priority_engine_enabled,
    update_runtime_settings,
)
from src.trading.dydx_client import connect_dydx, connect_dydx_runtime  # noqa: E402
from src.trading.pair_priority import prioritize_pairs, score_pair  # noqa: E402

# Filter noisy third-party warnings after imports
_original_stderr = sys.stderr


class _FilteredStderr:
    """Filter noisy third-party warnings that are expected and already handled."""

    def __init__(self, stderr):
        self.stderr = stderr

    def write(self, message):
        if "Node URL should not contain http(s)://" not in message:
            self.stderr.write(message)
            self.stderr.flush()

    def flush(self):
        self.stderr.flush()

    def __getattr__(self, name):
        return getattr(self.stderr, name)


sys.stderr = _FilteredStderr(_original_stderr)

# Setup logging (Loguru + stdlib bridge)
setup_logging()
trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
INTERNAL_ERROR_MESSAGE = "Internal server error"
bot_manager_monitor_task: Optional[asyncio.Task] = None

MARKET_RESOLUTION_TIMEOUT_SECONDS = 10.0


# ---------------------------------------------------------------------------
# In-process rate limiter (sliding window, per caller key)
# Protects expensive mutation endpoints from rapid repeated calls.
# Limits are configurable via env vars; defaults are intentionally permissive.
# ---------------------------------------------------------------------------


class _SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter for async FastAPI handlers."""

    def __init__(self, max_requests: int, window_seconds: float):
        self._max = max_requests
        self._window = window_seconds
        self._buckets: Dict[str, list] = {}
        self._lock = threading.Lock()

    def _caller_key(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        return forwarded_for or (request.client.host if request.client else "unknown")

    def is_allowed(self, request: Request) -> bool:
        key = self._caller_key(request)
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            timestamps = self._buckets.get(key, [])
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self._max:
                self._buckets[key] = timestamps
                return False
            timestamps.append(now)
            self._buckets[key] = timestamps
        return True


class _RedisSlidingWindowRateLimiter:
    """Redis-backed sliding-window rate limiter using sorted sets.

    Falls back transparently to the in-process limiter on any Redis error so
    the API remains available even when Redis is down.
    """

    def __init__(
            self,
            max_requests: int,
            window_seconds: float,
            endpoint_label: str,
            fallback: "_SlidingWindowRateLimiter",
    ):
        self._max = max_requests
        self._window = window_seconds
        self._label = endpoint_label
        self._fallback = fallback
        self._redis_client: Any = None
        self._redis_unavailable = False
        self._redis_retry_at: float = 0.0

    def _get_redis(self) -> Any:
        import importlib.util as _importlib_util

        now = time.monotonic()
        if self._redis_unavailable and now < self._redis_retry_at:
            return None
        if self._redis_client is not None:
            return self._redis_client
        if _importlib_util.find_spec("redis") is None:
            self._redis_unavailable = True
            return None
        try:
            import redis as _redis

            url = redis_url(prefer_celery_broker=True)
            self._redis_client = _redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            self._redis_unavailable = False
            return self._redis_client
        except Exception:
            self._redis_unavailable = True
            self._redis_retry_at = time.monotonic() + 30.0
            return None

    def _caller_key(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        ip = forwarded_for or (request.client.host if request.client else "unknown")
        return f"ratelimit:{self._label}:{ip}"

    def is_allowed(self, request: Request) -> bool:
        rc = self._get_redis()
        if rc is None:
            return self._fallback.is_allowed(request)
        key = self._caller_key(request)
        now_ts = time.time()
        cutoff = now_ts - self._window
        try:
            pipe = rc.pipeline()
            pipe.zremrangebyscore(key, "-inf", cutoff)
            pipe.zadd(key, {str(now_ts): now_ts})
            pipe.zcard(key)
            pipe.expire(key, int(self._window) + 1)
            results = pipe.execute()
            count = int(results[2])
            return count <= self._max
        except Exception:
            self._redis_client = None
            self._redis_unavailable = True
            self._redis_retry_at = time.monotonic() + 30.0
            return self._fallback.is_allowed(request)


def _check_backtest_rate_limit(request: Request) -> None:
    """FastAPI dependency: raises 429 if backtest rate limit is exceeded."""
    if not _backtest_rate_limiter.is_allowed(request):
        raise HTTPException(
            status_code=429,
            detail="Too many backtest requests. Please wait before retrying.",
            headers={"Retry-After": str(int(_backtest_rate_limiter._window))},
        )


def _check_instance_rate_limit(request: Request) -> None:
    """FastAPI dependency: raises 429 if instance-creation rate limit is exceeded."""
    if not _instance_create_rate_limiter.is_allowed(request):
        raise HTTPException(
            status_code=429,
            detail="Too many instance creation requests. Please wait before retrying.",
            headers={"Retry-After": str(int(_instance_create_rate_limiter._window))},
        )


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


_BACKTEST_ENDPOINT_CACHE_TTL_SECONDS = _read_non_negative_int_env(
    "BACKTEST_ENDPOINT_CACHE_TTL_SECONDS", 2
)
_BACKTEST_ENDPOINT_CACHE_MAX_ENTRIES = max(
    50,
    _read_non_negative_int_env("BACKTEST_ENDPOINT_CACHE_MAX_ENTRIES", 512),
)

# Instantiate rate limiters now that _read_non_negative_int_env is defined.
_backtest_rate_limiter_fallback = _SlidingWindowRateLimiter(
    max_requests=_read_non_negative_int_env("RATE_LIMIT_BACKTEST_MAX_REQUESTS", 20),
    window_seconds=float(os.getenv("RATE_LIMIT_BACKTEST_WINDOW_SECONDS", "60") or "60"),
)
_backtest_rate_limiter: _RedisSlidingWindowRateLimiter = _RedisSlidingWindowRateLimiter(
    max_requests=_read_non_negative_int_env("RATE_LIMIT_BACKTEST_MAX_REQUESTS", 20),
    window_seconds=float(os.getenv("RATE_LIMIT_BACKTEST_WINDOW_SECONDS", "60") or "60"),
    endpoint_label="backtest",
    fallback=_backtest_rate_limiter_fallback,
)
_instance_create_rate_limiter_fallback = _SlidingWindowRateLimiter(
    max_requests=_read_non_negative_int_env("RATE_LIMIT_INSTANCE_MAX_REQUESTS", 10),
    window_seconds=float(os.getenv("RATE_LIMIT_INSTANCE_WINDOW_SECONDS", "60") or "60"),
)
_instance_create_rate_limiter: _RedisSlidingWindowRateLimiter = (
    _RedisSlidingWindowRateLimiter(
        max_requests=_read_non_negative_int_env("RATE_LIMIT_INSTANCE_MAX_REQUESTS", 10),
        window_seconds=float(
            os.getenv("RATE_LIMIT_INSTANCE_WINDOW_SECONDS", "60") or "60"
        ),
        endpoint_label="instance_create",
        fallback=_instance_create_rate_limiter_fallback,
    )
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
_strategy_resolution_recent_paths = deque(
    maxlen=max(
        1,
        _read_non_negative_int_env("STRATEGY_RESOLUTION_ALERT_WINDOW_SIZE", 200),
    )
)

# ---------------------------------------------------------------------------
# Market data cache – serves stale data when dYdX is temporarily unavailable.
# TTL: how long a fresh result is reused before a live refresh is attempted.
# Stale TTL: how long expired data may still be served as a fallback on error.
# Both are configurable via env vars; 0 disables the respective behaviour.
# ---------------------------------------------------------------------------
_MARKETS_CACHE_TTL_SECONDS = _read_non_negative_int_env("MARKETS_CACHE_TTL_SECONDS", 60)
_MARKETS_STALE_TTL_SECONDS = _read_non_negative_int_env(
    "MARKETS_STALE_TTL_SECONDS", 300
)
_MARKETS_ENDPOINT_TIMEOUT_SECONDS = float(
    _read_non_negative_int_env(
        "MARKETS_ENDPOINT_TIMEOUT_SECONDS",
        int(MARKET_RESOLUTION_TIMEOUT_SECONDS),
    )
)
_markets_cache: Dict[str, Any] = {}
_markets_cache_lock = threading.Lock()


def _markets_cache_get(*, allow_stale: bool = False) -> Optional[Dict[str, Any]]:
    """Return cached market data, optionally including expired (stale) entries.

    Returns a dict with keys ``data`` (the cached payload) and ``stale`` (bool),
    or *None* when no usable entry exists.
    """
    now = time.monotonic()
    with _markets_cache_lock:
        entry = _markets_cache.get("last")
        if not entry:
            return None
        expires_at = float(entry.get("expires_at", 0.0))
        stale_deadline = expires_at + float(_MARKETS_STALE_TTL_SECONDS)
        if expires_at > now:
            return {"data": entry["value"], "stale": False}
        if allow_stale and _MARKETS_STALE_TTL_SECONDS > 0 and stale_deadline > now:
            return {"data": entry["value"], "stale": True}
        return None


def _markets_cache_set(value: Dict[str, Any]) -> None:
    """Store a fresh market data payload in the cache."""
    if _MARKETS_CACHE_TTL_SECONDS <= 0:
        return
    now = time.monotonic()
    with _markets_cache_lock:
        _markets_cache["last"] = {
            "value": value,
            "expires_at": now + float(_MARKETS_CACHE_TTL_SECONDS),
            "updated_at": now,
        }


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


def _payload_size_bytes(payload: Any) -> int:
    try:
        return len(json.dumps(payload, default=str, separators=(",", ":")))
    except Exception:
        return -1


def _log_endpoint_timing(
        endpoint: str,
        started_at: float,
        payload: Any,
        *,
        cache_hit: bool = False,
        payload_items: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    size_bytes = _payload_size_bytes(payload)
    details: Dict[str, Any] = {
        "endpoint": endpoint,
        "duration_ms": round(elapsed_ms, 2),
        "cache_hit": cache_hit,
        "payload_bytes": size_bytes,
    }
    if payload_items is not None:
        details["payload_items"] = int(payload_items)
    if extra:
        details.update(extra)

    logger.info(
        "endpoint_perf endpoint={} duration_ms={} cache_hit={} payload_bytes={} payload_items={} details={}",
        details["endpoint"],
        details["duration_ms"],
        details["cache_hit"],
        details["payload_bytes"],
        details.get("payload_items", -1),
        details,
    )


def _endpoint_perf_headers(
        started_at: float, *, cache_hit: Optional[bool] = None
) -> Dict[str, str]:
    elapsed_ms = max(0.0, (time.perf_counter() - started_at) * 1000.0)
    headers: Dict[str, str] = {"X-Endpoint-Duration-Ms": f"{elapsed_ms:.2f}"}
    if cache_hit is not None:
        headers["X-Cache-Hit"] = "1" if cache_hit else "0"
    return headers


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


def _optional_env_int(name: str) -> Optional[int]:
    raw = os.getenv(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _runtime_db_pool_warnings(config: DatabaseConfig) -> List[str]:
    warnings: List[str] = []
    configured_max_connections = _optional_env_int("DB_MAX_CONNECTIONS")

    if (
            configured_max_connections is not None
            and configured_max_connections > 0
            and configured_max_connections < config.pool_size
    ):
        warnings.append(
            "DB_MAX_CONNECTIONS ({}) is lower than DB_POOL_SIZE ({}). "
            "Effective max_overflow is clamped to 0; increase DB_MAX_CONNECTIONS or reduce DB_POOL_SIZE.".format(
                configured_max_connections, config.pool_size
            )
        )

    if config.timeout_seconds <= 5:
        warnings.append(
            "DB_TIMEOUT is {}s; low pool timeout can amplify transient saturation into repeated persistence failures.".format(
                config.timeout_seconds
            )
        )

    if config.pool_size <= 5:
        warnings.append(
            "DB_POOL_SIZE is {}; this is small for concurrent backtests and runtime writes.".format(
                config.pool_size
            )
        )

    return warnings


class StrategyRequest(BaseModel):
    """UI-compatible strategy payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Balanced Mean Reversion",
                "category": "pairs_trading",
                "description": "Strategy with liquidity-ranked pair selection",
                "resolution": "1HOUR",
                "zscore_threshold": 1.5,
                "stats_window": 21,
                "usd_per_trade": 10.0,
                "max_positions": 5,
                "pair_selection_mode": "liquidity",
            }
        }
    )

    name: str
    category: str = "pairs_trading"
    description: str = ""
    is_public: bool = False
    user_id: int = 1
    resolution: str = "1HOUR"
    candle_resolution: Optional[str] = None
    zscore_threshold: float = 1.5
    stats_window: int = 21
    max_half_life: float = 24.0
    usd_per_trade: float = 10.0
    usd_min_collateral: float = 100.0
    close_at_zscore_cross: bool = True
    find_cointegrated_pairs: bool = True
    manage_exits: bool = True
    place_trades: bool = True
    abort_all_positions: bool = False
    max_positions: int = 5
    max_drawdown_pct: float = 15.0
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 8.0
    trailing_stop_pct: float = 2.0
    rebalance_interval_hours: int = 24
    position_timeout_hours: int = 72
    initial_amount: float = 1000.0
    starting_balance: float = 1000.0
    transaction_fee: float = 0.0005
    slippage: float = 0.001
    max_history_days: int = 90
    benchmark_symbol: str = "BTC-USD"
    risk_free_rate: float = 0.02
    pair_selection_mode: str = "liquidity"


class StrategyVersionRevertRequest(BaseModel):
    """Placeholder body for strategy version revert."""


class RuntimePreflightRequest(BaseModel):
    """Preflight payload for environment-specific runtime readiness checks."""

    credentials: BotCredentials
    trading_params: TradingParameters
    instance_name: Optional[str] = None


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

    start_date: str
    end_date: str
    strategy_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    initial_balance: float = 1000.0
    timeout_seconds: Optional[float] = None
    # 0 means "all available markets" (no cap)
    max_pairs: int = 0
    pair_selection_mode: Optional[str] = None
    trading_parameters: Optional[Dict[str, Any]] = None
    pairs: Optional[List[str]] = None
    selected_pairs: Optional[List[str]] = None
    strategy_payload_snapshot: Optional[Dict[str, Any]] = None
    bot_id: Optional[str] = None
    source: Optional[str] = None
    environment: Optional[str] = None
    requested_by_user_id: Optional[int] = None
    source_strategy_version: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None


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
        for right in markets[idx + 1:]:
            labels.append(f"{left}/{right}")
    return labels


class BacktestCreateStrategyRequest(BaseModel):
    """Create a strategy from an existing backtest."""

    name: str
    description: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)


class InMemoryStrategyStore:
    """DB-backed strategy storage with the same interface as the prior in-memory store."""

    @classmethod
    def list(cls, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.list(skip=skip, limit=limit)
        finally:
            session.close()

    @classmethod
    def list_public(cls) -> Dict[str, Any]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.list_public()
        finally:
            session.close()

    @classmethod
    def get(cls, strategy_id: int) -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.get(strategy_id)
        finally:
            session.close()

    @classmethod
    def create(
            cls,
            payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.create(payload, note="Initial version")
        finally:
            session.close()

    @classmethod
    def update(
            cls,
            strategy_id: int,
            payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.update(strategy_id, payload, note="Updated strategy")
        finally:
            session.close()

    @classmethod
    def delete(cls, strategy_id: int) -> bool:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.delete(strategy_id)
        finally:
            session.close()

    @classmethod
    def versions(cls, strategy_id: int) -> List[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.versions(strategy_id)
        finally:
            session.close()

    @classmethod
    def revert(
            cls,
            strategy_id: int,
            version_id: int,
    ) -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.revert(strategy_id, version_id)
        finally:
            session.close()


def _bot_manager_ready() -> bool:
    return bot_manager is not None


def _bot_manager_unavailable_response() -> JSONResponse:
    return api_response(
        success=False,
        message="Bot manager unavailable in this environment",
        status_code=503,
    )


def _bot_recovery_diagnostics() -> Dict[str, Any]:
    if bot_manager is None:
        return {
            "source": "unavailable",
            "attempted": 0,
            "loaded": 0,
            "skipped": 0,
            "skipped_instances": [],
            "last_error": "bot manager unavailable",
        }

    try:
        return bot_manager.get_recovery_diagnostics()
    except Exception as exc:
        logger.warning("Failed to read bot recovery diagnostics: {}", exc)
        return {
            "source": "error",
            "attempted": 0,
            "loaded": 0,
            "skipped": 0,
            "skipped_instances": [],
            "last_error": str(exc),
        }


def _bot_db_sync_diagnostics() -> Dict[str, Any]:
    if bot_manager is None:
        return {
            "active": False,
            "remaining_seconds": 0.0,
            "cooldown_seconds": _read_positive_int_env(
                "BOT_DB_SYNC_COOLDOWN_SECONDS", 20
            ),
            "log_every_seconds": _read_positive_int_env(
                "BOT_DB_SYNC_BACKOFF_LOG_EVERY_SECONDS", 15
            ),
            "state": "unavailable",
            "last_error": "bot manager unavailable",
        }

    try:
        diagnostics = bot_manager.get_db_sync_backoff_diagnostics()
        diagnostics["state"] = "ok"
        return diagnostics
    except Exception as exc:
        logger.warning("Failed to read bot DB sync diagnostics: {}", exc)
        return {
            "active": False,
            "remaining_seconds": 0.0,
            "cooldown_seconds": _read_positive_int_env(
                "BOT_DB_SYNC_COOLDOWN_SECONDS", 20
            ),
            "log_every_seconds": _read_positive_int_env(
                "BOT_DB_SYNC_BACKOFF_LOG_EVERY_SECONDS", 15
            ),
            "state": "error",
            "last_error": str(exc),
        }


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


# Custom OpenAPI schema for JWT Bearer authentication
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="dYdX Trading Bot API",
        version="1.0.0",
        description=(
            "API for managing multiple dYdX trading bot instances with JWT Authentication. "
            "Most non-auth HTTP endpoints return a standardized envelope: "
            "{success, message, data, timestamp, trace_id}."
        ),
        routes=app.routes,
    )

    components = openapi_schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas["StandardApiResponse"] = {
        "type": "object",
        "required": ["success", "message", "data", "timestamp", "trace_id"],
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "data": {
                "type": ["object", "array", "string", "number", "boolean", "null"]
            },
            "timestamp": {"type": "string", "format": "date-time"},
            "trace_id": {"type": "string"},
        },
        "description": "Standard API response envelope used by bot/runtime HTTP endpoints.",
    }

    # Add Bearer authentication scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token",
        }
    }

    # Apply Bearer auth to all endpoints
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                # Skip auth endpoints from requiring authentication
                if not any(
                        skip_path in path
                        for skip_path in ["/auth/", "/docs", "/redoc", "/openapi.json"]
                ):
                    openapi_schema["paths"][path][method]["security"] = [
                        {"BearerAuth": []}
                    ]

    # Document the standardized response envelope used by non-auth HTTP endpoints.
    for path, path_item in openapi_schema.get("paths", {}).items():
        if path.startswith("/auth/") or path.startswith("/api/v1/auth"):
            continue

        if not (path in {"/health", "/ready"} or path.startswith("/api/v1/")):
            continue

        for method, operation in path_item.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                continue

            responses = operation.get("responses", {})
            success_response = responses.get("200")
            if not isinstance(success_response, dict):
                continue

            content = success_response.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema")
            if schema is None:
                continue

            if isinstance(schema, dict):
                all_of = schema.get("allOf")
                if isinstance(all_of, list) and any(
                        isinstance(item, dict)
                        and item.get("$ref") == "#/components/schemas/StandardApiResponse"
                        for item in all_of
                ):
                    continue

            json_content["schema"] = {
                "allOf": [
                    {"$ref": "#/components/schemas/StandardApiResponse"},
                    {
                        "type": "object",
                        "properties": {
                            "data": schema,
                        },
                    },
                ]
            }
            content["application/json"] = json_content
            success_response["content"] = content
            operation["responses"]["200"] = success_response
            operation["x-response-envelope"] = "StandardApiResponse"

    app.openapi_schema = openapi_schema
    return app.openapi_schema


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown lifecycle for the Bot API."""
    global bot_manager_monitor_task

    # Runtime default: route long-running backtests through Celery. Operators can
    # explicitly opt into the legacy in-process backend with BACKTEST_WORKER_BACKEND=asyncio.
    if "BACKTEST_WORKER_BACKEND" not in os.environ:
        os.environ["BACKTEST_WORKER_BACKEND"] = "celery"
        try:
            from src.infrastructure.workers.celery_app import celery_app

            _ping = celery_app.control.ping(timeout=2.0, limit=1)
            if _ping:
                logger.info("Celery broker reachable — backtest worker backend: celery")
            else:
                logger.warning(
                    "Celery ping returned no workers — backtests will remain queued until a worker is online"
                )
        except Exception as _celery_probe_err:
            logger.warning(
                "Celery broker not reachable ({}); backtest enqueue will fail until the broker is available",
                _celery_probe_err,
            )

    # Safety guard: API_BYPASS_AUTH must never be enabled outside explicit dev/test environments.
    validate_auth_bypass_configuration()
    if is_auth_bypass_enabled():
        logger.warning(
            "API_BYPASS_AUTH=true — authentication is DISABLED (environment={}). "
            "Allowed only for explicit local/dev/test environments.",
            current_environment_name().strip().lower() or "development",
        )

    logger.info("Starting Bot API Server...")
    runtime_db_config = DatabaseConfig()
    logger.info(
        "Runtime DB target: type={} host={} port={} name={} mode={} source={}",
        runtime_db_config.db_type,
        runtime_db_config.db_host,
        runtime_db_config.db_port,
        runtime_db_config.db_name,
        runtime_db_config.cutover_mode,
        runtime_db_config.field_source,
    )
    logger.info(
        "Runtime DB pool: pool_size={} max_overflow={} timeout_seconds={} max_connections={}",
        runtime_db_config.pool_size,
        runtime_db_config.max_overflow,
        runtime_db_config.timeout_seconds,
        runtime_db_config.pool_size + runtime_db_config.max_overflow,
    )
    pool_warnings = _runtime_db_pool_warnings(runtime_db_config)
    for warning in pool_warnings:
        logger.warning("Runtime DB pool config warning: {}", warning)
    if not db.health_check():
        raise RuntimeError("Bot database health check failed during API startup")
    db.run_pending_migrations()
    # Metadata creation remains a compatibility safety net for ORM-only tables;
    # migrations run first so an empty database cannot be mistaken for legacy.
    db.create_all_tables()
    db.ensure_schema_compatibility()
    db.verify_required_tables()
    try:
        with backtest_service_scope() as service:
            backtest_recovery = await service.auto_recover_interrupted_runs(
                _broadcast_backtest_progress
            )
        logger.info(
            "Backtest auto-recovery completed: mode={} candidates={} restarted={} marked_failed={}",
            backtest_recovery.get("mode"),
            backtest_recovery.get("candidate_count"),
            backtest_recovery.get("restarted_count"),
            backtest_recovery.get("marked_failed_count"),
        )
    except Exception as exc:
        logger.warning("Backtest auto-recovery failed during API startup: {}", exc)
    if bot_manager is not None:
        bot_manager.set_status_event_publisher(broadcast_strategy_status)
        await bot_manager.cleanup_dead_processes()
        live_recovery = await bot_manager.auto_recover_live_runtimes()
        logger.info(
            "Live runtime auto-recovery completed: checked={} verified={} restarted={} marked_error={}",
            live_recovery.get("checked"),
            len(live_recovery.get("verified_running", [])),
            len(live_recovery.get("restarted", [])),
            len(live_recovery.get("marked_error", [])),
        )
        if bot_manager_monitor_task is None or bot_manager_monitor_task.done():
            bot_manager_monitor_task = async_job_manager.create_supervised_task(
                _bot_manager_monitor_loop(),
                job_type="readiness_check",
                job_id="bot-manager-monitor",
                metadata={"component": "bot_manager"},
                auto_complete=False,
            )
    else:
        logger.warning(
            "Bot manager unavailable; bot-instance endpoints may be degraded"
        )
    logger.info("Bot API Server ready")

    try:
        yield
    finally:
        if bot_manager_monitor_task is not None:
            bot_manager_monitor_task.cancel()
            try:
                await bot_manager_monitor_task
            except asyncio.CancelledError:
                pass
            finally:
                bot_manager_monitor_task = None
        await async_job_manager.cancel_all(reason="api shutdown")
        if bot_manager is not None:
            await bot_manager.shutdown(
                stop_active=os.getenv("BOT_STOP_RUNTIME_ON_API_SHUTDOWN", "false")
                            .strip()
                            .lower()
                            in {"1", "true", "yes", "on"}
            )
        logger.info("Shutting down Bot API Server...")


# Initialize FastAPI app
app = FastAPI(
    title="dYdX Trading Bot API",
    description="API for managing multiple dYdX trading bot instances with JWT Authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Set custom OpenAPI schema
app.openapi = custom_openapi

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication routes
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


# ============================================================================
# API RESPONSE WRAPPER
# ============================================================================


def api_response(
        success: bool,
        data=None,
        message: str = "",
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
):
    """Standardized API response format"""
    if status_code >= 500:
        # Never expose raw exceptions/DB internals in client-facing 5xx responses.
        message = INTERNAL_ERROR_MESSAGE
    trace_id = trace_id_ctx.get()
    response_data = {
        "success": success,
        "message": message,
        "data": data,
        "timestamp": utc_now_iso(),
        "trace_id": trace_id,
    }
    response = JSONResponse(
        content=jsonable_encoder(response_data),
        status_code=status_code,
    )
    for header_name, header_value in (headers or {}).items():
        response.headers[header_name] = str(header_value)
    return response


@app.post("/api/v1/runtime/preflight")
async def runtime_preflight(
        request: RuntimePreflightRequest,
        current_user: User = Depends(get_current_active_user),
):
    """Evaluate whether a live runtime is ready to start on the selected environment."""
    del current_user
    try:
        assert_supported_live_risk_controls(request.trading_params.model_dump())
    except ValueError as exc:
        return api_response(
            success=False,
            message=f"Validation error: {exc}",
            data={"error": "UNSUPPORTED_RISK_CONTROL"},
            status_code=422,
        )

    environment = (
        "mainnet"
        if str(request.credentials.chain_id).lower().startswith("dydx-mainnet")
        else "testnet"
    )
    blockers: list[str] = []
    warnings: list[str] = []
    subaccount_number = int(request.trading_params.subaccount_number or 0)
    available_collateral = 0.0
    equity = 0.0
    open_positions = 0
    wallet_ready = False
    account_exists = False

    try:
        client = await connect_dydx_runtime(
            address=request.credentials.address,
            mnemonic=request.credentials.mnemonic,
            is_testnet=request.trading_params.is_testnet,
        )
        wallet_ready = client.wallet is not None
        if not wallet_ready:
            blockers.append(
                "Unable to derive a dYdX wallet from the provided credentials."
            )

        try:
            response = await client.indexer_account.account.get_subaccount(
                request.credentials.address,
                subaccount_number,
            )
            subaccount = response.get("subaccount") or {}
            available_collateral = float(subaccount.get("freeCollateral") or 0.0)
            equity = float(subaccount.get("equity") or 0.0)
            open_positions = len(subaccount.get("openPerpetualPositions") or {})
            account_exists = True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                blockers.append(
                    f"Subaccount {subaccount_number} is not initialized or funded on {environment}."
                )
            else:
                raise

        usd_per_trade = float(request.trading_params.usd_per_trade or 0.0)
        usd_min_collateral = float(request.trading_params.usd_min_collateral or 0.0)
        capital_allocation_usd = float(
            request.trading_params.capital_allocation_usd or 0.0
        )

        # P1.6: Enhanced collateral guardrails
        # Recommended minimum buffer: 25% above required minimums to prevent accidental liquidation
        COLLATERAL_SAFETY_BUFFER_RATIO = 1.25
        required_collateral_with_buffer = (
                max(usd_per_trade, usd_min_collateral) * COLLATERAL_SAFETY_BUFFER_RATIO
        )

        if account_exists and available_collateral < usd_per_trade:
            blockers.append(
                f"Free collateral ${available_collateral:.2f} is below per-trade size ${usd_per_trade:.2f}."
            )
        if account_exists and available_collateral < usd_min_collateral:
            blockers.append(
                f"Free collateral ${available_collateral:.2f} is below minimum collateral ${usd_min_collateral:.2f}."
            )
        if (
                account_exists
                and capital_allocation_usd > 0
                and available_collateral < capital_allocation_usd
        ):
            warnings.append(
                f"Configured capital allocation ${capital_allocation_usd:.2f} exceeds current free collateral ${available_collateral:.2f}."
            )

        # P1.6: Warn if available collateral is below safety buffer
        if account_exists and available_collateral < required_collateral_with_buffer:
            warnings.append(
                f"Available collateral ${available_collateral:.2f} is below recommended buffer (25% above minimum). Consider funding before production deployment."
            )

        # P1.6: Warn if trade size is aggressive relative to collateral (>10% per trade)
        if account_exists and usd_per_trade > 0:
            trade_size_ratio = (
                usd_per_trade / available_collateral
                if available_collateral > 0
                else 1.0
            )
            if trade_size_ratio > 0.10:
                warnings.append(
                    f"Trade size ${usd_per_trade:.2f} is {(trade_size_ratio * 100):.1f}% of available collateral. Higher risk if multiple positions open simultaneously."
                )

        # P1.6: Note subaccount isolation for operator awareness
        if subaccount_number > 0:
            warnings.append(
                f"Subaccount {subaccount_number} is isolated from subaccount 0. Ensure strategy capital is segregated intentionally."
            )

        data = {
            "selected_runtime_network": environment,
            "selected_subaccount": subaccount_number,
            "wallet_ready": wallet_ready,
            "account_exists": account_exists,
            "available_collateral": available_collateral,
            "equity": equity,
            "open_positions": open_positions,
            "usd_per_trade": usd_per_trade,
            "usd_min_collateral": usd_min_collateral,
            "capital_allocation_usd": capital_allocation_usd,
            "trade_size_to_collateral_ratio": (
                round(usd_per_trade / available_collateral, 4)
                if available_collateral > 0
                else None
            ),
            "sufficient_for_trade_size": available_collateral >= usd_per_trade,
            "sufficient_for_min_collateral": available_collateral >= usd_min_collateral,
            "ready": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
        }
        return api_response(
            success=True,
            data=data,
            message="Runtime readiness evaluated",
        )
    except Exception as exc:
        logger.error("Runtime preflight failed: {}", exc)
        return api_response(
            success=True,
            data={
                "selected_runtime_network": environment,
                "selected_subaccount": subaccount_number,
                "wallet_ready": False,
                "account_exists": False,
                "available_collateral": 0.0,
                "equity": 0.0,
                "open_positions": 0,
                "usd_per_trade": float(request.trading_params.usd_per_trade or 0.0),
                "usd_min_collateral": float(
                    request.trading_params.usd_min_collateral or 0.0
                ),
                "capital_allocation_usd": float(
                    request.trading_params.capital_allocation_usd or 0.0
                ),
                "trade_size_to_collateral_ratio": None,
                "sufficient_for_trade_size": False,
                "sufficient_for_min_collateral": False,
                "ready": False,
                "blockers": [str(exc)],
                "warnings": [],
            },
            message="Runtime readiness evaluated with blockers",
        )


def _resolve_operator_name(current_user: Optional[User]) -> str:
    if current_user is None:
        return "system"
    return (
            str(getattr(current_user, "full_name", "") or "").strip()
            or str(getattr(current_user, "username", "") or "").strip()
            or str(getattr(current_user, "email", "") or "").strip()
            or "system"
    )


def _resolve_action_details(message: Optional[str], fallback: str) -> str:
    text = str(message or "").strip()
    return text or fallback


def _build_bot_lifecycle_context(
        instance_id: str,
        config_payload: Optional[Dict[str, Any]],
        current_user: Optional[User],
        *,
        details: str = "",
        reason: str = "",
) -> Dict[str, Any]:
    payload = config_payload or {}
    trading_params = payload.get("trading_params") or {}
    credentials = payload.get("credentials") or {}
    is_testnet = bool(trading_params.get("is_testnet", True))
    return {
        "instance_id": instance_id,
        "instance_name": payload.get("instance_name") or instance_id,
        "strategy": trading_params.get("strategy", "unknown"),
        "is_testnet": is_testnet,
        "account_address": credentials.get("address"),
        "operator": _resolve_operator_name(current_user),
        "details": details,
        "reason": reason,
    }


def _send_bot_lifecycle_notification(
        action: str,
        instance_id: str,
        config_payload: Optional[Dict[str, Any]],
        current_user: Optional[User],
        *,
        success: bool = True,
        details: str = "",
        reason: str = "",
) -> bool:
    payload = config_payload or {}
    telegram = payload.get("telegram") or {}
    messenger = TelegramMessenger(
        bot_token=str(telegram.get("token") or "").strip(),
        chat_id=str(telegram.get("chat_id") or "").strip(),
        instance_id=instance_id,
        environment=os.getenv("ENVIRONMENT", "development"),
    )
    return messenger.send_lifecycle_message(
        action,
        _build_bot_lifecycle_context(
            instance_id,
            payload,
            current_user,
            details=details,
            reason=reason,
        ),
        success=success,
    )


def _persist_bot_status_and_event(
        instance_id: str,
        *,
        status: Optional[BotStatusEnum] = None,
        process_id: Optional[int] = None,
        event_type: Optional[str] = None,
        severity: str = "info",
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Persist lifecycle status/event updates and return the current bot config payload."""
    session = None
    try:
        session = db.get_session()
        uow = UnitOfWork(session)
        bot = uow.bots.get_by_instance_id(instance_id)
        if bot is None:
            return None

        if status is not None:
            uow.bots.update_status(instance_id, status, process_id=process_id)
            bot = uow.bots.get_by_instance_id(instance_id)
            if bot is None:
                return None

        if event_type:
            uow.events.log_event(
                int(bot.id),  # type: ignore[arg-type]
                event_type,
                severity,
                message,
                details=details,
            )

        # The stored config is encrypted at rest; decrypt before returning so the
        # notification/context helpers (which read telegram.token/credentials)
        # observe plaintext secrets.
        raw_config = dict(bot.config) if bot.config is not None else {}  # type: ignore[arg-type]
        return open_config_secrets(raw_config)
    except Exception as db_error:
        logger.warning(
            "Failed to persist bot lifecycle state for {}: {}",
            instance_id,
            db_error,
        )
        if session is not None:
            session.rollback()
        return None
    finally:
        if session is not None:
            session.close()


@app.middleware("http")
async def request_trace_logging_middleware(request: Request, call_next):
    """Attach per-request trace IDs and emit verbose request logs in development."""
    inbound_trace_id = (request.headers.get("X-Trace-Id") or "").strip()
    trace_id = inbound_trace_id or str(uuid4())
    token = trace_id_ctx.set(trace_id)
    started = time.perf_counter()
    is_development = os.getenv("ENVIRONMENT", "development").lower() == "development"
    query = (request.url.query or "").strip()
    if len(query) > 256:
        query = f"{query[:253]}..."
    client = request.client.host if request.client else "unknown"

    try:
        with logger.contextualize(trace_id=trace_id):
            if is_development:
                logger.debug(
                    "request_started trace_id={} method={} path={} query={} client={}",
                    trace_id,
                    request.method,
                    request.url.path,
                    query or "-",
                    client,
                )

            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id

            if is_development:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                log_message = (
                    "request_completed trace_id={} method={} path={} query={} status={} "
                    "duration_ms={:.2f} client={}"
                )
                log_args = (
                    trace_id,
                    request.method,
                    request.url.path,
                    query or "-",
                    response.status_code,
                    elapsed_ms,
                    client,
                )
                if response.status_code >= 500:
                    logger.error(log_message, *log_args)
                elif _is_expected_strategy_runtime_probe_404(
                        request, response.status_code
                ):
                    logger.debug(log_message, *log_args)
                elif response.status_code >= 400:
                    logger.warning(log_message, *log_args)
                else:
                    logger.info(log_message, *log_args)

            return response
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        logger.exception(
            "request_failed trace_id={} method={} path={} query={} duration_ms={:.2f} client={}",
            trace_id,
            request.method,
            request.url.path,
            query or "-",
            elapsed_ms,
            client,
        )
        raise
    finally:
        trace_id_ctx.reset(token)


def _is_expected_strategy_runtime_probe_404(request: Request, status_code: int) -> bool:
    if status_code != 404 or request.method != "GET":
        return False
    return (
            re.fullmatch(
                r"/api/v1/bots/strategy-\d+-\d+(?:/stats)?", request.url.path or ""
            )
            is not None
    )


# ============================================================================
# BOT INSTANCE MANAGEMENT ENDPOINTS
# ============================================================================


@app.post("/api/v1/bots", response_model=BotOperationResult)
async def create_bot_instance(
        config: BotInstanceConfig,
        current_user: User = Depends(get_current_active_user),
        _rate: None = Depends(_check_instance_rate_limit),
):
    """Create a new bot instance"""
    try:
        assert_supported_live_risk_controls(config.trading_params.model_dump())
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        result = await bot_manager.create_instance(config)

        if result.success:
            # Persist DB-backed runtime config. Worker startup requires this row.
            persisted_config: Dict[str, Any] = {
                "instance_name": config.instance_name,
                "credentials": (
                    config.credentials.model_dump() if config.credentials else {}
                ),
                "telegram": (config.telegram.model_dump() if config.telegram else {}),
                "trading_params": (
                    config.trading_params.model_dump() if config.trading_params else {}
                ),
                "backtesting_params": (
                    config.backtesting_params.model_dump()
                    if config.backtesting_params
                    else {}
                ),
            }
            session = None
            try:
                session = db.get_session()
                uow = UnitOfWork(session)

                # Create database record if the manager has not already done so.
                bot_db = uow.bots.get_by_instance_id(config.instance_id)
                config_meta = bot_manager._build_config_meta(persisted_config)
                # Seal credential/telegram blocks at the persistence boundary so
                # secrets are encrypted at rest. persisted_config itself stays
                # plaintext for the lifecycle notification below.
                stored_config = seal_config_secrets(
                    {**persisted_config, "config_meta": config_meta}
                )
                if bot_db is None:
                    bot_db = uow.bots.create_bot(
                        instance_id=config.instance_id,
                        network=(
                            "testnet"
                            if (
                                    config.trading_params
                                    and config.trading_params.is_testnet
                            )
                            else "mainnet"
                        ),
                        strategy=(
                            config.trading_params.strategy
                            if config.trading_params
                            else "default"
                        ),
                        config=stored_config,
                    )
                else:
                    bot_db.config = stored_config
                    session.commit()

                try:
                    uow.events.log_event(
                        int(bot_db.id),  # type: ignore[arg-type]
                        "bot_created",
                        "info",
                        f"Bot instance created via API: {config.instance_id}",
                        details={"instance_name": config.instance_name},
                    )
                except Exception as event_error:
                    logger.warning(
                        "Failed to record bot_created event for '{}': {}",
                        config.instance_id,
                        event_error,
                    )
                logger.info(
                    f"Bot instance '{config.instance_id}' persisted to database"
                )
            except Exception as db_error:
                logger.error(f"Failed to persist bot to database: {db_error}")
                if session is not None:
                    session.rollback()
                try:
                    await bot_manager.delete_instance(config.instance_id)
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to clean up bot instance '{}' after DB persistence failure: {}",
                        config.instance_id,
                        cleanup_error,
                    )
                return api_response(
                    success=False,
                    message=(
                        "Failed to persist DB-backed bot configuration; "
                        "instance was not created"
                    ),
                    status_code=500,
                )
            finally:
                if session is not None:
                    session.close()

            _send_bot_lifecycle_notification(
                "created",
                config.instance_id,
                persisted_config,
                current_user,
                success=True,
                details="Runtime instance created and ready to start.",
            )

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{config.instance_id}' created successfully",
            )
        else:
            return api_response(success=False, message=result.message, status_code=400)

    except Exception as e:
        if isinstance(e, ValueError):
            return api_response(
                success=False,
                message=f"Validation error: {str(e)}",
                data={"error": "UNSUPPORTED_RISK_CONTROL"},
                status_code=422,
            )
        logger.error(f"Error creating bot instance: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/bots", response_model=BotInstanceList)
async def list_bot_instances(current_user: User = Depends(get_current_active_user)):
    """Get list of all bot instances"""
    try:
        if bot_manager is None:
            return api_response(
                success=True,
                data={"bots": [], "total": 0},
                message="Retrieved 0 bot instances (bot manager unavailable)",
            )
        instances = await bot_manager.list_instances()

        return api_response(
            success=True,
            data={
                "bots": [instance.model_dump() for instance in instances],
                "total": len(instances),
            },
            message=f"Retrieved {len(instances)} bot instances",
        )

    except Exception as e:
        logger.error(f"Error listing bot instances: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/bots/{instance_id}", response_model=BotInstanceStatus)
async def get_bot_instance(
        instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get specific bot instance status"""
    try:
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        instance = await bot_manager.get_instance_status(instance_id)

        if instance is None:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        return api_response(
            success=True,
            data=instance.model_dump(),
            message=f"Retrieved status for bot instance '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.delete("/api/v1/bots/{instance_id}")
async def delete_bot_instance(
        instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Delete bot instance"""
    try:
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        existing_config = _persist_bot_status_and_event(
            instance_id,
            event_type=None,
        )
        result = await bot_manager.delete_instance(instance_id)

        if result.success:
            session = None
            try:
                session = db.get_session()
                uow = UnitOfWork(session)
                bot = uow.bots.get_by_instance_id(instance_id)
                if bot is not None:
                    uow.events.log_event(
                        int(bot.id),  # type: ignore[arg-type]
                        "bot_deleted",
                        "info",
                        "Bot instance deleted via API",
                    )
                uow.bots.delete_bot(instance_id)
            except Exception as db_error:
                logger.warning(
                    f"Failed to delete bot instance '{instance_id}' from database: {db_error}"
                )
                if session is not None:
                    session.rollback()
            finally:
                if session is not None:
                    session.close()
            _send_bot_lifecycle_notification(
                "deleted",
                instance_id,
                existing_config,
                current_user,
                success=True,
                details=_resolve_action_details(
                    result.message,
                    "Runtime definition deleted successfully.",
                ),
            )
            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' deleted successfully",
            )
        else:
            _send_bot_lifecycle_notification(
                "delete",
                instance_id,
                existing_config,
                current_user,
                success=False,
                details=_resolve_action_details(
                    result.error or result.message,
                    "Runtime deletion failed.",
                ),
            )
            return api_response(success=False, message=result.message, status_code=400)

    except Exception as e:
        logger.error(f"Error deleting bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# BOT CONTROL ENDPOINTS
# ============================================================================


@app.post("/api/v1/bots/{instance_id}/start")
async def start_bot_instance(
        instance_id: str,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_active_user),
):
    """Start bot instance"""
    try:
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        result = await bot_manager.start_instance(instance_id)

        if result.success:
            # Update database
            persisted_config = _persist_bot_status_and_event(
                instance_id,
                status=BotStatusEnum.RUNNING,
                process_id=(result.data.get("process_id") if result.data else None),
                event_type="bot_started",
                severity="info",
                message=f"Bot started via API (PID: {result.data.get('process_id') if result.data else 'unknown'})",
                details={
                    "process_id": result.data.get("process_id") if result.data else None
                },
            )
            _send_bot_lifecycle_notification(
                "started",
                instance_id,
                persisted_config,
                current_user,
                success=True,
                details=_resolve_action_details(
                    result.message,
                    "Runtime process started successfully.",
                ),
            )

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' started successfully",
            )
        else:
            persisted_config = _persist_bot_status_and_event(
                instance_id,
                status=BotStatusEnum.ERROR,
                process_id=None,
                event_type="bot_start_failed",
                severity="error",
                message=_resolve_action_details(result.message, "Bot failed to start"),
                details={"error": result.error or result.message},
            )
            _send_bot_lifecycle_notification(
                "start",
                instance_id,
                persisted_config,
                current_user,
                success=False,
                details=_resolve_action_details(
                    result.error or result.message,
                    "Runtime start failed before reaching RUNNING state.",
                ),
            )
            return api_response(success=False, message=result.message, status_code=400)

    except Exception as e:
        logger.error(f"Error starting bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/bots/{instance_id}/stop")
async def stop_bot_instance(
        instance_id: str,
        force: bool = False,
        current_user: User = Depends(get_current_active_user),
):
    """Stop bot instance"""
    try:
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        result = await bot_manager.stop_instance(instance_id, force=force)

        if result.success:
            # Update database
            persisted_config = _persist_bot_status_and_event(
                instance_id,
                status=BotStatusEnum.STOPPED,
                process_id=None,
                event_type="bot_stopped",
                severity="info",
                message=f"Bot stopped via API (force={force})",
                details={"force": force},
            )
            _send_bot_lifecycle_notification(
                "stopped",
                instance_id,
                persisted_config,
                current_user,
                success=True,
                details=_resolve_action_details(
                    result.message,
                    "Runtime process stopped successfully.",
                ),
                reason="Force stop" if force else "Operator stop",
            )

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' stopped successfully",
            )
        else:
            persisted_config = _persist_bot_status_and_event(
                instance_id,
                status=BotStatusEnum.ERROR,
                process_id=None,
                event_type="bot_stop_failed",
                severity="error",
                message=_resolve_action_details(result.message, "Bot failed to stop"),
                details={"error": result.error or result.message, "force": force},
            )
            _send_bot_lifecycle_notification(
                "stop",
                instance_id,
                persisted_config,
                current_user,
                success=False,
                details=_resolve_action_details(
                    result.error or result.message,
                    "Runtime stop request failed.",
                ),
                reason="Force stop" if force else "Operator stop",
            )
            return api_response(success=False, message=result.message, status_code=400)

    except Exception as e:
        logger.error(f"Error stopping bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/bots/{instance_id}/restart")
async def restart_bot_instance(
        instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Restart bot instance"""
    try:
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        # Stop first
        stop_result = await bot_manager.stop_instance(instance_id, force=False)
        if not stop_result.success:
            persisted_config = _persist_bot_status_and_event(
                instance_id,
                status=BotStatusEnum.ERROR,
                process_id=None,
                event_type="bot_restart_failed",
                severity="error",
                message=_resolve_action_details(
                    stop_result.message,
                    "Failed to stop runtime during restart",
                ),
                details={
                    "phase": "stop",
                    "error": stop_result.error or stop_result.message,
                },
            )
            _send_bot_lifecycle_notification(
                "restart",
                instance_id,
                persisted_config,
                current_user,
                success=False,
                details=_resolve_action_details(
                    stop_result.error or stop_result.message,
                    "Restart failed during stop phase.",
                ),
                reason="Operator restart",
            )
            return api_response(
                success=False,
                message=f"Failed to stop instance: {stop_result.message}",
                status_code=400,
            )

        # Wait a moment
        await asyncio.sleep(2)

        # Start again
        start_result = await bot_manager.start_instance(instance_id)

        if start_result.success:
            persisted_config = _persist_bot_status_and_event(
                instance_id,
                status=BotStatusEnum.RUNNING,
                process_id=(
                    start_result.data.get("process_id") if start_result.data else None
                ),
                event_type="bot_restarted",
                severity="info",
                message=f"Bot restarted via API (PID: {start_result.data.get('process_id') if start_result.data else 'unknown'})",
                details={
                    "process_id": (
                        start_result.data.get("process_id")
                        if start_result.data
                        else None
                    )
                },
            )
            _send_bot_lifecycle_notification(
                "restarted",
                instance_id,
                persisted_config,
                current_user,
                success=True,
                details=_resolve_action_details(
                    start_result.message,
                    "Runtime restarted successfully.",
                ),
                reason="Operator restart",
            )
            return api_response(
                success=True,
                data=start_result.model_dump(),
                message=f"Bot instance '{instance_id}' restarted successfully",
            )
        else:
            persisted_config = _persist_bot_status_and_event(
                instance_id,
                status=BotStatusEnum.ERROR,
                process_id=None,
                event_type="bot_restart_failed",
                severity="error",
                message=_resolve_action_details(
                    start_result.message,
                    "Failed to start runtime during restart",
                ),
                details={
                    "phase": "start",
                    "error": start_result.error or start_result.message,
                },
            )
            _send_bot_lifecycle_notification(
                "restart",
                instance_id,
                persisted_config,
                current_user,
                success=False,
                details=_resolve_action_details(
                    start_result.error or start_result.message,
                    "Restart failed during start phase.",
                ),
                reason="Operator restart",
            )
            return api_response(
                success=False,
                message=f"Failed to start instance: {start_result.message}",
                status_code=400,
            )

    except Exception as e:
        logger.error(f"Error restarting bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# DATABASE & HISTORY ENDPOINTS
# ============================================================================


@app.get("/api/v1/bots/{instance_id}/history")
async def get_bot_history(
        instance_id: str,
        days: int = 7,
        current_user: User = Depends(get_current_active_user),
):
    """Get bot event history"""
    try:
        session = db.get_session()
        uow = UnitOfWork(session)

        # Get bot first to verify it exists
        bot = uow.bots.get_by_instance_id(instance_id)
        if not bot:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        # Get events
        events = uow.events.get_bot_events(int(bot.id), days=days)  # type: ignore[arg-type]

        return api_response(
            success=True,
            data={
                "instance_id": instance_id,
                "total_events": len(events),
                "days_requested": days,
                "events": [
                    {
                        "timestamp": e.created_at.isoformat(),
                        "event_type": e.event_type,
                        "severity": e.severity,
                        "message": e.message,
                        "details": e.details,
                    }
                    for e in events
                ],
            },
            message=f"Retrieved {len(events)} events for bot '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot history for {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )
    finally:
        session.close()


@app.get("/api/v1/bots/{instance_id}/jobs")
async def get_bot_jobs(
        instance_id: str,
        days: int = 7,
        current_user: User = Depends(get_current_active_user),
):
    """Get bot job history"""
    try:
        session = db.get_session()
        uow = UnitOfWork(session)

        # Get bot first
        bot = uow.bots.get_by_instance_id(instance_id)
        if not bot:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        # Get jobs
        jobs = uow.jobs.get_job_history(int(bot.id), days=days)  # type: ignore[arg-type]

        # Calculate job statistics
        total_jobs = len(jobs)

        def _job_status_value(job) -> str:
            return str(getattr(job.status, "value", job.status)).lower()

        completed_jobs = len([j for j in jobs if _job_status_value(j) == "completed"])
        failed_jobs = len([j for j in jobs if _job_status_value(j) == "failed"])
        cancelled_jobs = len([j for j in jobs if _job_status_value(j) == "cancelled"])
        pending_jobs = len([j for j in jobs if _job_status_value(j) == "pending"])
        running_jobs = len([j for j in jobs if _job_status_value(j) == "running"])

        return api_response(
            success=True,
            data={
                "instance_id": instance_id,
                "statistics": {
                    "total_jobs": total_jobs,
                    "completed": completed_jobs,
                    "failed": failed_jobs,
                    "cancelled": cancelled_jobs,
                    "pending": pending_jobs,
                    "running": running_jobs,
                },
                "jobs": [
                    {
                        "job_id": j.job_id,
                        "job_type": j.job_type,
                        "status": _job_status_value(j),
                        "progress_pct": float(getattr(j, "progress_pct", 0.0) or 0.0),
                        "process_id": getattr(j, "process_id", None),
                        "execution_time_ms": getattr(j, "execution_time_ms", None),
                        "retry_count": f"{j.retry_count}/{j.max_retries}",
                        "created_at": j.created_at.isoformat(),
                        "updated_at": (
                            j.updated_at.isoformat()
                            if getattr(j, "updated_at", None)
                            else None
                        ),
                        "started_at": (
                            j.started_at.isoformat()
                            if j.started_at is not None
                            else None
                        ),
                        "completed_at": (
                            j.completed_at.isoformat()
                            if j.completed_at is not None
                            else None
                        ),
                        "error_message": j.error_message,
                        "cancellation_reason": getattr(j, "cancellation_reason", None),
                        "metadata": dict(getattr(j, "metadata_json", None) or {}),
                    }
                    for j in jobs
                ],
            },
            message=f"Retrieved {total_jobs} jobs for bot '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot jobs for {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )
    finally:
        session.close()


@app.get("/api/v1/bots/{instance_id}/trades")
async def get_bot_trades(
        instance_id: str,
        status: Optional[str] = None,
        current_user: User = Depends(get_current_active_user),
):
    """Get bot trades"""
    try:
        session = db.get_session()
        uow = UnitOfWork(session)

        # Get bot first
        bot = uow.bots.get_by_instance_id(instance_id)
        if not bot:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        # Get trades
        trades = uow.trades.get_bot_trades(int(bot.id))  # type: ignore[arg-type]

        # Filter by status if requested
        if status:
            trades = [t for t in trades if str(t.status) == status.upper()]

        return api_response(
            success=True,
            data={
                "instance_id": instance_id,
                "total_trades": len(trades),
                "filter_status": status,
                "trades": [
                    {
                        "trade_id": t.trade_id,
                        "pair1": t.pair1,
                        "pair2": t.pair2,
                        "status": t.status,
                        "entry_price1": (
                            float(t.entry_price1) if t.entry_price1 is not None else None  # type: ignore[arg-type]
                        ),
                        "entry_price2": (
                            float(t.entry_price2) if t.entry_price2 is not None else None  # type: ignore[arg-type]
                        ),
                        "exit_price1": float(t.exit_price1) if t.exit_price1 is not None else None,
                        # type: ignore[arg-type]
                        "exit_price2": float(t.exit_price2) if t.exit_price2 is not None else None,
                        # type: ignore[arg-type]
                        "entry_cost": float(t.entry_cost) if t.entry_cost is not None else None,
                        # type: ignore[arg-type]
                        "exit_proceeds": (
                            float(t.exit_proceeds) if t.exit_proceeds is not None else None  # type: ignore[arg-type]
                        ),
                        "profit_loss": float(t.profit_loss) if t.profit_loss is not None else None,
                        # type: ignore[arg-type]
                        "profit_loss_percentage": (
                            float(t.profit_loss_percentage)  # type: ignore[arg-type]
                            if t.profit_loss_percentage is not None
                            else None
                        ),
                        "opened_at": (
                            t.opened_at.isoformat() if t.opened_at is not None else None
                        ),
                        "closed_at": (
                            t.closed_at.isoformat() if t.closed_at is not None else None
                        ),
                        "duration_seconds": t.duration_seconds,
                    }
                    for t in trades
                ],
            },
            message=f"Retrieved {len(trades)} trades for bot '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot trades for {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )
    finally:
        session.close()


@app.get("/api/v1/bots/{instance_id}/stats")
async def get_bot_stats(
        instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get bot statistics"""
    try:
        session = db.get_session()
        uow = UnitOfWork(session)

        # Get bot first
        bot = uow.bots.get_by_instance_id(instance_id)
        if not bot:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        # Get bot statistics
        bot_stats = uow.bots.get_statistics(instance_id)

        # Get trade statistics
        trade_stats = uow.trades.get_trade_statistics(int(bot.id))  # type: ignore[arg-type]

        return api_response(
            success=True,
            data={
                "instance_id": instance_id,
                "bot_statistics": {
                    "total_trades": bot_stats.get("total_trades", 0),
                    "successful_trades": bot_stats.get("successful_trades", 0),
                    "failed_trades": bot_stats.get("failed_trades", 0),
                    "total_profit_loss": float(bot_stats.get("total_profit_loss", 0)),
                    "win_rate": float(bot_stats.get("win_rate", 0)),
                    "uptime_seconds": (
                        bot.uptime_seconds if hasattr(bot, "uptime_seconds") else None
                    ),
                },
                "trade_statistics": {
                    "total_trades": trade_stats.get("total_trades", 0),
                    "winning_trades": trade_stats.get("winning_trades", 0),
                    "losing_trades": trade_stats.get("losing_trades", 0),
                    "total_profit": float(trade_stats.get("total_profit", 0)),
                    "total_loss": float(trade_stats.get("total_loss", 0)),
                    "net_profit": float(trade_stats.get("net_profit", 0)),
                    "average_profit": float(trade_stats.get("average_profit", 0)),
                    "win_rate": float(trade_stats.get("win_rate", 0)),
                    "average_duration_seconds": trade_stats.get(
                        "average_duration_seconds", 0
                    ),
                },
            },
            message=f"Retrieved statistics for bot '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot statistics for {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )
    finally:
        session.close()


# ============================================================================
# QUICK DEPLOYMENT ENDPOINTS
# ============================================================================


@app.post("/api/v1/bots/quick-deploy")
async def quick_deploy_bot(
        instance_name: str,
        credentials: BotCredentials,
        trading_params: TradingParameters,
        auto_start: bool = True,
        current_user: User = Depends(get_current_active_user),
):
    """Quick deploy and optionally start a new bot instance"""
    try:
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        # Generate instance ID from name
        import re

        instance_id = re.sub(r"[^a-zA-Z0-9_-]", "-", instance_name.lower())
        instance_id = (
            f"{instance_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        )

        # Create configuration
        config = BotInstanceConfig(
            instance_id=instance_id,
            instance_name=instance_name,
            credentials=credentials,
            trading_params=trading_params,
        )

        # Create instance
        create_result = await bot_manager.create_instance(config)
        if not create_result.success:
            return api_response(
                success=False, message=create_result.message, status_code=400
            )

        # Auto-start if requested
        if auto_start:
            await asyncio.sleep(1)  # Brief pause
            start_result = await bot_manager.start_instance(instance_id)

            if start_result.success:
                return api_response(
                    success=True,
                    data={
                        "instance_id": instance_id,
                        "created": create_result.success,
                        "started": start_result.success,
                        "status": "running",
                    },
                    message=f"Bot '{instance_name}' deployed and started successfully",
                )
            else:
                return api_response(
                    success=True,
                    data={
                        "instance_id": instance_id,
                        "created": create_result.success,
                        "started": False,
                        "status": "stopped",
                        "start_error": start_result.message,
                    },
                    message=f"Bot '{instance_name}' deployed but failed to start: {start_result.message}",
                )
        else:
            return api_response(
                success=True,
                data={
                    "instance_id": instance_id,
                    "created": create_result.success,
                    "started": False,
                    "status": "stopped",
                },
                message=f"Bot '{instance_name}' deployed successfully (not started)",
            )

    except Exception as e:
        logger.error(f"Error in quick deploy: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# HEALTH AND STATUS ENDPOINTS
# ============================================================================


def _backtest_storage_health(service: Any) -> Dict[str, Any]:
    repository = getattr(service, "repository", None)
    probe = getattr(repository, "storage_health", None)
    if callable(probe):
        return probe()
    return {
        "ready": True,
        "artifacts": {"enabled": False, "healthy": True},
        "analytics": {"enabled": False, "healthy": True},
    }


@app.get("/health")
async def health_check():
    """API health check"""
    with backtest_service_scope() as service:
        runtime_health = service.get_runtime_health()
        storage_health = _backtest_storage_health(service)
        backtest_limits = _backtest_capacity_snapshot(runtime_health)
        strategy_resolution_metrics = _strategy_resolution_metrics_snapshot()
        strategy_resolution_alerts = dict(strategy_resolution_metrics.get("alerts", {}))
        return api_response(
            success=True,
            data={
                "status": "healthy",
                "api_version": "1.0.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backtest_runtime": runtime_health,
                "storage": storage_health,
                "backtest_limits": backtest_limits,
                "strategy_resolution_metrics": strategy_resolution_metrics,
                "strategy_resolution_alerts": strategy_resolution_alerts,
                "strategy_resolution_alert_recommended": bool(
                    strategy_resolution_alerts.get(
                        "request_ratio_alert_triggered", False
                    )
                ),
                "backtest_websocket_metrics": manager.get_backtest_send_failure_summary(),
                "bot_recovery": _bot_recovery_diagnostics(),
                "bot_db_sync": _bot_db_sync_diagnostics(),
            },
            message="API is healthy",
        )


@app.get("/ready")
async def readiness_check():
    """Strict readiness probe for orchestrators and deployment gates."""
    with backtest_service_scope() as service:
        runtime_health = service.get_runtime_health()
        storage_health = _backtest_storage_health(service)
        backtest_limits = _backtest_capacity_snapshot(runtime_health)
        strategy_resolution_metrics = _strategy_resolution_metrics_snapshot()
        strategy_resolution_alerts = dict(strategy_resolution_metrics.get("alerts", {}))
        ready = bot_manager is not None and bool(storage_health.get("ready", False))
        status_code = 200 if ready else 503

        return api_response(
            success=ready,
            data={
                "status": "ready" if ready else "not_ready",
                "bot_manager_ready": bot_manager is not None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backtest_runtime": runtime_health,
                "storage": storage_health,
                "backtest_limits": backtest_limits,
                "strategy_resolution_metrics": strategy_resolution_metrics,
                "strategy_resolution_alerts": strategy_resolution_alerts,
                "strategy_resolution_alert_recommended": bool(
                    strategy_resolution_alerts.get(
                        "request_ratio_alert_triggered", False
                    )
                ),
                "backtest_websocket_metrics": manager.get_backtest_send_failure_summary(),
                "bot_recovery": _bot_recovery_diagnostics(),
                "bot_db_sync": _bot_db_sync_diagnostics(),
            },
            message=(
                "Bot API is ready"
                if ready
                else "Bot API is not ready: bot manager or required storage unavailable"
            ),
            status_code=status_code,
        )


@app.get("/metrics")
async def metrics():
    """Return bot-local runtime metrics for backend /metrics dependency probing."""
    return {
        "timestamp": utc_now_iso(),
        "service": "bot",
        "arbitrage": snapshot_metrics(
            {
                "feature_flags": get_feature_flags(),
                "runtime_settings": get_runtime_settings(),
            }
        ),
    }


@app.get("/api/v1/capabilities")
async def api_capabilities():
    """Expose bot-service HTTP and websocket capabilities for backend integration."""
    http_routes: List[str] = []
    websocket_routes: List[str] = []
    commands: List[str] = []
    queries: List[str] = []

    for route in app.routes:
        path = getattr(route, "path", "")
        if not path:
            continue

        is_supported_scope = (
                path.startswith("/api/v1/bots")
                or path.startswith("/api/v1/backtests")
                or path.startswith("/api/v1/arbitrage")
                or path.startswith("/ws/")
                or path == "/api/v1/capabilities"
        )
        if not is_supported_scope:
            continue

        methods = sorted(
            method
            for method in (getattr(route, "methods", set()) or set())
            if method not in {"HEAD", "OPTIONS"}
        )
        if methods:
            for method in methods:
                route_id = f"{method} {path}"
                http_routes.append(route_id)
                if method in {"POST", "PUT", "PATCH", "DELETE"}:
                    commands.append(route_id)
                elif method == "GET":
                    queries.append(route_id)
        elif "websocket" in route.__class__.__name__.lower():
            websocket_routes.append(f"WS {path}")

    http_routes = sorted(set(http_routes))
    websocket_routes = sorted(set(websocket_routes))
    commands = sorted(set(commands))
    queries = sorted(set(queries))

    return api_response(
        success=True,
        data={
            "service": "bot",
            "http_endpoints": http_routes,
            "websocket_channels": websocket_routes,
            "command_endpoints": commands,
            "query_endpoints": queries,
            "event_channels": websocket_routes,
            "http_count": len(http_routes),
            "websocket_count": len(websocket_routes),
            "command_count": len(commands),
            "query_count": len(queries),
            "count": len(http_routes) + len(websocket_routes),
        },
        message="Bot API and websocket capabilities retrieved",
    )


@app.get("/api/v1/arbitrage/improvement-metrics")
async def get_arbitrage_improvement_metrics(
        current_user: User = Depends(get_current_active_user),
):
    _ = current_user
    return api_response(
        success=True,
        data=snapshot_metrics(
            {
                "feature_flags": get_feature_flags(),
                "runtime_settings": get_runtime_settings(),
            }
        ),
        message="Arbitrage improvement metrics retrieved",
    )


@app.get("/api/v1/arbitrage/runtime-settings")
async def get_arbitrage_runtime_settings(
        current_user: User = Depends(get_current_active_user),
):
    _ = current_user
    settings = get_runtime_settings()
    return api_response(
        success=True,
        data={"settings": settings, "feature_flags": get_feature_flags()},
        message="Arbitrage runtime settings retrieved",
    )


@app.put("/api/v1/arbitrage/runtime-settings")
async def update_arbitrage_runtime_settings(
        payload: Dict[str, Any],
        current_user: User = Depends(get_current_active_user),
):
    _ = current_user
    settings = update_runtime_settings(payload or {})
    return api_response(
        success=True,
        data={"settings": settings, "feature_flags": get_feature_flags()},
        message="Arbitrage runtime settings updated",
    )


@app.get("/api/v1/arbitrage/pair-priority")
async def get_arbitrage_pair_priority(
        limit: int = 25,
        current_user: User = Depends(get_current_active_user),
):
    _ = current_user
    safe_limit = max(1, min(int(limit or 25), 100))
    pairs = pair_storage.load_pairs()
    pair_priority_enabled = is_pair_priority_engine_enabled()
    if pair_priority_enabled:
        ranked_pairs, scores = prioritize_pairs(pairs, max_pairs=safe_limit)
    else:
        ranked_pairs = pairs[:safe_limit]
        scores = [score_pair(pair) for pair in ranked_pairs]
    ranked_lookup = {score.pair: score for score in scores}
    data = []
    for pair in ranked_pairs:
        label = f"{pair.base_market}/{pair.quote_market}"
        score = ranked_lookup.get(label)
        data.append(
            {
                "pair": label,
                "base_market": pair.base_market,
                "quote_market": pair.quote_market,
                "score": score.score if score else 0.0,
                "components": score.components if score else {},
                "explanation": score.explanation if score else [],
                "enabled": pair_priority_enabled,
            }
        )
    return api_response(
        success=True,
        data={"pairs": data, "count": len(data), "enabled": pair_priority_enabled},
        message="Arbitrage pair priority retrieved",
    )


@app.get("/api/v1/arbitrage/opportunity/{opportunity_id}/explain")
async def get_arbitrage_opportunity_explain(
        opportunity_id: str,
        current_user: User = Depends(get_current_active_user),
):
    _ = current_user
    metrics = snapshot_metrics(
        {
            "feature_flags": get_feature_flags(),
            "runtime_settings": get_runtime_settings(),
        }
    )
    rejection_reasons = metrics.get("rejection_reasons", {})
    normalized_id = str(opportunity_id or "").strip().lower().replace(" ", "_")

    matched_reason = None
    if isinstance(rejection_reasons, dict) and normalized_id in rejection_reasons:
        matched_reason = {
            "reason": normalized_id,
            "count": rejection_reasons.get(normalized_id, 0),
        }

    top_rejections: List[Dict[str, Any]] = []
    if isinstance(rejection_reasons, dict):
        sorted_reasons = sorted(
            rejection_reasons.items(),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        top_rejections = [
            {"reason": str(reason), "count": float(count)}
            for reason, count in sorted_reasons[:10]
        ]

    return api_response(
        success=True,
        data={
            "opportunity_id": opportunity_id,
            "matched_rejection_reason": matched_reason,
            "top_rejection_reasons": top_rejections,
            "counters": metrics.get("counters", {}),
            "feature_flags": metrics.get("feature_flags", {}),
            "runtime_settings": metrics.get("runtime_settings", {}),
            "explainability_scope": "runtime_diagnostics",
            "note": (
                "Per-opportunity historical explain payloads are not persisted yet; "
                "this endpoint provides current runtime diagnostics and rejection trends."
            ),
        },
        message="Arbitrage opportunity explainability retrieved",
    )


@app.get("/api/v1/markets/perpetuals")
async def list_perpetual_markets(limit: int = 0):
    """Return available dYdX perpetual markets for run configuration.

    Results are cached for ``MARKETS_CACHE_TTL_SECONDS`` (default 60 s).
    When the live dYdX call fails, stale cache data is served (up to
    ``MARKETS_STALE_TTL_SECONDS``, default 300 s) with an ``X-Cache-Stale: 1``
    header so callers can distinguish live vs fallback responses.
    When both live resolution and stale cache data are unavailable, the endpoint
    returns 503 instead of inventing a market list.
    """
    cap = _normalize_requested_pair_cap(limit)
    client = None

    # Serve a fresh cache hit without making a network call.
    cached = _markets_cache_get(allow_stale=False)
    if cached is not None:
        data = cached["data"]
        result_markets = data["markets"] if cap is None else data["markets"][:cap]
        return api_response(
            success=True,
            data={
                "markets": result_markets,
                "count": len(result_markets),
                "source": "cache",
            },
            message=f"Retrieved {len(result_markets)} perpetual markets",
            headers={"X-Cache-Hit": "1"},
        )

    markets: List[str] = []
    live_error: Optional[Exception] = None

    try:
        client = await asyncio.wait_for(
            connect_dydx(),
            timeout=_MARKETS_ENDPOINT_TIMEOUT_SECONDS,
        )
        payload = await asyncio.wait_for(
            client.indexer.markets.get_perpetual_markets(),
            timeout=_MARKETS_ENDPOINT_TIMEOUT_SECONDS,
        )
        raw_map = payload.get("markets", {}) if isinstance(payload, dict) else {}
        if isinstance(raw_map, dict):
            markets = sorted(str(k) for k in raw_map.keys() if str(k).strip())
    except Exception as err:
        live_error = err
        logger.warning(
            "market_resolution_failed endpoint=/api/v1/markets/perpetuals error={}",
            err,
        )
    finally:
        if client is not None:
            for _closer in (
                    getattr(client, "node", None),
                    getattr(client, "indexer_client", None),
            ):
                if _closer is not None and hasattr(_closer, "close"):
                    try:
                        await _closer.close()
                    except Exception:
                        pass

    if live_error is not None:
        # Live call failed – try stale cache before giving up.
        stale = _markets_cache_get(allow_stale=True)
        if stale is not None:
            data = stale["data"]
            result_markets = data["markets"] if cap is None else data["markets"][:cap]
            logger.info(
                "markets_stale_fallback endpoint=/api/v1/markets/perpetuals "
                "count={} error={}",
                len(result_markets),
                live_error,
            )
            return api_response(
                success=True,
                data={
                    "markets": result_markets,
                    "count": len(result_markets),
                    "source": "cache_stale",
                },
                message=f"Retrieved {len(result_markets)} perpetual markets (stale cache fallback)",
                headers={"X-Cache-Stale": "1"},
            )

        return api_response(
            success=False,
            message=f"MARKET_RESOLUTION_FAILED: {live_error}",
            data={"error": "MARKET_RESOLUTION_FAILED"},
            status_code=503,
        )

    # Successful live fetch – populate cache and return.
    _markets_cache_set({"markets": markets, "count": len(markets), "source": "dydx"})

    if cap is not None:
        markets = markets[:cap]

    return api_response(
        success=True,
        data={"markets": markets, "count": len(markets), "source": "dydx"},
        message=f"Retrieved {len(markets)} perpetual markets",
    )


@app.get("/api/v1/runtime/db-config")
async def runtime_db_config(current_user: User = Depends(get_admin_user)):
    """Admin-only diagnostics for effective runtime database configuration."""
    _ = current_user
    try:
        config = DatabaseConfig()
        return api_response(
            success=True,
            data={
                **config.to_diagnostics(),
                "count": 1,
            },
            message="Runtime database configuration retrieved",
        )
    except Exception as e:
        logger.error(f"Error retrieving runtime DB config diagnostics: {e}")
        return api_response(
            success=False,
            message="Internal server error",
            status_code=500,
        )


@app.get("/api/v1/celery/tasks")
async def celery_tasks(
        status: Optional[str] = Query(default=None),
        task_name: Optional[str] = Query(default=None),
        queue: Optional[str] = Query(default=None),
        strategy_id: Optional[str] = Query(default=None),
        backtest_run_id: Optional[str] = Query(default=None),
        bot_id: Optional[str] = Query(default=None),
        environment: Optional[str] = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        current_user: User = Depends(get_admin_user),
):
    """Admin-only Celery task list with safe metadata redaction."""
    _ = current_user
    started_at = time.perf_counter()
    payload = list_celery_tasks(
        {
            "status": status,
            "task_name": task_name,
            "queue": queue,
            "strategy_id": strategy_id,
            "backtest_run_id": backtest_run_id,
            "bot_id": bot_id,
            "environment": environment,
        },
        limit,
    )
    task_count = (
        len(payload.get("tasks", []))
        if isinstance(payload, dict) and isinstance(payload.get("tasks"), list)
        else None
    )
    _log_endpoint_timing(
        "/api/v1/celery/tasks",
        started_at,
        payload,
        payload_items=task_count,
        extra={"limit": limit},
    )
    return api_response(
        True,
        payload,
        "Celery tasks fetched successfully",
        headers=_endpoint_perf_headers(started_at),
    )


@app.get("/api/v1/celery/tasks/{task_id}")
async def celery_task_detail(
        task_id: str,
        current_user: User = Depends(get_admin_user),
):
    """Admin-only Celery task detail including failure traceback when available."""
    _ = current_user
    started_at = time.perf_counter()
    task = get_celery_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Celery task not found")
    _log_endpoint_timing(
        "/api/v1/celery/tasks/{task_id}",
        started_at,
        {"task": task},
        payload_items=1,
    )
    return api_response(
        True,
        {"task": task},
        "Celery task fetched successfully",
        headers=_endpoint_perf_headers(started_at),
    )


@app.post("/api/v1/celery/tasks/{task_id}/revoke")
async def celery_task_revoke(
        task_id: str,
        payload: Dict[str, Any] = Body(default_factory=dict),
        current_user: User = Depends(get_admin_user),
):
    """Admin-only Celery revoke/cancel endpoint."""
    _ = current_user
    terminate = bool(payload.get("terminate", False))
    return api_response(
        True,
        revoke_celery_task(task_id, terminate=terminate),
        "Celery task revoke requested",
    )


@app.post("/api/v1/celery/tasks/{task_id}/retry")
async def celery_task_retry(
        task_id: str,
        current_user: User = Depends(get_admin_user),
):
    """Admin-only retry for supported failed tasks."""
    _ = current_user
    try:
        result = await retry_celery_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return api_response(True, result, "Celery task retry requested")


@app.get("/api/v1/celery/workers")
async def celery_workers(current_user: User = Depends(get_admin_user)):
    """Admin-only Celery worker inspection."""
    _ = current_user
    started_at = time.perf_counter()
    payload = list_celery_workers()
    worker_count = len(payload) if isinstance(payload, dict) else None
    _log_endpoint_timing(
        "/api/v1/celery/workers",
        started_at,
        payload,
        payload_items=worker_count,
    )
    return api_response(
        True,
        payload,
        "Celery workers fetched successfully",
        headers=_endpoint_perf_headers(started_at),
    )


@app.get("/api/v1/celery/queues")
async def celery_queues(current_user: User = Depends(get_admin_user)):
    """Admin-only Celery queue overview."""
    _ = current_user
    started_at = time.perf_counter()
    payload = list_celery_queues()
    queue_count = len(payload) if isinstance(payload, dict) else None
    _log_endpoint_timing(
        "/api/v1/celery/queues",
        started_at,
        payload,
        payload_items=queue_count,
    )
    return api_response(
        True,
        payload,
        "Celery queues fetched successfully",
        headers=_endpoint_perf_headers(started_at),
    )


@app.get("/api/v1/celery/health")
async def celery_monitor_health(current_user: User = Depends(get_admin_user)):
    """Admin-only Celery broker/backend/worker health."""
    _ = current_user
    started_at = time.perf_counter()
    payload = celery_health()
    _log_endpoint_timing(
        "/api/v1/celery/health",
        started_at,
        payload,
        payload_items=1,
    )
    return api_response(
        True,
        payload,
        "Celery health fetched successfully",
        headers=_endpoint_perf_headers(started_at),
    )


@app.get("/api/v1/users/me")
async def get_current_user_profile(
        current_user: User = Depends(get_current_active_user),
):
    """Frontend-compatible current user endpoint used after login."""
    return api_response(
        success=True,
        data={
            "id": int(getattr(current_user, "id", 1) or 1),
            "username": str(getattr(current_user, "username", "admin")),
            "email": str(getattr(current_user, "email", "admin@example.local")),
            "is_active": bool(getattr(current_user, "is_active", True)),
            "is_admin": bool(
                getattr(
                    current_user,
                    "is_admin",
                    getattr(current_user, "is_superuser", False),
                )
            ),
            "created_at": (
                getattr(current_user, "created_at", datetime.now(timezone.utc))
            ).isoformat(),
        },
        message="Current user profile retrieved",
    )


@app.get("/api/v1/system/status")
async def system_status(current_user: User = Depends(get_current_active_user)):
    """Get system status and statistics"""
    try:
        with backtest_service_scope() as service:
            runtime_health = service.get_runtime_health()
            backtest_limits = _backtest_capacity_snapshot(runtime_health)
            if bot_manager is None:
                return api_response(
                    success=True,
                    data={
                        "bot_instances": {"total": 0, "running": 0, "max_allowed": 0},
                        "system_resources": {
                            "cpu_usage_percent": 0,
                            "memory_usage_percent": 0,
                            "memory_available_gb": 0,
                        },
                        "api_info": {"version": "1.0.0", "uptime_hours": "N/A"},
                        "backtest_runtime": runtime_health,
                        "backtest_limits": backtest_limits,
                        "bot_recovery": _bot_recovery_diagnostics(),
                        "bot_db_sync": _bot_db_sync_diagnostics(),
                    },
                    message="System status available; bot manager unavailable",
                )
        instances = await bot_manager.list_instances()

        # Cleanup any dead processes
        await bot_manager.cleanup_dead_processes()

        # Calculate system stats
        total_instances = len(instances)
        running_instances = len([i for i in instances if i.status == BotStatus.RUNNING])

        # System resource usage
        import psutil  # type: ignore[import-untyped]

        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()

        return api_response(
            success=True,
            data={
                "bot_instances": {
                    "total": total_instances,
                    "running": running_instances,
                    "max_allowed": (
                        bot_manager.max_instances
                        if bot_manager.max_instances > 0
                        else None
                    ),
                },
                "system_resources": {
                    "cpu_usage_percent": cpu_usage,
                    "memory_usage_percent": memory.percent,
                    "memory_available_gb": round(memory.available / (1024 ** 3), 2),
                },
                "api_info": {
                    "version": "1.0.0",
                    "uptime_hours": "N/A",  # Could implement uptime tracking
                },
                "backtest_runtime": runtime_health,
                "backtest_limits": backtest_limits,
                "bot_recovery": _bot_recovery_diagnostics(),
                "bot_db_sync": _bot_db_sync_diagnostics(),
            },
            message="System status retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# REAL-TIME DATA ENDPOINTS
# ============================================================================


def _resolve_realtime_bot_id(session, bot_instance_id: str) -> Optional[int]:
    raw_id = str(bot_instance_id or "").strip()
    if not raw_id:
        return None
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        pass

    try:
        uow_core = UnitOfWork(session)
        bot = uow_core.bots.get_by_instance_id(raw_id)
        return int(bot.id) if bot else None  # type: ignore[arg-type]
    except Exception as exc:
        logger.warning(
            "Failed to resolve realtime bot id for {}: {}",
            raw_id,
            exc,
        )
        return None


@app.get("/api/v1/bots/{bot_instance_id}/positions/current")
async def get_current_positions(
        bot_instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get all currently open positions for a bot"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        positions = uow.positions.get_open_positions(bot_id_int)  # type: ignore[arg-type]

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "positions": [
                    serialize_realtime_position(p, include_updated_at=True)
                    for p in positions
                ],
                "count": len(positions),
            },
        )

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/positions/{position_id}")
async def get_position(
        bot_instance_id: str,
        position_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Get specific position details"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        resolved_bot_id = _resolve_realtime_bot_id(session, bot_instance_id)
        if resolved_bot_id is None:
            return api_response(
                success=False, message="Bot instance not found", status_code=404
            )

        position = uow.positions.get_position_by_id(position_id)

        if not position or position.bot_instance_id != resolved_bot_id:
            return api_response(
                success=False, message="Position not found", status_code=404
            )

        return api_response(
            success=True,
            data={
                "position_id": position.position_id,
                "pair1": position.pair1,
                "pair2": position.pair2,
                "side1": position.side1,
                "side2": position.side2,
                "status": position.status.value,
                "entry_price1": float(position.entry_price1 or 0.0),
                "entry_price2": float(position.entry_price2 or 0.0),
                "current_price1": float(position.current_price1 or 0.0),
                "current_price2": float(position.current_price2 or 0.0),
                "current_size1": float(position.current_size1 or 0.0),
                "current_size2": float(position.current_size2 or 0.0),
                "entry_cost": float(position.entry_cost or 0.0),
                "current_value": float(position.current_value or 0.0),
                "unrealized_pnl": float(position.unrealized_pnl),
                "unrealized_pnl_pct": float(position.unrealized_pnl_pct),
                "realized_pnl": (
                    float(position.realized_pnl) if position.realized_pnl else 0
                ),
                "z_score_entry": (
                    float(position.z_score_entry) if position.z_score_entry else None
                ),
                "z_score_current": (
                    float(position.z_score_current)
                    if position.z_score_current
                    else None
                ),
                "hedge_ratio": (
                    float(position.hedge_ratio) if position.hedge_ratio else None
                ),
                "correlation": (
                    float(position.correlation) if position.correlation else None
                ),
                "half_life": float(position.half_life) if position.half_life else None,
                "entered_at": position.entry_time.isoformat(),
                "updated_at": (
                    position.updated_at.isoformat() if position.updated_at else None
                ),
                "closed_at": (
                    position.closed_at.isoformat() if position.closed_at else None
                ),
            },
        )

    except Exception as e:
        logger.error(f"Error getting position: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/market-data")
async def get_market_data(
        bot_instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get latest market data for all symbols tracked by bot"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        market_data = uow.market_data.get_all_market_data(bot_id_int)

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "market_data": [
                    {
                        **serialize_market_core(m, include_volatility=True),
                        "rsi": float(m.rsi) if m.rsi else None,
                        "macd": float(m.macd) if m.macd else None,
                        "moving_avg_20": (
                            float(m.moving_avg_20) if m.moving_avg_20 else None
                        ),
                        "moving_avg_50": (
                            float(m.moving_avg_50) if m.moving_avg_50 else None
                        ),
                        "funding_rate": (
                            float(m.funding_rate) if m.funding_rate else None
                        ),
                        "updated_at": m.timestamp.isoformat() if m.timestamp else None,
                    }
                    for m in market_data
                ],
                "count": len(market_data),
            },
        )

    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/realtime-stats")
async def get_realtime_stats(
        bot_instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get real-time bot statistics"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        stats = uow.stats.get_stats(bot_id_int)

        if not stats:
            return api_response(
                success=True,
                data={
                    "bot_instance_id": bot_instance_id,
                    "stats": {
                        "total_open_positions": 0,
                        "total_unrealized_pnl": 0,
                        "total_unrealized_pnl_pct": 0,
                        "daily_pnl": 0,
                        "daily_pnl_pct": 0,
                        "daily_trades_opened": 0,
                        "daily_trades_closed": 0,
                        "daily_wins": 0,
                        "daily_losses": 0,
                        "daily_win_rate": 0,
                        "max_drawdown": 0,
                        "current_drawdown": 0,
                    },
                },
            )

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "stats": {
                    "total_open_positions": stats.total_open_positions,
                    "total_unrealized_pnl": float(stats.total_unrealized_pnl),
                    "total_unrealized_pnl_pct": float(stats.total_unrealized_pnl_pct),
                    "daily_pnl": float(stats.daily_pnl),
                    "daily_pnl_pct": float(stats.daily_pnl_pct),
                    "daily_trades_opened": stats.daily_trades_opened,
                    "daily_trades_closed": stats.daily_trades_closed,
                    "daily_wins": (
                        stats.daily_wins if hasattr(stats, "daily_wins") else 0
                    ),
                    "daily_losses": (
                        stats.daily_losses if hasattr(stats, "daily_losses") else 0
                    ),
                    **serialize_stats_risk_fields(stats),
                    "var_95": float(stats.var_95) if stats.var_95 else None,
                    "avg_trade_duration": (
                        stats.avg_trade_duration_seconds
                        if hasattr(stats, "avg_trade_duration_seconds")
                        else None
                    ),
                    "is_healthy": (
                        stats.is_healthy if hasattr(stats, "is_healthy") else True
                    ),
                    "updated_at": (
                        stats.updated_at.isoformat()
                        if hasattr(stats, "updated_at") and stats.updated_at
                        else None
                    ),
                },
            },
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/alerts")
async def get_alerts(
        bot_instance_id: str,
        limit: int = 50,
        current_user: User = Depends(get_current_active_user),
):
    """Get recent alerts for a bot"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        alerts = uow.alerts.get_unnotified_alerts(bot_id_int)
        # Limit to most recent
        alerts = alerts[:limit]

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "alerts": [
                    {
                        "id": a.id,
                        "type": a.alert_type,
                        "severity": a.severity,
                        "message": a.message,
                        "notified": a.notified,
                        "notified_via": a.notified_via if a.notified_via else {},
                        "created_at": a.timestamp.isoformat() if a.timestamp else None,
                        "details": a.details if a.details else {},
                    }
                    for a in alerts
                ],
                "count": len(alerts),
            },
        )

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/position-history/{position_id}")
async def get_position_history(
        bot_instance_id: str,
        position_id: str,
        hours: int = 24,
        current_user: User = Depends(get_current_active_user),
):
    """Get historical P&L snapshots for a position"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        snapshots = uow.snapshots.get_position_history(position_id, hours=hours)

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "position_id": position_id,
                "hours": hours,
                "snapshots": [
                    {
                        "pair1": s.pair1,
                        "pair2": s.pair2,
                        "unrealized_pnl": float(s.unrealized_pnl),
                        "unrealized_pnl_pct": float(s.unrealized_pnl_pct),
                        "current_price1": (
                            float(s.current_price1) if s.current_price1 else None
                        ),
                        "current_price2": (
                            float(s.current_price2) if s.current_price2 else None
                        ),
                        "z_score": float(s.z_score) if s.z_score else None,
                        "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                    }
                    for s in snapshots
                ],
                "count": len(snapshots),
            },
        )

    except Exception as e:
        logger.error(f"Error getting position history: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.websocket("/api/v1/bots/{bot_instance_id}/alerts/live")
async def websocket_alerts(websocket: WebSocket, bot_instance_id: str):
    """WebSocket endpoint for live alerts"""
    if not await _authorize_websocket_connection(websocket):
        return
    await WebSocketServer.handle_connection(websocket, str(bot_instance_id))


@app.websocket("/api/v1/backtests/{run_id}/live")
async def websocket_backtest_progress(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for live backtest progress updates."""
    if not await _authorize_websocket_connection(websocket):
        return
    await WebSocketServer.handle_connection(websocket, f"backtest-{run_id}")


@app.websocket("/ws/bots/{bot_instance_id}")
async def websocket_bot_runtime(websocket: WebSocket, bot_instance_id: str):
    """Alias websocket channel for backend integrations consuming bot runtime events."""
    if not await _authorize_websocket_connection(websocket):
        return
    await WebSocketServer.handle_connection(websocket, str(bot_instance_id))


@app.websocket("/ws/backtests/{run_id}")
async def websocket_backtest_progress_alias(websocket: WebSocket, run_id: str):
    """Alias websocket channel for backend integrations consuming backtest runtime events."""
    if not await _authorize_websocket_connection(websocket):
        return
    await WebSocketServer.handle_connection(websocket, f"backtest-{run_id}")


async def _authorize_websocket_connection(websocket: WebSocket) -> bool:
    """Validate websocket bearer token via Authorization header only."""
    if is_auth_bypass_enabled():
        return True

    auth_header = websocket.headers.get("authorization", "").strip()
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    # SECURITY: Removed query parameter token acceptance to prevent token logging
    # Tokens must only be provided via Authorization header

    if not token:
        await websocket.close(code=4401, reason="Missing websocket auth token")
        return False

    session = db.get_session()
    try:
        authenticate_bearer_token(token, session)
        return True
    except Exception:
        await websocket.close(code=4401, reason="Invalid websocket auth token")
        return False
    finally:
        session.close()


@app.websocket("/ws/strategies")
async def websocket_strategies(websocket: WebSocket):
    """Frontend strategy status websocket channel."""
    if not await _authorize_websocket_connection(websocket):
        return

    channel = "strategies"
    await manager.connect(websocket, channel)
    try:
        if bot_manager is not None:
            await manager.send_personal_message(
                build_strategy_snapshot_message(
                    bot_manager.get_strategy_status_snapshot()
                ),
                websocket,
            )
        else:
            await manager.send_personal_message(
                {
                    "type": "strategy_channel_connected",
                    "channel": channel,
                    "timestamp": utc_now_iso(),
                },
                websocket,
            )

        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if message.get("type") == "ping":
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": utc_now_iso()},
                    websocket,
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"Strategy websocket error: {e}")
        manager.disconnect(websocket, channel)


# ============================================================================
# BACKTESTING ENDPOINTS
# ============================================================================


# Initialize backtest service
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
    service = get_backtest_service()
    try:
        yield service
    finally:
        close_backtest_service(service)


def _run_with_backtest_service(operation):
    """Execute sync backtest-service work with request-scoped session cleanup."""
    service = get_backtest_service()
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


@app.post("/api/v1/backtests", response_model=BacktestResponse)
async def create_backtest(
        request: Union[BacktestConfigRequest, BacktestRunRequestCompat],
        _rate: None = Depends(_check_backtest_rate_limit),
        current_user: User = Depends(get_current_active_user),
):
    """Create and start a new backtest"""
    del current_user
    try:
        if isinstance(request, BacktestRunRequestCompat):
            resolved_pairs = await _resolve_backtest_markets(
                request.pairs,
                request.selected_pairs,
                request.max_pairs,
            )
            selected_pair_labels = _normalize_string_list(request.selected_pairs)
            if not selected_pair_labels:
                selected_pair_labels = _build_selected_pair_labels(resolved_pairs)
            normalized_request = _resolve_strategy_backtest_request(
                request,
                resolved_pairs,
                selected_pair_labels,
                "/api/v1/backtests",
            )
            if isinstance(normalized_request, JSONResponse):
                return normalized_request
        else:
            normalized_request = request

        with backtest_service_scope() as service:
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
    except Exception as e:
        logger.error(f"Error creating backtest: {e}")
        return api_response(
            success=False, message="Internal server error", status_code=500
        )


@app.post("/api/v1/backtests/run")
async def run_backtest_compat(
        request: BacktestRunRequestCompat,
        _rate: None = Depends(_check_backtest_rate_limit),
        current_user: User = Depends(get_current_active_user),
):
    """Frontend-compatible backtest execution route."""
    del current_user
    try:
        resolved_pairs = await _resolve_backtest_markets(
            request.pairs,
            request.selected_pairs,
            request.max_pairs,
        )
        selected_pair_labels = _normalize_string_list(request.selected_pairs)
        if not selected_pair_labels:
            selected_pair_labels = _build_selected_pair_labels(resolved_pairs)
        backtest_request = _resolve_strategy_backtest_request(
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

        with backtest_service_scope() as service:
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


@app.get("/api/v1/backtests", response_model=BacktestListResponse)
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
        result = _list_backtests_sync(limit, offset, status, days)
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


@app.get("/api/v1/backtests/interrupted")
async def list_interrupted_backtests(
        limit: int = 50,
        current_user: User = Depends(get_current_active_user),
):
    """Ops visibility for interrupted/orphaned persisted backtest runs."""
    del current_user
    return _list_interrupted_backtests_response(limit=limit)


def _list_interrupted_backtests_response(limit: int):
    """Shared response builder for interrupted backtest visibility routes."""
    try:
        with backtest_service_scope() as service:
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


@app.post("/api/v1/backtests/interrupted/reconcile")
async def reconcile_interrupted_backtests(
        dry_run: bool = True,
        current_user: User = Depends(get_current_active_user),
):
    """Explicitly reconcile persisted orphaned in-progress runs."""
    del current_user
    return _reconcile_interrupted_backtests_response(dry_run=dry_run)


def _reconcile_interrupted_backtests_response(dry_run: bool):
    """Shared response builder for interrupted backtest reconcile routes."""
    try:
        with backtest_service_scope() as service:
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
    except Exception as e:
        logger.error(f"Error reconciling interrupted backtests: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


def _repair_backtest_request_response(run_id: str, dry_run: bool):
    """Shared response builder for request repair routes."""
    try:
        with backtest_service_scope() as service:
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
    except Exception as e:
        logger.error(f"Error repairing backtest request: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/admin/backtests/interrupted")
async def list_interrupted_backtests_admin(
        limit: int = 50,
        current_user: User = Depends(get_admin_user),
):
    """Admin-scoped alias for interrupted/orphaned persisted backtest visibility."""
    _ = current_user
    return _list_interrupted_backtests_response(limit=limit)


@app.post("/api/v1/admin/backtests/interrupted/reconcile")
async def reconcile_interrupted_backtests_admin(
        dry_run: bool = True,
        current_user: User = Depends(get_admin_user),
):
    """Admin-scoped alias for explicit interrupted backtest reconciliation."""
    _ = current_user
    return _reconcile_interrupted_backtests_response(dry_run=dry_run)


@app.post("/api/v1/admin/backtests/{run_id}/repair-request")
async def repair_backtest_request_admin(
        run_id: str,
        dry_run: bool = True,
        current_user: User = Depends(get_admin_user),
):
    """Admin-scoped repair for legacy backtests missing request payloads."""
    _ = current_user
    return _repair_backtest_request_response(run_id=run_id, dry_run=dry_run)


@app.get("/api/v1/backtests/{run_id}", response_model=BacktestDetailResponse)
async def get_backtest_details(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Get detailed backtest results"""
    del current_user
    try:
        result = _get_backtest_details_sync(run_id)
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

    except Exception as e:
        logger.error(f"Error getting backtest details: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/status")
async def get_backtest_status(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Get current backtest status and progress"""
    del current_user
    try:
        result = _get_backtest_status_sync(run_id)
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

    except Exception as e:
        logger.error(f"Error getting backtest status: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/backtests/{run_id}/metadata")
async def update_backtest_metadata(
        run_id: str,
        payload: Dict[str, Any] = Body(default_factory=dict),
        current_user: User = Depends(get_current_active_user),
):
    """Attach or merge structured metadata into a persisted backtest run."""
    del current_user
    try:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return api_response(
                success=False,
                message="Validation error: metadata must be an object",
                data={"error": "INVALID_METADATA"},
                status_code=422,
            )

        merge = bool(payload.get("merge", True))
        with backtest_service_scope() as service:
            result = service.update_backtest_metadata(
                run_id,
                metadata,
                merge=merge,
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

    except Exception as e:
        logger.error(f"Error updating backtest metadata: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/websocket-metrics")
async def get_backtest_websocket_metrics(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Get per-run websocket send-failure metrics for reconnect-thrashing alerting."""
    del current_user
    try:
        status = _get_backtest_status_sync(run_id)
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
    except Exception as e:
        logger.error(f"Error getting backtest websocket metrics: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500,
        )


@app.post("/api/v1/backtests/{run_id}/create-strategy")
async def create_strategy_from_backtest(
        run_id: str,
        request: BacktestCreateStrategyRequest,
        current_user: User = Depends(get_current_active_user),
):
    """Create a strategy snapshot from an existing backtest."""
    del current_user
    with backtest_service_scope() as service:
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


@app.get("/api/v1/backtests/{run_id}/trades")
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
            trades = _get_backtest_trades_sync(
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


@app.get("/api/v1/backtests/{run_id}/logs")
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


@app.post("/api/v1/backtests/{run_id}/cancel")
async def cancel_backtest(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Cancel running backtest"""
    del current_user
    try:
        with backtest_service_scope() as service:
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

    except Exception as e:
        logger.error(f"Error cancelling backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/backtests/{run_id}/pause")
async def pause_backtest(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Request a cooperative pause for a running backtest."""
    del current_user
    try:
        with backtest_service_scope() as service:
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

    except Exception as e:
        logger.error(f"Error pausing backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/backtests/{run_id}/resume")
async def resume_backtest(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Resume a paused backtest."""
    del current_user
    try:
        with backtest_service_scope() as service:
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

    except Exception as e:
        logger.error(f"Error resuming backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/backtests/{run_id}/restart")
async def restart_backtest(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Cancel the current run if needed and start a fresh run from the same request."""
    del current_user
    try:
        with backtest_service_scope() as service:
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


@app.post("/api/v1/backtests/{run_id}/retry")
async def retry_backtest(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Start a fresh run from the same request payload."""
    del current_user
    try:
        with backtest_service_scope() as service:
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


@app.delete("/api/v1/backtests/{run_id}")
async def delete_backtest(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Delete backtest run and all associated data"""
    del current_user
    try:
        with backtest_service_scope() as service:
            success = service.delete_backtest(run_id)
        if not success:
            return api_response(
                success=False, message=f"Backtest '{run_id}' not found", status_code=404
            )

        return api_response(
            success=True, message=f"Backtest '{run_id}' deleted successfully"
        )

    except Exception as e:
        logger.error(f"Error deleting backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/stats/summary")
async def get_backtest_summary_stats(
        days: int = 30,
        current_user: User = Depends(get_current_active_user),
):
    """Get backtest system summary statistics"""
    del current_user
    try:
        stats = _get_backtest_summary_stats_sync(days)

        return api_response(
            success=True,
            data=stats,
            message=f"Retrieved backtest statistics for last {days} days",
        )

    except Exception as e:
        logger.error(f"Error getting backtest stats: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/analytics")
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
            analytics = _get_backtest_analytics_sync(run_id)
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


@app.get("/api/v1/backtests/{run_id}/analytics/summary")
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
                analytics = _get_backtest_analytics_sync(run_id)
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


@app.get("/api/v1/backtests/{run_id}/position-snapshots")
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
        snapshots = _get_position_snapshots_sync(
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


@app.post("/api/v1/backtests/compare")
async def compare_backtests(
        request: dict,  # BacktestComparisonRequest - simplified for now
        current_user: User = Depends(get_current_active_user),
):
    """Compare multiple backtest runs with advanced analytics"""
    del current_user
    try:
        run_ids = request.get("run_ids", [])
        metrics = request.get(
            "metrics", ["total_return_pct", "sharpe_ratio", "win_rate"]
        )

        if len(run_ids) < 2:
            return api_response(
                success=False,
                message="At least 2 backtest runs required for comparison",
                status_code=400,
            )

        comparison = _compare_backtests_sync(run_ids, metrics)

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


@app.get("/api/v1/backtests/sync-health")
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

        runtime_health = _get_backtest_runtime_health_sync()
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


@app.get("/api/v1/runtime/strategy-resolution-metrics")
async def get_strategy_resolution_metrics(
        current_user: User = Depends(get_current_active_user),
):
    """Lightweight dashboard endpoint for strategy-resolution drift metrics."""
    del current_user
    return api_response(
        success=True,
        data=_strategy_resolution_metrics_snapshot(),
        message="Strategy resolution metrics retrieved",
    )


@app.get(
    "/api/v1/runtime/strategy-resolution-metrics/prom",
    response_class=PlainTextResponse,
)
async def get_strategy_resolution_metrics_prometheus(
        current_user: User = Depends(get_current_active_user),
):
    """Prometheus text-format strategy-resolution metrics for dashboards/probes."""
    del current_user
    return PlainTextResponse(
        content=_strategy_resolution_metrics_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/v1/admin/runtime/strategy-resolution-metrics")
async def get_strategy_resolution_metrics_admin(
        current_user: User = Depends(get_admin_user),
):
    """Admin-only alias for strategy-resolution drift metrics."""
    del current_user
    return api_response(
        success=True,
        data=_strategy_resolution_metrics_snapshot(),
        message="Strategy resolution metrics retrieved",
    )


@app.post("/api/v1/admin/runtime/strategy-resolution-metrics/reset")
async def reset_strategy_resolution_metrics_admin(
        current_user: User = Depends(get_admin_user),
):
    """Admin-only endpoint to reset in-memory strategy-resolution counters."""
    del current_user
    return api_response(
        success=True,
        data=_reset_strategy_resolution_metrics(),
        message="Strategy resolution metrics reset",
    )


@app.get("/api/v1/backtests/{run_id}/dydx-validation")
async def validate_against_dydx_data(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Validate backtest results against real dYdX market data"""
    del current_user
    try:
        with backtest_service_scope() as service:
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


@app.get("/api/v1/backtests/{run_id}/performance-metrics")
async def get_advanced_performance_metrics(
        run_id: str,
        benchmark: str = "BTC-USD",
        current_user: User = Depends(get_current_active_user),
):
    """Get advanced performance metrics with market benchmarking"""
    del current_user
    try:
        metrics = _get_advanced_performance_metrics_sync(
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


@app.get("/api/v1/backtests/{run_id}/live-progress")
async def get_live_progress(
        run_id: str,
        current_user: User = Depends(get_current_active_user),
):
    """Get real-time backtest progress with current positions"""
    del current_user
    try:
        progress = _get_live_progress_sync(run_id)
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

    except Exception as e:
        logger.error(f"Error getting live progress: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# BACKGROUND TASKS
# ============================================================================


async def _bot_manager_monitor_loop():
    """Background loop that reconciles dead processes into API-visible error states."""
    interval_seconds = max(
        2,
        int(os.getenv("BOT_MANAGER_MONITOR_INTERVAL_SECONDS", "10")),
    )
    while True:
        try:
            if bot_manager is not None:
                await bot_manager.cleanup_dead_processes()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Bot manager monitor loop failed: {}", exc)

        await asyncio.sleep(interval_seconds)


# ============================================================================
# DATABASE MONITORING ENDPOINTS
# ============================================================================


@app.get("/api/v1/monitoring/database/pool")
async def get_database_pool_metrics(
        current_user: User = Depends(get_current_active_user),
):
    """Get current database connection pool metrics."""
    _ = current_user
    metrics = db.get_pool_metrics()
    return api_response(
        success=True,
        data=metrics,
        message="Database pool metrics retrieved",
    )


@app.get("/api/v1/monitoring/database/pool/health")
async def get_database_pool_health(
        current_user: User = Depends(get_current_active_user),
):
    """Get database connection pool health status."""
    _ = current_user
    health = db.get_pool_health_status()
    return api_response(
        success=True,
        data=health,
        message="Database pool health status retrieved",
    )


@app.get("/api/v1/monitoring/database/pool/history")
async def get_database_pool_history(
        limit: int = 50,
        current_user: User = Depends(get_current_active_user),
):
    """Get historical database connection pool metrics."""
    _ = current_user
    safe_limit = max(1, min(int(limit or 50), 500))
    history = db.get_pool_metrics_history(limit=safe_limit)
    return api_response(
        success=True,
        data={"history": history, "count": len(history)},
        message=f"Retrieved {len(history)} database pool metrics samples",
    )


@app.get("/api/v1/monitoring/database/diagnostics")
async def get_database_diagnostics(
        current_user: User = Depends(get_current_active_user),
):
    """Get comprehensive database diagnostics including pool metrics."""
    _ = current_user
    diagnostics = db.get_diagnostics()
    return api_response(
        success=True,
        data=diagnostics,
        message="Database diagnostics retrieved",
    )


# STRATEGY ENDPOINTS
# ============================================================================


@app.get("/api/v1/strategies")
async def list_strategies(
        skip: int = 0,
        limit: int = 50,
        current_user: User = Depends(get_current_active_user),
):
    """List stored strategies for the UI."""
    del current_user
    data = InMemoryStrategyStore.list(skip=skip, limit=limit)
    return api_response(
        success=True,
        data=data,
        message=f"Retrieved {len(data['strategies'])} strategies",
    )


@app.get("/api/v1/strategies/public")
async def list_public_strategies():
    """List public strategies."""
    data = InMemoryStrategyStore.list_public()
    return api_response(
        success=True,
        data=data,
        message=f"Retrieved {len(data['strategies'])} public strategies",
    )


@app.post("/api/v1/strategies")
async def create_strategy(
        request: StrategyRequest,
        current_user: User = Depends(get_current_active_user),
):
    """Create a strategy."""
    del current_user
    strategy = InMemoryStrategyStore.create(request.model_dump())
    return api_response(
        success=True,
        data=strategy,
        message=f"Strategy '{strategy['name']}' created successfully",
    )


@app.get("/api/v1/strategies/{strategy_id}")
async def get_strategy(
        strategy_id: int,
        current_user: User = Depends(get_current_active_user),
):
    """Get one strategy."""
    del current_user
    strategy = InMemoryStrategyStore.get(strategy_id)
    if not strategy:
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy retrieved")


@app.put("/api/v1/strategies/{strategy_id}")
async def update_strategy(
        strategy_id: int,
        request: StrategyRequest,
        current_user: User = Depends(get_current_active_user),
):
    """Update one strategy."""
    del current_user
    strategy = InMemoryStrategyStore.update(strategy_id, request.model_dump())
    if not strategy:
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy updated")


@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(
        strategy_id: int,
        current_user: User = Depends(get_current_active_user),
):
    """Delete one strategy."""
    del current_user
    if not InMemoryStrategyStore.delete(strategy_id):
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, message="Strategy deleted")


@app.get("/api/v1/strategies/{strategy_id}/versions")
async def get_strategy_versions(
        strategy_id: int,
        current_user: User = Depends(get_current_active_user),
):
    """Get in-memory version history for a strategy."""
    del current_user
    return api_response(
        success=True,
        data={"versions": InMemoryStrategyStore.versions(strategy_id)},
        message="Strategy version history retrieved",
    )


@app.post("/api/v1/strategies/{strategy_id}/versions/{version_id}/revert")
async def revert_strategy_version(
        strategy_id: int,
        version_id: int,
        request: StrategyVersionRevertRequest,
        current_user: User = Depends(get_current_active_user),
):
    """Revert a strategy to a prior stored version."""
    del request, current_user
    strategy = InMemoryStrategyStore.revert(strategy_id, version_id)
    if not strategy:
        return api_response(
            success=False,
            message="Strategy version not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy reverted")


# ============================================================================
# MAIN SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    # Configuration from environment
    host = os.getenv("BOT_API_HOST", "0.0.0.0")
    port = int(os.getenv("BOT_API_PORT", 8889))
    workers = int(os.getenv("BOT_API_WORKERS", 1))

    # Run server
    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,  # Set to True for development
        log_level="info",
    )
