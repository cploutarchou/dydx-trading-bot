"""
Bot API Models - Data structures for API-controlled trading bot instances
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator


class BotStatus(str, Enum):
    """Bot instance status"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class TradingStrategy(str, Enum):
    """Available trading strategies"""
    COINTEGRATION = "cointegration"
    MEAN_REVERSION = "mean_reversion"


class NetworkEnvironment(str, Enum):
    """Network environments"""
    TESTNET = "testnet" 
    MAINNET = "mainnet"


# ============================================================================
# API REQUEST MODELS
# ============================================================================

class BotCredentials(BaseModel):
    """dYdX wallet credentials for bot instance"""
    address: str = Field(..., min_length=40, description="dYdX wallet address")
    mnemonic: str = Field(..., min_length=10, description="Wallet mnemonic phrase")
    
    class Config:
        schema_extra = {
            "example": {
                "address": "dydx1abc123...",
                "mnemonic": "word1 word2 word3 ..."
            }
        }


class TradingParameters(BaseModel):
    """Bot trading configuration parameters"""
    # Network Configuration
    is_testnet: bool = Field(True, description="Use testnet (true) or mainnet (false)")
    
    # Position Management Flags
    abort_all_positions: bool = Field(False, description="Close all positions on startup")
    find_cointegrated_pairs: bool = Field(True, description="Run cointegration analysis")
    manage_exits: bool = Field(True, description="Monitor and close positions")
    place_trades: bool = Field(True, description="Execute new trades")
    
    # Trading Strategy Parameters
    resolution_timeframe: str = Field("1HOUR", description="Candle resolution for analysis")
    strategy: TradingStrategy = Field(TradingStrategy.COINTEGRATION, description="Trading strategy")
    stats_window: int = Field(21, ge=5, le=100, description="Statistical analysis window")
    max_half_life: int = Field(24, ge=1, le=168, description="Maximum mean reversion period (hours)")
    zscore_threshold: float = Field(1.5, ge=0.5, le=5.0, description="Z-score entry trigger")
    usd_per_trade: float = Field(10.0, ge=1.0, le=10000.0, description="Position size per trade (USD)")
    usd_min_collateral: float = Field(100.0, ge=10.0, description="Minimum account collateral (USD)")
    close_at_zscore_cross: bool = Field(True, description="Close positions on Z-score mean reversion")
    
    @validator('resolution_timeframe')
    def validate_timeframe(cls, v):
        valid_timeframes = ["1MIN", "5MINS", "15MINS", "30MINS", "1HOUR", "4HOURS", "1DAY"]
        if v not in valid_timeframes:
            raise ValueError(f"Invalid timeframe. Must be one of: {valid_timeframes}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "is_testnet": True,
                "abort_all_positions": False,
                "find_cointegrated_pairs": True,
                "manage_exits": True,
                "place_trades": True,
                "resolution_timeframe": "1HOUR",
                "strategy": "cointegration",
                "stats_window": 21,
                "max_half_life": 24,
                "zscore_threshold": 1.5,
                "usd_per_trade": 10.0,
                "usd_min_collateral": 100.0,
                "close_at_zscore_cross": True
            }
        }


class BotInstanceConfig(BaseModel):
    """Complete bot instance configuration"""
    instance_id: str = Field(..., min_length=1, max_length=50, description="Unique bot instance ID")
    instance_name: str = Field(..., min_length=1, max_length=100, description="Human-readable bot name")
    credentials: BotCredentials = Field(..., description="dYdX wallet credentials")
    trading_params: TradingParameters = Field(..., description="Trading configuration")
    
    @validator('instance_id')
    def validate_instance_id(cls, v):
        # Only alphanumeric, hyphens, underscores
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Instance ID must contain only letters, numbers, hyphens, and underscores")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "instance_id": "btc-eth-arb-bot",
                "instance_name": "BTC-ETH Arbitrage Bot",
                "credentials": {
                    "address": "dydx1abc123...",
                    "mnemonic": "word1 word2 word3 ..."
                },
                "trading_params": {
                    "is_testnet": True,
                    "zscore_threshold": 1.5,
                    "usd_per_trade": 25.0
                }
            }
        }


class BotActionRequest(BaseModel):
    """Request to perform action on bot instance"""
    action: str = Field(..., description="Action to perform")
    instance_id: str = Field(..., description="Target bot instance ID")
    
    @validator('action')
    def validate_action(cls, v):
        valid_actions = ["start", "stop", "restart", "pause", "resume"]
        if v not in valid_actions:
            raise ValueError(f"Invalid action. Must be one of: {valid_actions}")
        return v


# ============================================================================
# API RESPONSE MODELS  
# ============================================================================

class BotInstanceStatus(BaseModel):
    """Current status of a bot instance"""
    instance_id: str
    instance_name: str
    status: BotStatus
    network: NetworkEnvironment
    created_at: datetime
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    # Trading Statistics
    total_trades: int = 0
    active_positions: int = 0
    total_pnl_usd: float = 0.0
    daily_pnl_usd: float = 0.0
    
    # Configuration Summary
    strategy: TradingStrategy
    usd_per_trade: float
    zscore_threshold: float
    
    # Process Information
    pid: Optional[int] = None
    cpu_usage: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class BotInstanceList(BaseModel):
    """List of bot instances with summary"""
    instances: List[BotInstanceStatus]
    total_instances: int
    running_instances: int
    stopped_instances: int
    error_instances: int


class BotOperationResult(BaseModel):
    """Result of bot operation (start, stop, etc.)"""
    success: bool
    message: str
    instance_id: str
    status: BotStatus
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BotTradingStats(BaseModel):
    """Detailed trading statistics for bot instance"""
    instance_id: str
    period_start: datetime
    period_end: datetime
    
    # Trade Statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # P&L Statistics  
    total_pnl_usd: float
    avg_trade_pnl_usd: float
    max_win_usd: float
    max_loss_usd: float
    
    # Position Statistics
    current_positions: int
    max_positions: int
    avg_position_duration_hours: float
    
    # Risk Metrics
    sharpe_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    profit_factor: Optional[float] = None


# ============================================================================
# INTERNAL DATA STRUCTURES
# ============================================================================

@dataclass
class BotInstanceState:
    """Internal bot instance state management"""
    instance_id: str
    config: BotInstanceConfig
    status: BotStatus
    process_info: Dict
    trading_stats: Dict
    created_at: datetime
    last_update: datetime
    
    def to_api_status(self) -> BotInstanceStatus:
        """Convert to API response model"""
        return BotInstanceStatus(
            instance_id=self.instance_id,
            instance_name=self.config.instance_name,
            status=self.status,
            network=NetworkEnvironment.TESTNET if self.config.trading_params.is_testnet else NetworkEnvironment.MAINNET,
            created_at=self.created_at,
            started_at=self.process_info.get('started_at'),
            stopped_at=self.process_info.get('stopped_at'),
            last_activity=self.last_update,
            total_trades=self.trading_stats.get('total_trades', 0),
            active_positions=self.trading_stats.get('active_positions', 0),
            total_pnl_usd=self.trading_stats.get('total_pnl_usd', 0.0),
            daily_pnl_usd=self.trading_stats.get('daily_pnl_usd', 0.0),
            strategy=self.config.trading_params.strategy,
            usd_per_trade=self.config.trading_params.usd_per_trade,
            zscore_threshold=self.config.trading_params.zscore_threshold,
            pid=self.process_info.get('pid'),
            cpu_usage=self.process_info.get('cpu_usage'),
            memory_usage_mb=self.process_info.get('memory_usage_mb')
        )