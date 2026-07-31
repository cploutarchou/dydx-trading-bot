"""Shared serializers for realtime API/WebSocket payloads."""

from __future__ import annotations

from typing import Any, Dict, Optional


def _float_or_none(value: Any) -> Optional[float]:
    return float(value) if value is not None else None


def _float_or_zero(value: Any) -> float:
    return float(value) if value is not None else 0.0


def serialize_realtime_position(
    position: Any, include_updated_at: bool = False
) -> Dict[str, Any]:
    """Serialize an open position for realtime payloads."""
    payload: Dict[str, Any] = {
        "position_id": position.position_id,
        "pair1": position.pair1,
        "pair2": position.pair2,
        "status": position.status.value,
        "side1": position.side1,
        "side2": position.side2,
        "entry_price1": _float_or_none(position.entry_price1),
        "entry_price2": _float_or_none(position.entry_price2),
        "current_price1": _float_or_none(position.current_price1),
        "current_price2": _float_or_none(position.current_price2),
        "current_size1": _float_or_zero(position.current_size1),
        "current_size2": _float_or_zero(position.current_size2),
        "unrealized_pnl": _float_or_zero(position.unrealized_pnl),
        "unrealized_pnl_pct": _float_or_zero(position.unrealized_pnl_pct),
        "z_score_entry": _float_or_none(position.z_score_entry),
        "z_score_current": _float_or_none(position.z_score_current),
        "entered_at": position.entry_time.isoformat(),
    }

    if include_updated_at:
        payload["updated_at"] = (
            position.updated_at.isoformat() if position.updated_at else None
        )

    return payload


def serialize_market_core(
    market: Any, include_volatility: bool = True
) -> Dict[str, Any]:
    """Serialize common market snapshot fields."""
    payload: Dict[str, Any] = {
        "symbol": market.symbol,
        "current_price": float(market.current_price),
        "bid_price": _float_or_none(market.bid_price),
        "ask_price": _float_or_none(market.ask_price),
        "volume_24h": _float_or_none(market.volume_24h),
    }

    if include_volatility:
        payload["volatility_24h"] = _float_or_none(market.volatility_24h)

    return payload


def serialize_stats_risk_fields(stats: Any) -> Dict[str, float]:
    """Serialize shared risk/statistics fields used by API and realtime broadcaster."""
    return {
        "daily_win_rate": _float_or_zero(getattr(stats, "daily_win_rate", None)),
        "max_drawdown": _float_or_zero(getattr(stats, "max_drawdown_session", None)),
        "current_drawdown": _float_or_zero(getattr(stats, "current_drawdown", None)),
    }
