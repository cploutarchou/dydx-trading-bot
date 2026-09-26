"""Arbitrage runtime visibility + settings endpoints.

Extracted from ``src/api/server.py`` (monolith-breakup Phase 4). The 5
``/api/v1/arbitrage/*`` routes (improvement metrics, runtime settings get/put,
pair priority, opportunity explainability) + the ``ArbitrageRuntimeSettingsRequest``
model now live here. All routes require ``get_current_active_user``.

Auth, middleware, and global exception handlers apply automatically because the
router is mounted on the canonical app via ``app.include_router``. ``server.py``
re-imports ``ArbitrageRuntimeSettingsRequest`` so the input-validation tests keep
resolving.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.api.responses import api_response
from src.infrastructure.domain.cointegration_storage import pair_storage
from src.infrastructure.domain.models.auth_models import User
from src.middleware.auth_middleware import get_current_active_user
from src.trading.arbitrage_observability import snapshot_metrics
from src.trading.arbitrage_runtime_config import (
    get_feature_flags,
    get_runtime_settings,
    is_pair_priority_engine_enabled,
    update_runtime_settings,
)
from src.trading.pair_priority import prioritize_pairs, score_pair


class ArbitrageRuntimeSettingsRequest(BaseModel):
    """Validated body for arbitrage runtime-settings updates.

    Unknown keys are ignored so existing clients that send unrelated fields
    keep working; the downstream ``update_runtime_settings`` still clamps the
    typed values it recognizes.
    """

    model_config = ConfigDict(extra="ignore")

    ARBITRAGE_IMPROVEMENTS_ENABLED: Optional[bool] = None
    PAIR_PRIORITY_ENGINE_ENABLED: Optional[bool] = None
    POLYMARKET_SIGNALS_ENABLED: Optional[bool] = None
    DEFILLAMA_SIGNALS_ENABLED: Optional[bool] = None
    NEWS_SIGNALS_ENABLED: Optional[bool] = None
    AUTO_EXECUTION_CHANGES_ENABLED: Optional[bool] = None
    PAIR_PRIORITY_MAX_PAIRS: Optional[int] = Field(default=None, ge=0)
    PAIR_PRIORITY_STALE_SECONDS: Optional[float] = Field(default=None, ge=0.0)
    # Cost + funding entry gate. Out-of-range values are clamped by
    # ``update_runtime_settings`` (see ``src/trading/entry_cost_gate.py``).
    COST_GATE_ENABLED: Optional[bool] = None
    COST_GATE_EDGE_MULTIPLE: Optional[float] = Field(default=None, ge=0.0)
    COST_GATE_TAKER_FEE: Optional[float] = Field(default=None, ge=0.0)
    COST_GATE_SLIPPAGE_BPS: Optional[float] = Field(default=None, ge=0.0)
    FUNDING_SAME_SIDE_THRESHOLD: Optional[float] = Field(default=None, ge=0.0)


router = APIRouter(prefix="/api/v1/arbitrage")


@router.get("/improvement-metrics")
async def get_arbitrage_improvement_metrics(
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    _ = current_user
    return api_response(
        success=True,
        data=snapshot_metrics(
            {
                "feature_flags": get_feature_flags(),
                "runtime_settings": get_runtime_settings(),
            }
        ),
        message="Arbitrage improvement metrics retrieved",
    )


@router.get("/runtime-settings")
async def get_arbitrage_runtime_settings(
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    _ = current_user
    settings = get_runtime_settings()
    return api_response(
        success=True,
        data={"settings": settings, "feature_flags": get_feature_flags()},
        message="Arbitrage runtime settings retrieved",
    )


@router.put("/runtime-settings")
async def update_arbitrage_runtime_settings(
    payload: ArbitrageRuntimeSettingsRequest,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    _ = current_user
    # Only forward keys the caller actually set so unset fields keep their
    # current runtime value (matches prior ``payload or {}`` semantics).
    settings = update_runtime_settings(payload.model_dump(exclude_unset=True))
    return api_response(
        success=True,
        data={"settings": settings, "feature_flags": get_feature_flags()},
        message="Arbitrage runtime settings updated",
    )


@router.get("/pair-priority")
async def get_arbitrage_pair_priority(
    limit: int = 25,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    _ = current_user
    safe_limit = max(1, min(int(limit or 25), 100))
    pairs = pair_storage.load_pairs()
    pair_priority_enabled = is_pair_priority_engine_enabled()
    if pair_priority_enabled:
        ranked_pairs, scores = prioritize_pairs(pairs, max_pairs=safe_limit)
    else:
        ranked_pairs = pairs[:safe_limit]
        scores = [score_pair(pair) for pair in ranked_pairs]
    ranked_lookup = {score.pair: score for score in scores}
    data = []
    for pair in ranked_pairs:
        label = f"{pair.base_market}/{pair.quote_market}"
        score = ranked_lookup.get(label)
        data.append(
            {
                "pair": label,
                "base_market": pair.base_market,
                "quote_market": pair.quote_market,
                "score": score.score if score else 0.0,
                "components": score.components if score else {},
                "explanation": score.explanation if score else [],
                "enabled": pair_priority_enabled,
            }
        )
    return api_response(
        success=True,
        data={"pairs": data, "count": len(data), "enabled": pair_priority_enabled},
        message="Arbitrage pair priority retrieved",
    )


@router.get("/opportunity/{opportunity_id}/explain")
async def get_arbitrage_opportunity_explain(
    opportunity_id: str,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    _ = current_user
    metrics = snapshot_metrics(
        {
            "feature_flags": get_feature_flags(),
            "runtime_settings": get_runtime_settings(),
        }
    )
    rejection_reasons = metrics.get("rejection_reasons", {})
    normalized_id = str(opportunity_id or "").strip().lower().replace(" ", "_")

    matched_reason = None
    if isinstance(rejection_reasons, dict) and normalized_id in rejection_reasons:
        matched_reason = {
            "reason": normalized_id,
            "count": rejection_reasons.get(normalized_id, 0),
        }

    top_rejections: List[Dict[str, Any]] = []
    if isinstance(rejection_reasons, dict):
        sorted_reasons = sorted(
            rejection_reasons.items(),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        top_rejections = [
            {"reason": str(reason), "count": float(count)}
            for reason, count in sorted_reasons[:10]
        ]

    return api_response(
        success=True,
        data={
            "opportunity_id": opportunity_id,
            "matched_rejection_reason": matched_reason,
            "top_rejection_reasons": top_rejections,
            "counters": metrics.get("counters", {}),
            "feature_flags": metrics.get("feature_flags", {}),
            "runtime_settings": metrics.get("runtime_settings", {}),
            "explainability_scope": "runtime_diagnostics",
            "note": (
                "Per-opportunity historical explain payloads are not persisted yet; "
                "this endpoint provides current runtime diagnostics and rejection trends."
            ),
        },
        message="Arbitrage opportunity explainability retrieved",
    )
