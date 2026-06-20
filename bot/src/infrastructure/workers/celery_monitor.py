"""Admin-only Celery inspection helpers for bot background work."""

from __future__ import annotations

import copy
import os
import socket
import threading
import time
import traceback as traceback_module
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar, cast

from celery import states
from celery.result import AsyncResult
from src.infrastructure.database import db
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.workers.celery_app import celery_app

SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "mnemonic",
    "private",
    "credential",
    "authorization",
    "auth",
    "broker",
    "backend",
    "url",
    "dsn",
)

TERMINAL_STATES = {states.SUCCESS, states.FAILURE, states.REVOKED}
TASK_CONTEXT_KEY = "_task_context"
TASK_FAILURE_KEY = "_task_failure"
DEFAULT_CELERY_QUEUES = ("backtests", "default", "high_priority", "scheduled")
_MONITOR_CACHE: Dict[str, Dict[str, Any]] = {}
_MONITOR_CACHE_LOCK = threading.Lock()
_T = TypeVar("_T")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _monitor_cache_ttl_seconds(cache_key: Optional[str] = None) -> float:
    prefix = str(cache_key or "").split(":", 1)[0].strip().lower()
    default_by_prefix = {
        "tasks": 5.0,
        "workers": 5.0,
        "health": 5.0,
        "queues": 2.0,
    }
    default_ttl = default_by_prefix.get(prefix, 2.0)

    raw = None
    if prefix:
        raw = os.getenv(f"CELERY_MONITOR_CACHE_TTL_{prefix.upper()}_SECONDS")
    if raw in (None, ""):
        raw = os.getenv("CELERY_MONITOR_CACHE_TTL_SECONDS")
    if raw in (None, ""):
        return default_ttl
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return default_ttl


def _clear_monitor_cache() -> None:
    with _MONITOR_CACHE_LOCK:
        _MONITOR_CACHE.clear()


def _cached_monitor_result(cache_key: str, factory: Callable[[], _T]) -> _T:
    ttl = _monitor_cache_ttl_seconds(cache_key)
    if ttl <= 0:
        return factory()

    now = time.monotonic()
    with _MONITOR_CACHE_LOCK:
        entry = _MONITOR_CACHE.get(cache_key)
        if entry and float(entry.get("expires_at", 0.0)) > now:
            cached_value = entry.get("value")
            if cached_value is not None:
                return cast(_T, copy.deepcopy(cached_value))

    value = factory()
    with _MONITOR_CACHE_LOCK:
        _MONITOR_CACHE[cache_key] = {
            "expires_at": now + ttl,
            "value": copy.deepcopy(value),
        }
    return value


def celery_state_from_backtest(status: Any) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"completed", "success", "succeeded", "done"}:
        return states.SUCCESS
    if normalized in {"failed", "error", "timeout", "timed_out", "stale", "stalled"}:
        return states.FAILURE
    if normalized in {"cancelled", "canceled", "cancel_requested"}:
        return states.REVOKED
    if normalized in {"running", "started", "active", "processing"}:
        return states.STARTED
    if normalized in {"retry", "retrying"}:
        return states.RETRY
    return states.PENDING


def normalized_task_status(status: Any) -> str:
    normalized = str(status or "").strip().upper()
    if normalized in {states.SUCCESS, "COMPLETED", "SUCCEEDED", "DONE"}:
        return "success"
    if normalized in {states.FAILURE, "FAILED", "ERROR", "TIMEOUT", "TIMED_OUT"}:
        return "failed"
    if normalized in {states.RETRY, "RETRYING", "RETRY"}:
        return "retrying"
    if normalized in {states.STARTED, "RUNNING", "ACTIVE", "PROCESSING"}:
        return "running"
    if normalized in {states.REVOKED, "CANCELLED", "CANCELED"}:
        return "cancelled"
    return "pending"


def _is_sensitive_key(key: Any) -> bool:
    lowered = str(key or "").strip().lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, nested in value.items():
            redacted[str(key)] = (
                "redacted" if _is_sensitive_key(key) else redact_payload(nested)
            )
        return redacted
    if isinstance(value, (list, tuple, set)):
        return [redact_payload(item) for item in value]
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + "...[truncated]"
    return value


