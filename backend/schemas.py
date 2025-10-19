"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# ============================================================================
# Backtest Trade Schemas
# ============================================================================


class BacktestTradeBase(BaseModel):
    """Base trade schema with common fields."""

    market_1: str
    market_2: str
    entry_timestamp: datetime
    entry_price_1: float
    entry_price_2: float
    entry_z_score: float
    side_1: str
    side_2: str
    size_1: float
    size_2: float
    hedge_ratio: float
    transaction_fee: float
    slippage: float


class BacktestTradeCreate(BacktestTradeBase):
    """Schema for creating a trade."""

    trade_id: str
    run_id_fk: int


class BacktestTradeUpdate(BaseModel):
    """Schema for updating trade with exit details."""

    exit_timestamp: datetime
    exit_price_1: float
    exit_price_2: float
    exit_z_score: float
    pnl: float
    pnl_pct: float
    duration_hours: float


class BacktestTradeResponse(BacktestTradeBase):
    """Schema for trade API response."""

    id: int
    trade_id: str
    run_id_fk: int
    exit_timestamp: Optional[datetime] = None
    exit_price_1: Optional[float] = None
    exit_price_2: Optional[float] = None
    exit_z_score: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    duration_hours: Optional[float] = None

    class Config:
        from_attributes = True


# ============================================================================
# Backtest Position Schemas
# ============================================================================


class BacktestPositionBase(BaseModel):
    """Base position schema."""

    market_1: str
    market_2: str
    status: str
    entry_timestamp: datetime
    entry_price_1: float
    entry_price_2: float
    entry_z_score: float
    size_1: float
    size_2: float
    side_1: str
    side_2: str
    hedge_ratio: float


class BacktestPositionCreate(BacktestPositionBase):
    """Schema for creating a position."""

    position_id: str
    run_id_fk: int


class BacktestPositionUpdate(BaseModel):
    """Schema for updating position status."""

    status: str
    current_price_1: Optional[float] = None
    current_price_2: Optional[float] = None
    current_z_score: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    close_timestamp: Optional[datetime] = None
    realized_pnl: Optional[float] = None


class BacktestPositionResponse(BacktestPositionBase):
    """Schema for position API response."""

    id: int
    position_id: str
    run_id_fk: int
    close_timestamp: Optional[datetime] = None
    current_price_1: Optional[float] = None
    current_price_2: Optional[float] = None
    current_z_score: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None

    class Config:
        from_attributes = True


# ============================================================================
# Bot Settings Schemas
# ============================================================================


class SettingFieldConfig(BaseModel):
    """Configuration for a single setting field in UI."""

    key: str
    label: str
    description: Optional[str] = None
    value_type: str  # string, float, int, boolean, json
    value: Any
    default_value: Optional[Any] = None
    required: bool = False
    options: Optional[List[str]] = None  # For select fields
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    placeholder: Optional[str] = None


class SettingSectionConfig(BaseModel):
    """Configuration for a settings section."""

    section: str
    title: str
    description: Optional[str] = None
    fields: List[SettingFieldConfig]


class SettingsSchemaResponse(BaseModel):
    """Complete settings schema for UI generation."""

    sections: List[SettingSectionConfig]


class BotSettingBase(BaseModel):
    """Base setting schema."""

    section: str
    key: str
    value: str  # JSON serialized
    value_type: str
    description: Optional[str] = None


class BotSettingCreate(BotSettingBase):
    """Schema for creating a setting."""

    default_value: Optional[str] = None


class BotSettingUpdate(BaseModel):
    """Schema for updating a setting."""

    value: str
    version: Optional[int] = None


class BotSettingResponse(BotSettingBase):
    """Schema for setting API response."""

    id: int
    default_value: Optional[str] = None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BotSettingsSectionResponse(BaseModel):
    """Settings grouped by section."""

    section: str
    settings: List[BotSettingResponse]


class BotSettingsResponse(BaseModel):
    """All bot settings grouped by section."""

    sections: List[BotSettingsSectionResponse]


