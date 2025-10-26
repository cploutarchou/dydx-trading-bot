"""Helper functions for saving backtest trades, orders, and positions to database."""

import uuid
from datetime import datetime
from database import execute_query


def save_backtest_trade(
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
) -> dict:
    """Save a backtest trade to database using pure SQL."""
    # Verify BacktestRun exists
    run_check = execute_query(
        "SELECT id FROM backtest_runs WHERE id = %s",
        (run_id,),
        fetchone=True,
    )
    if not run_check:
        raise ValueError(
            f"BacktestRun with id={run_id} not found in database. "
            f"Cannot create trade without valid run_id_fk."
        )

    trade_id = f"trade_{uuid.uuid4().hex[:8]}"
    execute_query(
        """
        INSERT INTO backtest_trades (
            run_id_fk, trade_id, market_1, market_2, entry_timestamp, entry_price_1, entry_price_2, entry_z_score, side_1, side_2, size_1, size_2, hedge_ratio, transaction_fee, slippage, exit_timestamp, exit_price_1, exit_price_2, exit_z_score, pnl, pnl_pct, duration_hours
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            run_id,
            trade_id,
            market_1,
            market_2,
            entry_timestamp,
            entry_price_1,
            entry_price_2,
            entry_z_score,
            side_1,
            side_2,
            size_1,
            size_2,
            hedge_ratio,
            transaction_fee,
            slippage,
            exit_timestamp,
            exit_price_1,
            exit_price_2,
            exit_z_score,
            pnl,
            pnl_pct,
            duration_hours,
        ),
        commit=True,
    )
    trade = execute_query(
        "SELECT * FROM backtest_trades WHERE trade_id = %s",
        (trade_id,),
        fetchone=True,
    )
    return trade


def save_backtest_position(
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
) -> dict:
    """Save a backtest position to database using pure SQL."""
    # Verify BacktestRun exists
    run_check = execute_query(
        "SELECT id FROM backtest_runs WHERE id = %s",
        (run_id,),
        fetchone=True,
    )
    if not run_check:
        raise ValueError(
            f"BacktestRun with id={run_id} not found in database. "
            f"Cannot create position without valid run_id_fk."
        )

    position_id = f"pos_{uuid.uuid4().hex[:8]}"
    execute_query(
        """
        INSERT INTO backtest_positions (
            run_id_fk, position_id, market_1, market_2, status, entry_timestamp, entry_price_1, entry_price_2, entry_z_score, size_1, size_2, side_1, side_2, hedge_ratio, current_price_1, current_price_2, current_z_score, unrealized_pnl, close_timestamp, realized_pnl
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            run_id,
            position_id,
            market_1,
            market_2,
            status,
            entry_timestamp,
            entry_price_1,
            entry_price_2,
            entry_z_score,
            size_1,
            size_2,
            side_1,
            side_2,
            hedge_ratio,
            current_price_1,
            current_price_2,
            current_z_score,
            unrealized_pnl,
            close_timestamp,
            realized_pnl,
        ),
        commit=True,
    )
    position = execute_query(
        "SELECT * FROM backtest_positions WHERE position_id = %s",
        (position_id,),
        fetchone=True,
    )
    return position


def update_backtest_position(
    position_id: str,
    status: str | None = None,
    current_price_1: float | None = None,
    current_price_2: float | None = None,
    current_z_score: float | None = None,
    unrealized_pnl: float | None = None,
    close_timestamp: datetime | None = None,
    realized_pnl: float | None = None,
) -> dict:
    """Update an existing backtest position using pure SQL."""
    # Build update fields
    fields = []
    values = []
    if status is not None:
        fields.append("status = %s")
        values.append(status)
    if current_price_1 is not None:
        fields.append("current_price_1 = %s")
        values.append(current_price_1)
    if current_price_2 is not None:
        fields.append("current_price_2 = %s")
        values.append(current_price_2)
    if current_z_score is not None:
        fields.append("current_z_score = %s")
        values.append(current_z_score)
    if unrealized_pnl is not None:
        fields.append("unrealized_pnl = %s")
        values.append(unrealized_pnl)
    if close_timestamp is not None:
        fields.append("close_timestamp = %s")
        values.append(close_timestamp)
    if realized_pnl is not None:
        fields.append("realized_pnl = %s")
        values.append(realized_pnl)
    if not fields:
        raise ValueError("No fields to update for backtest position.")
    values.append(position_id)
    execute_query(
        f"UPDATE backtest_positions SET {', '.join(fields)} WHERE position_id = %s",
        tuple(values),
        commit=True,
    )
    position = execute_query(
        "SELECT * FROM backtest_positions WHERE position_id = %s",
        (position_id,),
        fetchone=True,
    )
    return position