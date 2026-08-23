"""Realtime bot HTTP queries and bot/strategy WebSocket adapters."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.realtime_serializers import (
    serialize_market_core,
    serialize_realtime_position,
    serialize_stats_risk_fields,
)
from src.api.responses import api_response
from src.api.websocket_server import (
    WebSocketServer,
    build_strategy_snapshot_message,
    manager,
)
from src.infrastructure.database import db
from src.infrastructure.db_offload import run_db
from src.infrastructure.domain.models.auth_models import User
from src.infrastructure.persistence.repository import UnitOfWork
from src.infrastructure.persistence.repository_realtime import UnitOfWorkRealtime
from src.middleware.auth_middleware import (
    authenticate_bearer_token,
    get_current_active_user,
    is_auth_bypass_enabled,
)
from src.shared.time_utils import utc_now_iso

BotManagerProvider = Callable[[], Any]
CoreUnitOfWorkFactory = Callable[[Any], Any]
RealtimeUnitOfWorkFactory = Callable[[Any], Any]
AuthBypassProvider = Callable[[], bool]
BearerAuthenticator = Callable[[str, Any], Any]


def _missing_bot_manager() -> None:
    return None


def _default_core_uow_factory(session: Any) -> Any:
    return UnitOfWork(session)


def _default_realtime_uow_factory(session: Any) -> Any:
    return UnitOfWorkRealtime(session)


_bot_manager_provider: BotManagerProvider = _missing_bot_manager
_core_uow_factory: CoreUnitOfWorkFactory = _default_core_uow_factory
_realtime_uow_factory: RealtimeUnitOfWorkFactory = _default_realtime_uow_factory
_auth_bypass_provider: AuthBypassProvider = is_auth_bypass_enabled
_bearer_authenticator: BearerAuthenticator = authenticate_bearer_token


def configure_bot_realtime(
    *,
    bot_manager_provider: BotManagerProvider,
    core_uow_factory: CoreUnitOfWorkFactory,
    realtime_uow_factory: RealtimeUnitOfWorkFactory,
    auth_bypass_provider: AuthBypassProvider,
    bearer_authenticator: BearerAuthenticator,
) -> None:
    """Connect this router to canonical server-owned runtime dependencies."""

    global _bot_manager_provider
    global _core_uow_factory
    global _realtime_uow_factory
    global _auth_bypass_provider
    global _bearer_authenticator

    _bot_manager_provider = bot_manager_provider
    _core_uow_factory = core_uow_factory
    _realtime_uow_factory = realtime_uow_factory
    _auth_bypass_provider = auth_bypass_provider
    _bearer_authenticator = bearer_authenticator


def _resolve_realtime_bot_id(session: Any, bot_instance_id: str) -> Optional[int]:
    raw_id = str(bot_instance_id or "").strip()
    if not raw_id:
        return None
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        pass

    try:
        uow_core = _core_uow_factory(session)
        bot = uow_core.bots.get_by_instance_id(raw_id)
        return int(bot.id) if bot else None
    except Exception as exc:
        logger.warning(
            "Failed to resolve realtime bot id for {}: {}",
            raw_id,
            exc,
        )
        return None


router = APIRouter()


def _get_current_positions_sync(bot_instance_id: str) -> JSONResponse:
    """Load open positions off the event loop; owns its own DB session."""
    session = None
    try:
        session = db.get_session()
        uow = _realtime_uow_factory(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        positions = uow.positions.get_open_positions(bot_id_int)

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "positions": [
                    serialize_realtime_position(position, include_updated_at=True)
                    for position in positions
                ],
                "count": len(positions),
            },
        )
    finally:
        if session is not None:
            session.close()


@router.get("/api/v1/bots/{bot_instance_id}/positions/current")
async def get_current_positions(
    bot_instance_id: str,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Get all currently open positions for a bot"""
    del current_user
    try:
        return await run_db(_get_current_positions_sync, bot_instance_id)
    except Exception as exc:
        logger.error(f"Error getting positions: {exc}")
        return api_response(
            success=False,
            message=f"Error: {str(exc)}",
            status_code=500,
        )


