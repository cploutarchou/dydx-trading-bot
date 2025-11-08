"""Tests for Phase 3 Task 4: Trade Log Enhancement with Strategy Metadata"""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add app directory to path for imports
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

from func_backtesting import BacktestEngine
from models.backtest_models import BacktestTrade


class TestBacktestTradeModel:
    """Tests for BacktestTrade dataclass enhancements"""

    def test_backtest_trade_has_strategy_fields(self):
        """Verify BacktestTrade includes new strategy fields"""
        trade = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="test-123",
            strategy_id=42,
            strategy_name="Test Strategy",
            strategy_zscore_threshold=1.5,
        )

        # Verify all strategy fields are stored
        assert trade.strategy_id == 42
        assert trade.strategy_name == "Test Strategy"
        assert trade.strategy_zscore_threshold == 1.5

    def test_backtest_trade_strategy_fields_optional(self):
        """Verify strategy fields are optional (backward compatibility)"""
        trade = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="test-123",
            # No strategy fields provided
        )

        # Verify optional fields default to None
        assert trade.strategy_id is None
        assert trade.strategy_name is None
        assert trade.strategy_zscore_threshold is None

    def test_backtest_trade_partial_strategy_metadata(self):
        """Verify partial strategy metadata is supported"""
        trade = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="test-123",
            strategy_id=42,
            strategy_name=None,  # Can be partially filled
            strategy_zscore_threshold=1.5,
        )

        assert trade.strategy_id == 42
        assert trade.strategy_name is None
        assert trade.strategy_zscore_threshold == 1.5

    def test_backtest_trade_with_exit_data_and_strategy(self):
        """Verify strategy fields work with completed trade data"""
        trade = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="test-123",
            exit_timestamp="2024-01-02T10:00:00Z",
            exit_price_1=46000.00,
            exit_price_2=2550.00,
            z_score_exit=0.2,
            pnl=150.00,
            duration_hours=24,
            strategy_id=42,
            strategy_name="Conservative Cointegration",
            strategy_zscore_threshold=1.5,
        )

        # Verify all fields including strategy
        assert trade.strategy_id == 42
        assert trade.strategy_name == "Conservative Cointegration"
        assert trade.strategy_zscore_threshold == 1.5
        assert trade.pnl == 150.00
        assert trade.duration_hours == 24

    def test_backtest_trade_strategy_dataclass_validation(self):
        """Verify BacktestTrade is a proper dataclass with strategy fields"""
        import dataclasses

        fields = {f.name: f.type for f in dataclasses.fields(BacktestTrade)}

        # Verify strategy fields exist
        assert "strategy_id" in fields
        assert "strategy_name" in fields
        assert "strategy_zscore_threshold" in fields

        # Verify field types are Optional
        assert "Optional[int]" in str(fields["strategy_id"])
        assert "Optional[str]" in str(fields["strategy_name"])
        assert "Optional[float]" in str(fields["strategy_zscore_threshold"])


class TestStrategyEnrichmentMethod:
    """Tests for update_trade_strategy_metadata enrichment method"""

    def test_enrichment_method_exists(self):
        """Verify BacktestEngine has update_trade_strategy_metadata method"""
        assert hasattr(BacktestEngine, "update_trade_strategy_metadata")

    def test_enrichment_handles_no_trades(self):
        """Verify enrichment handles empty trade list gracefully"""
        mock_engine = MagicMock()
        mock_engine.completed_trades = []
        mock_engine.logger = logging.getLogger(__name__)

        # Call the actual method
        BacktestEngine.update_trade_strategy_metadata(mock_engine, "Test Strategy")

        # Should not raise any errors
        assert len(mock_engine.completed_trades) == 0

    def test_enrichment_updates_strategy_name(self):
        """Verify enrichment updates strategy_name in trades"""
        # Create sample trades
        trade1 = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="test-1",
            strategy_id=42,
            strategy_name=None,  # Not set yet
            strategy_zscore_threshold=1.5,
        )

        mock_engine = MagicMock()
        mock_engine.strategy_id = 42
        mock_engine.completed_trades = [trade1]
        mock_engine.logger = logging.getLogger(__name__)

        # Update strategy metadata
        BacktestEngine.update_trade_strategy_metadata(
            mock_engine, "Conservative Cointegration"
        )

        # Verify trade was updated
        assert (
            mock_engine.completed_trades[0].strategy_name
            == "Conservative Cointegration"
        )

    def test_enrichment_preserves_existing_names(self):
        """Verify enrichment doesn't overwrite existing strategy_name"""
        # Create trade with existing strategy_name
        trade = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="test-1",
            strategy_id=42,
            strategy_name="Original Strategy",  # Already set
            strategy_zscore_threshold=1.5,
        )

        mock_engine = MagicMock()
        mock_engine.strategy_id = 42
        mock_engine.completed_trades = [trade]
        mock_engine.logger = logging.getLogger(__name__)

        # Attempt to update with different name
        BacktestEngine.update_trade_strategy_metadata(mock_engine, "New Strategy Name")

        # Verify original name was preserved
        assert mock_engine.completed_trades[0].strategy_name == "Original Strategy"


class TestTradeCreationWithStrategy:
    """Integration tests for trade creation capturing strategy metadata"""

    def test_trade_entry_contains_strategy_fields(self):
        """Verify entry trades capture strategy metadata"""
        trade = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="entry-123",
            strategy_id=42,
            strategy_name=None,  # Set at entry
            strategy_zscore_threshold=1.5,  # Capture threshold
        )

        # Entry trades should have all fields
        assert trade.strategy_id == 42
        assert trade.strategy_zscore_threshold == 1.5
        assert trade.exit_timestamp is None  # Not exited yet
        assert trade.pnl is None

    def test_trade_exit_preserves_entry_strategy_fields(self):
        """Verify exit trades preserve entry strategy metadata"""
        trade = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="entry-123",
            exit_timestamp="2024-01-02T10:00:00Z",
            exit_price_1=46000.00,
            exit_price_2=2550.00,
            z_score_exit=0.2,
            pnl=150.00,
            duration_hours=24,
            strategy_id=42,  # Preserved from entry
            strategy_name=None,  # Will be enriched
            strategy_zscore_threshold=1.5,  # Preserved from entry
        )

        # Exit trades should have strategy metadata from entry
        assert trade.strategy_id == 42
        assert trade.strategy_zscore_threshold == 1.5
        assert trade.exit_timestamp == "2024-01-02T10:00:00Z"
        assert trade.pnl == 150.00

    def test_backward_compatibility_trades_without_strategy(self):
        """Verify trades work without strategy metadata (backward compat)"""
        trade = BacktestTrade(
            timestamp="2024-01-01T10:00:00Z",
            market_1="BTC-USD",
            market_2="ETH-USD",
            side_1="BUY",
            side_2="SELL",
            size_1=0.1,
            size_2=1.5,
            entry_price_1=45000.00,
            entry_price_2=2500.00,
            z_score_entry=1.8,
            hedge_ratio=0.05,
            trade_id="legacy-123",
            # No strategy fields provided
        )

        # Legacy trades should still work
        assert trade.timestamp == "2024-01-01T10:00:00Z"
        assert trade.market_1 == "BTC-USD"
        assert trade.strategy_id is None
        assert trade.strategy_name is None
        assert trade.strategy_zscore_threshold is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
