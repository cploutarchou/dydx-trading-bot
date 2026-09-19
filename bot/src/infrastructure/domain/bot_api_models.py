"""Pydantic models for bot API operations and manager state."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from src.shared.trading_validators import normalize_market_list


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
    SAFEGUARDED = (
        "safeguarded"  # P1.7: Active incident-response mode (capital/position locked)
    )


class TradingParameters(BaseModel):
    """Trading parameters used by bot instances.

    Numeric fields carry explicit bounds so invalid trades (negative sizes,
    zero stats windows, etc.) are rejected at the API boundary with a 422
    instead of reaching the live runtime. Values left unbounded here are either
    config-driven free-form strings (``resolution_timeframe``, ``strategy``) or
    rejected later by ``assert_supported_live_risk_controls`` when > 0.
    """

    is_testnet: bool = True
    subaccount_number: int = Field(default=0, ge=0)
    capital_allocation_usd: float = Field(
        default=0.0, ge=0.0
    )  # rejected if > 0 by live risk controls
    find_cointegrated_pairs: bool = True
    manage_exits: bool = True
    place_trades: bool = True
    abort_all_positions: bool = False
    resolution_timeframe: str = Field(default="1HOUR", min_length=1, max_length=64)
    strategy: str = Field(default="cointegration", min_length=1, max_length=64)
    stats_window: int = Field(default=21, ge=2, le=2000)
    max_half_life: int = Field(default=24, ge=1, le=10000)
    zscore_threshold: float = Field(default=1.5, gt=0.0)
    usd_per_trade: float = Field(default=10.0, gt=0.0)
    usd_min_collateral: float = Field(default=100.0, ge=0.0)
    close_at_zscore_cross: bool = True
    max_positions: int = Field(default=5, ge=0, le=100)
    max_drawdown_pct: float = Field(
        default=0.0, ge=0.0, le=100.0
    )  # rejected if > 0 by live risk controls
    stop_loss_pct: float = Field(default=2.0, ge=0.0, le=100.0)
    take_profit_pct: float = Field(default=5.0, ge=0.0, le=1000.0)
    trailing_stop_pct: float = Field(
        default=0.0, ge=0.0, le=100.0
    )  # rejected if > 0 by live risk controls
    rebalance_interval_hours: int = Field(default=24, ge=0, le=8760)
    position_timeout_hours: int = Field(default=72, ge=0, le=8760)
    selected_markets: List[str] = Field(default_factory=list)

    @field_validator("selected_markets", mode="before")
    @classmethod
    def _normalize_selected_markets(cls, value: Any) -> List[str]:
        # Strip/dedupe/uppercase before constraints run so callers receive a
        # clean canonical list rather than a 422 on minor formatting.
        return normalize_market_list(value)


class BacktestingParameters(BaseModel):
    """Backtesting defaults stored alongside runtime-managed instances."""

    candle_resolution: str = Field(default="1HOUR", min_length=1, max_length=16)
    max_history_days: int = Field(default=90, ge=1, le=36500)
    starting_balance: float = Field(default=1000.0, gt=0.0)
    transaction_fee: float = Field(default=0.0005, ge=0.0, lt=1.0)
    slippage: float = Field(default=0.001, ge=0.0, lt=1.0)
    benchmark_symbol: str = Field(default="BTC-USD", min_length=1, max_length=32)
    risk_free_rate: float = Field(default=0.02, ge=0.0, le=1.0)


class BotCredentials(BaseModel):
    """Minimal credentials for managing instance configs."""

    chain_id: str = Field(default="dydx-testnet-4", min_length=1, max_length=64)
    address: str = Field(..., min_length=1, max_length=128)
    mnemonic: str = Field(..., min_length=1)


class TelegramConfig(BaseModel):
    """Shared Telegram notification settings for runtime-managed instances."""

    token: str = ""
    chat_id: str = ""


class BotInstanceConfig(BaseModel):
    """Bot instance configuration payload."""

    instance_id: str = Field(
        ..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )
    instance_name: Optional[str] = Field(
        None, description="Human-friendly instance name", max_length=255
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
    recovery_state: Optional[str] = (
        None  # "recovering", "degraded", "safeguarded", or None
    )
    recovery_reason: Optional[str] = None  # Why recovery state was activated

    def public_config(self) -> Dict[str, Any]:
        """Config view that is safe to return from the API.

        The signing mnemonic and the Telegram bot token never leave the
        process: they are dropped (not masked, so a client cannot round-trip a
        placeholder back as a credential) and replaced by presence flags.
        """
        config = self.config.model_dump()
        credentials = config.get("credentials")
        if isinstance(credentials, dict):
            credentials["mnemonic_configured"] = bool(credentials.pop("mnemonic", ""))
        telegram = config.get("telegram")
        if isinstance(telegram, dict):
            telegram["token_configured"] = bool(telegram.pop("token", ""))
        return config

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
            config=self.public_config(),
            trading_stats=self.trading_stats,
        )
