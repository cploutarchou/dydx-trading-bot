"""
Trade-related database models.

Models:
- TradeLog: Individual trade executed during backtesting
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base


class TradeLog(Base):
    """Individual trade executed during backtesting."""

    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key
    result_id_fk = Column(
        Integer, ForeignKey("backtest_results.id"), index=True, nullable=False
    )

    # Trade details
    trade_number = Column(Integer, nullable=False)
    entry_timestamp = Column(DateTime, nullable=False)
    exit_timestamp = Column(DateTime, nullable=True)

    # Position details
    entry_price_1 = Column(Float, nullable=False)
    entry_price_2 = Column(Float, nullable=False)
    exit_price_1 = Column(Float, nullable=True)
    exit_price_2 = Column(Float, nullable=True)

    quantity_1 = Column(Float, nullable=False)
    quantity_2 = Column(Float, nullable=False)

    side_1 = Column(String(10), nullable=False)  # BUY or SELL
    side_2 = Column(String(10), nullable=False)

    # PnL
    pnl = Column(Float, nullable=True)
    pnl_usd = Column(Float, nullable=True)

    # Entry/Exit signals
    entry_zscore = Column(Float, nullable=True)
    exit_zscore = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    result = relationship("BacktestResult", back_populates="trades")

    __table_args__ = (Index("idx_trade_result", "result_id_fk", "entry_timestamp"),)

    def __repr__(self):
        return f"<TradeLog #{self.trade_number}>"
