"""
Pydantic models for bot API operations
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class BotStatus(str):
    """Bot status enumeration"""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class TradingParameters(BaseModel):
    """Trading parameters configuration"""
    usd_per_trade: float = Field(..., description="USD amount per trade")
    zscore_threshold: float = Field(..., description="Z-score threshold for trades")
    max_positions: int = Field(..., description="Maximum open positions")
    hedge_ratio_lookback: int = Field(100, description="Lookback period for hedge ratio")
    zscore_lookback: int = Field(100, description="Lookback period for z-score")
    min_half_life: int = Field(10, description="Minimum half-life for cointegration")
    max_half_life: int = Field(250, description="Maximum half-life for cointegration")


class BotCredentials(BaseModel):
    """Bot credentials for dYdX"""
    api_key: str = Field(..., description="dYdX API key")
    api_secret: str = Field(..., description="dYdX API secret")
    api_passphrase: str = Field(..., description="dYdX API passphrase")
    wallet_address: str = Field(..., description="Wallet address")
    private_key: str = Field(..., description="Private key")


class BotInstanceConfig(BaseModel):
    """Bot instance configuration"""
    instance_id: str = Field(..., description="Unique instance identifier")
    network: str = Field(..., description="Network (testnet/mainnet)")
    strategy: str = Field(..., description="Trading strategy")
    credentials: Optional[BotCredentials] = Field(None, description="dYdX credentials")
    parameters: TradingParameters = Field(..., description="Trading parameters")
    telegram_chat_id: Optional[str] = Field(None, description="Telegram chat ID for notifications")


class BotInstanceStatus(BaseModel):
    """Bot instance status"""
    instance_id: str
    status: BotStatus
    process_id: Optional[int]
    uptime_seconds: Optional[int]
    last_update: datetime
    config: Dict[str, Any]


class BotInstanceList(BaseModel):
    """List of bot instances"""
    bots: List[BotInstanceStatus]
    total: int


class BotOperationResult(BaseModel):
    """Result of bot operation"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
