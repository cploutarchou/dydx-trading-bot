"""
Repository classes for realtime data operations
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from internal.domain.models import Bot
from internal.domain.models_realtime import (
    Alert,
    BotStats,
    MarketData,
    Position,
    PositionStatusEnum,
)
from src.infrastructure.persistence.repository import _build_clickhouse_analytics_writer
from src.infrastructure.storage import AnalyticsWriter
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


def _float_or_default(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(default)
        except (TypeError, ValueError):
            return 0.0


def _position_leg_pnl(
    side: str,
    entry_price: Any,
    current_price: Any,
    size: Any,
) -> float:
    entry = _float_or_default(entry_price)
    current = _float_or_default(current_price)
    quantity = abs(_float_or_default(size))
    normalized_side = str(side or "").upper()
    if normalized_side in {"SELL", "SHORT"}:
        return (entry - current) * quantity
    return (current - entry) * quantity


def _position_entry_notional(position: Any) -> float:
    size1 = _float_or_default(position.current_size1, position.entry_size1)
    size2 = _float_or_default(position.current_size2, position.entry_size2)
    return abs(_float_or_default(position.entry_price1) * size1) + abs(
        _float_or_default(position.entry_price2) * size2
    )


class PositionRepository:
    """Repository for position operations"""

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
        return _build_clickhouse_analytics_writer("position analytics")

    @staticmethod
    def _normalize_event_time(value: datetime | None) -> datetime:
        timestamp = value or utc_now()
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    @classmethod
    def _build_analytics_row(
        cls, position: Position, *, event_kind: str
    ) -> dict[str, Any]:
        closed_at_value = getattr(position, "closed_at", None)
        updated_at_value = getattr(position, "updated_at", None)
        entry_time_value = getattr(position, "entry_time", None)
        created_at_value = getattr(position, "created_at", None)
        snapshot_time = cls._normalize_event_time(
            closed_at_value
            if event_kind == "closed" and closed_at_value
            else updated_at_value or entry_time_value or created_at_value
        )
        closed_at = (
            cls._normalize_event_time(closed_at_value)
            if closed_at_value is not None
            else None
        )
        status = getattr(position, "status", "")
        if isinstance(status, PositionStatusEnum):
            status_value = status.value
        else:
            status_value = str(status or "")

        # Extract additional fields for strategy dimensions and exchange-native data
        bot_run_id = getattr(position, "bot_run_id", "") or ""
        market = getattr(position, "market", "") or ""
        side = getattr(position, "side", "") or ""
        strategy_id = getattr(position, "strategy_id", None)
        strategy_name = getattr(position, "strategy_name", "") or ""

        # Exchange-native fields
        exchange_position_id = getattr(position, "dydx_position_id", "") or ""
        leverage = getattr(position, "leverage", None)
        margin_used = getattr(position, "margin_used", None)

        # Fee accumulation
        fee_accrued = getattr(position, "fee_accrued", 0.0) or 0.0

        return {
            "snapshot_date": snapshot_time.date(),
            "snapshot_time": snapshot_time,
            "position_id": str(getattr(position, "position_id", "") or ""),
            "bot_id": str(getattr(position, "bot_instance_id", "") or ""),
            "instance_id": str(getattr(position, "_analytics_instance_id", "") or ""),
            "bot_run_id": str(bot_run_id),
            "pair1": str(getattr(position, "pair1", "") or ""),
            "pair2": str(getattr(position, "pair2", "") or ""),
            "market": str(market),
            "side1": str(getattr(position, "side1", "") or ""),
            "side2": str(getattr(position, "side2", "") or ""),
            "side": str(side),
            "status": status_value,
            "event_kind": str(event_kind or ""),
            "strategy_id": strategy_id,
            "strategy_name": str(strategy_name),
            "entry_price1": float(getattr(position, "entry_price1", 0.0) or 0.0),
            "entry_price2": float(getattr(position, "entry_price2", 0.0) or 0.0),
            "current_price1": (
                float(getattr(position, "current_price1"))
                if getattr(position, "current_price1", None) is not None
                else None
            ),
            "current_price2": (
                float(getattr(position, "current_price2"))
                if getattr(position, "current_price2", None) is not None
                else None
            ),
            "entry_size1": float(getattr(position, "entry_size1", 0.0) or 0.0),
            "entry_size2": float(getattr(position, "entry_size2", 0.0) or 0.0),
            "current_size1": (
                float(getattr(position, "current_size1"))
                if getattr(position, "current_size1", None) is not None
                else None
            ),
            "current_size2": (
                float(getattr(position, "current_size2"))
                if getattr(position, "current_size2", None) is not None
                else None
            ),
            "unrealized_pnl": float(getattr(position, "unrealized_pnl", 0.0) or 0.0),
            "unrealized_pnl_pct": float(
                getattr(position, "unrealized_pnl_pct", 0.0) or 0.0
            ),
            "realized_pnl": float(getattr(position, "realized_pnl", 0.0) or 0.0),
            "realized_pnl_pct": float(
                getattr(position, "realized_pnl_pct", 0.0) or 0.0
            ),
            "fee_accrued": float(fee_accrued),
            "exchange_position_id": str(exchange_position_id),
            "leverage": float(leverage) if leverage is not None else None,
            "margin_used": float(margin_used) if margin_used is not None else None,
            "z_score_entry": (
                float(getattr(position, "z_score_entry"))
                if getattr(position, "z_score_entry", None) is not None
                else None
            ),
            "z_score_current": (
                float(getattr(position, "z_score_current"))
                if getattr(position, "z_score_current", None) is not None
                else None
            ),
            "hedge_ratio": (
                float(getattr(position, "hedge_ratio"))
                if getattr(position, "hedge_ratio", None) is not None
                else None
            ),
            "correlation": (
                float(getattr(position, "correlation"))
                if getattr(position, "correlation", None) is not None
                else None
            ),
            "half_life": (
                float(getattr(position, "half_life"))
                if getattr(position, "half_life", None) is not None
                else None
            ),
            "funding_rate": (
                float(getattr(position, "funding_rate"))
                if getattr(position, "funding_rate", None) is not None
                else None
            ),
            "closed_at": closed_at,
        }

    def _write_position_snapshot(self, position: Position, *, event_kind: str) -> None:
        setattr(
            position,
            "_analytics_instance_id",
            _resolve_bot_instance_id(
                self.session, getattr(position, "bot_instance_id", None)
            ),
        )
        try:
            self.analytics_writer.write_rows(
                "position_snapshots",
                [self._build_analytics_row(position, event_kind=event_kind)],
            )
        except Exception as exc:
            logger.warning(
                "Failed to mirror realtime position %s (%s) to ClickHouse: %s",
                position.position_id,
                event_kind,
                exc,
            )

    def get_open_positions(self, bot_instance_id: int) -> List[Position]:
        """Get all open positions for a bot"""
        return (
            self.session.query(Position)
            .filter(
                Position.bot_instance_id == bot_instance_id,
                Position.status == PositionStatusEnum.OPEN,
            )
            .all()
        )

    def get_position_by_id(self, position_id: str) -> Optional[Position]:
        """Get position by ID"""
        return (
            self.session.query(Position)
            .filter(Position.position_id == position_id)
            .first()
        )

    def create_position(
        self,
        bot_instance_id: int,
        position_id: str,
        pair1: str,
        pair2: str,
        side1: str,
        side2: str,
        entry_price1: float,
        entry_price2: float,
        entry_size1: float,
        entry_size2: float,
        z_score_entry: Optional[float] = None,
        hedge_ratio: Optional[float] = None,
        correlation: Optional[float] = None,
        half_life: Optional[float] = None,
        funding_rate: Optional[float] = None,
    ) -> Position:
        """Create a new position"""
        position = Position(
            bot_instance_id=bot_instance_id,
            position_id=position_id,
            pair1=pair1,
            pair2=pair2,
            side1=side1,
            side2=side2,
            entry_price1=entry_price1,
            entry_price2=entry_price2,
            entry_size1=entry_size1,
            entry_size2=entry_size2,
            status=PositionStatusEnum.OPEN,
            z_score_entry=z_score_entry,
            hedge_ratio=hedge_ratio,
            correlation=correlation,
            half_life=half_life,
            funding_rate=funding_rate,
        )
        self.session.add(position)
        self.session.commit()
        self._write_position_snapshot(position, event_kind="opened")
        return position

    def update_position_prices(
        self,
        position_id: str,
        current_price1: float,
        current_price2: float,
        *,
        z_score_current: Optional[float] = None,
        funding_rate: Optional[float] = None,
    ) -> None:
        """Update current prices for a position"""
        position = (
            self.session.query(Position)
            .filter(Position.position_id == position_id)
            .first()
        )
        if position:
            size1 = _float_or_default(position.current_size1, position.entry_size1)
            size2 = _float_or_default(position.current_size2, position.entry_size2)
            pnl = _position_leg_pnl(
                position.side1, position.entry_price1, current_price1, size1
            ) + _position_leg_pnl(
                position.side2, position.entry_price2, current_price2, size2
            )
            entry_notional = _position_entry_notional(position)

            position.current_price1 = current_price1
            position.current_price2 = current_price2
            position.current_size1 = size1
            position.current_size2 = size2
            position.unrealized_pnl = pnl
            position.unrealized_pnl_pct = (
                (pnl / entry_notional) * 100 if entry_notional > 0 else 0.0
            )
            if z_score_current is not None:
                position.z_score_current = z_score_current
            if funding_rate is not None:
                position.funding_rate = funding_rate
            self.session.commit()
            self._write_position_snapshot(position, event_kind="mark_to_market")

    def close_position(self, position_id: str) -> None:
        """Close a position"""
        position = (
            self.session.query(Position)
            .filter(Position.position_id == position_id)
            .first()
        )
        if position:
            position.status = PositionStatusEnum.CLOSED
            position.closed_at = utc_now()
            self.session.commit()
            self._write_position_snapshot(position, event_kind="closed")


class MarketDataRepository:
    """Repository for market data operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_market_data(
        self, bot_instance_id: int, symbol: str
    ) -> Optional[MarketData]:
        """Get market data for a symbol"""
        return (
            self.session.query(MarketData)
            .filter(
                MarketData.bot_instance_id == bot_instance_id,
                MarketData.symbol == symbol,
            )
            .first()
        )

    def get_all_market_data(self, bot_instance_id: int) -> List[MarketData]:
        """Get all market data for a bot"""
        return (
            self.session.query(MarketData)
            .filter(MarketData.bot_instance_id == bot_instance_id)
            .all()
        )

    def upsert_market_data(
        self,
        bot_instance_id: int,
        symbol: str,
        current_price: float,
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        volume_24h: Optional[float] = None,
        volatility_24h: Optional[float] = None,
        rsi: Optional[float] = None,
        macd: Optional[float] = None,
        moving_avg_20: Optional[float] = None,
        moving_avg_50: Optional[float] = None,
        funding_rate: Optional[float] = None,
    ) -> MarketData:
        """Insert or update market data"""
        market_data = self.get_market_data(bot_instance_id, symbol)
        if market_data:
            # Update existing
            market_data.current_price = current_price
            market_data.bid_price = bid_price
            market_data.ask_price = ask_price
            market_data.volume_24h = volume_24h
            market_data.volatility_24h = volatility_24h
            market_data.rsi = rsi
            market_data.macd = macd
            market_data.moving_avg_20 = moving_avg_20
            market_data.moving_avg_50 = moving_avg_50
            market_data.funding_rate = funding_rate
        else:
            # Create new
            market_data = MarketData(
                bot_instance_id=bot_instance_id,
                symbol=symbol,
                current_price=current_price,
                bid_price=bid_price,
                ask_price=ask_price,
                volume_24h=volume_24h,
                volatility_24h=volatility_24h,
                rsi=rsi,
                macd=macd,
                moving_avg_20=moving_avg_20,
                moving_avg_50=moving_avg_50,
                funding_rate=funding_rate,
            )
            self.session.add(market_data)
        self.session.commit()
        return market_data


