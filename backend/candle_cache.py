"""
Smart Caching Service for Backtest Candles

Implements intelligent caching strategy to:
1. Check database for existing candles
2. Only fetch missing data from API
3. Minimize API calls while ensuring complete datasets
4. Support both real-time and historical data scenarios
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CandleCache:
    """
    Smart cache for backtest candles with gap detection and lazy loading.

    Implements a two-tier caching strategy:
    1. Database cache: Persistent storage for historical candles
    2. Memory cache: Fast access for current session
    """

    def __init__(self, db: Session):
        """
        Initialize candle cache with database session.

        Args:
            db: SQLAlchemy database session for persistence
        """
        self.db = db
        self._memory_cache: Dict[str, pd.DataFrame] = {}
        self.logger = logging.getLogger(__name__)

    def get_candles_for_backtest(
        self,
        run_id_fk: int,
        market: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        """
        Get complete candle dataset for backtest period.

        Implements smart caching:
        1. Check memory cache first (fastest)
        2. Query database for existing candles
        3. Identify gaps in data
        4. Return complete dataset from DB if available
        5. Log gaps for potential API refetch

        Args:
            run_id_fk: Backtest run ID
            market: Market symbol (e.g., "BTC-USD")
            start_date: Start of period (UTC)
            end_date: End of period (UTC)

        Returns:
            DataFrame with OHLCV data or None if insufficient data

        Example:
            >>> cache = CandleCache(db)
            >>> df = cache.get_candles_for_backtest(
            ...     run_id_fk=1, market="BTC-USD",
            ...     start_date=datetime(2025, 9, 20, tzinfo=UTC),
            ...     end_date=datetime(2025, 10, 20, tzinfo=UTC)
            ... )
            >>> print(f"Retrieved {len(df)} candles")
        """
        cache_key = f"{run_id_fk}:{market}:{start_date}:{end_date}"

        # Check memory cache
        if cache_key in self._memory_cache:
            self.logger.debug(f"Cache hit (memory): {market} for run {run_id_fk}")
            return self._memory_cache[cache_key]

        # Query database
        candles = self._query_database_candles(run_id_fk, market, start_date, end_date)

        if not candles:
            self.logger.warning(f"No candles found in DB for {market}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(candles)
        if df.empty:
            return None

        # Check for gaps
        gaps = self._find_gaps(df, start_date, end_date)
        if gaps:
            self.logger.info(
                f"Found {len(gaps)} gaps in {market} data: {gaps[:3]}..."
            )  # Log first 3 gaps

        # Store in memory cache
        self._memory_cache[cache_key] = df

        self.logger.info(f"Retrieved {len(df)} candles for {market} from DB")
        return df

    def _query_database_candles(
        self,
        run_id_fk: int,
        market: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List:
        """
        Query database for candles in date range.

        Args:
            run_id_fk: Backtest run ID
            market: Market symbol
            start_date: Start date
            end_date: End date

        Returns:
            List of BacktestCandle records
        """
        try:
            from backend.database import BacktestCandle

            query = (
                self.db.query(BacktestCandle)
                .filter_by(run_id_fk=run_id_fk, market=market)
                .filter(BacktestCandle.timestamp >= start_date)
                .filter(BacktestCandle.timestamp <= end_date)
                .order_by(BacktestCandle.timestamp)
                .all()
            )

            return query

        except Exception as e:
            self.logger.error(
                f"Failed to query candles for {market} (run {run_id_fk}): {e}"
            )
            return []

    def _find_gaps(
        self, df: pd.DataFrame, start_date: datetime, end_date: datetime
    ) -> List[Tuple]:
        """
        Find gaps in candle data for a given period.

        Args:
            df: DataFrame with candles
            start_date: Period start
            end_date: Period end

        Returns:
            List of (gap_start, gap_end) tuples for missing data

        Example:
            >>> gaps = cache._find_gaps(df, start, end)
            >>> for gap_start, gap_end in gaps:
            ...     print(f"Missing data: {gap_start} to {gap_end}")
        """
        gaps = []

        if df.empty:
            return [(start_date, end_date)]

        # Ensure timestamp column is datetime
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
            timestamps = df["timestamp"].tolist()
        else:
            return []

        # Check gap at beginning
        if pd.Timestamp(timestamps[0], tz="UTC") > pd.Timestamp(start_date, tz="UTC"):
            gaps.append((start_date, timestamps[0]))

        # Check gaps between candles (expect hourly, allow 1-hour gaps)
        for i in range(len(timestamps) - 1):
            current = pd.Timestamp(timestamps[i], tz="UTC")
            next_ts = pd.Timestamp(timestamps[i + 1], tz="UTC")

            time_diff = (next_ts - current).total_seconds() / 3600  # hours
            if time_diff > 1.5:  # Allow 1.5x normal gap
                gaps.append((current, next_ts))

        # Check gap at end
        if pd.Timestamp(timestamps[-1], tz="UTC") < pd.Timestamp(end_date, tz="UTC"):
            gaps.append((timestamps[-1], end_date))

        return gaps

    def get_candles_with_fallback(
        self,
        run_id_fk: int,
        market: str,
        start_date: datetime,
        end_date: datetime,
        fetch_func=None,
    ) -> Optional[pd.DataFrame]:
        """
        Get candles with fallback to API fetch if incomplete.

        Args:
            run_id_fk: Backtest run ID
            market: Market symbol
            start_date: Start date
            end_date: End date
            fetch_func: Optional async function to fetch from API

        Returns:
            Complete DataFrame or None

        Example:
            >>> async def fetch_from_api(market, start, end):
            ...     # Your API call here
            ...     return candles_df
            >>>
            >>> df = await cache.get_candles_with_fallback(
            ...     run_id_fk=1, market="BTC-USD",
            ...     start_date=start, end_date=end,
            ...     fetch_func=fetch_from_api
            ... )
        """
        # Try database first
        df = self.get_candles_for_backtest(run_id_fk, market, start_date, end_date)

        if df is not None and not df.empty:
            gaps = self._find_gaps(df, start_date, end_date)

            # If no gaps or no fetch function, return what we have
            if not gaps or not fetch_func:
                return df

            # If gaps exist and we can fetch, log but return partial data
            self.logger.info(
                f"Found {len(gaps)} gaps in {market}. "
                "Consider running fetch_and_save_missing_candles() to fill gaps."
            )
            return df

        # No data in DB, suggest fetching
        self.logger.warning(
            f"No candles for {market} in DB. "
            "Run fetch_and_save_missing_candles() to populate cache."
        )
        return None

    def clear_memory_cache(self) -> None:
        """Clear in-memory cache to free memory."""
        count = len(self._memory_cache)
        self._memory_cache.clear()
        self.logger.info(f"Cleared memory cache ({count} entries)")

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache info

        Example:
            >>> stats = cache.get_cache_stats()
            >>> print(f"Memory cache: {stats['memory_entries']} entries")
            >>> print(f"Memory used: {stats['memory_mb']:.2f} MB")
        """
        import sys

        memory_usage = sum(sys.getsizeof(df) for df in self._memory_cache.values()) / (
            1024 * 1024
        )

        return {
            "memory_entries": len(self._memory_cache),
            "memory_mb": memory_usage,
            "cache_keys": list(self._memory_cache.keys()),
        }


def create_cache_for_run(db: Session, run_id_fk: int) -> CandleCache:
    """
    Factory function to create cache for specific backtest run.

    Args:
        db: Database session
        run_id_fk: Backtest run ID

    Returns:
        Initialized CandleCache instance

    Example:
        >>> cache = create_cache_for_run(db, run_id_fk=1)
        >>> df = cache.get_candles_for_backtest(
        ...     run_id_fk=1, market="BTC-USD", start_date=start, end_date=end
        ... )
    """
    return CandleCache(db)
