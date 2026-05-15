"""
Repository classes for realtime data operations
"""

from typing import Any, List, Optional

from sqlalchemy.orm import Session

from internal.domain.models_realtime import (
    Alert,
    BotStats,
    MarketData,
    Position,
    PositionStatusEnum,
)
from src.shared.time_utils import utc_now


class PositionRepository:
    """Repository for position operations"""

    def __init__(self, session: Session):
        self.session = session

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
        )
        self.session.add(position)
        self.session.commit()
        return position

    def update_position_prices(
        self, position_id: str, current_price1: float, current_price2: float
    ):
        """Update current prices for a position"""
        position = (
            self.session.query(Position)
            .filter(Position.position_id == position_id)
            .first()
        )
        if position:
            position.current_price1 = current_price1
            position.current_price2 = current_price2
            # Calculate unrealized P&L (simplified calculation)
            # This would need more sophisticated logic based on the strategy
            position.unrealized_pnl = 0.0  # Placeholder
            position.unrealized_pnl_pct = 0.0  # Placeholder
            self.session.commit()

    def close_position(self, position_id: str):
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
    ):
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
    ):
        """Calculate and update bot statistics"""
        positions = position_repo.get_open_positions(bot_instance_id)
        stats = self.get_stats(bot_instance_id)

        if not stats:
            stats = BotStats(bot_instance_id=bot_instance_id)
            self.session.add(stats)

        # Calculate stats from positions
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        total_positions = len(positions)

        stats.total_open_positions = total_positions
        stats.total_unrealized_pnl = total_unrealized_pnl
        # Simplified calculations - would need more sophisticated logic
        stats.total_unrealized_pnl_pct = 0.0
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
    ):
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

    def acknowledge_alert(self, alert_id: int):
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
