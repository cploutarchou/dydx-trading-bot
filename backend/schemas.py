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
