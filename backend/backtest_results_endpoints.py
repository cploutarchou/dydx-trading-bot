"""
Enhanced Backtest Results Endpoints
Senior-grade pagination, filtering, and data validation
"""

from typing import Optional
from fastapi import HTTPException
from database import execute_query
from main import ApiResponse
from services import BacktestRunService
from datetime import datetime as dt, timezone


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
        limit = min(limit, 100)  # Cap at 100
        offset = max(offset, 0)

        # Get run
        run = BacktestRunService.get_run_by_run_id(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Backtest not found")
        if run["user_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Build SQL query
        base_query = "SELECT * FROM backtest_results WHERE run_id_fk = %s"
        params = [run["id"]]
        filters = []
        if min_win_rate is not None:
            filters.append("win_rate >= %s")
            params.append(min_win_rate)
        if min_trades is not None:
            filters.append("total_trades >= %s")
            params.append(min_trades)
        if filter_by_status:
            filters.append("status = %s")
            params.append(filter_by_status)
        if filters:
            base_query += " AND " + " AND ".join(filters)
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
        order = "ASC" if sort_order.lower() == "asc" else "DESC"
        base_query += f" ORDER BY {sort_by} {order}"
        # Get total count
        count_query = base_query.replace("SELECT *", "SELECT COUNT(*)")
        total = execute_query(count_query, tuple(params), fetchone=True)[0]
        # Pagination
        base_query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        results = execute_query(base_query, tuple(params))
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "id": result["id"],
                    "pair": f"{result['market_1']}/{result['market_2']}",
                    "market_1": result["market_1"],
                    "market_2": result["market_2"],
                    "total_trades": result.get("total_trades", 0) or 0,
                    "profitable_trades": result.get("profitable_trades", 0) or 0,
                    "losing_trades": result.get("losing_trades", 0) or 0,
                    "win_rate": round(result.get("win_rate", 0) or 0, 2),
                    "pnl_usd": round(result.get("pnl_usd", 0) or 0, 2),
                    "avg_win": round(result.get("avg_win", 0) or 0, 2),
                    "avg_loss": round(result.get("avg_loss", 0) or 0, 2),
                    "profit_factor": round(result.get("profit_factor", 1.0) or 1.0, 2),
                    "max_drawdown": round(result.get("max_drawdown", 0) or 0, 2),
                    "sharpe_ratio": round(result.get("sharpe_ratio", 0) or 0, 2)
                    if result.get("sharpe_ratio")
                    else "N/A",
                    "sortino_ratio": round(result.get("sortino_ratio", 0) or 0, 2)
                    if result.get("sortino_ratio")
                    else "N/A",
                    "avg_trade_duration_hours": round(result.get("avg_trade_duration_hours", 0) or 0, 1),
                    "cointegration_score": round(result.get("cointegration_score", 0) or 0, 3),
                    "zscore_mean": round(result.get("zscore_mean", 0) or 0, 3),
                    "zscore_std": round(result.get("zscore_std", 0) or 0, 3),
                }
            )
        return ApiResponse(
            success=True,
            message=f"Retrieved {len(formatted_results)} results",
            data={
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
                    "run_id": run["run_id"],
                    "status": run["status"],
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                },
            },
            timestamp=dt.now(timezone.utc),
        )

    @staticmethod
    def get_top_performers(
        run_id: str, top_n: int = 10, current_user_id: int = None
    ) -> ApiResponse:
        """Get top N performing pairs from a backtest."""
        run = BacktestRunService.get_run_by_run_id(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Backtest not found")
        if run["user_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        top_n = min(top_n, 50)  # Cap at 50
        results = execute_query(
            "SELECT * FROM backtest_results WHERE run_id_fk = %s ORDER BY pnl_usd DESC LIMIT %s",
            (run["id"], top_n),
        )
        formatted = [
            {
                "rank": i + 1,
                "pair": f"{r['market_1']}/{r['market_2']}",
                "pnl_usd": round(r.get("pnl_usd", 0) or 0, 2),
                "win_rate": round(r.get("win_rate", 0) or 0, 2),
                "trades": r.get("total_trades", 0) or 0,
                "sharpe_ratio": round(r.get("sharpe_ratio", 0) or 0, 2)
                if r.get("sharpe_ratio")
                else None,
            }
            for i, r in enumerate(results)
        ]
        return ApiResponse(
            success=True,
            message=f"Top {len(formatted)} performers",
            data={"performers": formatted},
            timestamp=dt.now(timezone.utc),
        )

    @staticmethod
    def get_pair_statistics(
        run_id: str,
        market_1: str,
        market_2: str,
        current_user_id: int = None,
    ) -> ApiResponse:
        """Get detailed statistics for a specific trading pair."""
        run = BacktestRunService.get_run_by_run_id(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Backtest not found")
        if run["user_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        result = execute_query(
            "SELECT * FROM backtest_results WHERE run_id_fk = %s AND market_1 = %s AND market_2 = %s",
            (run["id"], market_1, market_2),
            fetchone=True,
        )
        if not result:
            raise HTTPException(
                status_code=404, detail="Pair not found in this backtest"
            )
        trades = execute_query(
            "SELECT * FROM backtest_trades WHERE run_id_fk = %s AND market_1 = %s AND market_2 = %s ORDER BY entry_timestamp DESC LIMIT 100",
            (run["id"], market_1, market_2),
        )
        trade_data = [
            {
                "entry_time": t["entry_timestamp"].isoformat() if t["entry_timestamp"] else None,
                "exit_time": t["exit_timestamp"].isoformat() if t["exit_timestamp"] else None,
                "entry_zscore": round(t.get("entry_z_score", 0) or 0, 3),
                "exit_zscore": round(t.get("exit_z_score", 0) or 0, 3),
                "pnl": round(t.get("pnl", 0) or 0, 2),
                "duration_hours": round(
                    (
                        (t["exit_timestamp"] - t["entry_timestamp"]).total_seconds() / 3600
                        if t["exit_timestamp"] and t["entry_timestamp"]
                        else 0
                    ),
                    1,
                ),
            }
            for t in trades
        ]
        return ApiResponse(
            success=True,
            message=f"Statistics for {market_1}/{market_2}",
            data={
                "pair": f"{result['market_1']}/{result['market_2']}",
                "summary": {
                    "total_trades": result.get("total_trades", 0) or 0,
                    "profitable_trades": result.get("profitable_trades", 0) or 0,
                    "losing_trades": result.get("losing_trades", 0) or 0,
                    "win_rate": round(result.get("win_rate", 0) or 0, 2),
                    "total_pnl_usd": round(result.get("pnl_usd", 0) or 0, 2),
                    "avg_win": round(result.get("avg_win", 0) or 0, 2),
                    "avg_loss": round(result.get("avg_loss", 0) or 0, 2),
                    "profit_factor": round(result.get("profit_factor", 1.0) or 1.0, 2),
                    "sharpe_ratio": round(result.get("sharpe_ratio", 0) or 0, 2)
                    if result.get("sharpe_ratio")
                    else None,
                    "max_drawdown": round(result.get("max_drawdown", 0) or 0, 2),
                    "cointegration_score": round(result.get("cointegration_score", 0) or 0, 3),
                },
                "trades": trade_data,
                "trade_count": len(trade_data),
            },
            timestamp=dt.now(timezone.utc),
        )