"""
Database models package - SQLModel-based ORM models + Bot utility models.
All SQLModel models are defined in sqlmodel_models.py with full type hints and validation.
Bot utility models (dataclasses) are in bot_backtest_models.py and bot_pair_storage.py
"""
from .sqlmodel_models import (
    # User models
    User, UserBase, UserCreate, UserRead, UserUpdate,
    DYDXKey, DYDXKeyBase, DYDXKeyRead, DYDXKeyCreate,
    DYDXKeySettings, DYDXKeySettingsBase, DYDXKeySettingsRead, DYDXKeySettingsCreate,
    # Backtest Strategy & Version History models
    BacktestStrategy, BacktestStrategyBase, BacktestStrategyRead, BacktestStrategyCreate,
    StrategyVersionHistory, StrategyVersionHistoryBase, StrategyVersionHistoryRead, StrategyVersionHistoryCreate,
    # Backtest Run models
    BacktestRun, BacktestRunBase, BacktestRunRead, BacktestRunCreate,
    # Backtest Result models
    BacktestResult, BacktestResultBase, BacktestResultRead,
    # Backtest Trade models
    BacktestTrade, BacktestTradeBase, BacktestTradeRead,
    # Backtest Candle models
    BacktestCandle, BacktestCandleBase, BacktestCandleRead,
    # Backtest Log models
    BacktestLog, BacktestLogBase, BacktestLogRead,
    # Backtest Position models
    BacktestPosition, BacktestPositionBase, BacktestPositionRead,
    # Backtest Comparison models
    BacktestComparison, BacktestComparisonBase, BacktestComparisonRead,
    # Trade Log models
    TradeLog, TradeLogBase, TradeLogRead,
    # Strategy Execution State models
    StrategyExecutionState, StrategyExecutionStateBase, StrategyExecutionStateRead,
    # Audit models
    AuditLog, AuditLogBase, AuditLogRead, AuditLogCreate,
    # Settings models
    BotSetting, BotSettingBase, BotSettingRead,
    RedisSettings, RedisSettingsBase, RedisSettingsRead,
)

# Bot utility models (dataclasses for bot operations)
from .bot_backtest_models import BacktestTrade as BotBacktestTrade, BacktestMetrics, BacktestResult as BotBacktestResult
from .bot_pair_storage import CointegrationResult, PairStorageManager, pair_storage
from .bot_backtest_storage import BacktestStorage

__all__ = [
    # SQLModel - User models
    "User", "UserBase", "UserCreate", "UserRead", "UserUpdate",
    "DYDXKey", "DYDXKeyBase", "DYDXKeyRead", "DYDXKeyCreate",
    "DYDXKeySettings", "DYDXKeySettingsBase", "DYDXKeySettingsRead", "DYDXKeySettingsCreate",
    # SQLModel - Backtest Strategy & Version History models
    "BacktestStrategy", "BacktestStrategyBase", "BacktestStrategyRead", "BacktestStrategyCreate",
    "StrategyVersionHistory", "StrategyVersionHistoryBase", "StrategyVersionHistoryRead", "StrategyVersionHistoryCreate",
    # SQLModel - Backtest Run models
    "BacktestRun", "BacktestRunBase", "BacktestRunRead", "BacktestRunCreate",
    # SQLModel - Backtest Result models
    "BacktestResult", "BacktestResultBase", "BacktestResultRead",
    # SQLModel - Backtest Trade models
    "BacktestTrade", "BacktestTradeBase", "BacktestTradeRead",
    # SQLModel - Backtest Candle models
    "BacktestCandle", "BacktestCandleBase", "BacktestCandleRead",
    # SQLModel - Backtest Log models
    "BacktestLog", "BacktestLogBase", "BacktestLogRead",
    # SQLModel - Backtest Position models
    "BacktestPosition", "BacktestPositionBase", "BacktestPositionRead",
    # SQLModel - Backtest Comparison models
    "BacktestComparison", "BacktestComparisonBase", "BacktestComparisonRead",
    # SQLModel - Trade Log models
    "TradeLog", "TradeLogBase", "TradeLogRead",
    # SQLModel - Strategy Execution State models
    "StrategyExecutionState", "StrategyExecutionStateBase", "StrategyExecutionStateRead",
    # SQLModel - Audit & Settings
    "AuditLog", "AuditLogBase", "AuditLogRead", "AuditLogCreate",
    "BotSetting", "BotSettingBase", "BotSettingRead",
    "RedisSettings", "RedisSettingsBase", "RedisSettingsRead",
    # Bot utility models (dataclasses)
    "BotBacktestTrade", "BacktestMetrics", "BotBacktestResult",
    "CointegrationResult", "PairStorageManager", "pair_storage", "BacktestStorage",
]
