"""
Bot API Server - FastAPI server for controlling multiple bot instances
"""

import asyncio
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
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.shared.env_loader import load_repo_env
from src.shared.redis_env import redis_url
from src.shared.trading_validators import (
    ISO_DATE_PATTERN,
    normalize_market_list,
    validate_iso_date_range,
)

# Load structured config BEFORE importing project modules that initialize config/database.
load_repo_env(__file__)

# Import authentication modules
from src.api.v1.auth import router as auth_router  # noqa: E402
from src.api.v1.auth.password_2fa import (  # noqa: E402
    router as password_2fa_router,
)

# Import bot models and manager
from src.infrastructure.domain.bot_api_models import (  # noqa: E402
    BotCredentials,
    BotInstanceConfig,
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

from internal.domain.models import BacktestRun  # noqa: E402
from src.api.websocket_server import (  # noqa: E402
    WebSocketServer,
    broadcast_strategy_status,
    manager,
)
from src.infrastructure.broadcast import get_broadcast_bus  # noqa: E402

# Import database utilities
from src.infrastructure.database import DatabaseConfig, db  # noqa: E402

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

# Celery inspection helpers (list_celery_tasks, get_celery_task, revoke_celery_task,
# retry_celery_task, list_celery_workers, list_celery_queues, celery_health) are now
# imported directly by src/api/v1/celery_admin.py and no longer used here.
from src.shared.logging_setup import setup_logging  # noqa: E402
from src.shared.live_risk_controls import (
    assert_supported_live_risk_controls,
)  # noqa: E402
from src.shared.time_utils import utc_now_iso  # noqa: E402
from src.api.responses import (  # noqa: E402
    INTERNAL_ERROR_MESSAGE,
    api_response,
    trace_id_ctx,
)
from src.api.endpoint_timing import (  # noqa: E402
    endpoint_perf_headers as _endpoint_perf_headers,
    log_endpoint_timing as _log_endpoint_timing,
    payload_size_bytes as _payload_size_bytes,
)
from src.api.v1.strategies import (  # noqa: E402
    InMemoryStrategyStore,
    StrategyRequest,
    StrategyVersionRevertRequest,
)
from src.api.v1.arbitrage import ArbitrageRuntimeSettingsRequest  # noqa: E402
from src.trading.arbitrage_observability import snapshot_metrics  # noqa: E402
from src.trading.arbitrage_runtime_config import (  # noqa: E402
    get_feature_flags,
    get_runtime_settings,
)
from src.trading.dydx_client import connect_dydx, connect_dydx_runtime  # noqa: E402

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
# trace_id_ctx / INTERNAL_ERROR_MESSAGE / api_response live in src/api/responses.py
# (re-imported above) so extracted route modules can share them without a circular import.
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


# StrategyRequest / StrategyVersionRevertRequest / InMemoryStrategyStore now live in
# src/api/v1/strategies.py and are re-imported above for the backtest→strategy path.


class RuntimePreflightRequest(BaseModel):
    """Preflight payload for environment-specific runtime readiness checks."""

    credentials: BotCredentials
    trading_params: TradingParameters
    instance_name: Optional[str] = None


# ArbitrageRuntimeSettingsRequest moved to src/api/v1/arbitrage.py (re-imported above).


# InMemoryStrategyStore moved to src/api/v1/strategies.py (re-imported above for
# the backtest→strategy creation path).


def _bot_manager_ready() -> bool:
    return bot_manager is not None


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
    # Start the cross-worker WebSocket broadcast subscriber early (no-op when
    # WS_BROADCAST_ENABLED=false or no Redis URL resolves), BEFORE any broadcast
    # producer below (backtest auto-recovery, bot-manager status events) runs.
    # start() is non-raising and non-blocking: it spawns the listener, which
    # reconnects with backoff if Redis is not yet up.
    await get_broadcast_bus().start(manager.deliver_local_broadcast)
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
        # Stop the broadcast bus FIRST so in-flight fan-out drains before the
        # bot manager / job manager that produce those broadcasts tear down.
        await get_broadcast_bus().stop()
        await get_broadcast_bus().aclose()
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
app.openapi = custom_openapi  # type: ignore[method-assign]  # FastAPI's documented override pattern

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map FastAPI request-validation failures onto the standardized envelope.

    Without this, an out-of-bounds trading payload returns FastAPI's default
    ``{"detail": [...]}`` 422 instead of the ``api_response`` envelope required
    by the API safety contract. Kept scoped to ``RequestValidationError`` only;
    ``HTTPException`` keeps its default shape to limit regression surface.
    """
    del request
    return api_response(
        success=False,
        message="Validation error",
        data={"errors": jsonable_encoder(exc.errors())},
        status_code=422,
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for unhandled exceptions → standardized 500 envelope.

    Centralizes the envelope-preserving 500 behavior so individual routes no longer
    need a ``try/except Exception → return api_response(500)`` block, and clients
    always receive ``{success, message, data, timestamp, trace_id}`` rather than
    FastAPI's default ``{"detail": "Internal Server Error"}``. FastAPI dispatches by
    type specificity, so ``RequestValidationError`` (422) and ``HTTPException``
    (FastAPI default) still resolve to their own handlers; only truly unhandled
    ``Exception``s land here. ``BaseException`` (KeyboardInterrupt/SystemExit) is
    intentionally not caught.
    """
    logger.exception(
        "Unhandled exception on {method} {path}",
        method=request.method,
        path=request.url.path,
    )
    return api_response(
        success=False,
        message=INTERNAL_ERROR_MESSAGE,
        status_code=500,
    )


# Include authentication routes
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)
app.include_router(
    password_2fa_router,
    prefix="/api/v1/auth/2fa",
    tags=["Authentication", "2FA"],
)

