"""
Repository layer for real-time data
Handles live positions, market data, and streaming operations
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from models_realtime import (
    AlertEvent,
    BotRealTimeStats,
    LiveMarketData,
    LivePosition,
    PositionSnapshot,
    PositionStatusEnum,
)

logger = logging.getLogger(__name__)


class LivePositionRepository:
    """Repository for real-time position management"""

    def __init__(self, session: Session):
        self.session = session

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
        entry_fees: float = 0.0,
        z_score: Optional[float] = None,
        hedge_ratio: Optional[float] = None,
        half_life: Optional[float] = None,
        correlation: Optional[float] = None,
    ) -> LivePosition:
        """Create new live position"""
        entry_cost = (
            (entry_price1 * entry_size1) + (entry_price2 * entry_size2) + entry_fees
        )

        position = LivePosition(
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
            entry_fees=entry_fees,
            entry_time=datetime.utcnow(),
            current_price1=entry_price1,
            current_price2=entry_price2,
            current_size1=entry_size1,
            current_size2=entry_size2,
            entry_cost=entry_cost,
            current_value=entry_cost,
            z_score_entry=z_score,
            z_score_current=z_score,
            hedge_ratio=hedge_ratio,
            half_life=half_life,
            correlation=correlation,
        )
        self.session.add(position)
        self.session.commit()
        logger.info(f"Created position {position_id}: {pair1}/{pair2}")
        return position

    def get_open_positions(self, bot_instance_id: int) -> List[LivePosition]:
        """Get all open positions for a bot"""
        return (
            self.session.query(LivePosition)
            .filter(
                and_(
                    LivePosition.bot_instance_id == bot_instance_id,
                    LivePosition.status == PositionStatusEnum.OPEN,
                )
            )
            .all()
        )

    def get_all_positions(self, bot_instance_id: int) -> List[LivePosition]:
        """Get all positions (open and closed) for a bot"""
        return (
            self.session.query(LivePosition)
            .filter(LivePosition.bot_instance_id == bot_instance_id)
            .order_by(desc(LivePosition.updated_at))
            .all()
        )

    def get_position_by_id(self, position_id: str) -> Optional[LivePosition]:
        """Get position by ID"""
        return (
            self.session.query(LivePosition)
            .filter(LivePosition.position_id == position_id)
            .first()
        )

    def update_position_prices(
        self,
        position_id: str,
        current_price1: float,
        current_price2: float,
        z_score: Optional[float] = None,
    ) -> LivePosition:
        """Update position with current market prices"""
        position = self.get_position_by_id(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        position.current_price1 = current_price1
        position.current_price2 = current_price2

        # Calculate current value
        position.current_value = (current_price1 * position.current_size1) + (
            current_price2 * position.current_size2
        )

        # Calculate unrealized P&L
        position.unrealized_pnl = position.current_value - position.entry_cost
        position.unrealized_pnl_pct = (
            (position.unrealized_pnl / position.entry_cost * 100)
            if position.entry_cost
            else 0
        )

        # Update z-score if provided
        if z_score is not None:
            position.z_score_current = z_score

        position.updated_at = datetime.utcnow()
        self.session.commit()
        return position

    def partial_close_position(
        self,
        position_id: str,
        close_size1: float,
        close_size2: float,
        close_price1: float,
        close_price2: float,
        close_fees: float = 0.0,
    ) -> tuple[LivePosition, float]:
        """Partially close a position and return realized P&L"""
        position = self.get_position_by_id(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        # Calculate exit proceeds
        exit_proceeds = (
            (close_price1 * close_size1) + (close_price2 * close_size2) - close_fees
        )

        # Calculate proportional entry cost
        proportion_closed = (
            close_size1 / position.entry_size1 if position.entry_size1 > 0 else 0
        )
        proportional_entry_cost = (
            (position.entry_price1 * close_size1)
            + (position.entry_price2 * close_size2)
            + (position.entry_fees * proportion_closed)
        )

        # Calculate realized P&L
        realized_pnl = exit_proceeds - proportional_entry_cost

        # Update position
        position.current_size1 -= close_size1
        position.current_size2 -= close_size2
        position.realized_pnl += realized_pnl

        # Check if fully closed
        if position.current_size1 <= 0 and position.current_size2 <= 0:
            position.status = PositionStatusEnum.CLOSED
            position.closed_at = datetime.utcnow()
        else:
            position.status = PositionStatusEnum.PARTIALLY_CLOSED

        position.updated_at = datetime.utcnow()
        self.session.commit()
        logger.info(
            f"Partially closed position {position_id}, realized P&L: ${realized_pnl:.2f}"
        )
        return position, realized_pnl

    def close_position(self, position_id: str) -> LivePosition:
        """Close a position"""
        position = self.get_position_by_id(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        position.status = PositionStatusEnum.CLOSED
        position.closed_at = datetime.utcnow()
        position.updated_at = datetime.utcnow()
        self.session.commit()
        logger.info(f"Closed position {position_id}")
        return position

    def get_position_statistics(self, bot_instance_id: int) -> Dict[str, Any]:
        """Get position statistics for a bot"""
        open_positions = self.get_open_positions(bot_instance_id)
        all_positions = self.get_all_positions(bot_instance_id)

        total_unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)
        total_realized_pnl = sum(
            p.realized_pnl
            for p in all_positions
            if p.status == PositionStatusEnum.CLOSED
        )

        winning_positions = len([p for p in all_positions if (p.realized_pnl or 0) > 0])
        losing_positions = len([p for p in all_positions if (p.realized_pnl or 0) < 0])

        return {
            "open_positions": len(open_positions),
            "closed_positions": len(
                [p for p in all_positions if p.status == PositionStatusEnum.CLOSED]
            ),
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "total_pnl": total_unrealized_pnl + total_realized_pnl,
            "winning_positions": winning_positions,
            "losing_positions": losing_positions,
            "win_rate": (
                winning_positions / (winning_positions + losing_positions) * 100
            )
            if (winning_positions + losing_positions) > 0
            else 0,
        }


class LiveMarketDataRepository:
    """Repository for real-time market data"""

    def __init__(self, session: Session):
        self.session = session

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
    ) -> LiveMarketData:
        """Create or update market data"""
        market_data = (
            self.session.query(LiveMarketData)
            .filter(
                and_(
                    LiveMarketData.bot_instance_id == bot_instance_id,
                    LiveMarketData.symbol == symbol,
                )
            )
            .first()
        )

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
            market_data.timestamp = datetime.utcnow()
        else:
            # Create new
            market_data = LiveMarketData(
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

    def get_market_data(
        self, bot_instance_id: int, symbol: str
    ) -> Optional[LiveMarketData]:
        """Get latest market data for symbol"""
        return (
            self.session.query(LiveMarketData)
            .filter(
                and_(
                    LiveMarketData.bot_instance_id == bot_instance_id,
                    LiveMarketData.symbol == symbol,
                )
            )
            .order_by(desc(LiveMarketData.timestamp))
            .first()
        )

    def get_all_market_data(self, bot_instance_id: int) -> List[LiveMarketData]:
        """Get latest market data for all symbols"""
        subquery = (
            self.session.query(
                LiveMarketData.symbol,
                func.max(LiveMarketData.id).label("max_id"),
            )
            .filter(LiveMarketData.bot_instance_id == bot_instance_id)
            .group_by(LiveMarketData.symbol)
            .subquery()
        )

        return (
            self.session.query(LiveMarketData)
            .filter(LiveMarketData.id.in_(self.session.query(subquery.c.max_id)))
            .all()
        )


class BotRealTimeStatsRepository:
    """Repository for real-time bot statistics"""

    def __init__(self, session: Session):
        self.session = session

    def upsert_stats(self, bot_instance_id: int, **stats_data) -> BotRealTimeStats:
        """Create or update real-time statistics"""
        stats = (
            self.session.query(BotRealTimeStats)
            .filter(BotRealTimeStats.bot_instance_id == bot_instance_id)
            .first()
        )

        if stats:
            # Update existing
            for key, value in stats_data.items():
                if hasattr(stats, key):
                    setattr(stats, key, value)
            stats.updated_at = datetime.utcnow()
        else:
            # Create new
            stats = BotRealTimeStats(bot_instance_id=bot_instance_id, **stats_data)
            self.session.add(stats)

        self.session.commit()
        return stats

    def get_stats(self, bot_instance_id: int) -> Optional[BotRealTimeStats]:
        """Get real-time statistics for bot"""
        return (
            self.session.query(BotRealTimeStats)
            .filter(BotRealTimeStats.bot_instance_id == bot_instance_id)
            .first()
        )

    def calculate_and_update_stats(
        self, bot_instance_id: int, position_repo: LivePositionRepository
    ) -> BotRealTimeStats:
        """Calculate stats from positions and update"""
        positions = position_repo.get_open_positions(bot_instance_id)

        total_position_value = sum(
            p.current_value for p in positions if p.current_value
        )
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        total_unrealized_pnl_pct = (
            (total_unrealized_pnl / total_position_value * 100)
            if total_position_value
            else 0
        )

        max_unrealized_pnl = max([p.unrealized_pnl for p in positions], default=0)
        min_unrealized_pnl = min([p.unrealized_pnl for p in positions], default=0)

        return self.upsert_stats(
            bot_instance_id,
            total_open_positions=len(positions),
            total_position_value=total_position_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_unrealized_pnl_pct=total_unrealized_pnl_pct,
            max_unrealized_pnl=max_unrealized_pnl,
            min_unrealized_pnl=min_unrealized_pnl,
            updated_at=datetime.utcnow(),
        )


class PositionSnapshotRepository:
    """Repository for position snapshots"""

    def __init__(self, session: Session):
        self.session = session

    def create_snapshot(
        self,
        bot_instance_id: int,
        position: LivePosition,
    ) -> PositionSnapshot:
        """Create snapshot of current position state"""
        snapshot = PositionSnapshot(
            bot_instance_id=bot_instance_id,
            position_id=position.position_id,
            pair1=position.pair1,
            pair2=position.pair2,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_pct=position.unrealized_pnl_pct,
            current_price1=position.current_price1,
            current_price2=position.current_price2,
            z_score=position.z_score_current,
        )
        self.session.add(snapshot)
        self.session.commit()
        return snapshot

    def get_position_history(
        self, position_id: str, hours: int = 24
    ) -> List[PositionSnapshot]:
        """Get snapshot history for a position"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.session.query(PositionSnapshot)
            .filter(
                and_(
                    PositionSnapshot.position_id == position_id,
                    PositionSnapshot.timestamp >= cutoff_time,
                )
            )
            .order_by(PositionSnapshot.timestamp)
            .all()
        )


