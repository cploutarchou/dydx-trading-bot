"""
Backtest Data Persistence Helpers

Handles saving candles, positions, and trades to database during backtesting.
Provides smart caching to avoid duplicate saves and enable frontend chart rendering.
"""

import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def save_backtest_candles(
    db: Session,
    run_id_fk: int,
    market: str,
    candle_data: pd.DataFrame,
    resolution: str = "1HOUR",
) -> int:
    """
    Save OHLCV candles to database for chart rendering and caching.

    Args:
        db: SQLAlchemy database session
        run_id_fk: Backtest run ID (foreign key)
        market: Market symbol (e.g., "BTC-USD")
        candle_data: DataFrame with columns: timestamp, open, high, low, close, volume
        resolution: Candle resolution ("1MIN", "5MINS", "1HOUR", "1DAY", etc.)

    Returns:
        Number of candles saved

    Example:
        >>> df = pd.DataFrame({
        ...     'timestamp': [pd.Timestamp('2025-09-20 08:00:00', tz='UTC')],
        ...     'open': [45000.0], 'high': [45100.0], 'low': [44900.0],
        ...     'close': [45050.0], 'volume': [150.5]
        ... })
        >>> count = save_backtest_candles(db, run_id=1, market="BTC-USD", candle_data=df)
        >>> logger.info(f"Saved {count} candles")
    """
    try:
        from backend.database import BacktestCandle

        candles_saved = 0

        for idx, row in candle_data.iterrows():
            # Ensure timestamp is timezone-aware UTC
            ts = pd.Timestamp(row["timestamp"], tz="UTC")

            candle = BacktestCandle(
                run_id_fk=run_id_fk,
                market=market,
                timestamp=ts.to_pydatetime(),
                resolution=resolution,
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                close_price=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
                trades_count=int(row.get("trades_count", 0)),
            )

            db.add(candle)
            candles_saved += 1

            # Commit in batches of 100 for performance
            if candles_saved % 100 == 0:
                db.commit()

        db.commit()  # Final commit for remaining records
        logger.info(
            "Saved %d candles for %s (run_id=%d)", candles_saved, market, run_id_fk
        )
        return candles_saved

    except Exception as e:
        logger.error(
            "Failed to save candles for %s (run_id=%d): %s", market, run_id_fk, e
        )
        db.rollback()
        return 0


def save_backtest_position_entry(
    db: Session,
    run_id_fk: int,
    market_1: str,
    market_2: str,
    entry_timestamp: datetime,
    entry_price_1: float,
    entry_price_2: float,
    entry_z_score: float,
    size_1: float,
    size_2: float,
    side_1: str,
    side_2: str,
    hedge_ratio: float,
) -> Optional[str]:
    """
    Save position entry (open trade) to database.

    Args:
        db: SQLAlchemy database session
        run_id_fk: Backtest run ID
        market_1: First market (e.g., "BTC-USD")
        market_2: Second market (e.g., "ETH-USD")
        entry_timestamp: Timestamp when position was opened
        entry_price_1: Entry price for market_1
        entry_price_2: Entry price for market_2
        entry_z_score: Z-score at entry
        size_1: Position size for market_1
        size_2: Position size for market_2
        side_1: Side for market_1 ("BUY" or "SELL")
        side_2: Side for market_2 ("BUY" or "SELL")
        hedge_ratio: Hedge ratio used for the pair

    Returns:
        Position ID if saved successfully, None otherwise

    Example:
        >>> position_id = save_backtest_position_entry(
        ...     db, run_id_fk=1, market_1="BTC-USD", market_2="ETH-USD",
        ...     entry_timestamp=datetime.now(tz=UTC),
        ...     entry_price_1=45000, entry_price_2=2500, entry_z_score=1.8,
        ...     size_1=0.01, size_2=0.2, side_1="BUY", side_2="SELL",
        ...     hedge_ratio=0.05
        ... )
    """
    try:
        from backend.database import BacktestPosition

        position_id = f"{market_1}_{market_2}_{int(entry_timestamp.timestamp())}"

        position = BacktestPosition(
            run_id_fk=run_id_fk,
            position_id=position_id,
            market_1=market_1,
            market_2=market_2,
            status="OPEN",
            entry_timestamp=entry_timestamp,
            entry_price_1=entry_price_1,
            entry_price_2=entry_price_2,
            entry_z_score=entry_z_score,
            current_price_1=entry_price_1,
            current_price_2=entry_price_2,
            current_z_score=entry_z_score,
            size_1=size_1,
            size_2=size_2,
            side_1=side_1,
            side_2=side_2,
            hedge_ratio=hedge_ratio,
            unrealized_pnl=0.0,
        )

        db.add(position)
        db.commit()

        logger.debug(
            "Saved position entry: %s/%s (Z=%.2f)", market_1, market_2, entry_z_score
        )
        return position_id

    except Exception as e:
        logger.error("Failed to save position entry: %s", e)
        db.rollback()
        return None


