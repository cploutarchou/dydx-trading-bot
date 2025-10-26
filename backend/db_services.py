"""
Database service layer for backtest operations.
Handles CRUD operations and complex queries using raw SQL.
"""

import logging
from datetime import datetime
from typing import List, Optional
import datetime
import psycopg2
import sqlite3
import json

from auth import hash_password, verify_password
from database import execute_query

logger = logging.getLogger(__name__)


def row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys') and hasattr(row, '__getitem__'):
        # sqlite3.Row or similar
        return {k: row[k] for k in row.keys()}
    if hasattr(row, '_fields'):  # namedtuple
        return row._asdict()
    # fallback: try to convert
    try:
        return dict(row)
    except Exception:
        return None


class UserService:
    """Service for user management using raw SQL."""

    @staticmethod
    def create_user(username: str, email: str, password: str) -> dict:
        """Create new user account."""
        # Check if user already exists
        user = execute_query(
            "SELECT * FROM users WHERE username = %s OR email = %s",
            (username, email),
            fetchone=True,
        )
        if user:
            raise ValueError(f"User {username} already exists")
        hashed_pwd = hash_password(password)
        execute_query(
            "INSERT INTO users (username, email, hashed_password, is_active, created_at) VALUES (%s, %s, %s, 1, %s) ",
            (username, email, hashed_pwd, datetime.datetime.now(datetime.UTC)),
            commit=True,
        )
        user = execute_query(
            "SELECT * FROM users WHERE username = %s",
            (username,),
            fetchone=True,
        )
        logger.info(f"User created: {username}")
        return dict(user) if user else None

    @staticmethod
    def get_user_by_username(username: str) -> Optional[dict]:
        user = execute_query(
            "SELECT * FROM users WHERE username = %s",
            (username,),
            fetchone=True,
        )
        return row_to_dict(user) if user else None

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[dict]:
        user = execute_query(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetchone=True,
        )
        return row_to_dict(user) if user else None

    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[dict]:
        user = UserService.get_user_by_username(username)
        if not user or not verify_password(password, user["hashed_password"]):
            return None
        # Update last login
        execute_query(
            "UPDATE users SET last_login = %s WHERE id = %s",
            (datetime.datetime.now(datetime.UTC), user["id"]),
            commit=True,
        )
        return user

    @staticmethod
    def deactivate_user(user_id: int) -> bool:
        user = UserService.get_user_by_id(user_id)
        if not user:
            return False
        execute_query(
            "UPDATE users SET is_active = 0 WHERE id = %s",
            (user_id,),
            commit=True,
        )
        logger.info(f"User deactivated: {user['username']}")
        return True


