"""Strategy CRUD endpoints + the strategy store.

Extracted from ``src/api/server.py`` (monolith-breakup Phase 3). The strategy
request models, the DB-backed strategy store, and the 8 ``/api/v1/strategies/*``
routes now live here. ``list_public_strategies`` is intentionally unauthenticated
(public catalog); the other 7 require ``get_current_active_user``.

Auth, middleware, and global exception handlers apply automatically because the
router is mounted on the canonical app via ``app.include_router``. ``server.py``
re-imports ``StrategyRequest`` / ``StrategyVersionRevertRequest`` /
``InMemoryStrategyStore`` so existing call sites (and tests) keep resolving.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from src.api.responses import api_response
from src.infrastructure.database import db
from src.infrastructure.domain.models.auth_models import User
from src.infrastructure.persistence.repository import UnitOfWork
from src.middleware.auth_middleware import get_current_active_user

# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #


class StrategyRequest(BaseModel):
    """UI-compatible strategy payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Balanced Mean Reversion",
                "category": "pairs_trading",
                "description": "Strategy with liquidity-ranked pair selection",
                "resolution": "1HOUR",
                "zscore_threshold": 1.5,
                "stats_window": 21,
                "usd_per_trade": 10.0,
                "max_positions": 5,
                "pair_selection_mode": "liquidity",
            }
        }
    )

    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(default="pairs_trading", min_length=1, max_length=64)
    description: str = Field(default="", max_length=2000)
    is_public: bool = False
    user_id: int = Field(default=1, ge=1)
    resolution: str = Field(default="1HOUR", min_length=1, max_length=16)
    candle_resolution: Optional[str] = Field(default=None, max_length=16)
    zscore_threshold: float = Field(default=1.5, gt=0.0)
    stats_window: int = Field(default=21, ge=2, le=2000)
    max_half_life: float = Field(default=24.0, ge=1.0, le=10000.0)
    usd_per_trade: float = Field(default=10.0, gt=0.0)
    usd_min_collateral: float = Field(default=100.0, ge=0.0)
    close_at_zscore_cross: bool = True
    find_cointegrated_pairs: bool = True
    manage_exits: bool = True
    place_trades: bool = True
    abort_all_positions: bool = False
    max_positions: int = Field(default=5, ge=0, le=100)
    # Enforced on live bots (drawdown halt, trailing stop): off unless set.
    max_drawdown_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    stop_loss_pct: float = Field(default=3.0, ge=0.0, le=100.0)
    take_profit_pct: float = Field(default=8.0, ge=0.0, le=1000.0)
    trailing_stop_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    rebalance_interval_hours: int = Field(default=24, ge=0, le=8760)
    position_timeout_hours: int = Field(default=72, ge=0, le=8760)
    initial_amount: float = Field(default=1000.0, gt=0.0)
    starting_balance: float = Field(default=1000.0, gt=0.0)
    transaction_fee: float = Field(default=0.0005, ge=0.0, lt=1.0)
    slippage: float = Field(default=0.001, ge=0.0, lt=1.0)
    max_history_days: int = Field(default=90, ge=1, le=36500)
    benchmark_symbol: str = Field(default="BTC-USD", min_length=1, max_length=32)
    risk_free_rate: float = Field(default=0.02, ge=0.0, le=1.0)
    pair_selection_mode: str = Field(default="liquidity", min_length=1, max_length=64)


class StrategyVersionRevertRequest(BaseModel):
    """Placeholder body for strategy version revert."""


# --------------------------------------------------------------------------- #
# Strategy store (DB-backed)
# --------------------------------------------------------------------------- #


class InMemoryStrategyStore:
    """DB-backed strategy storage with the same interface as the prior in-memory store."""

    @classmethod
    def list(cls, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.list(skip=skip, limit=limit)
        finally:
            session.close()

    @classmethod
    def list_public(cls) -> Dict[str, Any]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.list_public()
        finally:
            session.close()

    @classmethod
    def get(cls, strategy_id: int) -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.get(strategy_id)
        finally:
            session.close()

    @classmethod
    def create(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.create(payload, note="Initial version")
        finally:
            session.close()

    @classmethod
    def update(
        cls, strategy_id: int, payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.update(strategy_id, payload, note="Updated strategy")
        finally:
            session.close()

    @classmethod
    def delete(cls, strategy_id: int) -> bool:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.delete(strategy_id)
        finally:
            session.close()

    @classmethod
    def versions(cls, strategy_id: int) -> List[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.versions(strategy_id)
        finally:
            session.close()

    @classmethod
    def revert(cls, strategy_id: int, version_id: int) -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.revert(strategy_id, version_id)
        finally:
            session.close()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

router = APIRouter(prefix="/api/v1/strategies", tags=["Strategies"])


@router.get("")
async def list_strategies(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """List stored strategies for the UI."""
    del current_user
    # The store is sync/session-owning; run it off the event loop.
    data = await run_in_threadpool(InMemoryStrategyStore.list, skip=skip, limit=limit)
    return api_response(
        success=True,
        data=data,
        message=f"Retrieved {len(data['strategies'])} strategies",
    )


@router.get("/public")
async def list_public_strategies() -> JSONResponse:
    """List public strategies (no auth — public catalog)."""
    data = await run_in_threadpool(InMemoryStrategyStore.list_public)
    return api_response(
        success=True,
        data=data,
        message=f"Retrieved {len(data['strategies'])} public strategies",
    )


@router.post("")
async def create_strategy(
    request: StrategyRequest,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Create a strategy."""
    del current_user
    strategy = await run_in_threadpool(
        InMemoryStrategyStore.create, request.model_dump()
    )
    return api_response(
        success=True,
        data=strategy,
        message=f"Strategy '{strategy['name']}' created successfully",
    )


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Get one strategy."""
    del current_user
    strategy = await run_in_threadpool(InMemoryStrategyStore.get, strategy_id)
    if not strategy:
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy retrieved")


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: int,
    request: StrategyRequest,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Update one strategy."""
    del current_user
    strategy = await run_in_threadpool(
        InMemoryStrategyStore.update, strategy_id, request.model_dump()
    )
    if not strategy:
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy updated")


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Delete one strategy."""
    del current_user
    if not await run_in_threadpool(InMemoryStrategyStore.delete, strategy_id):
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, message="Strategy deleted")


@router.get("/{strategy_id}/versions")
async def get_strategy_versions(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Get in-memory version history for a strategy."""
    del current_user
    versions = await run_in_threadpool(InMemoryStrategyStore.versions, strategy_id)
    return api_response(
        success=True,
        data={"versions": versions},
        message="Strategy version history retrieved",
    )


@router.post("/{strategy_id}/versions/{version_id}/revert")
async def revert_strategy_version(
    strategy_id: int,
    version_id: int,
    request: StrategyVersionRevertRequest,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Revert a strategy to a prior stored version."""
    del request, current_user
    strategy = await run_in_threadpool(
        InMemoryStrategyStore.revert, strategy_id, version_id
    )
    if not strategy:
        return api_response(
            success=False,
            message="Strategy version not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy reverted")
