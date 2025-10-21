"""
Backtesting engine for dYdX Trading Bot

Implements backtesting simulation using existing trading logic
and dYdX client patterns from func_entry_pairs.py and func_exit_pairs.py.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

import pandas as pd
from func_backtest_logging import (
    log_backtest_debug,
    log_backtest_info,
    log_backtest_warning,
)

# func_public import removed - using direct API calls for backtesting
from models.backtest_models import (
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    calculate_backtest_metrics,
)
from sqlalchemy.orm import Session

# Database helpers for persistence
try:
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from backend.backtest_helpers import save_backtest_position, save_backtest_trade
    from backend.database import BacktestCandle
except ImportError:
    # Helpers not available (e.g., in standalone testing)
    save_backtest_position = None
    save_backtest_trade = None
    BacktestCandle = None

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Backtesting engine following existing trading bot patterns.

    Uses the same statistical analysis and trading logic as the live bot,
    but simulates execution on historical data instead of placing real trades.

    Supports strategy-driven parameter injection for flexible testing of different
    trading configurations without modifying the base config.yaml.
    """

    def __init__(
        self,
        client,
        config,
        run_id: Optional[str] = None,
        run_id_int: Optional[int] = None,
        db: Optional[Session] = None,
        strategy_id: Optional[int] = None,
        strategy_params: Optional[Dict] = None,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Initialize BacktestEngine with optional strategy parameters and progress tracking.

        Args:
            client: dYdX client instance
            config: Configuration object from config.yaml
            run_id: UUID string for logging
            run_id_int: Integer database ID for persistence
            db: SQLAlchemy session for storing logs
            strategy_id: Optional strategy ID from database (for reference)
            strategy_params: Optional dict of strategy parameters to override config
                Example: {'zscore_threshold': 2.0, 'usd_per_trade': 20.0}
            progress_callback: Optional async callback for progress updates
                Signature: async def callback(progress: float, current_pair: str, eta_seconds: int)
                - progress: 0-100 percentage
                - current_pair: market symbol being analyzed (e.g., "BTC-USD")
                - eta_seconds: estimated seconds remaining

        Parameter Precedence:
            1. strategy_params (highest priority - injected parameters)
            2. config.yaml (fallback)

        Type Hints:
            strategy_params keys should match config field names:
            - zscore_threshold (float)
            - usd_per_trade (float)
            - close_at_zscore_cross (bool)
            - stats_window (int)
            - transaction_fee (float)
            - slippage (float)
        """
        self.client = client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.run_id = run_id  # For logging to database (string UUID)
        self.run_id_int = run_id_int  # Integer database ID for helper function calls
        self.db = db  # Database session for storing logs
        self.strategy_id = strategy_id  # Optional strategy reference
        self.strategy_params = strategy_params or {}  # Store for reference
        self.progress_callback = progress_callback  # Progress tracking callback

        # Initialize simulation state
        self.starting_balance = config.backtesting.startingBalance
        self.current_balance = self.starting_balance
        self.transaction_fee = self._get_param(
            "transaction_fee", config.backtesting.transactionFee
        )
        self.slippage = self._get_param("slippage", config.backtesting.slippage)

        # Trading parameters (from strategy_params or fallback to config)
        self.zscore_threshold = self._get_param(
            "zscore_threshold", config.botSettings.ZScoreThreshold
        )
        self.usd_per_trade = self._get_param(
            "usd_per_trade", config.botSettings.usdPerTrade
        )
        self.close_at_zscore_cross = self._get_param(
            "close_at_zscore_cross", config.botSettings.closeAtZscoreCross
        )
        self.stats_window = self._get_param(
            "stats_window", config.botSettings.statsWindow
        )
        self.resolution = self._get_param(
            "resolution", config.backtesting.candleResolution
        )

        # Log strategy parameters if provided
        if strategy_id or strategy_params:
            self.logger.info(
                "BacktestEngine initialized with strategy_id=%s, params=%s",
                strategy_id,
                self.strategy_params,
            )

        # Simulation tracking
        self.open_positions = {}  # Similar to bot_agents.json structure
        self.completed_trades = []
        self.price_data = {}  # Cache for historical prices

        # Progress tracking state
        self._backtest_start_time: Optional[float] = None
        self._total_simulation_days: Optional[int] = None
        self._current_simulation_day = 0
        self._total_pairs_count = 0
        self._current_pair_index = 0

    def _get_param(self, key: str, default):
        """
        Get parameter from strategy_params or use default.

        Args:
            key: Parameter name
            default: Default value from config

        Returns:
            Parameter value from strategy_params if present, otherwise default
        """
        if key in self.strategy_params:
            value = self.strategy_params[key]
            self.logger.debug(
                "Using strategy parameter: %s=%s (default was %s)", key, value, default
            )
            return value
        return default

    def validate_strategy_params(self) -> bool:
        """
        Validate all strategy parameters for type correctness and value ranges.

        Returns:
            True if all parameters are valid, False otherwise

        Raises:
            ValueError: If any parameter is invalid
        """
        validation_rules = {
            "zscore_threshold": {"type": (int, float), "min": 0.1, "max": 10.0},
            "usd_per_trade": {"type": (int, float), "min": 0.01, "max": 10000.0},
            "close_at_zscore_cross": {"type": bool},
            "stats_window": {"type": int, "min": 5, "max": 365},
            "transaction_fee": {"type": (int, float), "min": 0.0, "max": 1.0},
            "slippage": {"type": (int, float), "min": 0.0, "max": 1.0},
        }

        for param_key, param_value in self.strategy_params.items():
            if param_key not in validation_rules:
                self.logger.warning(
                    "Unknown parameter: %s (will be ignored)", param_key
                )
                continue

            rule = validation_rules[param_key]

            # Type validation
            if not isinstance(param_value, rule["type"]):
                raise ValueError(
                    f"Parameter '{param_key}' must be {rule['type']}, "
                    f"got {type(param_value).__name__}: {param_value}"
                )

            # Range validation for numeric types
            if "min" in rule:
                if param_value < rule["min"]:
                    raise ValueError(
                        f"Parameter '{param_key}' must be >= {rule['min']}, "
                        f"got {param_value}"
                    )

            if "max" in rule:
                if param_value > rule["max"]:
                    raise ValueError(
                        f"Parameter '{param_key}' must be <= {rule['max']}, "
                        f"got {param_value}"
                    )

            self.logger.debug(
                "Validated parameter: %s=%s (type=%s)",
                param_key,
                param_value,
                type(param_value).__name__,
            )

        return True

    def get_parameter_summary(self) -> Dict:
        """
        Get summary of all active parameters (injected + defaults).

        Returns:
            Dictionary with all parameter values in use
        """
        return {
            "zscore_threshold": self.zscore_threshold,
            "usd_per_trade": self.usd_per_trade,
            "close_at_zscore_cross": self.close_at_zscore_cross,
            "stats_window": self.stats_window,
            "transaction_fee": self.transaction_fee,
            "slippage": self.slippage,
            "starting_balance": self.starting_balance,
            "strategy_id": self.strategy_id,
            "strategy_params_provided": len(self.strategy_params) > 0,
        }

    def update_trade_strategy_metadata(
        self, strategy_name: Optional[str] = None
    ) -> None:
        """
        Update strategy metadata in all completed trades.

        Called after backtest completion to enrich trade records with strategy
        information (typically retrieved from database).

        Args:
            strategy_name: Optional name of the strategy (for UI display)

        Returns:
            None (updates trades in-place)

        Example:
            >>> engine = BacktestEngine(..., strategy_id=10)
            >>> result = await engine.run_backtest(start_date, end_date)
            >>> # Later, after retrieving strategy name from database:
            >>> engine.update_trade_strategy_metadata(strategy_name="Conservative Cointegration")
            >>> # Now all trades have strategy_name populated
        """
        if not self.completed_trades:
            return

        # Count how many trades were updated
        trades_updated = 0

        for trade in self.completed_trades:
            # Update strategy metadata if not already set
            if trade.strategy_id is None and self.strategy_id is not None:
                trade.strategy_id = self.strategy_id

            if trade.strategy_name is None and strategy_name is not None:
                trade.strategy_name = strategy_name
                trades_updated += 1

        if trades_updated > 0:
            self.logger.debug(
                "Updated %d completed trades with strategy name: %s",
                trades_updated,
                strategy_name,
            )

    async def _emit_progress(
        self, progress_pct: float, current_pair: str = "", eta_seconds: int = 0
    ) -> None:
        """
        Emit progress update via callback if registered.

        Args:
            progress_pct: Progress percentage (0-100)
            current_pair: Market symbol being analyzed (e.g., "BTC-USD")
            eta_seconds: Estimated seconds remaining

        Returns:
            None (silently continues if callback unavailable)
        """
        if not self.progress_callback:
            return

        try:
            # Call async callback if available
            if self.progress_callback:
                await self.progress_callback(
                    progress=progress_pct,
                    current_pair=current_pair,
                    eta_seconds=eta_seconds,
                )
                self.logger.debug(
                    "Progress update sent: %.1f%% (%s), ETA: %ds",
                    progress_pct,
                    current_pair,
                    eta_seconds,
                )
        except Exception as e:
            # Don't fail the backtest if progress tracking fails
            self.logger.warning("Progress callback failed: %s", e)

    def _calculate_eta_seconds(self) -> int:
        """
        Calculate estimated seconds remaining based on progress.

        Uses elapsed time and current progress percentage to extrapolate
        total time and calculate remaining seconds.

        Returns:
            Estimated seconds remaining (0 if unable to calculate)
        """
        if not self._backtest_start_time or self._current_simulation_day == 0:
            return 0

        elapsed_seconds = time.time() - self._backtest_start_time
        if elapsed_seconds < 1:
            # Not enough data for accurate estimate
            return 0

        if not self._total_simulation_days:
            return 0

        # Calculate days per second
        days_per_second = self._current_simulation_day / elapsed_seconds
        if days_per_second <= 0:
            return 0

        # Estimate total seconds needed
        total_estimated_seconds = self._total_simulation_days / days_per_second
        remaining_seconds = max(0, int(total_estimated_seconds - elapsed_seconds))

        return remaining_seconds

    def _calculate_progress_percentage(self) -> float:
        """
        Calculate current progress as percentage.

        Returns:
            Progress percentage (0-100)
        """
        if not self._total_simulation_days or self._total_simulation_days == 0:
            return 0.0

        # Weight simulation days at 70%, pair processing at 30%
        days_progress = (
            self._current_simulation_day / self._total_simulation_days
        ) * 70
        pairs_progress = (
            self._current_pair_index / max(1, self._total_pairs_count)
        ) * 30

        return min(99.0, days_progress + pairs_progress)  # Cap at 99% until complete

    async def run_backtest(
        self, start_date: datetime, end_date: datetime, max_pairs: Optional[int] = None
    ) -> BacktestResult:
        """
        Run complete backtesting simulation.

        Args:
            start_date: Start date for backtesting
            end_date: End date for backtesting
            max_pairs: Maximum number of pairs to trade

        Returns:
            BacktestResult with performance metrics and trade history
        """
        pairs_info = "ALL" if max_pairs is None else str(max_pairs)
        self.logger.info(
            "Starting backtest: %s to %s (%s max pairs)",
            start_date.date(),
            end_date.date(),
            pairs_info,
        )

        # Log to database
        if self.run_id and self.db:
            log_backtest_info(
                self.run_id,
                f"Backtest started: {start_date.date()} to {end_date.date()} ({pairs_info} max pairs)",
                self.db,
            )

        # Store dates for use in data loading
        self.start_date = start_date
        self.end_date = end_date

        # Initialize progress tracking
        self._total_simulation_days = (end_date - start_date).days
        self._current_simulation_day = 0
        self._total_pairs_count = 0
        self._current_pair_index = 0
        self._backtest_start_time = time.time()

        try:
            # Step 1: Load historical market data
            if self.run_id and self.db:
                log_backtest_info(
                    self.run_id, "Loading historical price data...", self.db
                )
            await self._emit_progress(5.0, "Loading market data...")
            await self._load_historical_data()

            # Step 2: Find cointegrated pairs (using existing logic)
            if self.run_id and self.db:
                log_backtest_info(self.run_id, "Finding cointegrated pairs...", self.db)
            await self._emit_progress(10.0, "Finding cointegrated pairs...")
            cointegrated_pairs = await self._find_cointegrated_pairs(
                start_date, max_pairs
            )

            if not cointegrated_pairs:
                self.logger.warning("No cointegrated pairs found for backtesting")
                if self.run_id and self.db:
                    log_backtest_warning(
                        self.run_id, "No cointegrated pairs found", self.db
                    )
                await self._emit_progress(100.0, "Completed (no pairs)")
                return self._create_empty_result(start_date, end_date)

            self.logger.info(
                "Found %d cointegrated pairs for backtesting", len(cointegrated_pairs)
            )
            if self.run_id and self.db:
                log_backtest_info(
                    self.run_id,
                    f"Found {len(cointegrated_pairs)} cointegrated pairs",
                    self.db,
                )

            # Step 3: Simulate trading day by day
            self._total_pairs_count = len(cointegrated_pairs)
            current_date = start_date
            simulation_days = 0

            while current_date < end_date:
                await self._simulate_trading_day(current_date, cointegrated_pairs)
                current_date += timedelta(days=1)
                simulation_days += 1
                self._current_simulation_day = simulation_days

                # Progress logging every 10 days
                if simulation_days % 10 == 0:
                    self.logger.info(
                        "Backtest progress: %d days, %d open positions",
                        simulation_days,
                        len(self.open_positions),
                    )
                    if self.run_id and self.db:
                        log_backtest_debug(
                            self.run_id,
                            f"Progress: {simulation_days} days, {len(self.open_positions)} open positions",
                            self.db,
                        )

                    # Emit progress update
                    progress = self._calculate_progress_percentage()
                    eta = self._calculate_eta_seconds()
                    date_str = current_date.strftime("%Y-%m-%d")
                    await self._emit_progress(progress, date_str, eta)

            # Step 4: Close any remaining open positions at end date
            if self.run_id and self.db:
                log_backtest_info(
                    self.run_id,
                    f"Closing remaining {len(self.open_positions)} positions at backtest end",
                    self.db,
                )
            await self._emit_progress(95.0, "Closing positions...")
            await self._close_remaining_positions(end_date)

            # Step 5: Calculate performance metrics
            await self._emit_progress(98.0, "Calculating metrics...")
            total_days = (end_date - start_date).days
            metrics = calculate_backtest_metrics(
                self.completed_trades, self.starting_balance, total_days
            )

            # Step 6: Create result object
            result = BacktestResult(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                total_days=total_days,
                starting_balance=self.starting_balance,
                ending_balance=self.current_balance,
                metrics=metrics,
                trades=self.completed_trades,
                config_snapshot=self._get_config_snapshot(),
                analysis_timestamp=datetime.now().isoformat(),
            )

            self.logger.info(
                "Backtest completed: $%.2f PnL, %d trades, %.1f%% win rate",
                metrics.total_pnl,
                metrics.total_trades,
                metrics.win_rate,
            )

            if self.run_id and self.db:
                log_backtest_info(
                    self.run_id,
                    f"Backtest completed successfully: ${metrics.total_pnl:.2f} PnL, {metrics.total_trades} trades, {metrics.win_rate:.1f}% win rate",
                    self.db,
                )

            # Emit completion progress update
            await self._emit_progress(
                100.0,
                "Completed",
                0,
            )

            return result

        except Exception as e:
            self.logger.error("Backtest failed: %s", e)
            # Emit error progress update
            await self._emit_progress(0.0, f"Error: {str(e)}", 0)
            raise

    async def _load_historical_data_direct(self):
        """Load historical price data using direct dYdX API calls."""
        self.logger.info("Loading historical market data...")

        # Get available markets directly for backtesting
        markets_response = await self.client.indexer.markets.get_perpetual_markets()
        market_symbols = [
            market
            for market, info in markets_response["markets"].items()
            if info["status"] == "ACTIVE"
        ]

        # Calculate date range for backtesting
        end_date = self.end_date
        # Load extra data for statistical analysis (need window before start)
        # This extra data is used for cointegration analysis, not included in trading period
        data_start = self.start_date - timedelta(days=30)

        self.logger.info(
            "Backtesting period: %s to %s | Loading data from %s (includes 30-day pre-window for analysis)",
            self.start_date.date(),
            end_date.date(),
            data_start.date(),
        )

        # Load data for each market using direct API
        for symbol in market_symbols:
            try:
                # Make direct API call to get candle data
                response = (
                    await self.client.indexer.markets.get_perpetual_market_candles(
                        market=symbol,
                        resolution=self.resolution,
                        from_iso=data_start.isoformat() + ".000Z",
                        to_iso=end_date.isoformat() + ".000Z",
                        limit=1000,
                    )
                )

                if response and "candles" in response and len(response["candles"]) > 0:
                    candles_data = []

                    # Process each candle
                    for candle in response["candles"]:
                        candles_data.append(
                            {
                                "timestamp": candle.get("startedAt"),
                                "open": float(
                                    candle.get("open", candle.get("close", 0))
                                ),
                                "high": float(
                                    candle.get("high", candle.get("close", 0))
                                ),
                                "low": float(candle.get("low", candle.get("close", 0))),
                                "close": float(candle.get("close", 0)),
                                "volume": float(candle.get("baseTokenVolume", 0)),
                            }
                        )

                    # Convert to DataFrame
                    df = pd.DataFrame(candles_data)
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df.set_index("timestamp", inplace=True)
                    df.sort_index(inplace=True)

                    self.price_data[symbol] = df

                    # Save candles to database for later retrieval (Phase 3 persistence)
                    if self.db and self.run_id_int and BacktestCandle:
                        self._save_candles_to_db(symbol, df)

                    self.logger.debug("Loaded %d candles for %s", len(df), symbol)
                else:
                    self.logger.warning("No candle data for %s", symbol)

                # Rate limiting - be more respectful of API limits
                time.sleep(0.5)

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    self.logger.warning(
                        "Rate limited for %s, sleeping longer...", symbol
                    )
                    time.sleep(2.0)  # Longer sleep for rate limits
                else:
                    self.logger.warning(
                        "Failed to load data for %s: %s", symbol, error_msg
                    )

        self.logger.info("Loaded historical data for %d markets", len(self.price_data))

    def _save_candles_to_db(self, market: str, df: pd.DataFrame):
        """
        Save candle data to database for smart caching and chart rendering.

        This enables:
        - Persistent storage of historical candles across backtests
        - Smart caching to avoid re-fetching unchanged data
        - Frontend chart rendering from database instead of re-computing

        Args:
            market: Market symbol (e.g., "BTC-USD")
            df: DataFrame with OHLCV data indexed by timestamp
        """
        if not self.db or not self.run_id_int or not BacktestCandle:
            return  # Database not available

        try:
            # Batch insert candles - more efficient than one-by-one
            candles_to_insert = []

            for timestamp, row in df.iterrows():
                # Convert pandas Timestamp to Python datetime
                if isinstance(timestamp, pd.Timestamp):
                    timestamp_dt = timestamp.to_pydatetime()
                else:
                    timestamp_dt = timestamp

                candle = BacktestCandle(
                    run_id_fk=self.run_id_int,
                    market=market,
                    timestamp=timestamp_dt,
                    resolution=self.resolution,
                    open_price=float(row.get("open", 0)),
                    high_price=float(row.get("high", 0)),
                    low_price=float(row.get("low", 0)),
                    close_price=float(row.get("close", 0)),
                    volume=float(row.get("volume", 0)),
                )
                candles_to_insert.append(candle)

            # Batch insert
            if candles_to_insert:
                self.db.add_all(candles_to_insert)
                self.db.commit()
                self.logger.debug(
                    "Saved %d candles for %s to database",
                    len(candles_to_insert),
                    market,
                )
        except Exception as e:
            self.logger.warning(
                "Failed to save candles to database for %s: %s", market, str(e)
            )
            self.db.rollback()

    async def _load_historical_data(self):
        """Load historical data using the improved direct method."""
        return await self._load_historical_data_direct()

    async def _find_cointegrated_pairs(
        self, analysis_date: datetime, max_pairs: Optional[int]
    ) -> List[Dict]:
        """Find cointegrated pairs using existing analysis logic."""
        try:
            # Use existing cointegration analysis (simulate running at analysis_date)
            self.logger.info(
                "Running cointegration analysis for %s", analysis_date.date()
            )

            # Get subset of price data up to analysis date for pair finding
            analysis_data = {}
            # Convert analysis_date to pandas Timestamp for proper comparison with datetime64[ns, UTC]
            # Ensure the timestamp is timezone-aware (UTC)
            analysis_timestamp = pd.Timestamp(analysis_date, tz="UTC")
            for symbol, df in self.price_data.items():
                mask = df.index <= analysis_timestamp
                if mask.any():
                    analysis_data[symbol] = df[mask]["close"]

            if len(analysis_data) < 2:
                self.logger.warning(
                    "Insufficient market data for cointegration analysis"
                )
                return []

            # Run cointegration analysis (following existing logic)
            # Convert dict of Series to DataFrame for store_cointegration_results
            from func_cointegration import store_cointegration_results

            analysis_df = pd.DataFrame(analysis_data)
            store_cointegration_results(analysis_df)

            # Load the results from storage
            from models.pair_storage import pair_storage

            cointegration_results = pair_storage.load_pairs()

            # Filter and sort by strength (same logic as live trading)
            valid_pairs = []
            for result in cointegration_results:
                # Apply same filters as live trading
                if (
                    result.p_value <= 0.05
                    and result.half_life <= self.config.botSettings.maxHalfLife
                ):
                    valid_pairs.append(result)

            # Sort by p-value (strongest cointegration first)
            valid_pairs.sort(key=lambda x: x.p_value)

            # Limit to max_pairs (if specified)
            if max_pairs is not None:
                selected_pairs = valid_pairs[:max_pairs]
            else:
                selected_pairs = valid_pairs

            self.logger.info(
                "Selected %d cointegrated pairs from %d candidates",
                len(selected_pairs),
                len(valid_pairs),
            )

            return selected_pairs

        except Exception as e:
            self.logger.error("Cointegration analysis failed: %s", e)
            return []

    async def _simulate_trading_day(
        self, trading_date: datetime, pairs: List[Dict]
    ) -> None:
        """Simulate trading logic for a specific day."""
        # Get price data for this day
        day_prices = self._get_day_prices(trading_date)

        if not day_prices:
            return

        # Check for entry signals (following func_entry_pairs.py logic)
        await self._check_entry_signals(trading_date, pairs, day_prices)

        # Check for exit signals (following func_exit_pairs.py logic)
        await self._check_exit_signals(trading_date, day_prices)

    def _get_day_prices(self, trading_date: datetime) -> Dict[str, float]:
        """Get closing prices for all markets on specific date."""
        day_prices = {}

        for symbol, df in self.price_data.items():
            # Find price data for this date (or closest available)
            mask = df.index.date == trading_date.date()

            if mask.any():
                # Use closing price of the day
                day_prices[symbol] = float(df[mask]["close"].iloc[-1])
            elif len(df) > 0:
                # Use last available price if exact date not found
                # Ensure timestamp is timezone-aware (UTC) for comparison
                trading_timestamp = pd.Timestamp(trading_date, tz="UTC")
                closest_data = df[df.index <= trading_timestamp]
                if len(closest_data) > 0:
                    day_prices[symbol] = float(closest_data["close"].iloc[-1])

        return day_prices

    async def _check_entry_signals(
        self, trading_date: datetime, pairs: List[Dict], prices: Dict[str, float]
    ) -> None:
        """Check for trade entry signals (following existing entry logic)."""
        for pair in pairs:
            market_1 = pair.base_market
            market_2 = pair.quote_market

            # Skip if either market price not available
            if market_1 not in prices or market_2 not in prices:
                continue

            # Skip if already have position in this pair
            pair_key = f"{market_1}_{market_2}"
            if pair_key in self.open_positions:
                continue

            # Calculate current Z-score (simplified version of existing logic)
            try:
                z_score = self._calculate_zscore(pair, prices, trading_date)

                # Check if Z-score exceeds threshold
                if abs(z_score) >= self.zscore_threshold:
                    await self._enter_position(trading_date, pair, z_score, prices)

            except Exception as e:
                self.logger.warning(
                    "Failed to calculate Z-score for %s/%s: %s", market_1, market_2, e
                )

    async def _check_exit_signals(
        self, trading_date: datetime, prices: Dict[str, float]
    ) -> None:
        """Check for trade exit signals (following existing exit logic)."""
        positions_to_close = []

        for pair_key, position in self.open_positions.items():
            market_1 = position["market_1"]
            market_2 = position["market_2"]

            # Skip if either market price not available
            if market_1 not in prices or market_2 not in prices:
                continue

            try:
                # Calculate current Z-score for position
                z_score = self._calculate_zscore_for_position(
                    position, prices, trading_date
                )

                # Check exit conditions (following existing logic)
                should_close = False

                if self.close_at_zscore_cross:
                    # Close on Z-score crossing zero (mean reversion)
                    entry_z_score = position["z_score_entry"]
                    if (entry_z_score > 0 and z_score <= 0) or (
                        entry_z_score < 0 and z_score >= 0
                    ):
                        should_close = True

                if should_close:
                    positions_to_close.append((pair_key, position, z_score))

            except Exception as e:
                self.logger.warning("Failed to check exit for %s: %s", pair_key, e)

        # Close positions
        for pair_key, position, exit_z_score in positions_to_close:
            await self._exit_position(
                trading_date, pair_key, position, exit_z_score, prices
            )

    def _calculate_zscore(
        self, pair: Dict, current_prices: Dict[str, float], current_date: datetime
    ) -> float:
        """Calculate Z-score for pair (simplified version of existing logic)."""
        # Handle both dict and object formats (for compatibility with CointegrationResult and position dicts)
        if isinstance(pair, dict):
            market_1 = pair.get("base_market") or pair.get("market_1")
            market_2 = pair.get("quote_market") or pair.get("market_2")
            hedge_ratio = pair.get("hedge_ratio")
        else:
            # CointegrationResult object with attributes
            market_1 = pair.base_market
            market_2 = pair.quote_market
            hedge_ratio = pair.hedge_ratio

        # Validate required fields
        if not market_1 or not market_2 or hedge_ratio is None:
            raise ValueError(
                f"Invalid pair data: m1={market_1}, m2={market_2}, hr={hedge_ratio}"
            )

        # Get historical price series for Z-score calculation
        df1 = self.price_data.get(market_1)
        df2 = self.price_data.get(market_2)

        if df1 is None or df2 is None:
            raise ValueError(f"Missing price data for {market_1} or {market_2}")

        # Get data up to current date
        # Ensure timestamp is timezone-aware (UTC) for comparison
        current_timestamp = pd.Timestamp(current_date, tz="UTC")
        recent_data1 = df1[df1.index <= current_timestamp]["close"].tail(
            self.stats_window
        )
        recent_data2 = df2[df2.index <= current_timestamp]["close"].tail(
            self.stats_window
        )

        if (
            len(recent_data1) < self.stats_window
            or len(recent_data2) < self.stats_window
        ):
            raise ValueError("Insufficient historical data for Z-score calculation")

        # Calculate spread series
        spread_series = recent_data1 - (hedge_ratio * recent_data2)

        # Calculate Z-score
        spread_mean = spread_series.mean()
        spread_std = spread_series.std()

        if spread_std == 0:
            return 0.0

        # Current spread
        current_spread = current_prices[market_1] - (
            hedge_ratio * current_prices[market_2]
        )

        # Z-score
        z_score = (current_spread - spread_mean) / spread_std

        # Convert to native Python float (avoid NumPy serialization issues with PostgreSQL)
        return float(z_score)

    def _calculate_zscore_for_position(
        self, position: Dict, current_prices: Dict[str, float], current_date: datetime
    ) -> float:
        """Calculate Z-score for existing position."""
        # Reconstruct pair info from position
        fake_pair = {
            "base_market": position["market_1"],
            "quote_market": position["market_2"],
            "hedge_ratio": position["hedge_ratio"],
        }

        return self._calculate_zscore(fake_pair, current_prices, current_date)

    async def _enter_position(
        self,
        trading_date: datetime,
        pair: Dict,
        z_score: float,
        prices: Dict[str, float],
    ) -> None:
        """Enter new position (simulate trade execution)."""
        market_1 = pair.base_market
        market_2 = pair.quote_market
        hedge_ratio = pair.hedge_ratio

        # Determine trade direction (following existing logic)
        if z_score < 0:
            # Z-score negative: buy base, sell quote
            side_1 = "BUY"
            side_2 = "SELL"
        else:
            # Z-score positive: sell base, buy quote
            side_1 = "SELL"
            side_2 = "BUY"

        # Calculate position sizes (following existing logic)
        price_1 = prices[market_1]
        price_2 = prices[market_2]

        # Base size from USD allocation
        base_size = self.usd_per_trade / price_1

        # Quote size using hedge ratio
        quote_size = base_size * hedge_ratio

        # Apply slippage and fees
        effective_price_1 = price_1 * (1 + self.slippage)
        effective_price_2 = price_2 * (1 + self.slippage)

        # Create trade record ID
        trade_id = f"{market_1}_{market_2}_{int(trading_date.timestamp())}"

        # Add to open positions (following bot_agents.json structure)
        pair_key = f"{market_1}_{market_2}"
        self.open_positions[pair_key] = {
            "market_1": market_1,
            "market_2": market_2,
            "side_1": side_1,
            "side_2": side_2,
            "size_1": base_size,
            "size_2": quote_size,
            "entry_price_1": effective_price_1,
            "entry_price_2": effective_price_2,
            "z_score_entry": z_score,
            "hedge_ratio": hedge_ratio,
            "trade_id": trade_id,
            "entry_timestamp": trading_date.isoformat(),
        }

        # Calculate transaction costs
        transaction_cost_1 = (base_size * effective_price_1) * self.transaction_fee
        transaction_cost_2 = (quote_size * effective_price_2) * self.transaction_fee
        total_transaction_cost = transaction_cost_1 + transaction_cost_2

        # Update balance (reserve for margin)
        self.current_balance -= total_transaction_cost

        self.logger.debug(
            "Opened position: %s/%s, Z-score: %.2f, Size: %.4f/%.4f",
            market_1,
            market_2,
            z_score,
            base_size,
            quote_size,
        )

        # Log to database
        if self.run_id and self.db:
            log_backtest_debug(
                self.run_id,
                f"Entry signal: {market_1}/{market_2}, Z={z_score:.2f}, {side_1} {base_size:.4f}/{side_2} {quote_size:.4f}",
                self.db,
            )

        # Save position to database (if database helpers are available)
        if self.run_id_int and self.db and save_backtest_position:
            try:
                save_backtest_position(
                    db=self.db,
                    run_id=self.run_id_int,
                    market_1=market_1,
                    market_2=market_2,
                    status="OPEN",
                    entry_timestamp=trading_date,
                    entry_price_1=effective_price_1,
                    entry_price_2=effective_price_2,
                    entry_z_score=z_score,
                    size_1=base_size,
                    size_2=quote_size,
                    side_1=side_1,
                    side_2=side_2,
                    hedge_ratio=hedge_ratio,
                )
            except ValueError as e:
                # Validation error - likely run_id doesn't exist in database
                self.logger.error(
                    f"Failed to save position - validation error: {e} "
                    f"(run_id_int={self.run_id_int})"
                )
                if self.run_id and self.db:
                    log_backtest_warning(
                        self.run_id,
                        f"Position save validation failed: {str(e)}",
                        self.db,
                    )
            except Exception as e:
                # Other database errors
                self.logger.error(
                    f"Failed to save position to database: {e} "
                    f"(run_id_int={self.run_id_int})"
                )
                if self.run_id and self.db:
                    log_backtest_warning(
                        self.run_id,
                        f"Failed to save position: {str(e)}",
                        self.db,
                    )

    async def _exit_position(
        self,
        trading_date: datetime,
        pair_key: str,
        position: Dict,
        exit_z_score: float,
        prices: Dict[str, float],
    ) -> None:
        """Exit existing position (simulate trade closure)."""
        market_1 = position["market_1"]
        market_2 = position["market_2"]

        # Get exit prices
        exit_price_1 = prices[market_1] * (1 + self.slippage)
        exit_price_2 = prices[market_2] * (1 + self.slippage)

        # Calculate PnL (following existing calculation patterns)
        pnl = self._calculate_position_pnl(position, exit_price_1, exit_price_2)

        # Calculate duration
        entry_time = datetime.fromisoformat(position["entry_timestamp"])
        duration = (trading_date - entry_time).total_seconds() / 3600  # hours

        # Create completed trade record
        trade = BacktestTrade(
            timestamp=position["entry_timestamp"],
            market_1=market_1,
            market_2=position["market_2"],
            side_1=position["side_1"],
            side_2=position["side_2"],
            size_1=position["size_1"],
            size_2=position["size_2"],
            entry_price_1=position["entry_price_1"],
            entry_price_2=position["entry_price_2"],
            z_score_entry=position["z_score_entry"],
            hedge_ratio=position["hedge_ratio"],
            trade_id=position["trade_id"],
            exit_timestamp=trading_date.isoformat(),
            exit_price_1=exit_price_1,
            exit_price_2=exit_price_2,
            z_score_exit=exit_z_score,
            pnl=pnl,
            duration_hours=duration,
            strategy_id=self.strategy_id,
            strategy_name=None,  # Will be populated if strategy is loaded from DB
            strategy_zscore_threshold=self.zscore_threshold,
        )

        # Update balance with PnL
        self.current_balance += pnl

        # Add to completed trades
        self.completed_trades.append(trade)

        # Remove from open positions
        del self.open_positions[pair_key]

        self.logger.debug(
            "Closed position: %s, Duration: %.1fh, PnL: $%.2f", pair_key, duration, pnl
        )

        # Log to database
        if self.run_id and self.db:
            if pnl > 0:
                log_backtest_info(
                    self.run_id,
                    f"Exit signal: {market_1}/{market_2}, Z={exit_z_score:.2f}, Duration: {duration:.1f}h, Profit: ${pnl:.2f}",
                    self.db,
                )
            else:
                log_backtest_warning(
                    self.run_id,
                    f"Exit signal: {market_1}/{market_2}, Z={exit_z_score:.2f}, Duration: {duration:.1f}h, Loss: ${pnl:.2f}",
                    self.db,
                )

        # Save trade to database (if database helpers are available)
        if self.run_id_int and self.db and save_backtest_trade:
            try:
                pnl_pct = (
                    (pnl / self.usd_per_trade * 100) if self.usd_per_trade > 0 else 0
                )
                save_backtest_trade(
                    db=self.db,
                    run_id=self.run_id_int,
                    market_1=market_1,
                    market_2=market_2,
                    entry_timestamp=entry_time,
                    entry_price_1=position["entry_price_1"],
                    entry_price_2=position["entry_price_2"],
                    entry_z_score=position["z_score_entry"],
                    side_1=position["side_1"],
                    side_2=position["side_2"],
                    size_1=position["size_1"],
                    size_2=position["size_2"],
                    hedge_ratio=position["hedge_ratio"],
                    transaction_fee=self.transaction_fee,
                    slippage=self.slippage,
                    exit_timestamp=trading_date,
                    exit_price_1=exit_price_1,
                    exit_price_2=exit_price_2,
                    exit_z_score=exit_z_score,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    duration_hours=duration,
                )
            except ValueError as e:
                # Validation error - likely run_id doesn't exist in database
                self.logger.error(
                    f"Failed to save trade - validation error: {e} "
                    f"(run_id_int={self.run_id_int})"
                )
                if self.run_id and self.db:
                    log_backtest_warning(
                        self.run_id,
                        f"Trade save validation failed: {str(e)}",
                        self.db,
                    )
            except Exception as e:
                # Other database errors
                self.logger.error(
                    f"Failed to save trade to database: {e} "
                    f"(run_id_int={self.run_id_int})"
                )
                if self.run_id and self.db:
                    log_backtest_warning(
                        self.run_id,
                        f"Failed to save trade: {str(e)}",
                        self.db,
                    )

    def _calculate_position_pnl(
        self, position: Dict, exit_price_1: float, exit_price_2: float
    ) -> float:
        """Calculate PnL for position closure."""
        side_1 = position["side_1"]
        side_2 = position["side_2"]
        size_1 = position["size_1"]
        size_2 = position["size_2"]
        entry_price_1 = position["entry_price_1"]
        entry_price_2 = position["entry_price_2"]

        # Calculate PnL for each leg
        if side_1 == "BUY":
            pnl_1 = (exit_price_1 - entry_price_1) * size_1
        else:  # SELL
            pnl_1 = (entry_price_1 - exit_price_1) * size_1

        if side_2 == "BUY":
            pnl_2 = (exit_price_2 - entry_price_2) * size_2
        else:  # SELL
            pnl_2 = (entry_price_2 - exit_price_2) * size_2

        # Total PnL minus transaction costs
        total_pnl = pnl_1 + pnl_2

        # Subtract transaction costs for both entry and exit
        exit_cost_1 = (size_1 * exit_price_1) * self.transaction_fee
        exit_cost_2 = (size_2 * exit_price_2) * self.transaction_fee
        total_transaction_cost = exit_cost_1 + exit_cost_2

        return total_pnl - total_transaction_cost

    async def _close_remaining_positions(self, end_date: datetime) -> None:
        """Close all remaining open positions at backtest end."""
        if not self.open_positions:
            return

        self.logger.info(
            "Closing %d remaining positions at backtest end", len(self.open_positions)
        )

        # Get final prices
        final_prices = self._get_day_prices(end_date)

        positions_to_close = list(self.open_positions.items())
        for pair_key, position in positions_to_close:
            market_1 = position["market_1"]
            market_2 = position["market_2"]

            if market_1 in final_prices and market_2 in final_prices:
                # Force close with final Z-score of 0 (assumed mean reversion)
                await self._exit_position(
                    end_date, pair_key, position, 0.0, final_prices
                )

    def _get_config_snapshot(self) -> Dict:
        """Get configuration snapshot for backtest record."""
        return {
            "zscore_threshold": self.zscore_threshold,
            "usd_per_trade": self.usd_per_trade,
            "stats_window": self.stats_window,
            "close_at_zscore_cross": self.close_at_zscore_cross,
            "transaction_fee": self.transaction_fee,
            "slippage": self.slippage,
            "starting_balance": self.starting_balance,
        }

    def _create_empty_result(
        self, start_date: datetime, end_date: datetime
    ) -> BacktestResult:
        """Create empty result when no pairs found."""
        empty_metrics = BacktestMetrics(
            total_pnl=0.0,
            total_return_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            calmar_ratio=0.0,
            max_consecutive_losses=0,
            avg_trade_duration_hours=0.0,
        )

        return BacktestResult(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_days=(end_date - start_date).days,
            starting_balance=self.starting_balance,
            ending_balance=self.starting_balance,
            metrics=empty_metrics,
            trades=[],
            config_snapshot=self._get_config_snapshot(),
            analysis_timestamp=datetime.now().isoformat(),
        )
