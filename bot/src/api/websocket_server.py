"""
WebSocket server for real-time bot data streaming
Provides live position updates, market data, and P&L tracking
"""

import json
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect
from internal.repository.repository_realtime import UnitOfWorkRealtime
from loguru import logger
from src.api.realtime_serializers import (
    serialize_market_core,
    serialize_realtime_position,
    serialize_stats_risk_fields,
)
from src.infrastructure.database import db
from src.infrastructure.persistence.repository import UnitOfWork
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.shared.time_utils import utc_now_iso


class ConnectionManager:
    """Manages WebSocket connections and broadcasts"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, bot_instance_id: str):
        """Register new WebSocket connection"""
        await websocket.accept()

        if bot_instance_id not in self.active_connections:
            self.active_connections[bot_instance_id] = set()

        self.active_connections[bot_instance_id].add(websocket)
        self.user_subscriptions[websocket] = {bot_instance_id}

        logger.info(
            f"Client connected to bot {bot_instance_id}. Total: {len(self.active_connections[bot_instance_id])}"
        )

    def disconnect(self, websocket: WebSocket, bot_instance_id: str):
        """Unregister WebSocket connection"""
        if bot_instance_id in self.active_connections:
            self.active_connections[bot_instance_id].discard(websocket)

            if not self.active_connections[bot_instance_id]:
                del self.active_connections[bot_instance_id]

        self.user_subscriptions.pop(websocket, None)
        logger.info(f"Client disconnected from bot {bot_instance_id}")

    async def broadcast_to_bot(self, bot_instance_id: str, message: Dict):
        """Broadcast message to all clients connected to a bot"""
        if bot_instance_id not in self.active_connections:
            return

        disconnected = set()
        for connection in self.active_connections[bot_instance_id]:
            try:
                await connection.send_json(message)
            except RuntimeError as e:
                logger.warning(f"Failed to send message: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.active_connections[bot_instance_id].discard(connection)

    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except RuntimeError as e:
            logger.warning(f"Failed to send personal message: {e}")


manager = ConnectionManager()


class WebSocketEvents:
    """WebSocket event handlers"""

    @staticmethod
    async def handle_position_opened(bot_instance_id: str, position_data: Dict):
        """Broadcast position opened event"""
        message = {
            "type": "position_opened",
            "timestamp": utc_now_iso(),
            "bot_instance_id": bot_instance_id,
            "data": position_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_position_updated(bot_instance_id: str, position_data: Dict):
        """Broadcast position price update"""
        message = {
            "type": "position_updated",
            "timestamp": utc_now_iso(),
            "bot_instance_id": bot_instance_id,
            "data": position_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_position_closed(bot_instance_id: str, position_data: Dict):
        """Broadcast position closed event"""
        message = {
            "type": "position_closed",
            "timestamp": utc_now_iso(),
            "bot_instance_id": bot_instance_id,
            "data": position_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_market_data(bot_instance_id: str, market_data: Dict):
        """Broadcast market data update"""
        message = {
            "type": "market_data",
            "timestamp": utc_now_iso(),
            "bot_instance_id": bot_instance_id,
            "data": market_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_stats_updated(bot_instance_id: str, stats_data: Dict):
        """Broadcast stats update"""
        message = {
            "type": "stats_updated",
            "timestamp": utc_now_iso(),
            "bot_instance_id": bot_instance_id,
            "data": stats_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_alert(bot_instance_id: str, alert_data: Dict):
        """Broadcast alert event"""
        message = {
            "type": "alert",
            "timestamp": utc_now_iso(),
            "bot_instance_id": bot_instance_id,
            "severity": alert_data.get("severity", "info"),
            "message": alert_data.get("message", ""),
            "data": alert_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)


class WebSocketServer:
    """WebSocket connection handler"""

    @staticmethod
    def _resolve_realtime_bot_id(session, bot_instance_id: str) -> int | None:
        raw = str(bot_instance_id or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass

        try:
            core_uow = UnitOfWork(session)
            bot = core_uow.bots.get_by_instance_id(raw)
            return int(bot.id) if bot else None
        except Exception as exc:
            logger.warning(
                "Failed resolving websocket bot instance '{}' to numeric id: {}",
                raw,
                exc,
            )
            return None

    @staticmethod
    def _is_backtest_channel(channel_id: str) -> bool:
        return channel_id.startswith("backtest-")

    @staticmethod
    def _backtest_run_id(channel_id: str) -> str:
        return channel_id.removeprefix("backtest-")

    @staticmethod
    def _build_backtest_status_message(run_id: str, data: Dict) -> Dict:
        progress = float(data.get("progress_pct", 0.0) or 0.0)
        return {
            "type": "backtest_progress",
            "timestamp": utc_now_iso(),
            "run_id": run_id,
            "status": str(data.get("status") or "pending"),
            "progress_pct": progress,
            "progress": progress,
            "current_pair": data.get("current_pair"),
            "current_task": data.get("current_task"),
            "eta_seconds": data.get("eta_seconds"),
            "total_pnl": float(data.get("total_pnl", 0.0) or 0.0),
            "total_trades": int(data.get("total_trades", 0) or 0),
            "win_rate": float(data.get("win_rate", 0.0) or 0.0),
            "sharpe_ratio": float(data.get("sharpe_ratio", 0.0) or 0.0),
            "max_drawdown_pct": float(data.get("max_drawdown_pct", 0.0) or 0.0),
            "profit_factor": float(data.get("profit_factor", 0.0) or 0.0),
            "error": data.get("error"),
            "error_message": data.get("error_message"),
            "message": data.get("current_task") or "backtest_status",
            "details": {
                "source": "initial_state",
                "updated_at": data.get("updated_at"),
            },
        }

    @staticmethod
    def _build_backtest_log_message(run_id: str, data: Dict) -> Dict | None:
        status = str(data.get("status") or "").strip().lower()
        current_pair = data.get("current_pair")
        current_task = data.get("current_task")

        message = None
        level = "info"

        if current_task == "complete" or status == "completed":
            message = "Backtest completed"
        elif current_task == "failed" or status == "failed":
            level = "error"
            message = str(data.get("error_message") or data.get("error") or "Backtest failed")
        elif current_task == "cancelled" or status == "cancelled":
            level = "warning"
            message = "Backtest cancelled"
        elif current_pair and current_task:
            message = f"{current_task}: {current_pair}"
        elif current_pair:
            message = f"Scanning: {current_pair}"
        elif current_task:
            message = str(current_task)
        elif status:
            message = f"Status: {status}"

        if not message:
            return None

        return {
            "type": "backtest_log",
            "timestamp": utc_now_iso(),
            "run_id": run_id,
            "level": level,
            "message": message,
            "status": status or None,
            "current_pair": current_pair,
            "current_task": current_task,
        }

    @staticmethod
    async def handle_connection(websocket: WebSocket, bot_instance_id: str):
        """Handle new WebSocket connection"""
        await manager.connect(websocket, bot_instance_id)

        try:
            # Send initial state
            await WebSocketServer.send_initial_state(websocket, bot_instance_id)

            # Handle incoming messages
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                await WebSocketServer.handle_message(
                    websocket, bot_instance_id, message
                )

        except WebSocketDisconnect:
            manager.disconnect(websocket, bot_instance_id)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            manager.disconnect(websocket, bot_instance_id)

    @staticmethod
    async def send_initial_state(websocket: WebSocket, bot_instance_id: str):
        """Send current bot state when client connects"""
        session = None
        try:
            if WebSocketServer._is_backtest_channel(bot_instance_id):
                await WebSocketServer.send_backtest_status(
                    websocket, WebSocketServer._backtest_run_id(bot_instance_id)
                )
                return

            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = WebSocketServer._resolve_realtime_bot_id(session, bot_instance_id)
            if bot_id is None:
                await manager.send_personal_message(
                    {
                        "type": "initial_state",
                        "timestamp": utc_now_iso(),
                        "data": {"positions": [], "market_data": [], "stats": {}},
                        "warning": f"Unknown bot instance id: {bot_instance_id}",
                    },
                    websocket,
                )
                return
            # Get open positions
            positions = uow.positions.get_open_positions(bot_id)
            # Get market data
            market_data = uow.market_data.get_all_market_data(bot_id)
            # Get stats
            stats = uow.stats.get_stats(bot_id)

            message = {
                "type": "initial_state",
                "timestamp": utc_now_iso(),
                "data": {
                    "positions": [
                        serialize_realtime_position(p)
                        for p in positions
                    ],
                    "market_data": [
                        serialize_market_core(m, include_volatility=True)
                        for m in market_data
                    ],
                    "stats": {
                        "total_open_positions": stats.total_open_positions
                        if stats
                        else 0,
                        "total_unrealized_pnl": float(stats.total_unrealized_pnl)
                        if stats
                        else 0,
                        "total_unrealized_pnl_pct": float(
                            stats.total_unrealized_pnl_pct
                        )
                        if stats
                        else 0,
                        "daily_pnl": float(stats.daily_pnl) if stats else 0,
                        "daily_pnl_pct": float(stats.daily_pnl_pct) if stats else 0,
                        "daily_trades_opened": stats.daily_trades_opened
                        if stats
                        else 0,
                        "daily_trades_closed": stats.daily_trades_closed
                        if stats
                        else 0,
                        "daily_win_rate": (
                            serialize_stats_risk_fields(stats)["daily_win_rate"]
                            if stats
                            else 0
                        ),
                    },
                },
            }

            await manager.send_personal_message(message, websocket)

        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
        finally:
            if session is not None:
                session.close()

    @staticmethod
    async def handle_message(websocket: WebSocket, bot_instance_id: str, message: Dict):
        """Handle incoming WebSocket message"""
        message_type = message.get("type")

        if message_type == "ping":
            # Respond to ping
            await manager.send_personal_message(
                {"type": "pong", "timestamp": utc_now_iso()}, websocket
            )

        elif (
                message_type == "request_status"
                and WebSocketServer._is_backtest_channel(bot_instance_id)
        ):
            await WebSocketServer.send_backtest_status(
                websocket, WebSocketServer._backtest_run_id(bot_instance_id)
            )

        elif message_type == "request_positions":
            # Client requests position list
            await WebSocketServer.send_positions(websocket, bot_instance_id)

        elif message_type == "request_stats":
            # Client requests statistics
            await WebSocketServer.send_stats(websocket, bot_instance_id)

        elif message_type == "request_market_data":
            # Client requests market data
            await WebSocketServer.send_market_data(websocket, bot_instance_id)

        else:
            logger.warning(f"Unknown message type: {message_type}")

    @staticmethod
    async def send_positions(websocket: WebSocket, bot_instance_id: str):
        """Send all positions to client"""
        session = None
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = WebSocketServer._resolve_realtime_bot_id(session, bot_instance_id)
            if bot_id is None:
                await manager.send_personal_message(
                    {"type": "positions_list", "timestamp": utc_now_iso(), "data": []},
                    websocket,
                )
                return
            positions = uow.positions.get_open_positions(bot_id)

            message = {
                "type": "positions_list",
                "timestamp": utc_now_iso(),
                "data": [
                    {
                        "position_id": p.position_id,
                        "pair1": p.pair1,
                        "pair2": p.pair2,
                        "unrealized_pnl": float(p.unrealized_pnl),
                        "unrealized_pnl_pct": float(p.unrealized_pnl_pct),
                    }
                    for p in positions
                ],
            }

            await manager.send_personal_message(message, websocket)

        except Exception as e:
            logger.error(f"Error sending positions: {e}")
        finally:
            if session is not None:
                session.close()

    @staticmethod
    async def send_stats(websocket: WebSocket, bot_instance_id: str):
        """Send statistics to client"""
        session = None
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = WebSocketServer._resolve_realtime_bot_id(session, bot_instance_id)
            if bot_id is None:
                await manager.send_personal_message(
                    {"type": "stats", "timestamp": utc_now_iso(), "data": {}},
                    websocket,
                )
                return
            stats = uow.stats.get_stats(bot_id)

            message = {
                "type": "stats",
                "timestamp": utc_now_iso(),
                "data": {
                    "total_open_positions": stats.total_open_positions if stats else 0,
                    "total_unrealized_pnl": float(stats.total_unrealized_pnl)
                    if stats
                    else 0,
                    "total_unrealized_pnl_pct": float(stats.total_unrealized_pnl_pct)
                    if stats
                    else 0,
                    "daily_pnl": float(stats.daily_pnl) if stats else 0,
                    "daily_pnl_pct": float(stats.daily_pnl_pct) if stats else 0,
                    "daily_trades_opened": stats.daily_trades_opened if stats else 0,
                    "daily_trades_closed": stats.daily_trades_closed if stats else 0,
                    **(serialize_stats_risk_fields(stats) if stats else {}),
                }
                if stats
                else {},
            }

            await manager.send_personal_message(message, websocket)

        except Exception as e:
            logger.error(f"Error sending stats: {e}")
        finally:
            if session is not None:
                session.close()

    @staticmethod
    async def send_market_data(websocket: WebSocket, bot_instance_id: str):
        """Send market data to client"""
        session = None
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = WebSocketServer._resolve_realtime_bot_id(session, bot_instance_id)
            if bot_id is None:
                await manager.send_personal_message(
                    {"type": "market_data", "timestamp": utc_now_iso(), "data": []},
                    websocket,
                )
                return
            market_data = uow.market_data.get_all_market_data(bot_id)

            message = {
                "type": "market_data",
                "timestamp": utc_now_iso(),
                "data": [
                    {
                        **serialize_market_core(m, include_volatility=False),
                        "rsi": float(m.rsi) if m.rsi else None,
                        "macd": float(m.macd) if m.macd else None,
                        "funding_rate": float(m.funding_rate)
                        if m.funding_rate
                        else None,
                    }
                    for m in market_data
                ],
            }

            await manager.send_personal_message(message, websocket)

        except Exception as e:
            logger.error(f"Error sending market data: {e}")
        finally:
            if session is not None:
                session.close()

    @staticmethod
    async def send_backtest_status(websocket: WebSocket, run_id: str):
        """Send backtest status to client on initial connect or explicit request."""
        session = None
        try:
            session = db.get_session()
            repository = BacktestRepository(session)
            run_data = repository.get_run(run_id)

            if run_data is None:
                message = {
                    "type": "backtest_progress",
                    "timestamp": utc_now_iso(),
                    "run_id": run_id,
                    "status": "not_found",
                    "progress_pct": 0.0,
                    "progress": 0.0,
                    "message": "backtest_not_found",
                }
                log_message = None
            else:
                message = WebSocketServer._build_backtest_status_message(run_id, run_data)
                log_message = WebSocketServer._build_backtest_log_message(run_id, run_data)

            await manager.send_personal_message(message, websocket)
            if log_message is not None:
                await manager.send_personal_message(log_message, websocket)
        except Exception as e:
            logger.error(f"Error sending backtest status: {e}")
        finally:
            if session is not None:
                session.close()


# Broadcast helper functions for use in bot operations


async def broadcast_position_opened(bot_instance_id: int, position_data: Dict):
    """Called when bot opens new position"""
    await WebSocketEvents.handle_position_opened(str(bot_instance_id), position_data)


async def broadcast_position_update(bot_instance_id: int, position_data: Dict):
    """Called when position prices update"""
    await WebSocketEvents.handle_position_updated(str(bot_instance_id), position_data)


async def broadcast_position_closed(bot_instance_id: int, position_data: Dict):
    """Called when bot closes position"""
    await WebSocketEvents.handle_position_closed(str(bot_instance_id), position_data)


async def broadcast_market_update(bot_instance_id: int, market_data: Dict):
    """Called when market data updates"""
    await WebSocketEvents.handle_market_data(str(bot_instance_id), market_data)


async def broadcast_stats_update(bot_instance_id: int, stats_data: Dict):
    """Called when statistics update"""
    await WebSocketEvents.handle_stats_updated(str(bot_instance_id), stats_data)


async def broadcast_alert(bot_instance_id: int, alert_data: Dict):
    """Called when alert is triggered"""
    await WebSocketEvents.handle_alert(str(bot_instance_id), alert_data)


async def broadcast_strategy_status(status_payload: Dict):
    """Broadcast strategy runtime lifecycle updates to strategy channel subscribers."""
    await manager.broadcast_to_bot("strategies", status_payload)


def build_strategy_snapshot_message(status_payloads: list[Dict]) -> Dict:
    """Build initial strategy channel snapshot payload."""
    return {
        "type": "strategy_status_snapshot",
        "timestamp": utc_now_iso(),
        "count": len(status_payloads),
        "data": status_payloads,
    }
