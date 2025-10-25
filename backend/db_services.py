"""
Database service layer for backtest operations.
Handles CRUD operations and complex queries.
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from .auth import hash_password, verify_password
from .database import (
    AuditLog,
    BacktestResult,
    BacktestRun,
    BacktestStrategy,
    RedisSetting,
    StrategyVersionHistory,
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
    ) -> list[type[BacktestRun]]:
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
    def get_latest_runs(db: Session, limit: int = 10) -> list[type[BacktestRun]]:
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
    ) -> list[type[BacktestResult]]:
        """Get all results for a backtest run."""
        return (
            db.query(BacktestResult)
            .filter(BacktestResult.run_id_fk == run_id_fk)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_profitable_pairs(db: Session, run_id_fk: int) -> list[type[BacktestResult]]:
        """Get profitable trading pairs from a run."""
        return (
            db.query(BacktestResult)
            .filter(and_(BacktestResult.run_id_fk == run_id_fk, BacktestResult.pnl > 0))
            .order_by(desc(BacktestResult.pnl))
            .all()
        )

    @staticmethod
    def aggregate_run_metrics(db: Session, run_id_pk: int) -> Optional[BacktestRun]:
        """Aggregate metrics from all BacktestResult and TradeLog records into BacktestRun.

        This function computes overall performance metrics from individual trades and results,
        and updates the BacktestRun record with aggregated statistics.

        Args:
            db: Database session
            run_id_pk: Primary key of BacktestRun record

        Returns:
            Updated BacktestRun object with aggregated metrics
        """
        run = db.query(BacktestRun).filter(BacktestRun.id == run_id_pk).first()
        if not run:
            return None

        # Get all trades for this run
        from .database import BacktestTrade

        trades = (
            db.query(BacktestTrade).filter(BacktestTrade.run_id_fk == run_id_pk).all()
        )

        if not trades:
            # No trades, backtest had zero trading activity
            run.total_trades = 0
            run.profitable_trades = 0
            run.losing_trades = 0
            run.win_rate = 0.0
            run.total_pnl = 0.0
            run.total_pnl_usd = 0.0
            run.ending_balance = run.starting_balance
            db.commit()
            return run

        # Aggregate trade metrics
        total_trades = len(trades)
        profitable_trades = len([t for t in trades if t.pnl and t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl and t.pnl < 0])
        total_pnl = sum([t.pnl for t in trades if t.pnl is not None])

        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate advanced metrics
        pnls = [t.pnl for t in trades if t.pnl is not None]

        # Sharpe Ratio calculation
        sharpe_ratio = None
        sortino_ratio = None
        profit_factor = None
        max_drawdown = None

        if len(pnls) > 1:
            import numpy as np

            returns = np.array(pnls)
            daily_returns = (
                returns / run.starting_balance
            )  # Normalize by starting balance

            # Sharpe Ratio: (mean return - risk_free_rate) / std_dev
            mean_return = np.mean(daily_returns)
            std_dev = np.std(daily_returns)
            risk_free_rate = 0.02 / 252  # Annualized 2% risk-free rate

            if std_dev > 0:
                sharpe_ratio = (mean_return - risk_free_rate) / std_dev * np.sqrt(252)

            # Sortino Ratio: (mean return - risk_free_rate) / downside_std_dev
            downside_returns = np.minimum(daily_returns, 0)
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                sortino_ratio = (
                    (mean_return - risk_free_rate) / downside_std * np.sqrt(252)
                )

            # Profit Factor: gross_profit / gross_loss
            gross_profit = sum([t.pnl for t in trades if t.pnl and t.pnl > 0])
            gross_loss = abs(sum([t.pnl for t in trades if t.pnl and t.pnl < 0]))
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss

            # Max Drawdown calculation
            cumulative_pnl = np.cumsum(returns)
            running_max = np.maximum.accumulate(cumulative_pnl)
            drawdown = (cumulative_pnl - running_max) / (running_max + 1e-9)
            max_drawdown = float(np.min(drawdown)) * 100 if len(drawdown) > 0 else 0.0

        # Update BacktestRun with aggregated metrics
        # CRITICAL: Convert numpy types to Python floats for SQLAlchemy compatibility
        run.total_trades = total_trades
        run.profitable_trades = profitable_trades
        run.losing_trades = losing_trades
        run.win_rate = float(win_rate)
        run.total_pnl = float(total_pnl)
        run.total_pnl_usd = float(total_pnl)
        run.sharpe_ratio = float(sharpe_ratio) if sharpe_ratio is not None else None
        run.sortino_ratio = float(sortino_ratio) if sortino_ratio is not None else None
        run.profit_factor = float(profit_factor) if profit_factor is not None else None
        run.max_drawdown = float(max_drawdown) if max_drawdown is not None else None
        run.ending_balance = float(run.starting_balance + total_pnl)

        db.commit()
        db.refresh(run)
        logger.info(
            f"Aggregated metrics for run {run.run_id}: {total_trades} trades, "
            f"${total_pnl:.2f} PnL, {win_rate:.1f}% win rate, "
            f"Sharpe: {sharpe_ratio or 'N/A'}"
        )
        return run

    @staticmethod
    def find_cached_backtest(
        db: Session,
        start_date: str,
        end_date: str,
        num_pairs: int,
        strategy_snapshot: Optional[dict] = None,
    ) -> Optional[BacktestRun]:
        """Find an existing completed backtest with identical parameters (cache-first lookup).

        Searches for a backtest run with the same date range, pair count, and strategy parameters.
        Returns the most recent completed matching run if found.

        Args:
            db: Database session
            start_date: Backtest start date (YYYY-MM-DD format)
            end_date: Backtest end date (YYYY-MM-DD format)
            num_pairs: Number of pairs analyzed
            strategy_snapshot: Strategy parameters dict (optional, compared if provided)

        Returns:
            BacktestRun object if matching completed backtest found, None otherwise
        """
        import json

        # Build query for matching backtests
        query = (
            db.query(BacktestRun)
            .filter(
                and_(
                    BacktestRun.status == "completed",  # Only completed runs
                    BacktestRun.start_date == start_date,
                    BacktestRun.end_date == end_date,
                    BacktestRun.num_pairs == num_pairs,
                )
            )
            .order_by(desc(BacktestRun.created_at))  # Most recent first
        )

        # Find matching runs
        candidates = query.all()

        if not candidates:
            return None

        # If no strategy snapshot provided, return most recent matching by dates/pairs
        if strategy_snapshot is None:
            logger.info(
                f"Found cached backtest: {candidates[0].run_id} "
                f"({candidates[0].start_date} to {candidates[0].end_date})"
            )
            return candidates[0]

        # Compare strategy parameters - find exact match
        for run in candidates:
            if run.strategy_snapshot is None:
                continue

            # Strategy snapshots might be JSON strings or dicts
            cached_strategy = run.strategy_snapshot
            if isinstance(cached_strategy, str):
                cached_strategy = json.loads(cached_strategy)

            # Compare all strategy parameters
            if cached_strategy == strategy_snapshot:
                logger.info(
                    f"Found cached backtest with matching strategy: {run.run_id} "
                    f"({run.start_date} to {run.end_date})"
                )
                return run

        logger.info(
            f"No cached backtest with matching strategy found for "
            f"{start_date} to {end_date} ({num_pairs} pairs)"
        )
        return None

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
    @staticmethod
    def create_strategy(
        db: Session,
        user_id: int,
        name: str,
        description: str,
        category: str = "custom",
        is_public: bool = False,
        resolution: str = "1HOUR",
        zscore_threshold: float = 1.5,
        stats_window: int = 21,
        max_half_life: int = 24,
        usd_per_trade: float = 10.0,
        usd_min_collateral: float = 100.0,
        close_at_zscore_cross: bool = True,
        find_cointegrated_pairs: bool = True,
        manage_exits: bool = True,
        place_trades: bool = True,
        abort_all_positions: bool = False,
        max_positions: int = 5,
        max_drawdown_pct: float = 15.0,
        stop_loss_pct: float = 2.0,
        take_profit_pct: float = 5.0,
        trailing_stop_pct: float = 1.0,
        rebalance_interval_hours: int = 24,
        position_timeout_hours: int = 72,
        initial_amount: float = 1000.0,
        transaction_fee: float = 0.0005,
        slippage: float = 0.001,
    ) -> BacktestStrategy:
        """Create a new backtest strategy with all parameters."""
        strategy = BacktestStrategy(
            user_id=user_id,
            name=name,
            description=description,
            category=category,
            is_public=is_public,
            is_default=False,
            candle_resolution=resolution,
            zscore_threshold=zscore_threshold,
            stats_window=stats_window,
            max_half_life=max_half_life,
            usd_per_trade=usd_per_trade,
            usd_min_collateral=usd_min_collateral,
            close_at_zscore_cross=close_at_zscore_cross,
            find_cointegrated_pairs=find_cointegrated_pairs,
            manage_exits=manage_exits,
            place_trades=place_trades,
            abort_all_positions=abort_all_positions,
            max_positions=max_positions,
            max_drawdown_pct=max_drawdown_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            trailing_stop_pct=trailing_stop_pct,
            rebalance_interval_hours=rebalance_interval_hours,
            position_timeout_hours=position_timeout_hours,
            initial_amount=initial_amount,
            transaction_fee=transaction_fee,
            slippage=slippage,
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
            "resolution",
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
            "initial_amount",
            "transaction_fee",
            "slippage",
        }

        for key, value in update_data.items():
            if key in allowed_fields:
                # Map 'resolution' to 'candle_resolution' in database
                if key == "resolution":
                    setattr(strategy, "candle_resolution", value)
                else:
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


class RedisSettingsService:
    """Service for Redis configuration and settings management."""

    @staticmethod
    def get_redis_settings(db: Session) -> Optional[dict]:
        """Get current Redis settings from database."""
        from .database import RedisSetting

        settings = db.query(RedisSetting).first()
        if not settings:
            return None

        return {
            "id": settings.id,
            "enabled": settings.enabled,
            "host": settings.host,
            "port": settings.port,
            "db": settings.db,
            "password": "***" if settings.password else None,  # Don't expose password
            "ssl": settings.ssl,
            "timeout": settings.timeout,
            "max_connections": settings.max_connections,
            "cache_ttl_seconds": settings.cache_ttl_seconds,
            "cache_backtest_results": settings.cache_backtest_results,
            "cache_market_data": settings.cache_market_data,
            "cache_analysis_results": settings.cache_analysis_results,
            "last_connection_test": settings.last_connection_test,
            "last_connection_status": settings.last_connection_status,
            "total_cache_hits": settings.total_cache_hits,
            "total_cache_misses": settings.total_cache_misses,
        }

    @staticmethod
    def update_redis_settings(
        db: Session,
        enabled: Optional[bool] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[int] = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = None,
        timeout: Optional[int] = None,
        max_connections: Optional[int] = None,
        cache_ttl_seconds: Optional[int] = None,
        cache_backtest_results: Optional[bool] = None,
        cache_market_data: Optional[bool] = None,
        cache_analysis_results: Optional[bool] = None,
    ) -> Optional[dict]:
        """Update Redis settings."""
        from .database import RedisSetting

        settings = db.query(RedisSetting).first()
        if not settings:
            # Create default settings
            settings = RedisSetting()
            db.add(settings)

        # Update only provided fields
        if enabled is not None:
            settings.enabled = enabled
        if host is not None:
            settings.host = host
        if port is not None:
            settings.port = port
        if database is not None:
            settings.db = database
        if password is not None:
            settings.password = password
        if ssl is not None:
            settings.ssl = ssl
        if timeout is not None:
            settings.timeout = timeout
        if max_connections is not None:
            settings.max_connections = max_connections
        if cache_ttl_seconds is not None:
            settings.cache_ttl_seconds = cache_ttl_seconds
        if cache_backtest_results is not None:
            settings.cache_backtest_results = cache_backtest_results
        if cache_market_data is not None:
            settings.cache_market_data = cache_market_data
        if cache_analysis_results is not None:
            settings.cache_analysis_results = cache_analysis_results

        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)

        logger.info("Redis settings updated")
        return RedisSettingsService.get_redis_settings(db)

    @staticmethod
    def test_redis_connection(db: Session) -> dict:
        """Test Redis connection and update status in database."""
        from .database import RedisSetting
        from redis_service import get_redis_service

        redis_service = get_redis_service()
        status = redis_service.check_connection()

        settings = db.query(RedisSetting).first()
        if settings:
            settings.last_connection_test = datetime.utcnow()
            settings.last_connection_status = (
                "connected" if status.get("connected") else "failed"
            )
            db.commit()

        return status

    @staticmethod
    def get_cache_stats(db: Session) -> dict:
        """Get cache statistics."""
        from redis_service import get_redis_service

        redis_service = get_redis_service()
        stats = redis_service.get_cache_stats()

        settings = db.query(RedisSetting).first()
        if settings:
            stats["cache_ttl_seconds"] = settings.cache_ttl_seconds
            stats["cache_backtest_results"] = settings.cache_backtest_results
            stats["cache_market_data"] = settings.cache_market_data
            stats["cache_analysis_results"] = settings.cache_analysis_results

        return stats

    @staticmethod
    def toggle_redis_enabled(db: Session, enabled: bool) -> dict:
        """Toggle Redis caching on/off."""
        from .database import RedisSetting

        settings = db.query(RedisSetting).first()
        if not settings:
            settings = RedisSetting(enabled=enabled)
            db.add(settings)
        else:
            settings.enabled = enabled

        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)

        logger.info(f"Redis caching {'enabled' if enabled else 'disabled'}")


class StrategyVersionHistoryService:
    """Service for managing strategy version history and version control."""

    @staticmethod
    def create_version(
        db: Session,
        strategy_id: int,
        config_snapshot: dict,
        version_number: int,
        created_by_user_id: Optional[int] = None,
        change_description: Optional[str] = None,
        changes: Optional[dict] = None,
    ):
        """Create a new strategy version with configuration snapshot."""
        version = StrategyVersionHistory(
            strategy_id=strategy_id,
            version_number=version_number,
            config_snapshot=config_snapshot,
            change_description=change_description,
            changes=changes,
            created_by_user_id=created_by_user_id,
            created_at=datetime.utcnow(),
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        logger.info(
            f"Strategy version created: Strategy {strategy_id} v{version_number}"
        )
        return version

    @staticmethod
    def get_version_by_id(db: Session, version_id: int):
        """Get strategy version by ID."""
        return (
            db.query(StrategyVersionHistory)
            .filter(StrategyVersionHistory.id == version_id)
            .first()
        )

    @staticmethod
    def get_strategy_versions(
        db: Session, strategy_id: int, skip: int = 0, limit: int = 50
    ) -> list:
        """Get all versions for a strategy, ordered by version number descending."""
        return (
            db.query(StrategyVersionHistory)
            .filter(StrategyVersionHistory.strategy_id == strategy_id)
            .order_by(desc(StrategyVersionHistory.version_number))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_latest_version(db: Session, strategy_id: int):
        """Get the latest version of a strategy."""
        return (
            db.query(StrategyVersionHistory)
            .filter(StrategyVersionHistory.strategy_id == strategy_id)
            .order_by(desc(StrategyVersionHistory.version_number))
            .first()
        )

    @staticmethod
    def get_version_by_number(db: Session, strategy_id: int, version_number: int):
        """Get specific version by strategy and version number."""
        return (
            db.query(StrategyVersionHistory)
            .filter(
                and_(
                    StrategyVersionHistory.strategy_id == strategy_id,
                    StrategyVersionHistory.version_number == version_number,
                )
            )
            .first()
        )

    @staticmethod
    def get_next_version_number(db: Session, strategy_id: int) -> int:
        """Get the next version number for a strategy."""
        latest = (
            db.query(StrategyVersionHistory)
            .filter(StrategyVersionHistory.strategy_id == strategy_id)
            .order_by(desc(StrategyVersionHistory.version_number))
            .first()
        )
        return (latest.version_number + 1) if latest else 1

    @staticmethod
    def track_config_changes(old_config: dict, new_config: dict) -> dict:
        """Track which configuration fields changed between versions."""
        changes = {}
        for key in set(list(old_config.keys()) + list(new_config.keys())):
            old_value = old_config.get(key)
            new_value = new_config.get(key)
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}
        return changes if changes else None


# Module-level utility function for data validation
def validate_results_quality(results: List[BacktestResult]) -> dict:
    """
    Validate backtest results for consistency issues.
    Returns quality score and list of warnings.

    Args:
        results: List of BacktestResult objects to validate

    Returns:
        Dictionary with quality score (0-100), warnings list, and fixes applied
    """
    warnings = []

    for result in results:
        # Check 1: Win rate must be 0-100%
        if result.win_rate is not None and (
            result.win_rate < 0 or result.win_rate > 100
        ):
            warnings.append(
                f"{result.market_1}/{result.market_2}: "
                f"Win rate {result.win_rate}% outside valid range [0-100%]"
            )

        # Check 2: Profitable trades must be <= total trades
        profitable = result.profitable_trades or 0
        total = result.total_trades or 0
        if profitable > total:
            warnings.append(
                f"{result.market_1}/{result.market_2}: "
                f"Profitable trades ({profitable}) > total trades ({total})"
            )

        # Check 3: Losing trades must be <= total trades
        losing = result.losing_trades or 0
        if losing > total:
            warnings.append(
                f"{result.market_1}/{result.market_2}: "
                f"Losing trades ({losing}) > total trades ({total})"
            )

        # Check 4: Profit factor must be >= 0
        if result.profit_factor is not None and result.profit_factor < 0:
            warnings.append(
                f"{result.market_1}/{result.market_2}: "
                f"Negative profit factor {result.profit_factor}"
            )

        # Check 5: Sum of profitable + losing should not exceed total
        total_categorized = profitable + losing
        if total_categorized > total:
            warnings.append(
                f"{result.market_1}/{result.market_2}: "
                f"Profitable ({profitable}) + Losing ({losing}) > Total ({total})"
            )

        # Check 6: Max drawdown should not exceed -100%
        if result.max_drawdown is not None and result.max_drawdown < -100:
            warnings.append(
                f"{result.market_1}/{result.market_2}: "
                f"Extreme max drawdown {result.max_drawdown}% (likely data error)"
            )

    # Calculate quality score
    # Start at 100, deduct 10 points per warning (capped at 0)
    quality_score = max(0, 100 - len(warnings) * 10)

    logger.info(
        f"Results validation: {len(results)} results, "
        f"quality score: {quality_score}, warnings: {len(warnings)}"
    )

    return {
        "score": quality_score,
        "warnings": warnings[:10],  # Limit to 10 warnings for API response
        "fixes_applied": [],
        "total_results": len(results),
    }