def update_backtest_position_exit(
    db: Session,
    position_id: str,
    exit_timestamp: datetime,
    exit_price_1: float,
    exit_price_2: float,
    exit_z_score: float,
    realized_pnl: float,
) -> bool:
    """
    Update position with exit details (close trade).

    Args:
        db: SQLAlchemy database session
        position_id: Position ID (from save_backtest_position_entry)
        exit_timestamp: Timestamp when position was closed
        exit_price_1: Exit price for market_1
        exit_price_2: Exit price for market_2
        exit_z_score: Z-score at exit
        realized_pnl: Realized profit/loss

    Returns:
        True if updated successfully, False otherwise

    Example:
        >>> success = update_backtest_position_exit(
        ...     db, position_id="BTC-USD_ETH-USD_1695225600",
        ...     exit_timestamp=datetime.now(tz=UTC),
        ...     exit_price_1=44950, exit_price_2=2480, exit_z_score=0.05,
        ...     realized_pnl=125.50
        ... )
    """
    try:
        from backend.database import BacktestPosition

        position = db.query(BacktestPosition).filter_by(position_id=position_id).first()

        if not position:
            logger.warning("Position not found: %s", position_id)
            return False

        position.status = "CLOSED"
        position.close_timestamp = exit_timestamp
        position.exit_price_1 = exit_price_1
        position.exit_price_2 = exit_price_2
        position.exit_z_score = exit_z_score
        position.realized_pnl = realized_pnl

        # Calculate duration in hours
        if position.entry_timestamp:
            duration = (
                exit_timestamp - position.entry_timestamp
            ).total_seconds() / 3600
            position.duration_hours = duration

        db.commit()

        logger.debug("Updated position exit: %s (PnL=%.2f)", position_id, realized_pnl)
        return True

    except Exception as e:
        logger.error("Failed to update position exit: %s", e)
        db.rollback()
        return False


def save_backtest_trade(
    db: Session,
    run_id_fk: int,
    trade_id: str,
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
    exit_timestamp: Optional[datetime] = None,
    exit_price_1: Optional[float] = None,
    exit_price_2: Optional[float] = None,
    exit_z_score: Optional[float] = None,
    pnl: Optional[float] = None,
    pnl_pct: Optional[float] = None,
    hedge_ratio: float = 0.0,
    transaction_fee: float = 0.0005,
    slippage: float = 0.001,
) -> bool:
    """
    Save complete trade record (entry + exit) to database.

    Args:
        db: SQLAlchemy database session
        run_id_fk: Backtest run ID
        trade_id: Unique trade identifier
        market_1: First market
        market_2: Second market
        entry_timestamp: Entry timestamp
        entry_price_1: Entry price for market_1
        entry_price_2: Entry price for market_2
        entry_z_score: Z-score at entry
        side_1: Side for market_1
        side_2: Side for market_2
        size_1: Position size for market_1
        size_2: Position size for market_2
        exit_timestamp: Exit timestamp (optional, for open trades)
        exit_price_1: Exit price for market_1 (optional)
        exit_price_2: Exit price for market_2 (optional)
        exit_z_score: Z-score at exit (optional)
        pnl: Profit/loss in USD (optional)
        pnl_pct: Profit/loss percentage (optional)
        hedge_ratio: Hedge ratio used
        transaction_fee: Transaction fee percentage
        slippage: Slippage percentage

    Returns:
        True if saved successfully, False otherwise

    Example:
        >>> success = save_backtest_trade(
        ...     db, run_id_fk=1, trade_id="trade_123",
        ...     market_1="BTC-USD", market_2="ETH-USD",
        ...     entry_timestamp=datetime.now(tz=UTC),
        ...     entry_price_1=45000, entry_price_2=2500, entry_z_score=1.8,
        ...     side_1="BUY", side_2="SELL", size_1=0.01, size_2=0.2,
        ...     exit_timestamp=datetime.now(tz=UTC),
        ...     exit_price_1=44950, exit_price_2=2480, exit_z_score=0.05,
        ...     pnl=125.50, pnl_pct=2.1, hedge_ratio=0.05
        ... )
    """
    try:
        from backend.database import BacktestTrade

        # Calculate duration if both timestamps present
        duration_hours = None
        if exit_timestamp and entry_timestamp:
            duration_hours = (exit_timestamp - entry_timestamp).total_seconds() / 3600

        trade = BacktestTrade(
            run_id_fk=run_id_fk,
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
            exit_timestamp=exit_timestamp,
            exit_price_1=exit_price_1,
            exit_price_2=exit_price_2,
            exit_z_score=exit_z_score,
            pnl=pnl,
            pnl_pct=pnl_pct,
            duration_hours=duration_hours,
            hedge_ratio=hedge_ratio,
            transaction_fee=transaction_fee,
            slippage=slippage,
        )

        db.add(trade)
        db.commit()

        logger.debug("Saved trade: %s (PnL=%.2f)", trade_id, pnl or 0)
        return True

    except Exception as e:
        logger.error("Failed to save trade %s: %s", trade_id, e)
        db.rollback()
        return False


