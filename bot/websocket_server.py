"""
WebSocket server for real-time bot data streaming
Provides live position updates, market data, and P&L tracking
"""

import json
import logging
from datetime import datetime
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

from database import db
from internal.repository.repository_realtime import UnitOfWorkRealtime

logger = logging.getLogger(__name__)


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
            "timestamp": datetime.utcnow().isoformat(),
            "bot_instance_id": bot_instance_id,
            "data": position_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_position_updated(bot_instance_id: str, position_data: Dict):
        """Broadcast position price update"""
        message = {
            "type": "position_updated",
            "timestamp": datetime.utcnow().isoformat(),
            "bot_instance_id": bot_instance_id,
            "data": position_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_position_closed(bot_instance_id: str, position_data: Dict):
        """Broadcast position closed event"""
        message = {
            "type": "position_closed",
            "timestamp": datetime.utcnow().isoformat(),
            "bot_instance_id": bot_instance_id,
            "data": position_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_market_data(bot_instance_id: str, market_data: Dict):
        """Broadcast market data update"""
        message = {
            "type": "market_data",
            "timestamp": datetime.utcnow().isoformat(),
            "bot_instance_id": bot_instance_id,
            "data": market_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_stats_updated(bot_instance_id: str, stats_data: Dict):
        """Broadcast stats update"""
        message = {
            "type": "stats_updated",
            "timestamp": datetime.utcnow().isoformat(),
            "bot_instance_id": bot_instance_id,
            "data": stats_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)

    @staticmethod
    async def handle_alert(bot_instance_id: str, alert_data: Dict):
        """Broadcast alert event"""
        message = {
            "type": "alert",
            "timestamp": datetime.utcnow().isoformat(),
            "bot_instance_id": bot_instance_id,
            "severity": alert_data.get("severity", "info"),
            "message": alert_data.get("message", ""),
            "data": alert_data,
        }
        await manager.broadcast_to_bot(bot_instance_id, message)


class WebSocketServer:
    """WebSocket connection handler"""

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
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = int(bot_instance_id)
            # Get open positions
            positions = uow.positions.get_open_positions(bot_id)
            # Get market data
            market_data = uow.market_data.get_all_market_data(bot_id)
            # Get stats
            stats = uow.stats.get_stats(bot_id)

            message = {
                "type": "initial_state",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "positions": [
                        {
                            "position_id": p.position_id,
                            "pair1": p.pair1,
                            "pair2": p.pair2,
                            "status": p.status.value,
                            "side1": p.side1,
                            "side2": p.side2,
                            "entry_price1": float(p.entry_price1),
                            "entry_price2": float(p.entry_price2),
                            "current_price1": float(p.current_price1)
                            if p.current_price1
                            else None,
                            "current_price2": float(p.current_price2)
                            if p.current_price2
                            else None,
                            "current_size1": float(p.current_size1),
                            "current_size2": float(p.current_size2),
                            "unrealized_pnl": float(p.unrealized_pnl),
                            "unrealized_pnl_pct": float(p.unrealized_pnl_pct),
                            "z_score_entry": float(p.z_score_entry)
                            if p.z_score_entry
                            else None,
                            "z_score_current": float(p.z_score_current)
                            if p.z_score_current
                            else None,
                            "entered_at": p.entry_time.isoformat(),
                        }
                        for p in positions
                    ],
                    "market_data": [
                        {
                            "symbol": m.symbol,
                            "current_price": float(m.current_price),
                            "bid_price": float(m.bid_price) if m.bid_price else None,
                            "ask_price": float(m.ask_price) if m.ask_price else None,
                            "volume_24h": float(m.volume_24h) if m.volume_24h else None,
                            "volatility_24h": float(m.volatility_24h)
                            if m.volatility_24h
                            else None,
                        }
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
                        "daily_win_rate": float(stats.daily_win_rate) if stats else 0,
                    },
                },
            }

            await manager.send_personal_message(message, websocket)
            session.close()

        except Exception as e:
            logger.error(f"Error sending initial state: {e}")

    @staticmethod
    async def handle_message(websocket: WebSocket, bot_instance_id: str, message: Dict):
        """Handle incoming WebSocket message"""
        message_type = message.get("type")

        if message_type == "ping":
            # Respond to ping
            await manager.send_personal_message(
                {"type": "pong", "timestamp": datetime.utcnow().isoformat()}, websocket
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
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = int(bot_instance_id)
            positions = uow.positions.get_open_positions(bot_id)

            message = {
                "type": "positions_list",
                "timestamp": datetime.utcnow().isoformat(),
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
            session.close()

        except Exception as e:
            logger.error(f"Error sending positions: {e}")

    @staticmethod
    async def send_stats(websocket: WebSocket, bot_instance_id: str):
        """Send statistics to client"""
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = int(bot_instance_id)
            stats = uow.stats.get_stats(bot_id)

            message = {
                "type": "stats",
                "timestamp": datetime.utcnow().isoformat(),
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
                    "daily_win_rate": float(stats.daily_win_rate) if stats else 0,
                    "max_drawdown": float(stats.max_drawdown_session) if stats else 0,
                    "current_drawdown": float(stats.current_drawdown) if stats else 0,
                }
                if stats
                else {},
            }

            await manager.send_personal_message(message, websocket)
            session.close()

        except Exception as e:
            logger.error(f"Error sending stats: {e}")

    @staticmethod
    async def send_market_data(websocket: WebSocket, bot_instance_id: str):
        """Send market data to client"""
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = int(bot_instance_id)
            market_data = uow.market_data.get_all_market_data(bot_id)

            message = {
                "type": "market_data",
                "timestamp": datetime.utcnow().isoformat(),
                "data": [
                    {
                        "symbol": m.symbol,
                        "current_price": float(m.current_price),
                        "bid_price": float(m.bid_price) if m.bid_price else None,
                        "ask_price": float(m.ask_price) if m.ask_price else None,
                        "volume_24h": float(m.volume_24h) if m.volume_24h else None,
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
            session.close()

        except Exception as e:
            logger.error(f"Error sending market data: {e}")


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
