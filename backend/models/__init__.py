"""
Database models for dYdX Trading Bot backend.

This package contains all SQLAlchemy ORM models for:
- Backtest runs and results
- Trading logs and positions
- User accounts and authentication
- Strategy configurations and version history
- Execution states and comparisons
- Bot settings and audit logs
"""

from .backtest import (
    BacktestCandle,
    BacktestComparison,
    BacktestLog,
    BacktestPosition,
    BacktestResult,
    BacktestRun,
    BacktestTrade,
)
from .strategy import (
    BacktestStrategy,
    StrategyExecutionState,
    StrategyVersionHistory,
)
from .trade import TradeLog
from .user import AuditLog, User
from .settings import BotSetting, RedisSetting

__all__ = [
    # Backtest models
    "BacktestRun",
    "BacktestResult",
    "BacktestTrade",
    "BacktestLog",
    "BacktestPosition",
    "BacktestCandle",
    "BacktestComparison",
    # Strategy models
    "BacktestStrategy",
    "StrategyVersionHistory",
    "StrategyExecutionState",
    # Trade models
    "TradeLog",
    # User models
    "User",
    "AuditLog",
    # Settings models
    "BotSetting",
    "RedisSetting",
]
