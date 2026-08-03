"""Backtest response/serialization DTOs and the linregress slope helper.

Extracted from :mod:`src.infrastructure.use_cases.service_backtest` (Phase 1 of the
backtest-service decomposition). These types are intentionally underscore-prefixed
(service-internal) and re-imported by ``service_backtest`` so every existing
bare-name reference keeps resolving to the same class/function object.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from pydantic import BaseModel
from scipy.stats import linregress


def _linregress_slope(x: Any, y: Any) -> float:
    """Return slope from scipy.stats.linregress across typing/runtime variants."""
    result = linregress(x, y)
    slope_value: Any = getattr(result, "slope", None)
    if slope_value is None:
        if isinstance(result, tuple) and result:
            slope_value = result[0]
        else:
            raise ValueError("Unable to extract slope from linregress result")

    if isinstance(slope_value, tuple):
        if not slope_value:
            raise ValueError("Unable to extract slope from empty linregress tuple")
        slope_value = slope_value[0]

    return float(cast(Any, slope_value))


class _BacktestRunStatus(BaseModel):
    run_id: str
    status: str
    progress_pct: float
    updated_at: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    finished_at: Optional[str] = None
    deadline_at: Optional[str] = None
    timeout_seconds: Optional[float] = None
    last_heartbeat_at: Optional[str] = None
    heartbeat_age_seconds: Optional[float] = None
    cancellable: bool = False
    pausable: bool = False
    resumable: bool = False
    restartable: bool = False
    control_status: Optional[str] = None
    control_action: Optional[str] = None
    worker_backend: Optional[str] = None
    worker_task_id: Optional[str] = None
    request: Optional[Dict[str, Any]] = None
    request_available: bool = False
    current_pair: Optional[str] = None
    current_task: Optional[str] = None
    error: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    traceback: Optional[str] = None
    result_location: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    strategy_id: Optional[int] = None
    bot_id: Optional[str] = None
    source: Optional[str] = None
    selected_pairs: List[str] = []
    metadata: Dict[str, Any] = {}
    worker_hostname: Optional[str] = None
    retry_count: Optional[int] = None


class _BacktestTrade(BaseModel):
    trade_id: str
    market_1: str
    market_2: str
    entry_timestamp: str
    exit_timestamp: str
    entry_zscore: float
    exit_zscore: float
    entry_price_m1: float
    exit_price_m1: float
    entry_price_m2: float
    exit_price_m2: float
    hedge_ratio: float
    pnl_usd: float
    pnl_pct: float
    duration_hours: float
    win: bool


class _BacktestRunDetails(BaseModel):
    run_id: str
    name: str
    status: str
    total_pnl: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_trades: int
    created_at: str
    updated_at: str
    profit_factor: float = 0.0
    start_date: str = ""
    end_date: str = ""
    progress_pct: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    finished_at: Optional[str] = None
    deadline_at: Optional[str] = None
    timeout_seconds: Optional[float] = None
    last_heartbeat_at: Optional[str] = None
    heartbeat_age_seconds: Optional[float] = None
    cancellable: bool = False
    pausable: bool = False
    resumable: bool = False
    restartable: bool = False
    control_status: Optional[str] = None
    control_action: Optional[str] = None
    worker_backend: Optional[str] = None
    worker_task_id: Optional[str] = None
    current_pair: Optional[str] = None
    current_task: Optional[str] = None
    error: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    traceback: Optional[str] = None
    result_location: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    strategy_id: Optional[int] = None
    bot_id: Optional[str] = None
    source: Optional[str] = None
    selected_pairs: List[str] = []
    metadata: Dict[str, Any] = {}
    worker_hostname: Optional[str] = None
    retry_count: Optional[int] = None
    artifact_refs: Dict[str, str] = {}
    analytics_rows_written: int = 0


class _BacktestRunList(BaseModel):
    runs: List[Dict[str, Any]]
    total: int
