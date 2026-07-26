"""Best-effort live trade persistence using existing repository APIs."""

import hashlib
import os
from typing import Any, Dict, Optional

from loguru import logger
from src.infrastructure.database import db
from src.infrastructure.persistence.repository import UnitOfWork
from src.infrastructure.persistence.repository_realtime import UnitOfWorkRealtime


def _db_persistence_enabled() -> bool:
    if any(
            bool(os.getenv(name, "").strip())
            for name in (
                    "BOT_DATABASE_URL",
                    "DATABASE_URL",
                    "BOT_DB_HOST",
                    "DB_HOST",
            )
    ):
        return True
    return getattr(db.get_session, "__self__", None) is not db


def _runtime_instance_id() -> Optional[str]:
    instance_id = os.getenv("BOT_INSTANCE_ID", "").strip()
    return instance_id or None


def persist_trade_activity_event(
        event_type: str,
        message: str,
        *,
        severity: str = "info",
        details: Optional[Dict[str, Any]] = None,
        related_trade_id: Optional[str] = None,
) -> bool:
    """
    Persist structured trade activity events to the bot event log.

    Best-effort and non-blocking by design. This is environment-agnostic and
    applies to any runtime instance that has a DB bot record.
    """
    instance_id = _runtime_instance_id()
    if not instance_id or not _db_persistence_enabled():
        return False

    session = None
    try:
        session = db.get_session()
        uow = UnitOfWork(session)
        bot = uow.bots.get_by_instance_id(instance_id)
        if bot is None:
            logger.debug(
                "Skipping trade activity event persistence; no bot row for {}",
                instance_id,
            )
            return False

        event_details = dict(details or {})
        event_details.setdefault("instance_id", instance_id)

        uow.events.log_event(
            bot_instance_id=bot.id,
            event_type=str(event_type or "trade_activity"),
            severity=str(severity or "info"),
            message=str(message or "trade activity"),
            details=event_details,
            related_trade_id=(str(related_trade_id) if related_trade_id else None),
        )
        return True
    except Exception as exc:
        logger.warning("Failed to persist trade activity event {}: {}", event_type, exc)
        if session is not None:
            session.rollback()
        return False
    finally:
        if session is not None:
            session.close()


def live_trade_id(position: Dict[str, Any], instance_id: Optional[str] = None) -> str:
    raw = "|".join(
        [
            instance_id or _runtime_instance_id() or "default",
            str(position.get("market_1", "")),
            str(position.get("market_2", "")),
            str(position.get("order_id_m1", "")),
            str(position.get("order_id_m2", "")),
        ]
    )
    return f"live-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def persist_live_trade_opened(position: Dict[str, Any]) -> Optional[str]:
    """
    Persist a live pair into core trade history and realtime position tables.

    Existing schemas cover the minimal open/close lifecycle. Persistence is
    best-effort and must never block exchange state tracking or emergency cleanup.
    """
    instance_id = _runtime_instance_id()
    if not instance_id or not _db_persistence_enabled():
        return None

    session = None
    trade_id = live_trade_id(position, instance_id)
    try:
        session = db.get_session()
        uow = UnitOfWork(session)
        realtime = UnitOfWorkRealtime(session)
        bot = uow.bots.get_by_instance_id(instance_id)
        if bot is None:
            logger.debug("Skipping live trade persistence; no bot row for {}", instance_id)
            return None

        if uow.trades.get_by_position_id(trade_id) is None:
            uow.trades.create_trade(
                trade_id=trade_id,
                bot_id=bot.id,
                pair1=str(position.get("market_1", "")),
                pair2=str(position.get("market_2", "")),
                entry_price1=_float_or_zero(position.get("order_m1_price")),
                entry_price2=_float_or_zero(position.get("order_m2_price")),
                entry_size1=_float_or_zero(position.get("order_m1_size")),
                entry_size2=_float_or_zero(position.get("order_m2_size")),
                side1=str(position.get("order_m1_side", "")),
                side2=str(position.get("order_m2_side", "")),
            )

        if realtime.positions.get_position_by_id(trade_id) is None:
            realtime.positions.create_position(
                bot_instance_id=bot.id,
                position_id=trade_id,
                pair1=str(position.get("market_1", "")),
                pair2=str(position.get("market_2", "")),
                side1=str(position.get("order_m1_side", "")),
                side2=str(position.get("order_m2_side", "")),
                entry_price1=_float_or_zero(position.get("order_m1_price")),
                entry_price2=_float_or_zero(position.get("order_m2_price")),
                entry_size1=_float_or_zero(position.get("order_m1_size")),
                entry_size2=_float_or_zero(position.get("order_m2_size")),
            )
        return trade_id
    except Exception as exc:
        logger.warning("Failed to persist opened live trade {}: {}", trade_id, exc)
        if session is not None:
            session.rollback()
        return None
    finally:
        if session is not None:
            session.close()


def persist_live_trade_closed(
        position: Dict[str, Any],
        *,
        exit_price1: Any,
        exit_price2: Any,
        exit_size1: Any,
        exit_size2: Any,
) -> Optional[str]:
    """Mark an existing live trade/position closed when both reduce-only exits submit."""
    instance_id = _runtime_instance_id()
    if not instance_id or not _db_persistence_enabled():
        return None

    session = None
    trade_id = live_trade_id(position, instance_id)
    try:
        session = db.get_session()
        uow = UnitOfWork(session)
        realtime = UnitOfWorkRealtime(session)
        uow.trades.update_trade_exit(
            trade_id,
            exit_price1=_float_or_zero(exit_price1),
            exit_price2=_float_or_zero(exit_price2),
            exit_size1=_float_or_zero(exit_size1),
            exit_size2=_float_or_zero(exit_size2),
        )
        realtime.positions.close_position(trade_id)
        return trade_id
    except Exception as exc:
        logger.warning("Failed to persist closed live trade {}: {}", trade_id, exc)
        if session is not None:
            session.rollback()
        return None
    finally:
        if session is not None:
            session.close()