# ============================================================================
# Batch Update Schemas
# ============================================================================


class BotSettingBatchUpdate(BaseModel):
    """Batch update multiple settings."""

    updates: Dict[str, Any]  # {section.key: value, ...}


# ============================================================================
# Analysis Schemas
# ============================================================================


class BacktestAnalysisSummary(BaseModel):
    """Summary statistics for backtest analysis."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_trade_pnl: float
    best_trade: float
    worst_trade: float
    avg_duration_hours: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None


class BacktestTradeListResponse(BaseModel):
    """List of trades from a backtest."""

    run_id: int
    total: int
    trades: List[BacktestTradeResponse]


class BacktestPositionListResponse(BaseModel):
    """List of positions from a backtest."""

    run_id: int
    total: int
    positions: List[BacktestPositionResponse]


# ============================================================================
# Backtest Strategy Schemas
# ============================================================================


class BacktestStrategyBase(BaseModel):
    """Base strategy schema with common fields."""

    name: str
    description: Optional[str] = None
    category: str = "custom"
    is_public: bool = False
    zscore_threshold: float = 1.5
    stats_window: int = 21
    max_half_life: int = 24
    usd_per_trade: float = 10.0
    usd_min_collateral: float = 100.0
    close_at_zscore_cross: bool = True
    find_cointegrated_pairs: bool = True
    manage_exits: bool = True
    place_trades: bool = True
    abort_all_positions: bool = False
    max_positions: int = 5
    max_drawdown_pct: float = 15.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 5.0
    trailing_stop_pct: float = 1.0
    rebalance_interval_hours: int = 24
    position_timeout_hours: int = 72


class BacktestStrategyCreate(BacktestStrategyBase):
    """Schema for creating a new strategy."""

    pass


class BacktestStrategyUpdate(BaseModel):
    """Schema for updating a strategy."""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_public: Optional[bool] = None
    zscore_threshold: Optional[float] = None
    stats_window: Optional[int] = None
    max_half_life: Optional[int] = None
    usd_per_trade: Optional[float] = None
    usd_min_collateral: Optional[float] = None
    close_at_zscore_cross: Optional[bool] = None
    find_cointegrated_pairs: Optional[bool] = None
    manage_exits: Optional[bool] = None
    place_trades: Optional[bool] = None
    abort_all_positions: Optional[bool] = None
    max_positions: Optional[int] = None
    max_drawdown_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    rebalance_interval_hours: Optional[int] = None
    position_timeout_hours: Optional[int] = None


class BacktestStrategyResponse(BacktestStrategyBase):
    """Schema for strategy API response."""

    id: int
    user_id: int
    is_default: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BacktestStrategyListResponse(BaseModel):
    """List of strategies."""

    total: int
    skip: int
    limit: int
    strategies: List[BacktestStrategyResponse]


class BacktestStrategyUsageStats(BaseModel):
    """Usage statistics for a strategy."""

    strategy_id: int
    total_runs: int
    completed_runs: int
    failed_runs: int
    avg_pnl: float
    success_rate: float


class BacktestStrategyWithStats(BacktestStrategyResponse):
    """Strategy with usage statistics."""

    usage_stats: Optional[BacktestStrategyUsageStats] = None


# ============================================================================
# Backtest Run Schemas (Enhanced with Strategy Support)
# ============================================================================


class BacktestRunBase(BaseModel):
    """Base backtest run schema."""

    run_id: str
    start_date: str
    end_date: str
    num_pairs: int
    total_markets: int
    strategy_id: Optional[int] = None


class BacktestRunResponse(BacktestRunBase):
    """Schema for backtest run API response."""

    id: int
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    total_trades: int
    profitable_trades: int
    losing_trades: int
    win_rate: Optional[float] = None
    total_pnl: float
    total_pnl_usd: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    strategy: Optional[BacktestStrategyResponse] = None

    class Config:
        from_attributes = True
