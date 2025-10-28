"""
Models package for dYdX Trading Bot (DEPRECATED)

DEPRECATED: Use models package instead
This is now a compatibility shim that imports from the main models package.
All models have been consolidated to /backend/models/
"""

# Import from main models package for backward compatibility
from models import CointegrationResult, BacktestStorage, BotBacktestTrade, BacktestMetrics, BotBacktestResult

# For backward compatibility, also try to import PairStorageManager
try:
    from models.bot_pair_storage import PairStorageManager, pair_storage
except ImportError:
    # pair_storage singleton may not be initialized yet
    PairStorageManager = None
    pair_storage = None

__all__ = [
    'CointegrationResult', 
    'PairStorageManager', 
    'pair_storage',
    'BacktestStorage',
    'BotBacktestTrade',
    'BacktestMetrics', 
    'BotBacktestResult',
]