def _get_position_sync(bot_instance_id: str, position_id: str) -> JSONResponse:
    """Load a single position off the event loop; owns its own DB session."""
    session = None
    try:
        session = db.get_session()
        uow = _realtime_uow_factory(session)

        resolved_bot_id = _resolve_realtime_bot_id(session, bot_instance_id)
        if resolved_bot_id is None:
            return api_response(
                success=False,
                message="Bot instance not found",
                status_code=404,
            )

        position = uow.positions.get_position_by_id(position_id)

        if not position or position.bot_instance_id != resolved_bot_id:
            return api_response(
                success=False,
                message="Position not found",
                status_code=404,
            )

        return api_response(
            success=True,
            data={
                "position_id": position.position_id,
                "pair1": position.pair1,
                "pair2": position.pair2,
                "side1": position.side1,
                "side2": position.side2,
                "status": position.status.value,
                "entry_price1": float(position.entry_price1 or 0.0),
                "entry_price2": float(position.entry_price2 or 0.0),
                "current_price1": float(position.current_price1 or 0.0),
                "current_price2": float(position.current_price2 or 0.0),
                "current_size1": float(position.current_size1 or 0.0),
                "current_size2": float(position.current_size2 or 0.0),
                "entry_cost": float(position.entry_cost or 0.0),
                "current_value": float(position.current_value or 0.0),
                "unrealized_pnl": float(position.unrealized_pnl),
                "unrealized_pnl_pct": float(position.unrealized_pnl_pct),
                "realized_pnl": (
                    float(position.realized_pnl) if position.realized_pnl else 0
                ),
                "z_score_entry": (
                    float(position.z_score_entry) if position.z_score_entry else None
                ),
                "z_score_current": (
                    float(position.z_score_current)
                    if position.z_score_current
                    else None
                ),
                "hedge_ratio": (
                    float(position.hedge_ratio) if position.hedge_ratio else None
                ),
                "correlation": (
                    float(position.correlation) if position.correlation else None
                ),
                "half_life": (
                    float(position.half_life) if position.half_life else None
                ),
                "entered_at": position.entry_time.isoformat(),
                "updated_at": (
                    position.updated_at.isoformat() if position.updated_at else None
                ),
                "closed_at": (
                    position.closed_at.isoformat() if position.closed_at else None
                ),
            },
        )
    finally:
        if session is not None:
            session.close()


@router.get("/api/v1/bots/{bot_instance_id}/positions/{position_id}")
async def get_position(
    bot_instance_id: str,
    position_id: str,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Get specific position details"""
    del current_user
    try:
        return await run_db(_get_position_sync, bot_instance_id, position_id)
    except Exception as exc:
        logger.error(f"Error getting position: {exc}")
        return api_response(
            success=False,
            message=f"Error: {str(exc)}",
            status_code=500,
        )


def _get_market_data_sync(bot_instance_id: str) -> JSONResponse:
    """Load market data off the event loop; owns its own DB session."""
    session = None
    try:
        session = db.get_session()
        uow = _realtime_uow_factory(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        market_data = uow.market_data.get_all_market_data(bot_id_int)

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "market_data": [
                    {
                        **serialize_market_core(market, include_volatility=True),
                        "rsi": float(market.rsi) if market.rsi else None,
                        "macd": float(market.macd) if market.macd else None,
                        "moving_avg_20": (
                            float(market.moving_avg_20)
                            if market.moving_avg_20
                            else None
                        ),
                        "moving_avg_50": (
                            float(market.moving_avg_50)
                            if market.moving_avg_50
                            else None
                        ),
                        "funding_rate": (
                            float(market.funding_rate) if market.funding_rate else None
                        ),
                        "updated_at": (
                            market.timestamp.isoformat() if market.timestamp else None
                        ),
                    }
                    for market in market_data
                ],
                "count": len(market_data),
            },
        )
    finally:
        if session is not None:
            session.close()


@router.get("/api/v1/bots/{bot_instance_id}/market-data")
async def get_market_data(
    bot_instance_id: str,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Get latest market data for all symbols tracked by bot"""
    del current_user
    try:
        return await run_db(_get_market_data_sync, bot_instance_id)
    except Exception as exc:
        logger.error(f"Error getting market data: {exc}")
        return api_response(
            success=False,
            message=f"Error: {str(exc)}",
            status_code=500,
        )


def _get_realtime_stats_sync(bot_instance_id: str) -> JSONResponse:
    """Load realtime stats off the event loop; owns its own DB session."""
    session = None
    try:
        session = db.get_session()
        uow = _realtime_uow_factory(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        stats = uow.stats.get_stats(bot_id_int)

        if not stats:
            return api_response(
                success=True,
                data={
                    "bot_instance_id": bot_instance_id,
                    "stats": {
                        "total_open_positions": 0,
                        "total_unrealized_pnl": 0,
                        "total_unrealized_pnl_pct": 0,
                        "daily_pnl": 0,
                        "daily_pnl_pct": 0,
                        "daily_trades_opened": 0,
                        "daily_trades_closed": 0,
                        "daily_wins": 0,
                        "daily_losses": 0,
                        "daily_win_rate": 0,
                        "max_drawdown": 0,
                        "current_drawdown": 0,
                    },
                },
            )

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "stats": {
                    "total_open_positions": stats.total_open_positions,
                    "total_unrealized_pnl": float(stats.total_unrealized_pnl),
                    "total_unrealized_pnl_pct": float(stats.total_unrealized_pnl_pct),
                    "daily_pnl": float(stats.daily_pnl),
                    "daily_pnl_pct": float(stats.daily_pnl_pct),
                    "daily_trades_opened": stats.daily_trades_opened,
                    "daily_trades_closed": stats.daily_trades_closed,
                    "daily_wins": (
                        stats.daily_wins if hasattr(stats, "daily_wins") else 0
                    ),
                    "daily_losses": (
                        stats.daily_losses if hasattr(stats, "daily_losses") else 0
                    ),
                    **serialize_stats_risk_fields(stats),
                    "var_95": float(stats.var_95) if stats.var_95 else None,
                    "avg_trade_duration": (
                        stats.avg_trade_duration_seconds
                        if hasattr(stats, "avg_trade_duration_seconds")
                        else None
                    ),
                    "is_healthy": (
                        stats.is_healthy if hasattr(stats, "is_healthy") else True
                    ),
                    "updated_at": (
                        stats.updated_at.isoformat()
                        if hasattr(stats, "updated_at") and stats.updated_at
                        else None
                    ),
                },
            },
        )
    finally:
        if session is not None:
            session.close()