class AlertEventRepository:
    """Repository for alert events"""

    def __init__(self, session: Session):
        self.session = session

    def create_alert(
        self,
        bot_instance_id: int,
        alert_type: str,
        severity: str,
        message: str,
        details: Optional[Dict] = None,
        position_id: Optional[str] = None,
    ) -> AlertEvent:
        """Create alert event"""
        alert = AlertEvent(
            bot_instance_id=bot_instance_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details or {},
            position_id=position_id,
        )
        self.session.add(alert)
        self.session.commit()
        logger.info(f"Created alert: {alert_type} - {message}")
        return alert

    def get_unnotified_alerts(self, bot_instance_id: int) -> List[AlertEvent]:
        """Get alerts that haven't been sent yet"""
        return (
            self.session.query(AlertEvent)
            .filter(
                and_(
                    AlertEvent.bot_instance_id == bot_instance_id,
                    AlertEvent.notified == False,
                )
            )
            .order_by(desc(AlertEvent.timestamp))
            .all()
        )

    def mark_notified(self, alert_id: int, via: List[str]) -> AlertEvent:
        """Mark alert as notified"""
        alert = self.session.query(AlertEvent).filter(AlertEvent.id == alert_id).first()
        if alert:
            alert.notified = True
            alert.notified_via = {v: True for v in via}
            self.session.commit()
        return alert


class UnitOfWorkRealtime:
    """Unit of Work for real-time operations"""

    def __init__(self, session: Session):
        self.session = session
        self.positions = LivePositionRepository(session)
        self.market_data = LiveMarketDataRepository(session)
        self.stats = BotRealTimeStatsRepository(session)
        self.snapshots = PositionSnapshotRepository(session)
        self.alerts = AlertEventRepository(session)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()
