"""Pydantic models for bot API operations and manager state."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BotStatus(str, Enum):
    """Bot status enumeration with incident-safe recovery states."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERING = "recovering"  # P1.7: Recovery in progress after crash/restart
    DEGRADED = "degraded"  # P1.7: Operational but with guardrails active
    SAFEGUARDED = "safeguarded"  # P1.7: Active incident-response mode (capital/position locked)


class TradingParameters(BaseModel):
    """Trading parameters used by bot instances."""

    is_testnet: bool = True
    subaccount_number: int = 0
    capital_allocation_usd: float = 0.0
    find_cointegrated_pairs: bool = True
    manage_exits: bool = True
    place_trades: bool = True
    abort_all_positions: bool = False
    resolution_timeframe: str = "1HOUR"
    strategy: str = "cointegration"
    stats_window: int = 21
    max_half_life: int = 24
    zscore_threshold: float = 1.5
    usd_per_trade: float = 10.0
    usd_min_collateral: float = 100.0
    close_at_zscore_cross: bool = True
    max_positions: int = 5
    max_drawdown_pct: float = 0.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 5.0
    trailing_stop_pct: float = 0.0
    rebalance_interval_hours: int = 24
    position_timeout_hours: int = 72
    selected_markets: List[str] = Field(default_factory=list)


class BacktestingParameters(BaseModel):
    """Backtesting defaults stored alongside runtime-managed instances."""

    candle_resolution: str = "1HOUR"
    max_history_days: int = 90
    starting_balance: float = 1000.0
    transaction_fee: float = 0.0005
    slippage: float = 0.001
    benchmark_symbol: str = "BTC-USD"
    risk_free_rate: float = 0.02


class BotCredentials(BaseModel):
    """Minimal credentials for managing instance configs."""

    chain_id: str = "dydx-testnet-4"
    address: str
    mnemonic: str


class TelegramConfig(BaseModel):
    """Shared Telegram notification settings for runtime-managed instances."""

    token: str = ""
    chat_id: str = ""


class BotInstanceConfig(BaseModel):
    """Bot instance configuration payload."""

    instance_id: str = Field(..., description="Unique instance identifier")
    instance_name: Optional[str] = Field(
        None, description="Human-friendly instance name"
    )
    credentials: BotCredentials
    telegram: Optional[TelegramConfig] = None
    trading_params: TradingParameters
    backtesting_params: Optional[BacktestingParameters] = None


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
    # P1.7: Liveness and recovery tracking
    last_heartbeat: Optional[datetime] = None  # Last verified alive signal
    heartbeat_stale_seconds: int = 30  # Time before marking as stale/degraded
    recovery_state: Optional[str] = None  # "recovering", "degraded", "safeguarded", or None
    recovery_reason: Optional[str] = None  # Why recovery state was activated

    def to_api_status(self) -> BotInstanceStatus:
        """Convert internal state to API status view."""
        process_id = self.process_info.get("pid")
        uptime_seconds: Optional[int] = None
        started_at = self.process_info.get("started_at")
        if isinstance(started_at, datetime):
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            uptime_seconds = int(
                (datetime.now(timezone.utc) - started_at).total_seconds()
            )

        return BotInstanceStatus(
            instance_id=self.instance_id,
            status=self.status,
            process_id=process_id,
            uptime_seconds=uptime_seconds,
            last_update=self.last_update,
            config=self.config.model_dump(),
            trading_stats=self.trading_stats,
        )