@router.get("/api/v1/bots/{bot_instance_id}/realtime-stats")
async def get_realtime_stats(
    bot_instance_id: str,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Get real-time bot statistics"""
    del current_user
    try:
        return await run_db(_get_realtime_stats_sync, bot_instance_id)
    except Exception as exc:
        logger.error(f"Error getting stats: {exc}")
        return api_response(
            success=False,
            message=f"Error: {str(exc)}",
            status_code=500,
        )


def _get_alerts_sync(bot_instance_id: str, limit: int) -> JSONResponse:
    """Load recent alerts off the event loop; owns its own DB session."""
    session = None
    try:
        session = db.get_session()
        uow = _realtime_uow_factory(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        alerts = uow.alerts.get_unnotified_alerts(bot_id_int)
        # Limit to most recent
        alerts = alerts[:limit]

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "alerts": [
                    {
                        "id": alert.id,
                        "type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "notified": alert.notified,
                        "notified_via": (
                            alert.notified_via if alert.notified_via else {}
                        ),
                        "created_at": (
                            alert.timestamp.isoformat() if alert.timestamp else None
                        ),
                        "details": alert.details if alert.details else {},
                    }
                    for alert in alerts
                ],
                "count": len(alerts),
            },
        )
    finally:
        if session is not None:
            session.close()


@router.get("/api/v1/bots/{bot_instance_id}/alerts")
async def get_alerts(
    bot_instance_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Get recent alerts for a bot"""
    del current_user
    try:
        return await run_db(_get_alerts_sync, bot_instance_id, limit)
    except Exception as exc:
        logger.error(f"Error getting alerts: {exc}")
        return api_response(
            success=False,
            message=f"Error: {str(exc)}",
            status_code=500,
        )


def _get_position_history_sync(
    bot_instance_id: str, position_id: str, hours: int
) -> JSONResponse:
    """Load position history off the event loop; owns its own DB session."""
    session = None
    try:
        session = db.get_session()
        uow = _realtime_uow_factory(session)

        bot_id_int = _resolve_realtime_bot_id(session, bot_instance_id)
        if bot_id_int is None:
            return api_response(
                success=False,
                message=f"Bot instance '{bot_instance_id}' not found",
                status_code=404,
            )

        snapshots = uow.snapshots.get_position_history(position_id, hours=hours)

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "position_id": position_id,
                "hours": hours,
                "snapshots": [
                    {
                        "pair1": snapshot.pair1,
                        "pair2": snapshot.pair2,
                        "unrealized_pnl": float(snapshot.unrealized_pnl),
                        "unrealized_pnl_pct": float(snapshot.unrealized_pnl_pct),
                        "current_price1": (
                            float(snapshot.current_price1)
                            if snapshot.current_price1
                            else None
                        ),
                        "current_price2": (
                            float(snapshot.current_price2)
                            if snapshot.current_price2
                            else None
                        ),
                        "z_score": (
                            float(snapshot.z_score) if snapshot.z_score else None
                        ),
                        "timestamp": (
                            snapshot.timestamp.isoformat()
                            if snapshot.timestamp
                            else None
                        ),
                    }
                    for snapshot in snapshots
                ],
                "count": len(snapshots),
            },
        )
    finally:
        if session is not None:
            session.close()


