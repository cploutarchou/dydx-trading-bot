"""
Enhanced Backtest Results Endpoints
Senior-grade pagination, filtering, and data validation
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import (
    BacktestResult,
    BacktestTrade,
)
from main import ApiResponse

from services import BacktestRunService


class BacktestResultsEndpoint:
    """
    Encapsulates enhanced backtest results endpoints with:
    - Accurate data validation
    - Intelligent pagination
    - Filtering and sorting
    - Prefetch optimization
    """

    @staticmethod
    def get_backtest_results_enhanced(
        db: Session,
        run_id: str,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "pnl",
        sort_order: str = "desc",
        filter_by_status: Optional[str] = None,
        min_win_rate: Optional[float] = None,
        min_trades: Optional[int] = None,
        current_user_id: int = None,
    ) -> ApiResponse:
        """
        Enhanced backtest results endpoint with validation and filtering.

        Args:
            db: Database session
            run_id: Backtest run ID
            limit: Max results per page (max 100)
            offset: Pagination offset
            sort_by: Sort field (pnl, win_rate, sharpe_ratio, etc.)
            sort_order: asc or desc
            filter_by_status: Filter positions by status
            min_win_rate: Filter pairs with minimum win rate %
            min_trades: Filter pairs with minimum number of trades
            current_user_id: Current user ID for authorization

        Returns:
            ApiResponse with paginated, validated results
        """
        # Validate limits
        limit = min(limit, 100)  # Cap at 100
        offset = max(offset, 0)

        # Get run
        run = BacktestRunService.get_run_by_run_id(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Backtest not found")

        # Authorize
        if run.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Build query
        query = db.query(BacktestResult).filter(BacktestResult.run_id_fk == run.id)

        # Apply filters
        if min_win_rate is not None:
            query = query.filter(BacktestResult.win_rate >= min_win_rate)

        if min_trades is not None:
            query = query.filter(BacktestResult.total_trades >= min_trades)

        # Validate sort field
        valid_sorts = [
            "pnl",
            "win_rate",
            "sharpe_ratio",
            "total_trades",
            "avg_trade_duration_hours",
            "profit_factor",
        ]
        if sort_by not in valid_sorts:
            sort_by = "pnl"

        # Apply sort
        sort_column = getattr(BacktestResult, sort_by)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Get total before pagination
        total = query.count()

        # Paginate
        results = query.offset(offset).limit(limit).all()

        # Format with validation
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "id": result.id,
                    "pair": f"{result.market_1}/{result.market_2}",
                    "market_1": result.market_1,
                    "market_2": result.market_2,
                    "total_trades": result.total_trades or 0,
                    "profitable_trades": result.profitable_trades or 0,
                    "losing_trades": result.losing_trades or 0,
                    "win_rate": round(result.win_rate or 0, 2),
                    "pnl_usd": round(result.pnl_usd or 0, 2),
                    "avg_win": round(result.avg_win or 0, 2),
                    "avg_loss": round(result.avg_loss or 0, 2),
                    "profit_factor": round(result.profit_factor or 1.0, 2),
                    "max_drawdown": round(result.max_drawdown or 0, 2),
                    "sharpe_ratio": round(result.sharpe_ratio or 0, 2)
                    if result.sharpe_ratio
                    else "N/A",
                    "sortino_ratio": round(result.sortino_ratio or 0, 2)
                    if result.sortino_ratio
                    else "N/A",
                    "avg_trade_duration_hours": round(
                        result.avg_trade_duration_hours or 0, 1
                    ),
                    "cointegration_score": round(result.cointegration_score or 0, 3),
                    "zscore_mean": round(result.zscore_mean or 0, 3),
                    "zscore_std": round(result.zscore_std or 0, 3),
                }
            )

        return {
            "success": True,
            "message": f"Retrieved {len(formatted_results)} results",
            "data": {
                "results": formatted_results,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "returned": len(formatted_results),
                    "pages": (total + limit - 1) // limit,  # Ceil division
                    "current_page": (offset // limit) + 1 if limit > 0 else 1,
                },
                "metadata": {
                    "run_id": run.run_id,
                    "status": run.status,
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                },
            },
            "timestamp": None,  # Will be set by middleware
        }

    @staticmethod
    def get_top_performers(
        db: Session, run_id: str, top_n: int = 10, current_user_id: int = None
    ) -> ApiResponse:
        """Get top N performing pairs from a backtest."""
        run = BacktestRunService.get_run_by_run_id(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Backtest not found")

        if run.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        top_n = min(top_n, 50)  # Cap at 50

        results = (
            db.query(BacktestResult)
            .filter(BacktestResult.run_id_fk == run.id)
            .order_by(BacktestResult.pnl_usd.desc())
            .limit(top_n)
            .all()
        )

        formatted = [
            {
                "rank": i + 1,
                "pair": f"{r.market_1}/{r.market_2}",
                "pnl_usd": round(r.pnl_usd or 0, 2),
                "win_rate": round(r.win_rate or 0, 2),
                "trades": r.total_trades or 0,
                "sharpe_ratio": round(r.sharpe_ratio or 0, 2)
                if r.sharpe_ratio
                else None,
            }
            for i, r in enumerate(results)
        ]

        return {
            "success": True,
            "message": f"Top {len(formatted)} performers",
            "data": {"performers": formatted},
            "timestamp": None,
        }

    @staticmethod
    def get_pair_statistics(
        db: Session,
        run_id: str,
        market_1: str,
        market_2: str,
        current_user_id: int = None,
    ) -> ApiResponse:
        """Get detailed statistics for a specific trading pair."""
        run = BacktestRunService.get_run_by_run_id(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Backtest not found")

        if run.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        result = (
            db.query(BacktestResult)
            .filter(
                (BacktestResult.run_id_fk == run.id)
                & (BacktestResult.market_1 == market_1)
                & (BacktestResult.market_2 == market_2)
            )
            .first()
        )

        if not result:
            raise HTTPException(
                status_code=404, detail="Pair not found in this backtest"
            )

        # Get trades for this pair
        trades = (
            db.query(BacktestTrade)
            .filter(
                (BacktestTrade.run_id_fk == run.id)
                & (BacktestTrade.market_1 == market_1)
                & (BacktestTrade.market_2 == market_2)
            )
            .order_by(BacktestTrade.entry_timestamp.desc())
            .limit(100)
            .all()
        )

        trade_data = [
            {
                "entry_time": t.entry_timestamp.isoformat()
                if t.entry_timestamp
                else None,
                "exit_time": t.exit_timestamp.isoformat() if t.exit_timestamp else None,
                "entry_zscore": round(t.entry_zscore or 0, 3),
                "exit_zscore": round(t.exit_zscore or 0, 3),
                "pnl": round(t.pnl or 0, 2),
                "duration_hours": round(
                    (
                        (t.exit_timestamp - t.entry_timestamp).total_seconds() / 3600
                        if t.exit_timestamp and t.entry_timestamp
                        else 0
                    ),
                    1,
                ),
            }
            for t in trades
        ]

        return {
            "success": True,
            "message": f"Statistics for {market_1}/{market_2}",
            "data": {
                "pair": f"{result.market_1}/{result.market_2}",
                "summary": {
                    "total_trades": result.total_trades or 0,
                    "profitable_trades": result.profitable_trades or 0,
                    "losing_trades": result.losing_trades or 0,
                    "win_rate": round(result.win_rate or 0, 2),
                    "total_pnl_usd": round(result.pnl_usd or 0, 2),
                    "avg_win": round(result.avg_win or 0, 2),
                    "avg_loss": round(result.avg_loss or 0, 2),
                    "profit_factor": round(result.profit_factor or 1.0, 2),
                    "sharpe_ratio": round(result.sharpe_ratio or 0, 2)
                    if result.sharpe_ratio
                    else None,
                    "max_drawdown": round(result.max_drawdown or 0, 2),
                    "cointegration_score": round(result.cointegration_score or 0, 3),
                },
                "trades": trade_data,
                "trade_count": len(trade_data),
            },
            "timestamp": None,
        }
