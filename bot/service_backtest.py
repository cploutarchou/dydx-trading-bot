"""
Service layer for backtest management
Handles business logic for backtest execution and management
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from config import config
from func_backtesting import BacktestEngine
from func_connections import connect_dydx
from internal.domain.models_backtest import (
    BacktestConfigRequest,
    BacktestDetailResponse,
    BacktestListResponse,
    BacktestResponse,
    BacktestRun,
    BacktestStatusEnum,
    BacktestTradeResponse,
)
from repository_backtest import BacktestRepository

logger = logging.getLogger(__name__)


class BacktestService:
    """Service for managing backtest operations"""

    def __init__(self, repository: BacktestRepository):
        self.repository = repository
        self._running_backtests: Dict[str, asyncio.Task] = {}

    async def create_and_run_backtest(
        self,
        request: BacktestConfigRequest,
        progress_callback: Optional[Callable] = None,
    ) -> BacktestResponse:
        """Create new backtest and start execution"""

        try:
            # Parse dates
            start_date = datetime.fromisoformat(request.start_date)
            end_date = datetime.fromisoformat(request.end_date)

            # Validate date range
            if start_date >= end_date:
                raise ValueError("Start date must be before end date")

            if (end_date - start_date).days > 365:
                raise ValueError("Backtest period cannot exceed 365 days")

            # Prepare configuration
            backtest_config = {
                "max_pairs": request.max_pairs,
                "starting_balance": request.starting_balance or 1000.0,
            }

            # Create database record
            backtest_run = self.repository.create_backtest_run(
                name=request.name,
                start_date=start_date,
                end_date=end_date,
                strategy_params=request.strategy_params or {},
                backtest_config=backtest_config,
                starting_balance=request.starting_balance or 1000.0,
            )

            logger.info(f"Created backtest run: {backtest_run.run_id}")

            # Start backtest execution asynchronously
            task = asyncio.create_task(
                self._execute_backtest(backtest_run, progress_callback)
            )
            self._running_backtests[backtest_run.run_id] = task

            # Store task ID in database for tracking
            task_id = f"backtest_{backtest_run.run_id}_{id(task)}"
            self.repository.update_task_info(backtest_run.run_id, task_id, None)

            return BacktestResponse(
                id=backtest_run.id,
                run_id=backtest_run.run_id,
                name=backtest_run.name,
                status=backtest_run.status.value,
                task_id=task_id,
                progress_pct=0.0,
                created_at=backtest_run.created_at.isoformat(),
            )

        except ValueError as e:
            logger.error(f"Validation error in backtest creation: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating backtest: {e}")
            raise

    async def _execute_backtest(
        self, backtest_run: BacktestRun, progress_callback: Optional[Callable] = None
    ) -> None:
        """Execute backtest in background"""

        run_id = backtest_run.run_id

        try:
            # Update status to running
            self.repository.update_backtest_status(run_id, BacktestStatusEnum.RUNNING)

            logger.info(f"Starting backtest execution: {run_id}")

            # Connect to dYdX
            config_obj = config()
            client = await connect_dydx()

            # Create progress callback wrapper
            async def wrapped_progress_callback(
                progress: float, current_pair: str, eta: int
            ):
                # Update database
                self.repository.update_backtest_progress(
                    run_id, progress, current_pair, eta
                )

                # Call external callback if provided
                if progress_callback:
                    await progress_callback(run_id, progress, current_pair, eta)

            # Initialize backtest engine
            engine = BacktestEngine(
                client=client,
                config=config_obj,
                run_id=run_id,
                run_id_int=backtest_run.id,
                db=self.repository.db,
                strategy_params=backtest_run.strategy_params,
                progress_callback=wrapped_progress_callback,
            )

            # Validate strategy parameters
            engine.validate_strategy_params()

            # Execute backtest
            result = await engine.run_backtest(
                start_date=backtest_run.start_date,
                end_date=backtest_run.end_date,
                max_pairs=backtest_run.backtest_config.get("max_pairs"),
            )

            # Update database with results
            self.repository.update_backtest_results(
                run_id=run_id,
                ending_balance=result.ending_balance,
                total_pnl=result.metrics.total_pnl,
                total_return_pct=result.metrics.total_return_pct,
                total_trades=result.metrics.total_trades,
                winning_trades=result.metrics.winning_trades,
                losing_trades=result.metrics.losing_trades,
                win_rate=result.metrics.win_rate,
                sharpe_ratio=result.metrics.sharpe_ratio,
                max_drawdown=result.metrics.max_drawdown,
                max_drawdown_pct=result.metrics.max_drawdown_pct,
                profit_factor=result.metrics.profit_factor,
            )

            # Save individual trades to database
            for trade in result.trades:
                self.repository.save_backtest_trade(
                    backtest_run_id=backtest_run.id,
                    trade_id=trade.trade_id,
                    market_1=trade.market_1,
                    market_2=trade.market_2,
                    entry_timestamp=datetime.fromisoformat(trade.timestamp),
                    entry_price_1=trade.entry_price_1,
                    entry_price_2=trade.entry_price_2,
                    entry_zscore=trade.z_score_entry,
                    side_1=trade.side_1,
                    side_2=trade.side_2,
                    size_1=trade.size_1,
                    size_2=trade.size_2,
                    hedge_ratio=trade.hedge_ratio,
                    exit_timestamp=datetime.fromisoformat(trade.exit_timestamp)
                    if trade.exit_timestamp
                    else None,
                    exit_price_1=trade.exit_price_1,
                    exit_price_2=trade.exit_price_2,
                    exit_zscore=trade.z_score_exit,
                    pnl=trade.pnl,
                    duration_hours=trade.duration_hours,
                    strategy_zscore_threshold=trade.strategy_zscore_threshold,
                )

            # Mark as completed
            self.repository.update_backtest_status(run_id, BacktestStatusEnum.COMPLETED)

            logger.info(
                f"Backtest completed successfully: {run_id} (PnL: ${result.metrics.total_pnl:.2f})"
            )

        except Exception as e:
            logger.error(f"Backtest execution failed: {run_id}, Error: {e}")

            # Mark as failed
            self.repository.update_backtest_status(
                run_id, BacktestStatusEnum.FAILED, error_message=str(e)
            )

        finally:
            # Remove from running backtests
            if run_id in self._running_backtests:
                del self._running_backtests[run_id]

    def get_backtest_status(self, run_id: str) -> Optional[BacktestResponse]:
        """Get current backtest status"""

        backtest_run = self.repository.get_backtest_run(run_id)
        if not backtest_run:
            return None

        return BacktestResponse(
            id=backtest_run.id,
            run_id=backtest_run.run_id,
            name=backtest_run.name,
            status=backtest_run.status.value,
            total_pnl=backtest_run.total_pnl,
            win_rate=backtest_run.win_rate,
            total_trades=backtest_run.total_trades,
            sharpe_ratio=backtest_run.sharpe_ratio,
            progress_pct=backtest_run.progress_pct,
            current_pair=backtest_run.current_pair,
            eta_seconds=backtest_run.eta_seconds,
            created_at=backtest_run.created_at.isoformat(),
            started_at=backtest_run.started_at.isoformat()
            if backtest_run.started_at
            else None,
            completed_at=backtest_run.completed_at.isoformat()
            if backtest_run.completed_at
            else None,
        )

    def get_backtest_details(self, run_id: str) -> Optional[BacktestDetailResponse]:
        """Get detailed backtest results"""

        backtest_run = self.repository.get_backtest_run(run_id)
        if not backtest_run:
            return None

        # Get recent trades
        recent_trades_db = self.repository.get_recent_trades(run_id, limit=10)
        recent_trades = [
            BacktestTradeResponse(
                trade_id=trade.trade_id,
                market_1=trade.market_1,
                market_2=trade.market_2,
                entry_timestamp=trade.entry_timestamp.isoformat(),
                exit_timestamp=trade.exit_timestamp.isoformat()
                if trade.exit_timestamp
                else None,
                pnl=trade.pnl,
                duration_hours=trade.duration_hours,
                entry_zscore=trade.entry_zscore,
                exit_zscore=trade.exit_zscore,
            )
            for trade in recent_trades_db
        ]

        return BacktestDetailResponse(
            id=backtest_run.id,
            run_id=backtest_run.run_id,
            name=backtest_run.name,
            status=backtest_run.status.value,
            start_date=backtest_run.start_date.isoformat(),
            end_date=backtest_run.end_date.isoformat(),
            total_days=backtest_run.total_days,
            strategy_params=backtest_run.strategy_params,
            starting_balance=backtest_run.starting_balance,
            ending_balance=backtest_run.ending_balance,
            total_pnl=backtest_run.total_pnl,
            total_return_pct=backtest_run.total_return_pct,
            total_trades=backtest_run.total_trades,
            winning_trades=backtest_run.winning_trades,
            losing_trades=backtest_run.losing_trades,
            win_rate=backtest_run.win_rate,
            sharpe_ratio=backtest_run.sharpe_ratio,
            max_drawdown=backtest_run.max_drawdown,
            max_drawdown_pct=backtest_run.max_drawdown_pct,
            profit_factor=backtest_run.profit_factor,
            progress_pct=backtest_run.progress_pct,
            current_pair=backtest_run.current_pair,
            eta_seconds=backtest_run.eta_seconds,
            error_message=backtest_run.error_message,
            created_at=backtest_run.created_at.isoformat(),
            started_at=backtest_run.started_at.isoformat()
            if backtest_run.started_at
            else None,
            completed_at=backtest_run.completed_at.isoformat()
            if backtest_run.completed_at
            else None,
            recent_trades=recent_trades,
        )

    def list_backtest_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
        days_filter: Optional[int] = None,
    ) -> BacktestListResponse:
        """List backtest runs with filtering"""

        # Get runs and total count
        runs = self.repository.list_backtest_runs(
            limit=limit,
            offset=offset,
            status_filter=status_filter,
            days_filter=days_filter,
        )

        total = self.repository.count_backtest_runs(
            status_filter=status_filter, days_filter=days_filter
        )

        # Convert to response format
        run_responses = [
            BacktestResponse(
                id=run.id,
                run_id=run.run_id,
                name=run.name,
                status=run.status.value,
                total_pnl=run.total_pnl,
                win_rate=run.win_rate,
                total_trades=run.total_trades,
                sharpe_ratio=run.sharpe_ratio,
                progress_pct=run.progress_pct,
                current_pair=run.current_pair,
                eta_seconds=run.eta_seconds,
                created_at=run.created_at.isoformat(),
                started_at=run.started_at.isoformat() if run.started_at else None,
                completed_at=run.completed_at.isoformat() if run.completed_at else None,
            )
            for run in runs
        ]

        return BacktestListResponse(total=total, runs=run_responses)

    def get_backtest_trades(
        self, run_id: str, limit: int = 100, offset: int = 0, winning_only: bool = False
    ) -> List[BacktestTradeResponse]:
        """Get trades for specific backtest run"""

        trades = self.repository.get_backtest_trades(
            run_id=run_id, limit=limit, offset=offset, winning_only=winning_only
        )

        return [
            BacktestTradeResponse(
                trade_id=trade.trade_id,
                market_1=trade.market_1,
                market_2=trade.market_2,
                entry_timestamp=trade.entry_timestamp.isoformat(),
                exit_timestamp=trade.exit_timestamp.isoformat()
                if trade.exit_timestamp
                else None,
                pnl=trade.pnl,
                duration_hours=trade.duration_hours,
                entry_zscore=trade.entry_zscore,
                exit_zscore=trade.exit_zscore,
            )
            for trade in trades
        ]

    def cancel_backtest(self, run_id: str) -> bool:
        """Cancel running backtest"""

        # Check if backtest is running
        if run_id in self._running_backtests:
            task = self._running_backtests[run_id]
            task.cancel()
            del self._running_backtests[run_id]

            # Update database status
            self.repository.update_backtest_status(
                run_id, BacktestStatusEnum.CANCELLED, error_message="Cancelled by user"
            )

            logger.info(f"Cancelled backtest: {run_id}")
            return True

        return False

    def delete_backtest(self, run_id: str) -> bool:
        """Delete backtest run and all data"""

        # Cancel if running
        self.cancel_backtest(run_id)

        # Delete from database
        return self.repository.delete_backtest_run(run_id)

    def get_running_backtests(self) -> List[str]:
        """Get list of currently running backtest IDs"""
        return list(self._running_backtests.keys())

    def get_summary_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get backtest summary statistics"""
        return self.repository.get_backtest_summary_stats(days)

    def get_comprehensive_analytics(self, run_id: str) -> Optional[dict]:
        """Get comprehensive analytics for a backtest run"""

        backtest_run = self.repository.get_backtest_run(run_id)
        if not backtest_run:
            return None

        trades = self.repository.get_backtest_trades(run_id, limit=10000)

        # Calculate advanced metrics
        analytics = {
            "run_id": run_id,
            "name": getattr(backtest_run, "name", ""),
            "total_return_pct": getattr(backtest_run, "total_return_pct", 0.0) or 0.0,
            "sharpe_ratio": getattr(backtest_run, "sharpe_ratio", None),
            "max_drawdown_pct": getattr(backtest_run, "max_drawdown_pct", None),
            "win_rate": getattr(backtest_run, "win_rate", 0.0) or 0.0,
            "avg_position_duration": self._calculate_avg_position_duration(trades),
            "max_concurrent_positions": self._calculate_max_concurrent_positions(
                trades
            ),
            "position_turnover_rate": self._calculate_turnover_rate(trades),
            "var_95": self._calculate_var(trades),
            "expected_shortfall": self._calculate_expected_shortfall(trades),
            "calmar_ratio": self._calculate_calmar_ratio(backtest_run),
            "equity_curve": self._generate_equity_curve(trades),
            "drawdown_periods": self._calculate_drawdown_periods(trades),
            "position_performance_by_pair": self._analyze_pair_performance(trades),
        }

        return analytics

    def get_position_snapshots(
        self,
        run_id: str,
        limit: int = 100,
        offset: int = 0,
        market_pair: Optional[str] = None,
    ) -> List[dict]:
        """Get position snapshots for real-time tracking"""

        # This would query the BacktestPositionSnapshot table
        # For now, return empty list as snapshots aren't being saved yet
        return []

    def compare_backtests(self, run_ids: List[str], metrics: List[str]) -> dict:
        """Compare multiple backtest runs"""

        comparison_data = {}
        best_performers = {}

        for run_id in run_ids:
            backtest_run = self.repository.get_backtest_run(run_id)
            if backtest_run:
                run_data = {}
                for metric in metrics:
                    value = getattr(backtest_run, metric, None)
                    run_data[metric] = value if value is not None else 0.0
                comparison_data[run_id] = run_data

        # Find best performers for each metric
        for metric in metrics:
            best_run_id = None
            best_value = float("-inf")
            for run_id, data in comparison_data.items():
                if data.get(metric, 0) > best_value:
                    best_value = data[metric]
                    best_run_id = run_id
            best_performers[metric] = best_run_id

        return {
            "comparison_matrix": comparison_data,
            "best_performers": best_performers,
            "correlation_matrix": {},  # Would calculate correlations
            "summary_statistics": {},  # Would calculate summary stats
        }

    async def validate_against_dydx_data(self, run_id: str) -> Optional[dict]:
        """Validate backtest results against real dYdX market data"""

        backtest_run = self.repository.get_backtest_run(run_id)
        if not backtest_run:
            return None

        # This would fetch historical data from dYdX and compare
        # For now, return placeholder data
        return {
            "validation_status": "pending",
            "data_coverage": 0.0,
            "price_accuracy": 0.0,
            "volume_correlation": 0.0,
            "discrepancies": [],
            "market_conditions": {
                "volatility": 0.0,
                "trend": "neutral",
                "liquidity_score": 0.0,
            },
        }

    async def get_advanced_performance_metrics(
        self, run_id: str, benchmark: str
    ) -> Optional[dict]:
        """Get advanced performance metrics with market benchmarking"""

        backtest_run = self.repository.get_backtest_run(run_id)
        if not backtest_run:
            return None

        # This would calculate advanced metrics like alpha, beta, etc.
        return {
            "run_id": run_id,
            "benchmark": benchmark,
            "alpha": 0.0,
            "beta": 0.0,
            "treynor_ratio": 0.0,
            "information_ratio": 0.0,
            "tracking_error": 0.0,
            "up_capture_ratio": 0.0,
            "down_capture_ratio": 0.0,
            "benchmark_correlation": 0.0,
            "risk_adjusted_return": 0.0,
        }

    def get_live_progress(self, run_id: str) -> Optional[dict]:
        """Get real-time backtest progress with current positions"""

        backtest_run = self.repository.get_backtest_run(run_id)
        if not backtest_run:
            return None

        is_running = run_id in self._running_backtests

        return {
            "run_id": run_id,
            "status": getattr(backtest_run, "status", "unknown"),
            "progress_pct": getattr(backtest_run, "progress_pct", 0.0) or 0.0,
            "current_pair": getattr(backtest_run, "current_pair", None),
            "eta_seconds": getattr(backtest_run, "eta_seconds", 0) or 0,
            "is_running": is_running,
            "task_id": getattr(backtest_run, "task_id", None),
            "current_positions": [],  # Would get from position snapshots
            "current_portfolio_value": 0.0,
            "unrealized_pnl": 0.0,
        }

    def _calculate_avg_position_duration(self, trades: List) -> Optional[float]:
        """Calculate average position duration in hours"""
        durations = []
        for trade in trades:
            duration = getattr(trade, "duration_hours", None)
            if duration is not None:
                durations.append(duration)
        return sum(durations) / len(durations) if durations else None

    def _calculate_max_concurrent_positions(self, trades: List) -> int:
        """Calculate maximum concurrent positions"""
        # This would require position timeline analysis
        return len(trades) if trades else 0

    def _calculate_turnover_rate(self, trades: List) -> Optional[float]:
        """Calculate position turnover rate"""
        # This would calculate how frequently positions are opened/closed
        return len(trades) / 30.0 if trades else None  # Placeholder: trades per month

    def _calculate_var(self, trades: List, confidence: float = 0.95) -> Optional[float]:
        """Calculate Value at Risk"""
        pnls = [getattr(t, "pnl", 0) or 0 for t in trades if hasattr(t, "pnl")]
        if not pnls:
            return None
        pnls.sort()
        var_index = int((1 - confidence) * len(pnls))
        return pnls[var_index] if var_index < len(pnls) else None

    def _calculate_expected_shortfall(
        self, trades: List, confidence: float = 0.95
    ) -> Optional[float]:
        """Calculate Expected Shortfall (Conditional VaR)"""
        pnls = [getattr(t, "pnl", 0) or 0 for t in trades if hasattr(t, "pnl")]
        if not pnls:
            return None
        pnls.sort()
        var_index = int((1 - confidence) * len(pnls))
        tail_losses = pnls[:var_index] if var_index > 0 else []
        return sum(tail_losses) / len(tail_losses) if tail_losses else None

    def _calculate_calmar_ratio(self, backtest_run) -> Optional[float]:
        """Calculate Calmar ratio (return / max drawdown)"""
        total_return = getattr(backtest_run, "total_return_pct", None)
        max_drawdown = getattr(backtest_run, "max_drawdown_pct", None)

        if total_return is not None and max_drawdown is not None and max_drawdown != 0:
            return total_return / abs(max_drawdown)
        return None

    def _generate_equity_curve(self, trades: List) -> List[dict]:
        """Generate equity curve data points"""
        # This would create a time series of portfolio value
        return []

    def _calculate_drawdown_periods(self, trades: List) -> List[dict]:
        """Calculate significant drawdown periods"""
        # This would analyze periods of consecutive losses
        return []

    def _analyze_pair_performance(self, trades: List) -> Dict[str, dict]:
        """Analyze performance by market pair"""
        pair_stats = {}

        for trade in trades:
            market_1 = getattr(trade, "market_1", None)
            market_2 = getattr(trade, "market_2", None)

            if market_1 and market_2:
                pair_key = f"{market_1}/{market_2}"
                if pair_key not in pair_stats:
                    pair_stats[pair_key] = {
                        "total_trades": 0,
                        "total_pnl": 0.0,
                        "win_rate": 0.0,
                        "avg_duration": 0.0,
                    }

                pair_stats[pair_key]["total_trades"] += 1
                pnl = getattr(trade, "pnl", 0) or 0
                pair_stats[pair_key]["total_pnl"] += pnl

        return pair_stats
