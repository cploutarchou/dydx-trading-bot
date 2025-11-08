"""
Repository layer for backtest database operations
Handles CRUD operations for backtest runs and trades
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from models_backtest import BacktestRun, BacktestStatusEnum, BacktestTrade

logger = logging.getLogger(__name__)


class BacktestRepository:
    """Database operations for backtest system"""

    def __init__(self, db: Session):
        self.db = db

    def create_backtest_run(
        self,
        name: str,
        start_date: datetime,
        end_date: datetime,
        strategy_params: Dict[str, Any],
        backtest_config: Dict[str, Any],
        starting_balance: float = 1000.0,
    ) -> BacktestRun:
        """Create new backtest run record"""

        run_id = str(uuid4())
        total_days = (end_date - start_date).days

        backtest_run = BacktestRun(
            run_id=run_id,
            name=name,
            status=BacktestStatusEnum.QUEUED,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            strategy_params=strategy_params,
            backtest_config=backtest_config,
            starting_balance=starting_balance,
        )

        self.db.add(backtest_run)
        self.db.commit()
        self.db.refresh(backtest_run)

        logger.info(f"Created backtest run: {run_id} ({name})")
        return backtest_run

    def get_backtest_run(self, run_id: str) -> Optional[BacktestRun]:
        """Get backtest run by ID"""
        return self.db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()

    def get_backtest_run_by_db_id(self, db_id: int) -> Optional[BacktestRun]:
        """Get backtest run by database ID"""
        return self.db.query(BacktestRun).filter(BacktestRun.id == db_id).first()

    def list_backtest_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
        days_filter: Optional[int] = None,
    ) -> List[BacktestRun]:
        """List backtest runs with optional filtering"""

        query = self.db.query(BacktestRun)

        # Apply filters
        if status_filter:
            query = query.filter(BacktestRun.status == status_filter)

        if days_filter:
            cutoff_date = datetime.utcnow() - timedelta(days=days_filter)
            query = query.filter(BacktestRun.created_at >= cutoff_date)

        # Order by creation date (most recent first)
        query = query.order_by(desc(BacktestRun.created_at))

        # Apply pagination
        return query.offset(offset).limit(limit).all()

    def count_backtest_runs(
        self, status_filter: Optional[str] = None, days_filter: Optional[int] = None
    ) -> int:
        """Count total backtest runs with same filters"""

        query = self.db.query(BacktestRun)

        if status_filter:
            query = query.filter(BacktestRun.status == status_filter)

        if days_filter:
            cutoff_date = datetime.utcnow() - timedelta(days=days_filter)
            query = query.filter(BacktestRun.created_at >= cutoff_date)

        return query.count()

    def update_backtest_status(
        self,
        run_id: str,
        status: BacktestStatusEnum,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update backtest run status"""

        backtest_run = self.get_backtest_run(run_id)
        if not backtest_run:
            return False

        backtest_run.status = status

        if status == BacktestStatusEnum.RUNNING:
            backtest_run.started_at = datetime.utcnow()
        elif status in [BacktestStatusEnum.COMPLETED, BacktestStatusEnum.FAILED]:
            backtest_run.completed_at = datetime.utcnow()

        if error_message:
            backtest_run.error_message = error_message

        self.db.commit()
        logger.info(f"Updated backtest {run_id} status to {status.value}")
        return True

    def update_backtest_progress(
        self,
        run_id: str,
        progress_pct: float,
        current_pair: Optional[str] = None,
        eta_seconds: int = 0,
    ) -> bool:
        """Update backtest progress"""

        backtest_run = self.get_backtest_run(run_id)
        if not backtest_run:
            return False

        backtest_run.progress_pct = progress_pct
        backtest_run.current_pair = current_pair
        backtest_run.eta_seconds = eta_seconds

        self.db.commit()
        return True

    def update_backtest_results(
        self,
        run_id: str,
        ending_balance: float,
        total_pnl: float,
        total_return_pct: float,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        win_rate: float,
        sharpe_ratio: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        max_drawdown_pct: Optional[float] = None,
        profit_factor: Optional[float] = None,
    ) -> bool:
        """Update backtest final results"""

        backtest_run = self.get_backtest_run(run_id)
        if not backtest_run:
            return False

        backtest_run.ending_balance = ending_balance
        backtest_run.total_pnl = total_pnl
        backtest_run.total_return_pct = total_return_pct
        backtest_run.total_trades = total_trades
        backtest_run.winning_trades = winning_trades
        backtest_run.losing_trades = losing_trades
        backtest_run.win_rate = win_rate
        backtest_run.sharpe_ratio = sharpe_ratio
        backtest_run.max_drawdown = max_drawdown
        backtest_run.max_drawdown_pct = max_drawdown_pct
        backtest_run.profit_factor = profit_factor

        self.db.commit()
        logger.info(f"Updated backtest {run_id} results: PnL ${total_pnl:.2f}")
        return True

    def save_backtest_trade(
        self,
        backtest_run_id: int,
        trade_id: str,
        market_1: str,
        market_2: str,
        entry_timestamp: datetime,
        entry_price_1: float,
        entry_price_2: float,
        entry_zscore: float,
        side_1: str,
        side_2: str,
        size_1: float,
        size_2: float,
        hedge_ratio: float,
        exit_timestamp: Optional[datetime] = None,
        exit_price_1: Optional[float] = None,
        exit_price_2: Optional[float] = None,
        exit_zscore: Optional[float] = None,
        pnl: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        duration_hours: Optional[float] = None,
        strategy_zscore_threshold: Optional[float] = None,
    ) -> BacktestTrade:
        """Save backtest trade to database"""

        trade = BacktestTrade(
            backtest_run_id=backtest_run_id,
            trade_id=trade_id,
            market_1=market_1,
            market_2=market_2,
            entry_timestamp=entry_timestamp,
            entry_price_1=entry_price_1,
            entry_price_2=entry_price_2,
            entry_zscore=entry_zscore,
            side_1=side_1,
            side_2=side_2,
            size_1=size_1,
            size_2=size_2,
            hedge_ratio=hedge_ratio,
            exit_timestamp=exit_timestamp,
            exit_price_1=exit_price_1,
            exit_price_2=exit_price_2,
            exit_zscore=exit_zscore,
            pnl=pnl,
            pnl_pct=pnl_pct,
            duration_hours=duration_hours,
            strategy_zscore_threshold=strategy_zscore_threshold,
        )

        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)

        return trade

    def get_backtest_trades(
        self, run_id: str, limit: int = 100, offset: int = 0, winning_only: bool = False
    ) -> List[BacktestTrade]:
        """Get trades for specific backtest run"""

        backtest_run = self.get_backtest_run(run_id)
        if not backtest_run:
            return []

        query = self.db.query(BacktestTrade).filter(
            BacktestTrade.backtest_run_id == backtest_run.id
        )

        if winning_only:
            query = query.filter(BacktestTrade.pnl > 0)

        # Order by entry time (most recent first)
        query = query.order_by(desc(BacktestTrade.entry_timestamp))

        return query.offset(offset).limit(limit).all()

    def count_backtest_trades(self, run_id: str, winning_only: bool = False) -> int:
        """Count trades for specific backtest run"""

        backtest_run = self.get_backtest_run(run_id)
        if not backtest_run:
            return 0

        query = self.db.query(BacktestTrade).filter(
            BacktestTrade.backtest_run_id == backtest_run.id
        )

        if winning_only:
            query = query.filter(BacktestTrade.pnl > 0)

        return query.count()

    def update_task_info(
        self, run_id: str, task_id: Optional[str] = None, job_id: Optional[str] = None
    ) -> bool:
        """Update async task and job information for backtest run"""

        backtest_run = self.get_backtest_run(run_id)
        if not backtest_run:
            return False

        if task_id is not None:
            backtest_run.task_id = task_id
        if job_id is not None:
            backtest_run.job_id = job_id

        self.db.commit()
        logger.info(
            f"Updated task info for backtest {run_id}: task_id={task_id}, job_id={job_id}"
        )
        return True

    def save_position_snapshot(
        self,
        backtest_run_id: int,
        timestamp: datetime,
        market_1: str,
        market_2: str,
        is_open: bool,
        current_price_1: Optional[float] = None,
        current_price_2: Optional[float] = None,
        current_zscore: Optional[float] = None,
        unrealized_pnl: Optional[float] = None,
        portfolio_value: Optional[float] = None,
        trade_id: Optional[str] = None,
        **kwargs,
    ):
        """Save position snapshot for real-time tracking"""

        from models_backtest import BacktestPositionSnapshot

        snapshot = BacktestPositionSnapshot(
            backtest_run_id=backtest_run_id,
            timestamp=timestamp,
            market_1=market_1,
            market_2=market_2,
            is_open=1 if is_open else 0,
            current_price_1=current_price_1,
            current_price_2=current_price_2,
            current_zscore=current_zscore,
            unrealized_pnl=unrealized_pnl,
            portfolio_value=portfolio_value,
            trade_id=trade_id,
            **kwargs,
        )

        self.db.add(snapshot)
        self.db.commit()
        return snapshot

    def delete_backtest_run(self, run_id: str) -> bool:
        """Delete backtest run and all associated data"""

        backtest_run = self.get_backtest_run(run_id)
        if not backtest_run:
            return False

        # Cascade delete will handle trades automatically
        self.db.delete(backtest_run)
        self.db.commit()

        logger.info(f"Deleted backtest run: {run_id}")
        return True

    def get_recent_trades(self, run_id: str, limit: int = 10) -> List[BacktestTrade]:
        """Get most recent trades for a backtest run"""
        return self.get_backtest_trades(run_id, limit=limit, offset=0)

    def get_backtest_summary_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get summary statistics for backtests in last N days"""

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Total runs
        total_runs = (
            self.db.query(BacktestRun)
            .filter(BacktestRun.created_at >= cutoff_date)
            .count()
        )

        # Completed runs
        completed_runs = (
            self.db.query(BacktestRun)
            .filter(
                and_(
                    BacktestRun.created_at >= cutoff_date,
                    BacktestRun.status == BacktestStatusEnum.COMPLETED,
                )
            )
            .count()
        )

        # Failed runs
        failed_runs = (
            self.db.query(BacktestRun)
            .filter(
                and_(
                    BacktestRun.created_at >= cutoff_date,
                    BacktestRun.status == BacktestStatusEnum.FAILED,
                )
            )
            .count()
        )

        # Running runs
        running_runs = (
            self.db.query(BacktestRun)
            .filter(
                and_(
                    BacktestRun.created_at >= cutoff_date,
                    BacktestRun.status == BacktestStatusEnum.RUNNING,
                )
            )
            .count()
        )

        return {
            "period_days": days,
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": failed_runs,
            "running_runs": running_runs,
            "success_rate": (completed_runs / total_runs * 100)
            if total_runs > 0
            else 0,
        }
