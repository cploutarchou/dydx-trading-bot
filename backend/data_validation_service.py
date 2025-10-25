"""
Data Validation & Prefetch Service
Senior-level data engineering with accuracy validation and performance optimization
"""

import logging
from typing import Any, Dict, Optional

import numpy as np
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from database import (
    BacktestCandle,
    BacktestPosition,
    BacktestResult,
    BacktestRun,
    BacktestTrade,
)
from backend.services import BacktestRunService

logger = logging.getLogger(__name__)


class DataValidationService:
    """Enterprise-grade data validation and consistency checking."""

    @staticmethod
    def validate_backtest_integrity(db: Session, run_id_pk: int) -> Dict[str, Any]:
        """
        Comprehensive data integrity check for a backtest run.

        Returns:
            Dict with validation status, issues found, and fixes applied
        """
        issues = []
        fixes_applied = []
        run = db.query(BacktestRun).filter(BacktestRun.id == run_id_pk).first()

        if not run:
            return {"valid": False, "issues": ["BacktestRun not found"]}

        # Check 1: Orphaned records (trades without positions)
        trades_count = (
            db.query(func.count(BacktestTrade.id))
            .filter(BacktestTrade.run_id_fk == run_id_pk)
            .scalar()
        )

        positions_count = (
            db.query(func.count(BacktestPosition.id))
            .filter(BacktestPosition.run_id_fk == run_id_pk)
            .scalar()
        )

        if trades_count and not positions_count:
            issues.append("Trades exist but no positions recorded")

        # Check 2: Data consistency - verify aggregated metrics match actual data
        if trades_count and trades_count > 0:
            # Recalculate metrics
            trades = (
                db.query(BacktestTrade)
                .filter(BacktestTrade.run_id_fk == run_id_pk)
                .all()
            )

            actual_pnl = sum([t.pnl or 0 for t in trades])
            recorded_pnl = run.total_pnl or 0

            if abs(actual_pnl - recorded_pnl) > 0.01:  # 0.01 tolerance for rounding
                issues.append(
                    f"PnL mismatch: actual={actual_pnl:.2f}, recorded={recorded_pnl:.2f}"
                )
                logger.warning(f"Run {run.run_id}: PnL mismatch detected. Fixing...")
                run.total_pnl = float(actual_pnl)
                run.total_pnl_usd = float(actual_pnl)
                fixes_applied.append("PnL corrected")

            # Check win rate
            profitable = len([t for t in trades if (t.pnl or 0) > 0])
            actual_win_rate = (profitable / len(trades) * 100) if trades else 0
            recorded_win_rate = run.win_rate or 0

            if abs(actual_win_rate - recorded_win_rate) > 0.1:
                issues.append(
                    f"Win rate mismatch: actual={actual_win_rate:.1f}%, "
                    f"recorded={recorded_win_rate:.1f}%"
                )
                run.win_rate = float(actual_win_rate)
                fixes_applied.append("Win rate corrected")

        # Check 3: Candle data availability
        candle_markets = (
            db.query(func.distinct(BacktestCandle.market))
            .filter(BacktestCandle.run_id_fk == run_id_pk)
            .count()
        )

        if candle_markets == 0 and run.status == "completed":
            issues.append("No candle data found for completed backtest")

        # Check 4: Results consistency
        results_count = (
            db.query(func.count(BacktestResult.id))
            .filter(BacktestResult.run_id_fk == run_id_pk)
            .scalar()
        )

        if run.num_pairs and results_count < run.num_pairs:
            issues.append(
                f"Results incomplete: {results_count}/{run.num_pairs} pairs have results"
            )

        # Commit fixes
        if fixes_applied:
            db.commit()
            logger.info(f"Applied {len(fixes_applied)} data fixes for run {run.run_id}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "fixes_applied": fixes_applied,
            "data_quality_score": (
                max(0, 100 - len(issues) * 10) if len(issues) < 10 else 0
            ),  # 100 = perfect
        }

    @staticmethod
    def calculate_accurate_metrics(db: Session, run_id_pk: int) -> Dict[str, Any]:
        """
        Calculate metrics directly from raw data with full precision.
        Used to validate/replace aggregated metrics.
        """
        trades = (
            db.query(BacktestTrade).filter(BacktestTrade.run_id_fk == run_id_pk).all()
        )

        if not trades:
            return {
                "total_trades": 0,
                "profitable_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "total_pnl_usd": 0.0,
                "avg_trade_duration": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 1.0,
                "consecutive_wins": 0,
                "consecutive_losses": 0,
            }

        pnls = [t.pnl or 0 for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        total_pnl = sum(pnls)
        profit_factor = 1.0
        if losses:
            gross_profit = sum(wins) if wins else 0
            gross_loss = abs(sum(losses)) if losses else 1
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0

        # Calculate consecutive wins/losses
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0

        for pnl in pnls:
            if pnl > 0:
                consecutive_wins += 1
                consecutive_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            elif pnl < 0:
                consecutive_losses += 1
                consecutive_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)

        # Calculate trade durations
        durations = []
        for trade in trades:
            if trade.entry_timestamp and trade.exit_timestamp:
                duration = (
                    trade.exit_timestamp - trade.entry_timestamp
                ).total_seconds() / 3600
                durations.append(duration)

        avg_trade_duration = np.mean(durations) if durations else 0.0

        return {
            "total_trades": len(trades),
            "profitable_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": (len(wins) / len(trades) * 100) if trades else 0.0,
            "total_pnl": float(total_pnl),
            "total_pnl_usd": float(total_pnl),
            "avg_trade_duration": float(avg_trade_duration),
            "largest_win": float(max(wins)) if wins else 0.0,
            "largest_loss": float(min(losses)) if losses else 0.0,
            "avg_win": float(np.mean(wins)) if wins else 0.0,
            "avg_loss": float(np.mean(losses)) if losses else 0.0,
            "profit_factor": float(profit_factor),
            "consecutive_wins": max_consecutive_wins,
            "consecutive_losses": max_consecutive_losses,
        }


