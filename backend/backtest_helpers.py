"""Helper functions for saving backtest trades, orders, and positions to database."""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from backend.database import BacktestPosition, BacktestTrade


def save_backtest_trade(
    db: Session,
    run_id: int,
    market_1: str,
    market_2: str,
    entry_timestamp: datetime,
    entry_price_1: float,
    entry_price_2: float,
    entry_z_score: float,
    side_1: str,
    side_2: str,
    size_1: float,
    size_2: float,
    hedge_ratio: float,
    transaction_fee: float,
    slippage: float,
    exit_timestamp: datetime | None = None,
    exit_price_1: float | None = None,
    exit_price_2: float | None = None,
    exit_z_score: float | None = None,
    pnl: float | None = None,
    pnl_pct: float | None = None,
    duration_hours: float | None = None,
) -> BacktestTrade:
    """Save a backtest trade to database."""
    trade_id = f"trade_{uuid.uuid4().hex[:8]}"

    trade = BacktestTrade(
        run_id_fk=run_id,
        trade_id=trade_id,
        market_1=market_1,
        market_2=market_2,
        entry_timestamp=entry_timestamp,
        entry_price_1=entry_price_1,
        entry_price_2=entry_price_2,
        entry_z_score=entry_z_score,
        side_1=side_1,
        side_2=side_2,
        size_1=size_1,
        size_2=size_2,
        hedge_ratio=hedge_ratio,
        transaction_fee=transaction_fee,
        slippage=slippage,
        exit_timestamp=exit_timestamp,
        exit_price_1=exit_price_1,
        exit_price_2=exit_price_2,
        exit_z_score=exit_z_score,
        pnl=pnl,
        pnl_pct=pnl_pct,
        duration_hours=duration_hours,
    )

    db.add(trade)
    db.commit()
    return trade


def save_backtest_position(
    db: Session,
    run_id: int,
    market_1: str,
    market_2: str,
    status: str,
    entry_timestamp: datetime,
    entry_price_1: float,
    entry_price_2: float,
    entry_z_score: float,
    size_1: float,
    size_2: float,
    side_1: str,
    side_2: str,
    hedge_ratio: float,
    current_price_1: float | None = None,
    current_price_2: float | None = None,
    current_z_score: float | None = None,
    unrealized_pnl: float | None = None,
    close_timestamp: datetime | None = None,
    realized_pnl: float | None = None,
) -> BacktestPosition:
    """Save a backtest position to database."""
    position_id = f"pos_{uuid.uuid4().hex[:8]}"

    position = BacktestPosition(
        run_id_fk=run_id,
        position_id=position_id,
        market_1=market_1,
        market_2=market_2,
        status=status,
        entry_timestamp=entry_timestamp,
        entry_price_1=entry_price_1,
        entry_price_2=entry_price_2,
        entry_z_score=entry_z_score,
        size_1=size_1,
        size_2=size_2,
        side_1=side_1,
        side_2=side_2,
        hedge_ratio=hedge_ratio,
        current_price_1=current_price_1,
        current_price_2=current_price_2,
        current_z_score=current_z_score,
        unrealized_pnl=unrealized_pnl,
        close_timestamp=close_timestamp,
        realized_pnl=realized_pnl,
    )

    db.add(position)
    db.commit()
    return position


def update_backtest_position(
    db: Session,
    position: BacktestPosition,
    status: str | None = None,
    current_price_1: float | None = None,
    current_price_2: float | None = None,
    current_z_score: float | None = None,
    unrealized_pnl: float | None = None,
    close_timestamp: datetime | None = None,
    realized_pnl: float | None = None,
) -> BacktestPosition:
    """Update an existing backtest position."""
    if status is not None:
        position.status = status
    if current_price_1 is not None:
        position.current_price_1 = current_price_1
    if current_price_2 is not None:
        position.current_price_2 = current_price_2
    if current_z_score is not None:
        position.current_z_score = current_z_score
    if unrealized_pnl is not None:
        position.unrealized_pnl = unrealized_pnl
    if close_timestamp is not None:
        position.close_timestamp = close_timestamp
    if realized_pnl is not None:
        position.realized_pnl = realized_pnl

    db.commit()
    return position
