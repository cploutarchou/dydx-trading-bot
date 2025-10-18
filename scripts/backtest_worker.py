"""
Background task processor for executing queued backtests.

This worker polls the database for "queued" backtests and executes them
using the BacktestEngine, updating the database with results.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.config import config as get_config
from app.func_backtesting import BacktestEngine
from app.logging_setup import setup_logging
from backend.database import (
    BacktestResult,
    BacktestRun,
    TradeLog,
    get_db,
    init_db,
)
from backend.ws_broadcaster import BacktestProgressUpdate, get_broadcaster

logger = logging.getLogger(__name__)


class BacktestWorker:
    """
    Background worker for executing queued backtests.

    Polls the database for "queued" runs and executes them,
    updating the database with progress and results.
    """

    def __init__(self):
        self.config = get_config()
        self.running = False
        self.check_interval = 5  # Check for new backtests every 5 seconds

    async def start(self):
        """Start the background worker."""
        logger.info("Starting BacktestWorker...")
        self.running = True

        # Initialize database
        init_db()

        try:
            while self.running:
                await self._process_queue()
                await asyncio.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("BacktestWorker interrupted by user")
        except Exception as e:
            logger.error("BacktestWorker error: %s", e, exc_info=True)
        finally:
            self.running = False
            logger.info("BacktestWorker stopped")

    async def _process_queue(self):
        """Check for queued backtests and process them."""
        try:
            db = next(get_db())
            broadcaster = get_broadcaster()

            # Find all queued backtests
            queued_runs = db.query(BacktestRun).filter_by(status="queued").all()

            if not queued_runs:
                return

            logger.info("Found %d queued backtests to process", len(queued_runs))

            for run in queued_runs:
                try:
                    await self._execute_backtest(db, run, broadcaster)
                except Exception as e:
                    logger.error(
                        "Error executing backtest %s: %s", run.run_id, e, exc_info=True
                    )
                    # Broadcast failure update
                    update = BacktestProgressUpdate(
                        run_id=run.run_id,
                        status="failed",
                        message=f"Backtest failed: {str(e)}",
                        details={"error": str(e)},
                    )
                    await broadcaster.broadcast(update)
                    # Mark as failed
                    run.status = "failed"
                    run.error_message = str(e)
                    db.commit()

        except Exception as e:
            logger.error("Error processing queue: %s", e, exc_info=True)

    async def _execute_backtest(self, db, run, broadcaster):
        """
        Execute a single backtest run.

        Args:
            db: Database session
            run: BacktestRun record from database
            broadcaster: WebSocket broadcaster instance
        """
        logger.info("Starting backtest %s for user %s", run.run_id, run.user_id)

        # Emit queued status
        update = BacktestProgressUpdate(
            run_id=run.run_id,
            status="queued",
            progress=0,
            message="Backtest queued, waiting to start...",
        )
        await broadcaster.broadcast(update)

        # Update status to running
        run.status = "running"
        run.started_at = datetime.utcnow()
        db.commit()

        # Emit running status
        update = BacktestProgressUpdate(
            run_id=run.run_id,
            status="running",
            progress=5,
            message="Starting backtest execution...",
        )
        await broadcaster.broadcast(update)

        try:
            # Parse dates from config
            start_date = datetime.strptime(run.start_date, "%Y-%m-%d")
            end_date = datetime.strptime(run.end_date, "%Y-%m-%d")

            logger.info(f"Backtest period: {start_date.date()} to {end_date.date()}")

            # Emit progress
            update = BacktestProgressUpdate(
                run_id=run.run_id,
                status="running",
                progress=10,
                message="Loading historical data...",
            )
            await broadcaster.broadcast(update)

            # Initialize BacktestEngine
            # Note: We pass None for client since backtesting uses historical data
            engine = BacktestEngine(client=None, config=self.config)

            # Run the backtest with progress tracking
            logger.info("Running backtest for %d pairs...", run.num_pairs or 10)
            update = BacktestProgressUpdate(
                run_id=run.run_id,
                status="running",
                progress=20,
                message="Running statistical analysis...",
                details={"num_pairs": run.num_pairs or 10},
            )
            await broadcaster.broadcast(update)

            backtest_result = await engine.run_backtest(
                start_date=start_date,
                end_date=end_date,
                max_pairs=run.num_pairs,
            )

            # Emit progress
            update = BacktestProgressUpdate(
                run_id=run.run_id,
                status="running",
                progress=70,
                message=f"Completed {backtest_result.total_trades} trades, storing results...",
                details={
                    "total_trades": backtest_result.total_trades,
                    "pairs_analyzed": len(backtest_result.results_by_pair),
                },
            )
            await broadcaster.broadcast(update)

            # Store results in database
            await self._store_results(db, run, backtest_result)

            # Update run status
            run.status = "completed"
            run.completed_at = datetime.utcnow()

            # Calculate duration
            if run.started_at and run.completed_at:
                duration = (run.completed_at - run.started_at).total_seconds()
                run.duration_seconds = int(duration)

            db.commit()

            logger.info(
                "Backtest %s completed successfully in %d seconds",
                run.run_id,
                run.duration_seconds or 0,
            )

            # Emit completion update
            update = BacktestProgressUpdate(
                run_id=run.run_id,
                status="completed",
                progress=100,
                message="Backtest completed successfully!",
                details={
                    "total_trades": backtest_result.total_trades,
                    "total_pnl_usd": backtest_result.total_pnl_usd,
                    "duration_seconds": run.duration_seconds,
                    "pairs_analyzed": len(backtest_result.results_by_pair),
                },
            )
            await broadcaster.broadcast(update)

        except Exception as e:
            logger.error("Backtest %s failed: %s", run.run_id, e, exc_info=True)
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            db.commit()

            # Emit failure update
            update = BacktestProgressUpdate(
                run_id=run.run_id,
                status="failed",
                progress=0,
                message=f"Backtest failed: {str(e)}",
                details={"error": str(e)},
            )
            await broadcaster.broadcast(update)
            raise

    async def _store_results(self, db, run, backtest_result):
        """
        Store backtest results in database.

        Args:
            db: Database session
            run: BacktestRun record
            backtest_result: BacktestResult from engine
        """
        logger.info("Storing results for backtest %s", run.run_id)

        # Update run totals
        run.total_trades = backtest_result.total_trades
        run.total_pnl = backtest_result.total_pnl_usd
        run.starting_balance = backtest_result.starting_balance
        run.ending_balance = backtest_result.ending_balance

        # Store results per pair
        for pair_result in backtest_result.results_by_pair.values():
            result = BacktestResult(
                run_id=run.id,
                market_1=pair_result.base_market,
                market_2=pair_result.quote_market,
                total_trades=pair_result.total_trades,
                profitable_trades=pair_result.profitable_trades,
                losing_trades=pair_result.total_trades - pair_result.profitable_trades,
                win_rate=pair_result.win_rate,
                pnl=pair_result.total_pnl,
                pnl_usd=pair_result.total_pnl_usd,
                sharpe_ratio=pair_result.sharpe_ratio,
                max_drawdown=pair_result.max_drawdown,
                profit_factor=pair_result.profit_factor,
            )
            db.add(result)
            db.flush()  # Get the result ID

            # Store trades for this pair
            for trade in pair_result.trades:
                trade_log = TradeLog(
                    result_id_fk=result.id,
                    trade_number=trade.trade_number,
                    entry_timestamp=trade.entry_time,
                    exit_timestamp=trade.exit_time,
                    entry_price_1=trade.entry_price_1,
                    entry_price_2=trade.entry_price_2,
                    exit_price_1=trade.exit_price_1,
                    exit_price_2=trade.exit_price_2,
                    quantity_1=trade.quantity_1,
                    quantity_2=trade.quantity_2,
                    side_1=trade.side_1,
                    side_2=trade.side_2,
                    pnl=trade.pnl,
                    pnl_usd=trade.pnl_usd,
                    entry_zscore=trade.entry_zscore,
                    exit_zscore=trade.exit_zscore,
                )
                db.add(trade_log)

        db.commit()
        logger.info("Stored results for %d pairs", len(backtest_result.results_by_pair))

    def stop(self):
        """Stop the background worker."""
        logger.info("Stopping BacktestWorker...")
        self.running = False


async def main():
    """Main entry point for the background worker."""
    # Setup logging first
    setup_logging()

    logger.info("=== dYdX Backtest Worker Started ===")
    logger.info("Monitoring for queued backtests...")

    worker = BacktestWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
        worker.stop()
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
