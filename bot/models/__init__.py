"""
Models package for the dYdX trading bot

This package contains data models and structures used throughout the bot system,
including backtest results, trading data, and configuration models.
"""

import importlib.util
from pathlib import Path

# Import from local backtest models
from .backtest_models import (
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    calculate_backtest_metrics,
)

# Load models.py directly to avoid circular imports
models_file = Path(__file__).parent / "models.py"
if not models_file.exists():
    models_file = Path(__file__).parent.parent / "models.py"

spec = importlib.util.spec_from_file_location("models_main", models_file)
if spec and spec.loader:
    models_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(models_module)

    # Export all needed classes and enums
    Base = models_module.Base
    BotStatusEnum = models_module.BotStatusEnum
    JobStatusEnum = models_module.JobStatusEnum
    TradeStatusEnum = models_module.TradeStatusEnum
    BotInstance = models_module.BotInstance
    Job = models_module.Job
    Trade = models_module.Trade
    EventLog = models_module.EventLog
    SystemMetrics = models_module.SystemMetrics
    DailyReport = models_module.DailyReport

    # Import BacktestRun from models_backtest since it's not in the main models.py
    try:
        from models_backtest import BacktestRun
    except ImportError:
        BacktestRun = None
else:
    raise ImportError("Could not load models.py")

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
]
