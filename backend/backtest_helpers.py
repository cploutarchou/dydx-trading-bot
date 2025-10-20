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
    """Save a backtest trade to database.

    Args:
        db: SQLAlchemy session
        run_id: BacktestRun.id foreign key
        market_1: First market symbol
        market_2: Second market symbol
        entry_timestamp: When trade was entered
        entry_price_1: Entry price for market 1
        entry_price_2: Entry price for market 2
        entry_z_score: Z-score at entry
        side_1: BUY or SELL for market 1
        side_2: BUY or SELL for market 2
        size_1: Trade size for market 1
        size_2: Trade size for market 2
        hedge_ratio: Hedge ratio between markets
        transaction_fee: Transaction fee percentage
        slippage: Slippage percentage
        exit_timestamp: When trade was exited (optional)
        exit_price_1: Exit price for market 1 (optional)
        exit_price_2: Exit price for market 2 (optional)
        exit_z_score: Z-score at exit (optional)
        pnl: Profit/loss in USD (optional)
        pnl_pct: Profit/loss percentage (optional)
        duration_hours: Trade duration in hours (optional)

    Returns:
        BacktestTrade object

    Raises:
        ValueError: If run_id doesn't exist in BacktestRun table
    """
    try:
        from backend.database import BacktestRun

        # CRITICAL: Verify the BacktestRun exists BEFORE creating trade
        # This prevents foreign key constraint violations
        run_check = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
        if not run_check:
            raise ValueError(
                f"BacktestRun with id={run_id} not found in database. "
                f"Cannot create trade without valid run_id_fk."
            )

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
        db.refresh(trade)  # Refresh to get any database-generated values
        return trade
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        db.rollback()
        raise RuntimeError(
            f"Failed to save backtest trade for run_id={run_id}: {str(e)}"
        ) from e


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
    """Save a backtest position to database.

    Args:
        db: SQLAlchemy session
        run_id: BacktestRun.id foreign key
        market_1: First market symbol
        market_2: Second market symbol
        status: Position status (OPEN, CLOSED, FAILED)
        entry_timestamp: When position was opened
        entry_price_1: Entry price for market 1
        entry_price_2: Entry price for market 2
        entry_z_score: Z-score at entry
        size_1: Position size for market 1
        size_2: Position size for market 2
        side_1: BUY or SELL for market 1
        side_2: BUY or SELL for market 2
        hedge_ratio: Hedge ratio between markets
        current_price_1: Current price for market 1 (optional)
        current_price_2: Current price for market 2 (optional)
        current_z_score: Current Z-score (optional)
        unrealized_pnl: Unrealized P&L (optional)
        close_timestamp: When position was closed (optional)
        realized_pnl: Realized P&L (optional)

    Returns:
        BacktestPosition object

    Raises:
        ValueError: If run_id doesn't exist in BacktestRun table
    """
    try:
        from backend.database import BacktestRun

        # CRITICAL: Verify the BacktestRun exists BEFORE creating position
        # This prevents foreign key constraint violations
        run_check = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
        if not run_check:
            raise ValueError(
                f"BacktestRun with id={run_id} not found in database. "
                f"Cannot create position without valid run_id_fk."
            )

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
        db.refresh(position)  # Refresh to get any database-generated values
        return position
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        db.rollback()
        raise RuntimeError(
            f"Failed to save backtest position for run_id={run_id}: {str(e)}"
        ) from e


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
