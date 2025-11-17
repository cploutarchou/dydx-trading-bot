"""
Models package for the dYdX trading bot

This package contains data models and structures used throughout the bot system,
including backtest results, trading data, and configuration models.
"""

# Import from reorganized models structure
from internal.domain.analysis.backtest_metrics import (
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    calculate_backtest_metrics,
)
from internal.domain.models.core import (
    Base,
    BotInstance,
    BotStatusEnum,
    DailyReport,
    EventLog,
    Job,
    JobStatusEnum,
    SystemMetrics,
    Trade,
    TradeStatusEnum,
)
from internal.domain.persistence.cointegration_storage import (
    CointegrationResult,
    PairStorage,
    calculate_confidence_score,
    pair_storage,
)

# Import BacktestRun if available
try:
    from internal.domain.models.backtest import BacktestRun
except ImportError:
    BacktestRun = None

__all__ = [
    "Base",
    "BotStatusEnum",
    "JobStatusEnum",
    "TradeStatusEnum",
    "BotInstance",
    "Job",
    "Trade",
    "EventLog",
    "SystemMetrics",
    "DailyReport",
    "BacktestRun",
    "BacktestMetrics",
    "BacktestResult",
    "BacktestTrade",
    "calculate_backtest_metrics",
    "CointegrationResult",
    "calculate_confidence_score",
    "PairStorage",
    "pair_storage",
]
