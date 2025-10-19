"""
Database service layer for backtest operations.
Handles CRUD operations and complex queries.
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from backend.auth import hash_password, verify_password
from backend.database import (
    AuditLog,
    BacktestResult,
    BacktestRun,
    BacktestStrategy,
    TradeLog,
    User,
)

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management."""

    @staticmethod
    def create_user(db: Session, username: str, email: str, password: str) -> User:
        """Create new user account."""
        # Check if user already exists
        existing = (
            db.query(User)
            .filter((User.username == username) | (User.email == email))
            .first()
        )
        if existing:
            raise ValueError(f"User {username} already exists")

        hashed_pwd = hash_password(password)
        user = User(
            username=username, email=email, hashed_password=hashed_pwd, is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"User created: {username}")
        return user

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Get user by username."""
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user with credentials."""
        user = UserService.get_user_by_username(db, username)
        if not user or not verify_password(password, user.hashed_password):
            return None

        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        return user

    @staticmethod
    def deactivate_user(db: Session, user_id: int) -> bool:
        """Deactivate user account."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        user.is_active = False
        db.commit()
        logger.info(f"User deactivated: {user.username}")
        return True


class BacktestRunService:
    """Service for backtest run management."""

    @staticmethod
    def create_run(
        db: Session,
        run_id: str,
        start_date: str,
        end_date: str,
        num_pairs: int,
        total_markets: int,
        user_id: Optional[int] = None,
        config: Optional[dict] = None,
        strategy_id: Optional[int] = None,
        strategy_snapshot: Optional[dict] = None,
    ) -> BacktestRun:
        """Create new backtest run."""
        run = BacktestRun(
            run_id=run_id,
            status="running",
            start_date=start_date,
            end_date=end_date,
            num_pairs=num_pairs,
            total_markets=total_markets,
            user_id=user_id,
            config=config,
            strategy_id=strategy_id,
            strategy_snapshot=strategy_snapshot,
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info(f"Backtest run created: {run_id}")
        return run

    @staticmethod
    def get_run_by_id(db: Session, run_id_pk: int) -> Optional[BacktestRun]:
        """Get backtest run by ID."""
        return db.query(BacktestRun).filter(BacktestRun.id == run_id_pk).first()

    @staticmethod
    def get_run_by_run_id(db: Session, run_id: str) -> Optional[BacktestRun]:
        """Get backtest run by run_id string."""
        return db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()

    @staticmethod
    def get_user_runs(
        db: Session, user_id: int, skip: int = 0, limit: int = 50
    ) -> List[BacktestRun]:
        """Get all backtest runs for a user."""
        return (
            db.query(BacktestRun)
            .filter(BacktestRun.user_id == user_id)
            .order_by(desc(BacktestRun.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_run_status(
        db: Session, run_id_pk: int, status: str
    ) -> Optional[BacktestRun]:
        """Update backtest run status."""
        run = db.query(BacktestRun).filter(BacktestRun.id == run_id_pk).first()
        if not run:
            return None

        run.status = status
        if status == "completed":
            run.completed_at = datetime.utcnow()
            if run.started_at:
                duration = (run.completed_at - run.started_at).total_seconds()
                run.duration_seconds = duration

        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def update_run_metrics(
        db: Session, run_id_pk: int, metrics: dict
    ) -> Optional[BacktestRun]:
        """Update backtest run with metrics."""
        run = db.query(BacktestRun).filter(BacktestRun.id == run_id_pk).first()
        if not run:
            return None

        # Update metrics from dict
        for key, value in metrics.items():
            if hasattr(run, key):
                setattr(run, key, value)

        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get_latest_runs(db: Session, limit: int = 10) -> List[BacktestRun]:
        """Get latest backtest runs."""
        return (
            db.query(BacktestRun)
            .order_by(desc(BacktestRun.created_at))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_run_stats(db: Session) -> dict:
        """Get aggregate statistics for backtest runs."""
        total_runs = db.query(func.count(BacktestRun.id)).scalar()
        completed_runs = (
            db.query(func.count(BacktestRun.id))
            .filter(BacktestRun.status == "completed")
            .scalar()
        )
        avg_pnl = (
            db.query(func.avg(BacktestRun.total_pnl))
            .filter(BacktestRun.status == "completed")
            .scalar()
        )

        return {
            "total_runs": total_runs or 0,
            "completed_runs": completed_runs or 0,
            "failed_runs": db.query(func.count(BacktestRun.id))
            .filter(BacktestRun.status == "failed")
            .scalar()
            or 0,
            "avg_pnl": float(avg_pnl) if avg_pnl else 0.0,
        }


class BacktestResultService:
    """Service for individual backtest results."""

    @staticmethod
    def create_result(
        db: Session, run_id_fk: int, market_1: str, market_2: str, metrics: dict
    ) -> BacktestResult:
        """Create backtest result for a pair."""
        result = BacktestResult(
            run_id_fk=run_id_fk, market_1=market_1, market_2=market_2, **metrics
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result

    @staticmethod
    def get_run_results(
        db: Session, run_id_fk: int, skip: int = 0, limit: int = 1000
    ) -> List[BacktestResult]:
        """Get all results for a backtest run."""
        return (
            db.query(BacktestResult)
            .filter(BacktestResult.run_id_fk == run_id_fk)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_profitable_pairs(db: Session, run_id_fk: int) -> List[BacktestResult]:
        """Get profitable trading pairs from a run."""
        return (
            db.query(BacktestResult)
            .filter(and_(BacktestResult.run_id_fk == run_id_fk, BacktestResult.pnl > 0))
            .order_by(desc(BacktestResult.pnl))
            .all()
        )

    @staticmethod
    def get_top_pairs(
        db: Session, limit: int = 10, metric: str = "pnl"
    ) -> List[BacktestResult]:
        """Get top trading pairs across all runs."""
        column = getattr(BacktestResult, metric, BacktestResult.pnl)
        return db.query(BacktestResult).order_by(desc(column)).limit(limit).all()

    @staticmethod
    def get_results_by_strategy(
        db: Session, strategy_id: int, skip: int = 0, limit: int = 100
    ) -> List[BacktestResult]:
        """Get all backtest results for a specific strategy.

        Args:
            db: Database session
            strategy_id: Strategy ID to filter by
            skip: Number of results to skip (pagination)
            limit: Maximum results to return

        Returns:
            List of BacktestResult records for the strategy
        """
        return (
            db.query(BacktestResult)
            .join(BacktestRun, BacktestResult.run_id_fk == BacktestRun.id)
            .filter(BacktestRun.strategy_id == strategy_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_strategy_performance_summary(db: Session, strategy_id: int) -> dict:
        """Get aggregate performance metrics for a strategy across all runs.

        Args:
            db: Database session
            strategy_id: Strategy ID to aggregate

        Returns:
            Dictionary with aggregated metrics:
            - total_trades: Sum of all trades
            - total_pnl: Sum of all P&L
            - avg_win_rate: Average win rate across pairs
            - profitable_pairs: Count of pairs with positive P&L
            - best_pair: Pair with highest P&L
            - worst_pair: Pair with lowest P&L
        """
        results = (
            db.query(BacktestResult)
            .join(BacktestRun, BacktestResult.run_id_fk == BacktestRun.id)
            .filter(BacktestRun.strategy_id == strategy_id)
            .all()
        )

        if not results:
            return {
                "total_trades": 0,
                "total_pnl": 0.0,
                "avg_win_rate": 0.0,
                "profitable_pairs": 0,
                "best_pair": None,
                "worst_pair": None,
            }

        total_trades = sum(r.total_trades or 0 for r in results)
        total_pnl = sum(r.pnl or 0.0 for r in results)
        win_rates = [r.win_rate for r in results if r.win_rate is not None]
        profitable = [r for r in results if (r.pnl or 0.0) > 0.0]
        best = None
        worst = None
        if results:
            pnl_values = [(r, r.pnl or 0.0) for r in results]
            best = max(pnl_values, key=lambda x: x[1])[0]
            worst = min(pnl_values, key=lambda x: x[1])[0]

        return {
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "avg_win_rate": sum(win_rates) / len(win_rates) if win_rates else 0.0,
            "profitable_pairs": len(profitable),
            "best_pair": f"{best.market_1}/{best.market_2}" if best else None,
            "worst_pair": f"{worst.market_1}/{worst.market_2}" if worst else None,
            "num_pairs_tested": len(results),
        }


class TradeLogService:
    """Service for trade logs."""

    @staticmethod
    def create_trade(
        db: Session, result_id_fk: int, trade_number: int, trade_data: dict
    ) -> TradeLog:
        """Create trade log entry."""
        trade = TradeLog(
            result_id_fk=result_id_fk, trade_number=trade_number, **trade_data
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return trade

    @staticmethod
    def get_result_trades(db: Session, result_id_fk: int) -> List[TradeLog]:
        """Get all trades for a backtest result."""
        return db.query(TradeLog).filter(TradeLog.result_id_fk == result_id_fk).all()


class AuditLogService:
    """Service for audit logging."""

    @staticmethod
    def log_action(
        db: Session,
        action: str,
        resource_type: str,
        user_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log an action to audit trail."""
        audit = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            status=status,
            ip_address=ip_address,
            created_at=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        logger.info(f"Audit: {action} on {resource_type} by user {user_id}")
        return audit

    @staticmethod
    def get_user_actions(
        db: Session, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        """Get user action history."""
        return (
            db.query(AuditLog)
            .filter(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )


class BacktestStrategyService:
    """Service for backtest strategy management and CRUD operations."""

    @staticmethod
    def create_strategy(
        db: Session,
        user_id: int,
        name: str,
        description: str,
        category: str = "custom",
        is_public: bool = False,
        zscore_threshold: float = 1.5,
        stats_window: int = 21,
        max_half_life: float = 24.0,
        usd_per_trade: float = 10.0,
        usd_min_collateral: float = 100.0,
        close_at_zscore_cross: bool = True,
        transaction_fee: float = 0.0005,
        slippage: float = 0.001,
        starting_balance: float = 1000.0,
        candle_resolution: str = "1HOUR",
        max_history_days: int = 90,
        benchmark_symbol: str = "BTC-USD",
        risk_free_rate: float = 0.02,
    ) -> BacktestStrategy:
        """Create a new backtest strategy with all parameters."""
        strategy = BacktestStrategy(
            user_id=user_id,
            name=name,
            description=description,
            category=category,
            is_public=is_public,
            is_default=False,
            zscore_threshold=zscore_threshold,
            stats_window=stats_window,
            max_half_life=max_half_life,
            usd_per_trade=usd_per_trade,
            usd_min_collateral=usd_min_collateral,
            close_at_zscore_cross=close_at_zscore_cross,
            transaction_fee=transaction_fee,
            slippage=slippage,
            starting_balance=starting_balance,
            candle_resolution=candle_resolution,
            max_history_days=max_history_days,
            benchmark_symbol=benchmark_symbol,
            risk_free_rate=risk_free_rate,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        logger.info(f"Strategy created: {name} by user {user_id}")
        return strategy

    @staticmethod
    def get_strategy_by_id(db: Session, strategy_id: int) -> Optional[BacktestStrategy]:
        """Get strategy by ID."""
        return (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.id == strategy_id)
            .first()
        )

    @staticmethod
    def get_user_strategies(
        db: Session, user_id: int, skip: int = 0, limit: int = 50
    ) -> List[BacktestStrategy]:
        """Get all strategies for a user."""
        return (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.user_id == user_id)
            .order_by(desc(BacktestStrategy.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_public_strategies(
        db: Session, skip: int = 0, limit: int = 50
    ) -> List[BacktestStrategy]:
        """Get all public strategies available to all users."""
        return (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.is_public == True)
            .order_by(desc(BacktestStrategy.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_strategies_by_category(
        db: Session, category: str, skip: int = 0, limit: int = 50
    ) -> List[BacktestStrategy]:
        """Get strategies by category."""
        return (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.category == category)
            .order_by(desc(BacktestStrategy.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_strategy(
        db: Session, strategy_id: int, update_data: dict
    ) -> Optional[BacktestStrategy]:
        """Update strategy with new data."""
        strategy = (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.id == strategy_id)
            .first()
        )
        if not strategy:
            return None

        # Update allowed fields
        allowed_fields = {
            "name",
            "description",
            "category",
            "is_public",
            "is_default",
            "zscore_threshold",
            "stats_window",
            "max_half_life",
            "usd_per_trade",
            "usd_min_collateral",
            "close_at_zscore_cross",
            "find_cointegrated_pairs",
            "manage_exits",
            "place_trades",
            "abort_all_positions",
            "max_positions",
            "max_drawdown_pct",
            "stop_loss_pct",
            "take_profit_pct",
            "trailing_stop_pct",
            "rebalance_interval_hours",
            "position_timeout_hours",
        }

        for key, value in update_data.items():
            if key in allowed_fields:
                setattr(strategy, key, value)

        strategy.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(strategy)
        logger.info(f"Strategy updated: {strategy.name} (ID: {strategy_id})")
        return strategy

    @staticmethod
    def delete_strategy(db: Session, strategy_id: int) -> bool:
        """Delete strategy by ID."""
        strategy = (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.id == strategy_id)
            .first()
        )
        if not strategy:
            return False

        db.delete(strategy)
        db.commit()
        logger.info(f"Strategy deleted: {strategy.name} (ID: {strategy_id})")
        return True

    @staticmethod
    def set_default_strategy(
        db: Session, user_id: int, strategy_id: int
    ) -> Optional[BacktestStrategy]:
        """Set a strategy as the default for a user."""
        # Clear previous default
        db.query(BacktestStrategy).filter(
            and_(
                BacktestStrategy.user_id == user_id, BacktestStrategy.is_default == True
            )
        ).update({"is_default": False})

        # Set new default
        strategy = (
            db.query(BacktestStrategy)
            .filter(
                and_(
                    BacktestStrategy.id == strategy_id,
                    BacktestStrategy.user_id == user_id,
                )
            )
            .first()
        )

        if strategy:
            strategy.is_default = True
            db.commit()
            db.refresh(strategy)
            logger.info(f"Default strategy set: {strategy.name} for user {user_id}")

        return strategy

    @staticmethod
    def get_default_strategy(db: Session, user_id: int) -> Optional[BacktestStrategy]:
        """Get the default strategy for a user."""
        return (
            db.query(BacktestStrategy)
            .filter(
                and_(
                    BacktestStrategy.user_id == user_id,
                    BacktestStrategy.is_default == True,
                )
            )
            .first()
        )

    @staticmethod
    def update_last_used(db: Session, strategy_id: int) -> Optional[BacktestStrategy]:
        """Update the last_used_at timestamp for a strategy."""
        strategy = (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.id == strategy_id)
            .first()
        )
        if not strategy:
            return None

        strategy.last_used_at = datetime.utcnow()
        db.commit()
        db.refresh(strategy)
        return strategy

    @staticmethod
    def get_strategy_usage_stats(db: Session, strategy_id: int) -> dict:
        """Get usage statistics for a strategy (how many backtests used it)."""
        total_runs = (
            db.query(func.count(BacktestRun.id))
            .filter(BacktestRun.strategy_id == strategy_id)
            .scalar()
        ) or 0

        completed_runs = (
            db.query(func.count(BacktestRun.id))
            .filter(
                and_(
                    BacktestRun.strategy_id == strategy_id,
                    BacktestRun.status == "completed",
                )
            )
            .scalar()
        ) or 0

        avg_pnl = (
            db.query(func.avg(BacktestRun.total_pnl))
            .filter(
                and_(
                    BacktestRun.strategy_id == strategy_id,
                    BacktestRun.status == "completed",
                )
            )
            .scalar()
        ) or 0.0

        return {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": total_runs - completed_runs,
            "avg_pnl": float(avg_pnl),
            "success_rate": (completed_runs / total_runs * 100)
            if total_runs > 0
            else 0.0,
        }