def get_backtest_candles(
    db: Session,
    run_id_fk: int,
    market: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List:
    """
    Retrieve candles from database with optional filtering.

    Args:
        db: SQLAlchemy database session
        run_id_fk: Backtest run ID
        market: Optional market filter (e.g., "BTC-USD")
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of BacktestCandle records

    Example:
        >>> candles = get_backtest_candles(
        ...     db, run_id_fk=1, market="BTC-USD",
        ...     start_date=datetime(2025, 9, 20),
        ...     end_date=datetime(2025, 10, 20)
        ... )
        >>> for c in candles:
        ...     print(f"{c.timestamp}: O{c.open_price} C{c.close_price}")
    """
    try:
        from backend.database import BacktestCandle

        query = db.query(BacktestCandle).filter_by(run_id_fk=run_id_fk)

        if market:
            query = query.filter_by(market=market)

        if start_date:
            query = query.filter(BacktestCandle.timestamp >= start_date)

        if end_date:
            query = query.filter(BacktestCandle.timestamp <= end_date)

        return query.order_by(BacktestCandle.timestamp).all()

    except Exception as e:
        logger.error("Failed to retrieve candles: %s", e)
        return []


def get_backtest_positions(
    db: Session,
    run_id_fk: int,
    status: Optional[str] = None,
) -> List:
    """
    Retrieve positions from database with optional status filter.

    Args:
        db: SQLAlchemy database session
        run_id_fk: Backtest run ID
        status: Optional status filter ("OPEN", "CLOSED", "FAILED")

    Returns:
        List of BacktestPosition records

    Example:
        >>> closed_positions = get_backtest_positions(db, run_id_fk=1, status="CLOSED")
        >>> for pos in closed_positions:
        ...     print(f"{pos.market_1}/{pos.market_2}: PnL={pos.realized_pnl}")
    """
    try:
        from backend.database import BacktestPosition

        query = db.query(BacktestPosition).filter_by(run_id_fk=run_id_fk)

        if status:
            query = query.filter_by(status=status)

        return query.order_by(BacktestPosition.entry_timestamp).all()

    except Exception as e:
        logger.error("Failed to retrieve positions: %s", e)
        return []


def get_backtest_trades(
    db: Session,
    run_id_fk: int,
    market_1: Optional[str] = None,
    market_2: Optional[str] = None,
) -> List:
    """
    Retrieve trades from database with optional market filtering.

    Args:
        db: SQLAlchemy database session
        run_id_fk: Backtest run ID
        market_1: Optional first market filter
        market_2: Optional second market filter

    Returns:
        List of BacktestTrade records

    Example:
        >>> btc_eth_trades = get_backtest_trades(
        ...     db, run_id_fk=1, market_1="BTC-USD", market_2="ETH-USD"
        ... )
        >>> total_pnl = sum(t.pnl for t in btc_eth_trades if t.pnl)
    """
    try:
        from backend.database import BacktestTrade

        query = db.query(BacktestTrade).filter_by(run_id_fk=run_id_fk)

        if market_1:
            query = query.filter_by(market_1=market_1)

        if market_2:
            query = query.filter_by(market_2=market_2)

        return query.order_by(BacktestTrade.entry_timestamp).all()

    except Exception as e:
        logger.error("Failed to retrieve trades: %s", e)
        return []