class StatsRepository:
    """Repository for bot statistics operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_stats(self, bot_instance_id: int) -> Optional[BotStats]:
        """Get stats for a bot"""
        return (
            self.session.query(BotStats)
            .filter(BotStats.bot_instance_id == bot_instance_id)
            .first()
        )

    def calculate_and_update_stats(
        self, bot_instance_id: int, position_repo: PositionRepository
    ) -> None:
        """Calculate and update bot statistics"""
        positions = position_repo.get_open_positions(bot_instance_id)
        stats = self.get_stats(bot_instance_id)

        if not stats:
            stats = BotStats(bot_instance_id=bot_instance_id)
            self.session.add(stats)

        # Calculate stats from positions
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        total_positions = len(positions)
        total_entry_notional = sum(_position_entry_notional(p) for p in positions)

        stats.total_open_positions = total_positions
        stats.total_unrealized_pnl = total_unrealized_pnl
        stats.total_unrealized_pnl_pct = (
            (total_unrealized_pnl / total_entry_notional) * 100
            if total_entry_notional > 0
            else 0.0
        )
        stats.daily_pnl = 0.0
        stats.daily_pnl_pct = 0.0
        stats.daily_trades_opened = 0
        stats.daily_trades_closed = 0
        stats.daily_win_rate = 0.0
        stats.current_drawdown = 0.0

        self.session.commit()


class AlertRepository:
    """Repository for alert operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_alert(
        self,
        bot_instance_id: int,
        alert_type: str,
        severity: str,
        message: str,
        details: Optional[dict] = None,
    ) -> Alert:
        """Create a new alert"""
        alert = Alert(
            bot_instance_id=bot_instance_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details,
        )
        self.session.add(alert)
        self.session.commit()
        return alert

    def get_unacknowledged_alerts(self, bot_instance_id: int) -> List[Alert]:
        """Get unacknowledged alerts for a bot"""
        return (
            self.session.query(Alert)
            .filter(
                Alert.bot_instance_id == bot_instance_id, Alert.acknowledged == False
            )
            .all()
        )

    def get_unnotified_alerts(self, bot_instance_id: int) -> List[Alert]:
        """Alias for get_unacknowledged_alerts for API compatibility"""
        return self.get_unacknowledged_alerts(bot_instance_id)

    def acknowledge_alert(self, alert_id: int) -> None:
        """Mark an alert as acknowledged"""
        alert = self.session.query(Alert).filter(Alert.id == alert_id).first()
        if alert:
            alert.acknowledged = True
            alert.acknowledged_at = utc_now()
            self.session.commit()


class PositionSnapshotsRepository:
    """Repository for position snapshots"""

    def __init__(self, session: Session):
        self.session = session

    def get_position_history(self, position_id: str, hours: int = 24) -> List[Any]:
        """Get historical P&L snapshots for a position"""
        # Placeholder: fetch snapshots from a dedicated table if it exists
        # For now, return empty list as the schema may not have a dedicated snapshots table
        return []


class UnitOfWorkRealtime:
    """Unit of Work for realtime data operations"""

    def __init__(self, session: Session):
        self.session = session
        self.positions = PositionRepository(session)
        self.market_data = MarketDataRepository(session)
        self.stats = StatsRepository(session)
        self.alerts = AlertRepository(session)
        self.snapshots = PositionSnapshotsRepository(session)

    def __enter__(self) -> "UnitOfWorkRealtime":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
