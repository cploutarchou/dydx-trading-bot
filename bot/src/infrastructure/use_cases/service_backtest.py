"""Backtest service for handling backtest operations."""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import math
import os
import threading
import time
import traceback as traceback_module
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast
from uuid import uuid4

import numpy as np

from src.infrastructure.database import db
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.use_cases.async_job_manager import async_job_manager
from src.trading.dydx_client import connect_dydx

logger = logging.getLogger(__name__)

_BACKEND_PROBE_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="backtest-celery-probe",
)


# Canonical definition lives in :mod:`src.exceptions` (under ``BacktestError``);
# re-imported here so existing ``from ...service_backtest import BacktestEnqueueError``
# paths keep resolving to the same class.
from src.exceptions import BacktestEnqueueError  # noqa: E402

# Pair-prioritization / scoring engine (Phase 2). The implementation lives in
# :mod:`src.infrastructure.use_cases.backtest_pair_selection`; the thin delegating
# methods below preserve the existing ``cls.``/``self.`` call sites unchanged.
from src.infrastructure.use_cases import (  # noqa: E402
    backtest_checkpoint as _checkpoint,
)
from src.infrastructure.use_cases import backtest_history as _history
from src.infrastructure.use_cases import backtest_pair_selection as _pair_selection

# Runtime control / mutation methods (Phase 5a). Same mixin pattern as Phase 4.
from src.infrastructure.use_cases.backtest_controls import (  # noqa: E402
    BacktestControlMixin,
)

# Backtest response/serialization DTOs live in a focused module
# (:mod:`src.infrastructure.use_cases.backtest_models`); re-imported here so existing
# bare-name references (e.g. ``_BacktestRunDetails(**run_data)``) resolve to the same
# class objects. Part of the backtest-service decomposition (Phase 1).
from src.infrastructure.use_cases.backtest_models import (  # noqa: E402
    _BacktestRunDetails,
    _BacktestRunList,
)

# Read-side / reporting query methods (Phase 4). Mixed in so the public
# ``service.get_X(...)`` API is unchanged; implementations live in that module.
from src.infrastructure.use_cases.backtest_queries import (  # noqa: E402
    BacktestQueryMixin,
)