@router.get("/api/v1/bots/{bot_instance_id}/position-history/{position_id}")
async def get_position_history(
    bot_instance_id: str,
    position_id: str,
    hours: int = 24,
    current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    """Get historical P&L snapshots for a position"""
    del current_user
    try:
        return await run_db(
            _get_position_history_sync, bot_instance_id, position_id, hours
        )
    except Exception as exc:
        logger.error(f"Error getting position history: {exc}")
        return api_response(
            success=False,
            message=f"Error: {str(exc)}",
            status_code=500,
        )


async def _authorize_websocket_connection(websocket: WebSocket) -> bool:
    """Validate websocket bearer token via Authorization header only."""
    if _auth_bypass_provider():
        return True

    auth_header = websocket.headers.get("authorization", "").strip()
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    # SECURITY: Query parameter tokens are intentionally ignored to prevent
    # credentials from leaking into proxy and access logs.
    if not token:
        await websocket.close(code=4401, reason="Missing websocket auth token")
        return False

    session = None
    try:
        session = db.get_session()
        _bearer_authenticator(token, session)
        return True
    except Exception:
        await websocket.close(code=4401, reason="Invalid websocket auth token")
        return False
    finally:
        if session is not None:
            session.close()


@router.websocket("/api/v1/bots/{bot_instance_id}/alerts/live")
async def websocket_alerts(websocket: WebSocket, bot_instance_id: str) -> None:
    """WebSocket endpoint for live alerts"""
    if not await _authorize_websocket_connection(websocket):
        return
    await WebSocketServer.handle_connection(websocket, str(bot_instance_id))


@router.websocket("/ws/bots/{bot_instance_id}")
async def websocket_bot_runtime(websocket: WebSocket, bot_instance_id: str) -> None:
    """Alias websocket channel for backend integrations consuming bot runtime events."""
    if not await _authorize_websocket_connection(websocket):
        return
    await WebSocketServer.handle_connection(websocket, str(bot_instance_id))


@router.websocket("/ws/strategies")
async def websocket_strategies(websocket: WebSocket) -> None:
    """Frontend strategy status websocket channel."""
    if not await _authorize_websocket_connection(websocket):
        return

    channel = "strategies"
    await manager.connect(websocket, channel)
    try:
        bot_manager = _bot_manager_provider()
        if bot_manager is not None:
            await manager.send_personal_message(
                build_strategy_snapshot_message(
                    bot_manager.get_strategy_status_snapshot()
                ),
                websocket,
            )
        else:
            await manager.send_personal_message(
                {
                    "type": "strategy_channel_connected",
                    "channel": channel,
                    "timestamp": utc_now_iso(),
                },
                websocket,
            )

        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if message.get("type") == "ping":
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": utc_now_iso()},
                    websocket,
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
    except Exception as exc:
        logger.error(f"Strategy websocket error: {exc}")
        manager.disconnect(websocket, channel)


__all__ = [
    "_authorize_websocket_connection",
    "_resolve_realtime_bot_id",
    "configure_bot_realtime",
    "get_alerts",
    "get_current_positions",
    "get_market_data",
    "get_position",
    "get_position_history",
    "get_realtime_stats",
    "router",
    "websocket_alerts",
    "websocket_bot_runtime",
    "websocket_strategies",
]
