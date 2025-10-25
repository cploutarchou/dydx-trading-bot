"""
WebSocket broadcaster for real-time backtest progress updates.

Provides a singleton manager for WebSocket connections and broadcasting
progress messages to subscribed clients. Includes strategy metadata in
real-time progress broadcasts.
"""

import json
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class BacktestProgressUpdate:
    """Data class for backtest progress updates."""

    def __init__(
        self,
        run_id: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        details: Optional[dict] = None,
        strategy_id: Optional[int] = None,
        strategy_name: Optional[str] = None,
    ):
        """
        Initialize progress update.

        Args:
            run_id: Backtest run ID
            status: Current status (queued, running, completed, failed)
            progress: Progress percentage (0-100)
            message: Human-readable message
            details: Additional details (pairs processed, trades, etc.)
            strategy_id: ID of the strategy being used (optional)
            strategy_name: Name of the strategy for UI display (optional)
        """
        self.run_id = run_id
        self.status = status
        self.progress = progress
        self.message = message
        self.details = details or {}
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "details": self.details,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class WebSocketBroadcaster:
    """
    Manages WebSocket connections and broadcasts progress updates.

    Uses a callback-based system since WebSocket connections are managed
    by FastAPI and not accessible directly from background workers.
    """

    def __init__(self):
        """Initialize the broadcaster."""
        self._callbacks: Dict[str, List[Callable]] = {}
        self._global_callbacks: List[Callable] = []

    def subscribe(self, run_id: str, callback: Callable):
        """
        Subscribe to updates for a specific backtest run.

        Args:
            run_id: Backtest run ID to subscribe to
            callback: Async callable(update: BacktestProgressUpdate) to receive updates
        """
        if run_id not in self._callbacks:
            self._callbacks[run_id] = []
        self._callbacks[run_id].append(callback)
        logger.debug(f"WebSocket subscription added for run {run_id}")

    def unsubscribe(self, run_id: str, callback: Callable):
        """
        Unsubscribe from updates for a specific backtest run.

        Args:
            run_id: Backtest run ID to unsubscribe from
            callback: Callback to remove
        """
        if run_id in self._callbacks:
            self._callbacks[run_id] = [
                cb for cb in self._callbacks[run_id] if cb != callback
            ]
            if not self._callbacks[run_id]:
                del self._callbacks[run_id]
            logger.debug(f"WebSocket subscription removed for run {run_id}")

    def subscribe_global(self, callback: Callable):
        """
        Subscribe to all updates.

        Args:
            callback: Async callable(update: BacktestProgressUpdate) to receive updates
        """
        self._global_callbacks.append(callback)
        logger.debug("Global WebSocket subscription added")

    def unsubscribe_global(self, callback: Callable):
        """
        Unsubscribe from all updates.

        Args:
            callback: Callback to remove
        """
        self._global_callbacks = [cb for cb in self._global_callbacks if cb != callback]
        logger.debug("Global WebSocket subscription removed")

    async def broadcast(self, update: BacktestProgressUpdate):
        """
        Broadcast an update to subscribed clients.

        Enriches the update with strategy information if strategy_id is provided
        and database session is available.

        Args:
            update: BacktestProgressUpdate to broadcast
        """
        # Send to run-specific subscribers
        if update.run_id in self._callbacks:
            for callback in self._callbacks[update.run_id]:
                try:
                    await callback(update)
                except Exception as e:
                    logger.error(f"Error calling callback for {update.run_id}: {e}")

        # Send to global subscribers
        for callback in self._global_callbacks:
            try:
                await callback(update)
            except Exception as e:
                logger.error(f"Error calling global callback: {e}")

        logger.debug(
            f"Broadcasted update for run {update.run_id}: {update.status} "
            f"({update.progress or 0}%) - Strategy: {update.strategy_name or 'N/A'}"
        )

    def enrich_with_strategy(
        self, update: BacktestProgressUpdate, db: Optional[Session] = None
    ) -> BacktestProgressUpdate:
        """
        Enrich progress update with strategy information from database.

        Args:
            update: BacktestProgressUpdate to enrich
            db: Database session for querying strategy info

        Returns:
            Enriched BacktestProgressUpdate with strategy_name populated
        """
        if db is not None and update.strategy_id is not None:
            try:
                # Import here to avoid circular imports
                from database import BacktestStrategy

                strategy = (
                    db.query(BacktestStrategy)
                    .filter(BacktestStrategy.id == update.strategy_id)
                    .first()
                )

                if strategy:
                    update.strategy_name = strategy.name
                    logger.debug(
                        f"Enriched update with strategy: {strategy.name} (ID: {strategy.id})"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to enrich update with strategy info: {e}. Continuing without strategy_name."
                )

        return update

    def has_subscribers(self, run_id: Optional[str] = None) -> bool:
        """
        Check if there are subscribers.

        Args:
            run_id: Check for a specific run ID, or None for global

        Returns:
            True if there are subscribers
        """
        if run_id:
            return run_id in self._callbacks and len(self._callbacks[run_id]) > 0
        return len(self._global_callbacks) > 0 or any(self._callbacks.values())


# Singleton instance
_broadcaster: Optional[WebSocketBroadcaster] = None


def get_broadcaster() -> WebSocketBroadcaster:
    """Get or create the WebSocket broadcaster singleton."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = WebSocketBroadcaster()
    return _broadcaster
