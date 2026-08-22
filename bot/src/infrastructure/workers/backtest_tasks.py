"""Celery tasks for durable backtest execution."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import traceback as traceback_module
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger as loguru_logger

from src.infrastructure.database import db
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.use_cases.backtest_history import _extract_retry_after_seconds
from src.infrastructure.use_cases.service_backtest import BacktestService
from src.infrastructure.workers.backtest_event_emitter import (
    emit_backtest_event_sync,
    publish_backtest_event,
)
from src.infrastructure.workers.celery_app import celery_app
from src.infrastructure.workers.celery_monitor import build_progress_meta, failure_meta
from src.shared.redis_env import (
    redis_db,
    redis_host,
    redis_password,
    redis_port,
    redis_ssl_enabled,
    redis_url,
)

logger = logging.getLogger(__name__)

_LOCK_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


def _normalize_request_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _merge_task_context_overrides(
    task_context: Dict[str, Any] | None,
    **overrides: Any,
) -> Dict[str, Any]:
    merged = dict(task_context or {})
    merged.update(overrides)
    return merged


def _build_runtime_task_context(
    service: BacktestService,
    request_payload: Dict[str, Any],
    task_context: Dict[str, Any] | None = None,
    *,
    worker_hostname: str | None = None,
    retry_count: int | None = None,
) -> Dict[str, Any]:
    """Merge persisted, queued, and live worker task context without duplicate kwargs."""
    merged = _merge_task_context_overrides(
        service._task_context_from_request(request_payload),
        **dict(task_context or {}),
    )
    merged = _merge_task_context_overrides(
        merged,
        worker_hostname=worker_hostname or socket.gethostname(),
        retry_count=retry_count,
    )
    return service._build_task_context(request_payload, **merged)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_redis_client():
    """Return a lazily-created synchronous redis client for pub/sub publishing."""
    import redis as _redis

    try:
        explicit_url = redis_url(prefer_celery_broker=True)
        if explicit_url:
            return _redis.from_url(explicit_url, decode_responses=True)

        return _redis.Redis(
            host=redis_host(),
            port=int(redis_port()),
            db=int(redis_db() or "0"),
            password=redis_password() or None,
            ssl=redis_ssl_enabled(),
            decode_responses=True,
        )
    except Exception as exc:
        logger.warning("backtest_pubsub_redis_init_failed error=%r", exc)
        return None


def _redis_lock_url() -> str | None:
    url = (
        os.getenv("BACKTEST_LOCK_REDIS_URL")
        or os.getenv("REDIS_URL")
        or os.getenv("VALKEY_URL")
    )
    broker_url = redis_url(prefer_celery_broker=True)
    if not url and broker_url:
        parsed = urlparse(broker_url)
        if parsed.scheme in {"redis", "rediss"}:
            url = broker_url
    if url:
        parsed = urlparse(url)
        if parsed.scheme in {"redis", "rediss"}:
            return url
    return None


def _get_lock_redis_client():
    import redis as _redis

    url = _redis_lock_url()
    if not url:
        return None
    return _redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
    )


def _lock_ttl_seconds() -> int:
    raw = os.getenv("BACKTEST_TASK_LOCK_TTL_SECONDS")
    if raw not in (None, ""):
        try:
            return max(60, int(raw))
        except (TypeError, ValueError):
            pass
    raw_limit = os.getenv("BACKTEST_CELERY_TASK_TIME_LIMIT")
    try:
        return max(60, int(raw_limit or str(7 * 24 * 60 * 60)) + 300)
    except (TypeError, ValueError):
        return 7 * 24 * 60 * 60 + 300


def _acquire_backtest_lock(run_id: str, token: str):
    try:
        client = _get_lock_redis_client()
    except Exception as exc:
        logger.warning(
            "backtest_lock_redis_init_failed run_id=%s error=%r", run_id, exc
        )
        return None
    if client is None:
        return None
    lock_key = f"backtest:run-lock:{run_id}"
    try:
        acquired = client.set(lock_key, token, nx=True, ex=_lock_ttl_seconds())
    except Exception:
        try:
            client.close()
        except Exception:
            pass
        raise
    if acquired:
        return client
    try:
        client.close()
    except Exception:
        pass
    raise RuntimeError(
        f"BACKTEST_ALREADY_RUNNING: backtest run '{run_id}' is already locked"
    )


def _release_backtest_lock(run_id: str, token: str, client: Any) -> None:
    if client is None:
        return
    try:
        client.eval(_LOCK_RELEASE_SCRIPT, 1, f"backtest:run-lock:{run_id}", token)
    except Exception as exc:
        logger.warning("backtest_lock_release_failed run_id=%s error=%r", run_id, exc)
    finally:
        try:
            client.close()
        except Exception:
            pass


def _max_retries() -> int:
    raw = os.getenv("BACKTEST_CELERY_MAX_RETRIES", "3")
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 3


def _retry_countdown_seconds(retries: int, exc: BaseException) -> float:
    retry_after: Optional[float] = _extract_retry_after_seconds(exc)
    if retry_after is not None:
        return retry_after
    raw_base = os.getenv("BACKTEST_CELERY_RETRY_BASE_SECONDS", "30")
    raw_max = os.getenv("BACKTEST_CELERY_RETRY_MAX_SECONDS", "600")
    try:
        base = max(1.0, float(raw_base))
    except (TypeError, ValueError):
        base = 30.0
    try:
        max_delay = max(base, float(raw_max))
    except (TypeError, ValueError):
        max_delay = 600.0
    return float(min(max_delay, base * (2 ** max(0, retries))))


def _is_transient_backtest_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, asyncio.CancelledError, ValueError)):
        return False
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = getattr(exc.response, "status_code", None)
        return status_code in {408, 425, 429, 500, 502, 503, 504}
    if isinstance(
        exc,
        (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
        ),
    ):
        return True
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "temporarily unavailable",
            "connection reset",
            "connection refused",
            "connection aborted",
            "timeout",
            "timed out",
            "too many requests",
            "rate limit",
            "502",
            "503",
            "504",
        )
    )


def _publish_backtest_status(
    run_id: str,
    status: str,
    progress: float = 0.0,
    current_pair: str = "",
    eta_seconds: float = 0.0,
) -> None:
    """Publish a backtest status event to Redis for downstream WebSocket push."""
    rc = _get_redis_client()
    if rc is None:
        return
    try:
        channel = f"backtest:{run_id}:status"
        payload = json.dumps(
            {
                "run_id": run_id,
                "status": status,
                "progress": progress,
                "current_pair": current_pair,
                "eta_seconds": eta_seconds,
                "timestamp": _now_iso(),
            }
        )
        rc.publish(channel, payload)
    except Exception as exc:
        logger.debug("backtest_pubsub_publish_failed run_id=%s error=%r", run_id, exc)
    finally:
        try:
            rc.close()
        except Exception:
            pass


def _mark_worker_failure(
    run_id: str,
    message: str,
    *,
    error_code: str | None = None,
    traceback_text: str | None = None,
    worker_hostname: str | None = None,
    retry_count: int | None = None,
) -> None:
    session = db.get_session()
    try:
        repository = BacktestRepository(session)
        run_data = repository.get_run_overview(run_id)
        if not isinstance(run_data, dict):
            return
        data: Dict[str, Any] = dict(run_data)
        request_payload: Dict[str, Any] = _normalize_request_payload(
            data.get("request")
        )
        data.update(
            {
                "status": "failed",
                "current_task": "failed",
                "error": message,
                "error_message": message,
                "finished_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        service = BacktestService(repository)
        task_context = _build_runtime_task_context(
            service,
            request_payload,
            worker_hostname=worker_hostname or socket.gethostname(),
            retry_count=retry_count,
        )
        data["request"] = service._set_task_failure(
            service._set_task_context(request_payload, task_context),
            {
                "error_code": error_code
                or service._error_code_from_message(
                    message, "BACKTEST_EXECUTION_FAILED"
                ),
                "error_message": message,
                "traceback": traceback_text,
            },
        )
        service._set_runtime_control(
            data,
            status="failed",
            action="fail",
            pause_requested=False,
            resume_requested=False,
            cancel_requested=False,
            worker_backend="celery",
            worker_task_id=run_id,
        )
        repository.update_run_progress(data)
    finally:
        session.close()


def _selected_pairs(data: Dict[str, Any]) -> list[str]:
    request: Dict[str, Any] = _normalize_request_payload(data.get("request"))
    raw = (
        data.get("selected_pairs")
        or request.get("selected_pairs")
        or request.get("pairs")
        or []
    )
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return []


@celery_app.task(
    name="backtests.run",
    bind=True,
    autoretry_for=(),
)
def run_backtest_task(
    self: Any,
    run_id: str,
    task_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run a persisted backtest by id inside a Celery worker process."""
    task_id = str(self.request.id or run_id)
    lock_client = None
    # Setup job-specific logging to bot_states/backtest_<run_id>.log
    log_file = os.path.join("bot_states", f"backtest_{run_id}.log")
    os.makedirs("bot_states", exist_ok=True)

    # Add a sink that only captures logs for this specific run_id
    handler_id = loguru_logger.add(
        log_file,
        filter=lambda record: record["extra"].get("run_id") == run_id,
        level=os.getenv("LOG_LEVEL", "INFO"),
        enqueue=True,
    )

    session = db.get_session()
    try:
        with loguru_logger.contextualize(run_id=run_id):
            try:
                lock_client = _acquire_backtest_lock(run_id, task_id)
            except RuntimeError as exc:
                loguru_logger.warning(
                    "Backtest task {} skipped for run {}: {}",
                    task_id,
                    run_id,
                    exc,
                )
                self.update_state(
                    state="SUCCESS",
                    meta={
                        "task_id": task_id,
                        "task_name": "backtests.run",
                        "status": "duplicate_skipped",
                        "backtest_run_id": run_id,
                        "error_message": str(exc),
                        "worker_hostname": socket.gethostname(),
                    },
                )
                return {
                    "run_id": run_id,
                    "status": "duplicate_skipped",
                    "reason": str(exc),
                }

            repository = BacktestRepository(session)
            run_data = repository.get_run(run_id)
            if not isinstance(run_data, dict):
                raise ValueError(f"Backtest run '{run_id}' not found")
            data: Dict[str, Any] = dict(run_data)

            service = BacktestService(repository)
            # ... rest of the setup code until update_state
            request_payload: Dict[str, Any] = _normalize_request_payload(
                data.get("request")
            )
            task_context = _build_runtime_task_context(
                service,
                request_payload,
                task_context,
                worker_hostname=socket.gethostname(),
                retry_count=int(getattr(self.request, "retries", 0) or 0),
            )
            request_payload = service._clear_task_failure(
                service._set_task_context(request_payload, task_context)
            )
            data["request"] = request_payload
            selected_pairs = _selected_pairs(data)
            strategy_snapshot = (
                request_payload.get("strategy_payload_snapshot")
                if isinstance(request_payload.get("strategy_payload_snapshot"), dict)
                else None
            )
            strategy_id = task_context.get("strategy_id") or request_payload.get(
                "strategy_id"
            )
            if strategy_snapshot and strategy_id is None:
                raise ValueError(
                    "STRATEGY_ID_MISSING: strategy-linked backtest requires strategy_id"
                )
            if strategy_id is not None and not strategy_snapshot:
                raise ValueError(
                    "STRATEGY_PAYLOAD_MISSING: strategy-linked backtest requires strategy_payload_snapshot"
                )
            if not selected_pairs:
                raise ValueError(
                    "SELECTED_PAIRS_MISSING: explicit selected_pairs are required"
                )
            self.update_state(
                state="STARTED",
                meta={
                    "task_id": task_id,
                    "task_name": "backtests.run",
                    "queue": (getattr(self.request, "delivery_info", None) or {}).get(
                        "routing_key", "backtests"
                    ),
                    "status": "STARTED",
                    "started_at": _now_iso(),
                    "worker_hostname": socket.gethostname(),
                    "backtest_run_id": run_id,
                    "strategy_id": strategy_id,
                    "bot_id": task_context.get("bot_id")
                    or request_payload.get("bot_id"),
                    "environment": task_context.get("environment")
                    or request_payload.get("environment")
                    or os.getenv("ENVIRONMENT")
                    or os.getenv("APP_ENV")
                    or "local",
                    "selected_pairs": selected_pairs,
                    "retry_count": int(getattr(self.request, "retries", 0) or 0),
                    "source": task_context.get("source"),
                    "metadata": task_context.get("metadata") or {},
                },
            )
            loguru_logger.info(
                "celery_backtest_task_started task_id={} run_id={} retry_count={}",
                task_id,
                run_id,
                int(getattr(self.request, "retries", 0) or 0),
            )
            data["worker_backend"] = "celery"
            data["worker_task_id"] = task_id
            service._set_runtime_control(
                data,
                status="started",
                action="start",
                pause_requested=False,
                resume_requested=False,
                cancel_requested=False,
                worker_backend="celery",
                worker_task_id=task_id,
                started_at=_now_iso(),
            )
            repository.save_run(data)
            _publish_backtest_status(run_id, "started")
            emit_backtest_event_sync(run_id=run_id, status="started")

            async def _progress_callback(
                callback_run_id: str, progress: float, current_pair: str, eta: float
            ) -> None:
                completed_pairs = None
                total_pairs = len(selected_pairs) if selected_pairs else None
                if total_pairs:
                    completed_pairs = min(
                        total_pairs, int((float(progress) / 100.0) * total_pairs)
                    )
                self.update_state(
                    state="PROGRESS",
                    meta=build_progress_meta(
                        run_id=callback_run_id,
                        progress_percent=progress,
                        current_pair=current_pair,
                        current_step=(
                            "processing pair"
                            if current_pair != "complete"
                            else "complete"
                        ),
                        total_pairs=total_pairs,
                        completed_pairs=completed_pairs,
                        current_phase="backtest",
                        eta_seconds=eta,
                        strategy_id=strategy_id,
                        bot_id=task_context.get("bot_id")
                        or request_payload.get("bot_id"),
                        environment=task_context.get("environment")
                        or request_payload.get("environment")
                        or os.getenv("ENVIRONMENT")
                        or os.getenv("APP_ENV")
                        or "local",
                        selected_pairs=selected_pairs,
                    ),
                )
                _publish_backtest_status(
                    callback_run_id, "progress", progress, current_pair, eta
                )
                await publish_backtest_event(
                    run_id=callback_run_id,
                    status="progress",
                    progress=progress,
                    current_pair=current_pair,
                )

            asyncio.run(
                service.execute_existing_backtest(
                    run_id,
                    _progress_callback,
                    propagate_exceptions=True,
                )
            )
            _publish_backtest_status(run_id, "completed", 100.0, "complete")
            emit_backtest_event_sync(run_id=run_id, status="completed", progress=100.0)
            loguru_logger.info(
                "celery_backtest_task_completed task_id={} run_id={}",
                task_id,
                run_id,
            )
            return {"run_id": run_id, "status": "completed"}
    except SoftTimeLimitExceeded:
        message = "Backtest Celery task exceeded soft time limit"
        loguru_logger.warning(
            "celery_backtest_task_failed task_id={} run_id={} reason=soft_time_limit",
            task_id,
            run_id,
        )
        _mark_worker_failure(
            run_id,
            message,
            error_code="BACKTEST_TIMEOUT",
            traceback_text=traceback_module.format_exc(),
            worker_hostname=socket.gethostname(),
            retry_count=int(getattr(self.request, "retries", 0) or 0),
        )
        _publish_backtest_status(run_id, "failed")
        emit_backtest_event_sync(
            run_id=run_id,
            status="failed",
            error_code="BACKTEST_TIMEOUT",
            error_message=message,
        )
        raise
    except asyncio.CancelledError:
        message = "Backtest Celery task cancelled"
        loguru_logger.warning(
            "celery_backtest_task_cancelled task_id={} run_id={}", task_id, run_id
        )
        _mark_worker_failure(
            run_id,
            message,
            error_code="BACKTEST_CANCELLED",
            traceback_text=traceback_module.format_exc(),
            worker_hostname=socket.gethostname(),
            retry_count=int(getattr(self.request, "retries", 0) or 0),
        )
        self.update_state(
            state="REVOKED",
            meta=failure_meta(
                RuntimeError(message),
                str(self.request.id or run_id),
                run_id,
                error_code="BACKTEST_CANCELLED",
            ),
        )
        _publish_backtest_status(run_id, "cancelled")
        emit_backtest_event_sync(
            run_id=run_id,
            status="cancelled",
            error_code="BACKTEST_CANCELLED",
            error_message=message,
        )
        raise
    except Exception as exc:
        retries = int(getattr(self.request, "retries", 0) or 0)
        if _is_transient_backtest_error(exc) and retries < _max_retries():
            countdown = _retry_countdown_seconds(retries, exc)
            try:
                retry_session = db.get_session()
                try:
                    retry_service = BacktestService(BacktestRepository(retry_session))
                    retry_service.mark_backtest_retrying(
                        run_id,
                        error=exc,
                        countdown_seconds=countdown,
                        retry_count=retries + 1,
                        task_id=task_id,
                    )
                finally:
                    retry_session.close()
            except Exception as retry_mark_exc:
                logger.warning(
                    "backtest_retry_status_persist_failed run_id=%s error=%r",
                    run_id,
                    retry_mark_exc,
                )
            self.update_state(
                state="RETRY",
                meta={
                    "task_id": task_id,
                    "task_name": "backtests.run",
                    "status": "RETRY",
                    "backtest_run_id": run_id,
                    "error_code": BacktestService._error_code_from_message(
                        str(exc), "BACKTEST_TRANSIENT_RETRY"
                    ),
                    "error_message": str(exc) or exc.__class__.__name__,
                    "retry_count": retries + 1,
                    "retry_after_seconds": round(float(countdown), 3),
                    "worker_hostname": socket.gethostname(),
                },
            )
            _publish_backtest_status(run_id, "retrying")
            loguru_logger.warning(
                "celery_backtest_task_retrying task_id={} run_id={} retry_count={} countdown_seconds={} error={}",
                task_id,
                run_id,
                retries + 1,
                round(float(countdown), 3),
                str(exc) or exc.__class__.__name__,
            )
            raise self.retry(exc=exc, countdown=countdown, max_retries=_max_retries())

        loguru_logger.exception("celery_backtest_task_failed run_id={}", run_id)
        _mark_worker_failure(
            run_id,
            str(exc) or "Backtest Celery task failed",
            error_code=BacktestService._error_code_from_message(
                str(exc), "BACKTEST_EXECUTION_FAILED"
            ),
            traceback_text=traceback_module.format_exc(),
            worker_hostname=socket.gethostname(),
            retry_count=int(getattr(self.request, "retries", 0) or 0),
        )
        _publish_backtest_status(run_id, "failed")
        emit_backtest_event_sync(
            run_id=run_id,
            status="failed",
            error_code=BacktestService._error_code_from_message(
                str(exc), "BACKTEST_EXECUTION_FAILED"
            ),
            error_message=str(exc) or "Backtest Celery task failed",
        )
        raise
    finally:
        _release_backtest_lock(run_id, task_id, lock_client)
        session.close()
        loguru_logger.remove(handler_id)