# Include extracted route modules (monolith breakup). Monitoring is first; its
# routes live in src/api/v1/monitoring.py and inherit app middleware/auth/handlers.
from src.api.v1.monitoring import router as monitoring_router  # noqa: E402
from src.api.v1.celery_admin import router as celery_admin_router  # noqa: E402
from src.api.v1.strategies import router as strategies_router  # noqa: E402
from src.api.v1.arbitrage import router as arbitrage_router  # noqa: E402
from src.api.v1.bot_lifecycle import (  # noqa: E402
    configure_bot_lifecycle,
    create_bot_instance,
    delete_bot_instance,
    get_bot_instance,
    list_bot_instances,
    quick_deploy_bot,
    restart_bot_instance,
    router as bot_lifecycle_router,
    start_bot_instance,
    stop_bot_instance,
)
from src.api.v1.bot_records import (  # noqa: E402
    get_bot_history,
    get_bot_jobs,
    get_bot_stats,
    get_bot_trades,
    router as bot_records_router,
)
from src.api.v1.bot_realtime import (  # noqa: E402
    _authorize_websocket_connection,
    _resolve_realtime_bot_id,
    configure_bot_realtime,
    get_alerts,
    get_current_positions,
    get_market_data,
    get_position,
    get_position_history,
    get_realtime_stats,
    router as bot_realtime_router,
    websocket_alerts,
    websocket_bot_runtime,
    websocket_strategies,
)
from src.api.v1 import backtests as backtest_routes  # noqa: E402
from src.api.v1.backtests import (  # noqa: E402
    _backtest_capacity_snapshot,
    _broadcast_backtest_progress,
    _normalize_requested_pair_cap,
    _read_positive_int_env,
    _reset_strategy_resolution_metrics,
    _strategy_resolution_metrics_prometheus,
    _strategy_resolution_metrics_snapshot,
    backtest_service_scope,
    configure_backtest_routes,
    router as backtests_router,
)

# Preserve the historical ``src.api.server`` import/monkeypatch surface while the
# canonical implementations live in the extracted backtest router.
for _backtest_export in backtest_routes.__all__:
    globals().setdefault(_backtest_export, getattr(backtest_routes, _backtest_export))

