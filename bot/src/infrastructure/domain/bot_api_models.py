"""Pydantic models for bot API operations and manager state."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BotStatus(str, Enum):
    """Bot status enumeration."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class TradingStrategy(str, Enum):
    """Supported strategy enum for bot instances."""

    MEAN_REVERSION = "mean_reversion"


class TradingParameters(BaseModel):
    """Trading parameters used by bot instances."""

    is_testnet: bool = True
    find_cointegrated_pairs: bool = True
    manage_exits: bool = True
    place_trades: bool = True
    abort_all_positions: bool = False
    resolution_timeframe: str = "1HOUR"
    strategy: TradingStrategy = TradingStrategy.MEAN_REVERSION
    stats_window: int = 21
    max_half_life: int = 24
    zscore_threshold: float = 1.5
    usd_per_trade: float = 10.0
    usd_min_collateral: float = 100.0
    close_at_zscore_cross: bool = True


class BotCredentials(BaseModel):
    """Minimal credentials for managing instance configs."""

    chain_id: str = "dydx-testnet-4"
    address: str
    mnemonic: str


class BotInstanceConfig(BaseModel):
    """Bot instance configuration payload."""

    instance_id: str = Field(..., description="Unique instance identifier")
    instance_name: Optional[str] = Field(
        None, description="Human-friendly instance name"
    )
    credentials: BotCredentials
    trading_params: TradingParameters


class BotInstanceStatus(BaseModel):
    """Runtime status exposed by bot manager."""

    instance_id: str
    status: BotStatus
    process_id: Optional[int] = None
    uptime_seconds: Optional[int] = None
    last_update: datetime
    config: Dict[str, Any] = Field(default_factory=dict)
    trading_stats: Dict[str, Any] = Field(default_factory=dict)


class BotInstanceList(BaseModel):
    """List of bot instances."""

    bots: List[BotInstanceStatus]
    total: int


class BotOperationResult(BaseModel):
    """Result of bot lifecycle operation."""

    success: bool
    message: str
    instance_id: Optional[str] = None
    status: Optional[BotStatus] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BotInstanceState(BaseModel):
    """Internal manager state for each instance."""

    instance_id: str
    config: BotInstanceConfig
    status: BotStatus
    process_info: Dict[str, Any] = Field(default_factory=dict)
    trading_stats: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    last_update: datetime

    def to_api_status(self) -> BotInstanceStatus:
        """Convert internal state to API status view."""
        process_id = self.process_info.get("pid")
        uptime_seconds: Optional[int] = None
        started_at = self.process_info.get("started_at")
        if isinstance(started_at, datetime):
            uptime_seconds = int((datetime.now() - started_at).total_seconds())

        return BotInstanceStatus(
            instance_id=self.instance_id,
            status=self.status,
            process_id=process_id,
            uptime_seconds=uptime_seconds,
            last_update=self.last_update,
            config=self.config.model_dump(),
            trading_stats=self.trading_stats,
        )
