"""
Backtest storage system for dYdX Trading Bot

Implements JSON-based backtest result storage following
project patterns from pair_storage.py singleton approach.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .bot_backtest_models import BacktestResult

logger = logging.getLogger(__name__)


class BacktestStorage:
    """
    Backtest result storage manager following singleton pattern like PairStorageManager.

    Provides JSON storage with timestamped results and analysis capabilities.
    Follows project patterns for file-based state persistence.
    """

    _instance: Optional['BacktestStorage'] = None

    def __new__(cls) -> 'BacktestStorage':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self.storage_path = Path("app")
        self.backtest_dir = self.storage_path / "backtest_results"

        # Create backtest results directory if it doesn't exist
        self.backtest_dir.mkdir(exist_ok=True)

        self._initialized = True
        logger.info("BacktestStorage initialized with directory: %s",
                    self.backtest_dir)

    def save_backtest_result(self, result: BacktestResult, test_name: str) -> str:
        """
        Save backtest result to JSON file with timestamped filename.

        Args:
            result: BacktestResult object to save
            test_name: Base name for the test (e.g., "3month_test")

        Returns:
            Filename of saved result

        Raises:
            Exception: If storage fails
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"backtest_{test_name}_{timestamp}.json"
        filepath = self.backtest_dir / filename

        try:
            with open(filepath, 'w') as f:
                json.dump(result.to_dict(), f, indent=2, default=str)

            logger.info("Saved backtest result: %s (%d trades, $%.2f PnL)",
                        filename, result.metrics.total_trades, result.metrics.total_pnl)
            return filename

        except Exception as e:
            logger.error("Failed to save backtest result %s: %s", filename, e)
            raise

    def load_backtest_result(self, filename: str) -> Optional[BacktestResult]:
        """
        Load specific backtest result by filename.

        Args:
            filename: Name of backtest result file

        Returns:
            BacktestResult if found, None otherwise
        """
        filepath = self.backtest_dir / filename

        if not filepath.exists():
            logger.warning("Backtest result file not found: %s", filename)
            return None

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            result = BacktestResult.from_dict(data)
            logger.info("Loaded backtest result: %s", filename)
            return result

        except Exception as e:
            logger.error("Failed to load backtest result %s: %s", filename, e)
            return None

    def list_backtest_results(self) -> List[Dict]:
        """
        List all available backtest results with summary info.

        Returns:
            List of dictionaries with result metadata
        """
        results = []

        for filepath in self.backtest_dir.glob("backtest_*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)

                # Extract summary information
                result_info = {
                    "filename": filepath.name,
                    "start_date": data.get('start_date'),
                    "end_date": data.get('end_date'),
                    "total_trades": data.get('metrics', {}).get('total_trades', 0),
                    "total_pnl": data.get('metrics', {}).get('total_pnl', 0.0),
                    "win_rate": data.get('metrics', {}).get('win_rate', 0.0),
                    "sharpe_ratio": data.get('metrics', {}).get('sharpe_ratio', 0.0),
                    "analysis_timestamp": data.get('analysis_timestamp'),
                    "file_size_kb": filepath.stat().st_size / 1024
                }
                results.append(result_info)

            except Exception as e:
                logger.warning("Failed to read backtest summary from %s: %s",
                               filepath.name, e)

        # Sort by analysis timestamp (newest first)
        results.sort(key=lambda x: x.get(
            'analysis_timestamp', ''), reverse=True)

        logger.info("Found %d backtest results", len(results))
        return results

    def get_best_results(self, limit: int = 10,
                         sort_by: str = 'total_pnl') -> List[BacktestResult]:
        """
        Get top backtest results sorted by specified metric.

        Args:
            limit: Maximum number of results to return
            sort_by: Metric to sort by ('total_pnl', 'sharpe_ratio', 'win_rate', etc.)

        Returns:
            List of best BacktestResult objects
        """
        results = []

        for result_info in self.list_backtest_results():
            result = self.load_backtest_result(result_info['filename'])
            if result:
                results.append(result)

        # Sort by specified metric
        if sort_by == 'total_pnl':
            results.sort(key=lambda r: r.metrics.total_pnl, reverse=True)
        elif sort_by == 'sharpe_ratio':
            results.sort(key=lambda r: r.metrics.sharpe_ratio, reverse=True)
        elif sort_by == 'win_rate':
            results.sort(key=lambda r: r.metrics.win_rate, reverse=True)
        elif sort_by == 'total_return_pct':
            results.sort(
                key=lambda r: r.metrics.total_return_pct, reverse=True)
        else:
            logger.warning("Unknown sort metric: %s, using total_pnl", sort_by)
            results.sort(key=lambda r: r.metrics.total_pnl, reverse=True)

        return results[:limit]

    def delete_backtest_result(self, filename: str) -> bool:
        """
        Delete specific backtest result file.

        Args:
            filename: Name of backtest result file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        filepath = self.backtest_dir / filename

        if not filepath.exists():
            logger.warning(
                "Cannot delete - backtest result file not found: %s", filename)
            return False

        try:
            filepath.unlink()
            logger.info("Deleted backtest result: %s", filename)
            return True

        except Exception as e:
            logger.error(
                "Failed to delete backtest result %s: %s", filename, e)
            return False

    def cleanup_old_results(self, keep_count: int = 50) -> int:
        """
        Clean up old backtest results, keeping only the most recent.

        Args:
            keep_count: Number of recent results to keep

        Returns:
            Number of files deleted
        """
        results = self.list_backtest_results()

        if len(results) <= keep_count:
            logger.info("No cleanup needed - %d results (limit: %d)",
                        len(results), keep_count)
            return 0

        # Delete oldest results
        to_delete = results[keep_count:]
        deleted_count = 0

        for result_info in to_delete:
            if self.delete_backtest_result(result_info['filename']):
                deleted_count += 1

        logger.info("Cleaned up %d old backtest results (kept %d)",
                    deleted_count, keep_count)
        return deleted_count

    def get_storage_info(self) -> Dict:
        """Get information about current backtest storage state."""
        results = self.list_backtest_results()

        if results:
            total_pnl = sum(r.get('total_pnl', 0) for r in results)
            avg_pnl = total_pnl / len(results)
            best_pnl = max(r.get('total_pnl', 0) for r in results)
            worst_pnl = min(r.get('total_pnl', 0) for r in results)
        else:
            total_pnl = avg_pnl = best_pnl = worst_pnl = 0

        total_size_kb = sum(r.get('file_size_kb', 0) for r in results)

        return {
            "total_results": len(results),
            "storage_directory": str(self.backtest_dir),
            "total_size_kb": total_size_kb,
            "avg_pnl_per_test": avg_pnl,
            "best_pnl": best_pnl,
            "worst_pnl": worst_pnl,
            "most_recent": results[0].get('analysis_timestamp') if results else None
        }


# Singleton instance following project pattern
backtest_storage = BacktestStorage()
