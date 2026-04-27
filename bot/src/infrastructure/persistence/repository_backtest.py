"""Repository classes for durable backtest operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session, defer

from internal.domain.models import BacktestRun


class BacktestRepository:
    """Repository for backtest operations."""

    _memory_runs: Dict[str, Dict[str, Any]] = {}

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
    def _parse_dt(value: Any, *, default: Optional[datetime] = None) -> Optional[datetime]:
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

    @classmethod
    def _record_to_dict(cls, record: BacktestRun) -> Dict[str, Any]:
        return {
            **cls._record_to_summary_dict(record),
            "request": dict(record.request_json or {}),
            "trades": list(record.trades_json or []),
            "position_snapshots": list(record.position_snapshots_json or []),
            "daily_pnl": list(record.daily_pnl_json or []),
        }

    def save_run(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._normalize_run_data(run_data)
        run_id = str(payload["run_id"])

        if self.session is None:
            BacktestRepository._memory_runs[run_id] = payload
            return dict(payload)

        record = (
            self.session.query(BacktestRun)
            .filter(BacktestRun.run_id == run_id)
            .first()
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
        record.max_drawdown_pct = float(
            payload.get("max_drawdown_pct", 0.0) or 0.0
        )
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
        record.created_at = self._parse_dt(payload.get("created_at"), default=self._now())
        record.started_at = self._parse_dt(payload.get("started_at"))
        record.completed_at = self._parse_dt(
            payload.get("completed_at") or payload.get("finished_at")
        )
        record.deadline_at = self._parse_dt(payload.get("deadline_at"))
        record.timeout_seconds = (
            float(payload.get("timeout_seconds"))
            if payload.get("timeout_seconds") is not None
            else None
        )
        record.updated_at = self._parse_dt(payload.get("updated_at"), default=self._now())

        self.session.commit()
        self.session.refresh(record)
        return self._record_to_dict(record)

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
            runs = sorted(runs, key=lambda row: str(row.get("updated_at", "")), reverse=True)
            if limit is None:
                return [dict(row) for row in runs[offset:]]
            return [dict(row) for row in runs[offset: offset + limit]]

        query = (
            self.session.query(BacktestRun)
            .options(
                defer(BacktestRun.request_json),
                defer(BacktestRun.trades_json),
                defer(BacktestRun.position_snapshots_json),
                defer(BacktestRun.daily_pnl_json),
            )
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
            return BacktestRepository._memory_runs.pop(normalized_run_id, None) is not None

        record = (
            self.session.query(BacktestRun)
            .filter(BacktestRun.run_id == normalized_run_id)
            .first()
        )
        if record is None:
            return False
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