class BacktestRunService:
    """Service for backtest run management."""

    @staticmethod
    def create_run(
        run_id: str,
        start_date: str,
        end_date: str,
        num_pairs: int,
        total_markets: int,
        user_id: Optional[int] = None,
        config: Optional[dict] = None,
        strategy_id: Optional[int] = None,
        strategy_snapshot: Optional[dict] = None,
    ) -> dict:
        """Create new backtest run."""
        execute_query(
            "INSERT INTO backtest_runs (run_id, status, start_date, end_date, num_pairs, total_markets, user_id, config, strategy_id, strategy_snapshot, created_at, started_at) VALUES (%s, 'running', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                run_id,
                start_date,
                end_date,
                num_pairs,
                total_markets,
                user_id,
                config,
                strategy_id,
                strategy_snapshot,
                datetime.datetime.now(datetime.UTC),
                datetime.datetime.now(datetime.UTC),
            ),
            commit=True,
        )
        run = execute_query(
            "SELECT * FROM backtest_runs WHERE run_id = %s",
            (run_id,),
            fetchone=True,
        )
        logger.info(f"Backtest run created: {run_id}")
        return dict(run) if run else None

    @staticmethod
    def get_run_by_id(run_id_pk: int) -> Optional[dict]:
        """Get backtest run by ID."""
        run = execute_query(
            "SELECT * FROM backtest_runs WHERE id = %s",
            (run_id_pk,),
            fetchone=True,
        )
        return dict(run) if run else None

    @staticmethod
    def get_run_by_run_id(run_id: str) -> Optional[dict]:
        """Get backtest run by run_id string."""
        run = execute_query(
            "SELECT * FROM backtest_runs WHERE run_id = %s",
            (run_id,),
            fetchone=True,
        )
        return dict(run) if run else None

    @staticmethod
    def get_user_runs(
        user_id: int, skip: int = 0, limit: int = 50
    ) -> list[dict]:
        """Get all backtest runs for a user."""
        return execute_query(
            "SELECT * FROM backtest_runs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (user_id, limit, skip),
        )

    @staticmethod
    def update_run_status(run_id_pk: int, status: str) -> Optional[dict]:
        """Update backtest run status."""
        run = BacktestRunService.get_run_by_id(run_id_pk)
        if not run:
            return None

        execute_query(
            "UPDATE backtest_runs SET status = %s, completed_at = %s WHERE id = %s",
            (status, datetime.datetime.now(datetime.UTC) if status == "completed" else None, run_id_pk),
            commit=True,
        )
        run = BacktestRunService.get_run_by_id(run_id_pk)
        return run

    @staticmethod
    def update_run_metrics(run_id_pk: int, metrics: dict) -> Optional[dict]:
        """Update backtest run with metrics."""
        run = BacktestRunService.get_run_by_id(run_id_pk)
        if not run:
            return None

        # Update metrics from dict
        for key, value in metrics.items():
            execute_query(
                f"UPDATE backtest_runs SET {key} = %s WHERE id = %s",
                (value, run_id_pk),
                commit=True,
            )

        run = BacktestRunService.get_run_by_id(run_id_pk)
        return run

    @staticmethod
    def get_latest_runs(limit: int = 10) -> list[dict]:
        """Get latest backtest runs."""
        return execute_query(
            "SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )

    @staticmethod
    def get_run_stats() -> dict:
        """Get aggregate statistics for backtest runs."""
        total_runs = execute_query("SELECT COUNT(*) FROM backtest_runs", fetchone=True)[0]
        completed_runs = execute_query(
            "SELECT COUNT(*) FROM backtest_runs WHERE status = 'completed'", fetchone=True
        )[0]
        avg_pnl = execute_query(
            "SELECT AVG(total_pnl) FROM backtest_runs WHERE status = 'completed'", fetchone=True
        )[0]

        return {
            "total_runs": total_runs or 0,
            "completed_runs": completed_runs or 0,
            "failed_runs": execute_query(
                "SELECT COUNT(*) FROM backtest_runs WHERE status = 'failed'", fetchone=True
            )[0]
            or 0,
            "avg_pnl": float(avg_pnl) if avg_pnl else 0.0,
        }


class BacktestResultService:
    """Service for individual backtest results."""

    @staticmethod
    def create_result(
        run_id_fk: int, market_1: str, market_2: str, metrics: dict
    ) -> dict:
        """Create backtest result for a pair."""
        execute_query(
            "INSERT INTO backtest_results (run_id_fk, market_1, market_2, {}) VALUES (%s, %s, %s, {})".format(
                ", ".join(metrics.keys()), ", ".join("%s" * len(metrics))
            ),
            (run_id_fk, market_1, market_2, *metrics.values()),
            commit=True,
        )
        result = execute_query(
            "SELECT * FROM backtest_results WHERE run_id_fk = %s AND market_1 = %s AND market_2 = %s",
            (run_id_fk, market_1, market_2),
            fetchone=True,
        )
        return dict(result) if result else None

    @staticmethod
    def get_run_results(
        run_id_fk: int, skip: int = 0, limit: int = 1000
    ) -> list[dict]:
        """Get all results for a backtest run."""
        return execute_query(
            "SELECT * FROM backtest_results WHERE run_id_fk = %s LIMIT %s OFFSET %s",
            (run_id_fk, limit, skip),
        )

    @staticmethod
    def get_profitable_pairs(run_id_fk: int) -> list[dict]:
        """Get profitable trading pairs from a run."""
        return execute_query(
            "SELECT * FROM backtest_results WHERE run_id_fk = %s AND pnl > 0 ORDER BY pnl DESC",
            (run_id_fk,),
        )

    @staticmethod
    def aggregate_run_metrics(run_id_pk: int) -> Optional[dict]:
        """Aggregate metrics from all BacktestResult and TradeLog records into BacktestRun.

        This function computes overall performance metrics from individual trades and results,
        and updates the BacktestRun record with aggregated statistics.

        Args:
            run_id_pk: Primary key of BacktestRun record

        Returns:
            Updated BacktestRun object with aggregated metrics
        """
        run = BacktestRunService.get_run_by_id(run_id_pk)
        if not run:
            return None

        # Get all trades for this run
        trades = execute_query(
            "SELECT * FROM backtest_trades WHERE run_id_fk = %s",
            (run_id_pk,),
        )

        if not trades:
            # No trades, backtest had zero trading activity
            execute_query(
                "UPDATE backtest_runs SET total_trades = 0, profitable_trades = 0, losing_trades = 0, win_rate = 0, total_pnl = 0, total_pnl_usd = 0, ending_balance = starting_balance WHERE id = %s",
                (run_id_pk,),
                commit=True,
            )
            return run

        # Aggregate trade metrics
        total_trades = len(trades)
        profitable_trades = len([t for t in trades if t["pnl"] and t["pnl"] > 0])
        losing_trades = len([t for t in trades if t["pnl"] and t["pnl"] < 0])
        total_pnl = sum([t["pnl"] for t in trades if t["pnl"] is not None])

        win_rate = (
            profitable_trades / total_trades * 100
            if total_trades > 0
            else 0.0
        )

        # Calculate advanced metrics
        pnls = [t["pnl"] for t in trades if t["pnl"] is not None]

        # Sharpe Ratio calculation
        sharpe_ratio = None
        sortino_ratio = None
        profit_factor = None
        max_drawdown = None

        if len(pnls) > 1:
            import numpy as np

            returns = np.array(pnls)
            daily_returns = returns / run["starting_balance"]  # Normalize by starting balance

            # Sharpe Ratio: (mean return - risk_free_rate) / std_dev
            mean_return = np.mean(daily_returns)
            std_dev = np.std(daily_returns)
            risk_free_rate = 0.02 / 252  # Annualized 2% risk-free rate

            if std_dev > 0:
                sharpe_ratio = (mean_return - risk_free_rate) / std_dev * np.sqrt(252.0)

            # Sortino Ratio: (mean return - risk_free_rate) / downside_std_dev
            downside_returns = np.minimum(daily_returns, 0)
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                sortino_ratio = (
                    (mean_return - risk_free_rate) / downside_std * np.sqrt(252.0)
                )

            # Profit Factor: gross_profit / gross_loss
            gross_profit = sum([t["pnl"] for t in trades if t["pnl"] and t["pnl"] > 0])
            gross_loss = abs(sum([t["pnl"] for t in trades if t["pnl"] and t["pnl"] < 0]))
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss

            # Max Drawdown calculation
            cumulative_pnl = np.cumsum(returns)
            running_max = np.maximum.accumulate(cumulative_pnl)
            drawdown = (cumulative_pnl - running_max) / (running_max + 1e-9)
            max_drawdown = float(np.min(drawdown)) * 100 if len(drawdown) > 0 else 0.0

        # Update BacktestRun with aggregated metrics
        # CRITICAL: Convert numpy types to Python floats for SQLAlchemy compatibility
        execute_query(
            "UPDATE backtest_runs SET total_trades = %s, profitable_trades = %s, losing_trades = %s, win_rate = %s, total_pnl = %s, total_pnl_usd = %s, sharpe_ratio = %s, sortino_ratio = %s, profit_factor = %s, max_drawdown = %s, ending_balance = %s WHERE id = %s",
            (
                total_trades,
                profitable_trades,
                losing_trades,
                float(win_rate),
                float(total_pnl),
                float(total_pnl),
                float(sharpe_ratio) if sharpe_ratio is not None else None,
                float(sortino_ratio) if sortino_ratio is not None else None,
                float(profit_factor) if profit_factor is not None else None,
                float(max_drawdown) if max_drawdown is not None else None,
                float(run["starting_balance"] + total_pnl),
                run_id_pk,
            ),
            commit=True,
        )

        logger.info(
            f"Aggregated metrics for run {run['run_id']}: {total_trades} trades, "
            f"${total_pnl:.2f} PnL, {win_rate:.1f}% win rate, "
            f"Sharpe: {sharpe_ratio or 'N/A'}"
        )
        return run

    @staticmethod
    def find_cached_backtest(
        start_date: str,
        end_date: str,
        num_pairs: int,
        strategy_snapshot: Optional[dict] = None,
    ) -> Optional[dict]:
        """Find an existing completed backtest with identical parameters (cache-first lookup).

        Searches for a backtest run with the same date range, pair count, and strategy parameters.
        Returns the most recent completed matching run if found.

        Args:
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
            "SELECT * FROM backtest_runs WHERE status = 'completed' AND start_date = %s AND end_date = %s AND num_pairs = %s ORDER BY created_at DESC"
        )

        # Find matching runs
        candidates = execute_query(query, (start_date, end_date, num_pairs))

        if not candidates:
            return None

        # If no strategy snapshot provided, return most recent matching by dates/pairs
        if strategy_snapshot is None:
            logger.info(
                f"Found cached backtest: {candidates[0]['run_id']} "
                f"({candidates[0]['start_date']} to {candidates[0]['end_date']})"
            )
            return dict(candidates[0])

        # Compare strategy parameters - find exact match
        for run in candidates:
            if run["strategy_snapshot"] is None:
                continue

            # Strategy snapshots might be JSON strings or dicts
            cached_strategy = run["strategy_snapshot"]
            if isinstance(cached_strategy, str):
                cached_strategy = json.loads(cached_strategy)

            # Compare all strategy parameters
            if cached_strategy == strategy_snapshot:
                logger.info(
                    f"Found cached backtest with matching strategy: {run['run_id']} "
                    f"({run['start_date']} to {run['end_date']})"
                )
                return dict(run)

        logger.info(
            f"No cached backtest with matching strategy found for "
            f"{start_date} to {end_date} ({num_pairs} pairs)"
        )
        return None

    @staticmethod
    def get_top_pairs(
        limit: int = 10, metric: str = "pnl"
    ) -> List[dict]:
        """Get top trading pairs across all runs."""
        column = metric if metric in ["pnl", "total_pnl", "sharpe_ratio", "sortino_ratio", "profit_factor", "max_drawdown"] else "pnl"
        return execute_query(
            f"SELECT * FROM backtest_results ORDER BY {column} DESC LIMIT %s",
            (limit,),
        )

    @staticmethod
    def get_results_by_strategy(
        strategy_id: int, skip: int = 0, limit: int = 100
    ) -> List[dict]:
        """Get all backtest results for a specific strategy.

        Args:
            strategy_id: Strategy ID to filter by
            skip: Number of results to skip (pagination)
            limit: Maximum results to return

        Returns:
            List of BacktestResult records for the strategy
        """
        return execute_query(
            "SELECT * FROM backtest_results br JOIN backtest_runs b ON br.run_id_fk = b.id WHERE b.strategy_id = %s LIMIT %s OFFSET %s",
            (strategy_id, limit, skip),
        )

    @staticmethod
    def get_strategy_performance_summary(strategy_id: int) -> dict:
        """Get aggregate performance metrics for a strategy across all runs.

        Args:
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
        results = execute_query(
            "SELECT * FROM backtest_results br JOIN backtest_runs b ON br.run_id_fk = b.id WHERE b.strategy_id = %s",
            (strategy_id,),
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

        total_trades = sum(r["total_trades"] or 0 for r in results)
        total_pnl = sum(r["pnl"] or 0.0 for r in results)
        win_rates = [r["win_rate"] for r in results if r["win_rate"] is not None]
        profitable = [r for r in results if (r["pnl"] or 0.0) > 0.0]
        best = None
        worst = None
        if results:
            pnl_values = [(r, r["pnl"] or 0.0) for r in results]
            best = max(pnl_values, key=lambda x: x[1])[0]
            worst = min(pnl_values, key=lambda x: x[1])[0]

        return {
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "avg_win_rate": sum(win_rates) / len(win_rates) if win_rates else 0.0,
            "profitable_pairs": len(profitable),
            "best_pair": f"{best['market_1']}/{best['market_2']}" if best else None,
            "worst_pair": f"{worst['market_1']}/{worst['market_2']}" if worst else None,
            "num_pairs_tested": len(results),
        }


class TradeLogService:
    """Service for trade logs."""

    @staticmethod
    def create_trade(
        result_id_fk: int, trade_number: int, trade_data: dict
    ) -> dict:
        """Create trade log entry."""
        execute_query(
            "INSERT INTO trade_logs (result_id_fk, trade_number, {}) VALUES (%s, %s, {})".format(
                ", ".join(trade_data.keys()), ", ".join("%" * len(trade_data))
            ),
            (result_id_fk, trade_number, *trade_data.values()),
            commit=True,
        )
        trade = execute_query(
            "SELECT * FROM trade_logs WHERE result_id_fk = %s AND trade_number = %s",
            (result_id_fk, trade_number),
            fetchone=True,
        )
        return dict(trade) if trade else None

    @staticmethod
    def get_result_trades(result_id_fk: int) -> list[dict]:
        """Get all trades for a backtest result."""
        return execute_query(
            "SELECT * FROM trade_logs WHERE result_id_fk = %s",
            (result_id_fk,),
        )


class AuditLogService:
    """Service for audit logging."""

    @staticmethod
    def log_action(
        action: str,
        resource_type: str,
        user_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
    ) -> dict:
        """Log an action to audit trail."""
        # Serialize details dict to JSON string if needed
        details_str = json.dumps(details) if details is not None else None
        execute_query(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, status, ip_address, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                user_id,
                action,
                resource_type,
                resource_id,
                details_str,
                status,
                ip_address,
                datetime.datetime.now(datetime.UTC),
            ),
            commit=True,
        )
        logger.info(f"Audit: {action} on {resource_type} by user {user_id}")
        return {}

    @staticmethod
    def get_user_actions(
        user_id: int, skip: int = 0, limit: int = 100
    ) -> List[dict]:
        """Get user action history."""
        return execute_query(
            "SELECT * FROM audit_logs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (user_id, limit, skip),
        )


class BacktestStrategyService:
    """Service for backtest strategy management and CRUD operations."""

    @staticmethod
    def create_strategy(
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
    ) -> dict:
        """Create a new backtest strategy with all parameters."""
        execute_query(
            "INSERT INTO backtest_strategies (user_id, name, description, category, is_public, is_default, candle_resolution, zscore_threshold, stats_window, max_half_life, usd_per_trade, usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs, manage_exits, place_trades, abort_all_positions, max_positions, max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct, rebalance_interval_hours, position_timeout_hours, initial_amount, transaction_fee, slippage, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                user_id,
                name,
                description,
                category,
                is_public,
                resolution,
                zscore_threshold,
                stats_window,
                max_half_life,
                usd_per_trade,
                usd_min_collateral,
                close_at_zscore_cross,
                find_cointegrated_pairs,
                manage_exits,
                place_trades,
                abort_all_positions,
                max_positions,
                max_drawdown_pct,
                stop_loss_pct,
                take_profit_pct,
                trailing_stop_pct,
                rebalance_interval_hours,
                position_timeout_hours,
                initial_amount,
                transaction_fee,
                slippage,
                datetime.datetime.now(datetime.UTC),
                datetime.datetime.now(datetime.UTC),
            ),
            commit=True,
        )
        strategy = execute_query(
            "SELECT * FROM backtest_strategies WHERE user_id = %s AND name = %s",
            (user_id, name),
            fetchone=True,
        )
        logger.info(f"Strategy created: {name} by user {user_id}")
        return dict(strategy) if strategy else None

    @staticmethod
    def get_strategy_by_id(strategy_id: int) -> Optional[dict]:
        """Get strategy by ID."""
        strategy = execute_query(
            "SELECT * FROM backtest_strategies WHERE id = %s",
            (strategy_id,),
            fetchone=True,
        )
        return dict(strategy) if strategy else None

    @staticmethod
    def get_user_strategies(
        user_id: int, skip: int = 0, limit: int = 50
    ) -> List[dict]:
        """Get all strategies for a user."""
        return execute_query(
            "SELECT * FROM backtest_strategies WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (user_id, limit, skip),
        )

    @staticmethod
    def get_public_strategies(
        skip: int = 0, limit: int = 50
    ) -> List[dict]:
        """Get all public strategies available to all users."""
        return execute_query(
            "SELECT * FROM backtest_strategies WHERE is_public = 1 ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (limit, skip),
        )

    @staticmethod
    def get_strategies_by_category(
        category: str, skip: int = 0, limit: int = 50
    ) -> List[dict]:
        """Get strategies by category."""
        return execute_query(
            "SELECT * FROM backtest_strategies WHERE category = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (category, limit, skip),
        )

    @staticmethod
    def update_strategy(
        strategy_id: int, update_data: dict
    ) -> Optional[dict]:
        """Update strategy with new data."""
        strategy = BacktestStrategyService.get_strategy_by_id(strategy_id)
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

        set_clause = ", ".join(
            f"{key} = %s" for key in update_data.keys() if key in allowed_fields
        )
        values = [v for v in update_data.values() if v is not None] + [strategy_id]

        execute_query(
            f"UPDATE backtest_strategies SET {set_clause} WHERE id = %s",
            values,
            commit=True,
        )
        strategy = BacktestStrategyService.get_strategy_by_id(strategy_id)
        logger.info(f"Strategy updated: {strategy['name']} (ID: {strategy_id})")
        return strategy

    @staticmethod
    def delete_strategy(strategy_id: int) -> bool:
        """Delete strategy by ID."""
        strategy = BacktestStrategyService.get_strategy_by_id(strategy_id)
        if not strategy:
            return False

        execute_query(
            "DELETE FROM backtest_strategies WHERE id = %s",
            (strategy_id,),
            commit=True,
        )
        logger.info(f"Strategy deleted: {strategy['name']} (ID: {strategy_id})")
        return True

    @staticmethod
    def set_default_strategy(
        user_id: int, strategy_id: int
    ) -> Optional[dict]:
        """Set a strategy as the default for a user."""
        # Clear previous default
        execute_query(
            "UPDATE backtest_strategies SET is_default = 0 WHERE user_id = %s",
            (user_id,),
            commit=True,
        )

        # Set new default
        strategy = (
            execute_query(
                "SELECT * FROM backtest_strategies WHERE id = %s AND user_id = %s",
                (strategy_id, user_id),
                fetchone=True,
            )
        )

        if strategy:
            execute_query(
                "UPDATE backtest_strategies SET is_default = 1 WHERE id = %s",
                (strategy_id,),
                commit=True,
            )
            logger.info(f"Default strategy set: {strategy['name']} for user {user_id}")

        return dict(strategy) if strategy else None

    @staticmethod
    def get_default_strategy(user_id: int) -> Optional[dict]:
        """Get the default strategy for a user."""
        strategy = execute_query(
            "SELECT * FROM backtest_strategies WHERE user_id = %s AND is_default = 1",
            (user_id,),
            fetchone=True,
        )
        return dict(strategy) if strategy else None

    @staticmethod
    def update_last_used(strategy_id: int) -> Optional[dict]:
        """Update the last_used_at timestamp for a strategy."""
        strategy = BacktestStrategyService.get_strategy_by_id(strategy_id)
        if not strategy:
            return None

        execute_query(
            "UPDATE backtest_strategies SET last_used_at = %s WHERE id = %s",
            (datetime.datetime.now(datetime.UTC), strategy_id),
            commit=True,
        )
        return strategy

    @staticmethod
    def get_strategy_usage_stats(strategy_id: int) -> dict:
        """Get usage statistics for a strategy (how many backtests used it)."""
        total_runs = (
            execute_query(
                "SELECT COUNT(*) FROM backtest_runs WHERE strategy_id = %s",
                (strategy_id,),
                fetchone=True,
            )
            or (0,)
        )[0]

        completed_runs = (
            execute_query(
                "SELECT COUNT(*) FROM backtest_runs WHERE strategy_id = %s AND status = 'completed'",
                (strategy_id,),
                fetchone=True,
            )
            or (0,)
        )[0]

        avg_pnl = (
            execute_query(
                "SELECT AVG(total_pnl) FROM backtest_runs WHERE strategy_id = %s AND status = 'completed'",
                (strategy_id,),
                fetchone=True,
            )
            or (0.0,)
        )[0]

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
    def get_redis_settings() -> Optional[dict]:
        """Get current Redis settings from database."""
        settings = execute_query("SELECT * FROM redis_settings", fetchone=True)
        if not settings:
            return None

        return {
            "id": settings["id"],
            "enabled": settings["enabled"],
            "host": settings["host"],
            "port": settings["port"],
            "db": settings["db"],
            "password": "***" if settings["password"] else None,  # Don't expose password
            "ssl": settings["ssl"],
            "timeout": settings["timeout"],
            "max_connections": settings["max_connections"],
            "cache_ttl_seconds": settings["cache_ttl_seconds"],
            "cache_backtest_results": settings["cache_backtest_results"],
            "cache_market_data": settings["cache_market_data"],
            "cache_analysis_results": settings["cache_analysis_results"],
            "last_connection_test": settings["last_connection_test"],
            "last_connection_status": settings["last_connection_status"],
            "total_cache_hits": settings["total_cache_hits"],
            "total_cache_misses": settings["total_cache_misses"],
        }

    @staticmethod
    def update_redis_settings(
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
        settings = execute_query("SELECT * FROM redis_settings", fetchone=True)
        if not settings:
            # Create default settings
            execute_query(
                "INSERT INTO redis_settings (enabled, host, port, db, password, ssl, timeout, max_connections, cache_ttl_seconds, cache_backtest_results, cache_market_data, cache_analysis_results) VALUES (1, 'localhost', 6379, 0, NULL, 0, 0, 10, 3600, 1, 1, 1)",
                commit=True,
            )
            settings = execute_query("SELECT * FROM redis_settings", fetchone=True)

        # Update only provided fields
        if enabled is not None:
            settings["enabled"] = enabled
        if host is not None:
            settings["host"] = host
        if port is not None:
            settings["port"] = port
        if database is not None:
            settings["db"] = database
        if password is not None:
            settings["password"] = password
        if ssl is not None:
            settings["ssl"] = ssl
        if timeout is not None:
            settings["timeout"] = timeout
        if max_connections is not None:
            settings["max_connections"] = max_connections
        if cache_ttl_seconds is not None:
            settings["cache_ttl_seconds"] = cache_ttl_seconds
        if cache_backtest_results is not None:
            settings["cache_backtest_results"] = cache_backtest_results
        if cache_market_data is not None:
            settings["cache_market_data"] = cache_market_data
        if cache_analysis_results is not None:
            settings["cache_analysis_results"] = cache_analysis_results

        execute_query(
            "UPDATE redis_settings SET enabled = %s, host = %s, port = %s, db = %s, password = %s, ssl = %s, timeout = %s, max_connections = %s, cache_ttl_seconds = %s, cache_backtest_results = %s, cache_market_data = %s, cache_analysis_results = %s WHERE id = %s",
            (
                settings["enabled"],
                settings["host"],
                settings["port"],
                settings["db"],
                settings["password"],
                settings["ssl"],
                settings["timeout"],
                settings["max_connections"],
                settings["cache_ttl_seconds"],
                settings["cache_backtest_results"],
                settings["cache_market_data"],
                settings["cache_analysis_results"],
                settings["id"],
            ),
            commit=True,
        )

        logger.info("Redis settings updated")
        return RedisSettingsService.get_redis_settings()

    @staticmethod
    def test_redis_connection() -> dict:
        """Test Redis connection and update status in database."""
        from redis_service import get_redis_service

        redis_service = get_redis_service()
        status = redis_service.check_connection()

        execute_query(
            "UPDATE redis_settings SET last_connection_test = %s, last_connection_status = %s",
            (datetime.datetime.now(datetime.UTC), "connected" if status.get("connected") else "failed"),
            commit=True,
        )

        return status

    @staticmethod
    def get_cache_stats() -> dict:
        """Get cache statistics."""
        from redis_service import get_redis_service

        redis_service = get_redis_service()
        stats = redis_service.get_cache_stats()

        settings = execute_query("SELECT * FROM redis_settings", fetchone=True)
        if settings:
            stats["cache_ttl_seconds"] = settings["cache_ttl_seconds"]
            stats["cache_backtest_results"] = settings["cache_backtest_results"]
            stats["cache_market_data"] = settings["cache_market_data"]
            stats["cache_analysis_results"] = settings["cache_analysis_results"]

        return stats

    @staticmethod
    def toggle_redis_enabled(enabled: bool) -> None:
        """Toggle Redis caching on/off."""
        settings = execute_query("SELECT * FROM redis_settings", fetchone=True)
        if not settings:
            execute_query(
                "INSERT INTO redis_settings (enabled) VALUES (%s)",
                (enabled,),
                commit=True,
            )
        else:
            execute_query(
                "UPDATE redis_settings SET enabled = %s WHERE id = %s",
                (enabled, settings["id"]),
                commit=True,
            )

        logger.info(f"Redis caching {'enabled' if enabled else 'disabled'}")


class StrategyVersionHistoryService:
    """Service for managing strategy version history and version control."""

    @staticmethod
    def create_version(
        strategy_id: int,
        config_snapshot: dict,
        version_number: int,
        created_by_user_id: Optional[int] = None,
        change_description: Optional[str] = None,
        changes: Optional[dict] = None,
    ):
        """Create a new strategy version with configuration snapshot."""
        execute_query(
            "INSERT INTO strategy_version_history (strategy_id, version_number, config_snapshot, change_description, changes, created_by_user_id, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                strategy_id,
                version_number,
                config_snapshot,
                change_description,
                changes,
                created_by_user_id,
                datetime.datetime.now(datetime.UTC),
            ),
            commit=True,
        )
        logger.info(
            f"Strategy version created: Strategy {strategy_id} v{version_number}"
        )
        return {}

    @staticmethod
    def get_version_by_id(version_id: int):
        """Get strategy version by ID."""
        version = execute_query(
            "SELECT * FROM strategy_version_history WHERE id = %s",
            (version_id,),
            fetchone=True,
        )
        return dict(version) if version else None

    @staticmethod
    def get_strategy_versions(
        strategy_id: int, skip: int = 0, limit: int = 50
    ) -> list:
        """Get all versions for a strategy, ordered by version number descending."""
        return execute_query(
            "SELECT * FROM strategy_version_history WHERE strategy_id = %s ORDER BY version_number DESC LIMIT %s OFFSET %s",
            (strategy_id, limit, skip),
        )

    @staticmethod
    def get_latest_version(strategy_id: int):
        """Get the latest version of a strategy."""
        version = execute_query(
            "SELECT * FROM strategy_version_history WHERE strategy_id = %s ORDER BY version_number DESC LIMIT 1",
            (strategy_id,),
            fetchone=True,
        )
        return dict(version) if version else None

    @staticmethod
    def get_version_by_number(strategy_id: int, version_number: int):
        """Get specific version by strategy and version number."""
        version = execute_query(
            "SELECT * FROM strategy_version_history WHERE strategy_id = %s AND version_number = %s",
            (strategy_id, version_number),
            fetchone=True,
        )
        return dict(version) if version else None

    @staticmethod
    def get_next_version_number(strategy_id: int) -> int:
        """Get the next version number for a strategy."""
        latest = execute_query(
            "SELECT version_number FROM strategy_version_history WHERE strategy_id = %s ORDER BY version_number DESC LIMIT 1",
            (strategy_id,),
            fetchone=True,
        )
        return (latest[0] + 1) if latest else 1

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
def validate_results_quality(results: list[dict]) -> dict:
    """
    Validate backtest results for consistency issues.
    Returns quality score and list of warnings.

    Args:
        results: List of result dicts to validate

    Returns:
        Dictionary with quality score (0-100), warnings list, and fixes applied
    """
    warnings = []

    for result in results:
        # Check 1: Win rate must be 0-100%
        win_rate = result.get("win_rate")
        if win_rate is not None and (win_rate < 0 or win_rate > 100):
            warnings.append(
                f"{result.get('market_1')}/{result.get('market_2')}: "
                f"Win rate {win_rate}% outside valid range [0-100%]"
            )
        # Check 2: Profitable trades must be <= total trades
        profitable = result.get("profitable_trades") or 0
        total = result.get("total_trades") or 0
        if profitable > total:
            warnings.append(
                f"{result.get('market_1')}/{result.get('market_2')}: "
                f"Profitable trades ({profitable}) > total trades ({total})"
            )
        # Check 3: Losing trades must be <= total trades
        losing = result.get("losing_trades") or 0
        if losing > total:
            warnings.append(
                f"{result.get('market_1')}/{result.get('market_2')}: "
                f"Losing trades ({losing}) > total trades ({total})"
            )
        # Check 4: Profit factor must be >= 0
        profit_factor = result.get("profit_factor")
        if profit_factor is not None and profit_factor < 0:
            warnings.append(
                f"{result.get('market_1')}/{result.get('market_2')}: "
                f"Negative profit factor {profit_factor}"
            )
        # Check 5: Sum of profitable + losing should not exceed total
        total_categorized = profitable + losing
        if total_categorized > total:
            warnings.append(
                f"{result.get('market_1')}/{result.get('market_2')}: "
                f"Profitable ({profitable}) + Losing ({losing}) > Total ({total})"
            )
        # Check 6: Max drawdown should not exceed -100%
        max_drawdown = result.get("max_drawdown")
        if max_drawdown is not None and max_drawdown < -100:
            warnings.append(
                f"{result.get('market_1')}/{result.get('market_2')}: "
                f"Extreme max drawdown {max_drawdown}% (likely data error)"
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
