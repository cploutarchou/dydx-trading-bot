"""Repository classes for durable backtest operations."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from internal.domain.models import BacktestRun, BacktestRunRequestPayload
from sqlalchemy.exc import OperationalError, PendingRollbackError
from sqlalchemy.orm import Session, defer


class BacktestRepository:
    """Repository for backtest operations."""

    _memory_runs: Dict[str, Dict[str, Any]] = {}
    _memory_request_snapshots: Dict[str, Dict[str, Any]] = {}

    def __init__(self, session: Optional[Session]):
        self.session = session

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _serialize_dt(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return str(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    @staticmethod
    def _parse_dt(
        value: Any, *, default: Optional[datetime] = None
    ) -> Optional[datetime]:
        if value is None or value == "":
            return default
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return default
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @classmethod
    def _normalize_run_data(cls, run_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(run_data)
        now = cls._now().isoformat()
        payload.setdefault("status", "pending")
        payload.setdefault("progress_pct", 0.0)
        payload.setdefault("current_pair", None)
        payload.setdefault("current_task", None)
        payload.setdefault("total_pnl", 0.0)
        payload.setdefault("win_rate", 0.0)
        payload.setdefault("sharpe_ratio", 0.0)
        payload.setdefault("max_drawdown_pct", 0.0)
        payload.setdefault("total_trades", 0)
        payload.setdefault("profit_factor", 0.0)
        payload.setdefault("start_date", "")
        payload.setdefault("end_date", "")
        payload.setdefault("error", None)
        payload.setdefault("error_message", None)
        payload.setdefault("request", {})
        payload.setdefault("trades", [])
        payload.setdefault("position_snapshots", [])
        payload.setdefault("daily_pnl", [])
        payload.setdefault("cancel_requested", False)
        payload.setdefault("created_at", now)
        payload.setdefault("started_at", None)
        payload.setdefault("completed_at", payload.get("finished_at"))
        payload.setdefault("finished_at", payload.get("completed_at"))
        payload.setdefault("deadline_at", None)
        payload.setdefault("timeout_seconds", None)
        payload.setdefault("updated_at", now)
        payload["created_at"] = cls._serialize_dt(payload.get("created_at")) or now
        payload["started_at"] = cls._serialize_dt(payload.get("started_at"))
        payload["completed_at"] = cls._serialize_dt(
            payload.get("completed_at") or payload.get("finished_at")
        )
        payload["finished_at"] = cls._serialize_dt(
            payload.get("finished_at") or payload.get("completed_at")
        )
        payload["deadline_at"] = cls._serialize_dt(payload.get("deadline_at"))
        payload["updated_at"] = cls._serialize_dt(payload.get("updated_at")) or now
        return payload

    @staticmethod
    def _sanitize_request_payload(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        cleaned = dict(payload)
        cleaned.pop("_runtime_control", None)
        return cleaned

    @staticmethod
    def _is_retryable_run_write_error(exc: OperationalError) -> bool:
        orig = getattr(exc, "orig", None)
        args = getattr(orig, "args", ()) or ()
        code = args[0] if args else None
        message = str(orig or exc)
        return code in {1020, 1205, 1213} or (
            "Record has changed since last read" in message
        )

    def _retry_with_backoff(
        self,
        operation: Any,
        *args: Any,
        max_attempts: int = 5,
        initial_backoff_ms: float = 10.0,
        **kwargs: Any,
    ) -> Any:
        """
        Retry operation with exponential backoff for transient database errors.

        Handles MySQL concurrency errors (1020, 1205, 1213) which can occur when
        heartbeat updates and progress updates collide on the same row.

        Args:
            operation: Callable to retry
            max_attempts: Maximum retry attempts (default 5)
            initial_backoff_ms: Initial backoff in milliseconds (default 10ms)
            *args, **kwargs: Arguments to pass to operation

        Returns:
            Result of operation

        Raises:
            OperationalError: If all retries exhausted or non-retryable error
        """
        backoff_ms = initial_backoff_ms
        last_exc = None

        for attempt in range(max_attempts):
            try:
                return operation(*args, **kwargs)
            except PendingRollbackError as exc:
                last_exc = exc
                if self.session is not None:
                    self.session.rollback()
                if attempt >= max_attempts - 1:
                    raise

                time.sleep(backoff_ms / 1000.0)
                backoff_ms = min(backoff_ms * 2, 250)  # Cap at 250ms
            except OperationalError as exc:
                last_exc = exc
                if self.session is not None:
                    self.session.rollback()
                if attempt >= max_attempts - 1:
                    # Last attempt exhausted
                    raise
                if not BacktestRepository._is_retryable_run_write_error(exc):
                    # Not a retryable error
                    raise

                # Exponential backoff: 10ms, 20ms, 40ms, 80ms, 160ms
                time.sleep(backoff_ms / 1000.0)
                backoff_ms = min(backoff_ms * 2, 250)  # Cap at 250ms

        raise last_exc or RuntimeError("unreachable retry state")

    @classmethod
    def _record_to_summary_dict(cls, record: BacktestRun) -> Dict[str, Any]:
        """Lightweight projection used for list queries — omits large JSON blob columns."""
        return {
            "run_id": record.run_id,
            "name": record.name,
            "status": record.status,
            "progress_pct": float(record.progress_pct or 0.0),
            "current_pair": record.current_pair,
            "current_task": record.current_task,
            "total_pnl": float(record.total_pnl or 0.0),
            "win_rate": float(record.win_rate or 0.0),
            "sharpe_ratio": float(record.sharpe_ratio or 0.0),
            "max_drawdown_pct": float(record.max_drawdown_pct or 0.0),
            "total_trades": int(record.total_trades or 0),
            "profit_factor": float(record.profit_factor or 0.0),
            "start_date": record.start_date or "",
            "end_date": record.end_date or "",
            "error": record.error,
            "error_message": record.error_message,
            "cancel_requested": bool(record.cancel_requested),
            "created_at": cls._serialize_dt(record.created_at),
            "started_at": cls._serialize_dt(record.started_at),
            "completed_at": cls._serialize_dt(record.completed_at),
            "finished_at": cls._serialize_dt(record.completed_at),
            "deadline_at": cls._serialize_dt(record.deadline_at),
            "timeout_seconds": (
                float(record.timeout_seconds)
                if record.timeout_seconds is not None
                else None
            ),
            "updated_at": cls._serialize_dt(record.updated_at),
        }

    def _record_to_dict(self, record: BacktestRun) -> Dict[str, Any]:
        request_payload = dict(record.request_json or {})
        if not request_payload:
            request_payload = self._get_request_snapshot(record.run_id)
        return {
            **self._record_to_summary_dict(record),
            "request": request_payload,
            "trades": list(record.trades_json or []),
            "position_snapshots": list(record.position_snapshots_json or []),
            "daily_pnl": list(record.daily_pnl_json or []),
        }

    def _record_to_overview_dict(self, record: BacktestRun) -> Dict[str, Any]:
        request_payload = dict(record.request_json or {})
        if not request_payload:
            request_payload = self._get_request_snapshot(record.run_id)
        return {
            **self._record_to_summary_dict(record),
            "request": request_payload,
        }

    def _upsert_request_snapshot(self, run_id: str, request_payload: Any) -> None:
        cleaned = self._sanitize_request_payload(request_payload)
        if not cleaned:
            return

        if self.session is None:
            BacktestRepository._memory_request_snapshots[run_id] = cleaned
            return

        snapshot = (
            self.session.query(BacktestRunRequestPayload)
            .filter(BacktestRunRequestPayload.run_id == run_id)
            .first()
        )
        if snapshot is None:
            snapshot = BacktestRunRequestPayload(run_id=run_id)
            self.session.add(snapshot)

        # Immutable-ish snapshot semantics: only fill if missing.
        if not dict(snapshot.request_json or {}):
            snapshot.request_json = cleaned

    def _get_request_snapshot(self, run_id: str) -> Dict[str, Any]:
        if self.session is None:
            return dict(BacktestRepository._memory_request_snapshots.get(run_id) or {})

        snapshot = (
            self.session.query(BacktestRunRequestPayload)
            .filter(BacktestRunRequestPayload.run_id == run_id)
            .first()
        )
        if snapshot is None:
            return {}
        return dict(snapshot.request_json or {})

    def save_run(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._normalize_run_data(run_data)
        run_id = str(payload["run_id"])
        incoming_request_payload = (
            run_data.get("request") if isinstance(run_data, dict) else None
        )

        if self.session is None:
            cleaned_request = self._sanitize_request_payload(incoming_request_payload)
            if cleaned_request:
                BacktestRepository._memory_request_snapshots[run_id] = cleaned_request
            BacktestRepository._memory_runs[run_id] = payload
            return dict(payload)

        return self._retry_with_backoff(
            self._save_run_once,
            payload=payload,
            run_id=run_id,
            incoming_request_payload=incoming_request_payload,
            max_attempts=5,
        )

    def _save_run_once(
        self,
        *,
        payload: Dict[str, Any],
        run_id: str,
        incoming_request_payload: Any,
    ) -> Dict[str, Any]:
        record = (
            self.session.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
        )
        if record is None:
            record = BacktestRun(run_id=run_id)
            self.session.add(record)

        record.name = str(payload.get("name") or "unnamed-backtest")
        record.status = str(payload.get("status") or "pending")
        record.progress_pct = float(payload.get("progress_pct", 0.0) or 0.0)
        record.current_pair = payload.get("current_pair")
        record.current_task = payload.get("current_task")
        record.total_pnl = float(payload.get("total_pnl", 0.0) or 0.0)
        record.win_rate = float(payload.get("win_rate", 0.0) or 0.0)
        record.sharpe_ratio = float(payload.get("sharpe_ratio", 0.0) or 0.0)
        record.max_drawdown_pct = float(payload.get("max_drawdown_pct", 0.0) or 0.0)
        record.total_trades = int(payload.get("total_trades", 0) or 0)
        record.profit_factor = float(payload.get("profit_factor", 0.0) or 0.0)
        record.start_date = str(payload.get("start_date") or "")
        record.end_date = str(payload.get("end_date") or "")
        record.error = payload.get("error")
        record.error_message = payload.get("error_message")
        record.request_json = payload.get("request") or {}
        record.trades_json = payload.get("trades") or []
        record.position_snapshots_json = payload.get("position_snapshots") or []
        record.daily_pnl_json = payload.get("daily_pnl") or []
        record.cancel_requested = bool(payload.get("cancel_requested", False))
        parsed_created_at = self._parse_dt(
            payload.get("created_at"), default=self._now()
        )
        record.created_at = parsed_created_at or self._now()
        record.started_at = self._parse_dt(payload.get("started_at"))
        record.completed_at = self._parse_dt(
            payload.get("completed_at") or payload.get("finished_at")
        )
        record.deadline_at = self._parse_dt(payload.get("deadline_at"))
        timeout_seconds_value = payload.get("timeout_seconds")
        record.timeout_seconds = (
            float(timeout_seconds_value) if timeout_seconds_value is not None else None
        )
        parsed_updated_at = self._parse_dt(
            payload.get("updated_at"), default=self._now()
        )
        record.updated_at = parsed_updated_at or self._now()

        self._upsert_request_snapshot(run_id, incoming_request_payload)

        self.session.commit()
        self.session.refresh(record)
        return self._record_to_dict(record)

    def touch_run(self, run_id: str, updated_at: Optional[str] = None) -> bool:
        """Refresh only the heartbeat timestamp for an existing run."""
        normalized_run_id = str(run_id)
        timestamp = updated_at or self._now().isoformat()

        if self.session is None:
            record = BacktestRepository._memory_runs.get(normalized_run_id)
            if record is None:
                return False
            record["updated_at"] = timestamp
            BacktestRepository._memory_runs[normalized_run_id] = record
            return True

        def _touch_once() -> bool:
            record: Any = (
                self.session.query(BacktestRun)
                .filter(BacktestRun.run_id == normalized_run_id)
                .first()
            )
            if record is None:
                return False

            parsed_updated_at = self._parse_dt(timestamp, default=self._now())
            record.updated_at = parsed_updated_at or self._now()
            self.session.commit()
            return True

        try:
            return self._retry_with_backoff(_touch_once, max_attempts=5)
        except OperationalError:
            self.session.rollback()
            raise

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        normalized_run_id = str(run_id)
        if self.session is None:
            record = BacktestRepository._memory_runs.get(normalized_run_id)
            return dict(record) if record else None

        record = (
            self.session.query(BacktestRun)
            .filter(BacktestRun.run_id == normalized_run_id)
            .first()
        )
        return self._record_to_dict(record) if record else None

    def get_run_overview(self, run_id: str) -> Optional[Dict[str, Any]]:
        normalized_run_id = str(run_id)
        if self.session is None:
            record = BacktestRepository._memory_runs.get(normalized_run_id)
            if not record:
                return None
            payload = self._normalize_run_data(record)
            return {
                **payload,
                # Internal overview consumers need runtime-control fields for
                # pause/resume/cancel reconciliation, matching the DB-backed path.
                "request": dict(payload.get("request") or {}),
            }

        record = (
            self.session.query(BacktestRun)
            .options(
                defer(BacktestRun.trades_json),
                defer(BacktestRun.position_snapshots_json),
                defer(BacktestRun.daily_pnl_json),
            )
            .filter(BacktestRun.run_id == normalized_run_id)
            .first()
        )
        return self._record_to_overview_dict(record) if record else None

    def list_run_overviews(
        self,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return monitor-safe runs in one query without loading result JSON blobs.

        Celery monitoring needs request/task context, but never the potentially large
        trade, position-snapshot, or daily-PnL payloads.  Joining the normalized
        request snapshot here avoids the previous list-then-get N+1 query pattern.
        """
        if self.session is None:
            runs = sorted(
                BacktestRepository._memory_runs.values(),
                key=lambda row: str(row.get("updated_at", "")),
                reverse=True,
            )
            selected = (
                runs[offset:] if limit is None else runs[offset : offset + limit]
            )
            overviews: List[Dict[str, Any]] = []
            for row in selected:
                payload = self._normalize_run_data(dict(row))
                request_payload = dict(payload.get("request") or {})
                if not request_payload:
                    request_payload = dict(
                        BacktestRepository._memory_request_snapshots.get(
                            str(payload.get("run_id") or "")
                        )
                        or {}
                    )
                overviews.append(
                    {
                        **{
                            key: value
                            for key, value in payload.items()
                            if key
                            not in {
                                "request",
                                "trades",
                                "position_snapshots",
                                "daily_pnl",
                            }
                        },
                        "request": request_payload,
                    }
                )
            return overviews

        query = (
            self.session.query(
                BacktestRun,
                BacktestRunRequestPayload.request_json.label("snapshot_request_json"),
            )
            .outerjoin(
                BacktestRunRequestPayload,
                BacktestRunRequestPayload.run_id == BacktestRun.run_id,
            )
            .options(
                defer(BacktestRun.trades_json),
                defer(BacktestRun.position_snapshots_json),
                defer(BacktestRun.daily_pnl_json),
            )
            .order_by(BacktestRun.updated_at.desc())
        )
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        overviews = []
        for record, snapshot_request_json in query.all():
            request_payload = dict(record.request_json or {})
            if not request_payload:
                request_payload = dict(snapshot_request_json or {})
            overviews.append(
                {
                    **self._record_to_summary_dict(record),
                    "request": request_payload,
                }
            )
        return overviews

    def update_run_progress(self, run_data: Dict[str, Any]) -> bool:
        """Persist lightweight progress/metric fields without rewriting JSON results."""
        run_id = str(run_data.get("run_id") or "").strip()
        if not run_id:
            return False

        scalar_updates = {
            "status": str(run_data.get("status") or "running"),
            "progress_pct": float(run_data.get("progress_pct", 0.0) or 0.0),
            "current_pair": run_data.get("current_pair"),
            "current_task": run_data.get("current_task"),
            "total_pnl": float(run_data.get("total_pnl", 0.0) or 0.0),
            "win_rate": float(run_data.get("win_rate", 0.0) or 0.0),
            "sharpe_ratio": float(run_data.get("sharpe_ratio", 0.0) or 0.0),
            "max_drawdown_pct": float(
                run_data.get("max_drawdown_pct", 0.0) or 0.0
            ),
            "total_trades": int(run_data.get("total_trades", 0) or 0),
            "profit_factor": float(run_data.get("profit_factor", 0.0) or 0.0),
            "updated_at": self._parse_dt(
                run_data.get("updated_at"), default=self._now()
            )
            or self._now(),
        }

        if self.session is None:
            record = BacktestRepository._memory_runs.get(run_id)
            if record is None:
                return False
            record.update(scalar_updates)
            record["updated_at"] = self._serialize_dt(record.get("updated_at"))
            return True

        def _update_once() -> bool:
            updated = (
                self.session.query(BacktestRun)
                .filter(BacktestRun.run_id == run_id)
                .update(scalar_updates, synchronize_session=False)
            )
            self.session.commit()
            return bool(updated)

        try:
            return self._retry_with_backoff(_update_once, max_attempts=5)
        except OperationalError:
            self.session.rollback()
            raise

    def list_runs(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        status_filter: Optional[str] = None,
        days_filter: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if self.session is None:
            runs = list(BacktestRepository._memory_runs.values())
            if status_filter:
                runs = [r for r in runs if str(r.get("status")) == status_filter]
            if days_filter is not None:
                cutoff = self._now() - timedelta(days=int(days_filter))
                runs = [
                    r
                    for r in runs
                    if (self._parse_dt(r.get("created_at")) or self._now()) >= cutoff
                ]
            runs = sorted(
                runs, key=lambda row: str(row.get("updated_at", "")), reverse=True
            )
            if limit is None:
                return [dict(row) for row in runs[offset:]]
            return [dict(row) for row in runs[offset : offset + limit]]

        query = self.session.query(BacktestRun).options(
            defer(BacktestRun.request_json),
            defer(BacktestRun.trades_json),
            defer(BacktestRun.position_snapshots_json),
            defer(BacktestRun.daily_pnl_json),
        )
        if status_filter:
            query = query.filter(BacktestRun.status == status_filter)
        if days_filter is not None:
            cutoff = self._now() - timedelta(days=int(days_filter))
            query = query.filter(BacktestRun.created_at >= cutoff)

        query = query.order_by(BacktestRun.updated_at.desc())
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return [self._record_to_summary_dict(record) for record in query.all()]

    def delete_run(self, run_id: str) -> bool:
        normalized_run_id = str(run_id)
        if self.session is None:
            BacktestRepository._memory_request_snapshots.pop(normalized_run_id, None)
            return (
                BacktestRepository._memory_runs.pop(normalized_run_id, None) is not None
            )

        record = (
            self.session.query(BacktestRun)
            .filter(BacktestRun.run_id == normalized_run_id)
            .first()
        )
        if record is None:
            return False

        snapshot = (
            self.session.query(BacktestRunRequestPayload)
            .filter(BacktestRunRequestPayload.run_id == normalized_run_id)
            .first()
        )
        if snapshot is not None:
            self.session.delete(snapshot)
        self.session.delete(record)
        self.session.commit()
        return True

    def count_runs(
        self,
        *,
        statuses: Optional[Sequence[str]] = None,
        days_filter: Optional[int] = None,
    ) -> int:
        if self.session is None:
            runs = self.list_runs(limit=None, offset=0, days_filter=days_filter)
            if statuses:
                normalized = set(statuses)
                runs = [r for r in runs if str(r.get("status")) in normalized]
            return len(runs)

        query = self.session.query(BacktestRun)
        if statuses:
            query = query.filter(BacktestRun.status.in_(list(statuses)))
        if days_filter is not None:
            cutoff = self._now() - timedelta(days=int(days_filter))
            query = query.filter(BacktestRun.created_at >= cutoff)
        return int(query.count())
