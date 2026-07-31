"""
WebSocket server for real-time bot data streaming
Provides live position updates, market data, and P&L tracking
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, Optional, Set, cast

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from starlette.concurrency import run_in_threadpool

from internal.repository.repository_realtime import UnitOfWorkRealtime
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
        self.send_metrics: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _is_backtest_channel(channel_id: str) -> bool:
        return str(channel_id or "").startswith("backtest-")

    @staticmethod
    def _backtest_run_id(channel_id: str) -> str:
        return str(channel_id or "").removeprefix("backtest-")

    @staticmethod
    def _positive_int_env(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw in (None, ""):
            return max(1, int(default))
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return max(1, int(default))

    @staticmethod
    def _positive_float_env(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw in (None, ""):
            return max(1.0, float(default))
        try:
            return max(1.0, float(raw))
        except (TypeError, ValueError):
            return max(1.0, float(default))

    def _run_metrics_bucket(self, run_id: str) -> Dict[str, Any]:
        bucket = self.send_metrics.get(run_id)
        if bucket is not None:
            return bucket

        bucket = {
            "run_id": run_id,
            "total_send_attempts": 0,
            "total_send_successes": 0,
            "total_send_failures": 0,
            "total_send_disconnects": 0,
            "consecutive_send_failures": 0,
            "last_error_type": None,
            "last_error_repr": None,
            "last_failure_at": None,
            "last_success_at": None,
            "recent_failure_timestamps": [],
            "updated_at": utc_now_iso(),
        }
        self.send_metrics[run_id] = bucket
        return bucket

    @staticmethod
    def _is_expected_disconnect(exc: Exception) -> bool:
        return isinstance(exc, WebSocketDisconnect)

    def _record_backtest_connect(self, channel_id: str) -> None:
        """Reset stale failure streaks when a backtest client reconnects."""
        if not self._is_backtest_channel(channel_id):
            return
        run_id = self._backtest_run_id(channel_id)
        if not run_id:
            return
        bucket = self._run_metrics_bucket(run_id)
        now_ts = time.time()
        bucket["consecutive_send_failures"] = 0
        bucket["updated_at"] = utc_now_iso()
        self._prune_recent_failures(bucket, now_ts)

    def _prune_recent_failures(self, bucket: Dict[str, Any], now_ts: float) -> None:
        window_seconds = self._positive_float_env(
            "BACKTEST_WS_FAILURE_ALERT_WINDOW_SECONDS", 60.0
        )
        cutoff = now_ts - window_seconds
        recent = bucket.get("recent_failure_timestamps") or []
        bucket["recent_failure_timestamps"] = [t for t in recent if t >= cutoff]

    def _record_send_success(self, channel_id: Optional[str]) -> None:
        if not channel_id or not self._is_backtest_channel(channel_id):
            return
        run_id = self._backtest_run_id(channel_id)
        if not run_id:
            return
        bucket = self._run_metrics_bucket(run_id)
        now_ts = time.time()
        bucket["total_send_attempts"] += 1
        bucket["total_send_successes"] += 1
        bucket["consecutive_send_failures"] = 0
        bucket["last_success_at"] = utc_now_iso()
        bucket["updated_at"] = bucket["last_success_at"]
        self._prune_recent_failures(bucket, now_ts)

    def _record_send_failure(
        self,
        channel_id: Optional[str],
        exc: Exception,
        *,
        operation: str,
    ) -> None:
        if not channel_id or not self._is_backtest_channel(channel_id):
            return
        run_id = self._backtest_run_id(channel_id)
        if not run_id:
            return

        bucket = self._run_metrics_bucket(run_id)
        now_ts = time.time()
        bucket["total_send_attempts"] += 1
        is_expected_disconnect = self._is_expected_disconnect(exc)
        if is_expected_disconnect:
            bucket["total_send_disconnects"] += 1
            bucket["consecutive_send_failures"] = 0
        else:
            bucket["total_send_failures"] += 1
            bucket["consecutive_send_failures"] += 1
        bucket["last_error_type"] = type(exc).__name__
        bucket["last_error_repr"] = repr(exc)
        bucket["last_failure_at"] = utc_now_iso()
        bucket["updated_at"] = bucket["last_failure_at"]
        if not is_expected_disconnect:
            recent = bucket.get("recent_failure_timestamps") or []
            recent.append(now_ts)
            bucket["recent_failure_timestamps"] = recent
        self._prune_recent_failures(bucket, now_ts)

        if is_expected_disconnect:
            logger.debug(
                "backtest_ws_expected_disconnect run_id={} operation={} last_error_type={} last_error_repr={!r}",
                run_id,
                operation,
                bucket["last_error_type"],
                bucket["last_error_repr"],
            )
            return

        alert_threshold = self._positive_int_env(
            "BACKTEST_WS_FAILURE_ALERT_THRESHOLD", 5
        )
        recent_failures = len(bucket.get("recent_failure_timestamps") or [])
        if (
            bucket["consecutive_send_failures"] >= alert_threshold
            or recent_failures >= alert_threshold
        ):
            logger.warning(
                "backtest_ws_send_failure_alert run_id={} operation={} consecutive_failures={} recent_failures={} threshold={} last_error_type={} last_error_repr={!r}",
                run_id,
                operation,
                bucket["consecutive_send_failures"],
                recent_failures,
                alert_threshold,
                bucket["last_error_type"],
                bucket["last_error_repr"],
            )

    def get_backtest_send_failure_metrics(self, run_id: str) -> Dict[str, Any]:
        run_key = str(run_id or "").strip()
        if not run_key:
            return {
                "run_id": run_key,
                "alert_threshold": self._positive_int_env(
                    "BACKTEST_WS_FAILURE_ALERT_THRESHOLD", 5
                ),
                "alert_window_seconds": self._positive_float_env(
                    "BACKTEST_WS_FAILURE_ALERT_WINDOW_SECONDS", 60.0
                ),
                "metrics": None,
            }

        existing = self.send_metrics.get(run_key)
        if existing is None:
            return {
                "run_id": run_key,
                "alert_threshold": self._positive_int_env(
                    "BACKTEST_WS_FAILURE_ALERT_THRESHOLD", 5
                ),
                "alert_window_seconds": self._positive_float_env(
                    "BACKTEST_WS_FAILURE_ALERT_WINDOW_SECONDS", 60.0
                ),
                "metrics": {
                    "total_send_attempts": 0,
                    "total_send_successes": 0,
                    "total_send_failures": 0,
                    "consecutive_send_failures": 0,
                    "recent_send_failures": 0,
                    "last_error_type": None,
                    "last_error_repr": None,
                    "last_failure_at": None,
                    "last_success_at": None,
                    "updated_at": None,
                },
                "alert_recommended": False,
            }

        now_ts = time.time()
        self._prune_recent_failures(existing, now_ts)
        bucket = dict(existing)
        recent_failures = len(bucket.get("recent_failure_timestamps") or [])
        alert_threshold = self._positive_int_env(
            "BACKTEST_WS_FAILURE_ALERT_THRESHOLD", 5
        )
        alert_window_seconds = self._positive_float_env(
            "BACKTEST_WS_FAILURE_ALERT_WINDOW_SECONDS", 60.0
        )
        alert_recommended = (
            int(bucket.get("consecutive_send_failures", 0) or 0) >= alert_threshold
            or recent_failures >= alert_threshold
        )

        return {
            "run_id": run_key,
            "alert_threshold": alert_threshold,
            "alert_window_seconds": alert_window_seconds,
            "metrics": {
                "total_send_attempts": int(bucket.get("total_send_attempts", 0) or 0),
                "total_send_successes": int(bucket.get("total_send_successes", 0) or 0),
                "total_send_failures": int(bucket.get("total_send_failures", 0) or 0),
                "total_send_disconnects": int(
                    bucket.get("total_send_disconnects", 0) or 0
                ),
                "consecutive_send_failures": int(
                    bucket.get("consecutive_send_failures", 0) or 0
                ),
                "recent_send_failures": recent_failures,
                "last_error_type": bucket.get("last_error_type"),
                "last_error_repr": bucket.get("last_error_repr"),
                "last_failure_at": bucket.get("last_failure_at"),
                "last_success_at": bucket.get("last_success_at"),
                "updated_at": bucket.get("updated_at"),
            },
            "alert_recommended": alert_recommended,
        }

    def get_backtest_send_failure_summary(self) -> Dict[str, Any]:
        alert_threshold = self._positive_int_env(
            "BACKTEST_WS_FAILURE_ALERT_THRESHOLD", 5
        )
        alert_window_seconds = self._positive_float_env(
            "BACKTEST_WS_FAILURE_ALERT_WINDOW_SECONDS", 60.0
        )

        runs = []
        for run_id in sorted(self.send_metrics.keys()):
            run_metrics = self.get_backtest_send_failure_metrics(run_id)
            if run_metrics.get("metrics") is not None:
                runs.append(run_metrics)

        total_failures = sum(
            int((row.get("metrics") or {}).get("total_send_failures", 0) or 0)
            for row in runs
        )
        runs_with_alerts = [
            row.get("run_id") for row in runs if row.get("alert_recommended")
        ]

        return {
            "alert_threshold": alert_threshold,
            "alert_window_seconds": alert_window_seconds,
            "tracked_runs": len(runs),
            "total_send_failures": total_failures,
            "runs_with_alerts": runs_with_alerts,
        }

    async def connect(self, websocket: WebSocket, bot_instance_id: str):
        """Register new WebSocket connection"""
        await websocket.accept()

        if bot_instance_id not in self.active_connections:
            self.active_connections[bot_instance_id] = set()

        self.active_connections[bot_instance_id].add(websocket)
        self.user_subscriptions[websocket] = {bot_instance_id}
        self._record_backtest_connect(bot_instance_id)

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

    def _drop_connection(self, websocket: WebSocket):
        """Remove websocket from all tracked channels/subscriptions."""
        channels = list(self.user_subscriptions.get(websocket, set()))
        for channel in channels:
            connections = self.active_connections.get(channel)
            if not connections:
                continue
            connections.discard(websocket)
            if not connections:
                self.active_connections.pop(channel, None)
        self.user_subscriptions.pop(websocket, None)

    async def _broadcast_connection_send(
        self,
        channel_id: str,
        connection: WebSocket,
        message: Dict,
    ) -> tuple[WebSocket, bool]:
        try:
            await connection.send_json(message)
            self._record_send_success(channel_id)
            return connection, True
        except WebSocketDisconnect as e:
            self._record_send_failure(
                channel_id,
                e,
                operation="broadcast_to_bot",
            )
            return connection, False
        except Exception as e:
            self._record_send_failure(
                channel_id,
                e,
                operation="broadcast_to_bot",
            )
            logger.warning(
                "Failed to send broadcast message on channel {}: type={} error={!r}",
                channel_id,
                type(e).__name__,
                e,
            )
            return connection, False

    async def broadcast_to_bot(self, bot_instance_id: str, message: Dict):
        """Broadcast message to all clients connected to a bot"""
        if bot_instance_id not in self.active_connections:
            return

        connections = list(self.active_connections.get(bot_instance_id) or set())
        if not connections:
            return

        results = await asyncio.gather(
            *[
                self._broadcast_connection_send(bot_instance_id, connection, message)
                for connection in connections
            ]
        )
        disconnected = {connection for connection, sent in results if not sent}

        # Clean up disconnected clients
        for connection in disconnected:
            self._drop_connection(connection)

    async def send_personal_message(
        self,
        message: Dict,
        websocket: WebSocket,
        *,
        channel_id: Optional[str] = None,
    ) -> bool:
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
            self._record_send_success(channel_id)
            return True
        except WebSocketDisconnect as e:
            self._record_send_failure(
                channel_id,
                e,
                operation="send_personal_message",
            )
            self._drop_connection(websocket)
            return False
        except Exception as e:
            self._record_send_failure(
                channel_id,
                e,
                operation="send_personal_message",
            )
            logger.warning(
                "Failed to send personal message: type={} error={!r}",
                type(e).__name__,
                e,
            )
            self._drop_connection(websocket)
            return False


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
            return int(cast(int, bot.id)) if bot else None
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
            message = str(
                data.get("error_message") or data.get("error") or "Backtest failed"
            )
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
            initial_state_sent = await WebSocketServer.send_initial_state(
                websocket, bot_instance_id
            )
            if not initial_state_sent:
                manager.disconnect(websocket, bot_instance_id)
                return

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
            logger.error(
                "WebSocket error for {}: type={} error={!r}",
                bot_instance_id,
                type(e).__name__,
                e,
            )
            manager.disconnect(websocket, bot_instance_id)

    @staticmethod
    async def send_initial_state(websocket: WebSocket, bot_instance_id: str) -> bool:
        """Send current bot state when client connects"""
        session = None
        try:
            if WebSocketServer._is_backtest_channel(bot_instance_id):
                return await WebSocketServer.send_backtest_status(
                    websocket, WebSocketServer._backtest_run_id(bot_instance_id)
                )

            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            bot_id = WebSocketServer._resolve_realtime_bot_id(session, bot_instance_id)
            if bot_id is None:
                sent = await manager.send_personal_message(
                    {
                        "type": "initial_state",
                        "timestamp": utc_now_iso(),
                        "data": {"positions": [], "market_data": [], "stats": {}},
                        "warning": f"Unknown bot instance id: {bot_instance_id}",
                    },
                    websocket,
                )
                return sent
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
                    "positions": [serialize_realtime_position(p) for p in positions],
                    "market_data": [
                        serialize_market_core(m, include_volatility=True)
                        for m in market_data
                    ],
                    "stats": {
                        "total_open_positions": (
                            stats.total_open_positions if stats else 0
                        ),
                        "total_unrealized_pnl": (
                            float(stats.total_unrealized_pnl) if stats else 0
                        ),
                        "total_unrealized_pnl_pct": (
                            float(stats.total_unrealized_pnl_pct) if stats else 0
                        ),
                        "daily_pnl": float(stats.daily_pnl) if stats else 0,
                        "daily_pnl_pct": float(stats.daily_pnl_pct) if stats else 0,
                        "daily_trades_opened": (
                            stats.daily_trades_opened if stats else 0
                        ),
                        "daily_trades_closed": (
                            stats.daily_trades_closed if stats else 0
                        ),
                        "daily_win_rate": (
                            serialize_stats_risk_fields(stats)["daily_win_rate"]
                            if stats
                            else 0
                        ),
                    },
                },
            }

            return await manager.send_personal_message(message, websocket)

        except Exception as e:
            logger.error(
                "Error sending initial state for {}: type={} error={!r}",
                bot_instance_id,
                type(e).__name__,
                e,
            )
            return False
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

        elif message_type == "request_status" and WebSocketServer._is_backtest_channel(
            bot_instance_id
        ):
            sent = await WebSocketServer.send_backtest_status(
                websocket, WebSocketServer._backtest_run_id(bot_instance_id)
            )
            if sent is False:
                raise RuntimeError(
                    "Backtest websocket status send failed; closing connection"
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
                "data": (
                    {
                        "total_open_positions": (
                            stats.total_open_positions if stats else 0
                        ),
                        "total_unrealized_pnl": (
                            float(stats.total_unrealized_pnl) if stats else 0
                        ),
                        "total_unrealized_pnl_pct": (
                            float(stats.total_unrealized_pnl_pct) if stats else 0
                        ),
                        "daily_pnl": float(stats.daily_pnl) if stats else 0,
                        "daily_pnl_pct": float(stats.daily_pnl_pct) if stats else 0,
                        "daily_trades_opened": (
                            stats.daily_trades_opened if stats else 0
                        ),
                        "daily_trades_closed": (
                            stats.daily_trades_closed if stats else 0
                        ),
                        **(serialize_stats_risk_fields(stats) if stats else {}),
                    }
                    if stats
                    else {}
                ),
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
                        "funding_rate": (
                            float(m.funding_rate) if m.funding_rate else None
                        ),
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
    async def send_backtest_status(websocket: WebSocket, run_id: str) -> bool:
        """Send backtest status to client on initial connect or explicit request."""
        try:

            def _load_backtest_run_overview() -> Optional[Dict]:
                session = db.get_session()
                try:
                    repository = BacktestRepository(session)
                    return repository.get_run_overview(run_id)
                finally:
                    session.close()

            run_data = await run_in_threadpool(_load_backtest_run_overview)

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
                message = WebSocketServer._build_backtest_status_message(
                    run_id, run_data
                )
                log_message = WebSocketServer._build_backtest_log_message(
                    run_id, run_data
                )

            sent = await manager.send_personal_message(
                message,
                websocket,
                channel_id=f"backtest-{run_id}",
            )
            if not sent:
                return False
            if log_message is not None:
                sent_log = await manager.send_personal_message(
                    log_message,
                    websocket,
                    channel_id=f"backtest-{run_id}",
                )
                if not sent_log:
                    return False
            return True
        except Exception as e:
            logger.error(
                "Error sending backtest status run_id={}: type={} error={!r}",
                run_id,
                type(e).__name__,
                e,
            )
            return False


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
