"""
Light-weight models package exports used in tests.
This avoids importing heavy SQLModel/Pydantic types during test collection.
"""

from .user import User, AuditLog
from .backtest import (
    BacktestRun, BacktestResult, BacktestLog, BacktestTrade, BacktestPosition, BacktestCandle, BacktestComparison
)
from .trade import TradeLog
from .settings import BotSetting, RedisSetting
from .strategy import BacktestStrategy, StrategyVersionHistory, StrategyExecutionState
from .dydx_keys import DYDXKey, DYDXKeySettings

# Bot utility dataclasses
from .bot_backtest_models import BacktestTrade as BotBacktestTrade, BacktestMetrics, BacktestResult as BotBacktestResult
from .bot_pair_storage import CointegrationResult
from .bot_backtest_storage import BacktestStorage, backtest_storage

__all__ = [
    "User", "AuditLog",
    "BacktestRun", "BacktestResult", "BacktestLog", "BacktestTrade", "BacktestPosition", "BacktestCandle", "BacktestComparison",
    "TradeLog",
    "BotSetting", "RedisSetting",
    "BacktestStrategy", "StrategyVersionHistory", "StrategyExecutionState",
    "DYDXKey", "DYDXKeySettings",
    "BotBacktestTrade", "BacktestMetrics", "BotBacktestResult", "CointegrationResult",
    "BacktestStorage", "backtest_storage",
]