configure_bot_lifecycle(
    bot_manager_provider=lambda: bot_manager,
    instance_rate_limiter=_check_instance_rate_limit,
)
configure_bot_realtime(
    bot_manager_provider=lambda: bot_manager,
    core_uow_factory=lambda session: UnitOfWork(session),
    realtime_uow_factory=lambda session: UnitOfWorkRealtime(session),
    auth_bypass_provider=lambda: is_auth_bypass_enabled(),
    bearer_authenticator=lambda token, session: authenticate_bearer_token(
        token, session
    ),
)
configure_backtest_routes(
    compatibility_namespace_provider=lambda: globals(),
    backtest_rate_limit_provider=lambda request: _check_backtest_rate_limit(request),
    websocket_authorizer=lambda websocket: _authorize_websocket_connection(websocket),
)

app.include_router(monitoring_router)
app.include_router(celery_admin_router)
app.include_router(strategies_router)
app.include_router(arbitrage_router)
app.include_router(bot_lifecycle_router)
app.include_router(bot_records_router)
app.include_router(bot_realtime_router)
app.include_router(backtests_router)


# ============================================================================
# API RESPONSE WRAPPER
# ============================================================================
# ``api_response`` (and ``trace_id_ctx`` / ``INTERNAL_ERROR_MESSAGE``) now live in
# ``src/api/responses.py`` and are re-imported at the top of this module so existing
# call sites and ``server.api_response`` / ``server.trace_id_ctx`` attribute access
# keep working unchanged.


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


# BOT LIFECYCLE ENDPOINTS — extracted to src/api/v1/bot_lifecycle.py.
# The canonical manager and instance-create rate limiter are injected above.


# BOT DATABASE RECORD ENDPOINTS — extracted to src/api/v1/bot_records.py.


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

    def _registered_routes(routes, prefix: str = ""):
        """Yield direct and lazily included FastAPI routes with effective paths.

        FastAPI 0.138+ stores ``include_router`` mounts as ``_IncludedRouter``
        objects. Walking only ``app.routes`` would omit every operation in an
        extracted router from this capability contract.
        """

        for route in routes:
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                include_context = getattr(route, "include_context", None)
                include_prefix = str(getattr(include_context, "prefix", "") or "")
                yield from _registered_routes(
                    getattr(original_router, "routes", []) or [],
                    f"{prefix}{include_prefix}",
                )
                continue

            path = f"{prefix}{getattr(route, 'path', '')}"
            yield route, path

    for route, path in _registered_routes(app.routes):
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


# ARBITRAGE ENDPOINTS — extracted to src/api/v1/arbitrage.py (APIRouter, mounted
# above via app.include_router). The 5 authenticated runtime visibility/settings
# routes and ArbitrageRuntimeSettingsRequest live there now; the request model is
# re-imported above for backwards-compatible server attribute access.


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


# CELERY INSPECTION ENDPOINTS — extracted to src/api/v1/celery_admin.py
# (APIRouter, mounted below via app.include_router). The 7 admin-only routes
# (tasks list/detail, revoke, retry, workers, queues, health) live there now.


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
                    "memory_available_gb": round(memory.available / (1024**3), 2),
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


# BOT REALTIME HTTP AND WEBSOCKET ENDPOINTS — extracted to src/api/v1/bot_realtime.py.
# BACKTEST HTTP AND WEBSOCKET ENDPOINTS — extracted to src/api/v1/backtests.py.


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
# MONITORING ENDPOINTS — extracted to src/api/v1/monitoring.py (APIRouter,
# mounted below via app.include_router). DataFrame memory/cleanup + DB pool
# metrics/health/history/diagnostics live there now.
# ============================================================================


# STRATEGY ENDPOINTS — extracted to src/api/v1/strategies.py (APIRouter, mounted
# below via app.include_router). The 8 strategy routes + StrategyRequest/
# StrategyVersionRevertRequest/InMemoryStrategyStore live there now (re-imported
# above for the backtest→strategy path).


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
