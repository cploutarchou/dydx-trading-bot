"""Unit coverage for src/api/server.py startup/lifespan and support seams.

Drives the lifespan context manager, runtime preflight, trace middleware,
rate limiters, markets cache, and diagnostics helpers directly with fakes —
no live database, Celery, Redis, or dYdX client.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import src.api.server as server
import src.api.v1.backtests as backtests
from src.infrastructure.domain.bot_api_models import (
    BotCredentials,
    BotStatus,
    TradingParameters,
)


@pytest.fixture(autouse=True)
def _restore_server_state(monkeypatch):
    monkeypatch.delenv("BACKTEST_WORKER_BACKEND", raising=False)
    saved_openapi_schema = server.app.openapi_schema
    saved_monitor_task = server.bot_manager_monitor_task
    server._markets_cache.clear()
    metrics = backtests._strategy_resolution_metrics
    saved_counts = dict(metrics.get("counts", {}))
    saved_recent = list(backtests._strategy_resolution_recent_paths)
    yield
    server._markets_cache.clear()
    server.app.openapi_schema = saved_openapi_schema
    if server.bot_manager_monitor_task is not None:
        server.bot_manager_monitor_task.cancel()
    server.bot_manager_monitor_task = saved_monitor_task
    with backtests._strategy_resolution_metrics_lock:
        metrics["counts"] = saved_counts
        backtests._strategy_resolution_recent_paths.clear()
        backtests._strategy_resolution_recent_paths.extend(saved_recent)


def _payload(response):
    return json.loads(response.body)


def _starlette_request(
    method="GET",
    path="/api/v1/example",
    query="",
    client=("1.2.3.4", 77),
    trace_id=None,
):
    headers = []
    if trace_id is not None:
        headers.append((b"x-trace-id", trace_id.encode()))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": headers,
        "client": client,
        "scheme": "http",
        "server": ("testserver", 80),
        "root_path": "",
    }
    return Request(scope)


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.headers = {}


# --- stderr filter -------------------------------------------------------------


def test_filtered_stderr_passes_through_and_filters_dydx_warnings():
    written = []
    flushed = []

    class _Inner:
        def write(self, message):
            written.append(message)

        def flush(self):
            flushed.append(True)

        def isatty(self):
            return False

    filtered = server._FilteredStderr(_Inner())
    filtered.write("ordinary message")
    filtered.write("Node URL should not contain http(s)://example")
    filtered.flush()
    assert written == ["ordinary message"]
    assert flushed  # pass-through writes flush immediately
    assert filtered.isatty() is False


# --- rate limiters ---------------------------------------------------------------


def _rate_request(forwarded=None, host="9.9.9.9"):
    headers = {}
    if forwarded is not None:
        headers["X-Forwarded-For"] = forwarded
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_sliding_window_rate_limiter_keys_and_limits():
    limiter = server._SlidingWindowRateLimiter(max_requests=2, window_seconds=60)

    # X-Forwarded-For wins; first hop of a proxy chain is used.
    assert limiter._caller_key(_rate_request(forwarded="7.7.7.7, 8.8.8.8")) == "7.7.7.7"
    assert limiter._caller_key(_rate_request(host="9.9.9.9")) == "9.9.9.9"
    assert limiter._caller_key(SimpleNamespace(headers={}, client=None)) == "unknown"

    request = _rate_request(host="9.9.9.9")
    assert limiter.is_allowed(request) is True
    assert limiter.is_allowed(request) is True
    assert limiter.is_allowed(request) is False  # over the cap

    # Old timestamps are pruned so a fresh window allows again.
    with limiter._lock:
        limiter._buckets["9.9.9.9"] = [time.monotonic() - 120]
    assert limiter.is_allowed(request) is True


def test_rate_limit_dependencies_raise_429_when_exceeded(monkeypatch):
    denied = SimpleNamespace(is_allowed=lambda request: False, _window=60)
    monkeypatch.setattr(server, "_backtest_rate_limiter", denied)
    with pytest.raises(HTTPException) as exc_info:
        server._check_backtest_rate_limit(SimpleNamespace())

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "60"

    monkeypatch.setattr(server, "_instance_create_rate_limiter", denied)
    with pytest.raises(HTTPException) as exc_info:
        server._check_instance_rate_limit(SimpleNamespace())
    assert exc_info.value.status_code == 429
    assert "instance creation" in exc_info.value.detail


def test_rate_limit_dependencies_pass_when_allowed(monkeypatch):
    allowed = SimpleNamespace(is_allowed=lambda request: True, _window=60)
    monkeypatch.setattr(server, "_backtest_rate_limiter", allowed)
    monkeypatch.setattr(server, "_instance_create_rate_limiter", allowed)
    assert server._check_backtest_rate_limit(SimpleNamespace()) is None
    assert server._check_instance_rate_limit(SimpleNamespace()) is None


class _FakeRedisPipeline:
    def __init__(self, results=None, error=None):
        self._results = results
        self._error = error
        self.commands = []

    def zremrangebyscore(self, key, low, high):
        self.commands.append(("zremrangebyscore", key))

    def zadd(self, key, mapping):
        self.commands.append(("zadd", key))

    def zcard(self, key):
        self.commands.append(("zcard", key))

    def expire(self, key, ttl):
        self.commands.append(("expire", key))

    def execute(self):
        if self._error is not None:
            raise self._error
        return self._results


class _FakeRedisClient:
    def __init__(self, results=None, error=None):
        self._results = results
        self._error = error

    def pipeline(self):
        return _FakeRedisPipeline(results=self._results, error=self._error)


def test_redis_rate_limiter_uses_redis_and_falls_back(monkeypatch):
    limiter = server._RedisSlidingWindowRateLimiter(
        max_requests=5,
        window_seconds=60,
        endpoint_label="unit",
        fallback=server._SlidingWindowRateLimiter(max_requests=1, window_seconds=60),
    )

    # Healthy redis: count from the pipeline decides.
    limiter._redis_client = _FakeRedisClient(results=[0, 1, 3, True])
    assert limiter.is_allowed(_rate_request()) is True
    limiter._redis_client = _FakeRedisClient(results=[0, 1, 6, True])
    assert limiter.is_allowed(_rate_request()) is False

    # Redis execution failure trips the unavailable flag and falls back.
    limiter._redis_client = _FakeRedisClient(error=RuntimeError("redis down"))
    assert limiter._redis_unavailable is False
    limiter.is_allowed(_rate_request())  # fallback (max 1): first call allowed
    assert limiter._redis_unavailable is True
    assert limiter._redis_retry_at > time.monotonic()

    # Within the retry window the client is not re-created; fallback answers.
    request = _rate_request(host="2.2.2.2")
    limiter._redis_client = None
    assert limiter.is_allowed(request) is True  # fallback first hit
    assert limiter.is_allowed(request) is False  # fallback second hit

    # A cached client short-circuits client creation.
    cached = _FakeRedisClient(results=[0, 1, 1, True])
    limiter._redis_unavailable = False
    limiter._redis_retry_at = 0.0
    limiter._redis_client = cached
    assert limiter._get_redis() is cached


def test_redis_rate_limiter_without_redis_package(monkeypatch):
    limiter = server._RedisSlidingWindowRateLimiter(
        max_requests=5,
        window_seconds=60,
        endpoint_label="unit",
        fallback=server._SlidingWindowRateLimiter(max_requests=10, window_seconds=60),
    )
    limiter._redis_unavailable = True
    limiter._redis_retry_at = time.monotonic() + 30
    assert limiter._get_redis() is None

    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    limiter._redis_unavailable = False
    limiter._redis_retry_at = 0.0
    assert limiter._get_redis() is None
    assert limiter._redis_unavailable is True


# --- env readers / markets cache ---------------------------------------------------


def test_env_reader_variants(monkeypatch):
    for name in ("SERVER_UNIT_INT", "SERVER_UNIT_FLOAT"):
        monkeypatch.delenv(name, raising=False)

    assert server._read_non_negative_int_env("SERVER_UNIT_INT", 4) == 4
    monkeypatch.setenv("SERVER_UNIT_INT", "junk")
    assert server._read_non_negative_int_env("SERVER_UNIT_INT", 4) == 4
    monkeypatch.setenv("SERVER_UNIT_INT", "-6")
    assert server._read_non_negative_int_env("SERVER_UNIT_INT", 4) == 0
    monkeypatch.setenv("SERVER_UNIT_INT", " 7 ")
    assert server._read_non_negative_int_env("SERVER_UNIT_INT", 4) == 7

    monkeypatch.setenv("SERVER_UNIT_FLOAT", "oops")
    assert server._read_non_negative_float_env("SERVER_UNIT_FLOAT", 1.25) == 1.25
    monkeypatch.setenv("SERVER_UNIT_FLOAT", "-1")
    assert server._read_non_negative_float_env("SERVER_UNIT_FLOAT", 1.25) == 0.0
    monkeypatch.setenv("SERVER_UNIT_FLOAT", "3.5")
    assert server._read_non_negative_float_env("SERVER_UNIT_FLOAT", 1.25) == 3.5

    monkeypatch.setenv("SERVER_UNIT_OPT", "12")
    assert server._optional_env_int("SERVER_UNIT_OPT") == 12
    monkeypatch.setenv("SERVER_UNIT_OPT", "nope")
    assert server._optional_env_int("SERVER_UNIT_OPT") is None
    monkeypatch.delenv("SERVER_UNIT_OPT", raising=False)
    assert server._optional_env_int("SERVER_UNIT_OPT") is None


def test_markets_cache_fresh_stale_and_disabled(monkeypatch):
    assert server._markets_cache_get(allow_stale=True) is None

    server._markets_cache_set({"markets": ["BTC-USD"]})
    fresh = server._markets_cache_get(allow_stale=False)
    assert fresh is not None and fresh["stale"] is False
    assert server._markets_cache_get(allow_stale=True)["stale"] is False

    # Expired entry: not returned fresh; returned stale while within the stale TTL.
    now = time.monotonic()
    with server._markets_cache_lock:
        server._markets_cache["last"]["expires_at"] = now - 10
    assert server._markets_cache_get(allow_stale=False) is None
    stale = server._markets_cache_get(allow_stale=True)
    assert stale is not None and stale["stale"] is True

    # Beyond the stale deadline nothing is served.
    with server._markets_cache_lock:
        server._markets_cache["last"]["expires_at"] = now - 10_000
    assert server._markets_cache_get(allow_stale=True) is None

    # TTL 0 disables writes entirely.
    monkeypatch.setattr(server, "_MARKETS_CACHE_TTL_SECONDS", 0)
    server._markets_cache_set({"markets": []})
    assert "last" not in server._markets_cache or (server._markets_cache_get() is None)


def test_runtime_db_pool_warning_branches(monkeypatch):
    def _config(pool_size, timeout_seconds, max_overflow=10):
        return SimpleNamespace(
            pool_size=pool_size,
            max_overflow=max_overflow,
            timeout_seconds=timeout_seconds,
        )

    monkeypatch.delenv("DB_MAX_CONNECTIONS", raising=False)
    assert server._runtime_db_pool_warnings(_config(10, 30)) == []

    monkeypatch.setenv("DB_MAX_CONNECTIONS", "5")
    warnings = server._runtime_db_pool_warnings(_config(10, 30))
    assert any("DB_MAX_CONNECTIONS" in warning for warning in warnings)

    monkeypatch.delenv("DB_MAX_CONNECTIONS", raising=False)
    assert len(server._runtime_db_pool_warnings(_config(10, 5))) == 1
    assert len(server._runtime_db_pool_warnings(_config(3, 30))) == 1
    assert len(server._runtime_db_pool_warnings(_config(3, 5))) == 2


# --- diagnostics helpers -------------------------------------------------------------


class _ExplodingManager:
    def get_recovery_diagnostics(self):
        raise RuntimeError("diag down")

    def get_db_sync_backoff_diagnostics(self):
        raise RuntimeError("diag down")


def test_bot_diagnostics_helpers_manage_and_unavailable(monkeypatch):
    monkeypatch.setattr(server, "bot_manager", None)
    recovery = server._bot_recovery_diagnostics()
    assert recovery["source"] == "unavailable"
    assert recovery["last_error"] == "bot manager unavailable"
    db_sync = server._bot_db_sync_diagnostics()
    assert db_sync["state"] == "unavailable"

    monkeypatch.setattr(server, "bot_manager", _ExplodingManager())
    assert server._bot_recovery_diagnostics()["source"] == "error"
    assert server._bot_db_sync_diagnostics()["state"] == "error"

    monkeypatch.setattr(
        server,
        "bot_manager",
        SimpleNamespace(
            get_recovery_diagnostics=lambda: {"source": "database", "loaded": 1},
            get_db_sync_backoff_diagnostics=lambda: {"active": False},
        ),
    )
    assert server._bot_recovery_diagnostics()["loaded"] == 1
    assert server._bot_db_sync_diagnostics()["state"] == "ok"


def test_backtest_storage_health_probe_variants():
    probed = {}

    def _probe():
        probed["called"] = True
        return {"ready": True, "artifacts": {"enabled": True}}

    service = SimpleNamespace(repository=SimpleNamespace(storage_health=_probe))
    assert server._backtest_storage_health(service)["artifacts"]["enabled"] is True
    assert probed == {"called": True}

    default = server._backtest_storage_health(SimpleNamespace())
    assert default["ready"] is True
    assert default["artifacts"] == {"enabled": False, "healthy": True}


# --- custom OpenAPI ------------------------------------------------------------------


def test_custom_openapi_adds_bearer_and_envelope():
    server.app.openapi_schema = None
    schema = server.custom_openapi()

    assert schema["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    assert schema["components"]["schemas"]["StandardApiResponse"]["required"] == [
        "success",
        "message",
        "data",
        "timestamp",
        "trace_id",
    ]
    bots_get = schema["paths"]["/api/v1/bots"]["get"]
    assert bots_get["security"] == [{"BearerAuth": []}]
    auth_paths = [path for path in schema["paths"] if path.startswith("/auth/")]
    assert auth_paths
    for path in auth_paths:
        for method, operation in schema["paths"][path].items():
            if method.lower() in {"get", "post", "put", "delete", "patch"}:
                applied = operation.get("security") or []
                assert {"BearerAuth": []} not in applied, path
    # Cached afterwards.
    assert server.custom_openapi() is schema


# --- exception handlers ----------------------------------------------------------------


def test_validation_and_unhandled_exception_handlers():
    class _FakeValidationError:
        def errors(self):
            return [{"loc": ["body", "x"], "msg": "bad"}]

    response = asyncio.run(
        server._validation_exception_handler(
            _starlette_request(), _FakeValidationError()
        )
    )
    assert response.status_code == 422
    body = _payload(response)
    assert body["success"] is False
    assert body["data"]["errors"][0]["msg"] == "bad"

    unhandled = asyncio.run(
        server._unhandled_exception_handler(
            _starlette_request(method="POST", path="/api/v1/bots"),
            RuntimeError("boom"),
        )
    )
    assert unhandled.status_code == 500
    assert _payload(unhandled)["message"] == server.INTERNAL_ERROR_MESSAGE


# --- lifespan ---------------------------------------------------------------------------


class _FakeBus:
    def __init__(self):
        self.started = []
        self.stopped = 0
        self.aclosed = 0

    async def start(self, deliver):
        self.started.append(deliver)

    async def stop(self):
        self.stopped += 1

    async def aclose(self):
        self.aclosed += 1


class _FakeJobManager:
    def __init__(self):
        self.created = []
        self.cancelled = []

    def create_supervised_task(self, coro, **kwargs):
        self.created.append(kwargs)
        return asyncio.create_task(coro)

    async def cancel_all(self, reason=None):
        self.cancelled.append(reason)


class _FakeLifecycleManager:
    max_instances = 5

    def __init__(self):
        self.calls = []

    def set_status_event_publisher(self, publisher):
        self.calls.append(("publisher", publisher))

    async def cleanup_dead_processes(self):
        self.calls.append(("cleanup",))

    async def auto_recover_live_runtimes(self):
        return {
            "checked": 2,
            "verified_running": ["a", "b"],
            "restarted": [],
            "marked_error": [],
        }

    async def list_instances(self):
        return [SimpleNamespace(status=BotStatus.RUNNING)]

    async def shutdown(self, *, stop_active=False):
        self.calls.append(("shutdown", stop_active))


class _FakeDbBackend:
    def __init__(self):
        self.calls = []
        self.startup_lock = _FakeStartupLock()

    def health_check(self):
        self.calls.append("health_check")
        return True

    def run_pending_migrations(self):
        self.calls.append("migrations")

    def create_all_tables(self):
        self.calls.append("create_all")

    def ensure_schema_compatibility(self):
        self.calls.append("schema_compat")

    def verify_required_tables(self):
        self.calls.append("verify_tables")


class _FakeStartupLock:
    def __init__(self, acquired=True):
        self.acquired = acquired
        self.acquire_calls = 0
        self.release_calls = 0

    def acquire(self):
        self.acquire_calls += 1
        return self.acquired

    def release(self):
        self.release_calls += 1


def _config_namespace():
    return SimpleNamespace(
        db_type="postgresql",
        db_host="db-host",
        db_port=5432,
        db_name="dydx_bot",
        cutover_mode="full",
        field_source="env",
        pool_size=10,
        max_overflow=10,
        timeout_seconds=30,
    )


def _wire_lifespan(
    monkeypatch,
    *,
    celery_ping=None,
    celery_error=None,
    recovery_error=None,
    manager=None,
):
    bus = _FakeBus()
    jobs = _FakeJobManager()
    db_backend = _FakeDbBackend()

    import src.infrastructure.workers.celery_app as celery_module

    class _Control:
        def ping(self, timeout=None, limit=None):
            if celery_error is not None:
                raise celery_error
            return celery_ping

    monkeypatch.setattr(
        celery_module, "celery_app", SimpleNamespace(control=_Control())
    )
    monkeypatch.setattr(server, "get_broadcast_bus", lambda: bus)
    monkeypatch.setattr(server, "async_job_manager", jobs)
    monkeypatch.setattr(server, "DatabaseConfig", lambda: _config_namespace())
    monkeypatch.setattr(server.db, "health_check", db_backend.health_check)
    monkeypatch.setattr(
        server.db, "run_pending_migrations", db_backend.run_pending_migrations
    )
    monkeypatch.setattr(server.db, "create_all_tables", db_backend.create_all_tables)
    monkeypatch.setattr(
        server.db, "ensure_schema_compatibility", db_backend.ensure_schema_compatibility
    )
    monkeypatch.setattr(
        server.db, "verify_required_tables", db_backend.verify_required_tables
    )
    monkeypatch.setattr(
        server.db, "startup_leader_lock", lambda: db_backend.startup_lock
    )
    monkeypatch.setattr(server, "validate_auth_bypass_configuration", lambda: None)
    monkeypatch.setattr(server, "is_auth_bypass_enabled", lambda: False)

    async def _recover(progress_callback=None):
        if recovery_error is not None:
            raise recovery_error
        return {
            "mode": "default",
            "candidate_count": 0,
            "restarted_count": 0,
            "marked_failed_count": 0,
        }

    @contextmanager
    def _scope():
        yield SimpleNamespace(auto_recover_interrupted_runs=_recover)

    monkeypatch.setattr(server, "backtest_service_scope", _scope)
    if manager is not None:
        monkeypatch.setattr(server, "bot_manager", manager)
    return bus, jobs, db_backend


def test_lifespan_full_startup_and_shutdown(monkeypatch):
    monkeypatch.setenv("BOT_STOP_RUNTIME_ON_API_SHUTDOWN", "true")
    monkeypatch.setenv("BOT_MANAGER_MONITOR_INTERVAL_SECONDS", "2")
    manager = _FakeLifecycleManager()
    bus, jobs, db_backend = _wire_lifespan(
        monkeypatch, celery_ping=[{"worker1": True}], manager=manager
    )

    async def _drive():
        async with server.lifespan(server.app):
            assert os.environ.get("BACKTEST_WORKER_BACKEND") == "celery"
            assert bus.started and callable(bus.started[0])
            assert ("publisher",) == (manager.calls[0][0],)
            assert jobs.created[0]["job_type"] == "readiness_check"

    asyncio.run(_drive())

    assert db_backend.calls == [
        "health_check",
        "migrations",
        "create_all",
        "schema_compat",
        "verify_tables",
    ]
    assert db_backend.startup_lock.acquire_calls == 1
    assert db_backend.startup_lock.release_calls == 1
    assert bus.stopped == 1
    assert bus.aclosed == 1
    assert jobs.cancelled == ["api shutdown"]
    assert ("shutdown", True) in manager.calls
    assert server.bot_manager_monitor_task is None


def test_lifespan_celery_probe_variants(monkeypatch):
    manager = _FakeLifecycleManager()
    _wire_lifespan(monkeypatch, celery_ping=[], manager=manager)

    async def _drive():
        async with server.lifespan(server.app):
            pass

    asyncio.run(_drive())  # ping returns no workers -> warning, still continues

    _wire_lifespan(
        monkeypatch, celery_error=RuntimeError("broker unreachable"), manager=manager
    )
    asyncio.run(_drive())  # probe raising -> warning, still continues

    # Pre-set backend env skips the Celery probe entirely.
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    _bus, _jobs, _db = _wire_lifespan(
        monkeypatch, celery_ping=[{"w": True}], manager=manager
    )
    asyncio.run(_drive())
    assert os.environ["BACKTEST_WORKER_BACKEND"] == "asyncio"


def test_lifespan_manager_unavailable_and_recovery_failure(monkeypatch):
    bus, _jobs, _db = _wire_lifespan(
        monkeypatch, celery_ping=[{"w": True}], manager=None
    )

    async def _drive():
        async with server.lifespan(server.app):
            pass

    asyncio.run(_drive())  # bot_manager None: warning path, no monitor task
    assert server.bot_manager_monitor_task is None

    _wire_lifespan(
        monkeypatch,
        celery_ping=[{"w": True}],
        recovery_error=RuntimeError("recovery failed"),
        manager=_FakeLifecycleManager(),
    )
    asyncio.run(_drive())  # recovery failure only logs


def test_lifespan_health_check_failure_aborts_startup(monkeypatch):
    _wire_lifespan(
        monkeypatch, celery_ping=[{"w": True}], manager=_FakeLifecycleManager()
    )
    monkeypatch.setattr(server.db, "health_check", lambda: False)

    async def _drive():
        async with server.lifespan(server.app):
            raise AssertionError("must not start when DB is unhealthy")

    with pytest.raises(RuntimeError, match="health check failed"):
        asyncio.run(_drive())


def test_lifespan_replaces_completed_monitor_task(monkeypatch):
    monkeypatch.setenv("BOT_MANAGER_MONITOR_INTERVAL_SECONDS", "2")
    manager = _FakeLifecycleManager()
    bus, jobs, _db = _wire_lifespan(
        monkeypatch, celery_ping=[{"w": True}], manager=manager
    )

    async def _drive():
        stale = asyncio.create_task(_sleep_coroutine())
        await stale  # completed task forces recreation on entry
        server.bot_manager_monitor_task = stale
        async with server.lifespan(server.app):
            assert server.bot_manager_monitor_task is not stale

    asyncio.run(_drive())


async def _sleep_coroutine():
    await asyncio.sleep(0)


def test_lifespan_auth_bypass_warning(monkeypatch):
    monkeypatch.setenv("BOT_STOP_RUNTIME_ON_API_SHUTDOWN", "false")
    manager = _FakeLifecycleManager()
    _wire_lifespan(monkeypatch, celery_ping=[{"w": True}], manager=manager)
    monkeypatch.setattr(server, "is_auth_bypass_enabled", lambda: True)
    monkeypatch.setattr(server, "current_environment_name", lambda: "development")

    async def _drive():
        async with server.lifespan(server.app):
            pass

    asyncio.run(_drive())
    assert ("shutdown", False) in manager.calls


def test_bot_manager_monitor_loop_variants(monkeypatch):
    class _BlockingManager:
        def __init__(self, error=None):
            self.error = error
            self.calls = 0

        async def cleanup_dead_processes(self):
            self.calls += 1
            if self.error is not None:
                raise self.error
            await asyncio.sleep(0.2)

    async def _cancel_during_cleanup():
        manager = _BlockingManager()
        monkeypatch.setattr(server, "bot_manager", manager)
        task = asyncio.create_task(server._bot_manager_monitor_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert manager.calls == 1

    asyncio.run(_cancel_during_cleanup())

    async def _survives_cleanup_error():
        manager = _BlockingManager(error=RuntimeError("cleanup exploded"))
        monkeypatch.setattr(server, "bot_manager", manager)
        task = asyncio.create_task(server._bot_manager_monitor_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert manager.calls >= 1

    asyncio.run(_survives_cleanup_error())

    async def _manager_none():
        monkeypatch.setattr(server, "bot_manager", None)
        task = asyncio.create_task(server._bot_manager_monitor_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(_manager_none())


# --- runtime preflight ------------------------------------------------------------------


class _FakeSubaccountAPI:
    def __init__(self, payload=None, status_error=None):
        self._payload = payload
        self._status_error = status_error

    async def get_subaccount(self, address, number):
        if self._status_error is not None:
            raise self._status_error
        return self._payload


def _preflight_request(
    *,
    chain_id="dydx-testnet-4",
    subaccount_number=0,
    usd_per_trade=10.0,
    usd_min_collateral=100.0,
    capital_allocation_usd=0.0,
    trailing_stop_pct=0.0,
):
    return server.RuntimePreflightRequest(
        credentials=BotCredentials(
            chain_id=chain_id, address="dydx1abc", mnemonic="alpha beta gamma delta"
        ),
        trading_params=TradingParameters(
            is_testnet=not chain_id.startswith("dydx-mainnet"),
            subaccount_number=subaccount_number,
            usd_per_trade=usd_per_trade,
            usd_min_collateral=usd_min_collateral,
            capital_allocation_usd=capital_allocation_usd,
            trailing_stop_pct=trailing_stop_pct,
            stop_loss_pct=2.0,
            take_profit_pct=5.0,
        ),
    )


def _preflight_client(monkeypatch, *, wallet=None, subaccount_api=None, error=None):
    async def _connect(address, mnemonic, is_testnet):
        if error is not None:
            raise error
        return SimpleNamespace(
            wallet=wallet,
            indexer_account=SimpleNamespace(account=subaccount_api),
        )

    monkeypatch.setattr(server, "connect_dydx_runtime", _connect)


def test_runtime_preflight_risk_control_rejection(monkeypatch):
    _preflight_client(monkeypatch, wallet=object())
    response = asyncio.run(
        server.runtime_preflight(
            _preflight_request(trailing_stop_pct=1.5), current_user=object()
        )
    )
    assert response.status_code == 422
    assert _payload(response)["data"]["error"] == "UNSUPPORTED_RISK_CONTROL"


def test_runtime_preflight_blockers(monkeypatch):
    http_error = httpx.HTTPStatusError(
        "not found",
        request=httpx.Request("GET", "https://indexer"),
        response=httpx.Response(404),
    )
    _preflight_client(
        monkeypatch,
        wallet=None,
        subaccount_api=_FakeSubaccountAPI(status_error=http_error),
    )
    response = asyncio.run(
        server.runtime_preflight(_preflight_request(), current_user=object())
    )
    body = _payload(response)
    assert response.status_code == 200
    assert body["data"]["wallet_ready"] is False
    assert any("wallet" in blocker.lower() for blocker in body["data"]["blockers"])
    assert any("not initialized" in blocker for blocker in body["data"]["blockers"])


def test_runtime_preflight_collateral_guardrails(monkeypatch):
    _preflight_client(
        monkeypatch,
        wallet=object(),
        subaccount_api=_FakeSubaccountAPI(
            payload={
                "subaccount": {
                    "freeCollateral": "5.0",
                    "equity": "7.5",
                    "openPerpetualPositions": {"BTC-USD": {}},
                }
            }
        ),
    )
    response = asyncio.run(
        server.runtime_preflight(
            _preflight_request(subaccount_number=2), current_user=object()
        )
    )
    data = _payload(response)["data"]
    assert data["selected_runtime_network"] == "testnet"
    assert data["account_exists"] is True
    assert data["available_collateral"] == 5.0
    assert data["equity"] == 7.5
    assert data["open_positions"] == 1
    assert data["ready"] is False
    assert any("below per-trade size" in blocker for blocker in data["blockers"])
    assert any("below minimum collateral" in blocker for blocker in data["blockers"])
    assert any("below recommended buffer" in warning for warning in data["warnings"])
    assert any("Higher risk" in warning for warning in data["warnings"])
    assert any("isolated from subaccount 0" in warning for warning in data["warnings"])
    assert data["trade_size_to_collateral_ratio"] == 2.0


def test_runtime_preflight_mainnet_ready(monkeypatch):
    _preflight_client(
        monkeypatch,
        wallet=object(),
        subaccount_api=_FakeSubaccountAPI(
            payload={
                "subaccount": {
                    "freeCollateral": "5000.0",
                    "equity": "6000.0",
                    "openPerpetualPositions": {},
                }
            }
        ),
    )
    response = asyncio.run(
        server.runtime_preflight(
            _preflight_request(chain_id="dydx-mainnet-0", usd_per_trade=50.0),
            current_user=object(),
        )
    )
    data = _payload(response)["data"]
    assert data["selected_runtime_network"] == "mainnet"
    assert data["ready"] is True
    assert data["blockers"] == []
    assert data["warnings"] == []
    assert data["trade_size_to_collateral_ratio"] == 0.01


def test_runtime_preflight_non_404_and_connect_failures(monkeypatch):
    server_error = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("GET", "https://indexer"),
        response=httpx.Response(503),
    )
    _preflight_client(
        monkeypatch,
        wallet=object(),
        subaccount_api=_FakeSubaccountAPI(status_error=server_error),
    )
    response = asyncio.run(
        server.runtime_preflight(_preflight_request(), current_user=object())
    )
    data = _payload(response)["data"]
    assert response.status_code == 200
    assert data["ready"] is False
    assert any("boom" in blocker for blocker in data["blockers"])

    _preflight_client(monkeypatch, error=RuntimeError("connect failed"))
    failed = asyncio.run(
        server.runtime_preflight(_preflight_request(), current_user=object())
    )
    data = _payload(failed)["data"]
    assert failed.status_code == 200
    assert data["wallet_ready"] is False
    assert data["blockers"] == ["connect failed"]
    assert "with blockers" in _payload(failed)["message"]


# --- trace middleware -----------------------------------------------------------------------


def test_trace_middleware_variants(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")

    def _next(status_code):
        async def _handler(request):
            return _FakeResponse(status_code)

        return _handler

    async def _run(request, call_next):
        return await server.request_trace_logging_middleware(request, call_next)

    # Inbound trace id is honored and echoed back.
    request = _starlette_request(trace_id="inbound-trace-1")
    response = asyncio.run(_run(request, _next(200)))
    assert response.headers["X-Trace-Id"] == "inbound-trace-1"

    # Generated trace id, query truncation, 500 error log path.
    long_query = "q=" + "a" * 300
    request = _starlette_request(method="POST", path="/api/v1/bots", query=long_query)
    response = asyncio.run(_run(request, _next(500)))
    assert response.headers["X-Trace-Id"]

    # 404 on a strategy runtime probe path logs at debug.
    request = _starlette_request(path="/api/v1/bots/strategy-1-7")
    response = asyncio.run(_run(request, _next(404)))
    assert response.status_code == 404

    # Plain 400 logs at warning.
    request = _starlette_request(path="/api/v1/other")
    response = asyncio.run(_run(request, _next(400)))
    assert response.status_code == 400

    # Exceptions propagate after failure logging.
    async def _explode(r):
        raise RuntimeError("handler failed")

    with pytest.raises(RuntimeError, match="handler failed"):
        asyncio.run(_run(_starlette_request(), _explode))

    # Production skips verbose logging but still tags the response.
    monkeypatch.setenv("ENVIRONMENT", "production")
    response = asyncio.run(_run(_starlette_request(), _next(200)))
    assert response.headers["X-Trace-Id"]


def test_expected_strategy_runtime_probe_404_branches():
    assert server._is_expected_strategy_runtime_probe_404(
        _starlette_request(path="/api/v1/bots/strategy-3-9"), 404
    )
    assert server._is_expected_strategy_runtime_probe_404(
        _starlette_request(path="/api/v1/bots/strategy-3-9/stats"), 404
    )
    assert not server._is_expected_strategy_runtime_probe_404(
        _starlette_request(path="/api/v1/bots/strategy-3-9"), 500
    )
    assert not server._is_expected_strategy_runtime_probe_404(
        _starlette_request(method="POST", path="/api/v1/bots/strategy-3-9"), 404
    )
    assert not server._is_expected_strategy_runtime_probe_404(
        _starlette_request(path="/api/v1/bots/other-1"), 404
    )


# --- health / ready / status routes ------------------------------------------------------------


def _wire_health_scope(monkeypatch, runtime_health=None):
    @contextmanager
    def _scope():
        yield SimpleNamespace(
            get_runtime_health=lambda: (
                runtime_health if runtime_health is not None else {"queue_depth": 0}
            )
        )

    monkeypatch.setattr(server, "backtest_service_scope", _scope)


def test_health_and_ready_routes(monkeypatch):
    _wire_health_scope(monkeypatch)
    health = asyncio.run(server.health_check())
    body = _payload(health)
    assert body["data"]["status"] == "healthy"
    assert "backtest_limits" in body["data"]
    assert "bot_recovery" in body["data"]

    ready = asyncio.run(server.readiness_check())
    assert ready.status_code == 200
    assert _payload(ready)["data"]["status"] == "ready"

    monkeypatch.setattr(server, "bot_manager", None)
    not_ready = asyncio.run(server.readiness_check())
    assert not_ready.status_code == 503
    assert _payload(not_ready)["data"]["status"] == "not_ready"


def test_system_status_routes(monkeypatch):
    _wire_health_scope(monkeypatch)

    monkeypatch.setattr(server, "bot_manager", None)
    degraded = asyncio.run(server.system_status(current_user=object()))
    data = _payload(degraded)["data"]
    assert data["bot_instances"] == {"total": 0, "running": 0, "max_allowed": 0}

    manager = _FakeLifecycleManager()
    monkeypatch.setattr(server, "bot_manager", manager)
    status = asyncio.run(server.system_status(current_user=object()))
    data = _payload(status)["data"]
    assert data["bot_instances"]["total"] == 1
    assert data["bot_instances"]["running"] == 1
    assert "system_resources" in data

    class _ExplodingList(_FakeLifecycleManager):
        async def list_instances(self):
            raise RuntimeError("listing failed")

    monkeypatch.setattr(server, "bot_manager", _ExplodingList())
    failed = asyncio.run(server.system_status(current_user=object()))
    assert failed.status_code == 500


def test_user_profile_route_defaults():
    response = asyncio.run(
        server.get_current_user_profile(
            current_user=SimpleNamespace(username="alice", email="a@x.io")
        )
    )
    data = _payload(response)["data"]
    assert data["id"] == 1
    assert data["username"] == "alice"
    assert data["is_admin"] is False
    assert data["is_active"] is True
    assert data["created_at"]

    admin = asyncio.run(
        server.get_current_user_profile(current_user=SimpleNamespace(is_superuser=True))
    )
    assert _payload(admin)["data"]["is_admin"] is True


def test_runtime_db_config_route(monkeypatch):
    monkeypatch.setattr(
        server,
        "DatabaseConfig",
        lambda: SimpleNamespace(
            to_diagnostics=lambda: {"db_type": "postgresql", "count": None}
        ),
    )
    response = asyncio.run(server.runtime_db_config(current_user=object()))
    assert _payload(response)["data"]["db_type"] == "postgresql"
    assert _payload(response)["data"]["count"] == 1

    def _boom():
        raise RuntimeError("config failed")

    monkeypatch.setattr(server, "DatabaseConfig", _boom)
    failed = asyncio.run(server.runtime_db_config(current_user=object()))
    assert failed.status_code == 500


def test_metrics_and_capabilities_routes():
    metrics = asyncio.run(server.metrics())
    assert metrics["service"] == "bot"
    assert "arbitrage" in metrics

    capabilities = asyncio.run(server.api_capabilities())
    data = _payload(capabilities)["data"]
    assert any(
        route.startswith("POST /api/v1/backtests")
        for route in data["command_endpoints"]
    )
    assert any(
        route.startswith("GET /api/v1/backtests") for route in data["query_endpoints"]
    )
    assert any("WS " in route for route in data["websocket_channels"])


def test_strategy_resolution_metric_routes():
    metrics = asyncio.run(server.get_strategy_resolution_metrics(current_user=object()))
    assert "counts" in _payload(metrics)["data"]

    prom = asyncio.run(
        server.get_strategy_resolution_metrics_prometheus(current_user=object())
    )
    assert b"bot_strategy_resolution_total" in prom.body

    admin = asyncio.run(
        server.get_strategy_resolution_metrics_admin(current_user=object())
    )
    assert "counts" in _payload(admin)["data"]

    reset = asyncio.run(
        server.reset_strategy_resolution_metrics_admin(current_user=object())
    )
    assert _payload(reset)["data"]["counts"]["store"] == 0


# --- markets route ------------------------------------------------------------------------------


class _FakeMarketsClient:
    def __init__(self, payload=None, close_error=None):
        self._payload = payload
        self._close_error = close_error

        class _Node:
            async def close(self):
                if close_error is not None:
                    raise close_error

        self.node = _Node()
        self.indexer_client = _Node()
        self.indexer = SimpleNamespace(
            markets=SimpleNamespace(get_perpetual_markets=self._get_markets)
        )

    async def _get_markets(self):
        return self._payload


def test_perpetual_markets_route_cache_live_stale_and_failure(monkeypatch):
    server._markets_cache.clear()

    # Fresh cache hit serves without a network call and honors the cap.
    server._markets_cache_set(
        {"markets": ["BTC-USD", "ETH-USD", "SOL-USD"], "count": 3, "source": "dydx"}
    )
    response = asyncio.run(server.list_perpetual_markets(limit=2))
    body = _payload(response)
    assert body["data"]["markets"] == ["BTC-USD", "ETH-USD"]
    assert body["data"]["source"] == "cache"
    assert response.headers["X-Cache-Hit"] == "1"

    server._markets_cache.clear()

    # Live fetch populates the cache; failing closers are swallowed.
    async def _connect():
        return _FakeMarketsClient(
            payload={"markets": {"ETH-USD": {}, "BTC-USD": {}}},
            close_error=RuntimeError("x"),
        )

    monkeypatch.setattr(server, "connect_dydx", _connect)
    response = asyncio.run(server.list_perpetual_markets())
    body = _payload(response)
    assert body["data"]["markets"] == ["BTC-USD", "ETH-USD"]
    assert body["data"]["source"] == "dydx"

    # Live failure with a stale entry serves the stale payload.
    now = time.monotonic()
    with server._markets_cache_lock:
        server._markets_cache["last"]["expires_at"] = now - 10

    async def _connect_boom():
        raise RuntimeError("indexer down")

    monkeypatch.setattr(server, "connect_dydx", _connect_boom)
    response = asyncio.run(server.list_perpetual_markets())
    body = _payload(response)
    assert body["data"]["source"] == "cache_stale"
    assert response.headers["X-Cache-Stale"] == "1"

    # Live failure without usable stale data fails closed with 503.
    server._markets_cache.clear()
    failed = asyncio.run(server.list_perpetual_markets())
    assert failed.status_code == 503
    assert _payload(failed)["data"]["error"] == "MARKET_RESOLUTION_FAILED"


# --- CORS settings ---------------------------------------------------------------


def test_cors_settings_default_to_wildcard_without_credentials(monkeypatch):
    monkeypatch.delenv("BOT_API_CORS_ORIGINS", raising=False)
    origins, allow_credentials = server._resolve_cors_settings()
    assert origins == ["*"]
    assert allow_credentials is False


def test_cors_settings_explicit_origins_enable_credentials(monkeypatch):
    monkeypatch.setenv(
        "BOT_API_CORS_ORIGINS",
        "https://dashboard.example, https://ops.example ",
    )
    origins, allow_credentials = server._resolve_cors_settings()
    assert origins == ["https://dashboard.example", "https://ops.example"]
    assert allow_credentials is True


def test_cors_settings_blank_env_falls_back_to_wildcard(monkeypatch):
    monkeypatch.setenv("BOT_API_CORS_ORIGINS", " , ,, ")
    origins, allow_credentials = server._resolve_cors_settings()
    assert origins == ["*"]
    assert allow_credentials is False


def test_lifespan_fails_fast_when_leader_lock_unavailable(monkeypatch):
    manager = _FakeLifecycleManager()
    bus, jobs, db_backend = _wire_lifespan(
        monkeypatch, celery_ping=[{"worker1": True}], manager=manager
    )
    db_backend.startup_lock.acquired = False

    async def _drive():
        async with server.lifespan(server.app):
            raise AssertionError("lifespan must not start serving without the lock")

    with pytest.raises(RuntimeError, match="Startup leader lock not acquired"):
        asyncio.run(_drive())

    # The critical section never ran and the lock was not released
    assert db_backend.calls == ["health_check"]
    assert db_backend.startup_lock.release_calls == 0