def build_progress_meta(
    *,
    run_id: str,
    progress_percent: float,
    current_pair: Optional[str],
    current_step: Optional[str],
    total_pairs: Optional[int] = None,
    completed_pairs: Optional[int] = None,
    current_phase: Optional[str] = None,
    eta_seconds: Optional[float] = None,
    strategy_id: Optional[Any] = None,
    bot_id: Optional[Any] = None,
    environment: Optional[str] = None,
    selected_pairs: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    return {
        "task_id": run_id,
        "task_name": "backtests.run",
        "status": "PROGRESS",
        "progress_percent": round(float(progress_percent or 0.0), 2),
        "current_pair": current_pair,
        "current_step": current_step,
        "current_phase": current_phase or current_step,
        "total_pairs": total_pairs,
        "completed_pairs": completed_pairs,
        "eta_seconds": eta_seconds,
        "last_heartbeat_at": utc_now_iso(),
        "strategy_id": strategy_id,
        "backtest_run_id": run_id,
        "bot_id": bot_id,
        "environment": environment
        or os.getenv("ENVIRONMENT")
        or os.getenv("APP_ENV")
        or "local",
        "selected_pairs": list(selected_pairs or []),
    }


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    return []


def _runtime_seconds(started_at: Any, finished_at: Any) -> Optional[float]:
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        end = (
            datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
            if finished_at
            else datetime.now(timezone.utc)
        )
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return round(max(0.0, (end - start).total_seconds()), 3)
    except Exception:
        return None


def _result_payload(result: AsyncResult) -> Dict[str, Any]:
    info = result.info
    payload: Dict[str, Any] = {}
    if isinstance(info, dict):
        payload.update(info)
    elif info is not None and result.state in {states.FAILURE, states.RETRY}:
        payload["error_message"] = str(info)
    return redact_payload(payload)


def _backtest_request(run: Dict[str, Any]) -> Dict[str, Any]:
    request = run.get("request")
    return request if isinstance(request, dict) else {}


def _task_context(run: Dict[str, Any]) -> Dict[str, Any]:
    request = _backtest_request(run)
    context = request.get(TASK_CONTEXT_KEY)
    return context if isinstance(context, dict) else {}


def _task_failure(run: Dict[str, Any]) -> Dict[str, Any]:
    request = _backtest_request(run)
    failure = request.get(TASK_FAILURE_KEY)
    return failure if isinstance(failure, dict) else {}


def _task_from_backtest(
    run: Dict[str, Any], result: Optional[AsyncResult] = None
) -> Dict[str, Any]:
    request = _backtest_request(run)
    task_context = _task_context(run)
    task_failure = _task_failure(run)
    progress = float(run.get("progress_pct") or 0.0)
    task_id = str(run.get("worker_task_id") or run.get("run_id") or "")
    status = (
        result.state
        if result is not None and result.state != states.PENDING
        else celery_state_from_backtest(run.get("status"))
    )
    started_at = run.get("started_at")
    finished_at = run.get("finished_at") or run.get("completed_at")
    result_meta = _result_payload(result) if result is not None else {}
    error_message = (
        result_meta.get("error_message")
        or task_failure.get("error_message")
        or run.get("error_message")
        or run.get("error")
    )
    traceback_value = (
        result.traceback
        if result is not None and result.traceback
        else task_failure.get("traceback") or run.get("traceback")
    )
    selected_pairs = (
        _as_list(result_meta.get("selected_pairs"))
        or _as_list(task_context.get("selected_pairs"))
        or _as_list(run.get("selected_pairs"))
        or _as_list(request.get("selected_pairs"))
        or _as_list(request.get("pairs"))
    )
    metadata: Dict[str, Any] = {}
    task_metadata = task_context.get("metadata")
    if isinstance(task_metadata, dict):
        metadata.update(task_metadata)
    result_metadata = result_meta.get("metadata")
    if isinstance(result_metadata, dict):
        metadata.update(result_metadata)
    if "pair_count" not in metadata:
        metadata["pair_count"] = len(selected_pairs)
    if task_context.get("payload_hash") and "payload_hash" not in metadata:
        metadata["payload_hash"] = task_context.get("payload_hash")
    if task_context.get("source") and "source" not in metadata:
        metadata["source"] = task_context.get("source")
    if task_context.get("strategy_name") and "strategy_name" not in metadata:
        metadata["strategy_name"] = task_context.get("strategy_name")

    return {
        "task_id": task_id,
        "task_name": "backtests.run",
        "queue": result_meta.get("queue")
        or run.get("queue")
        or task_context.get("queue")
        or "backtests",
        "status": status,
        "normalized_status": normalized_task_status(status),
        "created_at": run.get("created_at"),
        "started_at": started_at,
        "finished_at": finished_at,
        "runtime_seconds": _runtime_seconds(started_at, finished_at),
        "progress_percent": progress,
        "current_step": run.get("current_task") or result_meta.get("current_step"),
        "current_pair": run.get("current_pair") or result_meta.get("current_pair"),
        "strategy_id": result_meta.get("strategy_id")
        or task_context.get("strategy_id")
        or run.get("strategy_id")
        or request.get("strategy_id"),
        "backtest_run_id": run.get("run_id"),
        "bot_id": result_meta.get("bot_id")
        or task_context.get("bot_id")
        or run.get("bot_id")
        or request.get("bot_id"),
        "environment": result_meta.get("environment")
        or task_context.get("environment")
        or run.get("environment")
        or request.get("environment")
        or os.getenv("ENVIRONMENT")
        or os.getenv("APP_ENV")
        or "local",
        "selected_pairs": selected_pairs,
        "error_code": result_meta.get("error_code") or task_failure.get("error_code"),
        "error_message": str(error_message) if error_message else None,
        "traceback": traceback_value,
        "worker_hostname": result_meta.get("worker_hostname")
        or task_context.get("worker_hostname")
        or result_meta.get("hostname"),
        "retry_count": result_meta.get("retry_count")
        or task_context.get("retry_count"),
        "parent_task_id": result_meta.get("parent_task_id"),
        "child_task_ids": result_meta.get("child_task_ids") or [],
        "result": (
            redact_payload(result.result)
            if result is not None and result.state == states.SUCCESS
            else None
        ),
        "metadata": redact_payload(metadata),
    }


def _matches_filters(task: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    for key, expected in filters.items():
        if expected in (None, ""):
            continue
        value = task.get(key)
        if key == "status":
            if str(value or "").lower() != str(expected).lower():
                return False
        elif str(value or "") != str(expected):
            return False
    return True


def _load_backtest_runs() -> List[Dict[str, Any]]:
    session = db.get_session()
    try:
        repository = BacktestRepository(session)
        summaries = repository.list_runs(limit=None, offset=0)
        runs: List[Dict[str, Any]] = []
        for summary in summaries:
            run_id = str(summary.get("run_id") or "").strip()
            if not run_id:
                continue
            runs.append(repository.get_run(run_id) or summary)
        return runs
    finally:
        session.close()


def _inspect() -> Any:
    return celery_app.control.inspect(
        timeout=float(os.getenv("CELERY_INSPECT_TIMEOUT", "1.5"))
    )


def _inspect_call(method_name: str, default: Any) -> Any:
    try:
        inspector = _inspect()
        method = getattr(inspector, method_name, None)
        if not callable(method):
            return default
        payload = method()
        return payload if payload is not None else default
    except Exception:
        return default


def _should_probe_async_result(run: Dict[str, Any]) -> bool:
    if str(os.getenv("CELERY_TASK_RESULT_ENRICH_TERMINAL", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    status = celery_state_from_backtest(run.get("status"))
    return status not in TERMINAL_STATES


def _flatten_worker_tasks(
    worker_payload: Optional[Dict[str, Any]], state_name: str
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    if not worker_payload:
        return tasks
    for worker, items in worker_payload.items():
        for item in items or []:
            request = (
                item.get("request") if isinstance(item.get("request"), dict) else item
            )
            task_id = str(request.get("id") or item.get("id") or "")
            if not task_id:
                continue
            tasks.append(
                {
                    "task_id": task_id,
                    "task_name": request.get("name") or item.get("name"),
                    "queue": (
                        request.get("delivery_info", {}).get("routing_key")
                        if isinstance(request.get("delivery_info"), dict)
                        else None
                    ),
                    "status": state_name,
                    "normalized_status": normalized_task_status(state_name),
                    "worker_hostname": worker,
                    "created_at": None,
                    "started_at": None,
                    "finished_at": None,
                    "runtime_seconds": None,
                    "progress_percent": None,
                    "current_step": None,
                    "strategy_id": None,
                    "backtest_run_id": (
                        task_id if str(request.get("name")) == "backtests.run" else None
                    ),
                    "bot_id": None,
                    "environment": os.getenv("ENVIRONMENT")
                    or os.getenv("APP_ENV")
                    or "local",
                    "selected_pairs": [],
                    "error_message": None,
                    "traceback": None,
                    "retry_count": None,
                    "parent_task_id": request.get("parent_id"),
                    "child_task_ids": [],
                    "metadata": redact_payload(request),
                }
            )
    return tasks


def list_celery_tasks(
    filters: Optional[Dict[str, Any]] = None, limit: int = 100
) -> Dict[str, Any]:
    filters = filters or {}
    cache_key = f"tasks:{tuple(sorted(filters.items()))}:{max(1, min(limit, 500))}"

    def _build_tasks() -> Dict[str, Any]:
        tasks_by_id: Dict[str, Dict[str, Any]] = {}

        for run in _load_backtest_runs():
            task_id = str(run.get("worker_task_id") or run.get("run_id") or "")
            if not task_id:
                continue
            result = (
                AsyncResult(task_id, app=celery_app)
                if _should_probe_async_result(run)
                else None
            )
            tasks_by_id[task_id] = _task_from_backtest(run, result)

        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                active_future = executor.submit(_inspect_call, "active", {})
                reserved_future = executor.submit(_inspect_call, "reserved", {})
                scheduled_future = executor.submit(_inspect_call, "scheduled", {})

                worker_tasks = []
                worker_tasks.extend(
                    _flatten_worker_tasks(active_future.result(), states.STARTED)
                )
                worker_tasks.extend(
                    _flatten_worker_tasks(reserved_future.result(), states.PENDING)
                )
                worker_tasks.extend(
                    _flatten_worker_tasks(scheduled_future.result(), "SCHEDULED")
                )
            for task in worker_tasks:
                task_id = task["task_id"]
                if task_id in tasks_by_id:
                    tasks_by_id[task_id].update(
                        {k: v for k, v in task.items() if v not in (None, "", [])}
                    )
                else:
                    tasks_by_id[task_id] = task
        except Exception:
            pass

        tasks = [
            task for task in tasks_by_id.values() if _matches_filters(task, filters)
        ]
        tasks.sort(
            key=lambda item: str(
                item.get("created_at") or item.get("started_at") or ""
            ),
            reverse=True,
        )
        return {"tasks": tasks[: max(1, min(limit, 500))], "total": len(tasks)}

    return cast(Dict[str, Any], _cached_monitor_result(cache_key, _build_tasks))


def get_celery_task(task_id: str) -> Optional[Dict[str, Any]]:
    task_id = str(task_id or "").strip()
    if not task_id:
        return None
    for run in _load_backtest_runs():
        if task_id in {
            str(run.get("worker_task_id") or ""),
            str(run.get("run_id") or ""),
        }:
            return _task_from_backtest(run, AsyncResult(task_id, app=celery_app))
    result = AsyncResult(task_id, app=celery_app)
    if result.state == states.PENDING:
        return None
    return {
        "task_id": task_id,
        "task_name": None,
        "queue": None,
        "status": result.state,
        "normalized_status": normalized_task_status(result.state),
        "created_at": None,
        "started_at": None,
        "finished_at": None,
        "runtime_seconds": None,
        "progress_percent": _result_payload(result).get("progress_percent"),
        "current_step": _result_payload(result).get("current_step"),
        "strategy_id": _result_payload(result).get("strategy_id"),
        "backtest_run_id": _result_payload(result).get("backtest_run_id"),
        "bot_id": _result_payload(result).get("bot_id"),
        "environment": _result_payload(result).get("environment"),
        "selected_pairs": _result_payload(result).get("selected_pairs") or [],
        "error_code": _result_payload(result).get("error_code"),
        "error_message": _result_payload(result).get("error_message"),
        "traceback": result.traceback,
        "worker_hostname": _result_payload(result).get("worker_hostname"),
        "retry_count": _result_payload(result).get("retry_count"),
        "parent_task_id": _result_payload(result).get("parent_task_id"),
        "child_task_ids": _result_payload(result).get("child_task_ids") or [],
        "result": (
            redact_payload(result.result) if result.state == states.SUCCESS else None
        ),
        "metadata": _result_payload(result),
    }


def revoke_celery_task(task_id: str, terminate: bool = False) -> Dict[str, Any]:
    task_id = str(task_id or "").strip()
    if terminate:
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
    else:
        celery_app.control.revoke(task_id)
    _clear_monitor_cache()
    return {"task_id": task_id, "revoked": True, "terminate": bool(terminate)}


async def retry_celery_task(task_id: str) -> Dict[str, Any]:
    task = get_celery_task(task_id)
    if not task:
        raise ValueError("task not found")
    if task.get("task_name") != "backtests.run" or not task.get("backtest_run_id"):
        raise ValueError("task retry is not supported for this task")
    if str(task.get("status") or "").upper() not in {states.FAILURE, "TIMEOUT"}:
        raise ValueError("only failed backtest tasks can be retried")
    session = db.get_session()
    try:
        repository = BacktestRepository(session)
        data = repository.get_run(str(task["backtest_run_id"]))
        if not data:
            raise ValueError("backtest run not found")
        from src.infrastructure.use_cases.service_backtest import BacktestService

        service = BacktestService(repository)
        restarted = await service.restart_backtest(str(task["backtest_run_id"]))
        if not restarted:
            raise ValueError("backtest run is not retryable")
        _clear_monitor_cache()
        return {
            "task_id": task_id,
            "retried": True,
            "new_backtest_run_id": restarted.get("new_run_id"),
        }
    finally:
        session.close()


def list_celery_workers() -> Dict[str, Any]:
    def _build_workers() -> Dict[str, Any]:
        with ThreadPoolExecutor(max_workers=3) as executor:
            stats_future = executor.submit(_inspect_call, "stats", {})
            active_future = executor.submit(_inspect_call, "active", {})
            registered_future = executor.submit(_inspect_call, "registered", {})

            stats_payload = stats_future.result() or {}
            active_payload = active_future.result() or {}
            registered_payload = registered_future.result() or {}
        workers = []
        for worker, stats_value in stats_payload.items():
            active_tasks = active_payload.get(worker) or []
            workers.append(
                {
                    "hostname": worker,
                    "status": "online",
                    "queues": (
                        list((stats_value.get("pool") or {}).get("writes", {}).keys())
                        if isinstance(stats_value, dict)
                        else []
                    ),
                    "load": {"active_tasks": len(active_tasks)},
                    "registered_tasks": registered_payload.get(worker) or [],
                    "stats": redact_payload(stats_value),
                }
            )
        return {"workers": workers, "total": len(workers)}

    return cast(Dict[str, Any], _cached_monitor_result("workers", _build_workers))


def list_celery_queues() -> Dict[str, Any]:
    def _build_queues() -> Dict[str, Any]:
        queues = [
            queue.strip()
            for queue in os.getenv(
                "CELERY_QUEUES", ",".join(DEFAULT_CELERY_QUEUES)
            ).split(",")
            if queue.strip()
        ]
        payload = [{"name": queue, "length": None} for queue in queues]
        try:
            with celery_app.connection_or_acquire() as conn:
                channel = conn.default_channel
                client = getattr(channel, "client", None)
                if client is not None:
                    for item in payload:
                        item["length"] = int(client.llen(item["name"]))
        except Exception:
            pass
        return {"queues": payload, "total": len(payload)}

    return cast(Dict[str, Any], _cached_monitor_result("queues", _build_queues))


def celery_health() -> Dict[str, Any]:
    def _build_health() -> Dict[str, Any]:
        broker_ok = False
        backend_ok = False
        workers_ok = False
        errors: List[str] = []

        def _probe_broker() -> Optional[str]:
            nonlocal broker_ok
            try:
                with celery_app.connection_for_read() as conn:
                    conn.ensure_connection(max_retries=1)
                    broker_ok = True
                    return None
            except Exception as exc:
                return f"broker unavailable: {exc}"

        try:
            backend_ok = bool(celery_app.backend)
        except Exception as exc:
            errors.append(f"result backend unavailable: {exc}")

        def _probe_workers() -> Optional[str]:
            nonlocal workers_ok
            try:
                workers_ok = bool(_inspect_call("ping", {}))
                return None
            except Exception as exc:
                return f"workers unavailable: {exc}"

        with ThreadPoolExecutor(max_workers=2) as executor:
            broker_future = executor.submit(_probe_broker)
            workers_future = executor.submit(_probe_workers)
            broker_error = broker_future.result()
            worker_error = workers_future.result()

        if broker_error:
            errors.append(broker_error)
        if worker_error:
            errors.append(worker_error)

        return {
            "status": (
                "healthy" if broker_ok and backend_ok and workers_ok else "degraded"
            ),
            "broker": {"ok": broker_ok},
            "result_backend": {"ok": backend_ok},
            "workers": {"ok": workers_ok},
            "hostname": socket.gethostname(),
            "checked_at": utc_now_iso(),
            "errors": errors,
        }

    return cast(Dict[str, Any], _cached_monitor_result("health", _build_health))


def failure_meta(
    exc: BaseException,
    task_id: str,
    run_id: Optional[str] = None,
    *,
    error_code: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "task_name": "backtests.run",
        "status": states.FAILURE,
        "normalized_status": "failed",
        "backtest_run_id": run_id,
        "error_code": error_code,
        "error_message": str(exc) or exc.__class__.__name__,
        "traceback": traceback_module.format_exc(),
        "worker_hostname": socket.gethostname(),
        "finished_at": utc_now_iso(),
    }
