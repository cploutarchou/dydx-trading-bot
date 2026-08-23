"""
Repository classes for core bot operations
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from internal.domain.models import (
    Bot,
    BotStatusEnum,
    Event,
    Job,
    JobStatusEnum,
    Strategy,
    StrategyVersion,
    Trade,
    TradeStatusEnum,
)
from src.infrastructure.storage import (
    AnalyticsWriter,
    ClickHouseAnalyticsWriter,
    NoopAnalyticsWriter,
)
from src.shared.time_utils import utc_now

logger = logging.getLogger(__name__)


def _resolve_bot_instance_id(session: Session, bot_id: Any) -> str:
    try:
        normalized_bot_id = int(bot_id)
    except (TypeError, ValueError):
        return ""

    try:
        bot = session.query(Bot).filter(Bot.id == normalized_bot_id).first()
    except Exception:
        return ""

    return str(getattr(bot, "instance_id", "") or "")


def _build_clickhouse_analytics_writer(purpose: str) -> AnalyticsWriter:
    try:
        from config.config import config as load_runtime_config

        runtime_config = load_runtime_config()
        clickhouse = getattr(runtime_config, "clickhouse", None)
        if clickhouse is None or not getattr(clickhouse, "enabled", False):
            return NoopAnalyticsWriter()

        return ClickHouseAnalyticsWriter(
            enabled=True,
            database=str(getattr(clickhouse, "database", "default") or "default"),
            host=str(getattr(clickhouse, "host", "localhost") or "localhost"),
            port=int(getattr(clickhouse, "port", 8123) or 8123),
            username=str(getattr(clickhouse, "user", "default") or "default"),
            password=str(getattr(clickhouse, "password", "") or ""),
            secure=bool(getattr(clickhouse, "secure", False)),
            extra_config={
                "batch_size": int(getattr(clickhouse, "batch_size", 1000) or 1000),
                "flush_interval_seconds": float(
                    getattr(clickhouse, "flush_interval_seconds", 5.0) or 5.0
                ),
            },
        )
    except Exception as exc:
        logger.warning(
            "Failed to initialize %s ClickHouse writer; using noop fallback: %s",
            purpose,
            exc,
        )
        return NoopAnalyticsWriter()


class BotRepository:
    """Repository for bot operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_bot(
        self, instance_id: str, network: str, strategy: str, config: dict[str, Any]
    ) -> Bot:
        """Create a new bot"""
        bot = Bot(
            instance_id=instance_id,
            network=network,
            strategy=strategy,
            config=config,
        )
        self.session.add(bot)
        self.session.commit()
        return bot

    def get_by_instance_id(self, instance_id: str) -> Bot | None:
        """Get bot by instance ID"""
        return self.session.query(Bot).filter(Bot.instance_id == instance_id).first()

    def get_all(self) -> list[Bot]:
        """Get all bots"""
        return self.session.query(Bot).all()

    def update_status(
        self, instance_id: str, status: BotStatusEnum, process_id: Optional[int] = None
    ) -> None:
        """Update bot status"""
        bot = self.get_by_instance_id(instance_id)
        if bot:
            bot.status = status
            bot.process_id = process_id
            self.session.commit()

    def delete_bot(self, instance_id: str) -> None:
        """Delete a bot"""
        bot = self.get_by_instance_id(instance_id)
        if bot:
            self.session.delete(bot)
            self.session.commit()

    def get_statistics(self, instance_id: str) -> dict[str, Any]:
        """Get statistics for a bot"""
        bot = self.get_by_instance_id(instance_id)
        if not bot:
            return {}

        trades = self.session.query(Trade).filter(Trade.bot_id == bot.id).all()
        total_trades = len(trades)
        open_trades = len([t for t in trades if t.status == TradeStatusEnum.OPEN])
        successful_trades = len(
            [
                t
                for t in trades
                if t.status == TradeStatusEnum.CLOSED and t.realized_pnl > 0
            ]
        )
        failed_trades = len(
            [
                t
                for t in trades
                if t.status == TradeStatusEnum.CLOSED and t.realized_pnl <= 0
            ]
        )
        total_pnl = sum(t.realized_pnl for t in trades if t.realized_pnl)

        return {
            "total_trades": total_trades,
            "active_positions": open_trades,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades,
            "total_profit_loss": total_pnl,
            "win_rate": (
                (successful_trades / total_trades * 100) if total_trades > 0 else 0
            ),
        }