class PrefetchService:
    """
    Intelligent data prefetching and caching for performance optimization.
    Reduces N+1 queries and improves response times.
    """

    # Cache TTL in seconds
    CACHE_TTL = 3600  # 1 hour

    @staticmethod
    def prefetch_backtest_data(
        db: Session, run_id_pk: int, prefetch_options: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Prefetch all related data for a backtest in optimized queries.

        Args:
            db: Database session
            run_id_pk: BacktestRun primary key
            prefetch_options: Dict specifying what to prefetch (default: all)
                {
                    "trades": True,
                    "positions": True,
                    "candles": True,
                    "results": True,
                    "metrics": True
                }

        Returns:
            Dict with all prefetched data keyed by type
        """
        if prefetch_options is None:
            prefetch_options = {
                "trades": True,
                "positions": True,
                "candles": True,
                "results": True,
                "metrics": True,
            }

        prefetched = {}

        # Prefetch trades
        if prefetch_options.get("trades", False):
            trades = (
                db.query(BacktestTrade)
                .filter(BacktestTrade.run_id_fk == run_id_pk)
                .order_by(BacktestTrade.entry_timestamp.desc())
                .all()
            )
            prefetched["trades"] = trades
            logger.debug(f"Prefetched {len(trades)} trades for run {run_id_pk}")

        # Prefetch positions
        if prefetch_options.get("positions", False):
            positions = (
                db.query(BacktestPosition)
                .filter(BacktestPosition.run_id_fk == run_id_pk)
                .order_by(BacktestPosition.entry_timestamp.desc())
                .all()
            )
            prefetched["positions"] = positions
            logger.debug(f"Prefetched {len(positions)} positions for run {run_id_pk}")

        # Prefetch candles (limited to last 100 per market)
        if prefetch_options.get("candles", False):
            markets = (
                db.query(func.distinct(BacktestCandle.market))
                .filter(BacktestCandle.run_id_fk == run_id_pk)
                .all()
            )

            candles_by_market = {}
            for (market,) in markets:
                candles = (
                    db.query(BacktestCandle)
                    .filter(
                        and_(
                            BacktestCandle.run_id_fk == run_id_pk,
                            BacktestCandle.market == market,
                        )
                    )
                    .order_by(BacktestCandle.timestamp.desc())
                    .limit(500)
                    .all()
                )
                candles_by_market[market] = candles

            prefetched["candles"] = candles_by_market
            logger.debug(
                f"Prefetched candles for {len(candles_by_market)} markets for run {run_id_pk}"
            )

        # Prefetch results
        if prefetch_options.get("results", False):
            results = (
                db.query(BacktestResult)
                .filter(BacktestResult.run_id_fk == run_id_pk)
                .order_by(BacktestResult.pnl.desc())
                .all()
            )
            prefetched["results"] = results
            logger.debug(f"Prefetched {len(results)} results for run {run_id_pk}")

        # Calculate metrics
        if prefetch_options.get("metrics", False):
            metrics = DataValidationService.calculate_accurate_metrics(db, run_id_pk)
            prefetched["metrics"] = metrics
            logger.debug(f"Calculated accurate metrics for run {run_id_pk}")

        return prefetched

    @staticmethod
    def get_backtest_summary_optimized(
        db: Session, run_id: str, current_user_id: int
    ) -> Dict[str, Any]:
        """
        Optimized backtest summary with all essential data in minimal queries.
        """
        # Single query with join
        run = BacktestRunService.get_run_by_run_id(db, run_id)

        if not run:
            raise ValueError(f"Backtest {run_id} not found")

        # Authorize
        if run.user_id != current_user_id:
            raise PermissionError("Not authorized to access this backtest")

        # Prefetch all data in optimized queries
        prefetched = PrefetchService.prefetch_backtest_data(
            db,
            run.id,
            {
                "trades": True,
                "positions": True,
                "candles": False,  # Don't prefetch candles in summary
                "results": True,
                "metrics": True,
            },
        )

        # Calculate top performers
        results = prefetched.get("results", [])
        top_pairs = sorted(results, key=lambda r: r.pnl or 0, reverse=True)[:10]
        worst_pairs = sorted(results, key=lambda r: r.pnl or 0)[:10]

        return {
            "run_id": run.run_id,
            "status": run.status,
            "created_at": run.created_at.isoformat(),
            "start_date": run.start_date,
            "end_date": run.end_date,
            "metrics": prefetched.get("metrics"),
            "top_performers": [
                {
                    "pair": f"{r.market_1}/{r.market_2}",
                    "pnl": r.pnl,
                    "win_rate": r.win_rate,
                }
                for r in top_pairs
            ],
            "worst_performers": [
                {
                    "pair": f"{r.market_1}/{r.market_2}",
                    "pnl": r.pnl,
                    "win_rate": r.win_rate,
                }
                for r in worst_pairs
            ],
            "data_quality": {
                "total_trades": len(prefetched.get("trades", [])),
                "total_positions": len(prefetched.get("positions", [])),
                "total_results": len(results),
            },
        }
