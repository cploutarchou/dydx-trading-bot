#!/usr/bin/env python3
"""
Comprehensive Backtesting Script

Runs multiple backtests across different time periods:
- Last 30 days with ALL pairs
- Last 60 days with ALL pairs
- Last 1 year with ALL pairs

Usage:
    python scripts/run_comprehensive_backtests.py

This script automatically calculates date ranges and runs sequential backtests
with proper error handling and progress monitoring.
"""

import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


def setup_logging() -> logging.Logger:
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def calculate_date_range(days_back: int) -> Tuple[str, str]:
    """Calculate start and end dates for backtesting."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


def run_backtest(
    start_date: str,
    end_date: str,
    pairs: str,
    period_name: str,
    logger: logging.Logger
) -> bool:
    """Run a single backtest with the given parameters."""
    logger.info(
        f"🚀 Starting {period_name} backtest ({start_date} to {end_date})"
    )

    cmd = [
        sys.executable,
        'scripts/run_backtest.py',
        '--start', start_date,
        '--end', end_date,
        '--pairs', pairs
    ]

    try:
        # Run with timeout to prevent hanging
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,  # Run from project root
            timeout=3600,  # 1 hour timeout
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            logger.info(f"✅ {period_name} backtest completed successfully")
            return True
        else:
            logger.error(
                f"❌ {period_name} backtest failed with "
                f"code {result.returncode}"
            )
            logger.error(f"Error output: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"⏰ {period_name} backtest timed out after 1 hour")
        return False
    except Exception as e:
        logger.error(
            f"💥 {period_name} backtest failed with exception: {e}"
        )
        return False


def main() -> int:
    """Main execution function."""
    logger = setup_logging()

    logger.info("🔥 Starting Comprehensive dYdX Backtesting Suite")
    logger.info("=" * 60)

    # Define backtest periods
    periods: List[Tuple[int, str]] = [
        (30, "30-Day"),
        (60, "60-Day"),
        (365, "1-Year")
    ]

    results: Dict[str, bool] = {}

    for days_back, period_name in periods:
        start_date, end_date = calculate_date_range(days_back)

        logger.info(
            f"\n📅 {period_name} Period: {start_date} to {end_date}"
        )

        success = run_backtest(
            start_date, end_date, "ALL", period_name, logger
        )
        results[period_name] = success

        if not success:
            logger.warning(
                f"⚠️  {period_name} backtest failed, "
                f"continuing to next period..."
            )

    # Summary report
    logger.info("\n" + "=" * 60)
    logger.info("📊 COMPREHENSIVE BACKTEST SUMMARY")
    logger.info("=" * 60)

    successful_count = 0
    for period_name, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"{period_name:12} | {status}")
        if success:
            successful_count += 1

    logger.info(
        f"\n🎯 Results: {successful_count}/"
        f"{len(periods)} backtests completed successfully"
    )

    if successful_count == len(periods):
        logger.info(
            "🏆 ALL BACKTESTS COMPLETED! "
            "Check app/backtest_results/ for detailed results"
        )
        return 0
    elif successful_count > 0:
        logger.info(
            "⚠️  PARTIAL SUCCESS - Some backtests completed, "
            "check logs for failed periods"
        )
        return 1
    else:
        logger.error(
            "💥 ALL BACKTESTS FAILED - "
            "Check configuration and connectivity"
        )
        return 2


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