class BacktestService(BacktestQueryMixin, BacktestControlMixin):
    """Service for backtest operations."""

    _runs: Dict[str, Dict[str, Any]] = {}
    _tasks: Dict[str, asyncio.Task[None]] = {}
    _TASK_CONTEXT_KEY = "_task_context"
    _TASK_FAILURE_KEY = "_task_failure"
    _DEFAULT_TIMEOUT_SECONDS = 24 * 60 * 60
    _MIN_TIMEOUT_SECONDS = 1.0
    _MAX_TIMEOUT_SECONDS = 7 * 24 * 60 * 60
    _PROGRESS_CALLBACK_TIMEOUT_SECONDS = 5.0
    _SIMULATION_YIELD_EVERY_STEPS = 200
    _HEAVY_PROGRESS_PERSIST_EVERY_PAIRS = 10
    _HEAVY_PROGRESS_PERSIST_EVERY_SECONDS = 15.0
    _HEARTBEAT_KEEPALIVE_SECONDS = 30.0
    _STALE_BACKTEST_HEARTBEAT_SECONDS = 120.0
    _TERMINAL_STATUSES = {
        "completed",
        "failed",
        "timeout",
        "timed_out",
        "cancelled",
        "stale",
        "stalled",
    }
    _ACTIVE_STATUSES = {"pending", "running", "paused", "retrying"}
    _CONTROL_KEY = "_runtime_control"
    _BASELINE_METRICS: Dict[str, float] = {
        "total_pnl": 48.2,
        "win_rate": 0.59,
        "sharpe_ratio": 1.33,
        "max_drawdown_pct": 10.9,
        "total_trades": 24,
    }
    _INTERRUPTION_ERROR = "Backtest interrupted by API reload or restart"
    _BACKEND_REPROBE_COOLDOWN_SECONDS = 15.0
    _backend_reprobe_lock = threading.Lock()
    _backend_reprobe_last_monotonic = 0.0
    _backend_reprobe_last_available = False

    def __init__(self, session: Any):
        self.repository = (
            session
            if isinstance(session, BacktestRepository)
            else BacktestRepository(session)
        )
        self.session = getattr(self.repository, "session", session)
        # Reconciliation is explicit via API ops endpoints to avoid false-positive
        # failures when requests are served by different API worker processes.

    @staticmethod
    def _to_ops_row(run: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "run_id": str(run.get("run_id") or ""),
            "name": str(run.get("name") or ""),
            "status": str(run.get("status") or ""),
            "progress_pct": float(run.get("progress_pct", 0.0) or 0.0),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "error": run.get("error"),
            "error_message": run.get("error_message"),
        }

    @classmethod
    def _canonical_status(cls, status: Any) -> str:
        normalized = str(status or "").strip().lower()
        aliases = {
            "": "pending",
            "created": "pending",
            "queued": "pending",
            "scheduled": "pending",
            "in_progress": "running",
            "processing": "running",
            "active": "running",
            "started": "running",
            "retry": "retrying",
            "succeeded": "completed",
            "success": "completed",
            "done": "completed",
            "error": "failed",
            "timed_out": "timeout",
            "stalled": "stale",
            "canceled": "cancelled",
        }
        return aliases.get(normalized, normalized)

    @classmethod
    def _normalize_lifecycle_state(cls, run_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(run_data)
        status = cls._canonical_status(payload.get("status"))
        progress = cls._safe_float(payload.get("progress_pct"), 0.0)
        current_pair = str(payload.get("current_pair") or "").strip().lower()
        current_task = str(payload.get("current_task") or "").strip().lower()
        has_error = bool(
            str(payload.get("error") or payload.get("error_message") or "").strip()
        )
        has_cancel = (
            bool(payload.get("cancel_requested")) or current_task == "cancelled"
        )
        has_metrics = (
            any(
                cls._safe_float(payload.get(key), 0.0) != 0.0
                for key in ("total_pnl", "win_rate", "sharpe_ratio", "profit_factor")
            )
            or cls._safe_float(payload.get("total_trades"), 0.0) > 0.0
        )
        has_work_marker = (
            bool(payload.get("started_at"))
            or progress > 0.0
            or (
                current_pair
                and current_pair
                not in {"pending", "queued", "complete", "none", "null"}
            )
            or (
                current_task
                and current_task not in {"pending", "queued", "complete", "created"}
            )
        )

        if status == "pending":
            if has_cancel:
                status = "cancelled"
            elif has_error:
                status = "failed"
            elif (
                progress >= 100.0
                or current_pair == "complete"
                or current_task == "complete"
            ):
                status = "completed"
            elif has_work_marker or has_metrics:
                status = "running"

        payload["status"] = status
        return payload

    def _find_orphaned_in_progress_runs(
        self, runs: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        source = (
            runs
            if runs is not None
            else self.repository.list_runs(limit=None, offset=0)
        )
        candidates: List[Dict[str, Any]] = []
        for run in source:
            run_id = str(run.get("run_id") or "").strip()
            if not run_id:
                continue
            status = str(run.get("status") or "").strip().lower()
            if (
                self._canonical_status(status) in {"pending", "running"}
                and run_id not in self._tasks
            ):
                candidates.append(dict(run))
        return candidates

    def _build_interrupted_run_payload(self, run: Dict[str, Any]) -> Dict[str, Any]:
        interrupted = dict(run)
        interrupted.update(
            {
                "status": "failed",
                "current_task": "failed",
                "error": self._INTERRUPTION_ERROR,
                "error_message": self._INTERRUPTION_ERROR,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return interrupted

    def list_interrupted_runs_for_ops(self, limit: int = 50) -> Dict[str, Any]:
        runs = self.repository.list_runs(limit=None, offset=0)
        orphaned = self._find_orphaned_in_progress_runs(runs)
        reconciled = [
            dict(run)
            for run in runs
            if str(run.get("status") or "").strip().lower() == "failed"
            and str(run.get("error") or "").strip() == self._INTERRUPTION_ERROR
        ]

        safe_limit = max(1, int(limit or 50))
        return {
            "interruption_error": self._INTERRUPTION_ERROR,
            "orphaned_in_progress": [
                self._to_ops_row(run) for run in orphaned[:safe_limit]
            ],
            "interrupted_runs": [
                self._to_ops_row(run) for run in reconciled[:safe_limit]
            ],
            "orphaned_count": len(orphaned),
            "interrupted_count": len(reconciled),
        }

    def reconcile_interrupted_runs(self, dry_run: bool = True) -> Dict[str, Any]:
        runs = self.repository.list_runs(limit=None, offset=0)
        for run in runs:
            run_id = str(run.get("run_id") or "").strip()
            if run_id:
                self._runs[run_id] = dict(run)

        candidates = self._find_orphaned_in_progress_runs(runs)
        reconciled: List[Dict[str, Any]] = []
        if not dry_run:
            for run in candidates:
                persisted = self.repository.save_run(
                    self._build_interrupted_run_payload(run)
                )
                run_id = str(persisted.get("run_id") or "").strip()
                if run_id:
                    self._runs[run_id] = dict(persisted)
                reconciled.append(dict(persisted))

        return {
            "interruption_error": self._INTERRUPTION_ERROR,
            "dry_run": bool(dry_run),
            "candidates": [self._to_ops_row(run) for run in candidates],
            "reconciled": [self._to_ops_row(run) for run in reconciled],
            "candidate_count": len(candidates),
            "reconciled_count": len(reconciled),
        }

    def _load_run_data(self, run_id: str) -> Optional[Dict[str, Any]]:
        cached = self._runs.get(run_id)
        if self.session is None and cached is not None and "request" in cached:
            return dict(cached)

        persisted = self.repository.get_run(run_id)
        if persisted is not None:
            hydrated = self._hydrate_loaded_run(dict(persisted))
            self._runs[run_id] = dict(hydrated)
            return dict(hydrated)

        return dict(cached) if cached is not None else None

    def _load_run_overview(self, run_id: str) -> Optional[Dict[str, Any]]:
        cached = self._runs.get(run_id)
        if self.session is None and cached is not None and "request" in cached:
            return dict(cached)

        persisted = self.repository.get_run_overview(run_id)
        if persisted is not None:
            hydrated = self._hydrate_loaded_run(dict(persisted))
            self._runs[run_id] = dict(hydrated)
            return dict(hydrated)

        return dict(cached) if cached is not None else None

    def _persist_run_data(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        existing = None
        run_id = str(run_data.get("run_id") or "").strip()
        if run_id:
            try:
                existing = self.repository.get_run(run_id)
            except Exception:
                existing = None
        if existing:
            run_data = self._merge_runtime_control(run_data, existing)

        persisted = self.repository.save_run(run_data)
        for key in (
            "started_at",
            "finished_at",
            "deadline_at",
            "timeout_seconds",
            "control_status",
            "control_action",
            "worker_backend",
            "worker_task_id",
        ):
            if key in run_data and key not in persisted:
                persisted[key] = run_data[key]
        persisted["analytics_rows_written"] = self._normalize_analytics_rows_written(
            persisted.get("analytics_rows_written")
        )
        self._runs[str(persisted["run_id"])] = dict(persisted)
        return dict(persisted)

    @staticmethod
    def _normalize_analytics_rows_written(value: Any) -> int:
        if isinstance(value, dict):
            total = 0
            for item in value.values():
                try:
                    total += max(0, int(item or 0))
                except (TypeError, ValueError):
                    continue
            return total
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def _persist_progress_data(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist scalar progress without rewriting accumulated result JSON blobs."""
        run_id = str(run_data.get("run_id") or "").strip()
        if not run_id or not self.repository.update_run_progress(run_data):
            raise RuntimeError(
                f"Backtest run '{run_id}' is unavailable for progress update"
            )
        cached = dict(self._runs.get(run_id) or {})
        cached.update(run_data)
        self._runs[run_id] = cached
        return dict(run_data)

    @classmethod
    def _hydrate_loaded_run(cls, run_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(run_data)
        payload = cls._apply_task_observability(payload)
        control = cls._get_runtime_control(payload)
        payload["control_status"] = control.get("status")
        payload["control_action"] = control.get("action")
        payload["worker_backend"] = control.get("worker_backend")
        payload["worker_task_id"] = control.get("worker_task_id")
        payload["last_heartbeat_at"] = payload.get("updated_at")
        payload["heartbeat_age_seconds"] = cls._heartbeat_age_seconds(payload)
        return payload

    def _update_run_data(self, run_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
        run_data = self._load_run_data(run_id)
        if run_data is None:
            return None
        run_data.update(updates)
        if "updated_at" not in updates:
            run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self._persist_run_data(run_data)

    @classmethod
    def _get_runtime_control(cls, run_data: Dict[str, Any]) -> Dict[str, Any]:
        request = run_data.get("request")
        if not isinstance(request, dict):
            return {}
        control = request.get(cls._CONTROL_KEY)
        return dict(control) if isinstance(control, dict) else {}

    @classmethod
    def _set_runtime_control(
        cls,
        run_data: Dict[str, Any],
        **updates: Any,
    ) -> Dict[str, Any]:
        request = dict(run_data.get("request") or {})
        control = cls._get_runtime_control({"request": request})
        control.update(updates)
        request[cls._CONTROL_KEY] = control
        run_data["request"] = request
        run_data["control_status"] = control.get("status")
        run_data["control_action"] = control.get("action")
        run_data["worker_backend"] = control.get("worker_backend")
        run_data["worker_task_id"] = control.get("worker_task_id")
        return run_data

    @classmethod
    def _strip_runtime_control(cls, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(request_payload or {})
        cleaned.pop(cls._CONTROL_KEY, None)
        return cleaned

    @classmethod
    def _reconstruct_restart_request_payload(
        cls,
        run_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        existing_request = cls._strip_runtime_control(run_data.get("request") or {})
        if existing_request:
            return existing_request

        selected_pairs = cls._normalize_string_list(run_data.get("selected_pairs"))
        current_pair = str(run_data.get("current_pair") or "").strip().upper()
        if not selected_pairs and "/" in current_pair:
            selected_pairs = [current_pair]

        markets = cls._markets_from_pair_labels(selected_pairs)
        if len(markets) >= 2:
            pairs = markets
        else:
            pairs = selected_pairs[:]

        trading_parameters = {
            "resolution": "1HOUR",
            "zscore_threshold": 1.5,
            "stats_window": 21,
            "close_at_zscore_cross": True,
            "transaction_fee": 0.0,
            "slippage": 0.0,
        }

        reconstructed: Dict[str, Any] = {
            "name": run_data.get("name") or "restarted-backtest",
            "description": run_data.get("description") or "",
            "start_date": str(run_data.get("start_date") or ""),
            "end_date": str(run_data.get("end_date") or ""),
            "initial_balance": cls._safe_float(
                run_data.get("initial_balance"), 10000.0
            ),
            "pair_selection_mode": (
                "input"
                if selected_pairs
                else cls._normalize_pair_selection_mode(
                    run_data.get("pair_selection_mode")
                )
            ),
            "max_pairs": 0,
            "trading_parameters": trading_parameters,
            "pairs": pairs,
            "selected_pairs": selected_pairs,
            "strategy_id": run_data.get("strategy_id"),
            "bot_id": run_data.get("bot_id"),
            "source": run_data.get("source") or "api",
            "metadata": dict(run_data.get("metadata") or {}),
            "timeout_seconds": run_data.get("timeout_seconds"),
        }

        strategy_snapshot = run_data.get("strategy_payload_snapshot")
        if isinstance(strategy_snapshot, dict):
            reconstructed["strategy_payload_snapshot"] = dict(strategy_snapshot)

        return {key: value for key, value in reconstructed.items() if value is not None}

    @staticmethod
    def _normalize_string_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        items: List[str] = []
        seen: set[str] = set()
        for raw in value:
            cleaned = str(raw).strip().upper()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            items.append(cleaned)
        return items

    @classmethod
    def _build_pair_labels_from_markets(cls, markets: List[str]) -> List[str]:
        labels: List[str] = []
        for idx in range(len(markets) - 1):
            for jdx in range(idx + 1, len(markets)):
                labels.append(f"{markets[idx]}/{markets[jdx]}")
        return labels

    @classmethod
    def _markets_from_pair_labels(cls, pair_labels: List[str]) -> List[str]:
        markets: List[str] = []
        seen: set[str] = set()
        for label in pair_labels:
            for part in str(label).split("/"):
                market = str(part).strip().upper()
                if not market or market in seen:
                    continue
                seen.add(market)
                markets.append(market)
        return markets

    @classmethod
    def _markets_from_request(cls, request_payload: Dict[str, Any]) -> List[str]:
        markets = cls._normalize_string_list(request_payload.get("pairs"))
        if markets:
            return markets

        selected_pairs = cls._normalize_string_list(
            request_payload.get("selected_pairs")
        )
        if selected_pairs and all("/" in pair for pair in selected_pairs):
            return cls._markets_from_pair_labels(selected_pairs)
        return selected_pairs

    @classmethod
    def _selected_pair_labels_from_request(
        cls, request_payload: Dict[str, Any]
    ) -> List[str]:
        selected_pairs = cls._normalize_string_list(
            request_payload.get("selected_pairs")
        )
        if selected_pairs and all("/" in pair for pair in selected_pairs):
            return selected_pairs

        markets = cls._markets_from_request(request_payload)
        if len(markets) >= 2:
            return cls._build_pair_labels_from_markets(markets)
        return []

    @classmethod
    def _pair_markets_from_request(
        cls,
        request_payload: Dict[str, Any],
    ) -> tuple[List[tuple[str, str]], List[str], bool]:
        selected_pairs = cls._normalize_string_list(
            request_payload.get("selected_pairs")
        )
        if selected_pairs and any("/" in pair for pair in selected_pairs):
            if not all("/" in pair for pair in selected_pairs):
                raise ValueError(
                    "SELECTED_PAIRS_INVALID: selected_pairs must use MARKET_A/MARKET_B labels"
                )

            pair_markets: List[tuple[str, str]] = []
            pair_labels: List[str] = []
            seen: set[str] = set()
            invalid: List[str] = []
            for label in selected_pairs:
                parts = [
                    part.strip().upper()
                    for part in str(label).split("/")
                    if part.strip()
                ]
                if len(parts) != 2 or parts[0] == parts[1]:
                    invalid.append(str(label))
                    continue
                canonical = f"{parts[0]}/{parts[1]}"
                if canonical in seen:
                    continue
                seen.add(canonical)
                pair_labels.append(canonical)
                pair_markets.append((parts[0], parts[1]))
            if invalid:
                raise ValueError(
                    "SELECTED_PAIRS_INVALID: unsupported selected pairs "
                    + ", ".join(invalid)
                )
            return pair_markets, pair_labels, True

        markets = cls._markets_from_request(request_payload)
        if len(markets) < 2:
            raise ValueError(
                "SELECTED_PAIRS_MISSING: at least two selected pairs are required"
            )
        return (
            cls._build_market_pairs(markets),
            cls._build_pair_labels_from_markets(markets),
            False,
        )

    @classmethod
    def _request_payload_hash(cls, request_payload: Dict[str, Any]) -> str:
        sanitized = dict(cls._strip_runtime_control(request_payload))
        sanitized.pop(cls._TASK_CONTEXT_KEY, None)
        sanitized.pop(cls._TASK_FAILURE_KEY, None)
        encoded = json.dumps(
            sanitized, sort_keys=True, separators=(",", ":"), default=str
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @classmethod
    def _task_context_from_request(
        cls, request_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        context = request_payload.get(cls._TASK_CONTEXT_KEY)
        return dict(context) if isinstance(context, dict) else {}

    @classmethod
    def _task_failure_from_request(
        cls, request_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        failure = request_payload.get(cls._TASK_FAILURE_KEY)
        return dict(failure) if isinstance(failure, dict) else {}

    @classmethod
    def _set_task_context(
        cls,
        request_payload: Dict[str, Any],
        task_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        request = dict(request_payload or {})
        request[cls._TASK_CONTEXT_KEY] = task_context
        return request

    @classmethod
    def _clear_task_failure(cls, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        request = dict(request_payload or {})
        request.pop(cls._TASK_FAILURE_KEY, None)
        return request

    @classmethod
    def _set_task_failure(
        cls,
        request_payload: Dict[str, Any],
        failure_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        request = dict(request_payload or {})
        request[cls._TASK_FAILURE_KEY] = failure_payload
        return request

    @classmethod
    def _error_code_from_message(cls, message: str, default: str) -> str:
        prefix = str(message or "").split(":", 1)[0].strip().upper()
        if prefix and prefix.replace("_", "").isalnum() and " " not in prefix:
            return prefix
        return default

    @classmethod
    def _build_task_context(
        cls,
        request_payload: Dict[str, Any],
        **overrides: Any,
    ) -> Dict[str, Any]:
        clean_request = dict(cls._strip_runtime_control(request_payload or {}))
        existing = cls._task_context_from_request(clean_request)
        request_metadata = clean_request.get("metadata")
        request_metadata = (
            request_metadata if isinstance(request_metadata, dict) else {}
        )
        selected_pairs = cls._selected_pair_labels_from_request(clean_request)
        raw_strategy_snapshot = clean_request.get("strategy_payload_snapshot")
        strategy_snapshot = (
            raw_strategy_snapshot if isinstance(raw_strategy_snapshot, dict) else None
        )
        source_strategy_version = (
            clean_request.get("source_strategy_version")
            or existing.get("source_strategy_version")
            or (strategy_snapshot or {}).get("version_number")
            or (strategy_snapshot or {}).get("version")
        )
        strategy_name = (strategy_snapshot or {}).get("name") or existing.get(
            "strategy_name"
        )
        source = str(clean_request.get("source") or existing.get("source") or "api")
        requested_by_user_id = clean_request.get(
            "requested_by_user_id"
        ) or existing.get("requested_by_user_id")
        payload_hash = existing.get("payload_hash") or cls._request_payload_hash(
            clean_request
        )
        metadata: Dict[str, Any] = {
            "strategy_name": strategy_name,
            "strategy_version": source_strategy_version,
            "payload_hash": payload_hash,
            "pair_count": len(selected_pairs),
            "source": source,
        }
        if requested_by_user_id is not None:
            metadata["requested_by_user_id"] = requested_by_user_id

        merged_metadata: Dict[str, Any] = {}
        if request_metadata:
            merged_metadata.update(request_metadata)
        existing_metadata = existing.get("metadata")
        if isinstance(existing_metadata, dict):
            merged_metadata.update(existing_metadata)
        merged_metadata.update(metadata)
        queue = str(
            overrides.get("queue")
            or existing.get("queue")
            or os.getenv("BACKTEST_CELERY_QUEUE", "backtests")
        ).strip()

        context: Dict[str, Any] = {
            **existing,
            "strategy_id": clean_request.get("strategy_id")
            or existing.get("strategy_id"),
            "strategy_payload_snapshot": strategy_snapshot,
            "pairs": cls._markets_from_request(clean_request),
            "selected_pairs": selected_pairs,
            "bot_id": clean_request.get("bot_id") or existing.get("bot_id"),
            "environment": clean_request.get("environment")
            or existing.get("environment")
            or os.getenv("ENVIRONMENT")
            or os.getenv("APP_ENV")
            or "local",
            "source": source,
            "requested_by_user_id": requested_by_user_id,
            "strategy_name": strategy_name,
            "source_strategy_version": source_strategy_version,
            "queue": queue or "backtests",
            "payload_hash": payload_hash,
            "metadata": merged_metadata,
        }
        context.update(overrides)
        return context

    def update_backtest_metadata(
        self,
        run_id: str,
        metadata: Dict[str, Any],
        *,
        merge: bool = True,
    ) -> Optional[Dict[str, Any]]:
        run_data = self._load_run_data(run_id)
        if run_data is None:
            return None

        request_payload = dict(run_data.get("request") or {})
        task_context = self._task_context_from_request(request_payload)
        existing_metadata = task_context.get("metadata")
        existing_metadata = (
            dict(existing_metadata) if isinstance(existing_metadata, dict) else {}
        )
        incoming_metadata = dict(metadata or {})

        next_metadata = dict(existing_metadata)
        if merge:
            next_metadata.update(incoming_metadata)
        else:
            next_metadata = incoming_metadata

        task_context["metadata"] = next_metadata
        request_payload[self._TASK_CONTEXT_KEY] = task_context
        request_payload["metadata"] = next_metadata
        run_data["request"] = request_payload
        run_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        persisted = self._persist_run_data(run_data)
        observed = self._with_status_observability(persisted)
        return {
            "run_id": run_id,
            "status": observed.get("status"),
            "updated_at": observed.get("updated_at"),
            "metadata": dict(observed.get("metadata") or {}),
        }

    @classmethod
    def _merge_runtime_control(
        cls,
        run_data: Dict[str, Any],
        existing: Dict[str, Any],
    ) -> Dict[str, Any]:
        current_control = cls._get_runtime_control(run_data)
        existing_control = cls._get_runtime_control(existing)
        if not existing_control:
            return run_data
        current_action = str(current_control.get("action") or "").lower()
        has_pending_external_control = any(
            bool(existing_control.get(key))
            for key in ("pause_requested", "resume_requested", "cancel_requested")
        )
        should_keep_existing = not current_control or (
            has_pending_external_control
            and current_action not in {"pause", "resume", "cancel"}
        )
        if should_keep_existing:
            merged = dict(run_data)
            request = dict(merged.get("request") or {})
            request[cls._CONTROL_KEY] = existing_control
            merged["request"] = request
            merged["control_status"] = existing_control.get("status")
            merged["control_action"] = existing_control.get("action")
            merged["worker_backend"] = existing_control.get("worker_backend")
            merged["worker_task_id"] = existing_control.get("worker_task_id")
            return merged
        return run_data

    def _load_fresh_runtime_control(self, run_id: str) -> Dict[str, Any]:
        # Read control flags through a SHORT-LIVED session when the bound
        # repository carries the worker's long-lived session: a SELECT on it
        # opens a transaction that pins a pooled connection until the next
        # (throttled) write commit — and continuously while paused, because
        # the pause poll loop only reads. Open → read → close returns the
        # connection to the pool immediately.
        persisted: Optional[Dict[str, Any]] = None
        try:
            if self.repository.session is not None:
                session = db.get_session()
                try:
                    persisted = BacktestRepository(session).get_run_overview(run_id)
                finally:
                    session.close()
            else:
                persisted = self.repository.get_run_overview(run_id)
        except Exception:
            persisted = None
        if persisted:
            return self._get_runtime_control(persisted)
        return self._get_runtime_control(self._runs.get(run_id, {}))

    @classmethod
    def _apply_control_observability(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        control = cls._get_runtime_control(payload)
        status = cls._canonical_status(payload.get("status"))
        payload["status"] = status
        action = str(control.get("action") or "").lower()
        control_status = str(control.get("status") or "").lower()
        pause_requested = bool(control.get("pause_requested"))
        resume_requested = bool(control.get("resume_requested"))
        is_terminal = status in cls._TERMINAL_STATUSES

        payload["control_status"] = control.get("status")
        payload["control_action"] = control.get("action")
        payload["worker_backend"] = control.get("worker_backend") or "asyncio"
        payload["worker_task_id"] = control.get("worker_task_id")
        payload["pausable"] = (
            status in {"pending", "running"}
            and not pause_requested
            and action != "cancel"
        )
        payload["resumable"] = not is_terminal and (
            status == "paused"
            or (pause_requested and control_status in {"pause_requested", "paused"})
        )
        payload["restartable"] = True
        if resume_requested:
            payload["control_status"] = "resume_requested"
        return payload

    @classmethod
    def _apply_task_observability(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        request_payload = dict(payload.get("request") or {})
        task_context = cls._task_context_from_request(request_payload)
        task_failure = cls._task_failure_from_request(request_payload)

        payload["strategy_id"] = task_context.get("strategy_id")
        payload["bot_id"] = task_context.get("bot_id")
        payload["source"] = task_context.get("source")
        payload["selected_pairs"] = list(task_context.get("selected_pairs") or [])
        payload["metadata"] = dict(task_context.get("metadata") or {})
        payload["worker_hostname"] = task_context.get("worker_hostname")
        payload["retry_count"] = task_context.get("retry_count")
        payload["error_code"] = task_failure.get("error_code")
        payload["traceback"] = task_failure.get("traceback")
        payload["result_location"] = cls._result_location(payload)
        payload["result_summary"] = cls._result_summary(payload)
        return payload

    @staticmethod
    def _result_location(payload: Dict[str, Any]) -> str:
        run_id = str(payload.get("run_id") or "").strip()
        return f"/api/v1/backtests/{run_id}" if run_id else ""

    @classmethod
    def _result_summary(cls, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        status = cls._canonical_status(payload.get("status"))
        if status not in {"completed", "failed", "timeout", "cancelled"}:
            return None
        return {
            "status": status,
            "total_pnl": cls._safe_float(payload.get("total_pnl"), 0.0),
            "total_trades": int(payload.get("total_trades") or 0),
            "win_rate": cls._safe_float(payload.get("win_rate"), 0.0),
            "sharpe_ratio": cls._safe_float(payload.get("sharpe_ratio"), 0.0),
        }

    @staticmethod
    def _configured_worker_backend() -> str:
        backend = os.getenv("BACKTEST_WORKER_BACKEND", "asyncio").strip().lower()
        if backend in {"celery", "asyncio", "nats"}:
            return backend
        return "asyncio"

    @classmethod
    def _worker_backend_reprobe_cooldown_seconds(cls) -> float:
        raw = os.getenv("BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS")
        if raw in (None, ""):
            return float(cls._BACKEND_REPROBE_COOLDOWN_SECONDS)
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return float(cls._BACKEND_REPROBE_COOLDOWN_SECONDS)

    @staticmethod
    def _probe_celery_worker_available(timeout_seconds: float = 1.5) -> bool:
        try:
            from src.infrastructure.workers.celery_app import celery_app

            ping = celery_app.control.ping(timeout=float(timeout_seconds), limit=1)
            return bool(ping)
        except Exception:
            return False

    @classmethod
    async def _resolve_worker_backend(cls) -> str:
        backend = cls._configured_worker_backend()
        # celery and nats are explicit backend choices returned as-is. "nats" is
        # the JetStream-authoritative mode: execution is driven by a
        # backtest.command.start consumed by the NATS worker (WORKER_MODE=nats),
        # so the creation flow must neither enqueue Celery nor run asyncio.
        if backend in {"celery", "nats"}:
            return backend

        auto_reprobe = cls._coerce_bool(
            os.getenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "true"),
            default=True,
        )
        if not auto_reprobe:
            return backend

        now_monotonic = time.monotonic()
        cooldown_seconds = cls._worker_backend_reprobe_cooldown_seconds()
        with cls._backend_reprobe_lock:
            last_probe = float(cls._backend_reprobe_last_monotonic)
            if now_monotonic - last_probe < cooldown_seconds:
                return "celery" if cls._backend_reprobe_last_available else backend
            cls._backend_reprobe_last_monotonic = now_monotonic

        celery_available = False
        try:
            probe_timeout = 2.5
            celery_available = bool(
                await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        _BACKEND_PROBE_EXECUTOR,
                        cls._probe_celery_worker_available,
                    ),
                    timeout=probe_timeout,
                )
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Celery backend re-probe exceeded %.1fs; keeping backend=%s",
                probe_timeout,
                backend,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Celery backend re-probe failed: %s", exc)

        with cls._backend_reprobe_lock:
            cls._backend_reprobe_last_available = celery_available
            cls._backend_reprobe_last_monotonic = time.monotonic()

        if celery_available:
            os.environ["BACKTEST_WORKER_BACKEND"] = "celery"
            logger.info(
                "Celery worker detected after startup; promoting BACKTEST_WORKER_BACKEND=celery"
            )
            return "celery"

        return backend

    @staticmethod
    def _env_positive_int(name: str, default: int) -> int:
        # Implementation in :mod:`backtest_history` (Phase 3 extraction).
        return _history._env_positive_int(name, default)

    @staticmethod
    def _env_positive_float(name: str, default: float) -> float:
        return _history._env_positive_float(name, default)

    @classmethod
    def _stale_backtest_heartbeat_seconds(cls) -> float:
        raw = os.getenv("BACKTEST_STALE_HEARTBEAT_SECONDS")
        if raw is None:
            return float(cls._STALE_BACKTEST_HEARTBEAT_SECONDS)
        try:
            return max(5.0, float(raw))
        except (TypeError, ValueError):
            return float(cls._STALE_BACKTEST_HEARTBEAT_SECONDS)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def _heartbeat_age_seconds(cls, run_data: Dict[str, Any]) -> Optional[float]:
        heartbeat_at = cls._parse_dt(run_data.get("updated_at"))
        if heartbeat_at is None:
            return None
        return round(
            max(0.0, (datetime.now(timezone.utc) - heartbeat_at).total_seconds()), 3
        )

    @classmethod
    def _with_status_observability(cls, run_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = cls._normalize_lifecycle_state(run_data)
        payload = cls._apply_task_observability(payload)
        status = cls._canonical_status(payload.get("status"))
        payload["last_heartbeat_at"] = payload.get("updated_at")
        payload["heartbeat_age_seconds"] = cls._heartbeat_age_seconds(payload)
        if (
            status == "running"
            and payload["heartbeat_age_seconds"] is not None
            and payload["heartbeat_age_seconds"]
            > cls._stale_backtest_heartbeat_seconds()
        ):
            stale_message = (
                "Backtest heartbeat is stale; the worker task may have been interrupted "
                "or restarted"
            )
            payload["status"] = "stale"
            payload["current_task"] = "stale"
            payload["error"] = payload.get("error") or stale_message
            payload["error_message"] = payload.get("error_message") or stale_message
            status = "stale"
        payload["cancellable"] = status not in cls._TERMINAL_STATUSES
        return cls._apply_control_observability(payload)

    @classmethod
    def _heartbeat_keepalive_seconds(cls) -> float:
        raw = os.getenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS")
        if raw is None:
            stale_threshold = cls._stale_backtest_heartbeat_seconds()
            return min(
                float(cls._HEARTBEAT_KEEPALIVE_SECONDS), max(0.1, stale_threshold / 3.0)
            )
        try:
            return max(0.1, float(raw))
        except (TypeError, ValueError):
            stale_threshold = cls._stale_backtest_heartbeat_seconds()
            return min(
                float(cls._HEARTBEAT_KEEPALIVE_SECONDS), max(0.1, stale_threshold / 3.0)
            )

    async def _run_backtest_heartbeat_keepalive(
        self,
        run_id: str,
        deadline_monotonic: float,
    ) -> None:
        interval = self._heartbeat_keepalive_seconds()
        while self._remaining_seconds(deadline_monotonic) > 0:
            sleep_for = min(
                interval, max(0.1, self._remaining_seconds(deadline_monotonic))
            )
            await asyncio.sleep(sleep_for)

            run_data = self._load_run_data(run_id)
            if not run_data:
                return

            status = self._canonical_status(run_data.get("status"))
            if status in self._TERMINAL_STATUSES:
                return

            self._update_run_data(
                run_id, updated_at=datetime.now(timezone.utc).isoformat()
            )

    def _touch_run_heartbeat(self, run_id: str) -> bool:
        """Refresh only the stored heartbeat for a run without rewriting the row."""
        timestamp = datetime.now(timezone.utc).isoformat()
        if self.repository.session is None:
            touched: bool = self.repository.touch_run(run_id, timestamp)
            if touched and run_id in self._runs:
                cached = dict(self._runs.get(run_id) or {})
                cached["updated_at"] = timestamp
                self._runs[run_id] = cached
            return touched

        session = db.get_session()
        try:
            repository = BacktestRepository(session)
            touched_db: bool = repository.touch_run(run_id, timestamp)
            if touched_db and run_id in self._runs:
                cached = dict(self._runs.get(run_id) or {})
                cached["updated_at"] = timestamp
                self._runs[run_id] = cached
            return touched_db
        finally:
            session.close()

    def _run_backtest_heartbeat_keepalive_thread(
        self,
        run_id: str,
        deadline_monotonic: float,
        stop_event: threading.Event,
    ) -> None:
        interval = self._heartbeat_keepalive_seconds()
        while (
            not stop_event.is_set() and self._remaining_seconds(deadline_monotonic) > 0
        ):
            sleep_for = min(
                interval, max(0.1, self._remaining_seconds(deadline_monotonic))
            )
            if stop_event.wait(timeout=sleep_for):
                return

            if self._remaining_seconds(deadline_monotonic) <= 0:
                return

            try:
                run_data = self._load_run_data(run_id)
                if not run_data:
                    return

                status = self._canonical_status(run_data.get("status"))
                if status in self._TERMINAL_STATUSES:
                    return

                if not self._touch_run_heartbeat(run_id):
                    continue
            except Exception as exc:
                logger.warning(
                    "Backtest heartbeat keepalive thread failed for run %s: %s",
                    run_id,
                    exc,
                )
                continue

    async def _touch_run_heartbeat_async(self, run_id: str) -> None:
        await asyncio.to_thread(self._touch_run_heartbeat, run_id)

    def _resolve_stale_run_data(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        observed = self._with_status_observability(run_data)
        original_status = self._canonical_status(run_data.get("status"))
        if observed.get("status") != run_data.get("status") and original_status in {
            "pending",
            "running",
        }:
            persisted = dict(run_data)
            persisted.update(
                {
                    "status": observed.get("status"),
                    "current_task": observed.get("current_task"),
                    "error": observed.get("error"),
                    "error_message": observed.get("error_message"),
                }
            )
            if observed.get("status") in self._TERMINAL_STATUSES and not persisted.get(
                "finished_at"
            ):
                persisted["finished_at"] = datetime.now(timezone.utc).isoformat()
                persisted["completed_at"] = persisted["finished_at"]
            return self._with_status_observability(self._persist_run_data(persisted))

        if observed.get("status") != "stale" or original_status != "running":
            return observed

        stalled = dict(run_data)
        stalled.update(
            {
                "status": "stale",
                "current_task": "stale",
                "error": observed.get("error"),
                "error_message": observed.get("error_message"),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return self._with_status_observability(self._persist_run_data(stalled))

    @classmethod
    def _parse_timeout_seconds(cls, request_payload: Dict[str, Any]) -> float:
        params = request_payload.get("trading_parameters") or {}
        raw = request_payload.get("timeout_seconds", params.get("timeout_seconds"))
        if raw is None:
            return float(cls._DEFAULT_TIMEOUT_SECONDS)
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            return float(cls._DEFAULT_TIMEOUT_SECONDS)
        return cls._clamp(parsed, cls._MIN_TIMEOUT_SECONDS, cls._MAX_TIMEOUT_SECONDS)

    @staticmethod
    def _remaining_seconds(deadline_monotonic: float) -> float:
        # Implementation in :mod:`backtest_history` (Phase 3 extraction).
        return _history._remaining_seconds(deadline_monotonic)

    @staticmethod
    def _describe_exception(exc: BaseException) -> str:
        return _history._describe_exception(exc)

    @classmethod
    def _attach_history_fetch_summary(
        cls,
        run_data: Dict[str, Any],
        history_telemetry: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        request_payload = dict(run_data.get("request") or {})
        task_context = cls._task_context_from_request(request_payload)
        metadata = dict(task_context.get("metadata") or {})
        metadata["history_fetch_telemetry"] = _history._history_fetch_summary(
            history_telemetry
        )
        task_context["metadata"] = metadata
        request_payload[cls._TASK_CONTEXT_KEY] = task_context
        run_data["request"] = request_payload
        return run_data

    @classmethod
    async def _await_with_deadline(
        cls,
        awaitable: Awaitable[Any],
        deadline_monotonic: float,
        phase: str,
    ) -> Any:
        remaining = cls._remaining_seconds(deadline_monotonic)
        if remaining <= 0:
            raise TimeoutError(f"Backtest timed out during {phase}")
        try:
            return await asyncio.wait_for(awaitable, timeout=remaining)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Backtest timed out during {phase}") from exc

    async def _honor_runtime_control(
        self,
        run_id: str,
        run_data: Dict[str, Any],
        deadline_monotonic: float,
        *,
        checkpoint_writer: Optional[Callable[[], None]] = None,
    ) -> Dict[str, Any]:
        control = self._load_fresh_runtime_control(run_id)
        if run_data.get("cancel_requested") or control.get("cancel_requested"):
            raise asyncio.CancelledError()

        if not control.get("pause_requested"):
            return run_data

        now = datetime.now(timezone.utc).isoformat()
        run_data = self._set_runtime_control(
            run_data,
            **{
                **control,
                "status": "paused",
                "action": "pause",
                "pause_requested": True,
                "resume_requested": False,
                "worker_backend": control.get("worker_backend") or "asyncio",
            },
        )
        run_data.update(
            {
                "status": "paused",
                "current_task": "paused",
                "updated_at": now,
            }
        )
        run_data = self._persist_run_data(run_data)
        # Entering a pause is a likely precursor to an operator restart —
        # persist a resume point covering the completed prefix while the
        # in-memory state is still warm. The writer never raises.
        if checkpoint_writer is not None:
            checkpoint_writer()

        while True:
            if self._remaining_seconds(deadline_monotonic) <= 0:
                raise TimeoutError("Backtest timed out while paused")

            await asyncio.sleep(
                min(1.0, max(0.001, self._remaining_seconds(deadline_monotonic)))
            )
            control = self._load_fresh_runtime_control(run_id)
            if run_data.get("cancel_requested") or control.get("cancel_requested"):
                raise asyncio.CancelledError()
            if control.get("resume_requested") or not control.get("pause_requested"):
                now = datetime.now(timezone.utc).isoformat()
                run_data = self._set_runtime_control(
                    run_data,
                    **{
                        **control,
                        "status": "running",
                        "action": "resume",
                        "pause_requested": False,
                        "resume_requested": False,
                        "resumed_at": now,
                        "worker_backend": control.get("worker_backend") or "asyncio",
                    },
                )
                run_data.update(
                    {
                        "status": "running",
                        "current_task": "processing pair",
                        "updated_at": now,
                    }
                )
                return self._persist_run_data(run_data)

            now = datetime.now(timezone.utc).isoformat()
            run_data.update(
                {"status": "paused", "current_task": "paused", "updated_at": now}
            )
            run_data = self._persist_run_data(run_data)

    async def execute_existing_backtest(
        self,
        run_id: str,
        progress_callback: Any = None,
        *,
        propagate_exceptions: bool = False,
    ) -> None:
        """Execute an already-persisted run. Used by external worker backends."""
        run_data = self._load_run_data(run_id)
        if not run_data:
            raise ValueError(f"Backtest run '{run_id}' not found")
        request_payload = self._strip_runtime_control(run_data.get("request") or {})
        if not request_payload:
            raise ValueError(f"Backtest run '{run_id}' has no request payload")
        await self._execute_backtest(
            run_id=run_id,
            request_payload=request_payload,
            progress_callback=progress_callback,
            propagate_exceptions=propagate_exceptions,
        )

    def _enqueue_celery_backtest(
        self,
        run_id: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Dispatch a persisted backtest run to Celery."""
        try:
            from src.infrastructure.workers.backtest_tasks import run_backtest_task
        except Exception as exc:
            raise RuntimeError("Celery backtest worker is not available") from exc

        queue = (
            str(
                (task_context or {}).get("queue")
                or os.getenv("BACKTEST_CELERY_QUEUE", "backtests")
            ).strip()
            or "backtests"
        )
        async_result = run_backtest_task.apply_async(
            args=(run_id,),
            kwargs={"task_context": task_context or {}},
            task_id=run_id,
            queue=queue,
        )
        logger.info(
            "celery_backtest_task_created run_id=%s task_id=%s queue=%s",
            run_id,
            async_result.id,
            queue,
        )
        return str(async_result.id)

    def mark_backtest_retrying(
        self,
        run_id: str,
        *,
        error: BaseException | str,
        countdown_seconds: float,
        retry_count: int,
        task_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Persist retry visibility for a Celery-managed backtest run."""
        data = self._load_run_data(run_id)
        if not data:
            return None

        message = (
            self._describe_exception(error)
            if isinstance(error, BaseException)
            else str(error)
        )
        request_payload = dict(data.get("request") or {})
        task_context = self._task_context_from_request(request_payload)
        task_context["retry_count"] = retry_count
        task_context["last_retry_at"] = datetime.now(timezone.utc).isoformat()
        task_context["next_retry_in_seconds"] = round(float(countdown_seconds), 3)
        request_payload = self._set_task_context(request_payload, task_context)
        request_payload = self._set_task_failure(
            request_payload,
            {
                "error_code": self._error_code_from_message(
                    message, "BACKTEST_TRANSIENT_RETRY"
                ),
                "error_message": message,
                "traceback": traceback_module.format_exc(),
            },
        )

        data["request"] = request_payload
        data = self._set_runtime_control(
            data,
            status="retrying",
            action="retry",
            pause_requested=False,
            resume_requested=False,
            cancel_requested=False,
            worker_backend="celery",
            worker_task_id=task_id or data.get("worker_task_id") or run_id,
            retry_count=retry_count,
            retry_after_seconds=round(float(countdown_seconds), 3),
        )
        now = datetime.now(timezone.utc).isoformat()
        data.update(
            {
                "status": "retrying",
                "current_task": "retrying",
                "error": message,
                "error_message": message,
                "updated_at": now,
            }
        )
        async_job_manager.mark_progress(
            run_id,
            float(data.get("progress_pct") or 0.0),
            metadata={
                "run_id": run_id,
                "status": "retrying",
                "retry_count": retry_count,
                "retry_after_seconds": round(float(countdown_seconds), 3),
            },
        )
        logger.warning(
            "celery_backtest_task_retrying run_id=%s task_id=%s retry_count=%s countdown_seconds=%.3f error=%s",
            run_id,
            task_id or data.get("worker_task_id") or run_id,
            retry_count,
            float(countdown_seconds),
            message,
        )
        return self._persist_run_data(data)

    def _revoke_celery_backtest(self, task_id: Optional[str]) -> None:
        if not task_id:
            return
        try:
            from src.infrastructure.workers.celery_app import celery_app

            celery_app.control.revoke(str(task_id), terminate=True, signal="SIGTERM")
        except Exception as exc:
            logger.warning("Failed to revoke Celery backtest task %s: %s", task_id, exc)

    def _mark_celery_enqueue_failed(
        self,
        run_data: Dict[str, Any],
        exc: BaseException,
        *,
        action: str = "enqueue_failed",
    ) -> Dict[str, Any]:
        """Persist a failed handoff so the API never executes Celery runs inline."""
        run_id = str(run_data.get("run_id") or "")
        message = str(exc) or exc.__class__.__name__
        now = datetime.now(timezone.utc).isoformat()
        request_payload = dict(run_data.get("request") or {})
        request_payload = self._set_task_failure(
            request_payload,
            {
                "error_code": self._error_code_from_message(
                    message, "BACKTEST_ENQUEUE_FAILED"
                ),
                "error_message": message,
                "traceback": traceback_module.format_exc(),
            },
        )
        failed = dict(run_data)
        failed["request"] = request_payload
        failed = self._set_runtime_control(
            failed,
            status="failed",
            action=action,
            pause_requested=False,
            resume_requested=False,
            cancel_requested=False,
            worker_backend="celery",
            worker_task_id=failed.get("worker_task_id") or run_id,
        )
        failed.update(
            {
                "status": "failed",
                "current_task": "enqueue failed",
                "error": message,
                "error_message": message,
                "finished_at": now,
                "completed_at": now,
                "updated_at": now,
                "worker_backend": "celery",
                "worker_task_id": failed.get("worker_task_id") or run_id,
            }
        )
        async_job_manager.mark_failed(run_id, message)
        return self._persist_run_data(failed)

    @staticmethod
    def _extract_request_payload(request: Any) -> Dict[str, Any]:
        if hasattr(request, "model_dump"):
            dumped: Dict[str, Any] = request.model_dump()
            return dumped
        if isinstance(request, dict):
            return request
        return {}

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _auto_recovery_mode(cls) -> str:
        """Resolve startup auto-recovery mode for orphaned persisted backtests."""
        mode = os.getenv("BACKTEST_AUTO_RECOVERY_MODE", "").strip().lower()
        if not mode and cls._coerce_bool(
            os.getenv("BACKTEST_AUTO_RECOVER"), default=False
        ):
            mode = "restart"
        if not mode:
            return "mark_failed"
        aliases = {
            "0": "off",
            "false": "off",
            "no": "off",
            "disabled": "off",
            "disable": "off",
            "observe": "off",
            "dry_run": "off",
            "dry-run": "off",
            "reconcile": "mark_failed",
            "fail": "mark_failed",
            "failed": "mark_failed",
            "mark-failed": "mark_failed",
            "mark_failed": "mark_failed",
            "1": "restart",
            "true": "restart",
            "yes": "restart",
            "on": "restart",
            "rerun": "restart",
            "restart": "restart",
            "resume": "restart",
        }
        return aliases.get(mode, "mark_failed")

    @classmethod
    def _auto_recovery_min_age_seconds(cls) -> float:
        raw = os.getenv("BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS")
        if raw is None:
            return float(cls._stale_backtest_heartbeat_seconds())
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return float(cls._stale_backtest_heartbeat_seconds())

    @classmethod
    def _is_auto_recovery_candidate(cls, run_data: Dict[str, Any]) -> bool:
        minimum_age = cls._auto_recovery_min_age_seconds()
        if minimum_age <= 0:
            return True
        age = cls._heartbeat_age_seconds(run_data)
        return age is None or age >= minimum_age

    def _prepare_existing_run_recovery(
        self,
        run_data: Dict[str, Any],
        *,
        worker_backend: str,
        worker_task_id: str,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        recovered = dict(run_data)
        recovered.update(
            {
                "status": "pending" if worker_backend == "celery" else "running",
                "current_task": (
                    "auto recovery queued"
                    if worker_backend == "celery"
                    else "auto recovery running"
                ),
                "error": None,
                "error_message": None,
                "cancel_requested": False,
                "updated_at": now,
                "worker_backend": worker_backend,
                "worker_task_id": worker_task_id,
            }
        )
        recovered = self._set_runtime_control(
            recovered,
            status="pending" if worker_backend == "celery" else "running",
            action="auto_recover",
            pause_requested=False,
            resume_requested=False,
            cancel_requested=False,
            worker_backend=worker_backend,
            worker_task_id=worker_task_id,
            requested_at=now,
        )
        return self._persist_run_data(recovered)

    async def _restart_interrupted_existing_run(
        self,
        run: Dict[str, Any],
        progress_callback: Any = None,
    ) -> Optional[Dict[str, Any]]:
        run_id = str(run.get("run_id") or "").strip()
        if not run_id:
            return None

        run_data = self._load_run_data(run_id)
        if not run_data:
            return None

        request_payload = self._strip_runtime_control(run_data.get("request") or {})
        if not request_payload:
            return None

        worker_backend = await self._resolve_worker_backend()
        if worker_backend == "celery":
            try:
                task_id = self._enqueue_celery_backtest(
                    run_id,
                    self._build_task_context(request_payload),
                )
                return self._prepare_existing_run_recovery(
                    run_data,
                    worker_backend="celery",
                    worker_task_id=task_id,
                )
            except Exception as exc:
                logger.exception(
                    "Celery recovery enqueue failed for run %s; marking failed",
                    run_id,
                )
                return self._mark_celery_enqueue_failed(
                    run_data,
                    exc,
                    action="auto_recover_enqueue_failed",
                )

        if worker_backend == "nats":
            # JetStream-authoritative recovery: the NATS consumer will (re)process
            # this run via JetStream redelivery; do not asyncio-execute it here.
            logger.info(
                "Skipping asyncio recovery for run %s in NATS mode; NATS consumer will redeliver",
                run_id,
            )
            return None

        task = async_job_manager.create_supervised_task(
            self.execute_existing_backtest(run_id, progress_callback),
            job_type="backtest",
            job_id=run_id,
            parameters=request_payload,
            metadata={
                "run_id": run_id,
                "worker_backend": "asyncio",
                "recovery": "startup_auto_recover",
            },
            auto_complete=False,
        )
        self._tasks[run_id] = task
        task.add_done_callback(
            lambda completed_task: self._handle_task_done(run_id, completed_task)
        )
        return self._prepare_existing_run_recovery(
            run_data,
            worker_backend="asyncio",
            worker_task_id=run_id,
        )

    async def auto_recover_interrupted_runs(
        self,
        progress_callback: Any = None,
        *,
        mode: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Reconcile orphaned backtests at API startup.

        The default mode marks orphaned in-progress rows as failed so stale UI
        state does not masquerade as active work. Automatic restart is opt-in
        because it can consume exchange-history and CPU resources after a deploy.
        """
        resolved_mode = (mode or self._auto_recovery_mode()).strip().lower()
        if resolved_mode not in {"off", "mark_failed", "restart"}:
            resolved_mode = "mark_failed"

        runs = self.repository.list_runs(limit=None, offset=0)
        for run in runs:
            run_id = str(run.get("run_id") or "").strip()
            if run_id:
                self._runs[run_id] = dict(run)

        candidates = self._find_orphaned_in_progress_runs(runs)
        eligible_candidates = [
            run for run in candidates if self._is_auto_recovery_candidate(run)
        ]
        fresh_candidates = [
            run for run in candidates if not self._is_auto_recovery_candidate(run)
        ]
        safe_limit = max(1, int(limit or 50))
        marked_failed: List[Dict[str, Any]] = []
        restarted: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = list(fresh_candidates)

        if resolved_mode == "off":
            return {
                "mode": resolved_mode,
                "interruption_error": self._INTERRUPTION_ERROR,
                "candidate_count": len(candidates),
                "eligible_count": len(eligible_candidates),
                "marked_failed_count": 0,
                "restarted_count": 0,
                "skipped_count": len(candidates),
                "candidates": [
                    self._to_ops_row(run) for run in candidates[:safe_limit]
                ],
                "marked_failed": [],
                "restarted": [],
                "skipped": [self._to_ops_row(run) for run in candidates[:safe_limit]],
            }

        for run in eligible_candidates:
            run_id = str(run.get("run_id") or "").strip()
            if resolved_mode == "restart":
                recovered = await self._restart_interrupted_existing_run(
                    run,
                    progress_callback=progress_callback,
                )
                if recovered is not None:
                    restarted.append(recovered)
                    continue

            if not run_id:
                skipped.append(run)
                continue

            persisted = self.repository.save_run(
                self._build_interrupted_run_payload(run)
            )
            self._runs[run_id] = dict(persisted)
            if resolved_mode == "restart":
                skipped.append(
                    {
                        **persisted,
                        "error": persisted.get("error")
                        or "Backtest run has no restartable request payload",
                    }
                )
            else:
                marked_failed.append(persisted)

        return {
            "mode": resolved_mode,
            "interruption_error": self._INTERRUPTION_ERROR,
            "candidate_count": len(candidates),
            "eligible_count": len(eligible_candidates),
            "marked_failed_count": len(marked_failed),
            "restarted_count": len(restarted),
            "skipped_count": len(skipped),
            "candidates": [self._to_ops_row(run) for run in candidates[:safe_limit]],
            "marked_failed": [
                self._to_ops_row(run) for run in marked_failed[:safe_limit]
            ],
            "restarted": [self._to_ops_row(run) for run in restarted[:safe_limit]],
            "skipped": [self._to_ops_row(run) for run in skipped[:safe_limit]],
        }

    @classmethod
    def _build_metrics(cls, request: Any) -> Dict[str, Any]:
        payload = cls._extract_request_payload(request)
        params = (
            payload.get("trading_parameters") or payload.get("strategy_params") or {}
        )

        zscore_threshold = float(params.get("zscore_threshold", 1.5) or 1.5)
        stats_window = int(params.get("stats_window", 21) or 21)
        usd_per_trade = float(params.get("usd_per_trade", 10.0) or 10.0)
        close_at_zscore_cross = cls._coerce_bool(
            params.get("close_at_zscore_cross"), default=True
        )

        transaction_fee = float(params.get("transaction_fee", 0.0) or 0.0)
        slippage = float(params.get("slippage", 0.0) or 0.0)
        risk_free_rate = float(params.get("risk_free_rate", 0.02) or 0.02)
        max_positions = int(params.get("max_positions", 5) or 5)

        baseline = cls._BASELINE_METRICS

        total_pnl = float(baseline["total_pnl"])
        total_pnl += 4.0 * (1.5 - zscore_threshold)
        total_pnl -= 0.05 * ((stats_window - 21) ** 2)
        total_pnl += 0.08 * (usd_per_trade - 10.0)
        if not close_at_zscore_cross:
            total_pnl -= 1.2

        win_rate = float(baseline["win_rate"])
        win_rate -= 0.03 * abs(zscore_threshold - 1.5)
        win_rate -= 0.0025 * abs(stats_window - 21)
        win_rate -= 0.001 * max(0.0, usd_per_trade - 10.0)
        if not close_at_zscore_cross:
            win_rate -= 0.02

        sharpe_ratio = float(baseline["sharpe_ratio"])
        sharpe_ratio -= 0.18 * ((zscore_threshold - 1.5) ** 2)
        sharpe_ratio -= 0.002 * ((stats_window - 21) ** 2)
        sharpe_ratio -= 0.002 * max(0.0, usd_per_trade - 10.0)
        if not close_at_zscore_cross:
            sharpe_ratio -= 0.05

        max_drawdown_pct = float(baseline["max_drawdown_pct"])
        max_drawdown_pct += 1.2 * max(0.0, 1.5 - zscore_threshold)
        max_drawdown_pct += 0.12 * abs(stats_window - 21)
        max_drawdown_pct += 0.035 * max(0.0, usd_per_trade - 10.0)
        if not close_at_zscore_cross:
            max_drawdown_pct += 0.6

        total_trades = int(baseline["total_trades"])
        total_trades += round((1.5 - zscore_threshold) * 10)
        total_trades += round((21 - stats_window) / 4)
        total_trades += round(max(0.0, usd_per_trade - 10.0) / 8)
        if not close_at_zscore_cross:
            total_trades -= 3

        total_pnl -= (transaction_fee * 4000.0) + (slippage * 4400.0)
        total_pnl -= max(0.0, risk_free_rate - 0.02) * 40.0
        total_pnl -= max(0, max_positions - 5) * 0.25

        sharpe_ratio -= (transaction_fee * 60.0) + (slippage * 60.0)
        sharpe_ratio -= max(0.0, risk_free_rate - 0.02) * 0.6
        sharpe_ratio -= max(0, max_positions - 5) * 0.01

        max_drawdown_pct += (transaction_fee * 400.0) + (slippage * 1600.0)
        max_drawdown_pct += max(0, max_positions - 5) * 0.08

        total_trades += int(round(slippage * 5000.0))

        return {
            "total_pnl": round(total_pnl, 1),
            "win_rate": round(cls._clamp(win_rate, 0.25, 0.95), 2),
            "sharpe_ratio": round(cls._clamp(sharpe_ratio, -2.0, 5.0), 2),
            "max_drawdown_pct": round(max(0.0, max_drawdown_pct), 1),
            "total_trades": max(1, total_trades),
        }

    @staticmethod
    def _parse_date(value: str, end_of_day: bool = False) -> datetime:
        base = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        if end_of_day and "T" not in str(value):
            return base.replace(hour=23, minute=59, second=59, microsecond=0)
        return base

    @staticmethod
    def _normalize_resolution(resolution: str) -> str:
        # Implementation in :mod:`backtest_history` (Phase 3 extraction).
        return _history._normalize_resolution(resolution)

    @staticmethod
    def _align_series(
        market_1: Dict[str, float],
        market_2: Dict[str, float],
    ) -> tuple[list[str], np.ndarray, np.ndarray]:
        return _pair_selection._align_series(market_1, market_2)

    @staticmethod
    def _compute_sharpe(daily_pnl: List[float], initial_balance: float) -> float:
        if len(daily_pnl) < 2:
            return 0.0
        returns = np.array(daily_pnl, dtype=np.float64) / max(1e-9, initial_balance)
        std = np.std(returns)
        if std <= 1e-12:
            return 0.0
        # Daily sampling assumption
        sharpe = (np.mean(returns) / std) * math.sqrt(252)
        return float(sharpe)

    @staticmethod
    def _compute_max_drawdown_pct(
        daily_pnl: List[float], initial_balance: float
    ) -> float:
        equity = initial_balance
        peak = equity
        max_dd = 0.0
        for pnl in daily_pnl:
            equity += pnl
            peak = max(peak, equity)
            if peak > 0:
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)
        return float(max_dd * 100.0)

    @staticmethod
    def _build_daily_pnl_rows(
        daily_pnl_agg: Dict[str, float],
        all_trades: List[Dict[str, Any]],
        resolution: str,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "candle_id": f"{day}|PORTFOLIO|{resolution}",
                "date": day,
                "timestamp": f"{day}T00:00:00Z",
                "market": "PORTFOLIO",
                "resolution": resolution,
                "pnl": round(daily_pnl_agg[day], 4),
                "trades": len(
                    [
                        t
                        for t in all_trades
                        if str(t.get("exit_timestamp", "")).startswith(day)
                    ]
                ),
            }
            for day in sorted(daily_pnl_agg.keys())
        ]

    @staticmethod
    def _build_market_pairs(markets: List[str]) -> List[tuple[str, str]]:
        """Build all unique non-self market combinations preserving input order."""
        normalized: List[str] = []
        seen: set[str] = set()
        for market in markets:
            m = str(market).strip()
            if not m or m in seen:
                continue
            seen.add(m)
            normalized.append(m)

        pairs: List[tuple[str, str]] = []
        for i in range(len(normalized) - 1):
            for j in range(i + 1, len(normalized)):
                pairs.append((normalized[i], normalized[j]))
        return pairs

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        # Implementation in :mod:`backtest_pair_selection` (Phase 2 extraction).
        return _pair_selection._safe_float(value, default)

    @staticmethod
    def _normalize_pair_selection_mode(mode: Any) -> str:
        return _pair_selection._normalize_pair_selection_mode(mode)

    @classmethod
    def _prioritize_pairs(
        cls,
        pair_markets: List[tuple[str, str]],
        mode: str,
        market_map: Dict[str, Any],
        history_by_market: Dict[str, Dict[str, float]],
    ) -> List[tuple[str, str]]:
        return _pair_selection._prioritize_pairs(
            pair_markets, mode, market_map, history_by_market
        )

    async def _simulate_pair(
        self,
        run_id: str,
        market_a: str,
        market_b: str,
        timestamps: List[str],
        prices_a: np.ndarray,
        prices_b: np.ndarray,
        params: Dict[str, Any],
        trade_index_offset: int,
        heartbeat_callback: Optional[Any] = None,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, float]]:
        stats_window = max(5, int(params.get("stats_window", 21) or 21))
        entry_z = float(params.get("zscore_threshold", 1.5) or 1.5)
        usd_per_trade = float(params.get("usd_per_trade", 10.0) or 10.0)
        close_on_cross = self._coerce_bool(
            params.get("close_at_zscore_cross"), default=True
        )
        transaction_fee = float(params.get("transaction_fee", 0.0) or 0.0)
        slippage = float(params.get("slippage", 0.0) or 0.0)
        # Exit controls mirror the live ladder in
        # position_manager._resolve_exit_reason; defaults follow src/constants.py
        # (stopLossPct=2.0, takeProfitPct=5.0, positionTimeoutHours=72) so a
        # backtest books exits the live bot would actually take.
        stop_loss_pct = float(params.get("stop_loss_pct", 2.0) or 0.0)
        take_profit_pct = float(params.get("take_profit_pct", 5.0) or 0.0)
        position_timeout_hours = float(
            params.get("position_timeout_hours", 72.0) or 0.0
        )

        if len(prices_a) <= stats_window + 1:
            return [], [], {}

        var_b = float(np.var(prices_b))
        if var_b <= 1e-12:
            return [], [], {}

        # Fit the same mean-reverting residual the live pipeline trades:
        # OLS of prices_a on prices_b with a constant, spread = residual.
        poly_coeffs = np.polyfit(prices_b, prices_a, 1)
        hedge_ratio = float(poly_coeffs[0])
        intercept = float(poly_coeffs[1])

        spread = prices_a - (hedge_ratio * prices_b) - intercept
        trades: List[Dict[str, Any]] = []
        snapshots: List[Dict[str, Any]] = []
        daily_pnl: Dict[str, float] = {}

        open_pos: Optional[Dict[str, Any]] = None

        yield_every_steps = self._env_positive_int(
            "BACKTEST_SIMULATION_YIELD_EVERY_STEPS",
            self._SIMULATION_YIELD_EVERY_STEPS,
        )

        for idx in range(stats_window, len(spread)):
            if idx % yield_every_steps == 0:
                await asyncio.sleep(0)
                if heartbeat_callback is not None:
                    try:
                        await asyncio.wait_for(
                            heartbeat_callback(),
                            timeout=self._PROGRESS_CALLBACK_TIMEOUT_SECONDS,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Backtest inline heartbeat refresh failed for run %s at step %s: %s",
                            run_id,
                            idx,
                            exc,
                        )

            # Same rolling window semantics as the live calculate_zscore:
            # window INCLUDES the current bar and std is sample std (ddof=1,
            # matching pandas rolling.std), so backtest z-scores equal the
            # z-scores the live decision path would compute on the same data.
            window = spread[idx - stats_window + 1 : idx + 1]
            mean = float(np.mean(window))
            std = float(np.std(window, ddof=1))
            if std <= 1e-12:
                continue
            z = (float(spread[idx]) - mean) / std
            ts = timestamps[idx]

            if open_pos is None:
                if z >= entry_z:
                    open_pos = {
                        "side": "short_spread",
                        "entry_idx": idx,
                        "entry_z": z,
                        "entry_p1": float(prices_a[idx]),
                        "entry_p2": float(prices_b[idx]),
                        "entry_ts": ts,
                    }
                elif z <= -entry_z:
                    open_pos = {
                        "side": "long_spread",
                        "entry_idx": idx,
                        "entry_z": z,
                        "entry_p1": float(prices_a[idx]),
                        "entry_p2": float(prices_b[idx]),
                        "entry_ts": ts,
                    }
                continue

            # Mirror the live exit ladder (position_manager._resolve_exit_reason):
            # stop-loss, then take-profit, then timeout, then z-score
            # reversion — which requires BOTH a sign cross AND
            # |z_now| >= |z_entry|, not merely |z| decaying under 0.25.
            exit_reason: Optional[str] = None
            if open_pos is not None:
                ep1_chk = float(open_pos["entry_p1"])
                ep2_chk = float(open_pos["entry_p2"])
                move = (float(prices_a[idx]) - ep1_chk) - hedge_ratio * (
                    float(prices_b[idx]) - ep2_chk
                )
                if open_pos["side"] == "short_spread":
                    move *= -1.0
                notional_chk = max(1e-9, abs(ep1_chk) + abs(hedge_ratio * ep2_chk))
                unrealized_pnl_pct = (move / notional_chk) * 100.0

                entry_dt_chk = datetime.fromisoformat(
                    open_pos["entry_ts"].replace("Z", "+00:00")
                )
                exit_dt_chk = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                age_hours = max(
                    0.0, (exit_dt_chk - entry_dt_chk).total_seconds() / 3600.0
                )

                if stop_loss_pct > 0 and unrealized_pnl_pct <= -stop_loss_pct:
                    exit_reason = "stop_loss"
                elif take_profit_pct > 0 and unrealized_pnl_pct >= take_profit_pct:
                    exit_reason = "take_profit"
                elif position_timeout_hours > 0 and age_hours >= position_timeout_hours:
                    exit_reason = "timeout"
                elif close_on_cross:
                    z_cross = (z < 0 < open_pos["entry_z"]) or (
                        z > 0 > open_pos["entry_z"]
                    )
                    z_level = abs(z) >= abs(open_pos["entry_z"])
                    if z_cross and z_level:
                        exit_reason = "zscore_reversion"

            should_close = exit_reason is not None
            if not should_close or open_pos is None:
                continue

            ep1 = open_pos["entry_p1"]
            ep2 = open_pos["entry_p2"]
            xp1 = float(prices_a[idx])
            xp2 = float(prices_b[idx])

            spread_move = (xp1 - ep1) - hedge_ratio * (xp2 - ep2)
            if open_pos["side"] == "short_spread":
                spread_move *= -1.0

            notional = max(1e-9, abs(ep1) + abs(hedge_ratio * ep2))
            pnl_gross = (spread_move / notional) * usd_per_trade
            fee_cost = usd_per_trade * (transaction_fee + slippage) * 2.0
            pnl = pnl_gross - fee_cost
            pnl_pct = (pnl / max(1e-9, usd_per_trade)) * 100.0

            trade_id = f"t-{run_id}-{trade_index_offset + len(trades):03d}"
            exit_z = z
            entry_dt = datetime.fromisoformat(
                open_pos["entry_ts"].replace("Z", "+00:00")
            )
            exit_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            duration_hours = max(0.0, (exit_dt - entry_dt).total_seconds() / 3600.0)

            trades.append(
                {
                    "trade_id": trade_id,
                    "market_1": market_a,
                    "market_2": market_b,
                    "entry_timestamp": open_pos["entry_ts"],
                    "exit_timestamp": ts,
                    "entry_zscore": round(float(open_pos["entry_z"]), 4),
                    "exit_zscore": round(float(exit_z), 4),
                    "entry_price_m1": round(ep1, 4),
                    "exit_price_m1": round(xp1, 4),
                    "entry_price_m2": round(ep2, 4),
                    "exit_price_m2": round(xp2, 4),
                    "hedge_ratio": round(hedge_ratio, 6),
                    "pnl_usd": round(float(pnl), 4),
                    "pnl_pct": round(float(pnl_pct), 4),
                    "duration_hours": round(duration_hours, 3),
                    "exit_reason": exit_reason,
                    "win": bool(pnl > 0),
                }
            )

            snapshots.append(
                {
                    "timestamp": ts,
                    "positions": [
                        {
                            "position_id": f"pos-{trade_id}",
                            "market_1": market_a,
                            "market_2": market_b,
                            "entry_timestamp": open_pos["entry_ts"],
                            "exit_timestamp": ts,
                            "entry_price_m1": round(ep1, 4),
                            "entry_price_m2": round(ep2, 4),
                            "hedge_ratio": round(hedge_ratio, 6),
                            "entry_zscore": round(float(open_pos["entry_z"]), 4),
                            "total_pnl_usd": round(float(pnl), 4),
                            "status": "CLOSED",
                        }
                    ],
                }
            )

            day_key = ts[:10]
            daily_pnl[day_key] = round(daily_pnl.get(day_key, 0.0) + float(pnl), 4)
            open_pos = None

        return trades, snapshots, daily_pnl

    async def _execute_backtest(
        self,
        run_id: str,
        request_payload: Dict[str, Any],
        progress_callback: Any,
        *,
        propagate_exceptions: bool = False,
    ) -> None:
        run_data = self._load_run_data(run_id)
        if not run_data:
            return

        client = None
        history_fetch_telemetry: Dict[str, Dict[str, Any]] = {}
        heartbeat_thread: Optional[threading.Thread] = None
        heartbeat_stop_event = threading.Event()
        try:
            timeout_seconds = float(
                run_data.get("timeout_seconds")
                or self._parse_timeout_seconds(request_payload)
            )
            request_payload = self._clear_task_failure(request_payload)
            pair_markets, selected_pair_labels, explicit_pair_selection = (
                self._pair_markets_from_request(request_payload)
            )
            request_payload = self._set_task_context(
                request_payload,
                self._build_task_context(
                    request_payload,
                    selected_pairs=selected_pair_labels,
                ),
            )
            started_monotonic = time.monotonic()
            deadline_monotonic = started_monotonic + timeout_seconds
            started_at = datetime.now(timezone.utc)
            deadline_at = started_at + timedelta(seconds=timeout_seconds)
            run_data["status"] = "running"
            run_data["request"] = request_payload
            run_data["started_at"] = (
                run_data.get("started_at") or started_at.isoformat()
            )
            run_data["deadline_at"] = deadline_at.isoformat()
            run_data["timeout_seconds"] = timeout_seconds
            worker_backend = str(
                run_data.get("worker_backend") or self._configured_worker_backend()
            )
            run_data["worker_backend"] = worker_backend
            run_data = self._set_runtime_control(
                run_data,
                status="running",
                action="start",
                pause_requested=False,
                resume_requested=False,
                cancel_requested=False,
                worker_backend=worker_backend,
                worker_task_id=run_data.get("worker_task_id") or run_id,
                started_at=started_at.isoformat(),
            )
            run_data["updated_at"] = started_at.isoformat()
            run_data = self._persist_run_data(run_data)
            # mark_running is handled by create_supervised_task; do not call it here.

            params = request_payload.get("trading_parameters") or {}
            if request_payload.get("strategy_id") is not None and not isinstance(
                request_payload.get("strategy_payload_snapshot"), dict
            ):
                raise ValueError(
                    "STRATEGY_PAYLOAD_MISSING: strategy-linked backtest requires strategy_payload_snapshot"
                )
            if len(selected_pair_labels) == 0:
                raise ValueError(
                    "SELECTED_PAIRS_MISSING: at least two selected pairs are required"
                )

            start_dt = self._parse_date(str(request_payload.get("start_date")))
            end_dt = self._parse_date(
                str(request_payload.get("end_date")), end_of_day=True
            )
            if end_dt <= start_dt:
                raise ValueError("end_date must be after start_date")

            resolution = self._normalize_resolution(
                params.get("resolution", "1HOUR") or "1HOUR"
            )
            initial_balance = float(
                request_payload.get("initial_balance", 10000.0) or 10000.0
            )
            pair_selection_mode = self._normalize_pair_selection_mode(
                request_payload.get(
                    "pair_selection_mode",
                    params.get("pair_selection_mode", "liquidity"),
                )
            )

            max_pairs: Optional[int] = None
            max_pairs_raw = request_payload.get("max_pairs", None)
            if max_pairs_raw is None:
                max_pairs_raw = params.get("max_pairs", None)
            if max_pairs_raw is not None:
                try:
                    parsed_max_pairs = int(max_pairs_raw)
                    # 0 or negative means "no cap" (use all available pairs).
                    max_pairs = parsed_max_pairs if parsed_max_pairs > 0 else None
                except (TypeError, ValueError):
                    # Ignore malformed max_pairs and continue with all pairs.
                    max_pairs = None

            if not pair_markets:
                raise ValueError("No valid market pairs available from request")

            # Checkpoint resume: if a valid checkpoint exists for this exact
            # request, reuse its post-prioritization pair plan and accumulated
            # outputs instead of re-ranking and re-simulating completed pairs.
            # Any miss/corruption/mismatch fails open to a fresh run.
            checkpoint_store = None
            resumed_checkpoint = None
            if _checkpoint.checkpoints_enabled():
                try:
                    checkpoint_store = _checkpoint.get_checkpoint_store()
                except _checkpoint._CHECKPOINT_IO_ERRORS as exc:
                    logger.warning(
                        "Backtest checkpoint store unavailable for run %s: %s",
                        run_id,
                        exc,
                    )
                if checkpoint_store is not None:
                    resumed_checkpoint = _checkpoint.load_checkpoint(
                        checkpoint_store,
                        run_id,
                        expected_payload_hash=self._request_payload_hash(
                            request_payload
                        ),
                    )
            resumed = resumed_checkpoint is not None
            resumed_completed = (
                resumed_checkpoint["completed_pairs_count"]
                if resumed_checkpoint is not None
                else 0
            )

            heartbeat_thread = threading.Thread(
                target=self._run_backtest_heartbeat_keepalive_thread,
                args=(run_id, deadline_monotonic, heartbeat_stop_event),
                name=f"backtest-heartbeat-{run_id}",
                daemon=True,
            )
            heartbeat_thread.start()

            client = await self._await_with_deadline(
                cast(Awaitable[Any], connect_dydx()),
                deadline_monotonic,
                "connecting to dYdX",
            )

            unique_markets = sorted({m for pair in pair_markets for m in pair})
            market_history_cache: Dict[str, Dict[str, float]] = {}

            # Pull market metadata for liquidity ranking when available.
            market_map: Dict[str, Any] = {}
            try:
                markets_payload = await self._await_with_deadline(
                    client.indexer.markets.get_perpetual_markets(),
                    deadline_monotonic,
                    "loading market metadata",
                )
                market_map = (
                    markets_payload.get("markets", {})
                    if isinstance(markets_payload, dict)
                    else {}
                )
            except TimeoutError:
                raise
            except Exception:
                market_map = {}

            # Modes using historical behavior require per-market history cache.
            # Skipped entirely on checkpoint resume (plan already computed).
            if not resumed and pair_selection_mode in {"volatility", "cointegration"}:
                for market in unique_markets:
                    try:
                        market_history_cache[market] = await self._await_with_deadline(
                            _history._fetch_market_history(
                                client=client,
                                market=market,
                                start_dt=start_dt,
                                end_dt=end_dt,
                                resolution=resolution,
                                deadline_monotonic=deadline_monotonic,
                                history_telemetry=history_fetch_telemetry,
                            ),
                            deadline_monotonic,
                            f"loading history for {market}",
                        )
                    except TimeoutError:
                        raise
                    except Exception:
                        market_history_cache[market] = {}

            if not resumed and not explicit_pair_selection:
                pair_markets = self._prioritize_pairs(
                    pair_markets=pair_markets,
                    mode=pair_selection_mode,
                    market_map=market_map,
                    history_by_market=market_history_cache,
                )

                if max_pairs is not None:
                    pair_markets = pair_markets[:max_pairs]
            elif resumed_checkpoint is not None:
                # Trust the checkpointed plan — it defines what "completed"
                # means for this run. Re-ranking now could observe drifted
                # market data and produce a different order.
                pair_markets = [
                    (str(pair[0]), str(pair[1]))
                    for pair in resumed_checkpoint["pair_plan"]
                ]

            total_pairs = len(pair_markets)
            if resumed_checkpoint is not None:
                all_trades: List[Dict[str, Any]] = list(resumed_checkpoint["trades"])
                all_snapshots: List[Dict[str, Any]] = list(
                    resumed_checkpoint["position_snapshots"]
                )
                daily_pnl_agg: Dict[str, float] = dict(resumed_checkpoint["daily_pnl"])
                running_total_pnl = float(resumed_checkpoint["running_total_pnl"])
                running_winners = int(resumed_checkpoint["running_winners"])
                running_gross_profit = float(resumed_checkpoint["running_gross_profit"])
                running_gross_loss = float(resumed_checkpoint["running_gross_loss"])
                logger.info(
                    "Backtest %s resuming from checkpoint: %d/%d pairs already "
                    "complete (%d trades loaded)",
                    run_id,
                    resumed_completed,
                    total_pairs,
                    len(all_trades),
                )
            else:
                all_trades = []
                all_snapshots = []
                daily_pnl_agg = {}
                running_total_pnl = 0.0
                running_winners = 0
                running_gross_profit = 0.0
                running_gross_loss = 0.0
            heavy_every_pairs = self._env_positive_int(
                "BACKTEST_HEAVY_PROGRESS_PERSIST_EVERY_PAIRS",
                self._HEAVY_PROGRESS_PERSIST_EVERY_PAIRS,
            )
            heavy_every_seconds = self._env_positive_float(
                "BACKTEST_HEAVY_PROGRESS_PERSIST_EVERY_SECONDS",
                self._HEAVY_PROGRESS_PERSIST_EVERY_SECONDS,
            )
            last_heavy_persist_at = time.monotonic()
            checkpoint_payload_hash = self._request_payload_hash(request_payload)

            def _save_run_checkpoint(completed_pairs_count: int) -> None:
                if checkpoint_store is None:
                    return
                _checkpoint.save_checkpoint(
                    checkpoint_store,
                    _checkpoint.build_checkpoint(
                        run_id=run_id,
                        payload_hash=checkpoint_payload_hash,
                        pair_plan=pair_markets,
                        completed_pairs_count=completed_pairs_count,
                        trades=all_trades,
                        position_snapshots=all_snapshots,
                        daily_pnl=daily_pnl_agg,
                        running_total_pnl=running_total_pnl,
                        running_winners=running_winners,
                        running_gross_profit=running_gross_profit,
                        running_gross_loss=running_gross_loss,
                    ),
                )

            def _delete_run_checkpoint() -> None:
                if checkpoint_store is None:
                    return
                _checkpoint.delete_checkpoint(checkpoint_store, run_id)

            for idx, (m1, m2) in enumerate(pair_markets):
                if self._remaining_seconds(deadline_monotonic) <= 0:
                    raise TimeoutError("Backtest timed out while processing pairs")
                # Yield to event loop so other coroutines (e.g. API health checks)
                # are not starved during CPU-bound pair processing.
                await asyncio.sleep(0)
                run_data = await self._honor_runtime_control(
                    run_id,
                    run_data,
                    deadline_monotonic,
                    checkpoint_writer=functools.partial(_save_run_checkpoint, idx),
                )
                if resumed and idx < resumed_completed:
                    # Already captured by the checkpoint this attempt resumed
                    # from — skip its fetch + simulation entirely.
                    continue

                progress = round((idx / max(1, total_pairs)) * 95.0, 2)
                run_data["progress_pct"] = progress
                run_data["current_pair"] = f"{m1}/{m2}"
                run_data["current_task"] = "processing pair"
                run_data["updated_at"] = datetime.now(timezone.utc).isoformat()

                # Optimization: Only persist progress if it's significant or enough time passed.
                # This drastically reduces DB pressure for large backtests with many pairs.
                if async_job_manager._should_persist_progress(run_id, progress):
                    run_data = self._persist_progress_data(run_data)
                    async_job_manager.mark_progress(
                        run_id,
                        progress,
                        metadata={
                            "run_id": run_id,
                            "current_pair": run_data.get("current_pair"),
                            "current_task": run_data.get("current_task"),
                        },
                    )

                if progress_callback is not None:
                    try:
                        _elapsed = time.monotonic() - started_monotonic
                        # On checkpoint resume, skipped pairs must not inflate
                        # the throughput estimate for this attempt.
                        _pairs_done = max(1, idx - resumed_completed)
                        _eta_seconds = (
                            int((_elapsed / _pairs_done) * max(0, total_pairs - idx))
                            if _elapsed > 0 and _pairs_done > 0
                            else 0
                        )
                        await asyncio.wait_for(
                            progress_callback(
                                run_id, progress, f"{m1}/{m2}", _eta_seconds
                            ),
                            timeout=min(
                                self._PROGRESS_CALLBACK_TIMEOUT_SECONDS,
                                max(0.001, self._remaining_seconds(deadline_monotonic)),
                            ),
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Backtest progress callback timed out for run %s at %.2f%%",
                            run_id,
                            progress,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Backtest progress callback failed for run %s at %.2f%%: %s",
                            run_id,
                            progress,
                            exc,
                        )

                if m1 in market_history_cache:
                    candles_1 = market_history_cache[m1]
                else:
                    run_data = await self._honor_runtime_control(
                        run_id,
                        run_data,
                        deadline_monotonic,
                        checkpoint_writer=functools.partial(_save_run_checkpoint, idx),
                    )
                    candles_1 = await self._await_with_deadline(
                        _history._fetch_market_history(
                            client=client,
                            market=m1,
                            start_dt=start_dt,
                            end_dt=end_dt,
                            resolution=resolution,
                            deadline_monotonic=deadline_monotonic,
                            history_telemetry=history_fetch_telemetry,
                        ),
                        deadline_monotonic,
                        f"loading history for {m1}",
                    )
                    market_history_cache[m1] = candles_1

                if m2 in market_history_cache:
                    candles_2 = market_history_cache[m2]
                else:
                    run_data = await self._honor_runtime_control(
                        run_id,
                        run_data,
                        deadline_monotonic,
                        checkpoint_writer=functools.partial(_save_run_checkpoint, idx),
                    )
                    candles_2 = await self._await_with_deadline(
                        _history._fetch_market_history(
                            client=client,
                            market=m2,
                            start_dt=start_dt,
                            end_dt=end_dt,
                            resolution=resolution,
                            deadline_monotonic=deadline_monotonic,
                            history_telemetry=history_fetch_telemetry,
                        ),
                        deadline_monotonic,
                        f"loading history for {m2}",
                    )
                    market_history_cache[m2] = candles_2

                # A pause/cancel can arrive while either history request is in flight.
                # Re-check before entering the CPU-heavy simulation section so control
                # latency is bounded by one external fetch instead of a full pair run.
                run_data = await self._honor_runtime_control(
                    run_id,
                    run_data,
                    deadline_monotonic,
                    checkpoint_writer=functools.partial(_save_run_checkpoint, idx),
                )
                timestamps, p1, p2 = self._align_series(candles_1, candles_2)
                trades, snapshots, daily_pnl = await self._simulate_pair(
                    run_id=run_id,
                    market_a=m1,
                    market_b=m2,
                    timestamps=timestamps,
                    prices_a=p1,
                    prices_b=p2,
                    params=params,
                    trade_index_offset=len(all_trades),
                    heartbeat_callback=lambda: self._touch_run_heartbeat_async(run_id),
                )

                for trade in trades:
                    trade_pnl = float(trade["pnl_usd"])
                    running_total_pnl += trade_pnl
                    if bool(trade["win"]):
                        running_winners += 1
                    if trade_pnl > 0:
                        running_gross_profit += trade_pnl
                    elif trade_pnl < 0:
                        running_gross_loss += trade_pnl

                all_trades.extend(trades)
                all_snapshots.extend(snapshots)
                for day, pnl in daily_pnl.items():
                    daily_pnl_agg[day] = round(daily_pnl_agg.get(day, 0.0) + pnl, 4)

                running_total_trades = len(all_trades)
                running_win_rate = (
                    running_winners / running_total_trades
                    if running_total_trades > 0
                    else 0.0
                )
                ordered_running_daily = [
                    daily_pnl_agg[d] for d in sorted(daily_pnl_agg.keys())
                ]
                running_sharpe_ratio = self._compute_sharpe(
                    ordered_running_daily, initial_balance
                )
                running_max_drawdown_pct = self._compute_max_drawdown_pct(
                    ordered_running_daily, initial_balance
                )
                running_profit_factor = (
                    running_gross_profit / max(1e-9, abs(running_gross_loss))
                    if running_total_trades > 0
                    else 0.0
                )

                run_data.update(
                    {
                        "total_pnl": round(running_total_pnl, 4),
                        "total_trades": running_total_trades,
                        "win_rate": round(running_win_rate, 4),
                        "sharpe_ratio": round(running_sharpe_ratio, 4),
                        "max_drawdown_pct": round(running_max_drawdown_pct, 4),
                        "profit_factor": round(float(running_profit_factor), 4),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

                now_monotonic = time.monotonic()
                should_persist_heavy = (
                    idx == 0
                    or idx == resumed_completed
                    or (idx + 1) >= total_pairs
                    or ((idx + 1) % heavy_every_pairs == 0)
                    or (now_monotonic - last_heavy_persist_at) >= heavy_every_seconds
                )
                if should_persist_heavy:
                    run_data["trades"] = list(all_trades)
                    run_data["position_snapshots"] = list(all_snapshots)
                    run_data["daily_pnl"] = self._build_daily_pnl_rows(
                        daily_pnl_agg=daily_pnl_agg,
                        all_trades=all_trades,
                        resolution=resolution,
                    )
                    last_heavy_persist_at = now_monotonic

                    run_data = self._attach_history_fetch_summary(
                        run_data,
                        history_fetch_telemetry,
                    )
                    run_data = self._persist_run_data(run_data)
                    # Durable resume point: everything through pair ``idx`` is
                    # complete and persisted, so a retry/redelivery can skip it.
                    _save_run_checkpoint(idx + 1)

                # Yield control so other coroutines (status polling) run smoothly.
                await asyncio.sleep(0)

            total_pnl = float(running_total_pnl)
            total_trades = len(all_trades)
            win_rate = running_winners / total_trades if total_trades > 0 else 0.0
            profit_factor = (
                running_gross_profit / max(1e-9, abs(running_gross_loss))
                if total_trades > 0
                else 0.0
            )

            ordered_daily = [daily_pnl_agg[d] for d in sorted(daily_pnl_agg.keys())]
            sharpe_ratio = self._compute_sharpe(ordered_daily, initial_balance)
            max_drawdown_pct = self._compute_max_drawdown_pct(
                ordered_daily, initial_balance
            )

            finished_at = datetime.now(timezone.utc).isoformat()
            run_data.update(
                {
                    "status": "completed",
                    "progress_pct": 100.0,
                    "current_pair": "complete",
                    "current_task": "complete",
                    "total_pnl": round(total_pnl, 4),
                    "win_rate": round(win_rate, 4),
                    "sharpe_ratio": round(sharpe_ratio, 4),
                    "max_drawdown_pct": round(max_drawdown_pct, 4),
                    "total_trades": total_trades,
                    "profit_factor": round(float(profit_factor), 4),
                    "trades": all_trades,
                    "position_snapshots": all_snapshots,
                    "daily_pnl": self._build_daily_pnl_rows(
                        daily_pnl_agg=daily_pnl_agg,
                        all_trades=all_trades,
                        resolution=resolution,
                    ),
                    "error": None,
                    "error_message": None,
                    "finished_at": finished_at,
                    "completed_at": finished_at,
                    "updated_at": finished_at,
                }
            )
            run_data = self._attach_history_fetch_summary(
                run_data,
                history_fetch_telemetry,
            )
            run_data["request"] = self._clear_task_failure(
                dict(run_data.get("request") or {})
            )
            run_data = self._set_runtime_control(
                run_data,
                status="completed",
                action="complete",
                pause_requested=False,
                resume_requested=False,
                cancel_requested=False,
                worker_backend=run_data.get("worker_backend") or "asyncio",
                worker_task_id=run_data.get("worker_task_id") or run_id,
            )
            run_data = self._persist_run_data(run_data)
            async_job_manager.mark_completed(
                run_id,
                result={
                    "status": "completed",
                    "total_trades": total_trades,
                    "total_pnl": round(total_pnl, 4),
                },
            )
            # Terminal success: the checkpoint has no further resume value.
            _delete_run_checkpoint()

            if progress_callback is not None:
                try:
                    await asyncio.wait_for(
                        progress_callback(run_id, 100.0, "complete", 0),
                        timeout=self._PROGRESS_CALLBACK_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Backtest final progress callback timed out for run %s", run_id
                    )
                except Exception as exc:
                    logger.warning(
                        "Backtest final progress callback failed for run %s: %s",
                        run_id,
                        exc,
                    )

        except asyncio.CancelledError:
            failure_payload = {
                "error_code": "BACKTEST_CANCELLED",
                "error_message": "Backtest cancelled",
                "traceback": None,
            }
            run_data["request"] = self._set_task_failure(
                dict(run_data.get("request") or {}),
                failure_payload,
            )
            run_data = self._set_runtime_control(
                run_data,
                status="cancelled",
                action="cancel",
                pause_requested=False,
                resume_requested=False,
                cancel_requested=True,
                worker_backend=run_data.get("worker_backend") or "asyncio",
                worker_task_id=run_data.get("worker_task_id") or run_id,
            )
            finished_at = datetime.now(timezone.utc).isoformat()
            run_data.update(
                {
                    "status": "cancelled",
                    "progress_pct": run_data.get("progress_pct", 0.0),
                    "current_pair": None,
                    "current_task": "cancelled",
                    "error": "Backtest cancelled",
                    "error_message": "Backtest cancelled",
                    "finished_at": finished_at,
                    "completed_at": finished_at,
                    "updated_at": finished_at,
                }
            )
            run_data = self._attach_history_fetch_summary(
                run_data,
                history_fetch_telemetry,
            )
            run_data = self._persist_run_data(run_data)
            async_job_manager.mark_cancelled(run_id, reason="Backtest cancelled")
            # Operator-intentional terminal state — drop the resume point.
            _delete_run_checkpoint()
            if propagate_exceptions:
                raise
        except TimeoutError as exc:
            error_message = str(exc) or "Backtest timed out"
            failure_payload = {
                "error_code": self._error_code_from_message(
                    error_message, "BACKTEST_TIMEOUT"
                ),
                "error_message": error_message,
                "traceback": traceback_module.format_exc(),
            }
            run_data["request"] = self._set_task_failure(
                dict(run_data.get("request") or {}),
                failure_payload,
            )
            run_data = self._set_runtime_control(
                run_data,
                status="timeout",
                action="timeout",
                pause_requested=False,
                resume_requested=False,
                cancel_requested=False,
                worker_backend=run_data.get("worker_backend") or "asyncio",
                worker_task_id=run_data.get("worker_task_id") or run_id,
            )
            finished_at = datetime.now(timezone.utc).isoformat()
            run_data.update(
                {
                    "status": "timeout",
                    "current_task": "timeout",
                    "error": error_message,
                    "error_message": error_message,
                    "finished_at": finished_at,
                    "completed_at": finished_at,
                    "updated_at": finished_at,
                }
            )
            run_data = self._attach_history_fetch_summary(
                run_data,
                history_fetch_telemetry,
            )
            run_data = self._persist_progress_data(run_data)
            async_job_manager.mark_failed(run_id, error_message)
            if propagate_exceptions:
                raise
        except Exception as exc:
            error_message = str(exc)
            failure_payload = {
                "error_code": self._error_code_from_message(
                    error_message, "BACKTEST_EXECUTION_FAILED"
                ),
                "error_message": error_message,
                "traceback": traceback_module.format_exc(),
            }
            run_data["request"] = self._set_task_failure(
                dict(run_data.get("request") or {}),
                failure_payload,
            )
            run_data = self._set_runtime_control(
                run_data,
                status="failed",
                action="fail",
                pause_requested=False,
                resume_requested=False,
                cancel_requested=False,
                worker_backend=run_data.get("worker_backend") or "asyncio",
                worker_task_id=run_data.get("worker_task_id") or run_id,
            )
            finished_at = datetime.now(timezone.utc).isoformat()
            run_data.update(
                {
                    "status": "failed",
                    "current_task": "failed",
                    "error": error_message,
                    "error_message": error_message,
                    "finished_at": finished_at,
                    "completed_at": finished_at,
                    "updated_at": finished_at,
                }
            )
            run_data = self._attach_history_fetch_summary(
                run_data,
                history_fetch_telemetry,
            )
            run_data = self._persist_progress_data(run_data)
            async_job_manager.mark_failed(run_id, error_message)
            if propagate_exceptions:
                raise
        finally:
            heartbeat_stop_event.set()
            if heartbeat_thread is not None and heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=2.0)
            self._tasks.pop(run_id, None)
            if client is not None:
                try:
                    await client.node.close()
                except Exception:
                    pass

    async def create_and_run_backtest(
        self,
        request: Any,
        progress_callback: Any = None,
    ) -> _BacktestRunDetails:
        """Create a backtest run and execute asynchronously using historical market data."""
        now = datetime.now(timezone.utc).isoformat()
        run_id = f"run-{uuid4().hex[:12]}"
        request_payload = self._extract_request_payload(request)
        request_payload = self._clear_task_failure(request_payload)
        request_payload = self._set_task_context(
            request_payload,
            self._build_task_context(request_payload),
        )

        start_date = getattr(request, "start_date", None) or request_payload.get(
            "start_date", ""
        )
        end_date = getattr(request, "end_date", None) or request_payload.get(
            "end_date", ""
        )
        name = (
            getattr(request, "name", None)
            or request_payload.get("name")
            or "unnamed-backtest"
        )

        worker_backend = await self._resolve_worker_backend()
        run_data: Dict[str, Any] = {
            "run_id": run_id,
            "name": name,
            "status": "pending",
            "progress_pct": 0.0,
            "current_pair": "pending",
            "current_task": "pending",
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "total_trades": 0,
            "start_date": str(start_date) if start_date else "",
            "end_date": str(end_date) if end_date else "",
            "profit_factor": 0.0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "deadline_at": (
                datetime.now(timezone.utc)
                + timedelta(seconds=self._parse_timeout_seconds(request_payload))
            ).isoformat(),
            "timeout_seconds": self._parse_timeout_seconds(request_payload),
            "updated_at": now,
            "error": None,
            "error_message": None,
            "request": request_payload,
            "trades": [],
            "position_snapshots": [],
            "daily_pnl": [],
            "cancel_requested": False,
            "control_status": "pending",
            "control_action": "create",
            "worker_backend": worker_backend,
            "worker_task_id": run_id,
        }
        run_data = self._set_runtime_control(
            run_data,
            status="pending",
            action="create",
            pause_requested=False,
            resume_requested=False,
            cancel_requested=False,
            worker_backend=worker_backend,
            worker_task_id=run_id,
            created_at=now,
        )
        run_data = self._persist_run_data(run_data)

        if worker_backend == "celery":
            try:
                task_id = self._enqueue_celery_backtest(
                    run_id,
                    self._build_task_context(request_payload),
                )
                run_data = self._set_runtime_control(
                    run_data,
                    status="pending",
                    action="enqueue",
                    pause_requested=False,
                    resume_requested=False,
                    cancel_requested=False,
                    worker_backend="celery",
                    worker_task_id=task_id,
                )
                run_data["status"] = "pending"
                run_data["current_task"] = "queued"
                run_data["worker_backend"] = "celery"
                run_data["worker_task_id"] = task_id
                run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                run_data = self._persist_run_data(run_data)
                return _BacktestRunDetails(**self._resolve_stale_run_data(run_data))
            except Exception as exc:
                logger.exception(
                    "Celery enqueue failed for run %s; marking failed",
                    run_id,
                )
                run_data = self._mark_celery_enqueue_failed(run_data, exc)
                raise BacktestEnqueueError(
                    f"Failed to enqueue backtest '{run_id}' on Celery: {exc}"
                ) from exc

        if worker_backend == "nats":
            # JetStream-authoritative mode: the run is persisted; execution is
            # driven by the backend-published backtest.command.start consumed by
            # the NATS worker (WORKER_MODE=nats). Do NOT enqueue Celery or run
            # asyncio here — that would double-execute. The run stays "pending"
            # until the NATS consumer claims it.
            run_data = self._set_runtime_control(
                run_data,
                status="pending",
                action="enqueue",
                pause_requested=False,
                resume_requested=False,
                cancel_requested=False,
                worker_backend="nats",
                worker_task_id=run_id,
            )
            run_data["status"] = "pending"
            run_data["current_task"] = "queued"
            run_data["worker_backend"] = "nats"
            run_data["worker_task_id"] = run_id
            run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            run_data = self._persist_run_data(run_data)
            logger.info(
                "Backtest %s persisted for NATS (JetStream) execution; "
                "waiting for backtest.command.start consumer",
                run_id,
            )
            return _BacktestRunDetails(**self._resolve_stale_run_data(run_data))

        task = async_job_manager.create_supervised_task(
            self._execute_backtest(
                run_id=run_id,
                request_payload=request_payload,
                progress_callback=progress_callback,
            ),
            job_type="backtest",
            job_id=run_id,
            parameters=request_payload,
            metadata={
                "run_id": run_id,
                "worker_backend": "asyncio",
                "start_date": str(start_date) if start_date else "",
                "end_date": str(end_date) if end_date else "",
            },
            auto_complete=False,
        )
        self._tasks[run_id] = task
        task.add_done_callback(
            lambda completed_task: self._handle_task_done(run_id, completed_task)
        )
        run_data["status"] = "running"
        run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        run_data = self._persist_run_data(run_data)

        return _BacktestRunDetails(**run_data)

    def _handle_task_done(self, run_id: str, task: asyncio.Task[None]) -> None:
        self._tasks.pop(run_id, None)
        if task.cancelled():
            return
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            logger.error(
                "Backtest task %s exited with unhandled exception",
                run_id,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    def list_backtest_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
        days_filter: Optional[int] = None,
    ) -> _BacktestRunList:
        runs = self.repository.list_runs(
            limit=limit,
            offset=offset,
            status_filter=status_filter,
            days_filter=days_filter,
        )
        runs = [self._resolve_stale_run_data(run) for run in runs]
        total = self.repository.count_runs(
            statuses=[status_filter] if status_filter else None,
            days_filter=days_filter,
        )
        return _BacktestRunList(runs=runs, total=total)
