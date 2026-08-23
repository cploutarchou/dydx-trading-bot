"""Runtime control / mutation methods for backtests (Phase 5a).

Extracted from :mod:`src.infrastructure.use_cases.service_backtest` (Phase 5a of the
backtest-service decomposition). The seven public control methods the API router
calls as ``service.pause/resume/restart/cancel/delete/retry/repair``. Exposed as a
**mixin** mixed into :class:`BacktestService` so the public API is unchanged.

The mixin relies on attributes/methods provided by ``BacktestService`` at runtime:
``_load_run_data`` / ``_resolve_stale_run_data`` / ``_persist_run_data`` /
``_TERMINAL_STATUSES`` / ``_set_runtime_control`` / ``_get_runtime_control`` /
``_strip_runtime_control`` / ``_reconstruct_restart_request_payload`` /
``_configured_worker_backend`` / ``_tasks`` / ``_runs`` / ``_revoke_celery_backtest`` /
``create_and_run_backtest``. The private control-codec helpers themselves stay on
``BacktestService`` (they are the shared "nervous system" with ~50 call sites across
orchestration/persistence — highest coupling, deferred).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Set

from src.infrastructure.use_cases.async_job_manager import async_job_manager


class BacktestControlMixin:
    """Runtime control methods; mixed into :class:`BacktestService`."""

    if TYPE_CHECKING:
        # Host contract — provided by BacktestService at runtime (see module
        # docstring). Declared type-only so mypy checks this mixin's usage without
        # duplicating the implementations; the real definitions live on (and are
        # checked on) the host.
        _runs: Dict[str, Dict[str, Any]]
        _tasks: Dict[str, asyncio.Task[None]]
        _TERMINAL_STATUSES: Set[str]
        repository: Any
        _load_run_data: Callable[..., Optional[Dict[str, Any]]]
        _resolve_stale_run_data: Callable[..., Dict[str, Any]]
        _persist_run_data: Callable[..., Dict[str, Any]]
        _set_runtime_control: Callable[..., Dict[str, Any]]
        _get_runtime_control: Callable[..., Dict[str, Any]]
        _strip_runtime_control: Callable[..., Dict[str, Any]]
        _reconstruct_restart_request_payload: Callable[..., Dict[str, Any]]
        _revoke_celery_backtest: Callable[[Optional[str]], None]
        _configured_worker_backend: Callable[..., str]
        create_and_run_backtest: Callable[..., Any]

    def pause_backtest(self, run_id: str) -> Optional[Dict[str, Any]]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        data = self._resolve_stale_run_data(data)
        status = str(data.get("status") or "").lower()
        if status in self._TERMINAL_STATUSES:
            return None
        now = datetime.now(timezone.utc).isoformat()
        data = self._set_runtime_control(
            data,
            status="pause_requested",
            action="pause",
            pause_requested=True,
            resume_requested=False,
            cancel_requested=False,
            requested_at=now,
            worker_backend=data.get("worker_backend") or "asyncio",
            worker_task_id=data.get("worker_task_id") or run_id,
        )
        data["current_task"] = "pause requested"
        data["updated_at"] = now
        return self._resolve_stale_run_data(self._persist_run_data(data))

    def resume_backtest(self, run_id: str) -> Optional[Dict[str, Any]]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        data = self._resolve_stale_run_data(data)
        status = str(data.get("status") or "").lower()
        if status in self._TERMINAL_STATUSES:
            return None
        control = self._get_runtime_control(data)
        if status != "paused" and not control.get("pause_requested"):
            return None
        now = datetime.now(timezone.utc).isoformat()
        data = self._set_runtime_control(
            data,
            status="resume_requested",
            action="resume",
            pause_requested=False,
            resume_requested=True,
            cancel_requested=False,
            requested_at=now,
            worker_backend=data.get("worker_backend") or "asyncio",
            worker_task_id=data.get("worker_task_id") or run_id,
        )
        data["current_task"] = "resume requested"
        data["updated_at"] = now
        return self._resolve_stale_run_data(self._persist_run_data(data))

    async def restart_backtest(
        self,
        run_id: str,
        progress_callback: Any = None,
    ) -> Optional[Dict[str, Any]]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        request_payload = self._reconstruct_restart_request_payload(data)
        if not request_payload:
            return None
        status = str(data.get("status") or "").lower()
        if status not in self._TERMINAL_STATUSES:
            self.cancel_backtest(run_id)
            await asyncio.sleep(0)

        created = await self.create_and_run_backtest(request_payload, progress_callback)
        return {
            "run_id": run_id,
            "new_run_id": created.run_id,
            "status": "restarted",
            "new_status": created.status,
            "worker_backend": created.worker_backend
            or self._configured_worker_backend(),
        }

    def repair_backtest_request(
        self,
        run_id: str,
        dry_run: bool = True,
    ) -> Optional[Dict[str, Any]]:
        data = self._load_run_data(run_id)
        if not data:
            return None

        existing_request = self._strip_runtime_control(data.get("request") or {})
        reconstructed_request = self._reconstruct_restart_request_payload(data)
        repairable = bool(reconstructed_request)
        request_available = bool(existing_request)

        if not repairable:
            return {
                "run_id": run_id,
                "dry_run": bool(dry_run),
                "repaired": False,
                "request_available": request_available,
                "repairable": False,
                "status": str(data.get("status") or "unknown"),
                "error": "insufficient_fields_to_reconstruct_request",
            }

        if dry_run or request_available:
            return {
                "run_id": run_id,
                "dry_run": bool(dry_run),
                "repaired": False,
                "request_available": request_available,
                "repairable": True,
                "status": str(data.get("status") or "unknown"),
                "selected_pairs": list(
                    reconstructed_request.get("selected_pairs") or []
                ),
                "pairs": list(reconstructed_request.get("pairs") or []),
            }

        updated = dict(data)
        updated["request"] = reconstructed_request
        updated["updated_at"] = datetime.now(timezone.utc).isoformat()
        persisted = self._persist_run_data(updated)

        return {
            "run_id": run_id,
            "dry_run": False,
            "repaired": True,
            "request_available": True,
            "repairable": True,
            "status": str(persisted.get("status") or data.get("status") or "unknown"),
            "selected_pairs": list(reconstructed_request.get("selected_pairs") or []),
            "pairs": list(reconstructed_request.get("pairs") or []),
        }

    async def retry_backtest(
        self,
        run_id: str,
        progress_callback: Any = None,
    ) -> Optional[Dict[str, Any]]:
        return await self.restart_backtest(run_id, progress_callback)

    def cancel_backtest(self, run_id: str) -> bool:
        data = self._load_run_data(run_id)
        if not data:
            return False
        now = datetime.now(timezone.utc).isoformat()
        data = self._set_runtime_control(
            data,
            status="cancel_requested",
            action="cancel",
            pause_requested=False,
            resume_requested=False,
            cancel_requested=True,
            requested_at=now,
            worker_backend=data.get("worker_backend") or "asyncio",
            worker_task_id=data.get("worker_task_id") or run_id,
        )
        data["cancel_requested"] = True
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
        if str(data.get("worker_backend") or "").lower() == "celery":
            self._revoke_celery_backtest(data.get("worker_task_id"))
        data["status"] = "cancelled"
        data["current_task"] = "cancelled"
        data["error"] = data.get("error") or "Backtest cancelled"
        data["error_message"] = data.get("error_message") or "Backtest cancelled"
        data["finished_at"] = data.get("finished_at") or now
        data["completed_at"] = data.get("completed_at") or data["finished_at"]
        data["updated_at"] = now
        self._persist_run_data(data)
        async_job_manager.mark_cancelled(run_id, reason="Backtest cancelled")
        return True

    def delete_backtest(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
        self._runs.pop(run_id, None)
        deleted: bool = self.repository.delete_run(run_id)
        return deleted
