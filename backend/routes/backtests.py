"""
Backtest API Routes

Endpoints for retrieving backtest data including candles, positions, and trades.

Routes:
- GET /api/v1/backtests/{runId}/candles - Historical price data
- GET /api/v1/backtests/{runId}/positions - Open/closed positions
- GET /api/v1/backtests/{runId}/trades - Individual trade records
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import (
    BacktestCandle,
    BacktestPosition,
    BacktestRun,
    BacktestTrade,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])


def get_db():
    """
    Dependency to get database session.
    Should be replaced with actual session factory from backend.database
    """
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/{run_id}/candles")
async def get_backtest_candles(
    run_id: int,
    market: Optional[str] = Query(None, description="Market symbol (e.g., BTC-USD)"),
    start_date: Optional[str] = Query(
        None, description="Start date (ISO format: YYYY-MM-DD)"
    ),
    end_date: Optional[str] = Query(
        None, description="End date (ISO format: YYYY-MM-DD)"
    ),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get historical candle data for backtest.

    Query Parameters:
    - market: Market symbol (optional - returns all if not specified)
    - start_date: Filter from date (optional)
    - end_date: Filter to date (optional)

    Response:
    {
        "success": true,
        "data": {
            "run_id": 1,
            "candles": [
                {
                    "market": "BTC-USD",
                    "timestamp": "2025-09-20T00:00:00Z",
                    "open": 45123.50,
                    "high": 45234.75,
                    "low": 45012.25,
                    "close": 45189.00,
                    "volume": 1234567.89
                },
                ...
            ],
            "count": 720,
            "markets": ["BTC-USD", "ETH-USD"]
        },
        "timestamp": "2025-10-20T15:30:00Z"
    }

    Example:
        GET /api/v1/backtests/1/candles?market=BTC-USD&start_date=2025-09-20&end_date=2025-10-20
    """
    try:
        # Verify run exists
        run = db.query(BacktestRun).filter_by(run_id=run_id).first()
        if not run:
            raise HTTPException(
                status_code=404, detail=f"Backtest run {run_id} not found"
            )

        # Parse dates
        start_dt = None
        end_dt = None
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="start_date must be ISO format (YYYY-MM-DD)"
                )
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="end_date must be ISO format (YYYY-MM-DD)"
                )

        # Build query
        query = db.query(BacktestCandle).filter_by(run_id_fk=run_id)

        if market:
            query = query.filter_by(market=market)

        if start_dt:
            query = query.filter(BacktestCandle.timestamp >= start_dt)

        if end_dt:
            query = query.filter(BacktestCandle.timestamp <= end_dt)

        candles = query.order_by(BacktestCandle.timestamp).all()

        # Get unique markets
        markets = (
            db.query(BacktestCandle.market).filter_by(run_id_fk=run_id).distinct().all()
        )
        markets_list = [m[0] for m in markets]

        # Format response
        candles_data = [
            {
                "market": c.market,
                "timestamp": c.timestamp.isoformat() + "Z"
                if c.timestamp.tzinfo is None
                else c.timestamp.isoformat(),
                "open": float(c.open_price),
                "high": float(c.high_price),
                "low": float(c.low_price),
                "close": float(c.close_price),
                "volume": float(c.volume) if c.volume else 0.0,
            }
            for c in candles
        ]

        return {
            "success": True,
            "data": {
                "run_id": run_id,
                "candles": candles_data,
                "count": len(candles_data),
                "markets": markets_list,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get candles for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve candles")


@router.get("/{run_id}/positions")
async def get_backtest_positions(
    run_id: int,
    status: Optional[str] = Query(
        None, description="Position status (OPEN, CLOSED, ALL)"
    ),
    market_1: Optional[str] = Query(None, description="Filter by base market"),
    market_2: Optional[str] = Query(None, description="Filter by quote market"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get positions from backtest.

    Query Parameters:
    - status: OPEN, CLOSED, or ALL (default: ALL)
    - market_1: Base market symbol
    - market_2: Quote market symbol

    Response:
    {
        "success": true,
        "data": {
            "run_id": 1,
            "positions": [
                {
                    "position_id": 1,
                    "market_1": "BTC-USD",
                    "market_2": "ETH-USD",
                    "entry_timestamp": "2025-09-20T12:00:00Z",
                    "exit_timestamp": "2025-09-20T18:00:00Z",
                    "entry_price_m1": 45123.50,
                    "exit_price_m1": 45234.75,
                    "entry_price_m2": 2534.12,
                    "exit_price_m2": 2567.89,
                    "hedge_ratio": 0.056,
                    "entry_zscore": 1.85,
                    "exit_zscore": 0.02,
                    "pnl_m1_usd": 111.25,
                    "pnl_m2_usd": -33.77,
                    "total_pnl_usd": 77.48,
                    "status": "CLOSED"
                },
                ...
            ],
            "count": 42,
            "open_count": 2,
            "closed_count": 40
        },
        "timestamp": "2025-10-20T15:30:00Z"
    }

    Example:
        GET /api/v1/backtests/1/positions?status=CLOSED&market_1=BTC-USD
    """
    try:
        # Verify run exists
        run = db.query(BacktestRun).filter_by(run_id=run_id).first()
        if not run:
            raise HTTPException(
                status_code=404, detail=f"Backtest run {run_id} not found"
            )

        # Build query
        query = db.query(BacktestPosition).filter_by(run_id_fk=run_id)

        if status and status.upper() != "ALL":
            query = query.filter_by(status=status.upper())

        if market_1:
            query = query.filter_by(market_1=market_1)

        if market_2:
            query = query.filter_by(market_2=market_2)

        positions = query.order_by(BacktestPosition.entry_timestamp).all()

        # Format response
        positions_data = [
            {
                "position_id": p.position_id,
                "market_1": p.market_1,
                "market_2": p.market_2,
                "entry_timestamp": p.entry_timestamp.isoformat() + "Z"
                if p.entry_timestamp and p.entry_timestamp.tzinfo is None
                else p.entry_timestamp.isoformat()
                if p.entry_timestamp
                else None,
                "exit_timestamp": p.exit_timestamp.isoformat() + "Z"
                if p.exit_timestamp and p.exit_timestamp.tzinfo is None
                else p.exit_timestamp.isoformat()
                if p.exit_timestamp
                else None,
                "entry_price_m1": float(p.entry_price_m1) if p.entry_price_m1 else None,
                "exit_price_m1": float(p.exit_price_m1) if p.exit_price_m1 else None,
                "entry_price_m2": float(p.entry_price_m2) if p.entry_price_m2 else None,
                "exit_price_m2": float(p.exit_price_m2) if p.exit_price_m2 else None,
                "hedge_ratio": float(p.hedge_ratio) if p.hedge_ratio else None,
                "entry_zscore": float(p.entry_zscore) if p.entry_zscore else None,
                "exit_zscore": float(p.exit_zscore) if p.exit_zscore else None,
                "pnl_m1_usd": float(p.pnl_m1_usd) if p.pnl_m1_usd else 0.0,
                "pnl_m2_usd": float(p.pnl_m2_usd) if p.pnl_m2_usd else 0.0,
                "total_pnl_usd": float(p.pnl_m1_usd or 0) + float(p.pnl_m2_usd or 0),
                "status": p.status or "UNKNOWN",
            }
            for p in positions
        ]

        # Get counts
        open_count = (
            db.query(BacktestPosition)
            .filter_by(run_id_fk=run_id, status="OPEN")
            .count()
        )
        closed_count = (
            db.query(BacktestPosition)
            .filter_by(run_id_fk=run_id, status="CLOSED")
            .count()
        )

        return {
            "success": True,
            "data": {
                "run_id": run_id,
                "positions": positions_data,
                "count": len(positions_data),
                "open_count": open_count,
                "closed_count": closed_count,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get positions for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve positions")


@router.get("/{run_id}/trades")
async def get_backtest_trades(
    run_id: int,
    market_1: Optional[str] = Query(None, description="Filter by base market"),
    market_2: Optional[str] = Query(None, description="Filter by quote market"),
    skip: int = Query(0, ge=0, description="Skip first N trades"),
    limit: int = Query(50, ge=1, le=500, description="Limit results"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get individual trades from backtest (paginated).

    Query Parameters:
    - market_1: Base market filter
    - market_2: Quote market filter
    - skip: Number of trades to skip (pagination)
    - limit: Max trades to return (1-500, default 50)

    Response:
    {
        "success": true,
        "data": {
            "run_id": 1,
            "trades": [
                {
                    "trade_id": "trade_001",
                    "market_1": "BTC-USD",
                    "market_2": "ETH-USD",
                    "entry_timestamp": "2025-09-20T12:00:00Z",
                    "exit_timestamp": "2025-09-20T14:30:00Z",
                    "entry_zscore": 1.82,
                    "exit_zscore": 0.05,
                    "entry_price_m1": 45123.50,
                    "exit_price_m1": 45234.75,
                    "entry_price_m2": 2534.12,
                    "exit_price_m2": 2567.89,
                    "hedge_ratio": 0.0562,
                    "pnl_usd": 77.48,
                    "pnl_pct": 0.77,
                    "duration_hours": 2.5,
                    "win": true
                },
                ...
            ],
            "count": 42,
            "total": 100,
            "skip": 0,
            "limit": 50
        },
        "timestamp": "2025-10-20T15:30:00Z"
    }

    Example:
        GET /api/v1/backtests/1/trades?market_1=BTC-USD&skip=0&limit=25
    """
    try:
        # Verify run exists
        run = db.query(BacktestRun).filter_by(run_id=run_id).first()
        if not run:
            raise HTTPException(
                status_code=404, detail=f"Backtest run {run_id} not found"
            )

        # Build query
        query = db.query(BacktestTrade).filter_by(run_id_fk=run_id)

        if market_1:
            query = query.filter_by(market_1=market_1)

        if market_2:
            query = query.filter_by(market_2=market_2)

        # Get total count before pagination
        total = query.count()

        # Apply pagination
        trades = (
            query.order_by(BacktestTrade.entry_timestamp)
            .offset(skip)
            .limit(limit)
            .all()
        )

        # Format response
        trades_data = [
            {
                "trade_id": t.trade_id,
                "market_1": t.market_1,
                "market_2": t.market_2,
                "entry_timestamp": t.entry_timestamp.isoformat() + "Z"
                if t.entry_timestamp and t.entry_timestamp.tzinfo is None
                else t.entry_timestamp.isoformat()
                if t.entry_timestamp
                else None,
                "exit_timestamp": t.exit_timestamp.isoformat() + "Z"
                if t.exit_timestamp and t.exit_timestamp.tzinfo is None
                else t.exit_timestamp.isoformat()
                if t.exit_timestamp
                else None,
                "entry_zscore": float(t.entry_zscore) if t.entry_zscore else None,
                "exit_zscore": float(t.exit_zscore) if t.exit_zscore else None,
                "entry_price_m1": float(t.entry_price_m1) if t.entry_price_m1 else None,
                "exit_price_m1": float(t.exit_price_m1) if t.exit_price_m1 else None,
                "entry_price_m2": float(t.entry_price_m2) if t.entry_price_m2 else None,
                "exit_price_m2": float(t.exit_price_m2) if t.exit_price_m2 else None,
                "hedge_ratio": float(t.hedge_ratio) if t.hedge_ratio else None,
                "pnl_usd": float(t.pnl_usd) if t.pnl_usd else 0.0,
                "pnl_pct": float(t.pnl_pct) if t.pnl_pct else 0.0,
                "duration_hours": float(t.duration_hours) if t.duration_hours else 0.0,
                "win": bool(t.pnl_usd and t.pnl_usd > 0),
            }
            for t in trades
        ]

        return {
            "success": True,
            "data": {
                "run_id": run_id,
                "trades": trades_data,
                "count": len(trades_data),
                "total": total,
                "skip": skip,
                "limit": limit,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trades for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trades")
