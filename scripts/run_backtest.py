#!/usr/bin/env python3
"""
Backtesting script for dYdX trading bot

Runs historical backtesting simulation using existing trading logic
and statistical analysis patterns.

Usage: 
    python scripts/run_backtest.py --start 2024-01-01 --end 2024-03-31 --pairs 5
    
Examples:
    # Quick 1-month test
    python scripts/run_backtest.py --start 2024-01-01 --end 2024-01-31 --pairs 3
    
    # Comprehensive 3-month test  
    python scripts/run_backtest.py --start 2024-01-01 --end 2024-03-31 --pairs 10
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

# Add the app directory to path (following existing script patterns)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from config import config as app_config  # noqa: E402
from func_backtesting import BacktestEngine  # noqa: E402
from func_connections import connect_dydx  # noqa: E402
from logging_setup import setup_logging  # noqa: E402
from models.backtest_storage import backtest_storage  # noqa: E402


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Run dYdX trading bot backtest',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --start 2024-01-01 --end 2024-01-31 --pairs 3
  %(prog)s --start 2024-01-01 --end 2024-03-31 --pairs 10
  %(prog)s --start 2024-06-01 --end 2024-09-01 --pairs 5 --name summer_test
        """
    )

    parser.add_argument(
        '--start',
        required=True,
        help='Start date for backtest (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        required=True,
        help='End date for backtest (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--pairs',
        type=str,
        default='5',
        help='Number of top cointegrated pairs to trade (default: 5, use "ALL" for all available pairs)'
    )
    parser.add_argument(
        '--name',
        default=None,
        help='Custom name for this backtest (default: auto-generated)'
    )
    parser.add_argument(
        '--save',
        action='store_true',
        default=True,
        help='Save backtest results (default: true)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging output'
    )

    return parser.parse_args()


def validate_dates(start_str: str, end_str: str) -> tuple[datetime, datetime]:
    """Validate and parse date strings."""
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d')

        if start_date >= end_date:
            raise ValueError("Start date must be before end date")

        # Check if dates are too far in the past or future
        current_date = datetime.now()
        if end_date > current_date:
            raise ValueError("End date cannot be in the future")

        # Warn if backtest period is very long
        duration_days = (end_date - start_date).days
        if duration_days > 365:
            print(f"⚠️  Warning: Backtest period is {duration_days} days. "
                  "This may take a long time to complete.")

        return start_date, end_date

    except ValueError as e:
        raise ValueError(f"Invalid date format: {e}")


async def main():
    """Main backtesting execution function."""
    # Parse command line arguments
    args = parse_arguments()

    # Initialize logging (following existing patterns)
    if args.verbose:
        setup_logging()
        # Set more verbose logging for backtesting modules
        logging.getLogger('app.func_backtesting').setLevel(logging.DEBUG)
        logging.getLogger(
            'app.models.backtest_storage').setLevel(logging.DEBUG)
    else:
        setup_logging()

    logger = logging.getLogger(__name__)

    try:
        # Validate dates
        start_date, end_date = validate_dates(args.start, args.end)
        duration_days = (end_date - start_date).days

        # Validate pairs argument
        if args.pairs.upper() == "ALL":
            max_pairs = None  # None means all pairs
            pairs_display = "ALL"
        else:
            try:
                max_pairs = int(args.pairs)
                if max_pairs < 1:
                    raise ValueError("Number of pairs must be at least 1")
                pairs_display = str(max_pairs)
            except ValueError:
                logger.error(
                    "Invalid pairs argument: %s. Use a number or 'ALL'", args.pairs)
                sys.exit(1)

        logger.info("=== dYdX Trading Bot Backtest ===")
        logger.info("Period: %s to %s (%d days)",
                    start_date.date(), end_date.date(), duration_days)
        logger.info("Max pairs: %s", pairs_display)

        # Load configuration from the DB/env-backed runtime config path.
        config = app_config()

        if not config:
            logger.error("Failed to load configuration")
            sys.exit(1)

        logger.info("Configuration loaded: %s environment",
                    # Connect to dYdX (use testnet for backtesting to avoid mainnet costs)
                    config.environment)
        logger.info("Connecting to dYdX (testnet mode for backtesting)...")
        client = await connect_dydx()

        if not client:
            logger.error("Failed to connect to dYdX")
            sys.exit(1)

        logger.info("✅ Connected to dYdX successfully")

        # Initialize backtest engine
        logger.info("Initializing backtesting engine...")
        backtest_engine = BacktestEngine(client, config)

        # Run the backtest
        logger.info("🚀 Starting backtest simulation...")
        result = await backtest_engine.run_backtest(
            start_date=start_date,
            end_date=end_date,
            max_pairs=max_pairs
        )

        # Print results summary
        print("\n" + "="*60)
        print("           BACKTEST RESULTS SUMMARY")
        print("="*60)

        summary = result.summary_stats
        for key, value in summary.items():
            key_formatted = key.replace('_', ' ').title()
            print(f"{key_formatted:.<25} {value:>20}")

        print("\nDetailed Metrics:")
        print(f"{'Winning Trades':.<25} {result.metrics.winning_trades:>20}")
        print(f"{'Losing Trades':.<25} {result.metrics.losing_trades:>20}")
        print(f"{'Average Win':.<25} ${result.metrics.avg_win:>19.2f}")
        print(f"{'Average Loss':.<25} ${result.metrics.avg_loss:>19.2f}")
        print(f"{'Profit Factor':.<25} {result.metrics.profit_factor:>20.2f}")
        print(
            f"{'Max Consecutive Losses':.<25} {result.metrics.max_consecutive_losses:>20}")
        print(
            f"{'Avg Trade Duration':.<25} {result.metrics.avg_trade_duration_hours:>17.1f}h")

        # Save results
        if args.save:
            test_name = args.name or f"{args.start}_to_{args.end}_{pairs_display}pairs"
            filename = backtest_storage.save_backtest_result(result, test_name)
            print(f"\n✅ Results saved: {filename}")
            print("📁 Results directory: app/backtest_results/")
            print("📊 Analyze with: make backtest-analysis")

        # Final summary
        print("\n" + "="*60)
        if result.metrics.total_pnl > 0:
            print(f"🎉 PROFITABLE STRATEGY: +${result.metrics.total_pnl:.2f}")
        else:
            print(f"📉 UNPROFITABLE STRATEGY: ${result.metrics.total_pnl:.2f}")
        print("="*60)

        logger.info("Backtest completed successfully")

    except KeyboardInterrupt:
        logger.info("Backtest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Backtest failed: %s", e, exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    # Run backtest with proper event loop handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Backtest interrupted")
        sys.exit(1)