class JobRepository:
    """Repository for job operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_job(
        self,
        job_id: str,
        bot_id: Optional[int],
        job_type: str,
        parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Job:
        """Create a new job"""
        job = Job(
            job_id=job_id,
            bot_id=bot_id,
            job_type=job_type,
            config=parameters,
            metadata_json=metadata or {},
            progress_pct=0.0,
            updated_at=utc_now(),
        )
        self.session.add(job)
        self.session.commit()
        return job

    def get_by_job_id(self, job_id: str) -> Job | None:
        """Get job by job ID"""
        return self.session.query(Job).filter(Job.job_id == job_id).first()

    def get_by_id(self, job_id: int) -> Job | None:
        """Get a job by ID"""
        return self.session.query(Job).filter(Job.id == job_id).first()

    def get_by_bot_id(self, bot_id: int) -> list[Job]:
        """Get all jobs for a bot"""
        return self.session.query(Job).filter(Job.bot_id == bot_id).all()

    def start_job(self, job_id: str, process_id: Optional[int] = None) -> None:
        """Start a job"""
        job = self.get_by_job_id(job_id)
        if job:
            job.status = JobStatusEnum.RUNNING
            now = utc_now()
            job.started_at = now
            job.updated_at = now
            job.completed_at = None
            job.error_message = None
            job.error_traceback = None
            job.cancellation_reason = None
            if process_id is not None:
                job.process_id = process_id
            self.session.commit()

    def complete_job(
        self,
        job_id: str,
        result: Optional[dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None,
    ) -> None:
        """Complete a job"""
        job = self.get_by_job_id(job_id)
        if job:
            job.status = JobStatusEnum.COMPLETED
            job.result = result
            job.progress_pct = 100.0
            job.updated_at = utc_now()
            job.completed_at = utc_now()
            if execution_time_ms is not None:
                job.execution_time_ms = execution_time_ms
            self.session.commit()

    def fail_job(
        self, job_id: str, error_message: str, error_traceback: Optional[str] = None
    ) -> None:
        """Fail a job"""
        job = self.get_by_job_id(job_id)
        if job:
            job.status = JobStatusEnum.FAILED
            job.error_message = error_message
            job.error_traceback = error_traceback
            job.updated_at = utc_now()
            job.completed_at = utc_now()
            self.session.commit()

    def cancel_job(self, job_id: str, reason: Optional[str] = None) -> None:
        """Cancel a job and persist the cancellation reason."""
        job = self.get_by_job_id(job_id)
        if job:
            job.status = JobStatusEnum.CANCELLED
            job.cancellation_reason = reason
            job.updated_at = utc_now()
            job.completed_at = utc_now()
            self.session.commit()

    def update_progress(
        self,
        job_id: str,
        progress_pct: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Persist job progress and optional structured metadata."""
        job = self.get_by_job_id(job_id)
        if job:
            job.progress_pct = max(0.0, min(100.0, float(progress_pct or 0.0)))
            if metadata is not None:
                current = dict(job.metadata_json or {})
                current.update(metadata)
                job.metadata_json = current
            job.updated_at = utc_now()
            self.session.commit()

    def get_job_history(self, bot_id: int, days: int = 7) -> list[Job]:
        """Get job history for a bot within the last N days"""
        cutoff_date = utc_now() - timedelta(days=days)
        return (
            self.session.query(Job)
            .filter(Job.bot_id == bot_id, Job.created_at >= cutoff_date)
            .order_by(Job.created_at.desc())
            .all()
        )

    def update_status(
        self,
        job_id: int,
        status: JobStatusEnum,
        result: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
        cancellation_reason: Optional[str] = None,
        progress_pct: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Update job status"""
        job = self.get_by_id(job_id)
        if job:
            job.status = status
            if result is not None:
                job.result = result
            if error_message is not None:
                job.error_message = error_message
            if error_traceback is not None:
                job.error_traceback = error_traceback
            if cancellation_reason is not None:
                job.cancellation_reason = cancellation_reason
            if progress_pct is not None:
                job.progress_pct = max(0.0, min(100.0, float(progress_pct)))
            if metadata is not None:
                current = dict(job.metadata_json or {})
                current.update(metadata)
                job.metadata_json = current
            job.updated_at = utc_now()
            if status == JobStatusEnum.RUNNING and not job.started_at:
                job.started_at = utc_now()
            elif status in [
                JobStatusEnum.COMPLETED,
                JobStatusEnum.FAILED,
                JobStatusEnum.CANCELLED,
            ]:
                job.completed_at = utc_now()
            self.session.commit()


class TradeRepository:
    """Repository for trade operations"""

    _default_analytics_writer: AnalyticsWriter | None = None
    _analytics_writer_lock = threading.Lock()

    def __init__(
        self, session: Session, analytics_writer: AnalyticsWriter | None = None
    ):
        self.session = session
        self.analytics_writer = analytics_writer or self._resolve_analytics_writer()

    @classmethod
    def _resolve_analytics_writer(cls) -> AnalyticsWriter:
        if cls._default_analytics_writer is not None:
            return cls._default_analytics_writer

        with cls._analytics_writer_lock:
            if cls._default_analytics_writer is None:
                cls._default_analytics_writer = cls._build_analytics_writer()
        return cls._default_analytics_writer

    @staticmethod
    def _build_analytics_writer() -> AnalyticsWriter:
        return _build_clickhouse_analytics_writer("trade analytics")

    @staticmethod
    def _normalize_event_time(value: datetime | None) -> datetime:
        timestamp = value or utc_now()
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    @classmethod
    def _build_analytics_row(cls, trade: Trade, *, event_kind: str) -> dict[str, Any]:
        event_time = cls._normalize_event_time(
            trade.closed_at
            if event_kind == "closed" and trade.closed_at
            else trade.updated_at or trade.created_at
        )
        closed_at = (
            cls._normalize_event_time(trade.closed_at) if trade.closed_at else None
        )
        status = trade.status
        if isinstance(status, TradeStatusEnum):
            status_value = status.value
        else:
            status_value = str(status or "")

        # Extract additional fields from trade object and related data
        bot_run_id = getattr(trade, "bot_run_id", "") or ""
        order_id = getattr(trade, "order_id", "") or ""
        market = getattr(trade, "market", "") or ""
        side = getattr(trade, "side", "") or ""

        # Try to get fee information if available
        transaction_fee = getattr(trade, "transaction_fee", 0.0) or 0.0
        fee = float(transaction_fee) if transaction_fee else 0.0
        fee_pct = fee * 100 if fee else 0.0  # Approximate fee percentage

        # Try to get fill details if available
        fill_id = getattr(trade, "fill_id", "") or ""
        fill_index = getattr(trade, "fill_index", 0) or 0

        # Try to get correlation ID
        correlation_id = getattr(trade, "correlation_id", "") or ""

        # Try to get individual leg prices/sizes for per-fill detail
        price = getattr(trade, "price", 0.0) or 0.0
        size = getattr(trade, "size", 0.0) or 0.0

        return {
            "event_date": event_time.date(),
            "event_time": event_time,
            "trade_id": str(trade.trade_id or ""),
            "order_id": str(order_id),
            "bot_id": str(trade.bot_id),
            "instance_id": str(getattr(trade, "_analytics_instance_id", "") or ""),
            "bot_run_id": str(bot_run_id),
            "pair1": str(trade.pair1 or ""),
            "pair2": str(trade.pair2 or ""),
            "market": str(market),
            "side1": str(trade.side1 or ""),
            "side2": str(trade.side2 or ""),
            "side": str(side),
            "status": status_value,
            "event_kind": str(event_kind or ""),
            "entry_price1": float(trade.entry_price1 or 0.0),
            "entry_price2": float(trade.entry_price2 or 0.0),
            "exit_price1": (
                float(trade.exit_price1) if trade.exit_price1 is not None else None
            ),
            "exit_price2": (
                float(trade.exit_price2) if trade.exit_price2 is not None else None
            ),
            "entry_size1": float(trade.entry_size1 or 0.0),
            "entry_size2": float(trade.entry_size2 or 0.0),
            "exit_size1": (
                float(trade.exit_size1) if trade.exit_size1 is not None else None
            ),
            "exit_size2": (
                float(trade.exit_size2) if trade.exit_size2 is not None else None
            ),
            "price": float(price),
            "size": float(size),
            "fee": float(fee),
            "fee_pct": float(fee_pct),
            "realized_pnl": float(trade.realized_pnl or trade.profit_loss or 0.0),
            "realized_pnl_pct": float(
                trade.realized_pnl_pct or trade.profit_loss_percentage or 0.0
            ),
            "fill_id": str(fill_id),
            "fill_index": int(fill_index),
            "correlation_id": str(correlation_id),
            "closed_at": closed_at,
        }

    def _write_analytics_trade(self, trade: Trade, *, event_kind: str) -> None:
        setattr(
            trade,
            "_analytics_instance_id",
            _resolve_bot_instance_id(self.session, getattr(trade, "bot_id", None)),
        )
        try:
            self.analytics_writer.write_rows(
                "trade_events",
                [self._build_analytics_row(trade, event_kind=event_kind)],
            )
        except Exception as exc:
            logger.warning(
                "Failed to mirror trade %s (%s) to ClickHouse: %s",
                trade.trade_id,
                event_kind,
                exc,
            )

    def create_trade(
        self,
        trade_id: str,
        bot_id: int,
        pair1: str,
        pair2: str,
        entry_price1: float,
        entry_price2: float,
        entry_size1: float,
        entry_size2: float,
        side1: str = "BUY",
        side2: str = "SELL",
    ) -> Trade:
        """Create a new trade"""
        trade = Trade(
            bot_id=bot_id,
            trade_id=trade_id,
            pair1=pair1,
            pair2=pair2,
            side1=side1,
            side2=side2,
            entry_price1=entry_price1,
            entry_price2=entry_price2,
            entry_size1=entry_size1,
            entry_size2=entry_size2,
            status=TradeStatusEnum.OPEN,
        )
        self.session.add(trade)
        self.session.commit()
        self._write_analytics_trade(trade, event_kind="opened")
        return trade

    def get_by_position_id(self, position_id: str) -> Trade | None:
        """Get trade by position ID"""
        return self.session.query(Trade).filter(Trade.trade_id == position_id).first()

    def get_by_bot_id(self, bot_id: int) -> list[Trade]:
        """Get all trades for a bot"""
        return self.session.query(Trade).filter(Trade.bot_id == bot_id).all()

    def get_bot_trades(self, bot_id: int) -> list[Trade]:
        """Alias for get_by_bot_id"""
        return self.get_by_bot_id(bot_id)

    def close_trade(
        self,
        trade_id: str,
        exit_price1: Optional[float] = None,
        exit_price2: Optional[float] = None,
        exit_size1: Optional[float] = None,
        exit_size2: Optional[float] = None,
    ) -> None:
        """Close a trade"""
        trade = self.get_by_position_id(trade_id)
        if trade:
            if exit_price1 is not None:
                trade.exit_price1 = exit_price1
            if exit_price2 is not None:
                trade.exit_price2 = exit_price2
            if exit_size1 is not None:
                trade.exit_size1 = exit_size1
            if exit_size2 is not None:
                trade.exit_size2 = exit_size2
            # Calculate P&L
            if (
                exit_price1
                and exit_price2
                and trade.entry_price1
                and trade.entry_price2
            ):
                # Simple P&L calculation
                pnl1 = (exit_price1 - trade.entry_price1) * trade.entry_size1
                pnl2 = (trade.entry_price2 - exit_price2) * trade.entry_size2
                trade.profit_loss = pnl1 + pnl2
                trade.profit_loss_percentage = (
                    trade.profit_loss
                    / (
                        trade.entry_price1 * trade.entry_size1
                        + trade.entry_price2 * trade.entry_size2
                    )
                ) * 100
            trade.status = TradeStatusEnum.CLOSED
            trade.closed_at = utc_now()
            self.session.commit()
            self._write_analytics_trade(trade, event_kind="closed")

    def get_trade_statistics(self, bot_id: int) -> dict[str, Any]:
        """Get trade statistics for a bot"""
        trades = self.get_by_bot_id(bot_id)
        total_trades = len(trades)
        winning_trades = len(
            [
                t
                for t in trades
                if t.status == TradeStatusEnum.CLOSED and t.profit_loss > 0
            ]
        )
        losing_trades = len(
            [
                t
                for t in trades
                if t.status == TradeStatusEnum.CLOSED and t.profit_loss <= 0
            ]
        )
        total_profit_loss = sum(t.profit_loss for t in trades if t.profit_loss)
        average_trade_pnl = total_profit_loss / total_trades if total_trades > 0 else 0
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_profit_loss": total_profit_loss,
            "average_trade_pnl": average_trade_pnl,
            "win_rate": win_rate,
        }

    def update_trade_exit(
        self,
        position_id: str,
        exit_price1: Optional[float] = None,
        exit_price2: Optional[float] = None,
        exit_size1: Optional[float] = None,
        exit_size2: Optional[float] = None,
        realized_pnl: float = 0.0,
        realized_pnl_pct: float = 0.0,
    ) -> None:
        """Update trade exit information"""
        trade = self.get_by_position_id(position_id)
        if trade:
            if exit_price1 is not None:
                trade.exit_price1 = exit_price1
            if exit_price2 is not None:
                trade.exit_price2 = exit_price2
            if exit_size1 is not None:
                trade.exit_size1 = exit_size1
            if exit_size2 is not None:
                trade.exit_size2 = exit_size2
            trade.realized_pnl = realized_pnl
            trade.realized_pnl_pct = realized_pnl_pct
            trade.status = TradeStatusEnum.CLOSED
            trade.closed_at = utc_now()
            self.session.commit()
            self._write_analytics_trade(trade, event_kind="closed")


class EventRepository:
    """Repository for event logging operations"""

    _default_analytics_writer: AnalyticsWriter | None = None
    _analytics_writer_lock = threading.Lock()

    def __init__(
        self, session: Session, analytics_writer: AnalyticsWriter | None = None
    ):
        self.session = session
        self.analytics_writer = analytics_writer or self._resolve_analytics_writer()

    @classmethod
    def _resolve_analytics_writer(cls) -> AnalyticsWriter:
        if cls._default_analytics_writer is not None:
            return cls._default_analytics_writer

        with cls._analytics_writer_lock:
            if cls._default_analytics_writer is None:
                cls._default_analytics_writer = cls._build_analytics_writer()
        return cls._default_analytics_writer

    @staticmethod
    def _build_analytics_writer() -> AnalyticsWriter:
        return _build_clickhouse_analytics_writer("bot event")

    @staticmethod
    def _coerce_optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_optional_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_optional_datetime(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

    @classmethod
    def _event_context(cls, event: Event) -> tuple[dict[str, Any], datetime, str, str]:
        details: dict[str, Any] = (
            dict(event.details or {}) if isinstance(event.details, dict) else {}
        )
        created_at = event.created_at or utc_now()
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.astimezone(timezone.utc)

        correlation_id = str(
            details.get("correlation_id")
            or details.get("trace_id")
            or details.get("request_id")
            or event.related_job_id
            or ""
        )
        bot_run_id = str(
            details.get("bot_run_id")
            or details.get("run_id")
            or details.get("runtime_run_id")
            or ""
        )
        return details, created_at, correlation_id, bot_run_id

    @classmethod
    def _build_analytics_row(cls, event: Event) -> dict[str, Any]:
        details, created_at, correlation_id, bot_run_id = cls._event_context(event)
        worker_id = (
            details.get("instance_id")
            or details.get("worker_id")
            or os.getenv("BOT_INSTANCE_ID", "")
        )
        status = details.get("status") or details.get("state") or event.severity or ""
        strategy_id = cls._coerce_optional_int(
            details.get("strategy_id") or details.get("strategyId")
        )

        payload_attrs = {
            "message": event.message,
            "severity": event.severity,
            "details": details,
            "user_id": event.user_id,
            "related_job_id": event.related_job_id,
            "related_trade_id": event.related_trade_id,
        }

        return {
            "event_date": created_at.date(),
            "event_time": created_at,
            "bot_run_id": str(bot_run_id),
            "bot_id": str(event.bot_instance_id),
            "event_type": str(event.event_type or ""),
            "status": str(status),
            "strategy_id": strategy_id,
            "worker_id": str(worker_id or ""),
            "correlation_id": str(correlation_id),
            "payload_attrs": json.dumps(payload_attrs, sort_keys=True, default=str),
        }

    @staticmethod
    def _order_status_for_event(event_type: str) -> str:
        event_type = str(event_type or "")
        if event_type == "trade_entry_opened":
            return "filled"
        if event_type == "trade_exit_close_confirmed":
            return "closed"
        if event_type == "trade_exit_orphaned":
            return "orphaned"
        return ""

    @classmethod
    def _build_order_analytics_rows(cls, event: Event) -> list[dict[str, Any]]:
        details, created_at, correlation_id, bot_run_id = cls._event_context(event)
        event_type = str(event.event_type or "")
        instance_id = str(
            details.get("instance_id") or details.get("bot_instance_id") or ""
        )
        trade_id = str(
            event.related_trade_id
            or details.get("trade_id")
            or details.get("related_trade_id")
            or ""
        )

        order_specs: list[dict[str, Any]] = []
        if event_type == "trade_entry_opened":
            order_specs = [
                {
                    "order_id_key": "order_id_m1",
                    "market_key": "market_1",
                    "side_key": "order_m1_side",
                    "price_key": "order_m1_price",
                    "size_key": "order_m1_size",
                    "exchange_time_key": "order_time_m1",
                },
                {
                    "order_id_key": "order_id_m2",
                    "market_key": "market_2",
                    "side_key": "order_m2_side",
                    "price_key": "order_m2_price",
                    "size_key": "order_m2_size",
                    "exchange_time_key": "order_time_m2",
                },
            ]
        elif event_type == "trade_exit_close_confirmed":
            order_specs = [
                {
                    "order_id_key": "close_order_m1_id",
                    "market_key": "market_1",
                    "side_key": "close_order_m1_side",
                    "price_key": "close_order_m1_price",
                    "size_key": "close_order_m1_size",
                    "exchange_time_key": "close_order_time_m1",
                },
                {
                    "order_id_key": "close_order_m2_id",
                    "market_key": "market_2",
                    "side_key": "close_order_m2_side",
                    "price_key": "close_order_m2_price",
                    "size_key": "close_order_m2_size",
                    "exchange_time_key": "close_order_time_m2",
                },
            ]
        elif event_type == "trade_exit_orphaned":
            order_specs = [
                {
                    "order_id_key": "close_order_m1_id",
                    "market_key": "market_1",
                    "side_key": "close_order_m1_side",
                    "price_key": "close_order_m1_price",
                    "size_key": "close_order_m1_size",
                    "exchange_time_key": "close_order_time_m1",
                }
            ]

        status = cls._order_status_for_event(event_type)
        rows: list[dict[str, Any]] = []
        for spec in order_specs:
            order_id = details.get(spec["order_id_key"])
            if not order_id:
                continue
            # Extract additional exchange-native fields
            filled_size = cls._coerce_optional_float(details.get("filled_size"))
            remaining_size = cls._coerce_optional_float(details.get("remaining_size"))
            fee = cls._coerce_optional_float(details.get("fee"))
            exchange_order_id = str(details.get("exchange_order_id") or "")
            client_order_id = str(details.get("client_order_id") or "")
            order_type = str(details.get("type") or "")
            time_in_force = str(details.get("time_in_force") or "")
            post_only = int(details.get("post_only", 0) or 0)
            reduce_only = int(details.get("reduce_only", 0) or 0)
            ioc = int(details.get("ioc", 0) or 0)

            rows.append(
                {
                    "event_date": created_at.date(),
                    "event_time": created_at,
                    "order_id": str(order_id),
                    "trade_id": trade_id,
                    "bot_id": str(event.bot_instance_id),
                    "instance_id": instance_id,
                    "bot_run_id": bot_run_id,
                    "market": str(details.get(spec["market_key"]) or ""),
                    "side": str(details.get(spec["side_key"]) or ""),
                    "status": status,
                    "event_type": event_type,
                    "price": cls._coerce_optional_float(details.get(spec["price_key"])),
                    "size": cls._coerce_optional_float(details.get(spec["size_key"])),
                    "filled_size": filled_size,
                    "remaining_size": remaining_size,
                    "fee": fee,
                    "exchange_time": cls._normalize_optional_datetime(
                        details.get(spec["exchange_time_key"])
                    ),
                    "correlation_id": correlation_id,
                    "exchange_order_id": exchange_order_id,
                    "client_order_id": client_order_id,
                    "type": order_type,
                    "time_in_force": time_in_force,
                    "post_only": post_only,
                    "reduce_only": reduce_only,
                    "ioc": ioc,
                }
            )
        return rows

    def _write_analytics_event(self, event: Event) -> None:
        try:
            self.analytics_writer.write_rows(
                "bot_events", [self._build_analytics_row(event)]
            )
        except Exception as exc:
            logger.warning(
                "Failed to mirror bot event %s to ClickHouse: %s",
                event.event_type,
                exc,
            )
        order_rows = self._build_order_analytics_rows(event)
        if not order_rows:
            return
        try:
            self.analytics_writer.write_rows("order_events", order_rows)
        except Exception as exc:
            logger.warning(
                "Failed to mirror order events for %s to ClickHouse: %s",
                event.event_type,
                exc,
            )

    def log_event(
        self,
        bot_instance_id: int,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
        related_job_id: Optional[str] = None,
        related_trade_id: Optional[str] = None,
    ) -> Event:
        """Log an event"""
        event = Event(
            bot_instance_id=bot_instance_id,
            event_type=event_type,
            severity=severity,
            message=message,
            details=details,
            user_id=user_id,
            related_job_id=related_job_id,
            related_trade_id=related_trade_id,
            created_at=utc_now(),
        )
        self.session.add(event)
        self.session.commit()
        self._write_analytics_event(event)
        return event

    def get_bot_events(self, bot_instance_id: int, days: int = 7) -> list[Event]:
        """Get events for a bot within the last N days"""
        cutoff_date = utc_now() - timedelta(days=days)
        return (
            self.session.query(Event)
            .filter(
                Event.bot_instance_id == bot_instance_id,
                Event.created_at >= cutoff_date,
            )
            .order_by(Event.created_at.desc())
            .all()
        )

    def get_all_events(self, days: int = 7) -> list[Event]:
        """Get all events within the last N days"""
        cutoff_date = utc_now() - timedelta(days=days)
        return (
            self.session.query(Event)
            .filter(Event.created_at >= cutoff_date)
            .order_by(Event.created_at.desc())
            .all()
        )


class StrategyRepository:
    """Repository for persistent strategy operations"""

    def __init__(self, session: Session):
        self.session = session

    def _to_dict(self, strategy: Strategy) -> dict[str, Any]:
        return {
            "id": strategy.id,
            "name": strategy.name,
            "category": strategy.category,
            "description": strategy.description,
            "is_public": strategy.is_public,
            "is_default": strategy.is_default,
            "user_id": strategy.user_id,
            "resolution": strategy.candle_resolution,
            "zscore_threshold": float(strategy.zscore_threshold),
            "stats_window": int(strategy.stats_window),
            "max_half_life": float(strategy.max_half_life),
            "usd_per_trade": float(strategy.usd_per_trade),
            "usd_min_collateral": float(strategy.usd_min_collateral),
            "close_at_zscore_cross": strategy.close_at_zscore_cross,
            "find_cointegrated_pairs": strategy.find_cointegrated_pairs,
            "manage_exits": strategy.manage_exits,
            "place_trades": strategy.place_trades,
            "abort_all_positions": strategy.abort_all_positions,
            "max_positions": int(strategy.max_positions),
            "max_drawdown_pct": float(strategy.max_drawdown_pct),
            "stop_loss_pct": float(strategy.stop_loss_pct),
            "take_profit_pct": float(strategy.take_profit_pct),
            "trailing_stop_pct": float(strategy.trailing_stop_pct),
            "rebalance_interval_hours": int(strategy.rebalance_interval_hours),
            "position_timeout_hours": int(strategy.position_timeout_hours),
            "pair_selection_mode": strategy.pair_selection_mode,
            "transaction_fee": float(strategy.transaction_fee),
            "slippage": float(strategy.slippage),
            "starting_balance": float(strategy.starting_balance),
            "candle_resolution": strategy.candle_resolution,
            "max_history_days": int(strategy.max_history_days),
            "benchmark_symbol": strategy.benchmark_symbol,
            "risk_free_rate": float(strategy.risk_free_rate),
            "initial_amount": float(strategy.initial_amount),
            "usage_count": int(strategy.usage_count or 0),
            "last_used_at": (
                strategy.last_used_at.isoformat() if strategy.last_used_at else None
            ),
            "created_at": (
                strategy.created_at.isoformat() if strategy.created_at else None
            ),
            "updated_at": (
                strategy.updated_at.isoformat() if strategy.updated_at else None
            ),
            "deleted_at": (
                strategy.deleted_at.isoformat() if strategy.deleted_at else None
            ),
        }

    def list(self, skip: int = 0, limit: int = 50) -> dict[str, Any]:
        query = (
            self.session.query(Strategy)
            .filter(Strategy.deleted_at.is_(None))
            .order_by(Strategy.id.desc())
        )
        total = query.count()
        rows = query.offset(skip).limit(limit).all()
        return {"strategies": [self._to_dict(s) for s in rows], "total": total}

    def list_public(self) -> dict[str, Any]:
        rows = (
            self.session.query(Strategy)
            .filter(Strategy.is_public.is_(True), Strategy.deleted_at.is_(None))
            .order_by(Strategy.id.desc())
            .all()
        )
        return {"strategies": [self._to_dict(s) for s in rows], "total": len(rows)}

    def get(self, strategy_id: int) -> Optional[dict[str, Any]]:
        row = (
            self.session.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.deleted_at.is_(None))
            .first()
        )
        return self._to_dict(row) if row else None

    def create(
        self, payload: dict[str, Any], note: str = "Initial version"
    ) -> dict[str, Any]:
        strategy = Strategy(
            name=payload.get("name", "Untitled Strategy"),
            category=payload.get("category", "custom"),
            description=payload.get("description", ""),
            is_public=bool(payload.get("is_public", False)),
            is_default=bool(payload.get("is_default", False)),
            user_id=int(payload.get("user_id", 1)),
            zscore_threshold=float(payload.get("zscore_threshold", 1.5)),
            stats_window=int(payload.get("stats_window", 21)),
            max_half_life=float(payload.get("max_half_life", 24.0)),
            usd_per_trade=float(payload.get("usd_per_trade", 10.0)),
            usd_min_collateral=float(payload.get("usd_min_collateral", 100.0)),
            close_at_zscore_cross=bool(payload.get("close_at_zscore_cross", True)),
            find_cointegrated_pairs=bool(payload.get("find_cointegrated_pairs", True)),
            manage_exits=bool(payload.get("manage_exits", True)),
            place_trades=bool(payload.get("place_trades", True)),
            abort_all_positions=bool(payload.get("abort_all_positions", False)),
            max_positions=int(payload.get("max_positions", 5)),
            max_drawdown_pct=float(payload.get("max_drawdown_pct", 15.0)),
            stop_loss_pct=float(payload.get("stop_loss_pct", 3.0)),
            take_profit_pct=float(payload.get("take_profit_pct", 8.0)),
            trailing_stop_pct=float(payload.get("trailing_stop_pct", 2.0)),
            rebalance_interval_hours=int(payload.get("rebalance_interval_hours", 24)),
            position_timeout_hours=int(payload.get("position_timeout_hours", 72)),
            pair_selection_mode=str(payload.get("pair_selection_mode", "liquidity")),
            transaction_fee=float(payload.get("transaction_fee", 0.0005)),
            slippage=float(payload.get("slippage", 0.001)),
            starting_balance=float(payload.get("starting_balance", 1000.0)),
            candle_resolution=payload.get(
                "candle_resolution",
                payload.get("resolution", "1HOUR"),
            ),
            max_history_days=int(payload.get("max_history_days", 90)),
            benchmark_symbol=payload.get("benchmark_symbol", "BTC-USD"),
            risk_free_rate=float(payload.get("risk_free_rate", 0.02)),
            initial_amount=float(
                payload.get("initial_amount", payload.get("starting_balance", 1000.0))
            ),
        )
        self.session.add(strategy)
        self.session.flush()

        latest_version = (
            self.session.query(StrategyVersion)
            .filter(StrategyVersion.strategy_id == strategy.id)
            .order_by(StrategyVersion.version_number.desc())
            .first()
        )
        next_version = (latest_version.version_number + 1) if latest_version else 1

        version = StrategyVersion(
            strategy_id=strategy.id,
            version_number=next_version,
            change_description=note,
            config_snapshot=self._to_dict(strategy),
            changes={},
            created_by_user_id=int(payload.get("user_id", 1)),
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(strategy)
        return self._to_dict(strategy)

    def update(
        self, strategy_id: int, payload: dict[str, Any], note: str = "Updated strategy"
    ) -> Optional[dict[str, Any]]:
        strategy = (
            self.session.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.deleted_at.is_(None))
            .first()
        )
        if not strategy:
            return None

        current = self._to_dict(strategy)
        merged = {**current, **payload}

        strategy.name = merged.get("name", strategy.name)
        strategy.category = merged.get("category", strategy.category)
        strategy.description = merged.get("description", strategy.description)
        strategy.is_public = bool(merged.get("is_public", strategy.is_public))
        strategy.is_default = bool(merged.get("is_default", strategy.is_default))
        strategy.user_id = int(merged.get("user_id", strategy.user_id))
        strategy.zscore_threshold = float(
            merged.get("zscore_threshold", strategy.zscore_threshold)
        )
        strategy.stats_window = int(merged.get("stats_window", strategy.stats_window))
        strategy.max_half_life = float(
            merged.get("max_half_life", strategy.max_half_life)
        )
        strategy.usd_per_trade = float(
            merged.get("usd_per_trade", strategy.usd_per_trade)
        )
        strategy.usd_min_collateral = float(
            merged.get("usd_min_collateral", strategy.usd_min_collateral)
        )
        strategy.close_at_zscore_cross = bool(
            merged.get("close_at_zscore_cross", strategy.close_at_zscore_cross)
        )
        strategy.find_cointegrated_pairs = bool(
            merged.get("find_cointegrated_pairs", strategy.find_cointegrated_pairs)
        )
        strategy.manage_exits = bool(merged.get("manage_exits", strategy.manage_exits))
        strategy.place_trades = bool(merged.get("place_trades", strategy.place_trades))
        strategy.abort_all_positions = bool(
            merged.get("abort_all_positions", strategy.abort_all_positions)
        )
        strategy.max_positions = int(
            merged.get("max_positions", strategy.max_positions)
        )
        strategy.max_drawdown_pct = float(
            merged.get("max_drawdown_pct", strategy.max_drawdown_pct)
        )
        strategy.stop_loss_pct = float(
            merged.get("stop_loss_pct", strategy.stop_loss_pct)
        )
        strategy.take_profit_pct = float(
            merged.get("take_profit_pct", strategy.take_profit_pct)
        )
        strategy.trailing_stop_pct = float(
            merged.get("trailing_stop_pct", strategy.trailing_stop_pct)
        )
        strategy.rebalance_interval_hours = int(
            merged.get("rebalance_interval_hours", strategy.rebalance_interval_hours)
        )
        strategy.position_timeout_hours = int(
            merged.get("position_timeout_hours", strategy.position_timeout_hours)
        )
        strategy.pair_selection_mode = str(
            merged.get("pair_selection_mode", strategy.pair_selection_mode)
        )
        strategy.transaction_fee = float(
            merged.get("transaction_fee", strategy.transaction_fee)
        )
        strategy.slippage = float(merged.get("slippage", strategy.slippage))
        strategy.starting_balance = float(
            merged.get("starting_balance", strategy.starting_balance)
        )
        strategy.candle_resolution = merged.get(
            "candle_resolution",
            merged.get("resolution", strategy.candle_resolution),
        )
        strategy.max_history_days = int(
            merged.get("max_history_days", strategy.max_history_days)
        )
        strategy.benchmark_symbol = merged.get(
            "benchmark_symbol", strategy.benchmark_symbol
        )
        strategy.risk_free_rate = float(
            merged.get("risk_free_rate", strategy.risk_free_rate)
        )
        strategy.initial_amount = float(
            merged.get("initial_amount", strategy.initial_amount)
        )

        self.session.flush()

        latest_version = (
            self.session.query(StrategyVersion)
            .filter(StrategyVersion.strategy_id == strategy.id)
            .order_by(StrategyVersion.version_number.desc())
            .first()
        )
        next_version = (latest_version.version_number + 1) if latest_version else 1

        version = StrategyVersion(
            strategy_id=strategy.id,
            version_number=next_version,
            change_description=note,
            config_snapshot=self._to_dict(strategy),
            changes={},
            created_by_user_id=int(merged.get("user_id", strategy.user_id)),
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(strategy)
        return self._to_dict(strategy)

    def delete(self, strategy_id: int) -> bool:
        strategy = (
            self.session.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.deleted_at.is_(None))
            .first()
        )
        if not strategy:
            return False
        strategy.deleted_at = utc_now()
        self.session.commit()
        return True

    def versions(self, strategy_id: int) -> List[dict[str, Any]]:
        rows = (
            self.session.query(StrategyVersion)
            .filter(StrategyVersion.strategy_id == strategy_id)
            .order_by(StrategyVersion.id.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "strategy_id": row.strategy_id,
                "name": row.config_snapshot.get("name", ""),
                "description": row.change_description,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "config": row.config_snapshot,
            }
            for row in rows
        ]

    def revert(self, strategy_id: int, version_id: int) -> Optional[dict[str, Any]]:
        version = (
            self.session.query(StrategyVersion)
            .filter(
                StrategyVersion.strategy_id == strategy_id,
                StrategyVersion.id == version_id,
            )
            .first()
        )
        if not version:
            return None
        return self.update(
            strategy_id,
            version.config_snapshot,
            note=f"Reverted to version {version_id}",
        )


class UnitOfWork:
    """Unit of Work for core bot operations"""

    def __init__(self, session: Session):
        self.session = session
        self.bots = BotRepository(session)
        self.jobs = JobRepository(session)
        self.trades = TradeRepository(session)
        self.events = EventRepository(session)
        self.strategies = StrategyRepository(session)

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
