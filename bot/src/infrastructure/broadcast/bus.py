"""Redis pub/sub broadcast bus for cross-worker WebSocket fan-out.

The ``ConnectionManager`` in ``src/api/websocket_server.py`` is a process-local
singleton: its ``active_connections`` registry only knows about the WebSocket
clients connected to *this* Uvicorn worker. When the bot service runs more than
one worker (or more than one replica), a broadcast emitted on worker A — a
position update, a strategy-status lifecycle event, a backtest-progress tick —
never reaches the clients connected to worker B. This module closes that gap.

Design contract
---------------
* The bus is an **augmentation**, never a source of truth and never a hard
  dependency. ``publish`` and ``start`` are best-effort: a Redis outage degrades
  to local-only delivery (the originator still delivered to its own connections
  before publishing) and never raises into the caller. Like
  ``src/infrastructure/cache`` and the best-effort paths it mirrors, the broad
  ``except Exception`` blocks here are intentional isolation; this directory is
  excluded from the broad-catch ratchet (``tests/test_exception_handling_ratchet.py``).
* Ordering is **per-channel within a single subscriber**, not globally total.
  Messages from two different workers may interleave differently on different
  subscribers. All current producers (position/market/stats/strategy/backtest
  updates) are idempotent snapshots, so this is safe — do not use this bus for
  ordered event sourcing.
* Mirrors the storage-adapter conventions established by
  ``src/infrastructure/cache/market_cache.py``: ABC + concrete backend + no-op
  fallback, ``enabled`` flag, graceful degradation, ``health()``, lazy single
  persistent async client, ``reset_*`` for tests.

Wiring (see ``src/api/server.py`` lifespan): on startup each worker calls
``await get_broadcast_bus().start(manager.deliver_local_broadcast)``; on shutdown
``await bus.stop()`` then ``await bus.aclose()``. The bus is OFF by default
(``WS_BROADCAST_ENABLED=false``) so single-worker deployments and tests behave
identically to today.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

from loguru import logger

from src.constants import (
    WS_BROADCAST_ENABLED,
    WS_BROADCAST_REDIS_URL,
    WS_BROADCAST_SOCKET_TIMEOUT_SECONDS,
)
from src.shared.redis_env import redis_url

# Single shared pub/sub channel. Every WebSocket payload for every channel is
# multiplexed here; the subscriber skips delivery to channels with no local
# connections in O(1), so the only shared cost is one JSON decode per message.
_CHANNEL = "ws:broadcast"

# ``dispatch`` is the local-delivery callback the bus invokes on receipt — in
# production this is ``ConnectionManager.deliver_local_broadcast``.
Dispatch = Callable[[str, dict[str, Any]], Awaitable[None]]


class BroadcastBus(ABC):
    """Cross-worker fan-out bus for WebSocket broadcasts."""

    @abstractmethod
    async def publish(self, channel_id: str, message: dict[str, Any]) -> None:
        """Best-effort fan a broadcast out to other workers (never raises)."""

    @abstractmethod
    async def start(self, dispatch: Dispatch) -> None:
        """Begin receiving published broadcasts, invoking ``dispatch`` per message.

        Idempotent: a second call while running is a no-op. ``dispatch`` receives
        ``(channel_id, message)`` for messages published by *other* workers
        (self-originated messages are suppressed to avoid double delivery).
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop receiving and cancel the listener (idempotent, best-effort)."""

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return ``{enabled, backend, healthy, error, ...}`` for operators."""

    @abstractmethod
    async def aclose(self) -> None:
        """Release the underlying client (idempotent, best-effort)."""


class NoopBroadcastBus(BroadcastBus):
    """Fallback bus that performs no I/O (used when disabled or Redis absent)."""

    async def publish(self, channel_id: str, message: dict[str, Any]) -> None:
        del channel_id, message  # intentionally unused

    async def start(self, dispatch: Dispatch) -> None:
        del dispatch  # intentionally unused

    async def stop(self) -> None:
        return None

    async def health(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "backend": "noop",
            "healthy": True,
            "error": None,
            "worker_id": None,
            "listening": False,
        }

    async def aclose(self) -> None:
        return None


class RedisBroadcastBus(BroadcastBus):
    """Redis pub/sub-backed broadcast bus.

    The client is built lazily (``from_url`` defers the actual connection to the
    first command), so constructing this object never raises even when Redis is
    unreachable. ``publish`` is fire-and-forget; the listener reconnects with
    exponential backoff so a Redis blip or a late-starting Redis is self-healing.
    """

    def __init__(
        self,
        *,
        url: str,
        socket_timeout: float = 1.0,
        connect_timeout: float = 1.0,
        worker_id: str | None = None,
        channel: str = _CHANNEL,
        client: Any | None = None,
    ) -> None:
        self._url = url
        self._socket_timeout = float(socket_timeout)
        self._connect_timeout = float(connect_timeout)
        # Generated per-instance (not at module import) so forked children and
        # test doubles get distinct, injectable identities.
        self._worker_id = worker_id or uuid.uuid4().hex
        self._channel = channel
        # ``client`` is an injection seam for tests; production leaves it None
        # and the real client is built on first use.
        self._client: Any | None = client
        # Separate connection for the pub/sub listener. It must NOT inherit the
        # command ``socket_timeout``: an idle ``listen()`` read blocks forever
        # by design, whereas a finite timeout makes every idle second raise
        # TimeoutError, tearing the subscription down and resubscribing in a
        # loop — silently dropping messages published between resubscribes.
        self._listener_client: Any | None = None
        self._listener_build_error: str | None = None
        self._build_error: str | None = None
        self._pubsub: Any | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopped = False
        self._dispatch: Dispatch | None = None
        self._subscribed = False

    # ── internal helpers ────────────────────────────────────────────────────
    def _ensure_client(self) -> Any | None:
        """Return the async Redis client, building it on first use.

        Returns ``None`` (recording a build error) if ``redis.asyncio`` is
        unavailable or the client cannot be constructed.
        """
        if self._client is not None:
            return self._client
        try:  # pragma: no cover - optional dependency / config path
            import redis.asyncio as aioredis  # type: ignore[import]
        except Exception as exc:  # noqa: BLE001 - optional dep, degrade to noop
            self._build_error = f"redis.asyncio unavailable: {exc!r}"
            return None
        try:  # pragma: no cover - connection is deferred to first command
            self._client = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._connect_timeout,
            )
        except Exception as exc:  # noqa: BLE001 - bad URL/env, degrade to noop
            self._build_error = f"redis client build failed: {exc!r}"
            self._client = None
        return self._client

    def _ensure_listener_client(self) -> Any | None:
        """Return the pub/sub listener client (no read timeout, see __init__)."""
        if self._client is not None:
            # Test-injected client: use it for the listener as well.
            return self._client
        if self._listener_client is not None:
            return self._listener_client
        try:  # pragma: no cover - optional dependency / config path
            import redis.asyncio as aioredis  # type: ignore[import]
        except Exception as exc:  # noqa: BLE001 - optional dep, degrade to noop
            self._listener_build_error = f"redis.asyncio unavailable: {exc!r}"
            return None
        try:  # pragma: no cover - connection is deferred to first subscribe
            self._listener_client = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_timeout=None,
                socket_connect_timeout=self._connect_timeout,
            )
        except Exception as exc:  # noqa: BLE001 - bad URL/env, degrade to noop
            self._listener_build_error = f"redis client build failed: {exc!r}"
            self._listener_client = None
        return self._listener_client

    def _on_listener_done(self, task: asyncio.Task[None]) -> None:
        """Log unexpected listener termination (clean cancel is silent)."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning(
                "broadcast_bus_listener_terminated worker_id={} error={!r}",
                self._worker_id,
                exc,
            )

    async def _run(self) -> None:
        """Subscribe and dispatch until ``stop()``; reconnect on failure."""
        backoff = 1.0
        while not self._stopped:
            client = self._ensure_listener_client()
            if client is None:
                logger.debug(
                    "broadcast_bus_no_client_retry worker_id={} backoff={}",
                    self._worker_id,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
                continue

            pubsub: Any = client.pubsub()
            self._pubsub = pubsub
            try:
                await pubsub.subscribe(self._channel)
                self._subscribed = True
                backoff = 1.0
                async for msg in pubsub.listen():
                    if self._stopped:
                        break
                    if msg.get("type") != "message":
                        # Skip subscribe/ping acknowledgements emitted by redis-py.
                        continue
                    envelope = self._decode(msg.get("data"))
                    if envelope is None:
                        continue
                    if envelope.get("origin") == self._worker_id:
                        # We already delivered locally when we published; skip.
                        continue
                    channel_id = envelope.get("channel")
                    message = envelope.get("message")
                    if channel_id is None or message is None:
                        continue
                    if self._dispatch is None:
                        continue
                    try:
                        await self._dispatch(channel_id, message)
                    except Exception as exc:  # noqa: BLE001 - isolate one bad dispatch
                        logger.warning(
                            "broadcast_bus_dispatch_failed worker_id={} error={!r}",
                            self._worker_id,
                            exc,
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - reconnect on any listener failure
                logger.debug(
                    "broadcast_bus_listen_failed worker_id={} error={!r}",
                    self._worker_id,
                    exc,
                )
            finally:
                self._subscribed = False
                if self._pubsub is not None:
                    try:  # pragma: no cover - shutdown path
                        await self._pubsub.aclose()
                    except Exception:  # noqa: BLE001 - best-effort shutdown
                        pass
                    self._pubsub = None

            if self._stopped:
                break
            # listen() exited without being stopped (raised OR returned on a
            # dropped subscription). Pause ONCE with exponential backoff before
            # reconnecting, so a flapping Redis cannot tight-loop.
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)

    @staticmethod
    def _decode(raw: Any) -> dict[str, Any] | None:
        """JSON-decode a published envelope, returning ``None`` on any failure."""
        if not isinstance(raw, (str, bytes, bytearray)) or not raw:
            return None
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    # ── public API ──────────────────────────────────────────────────────────
    async def publish(self, channel_id: str, message: dict[str, Any]) -> None:
        client = self._ensure_client()
        if client is None:
            return
        try:  # pragma: no cover - requires a live Redis to exercise the command
            envelope = json.dumps(
                {
                    "channel": channel_id,
                    "message": message,
                    "origin": self._worker_id,
                }
            )
            await client.publish(self._channel, envelope)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - best-effort fan-out (serialize + send)
            logger.debug(
                "broadcast_bus_publish_failed worker_id={} channel={} error={!r}",
                self._worker_id,
                channel_id,
                exc,
            )

    async def start(self, dispatch: Dispatch) -> None:
        if self._task is not None and not self._task.done():
            return
        self._dispatch = dispatch
        self._stopped = False
        self._task = asyncio.create_task(self._run(), name="ws-broadcast-listener")
        self._task.add_done_callback(self._on_listener_done)

    async def stop(self) -> None:
        self._stopped = True
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutdown
                pass
        if self._pubsub is not None:
            try:  # pragma: no cover - shutdown path
                await self._pubsub.aclose()
            except Exception:  # noqa: BLE001 - best-effort shutdown
                pass
            self._pubsub = None

    async def health(self) -> dict[str, Any]:
        client = self._ensure_client()
        listening = self._task is not None and not self._task.done()
        base = {
            "enabled": True,
            "backend": "redis",
            "worker_id": self._worker_id,
            "listening": listening,
            "subscribed": self._subscribed,
        }
        if client is None:
            return {
                **base,
                "healthy": False,
                "error": self._build_error or "client not built",
            }
        try:  # pragma: no cover - requires a live Redis to exercise the command
            await client.ping()
            return {**base, "healthy": True, "error": None}
        except Exception as exc:  # noqa: BLE001 - report unhealthy, do not raise
            return {**base, "healthy": False, "error": str(exc)}

    async def aclose(self) -> None:
        # Ensure no listener is mid-flight before tearing down the clients it
        # uses (stop() is idempotent, so this is a no-op after a normal
        # stop()->aclose() shutdown sequence).
        await self.stop()
        client = self._client
        self._client = None
        listener_client = self._listener_client
        self._listener_client = None
        for candidate in (client, listener_client):
            if candidate is None:
                continue
            try:  # pragma: no cover - shutdown path
                await candidate.aclose()
            except Exception:  # noqa: BLE001 - best-effort shutdown
                continue


def _build_broadcast_bus() -> BroadcastBus:
    """Construct the bus from configuration, degrading to Noop as needed."""
    if not WS_BROADCAST_ENABLED:
        return NoopBroadcastBus()
    url = WS_BROADCAST_REDIS_URL or redis_url(prefer_celery_broker=True)
    if not url:
        return NoopBroadcastBus()
    return RedisBroadcastBus(
        url=url,
        socket_timeout=WS_BROADCAST_SOCKET_TIMEOUT_SECONDS,
    )


# Module-level singleton — built on first access. Tests reset it via
# ``reset_broadcast_bus()`` or replace it by monkeypatching the accessor at the
# importing module (e.g. ``websocket_server.get_broadcast_bus``).
_broadcast_bus: BroadcastBus | None = None


def get_broadcast_bus() -> BroadcastBus:
    """Return the process-wide broadcast bus (lazy singleton)."""
    global _broadcast_bus
    if _broadcast_bus is None:
        _broadcast_bus = _build_broadcast_bus()
    return _broadcast_bus


def reset_broadcast_bus() -> None:
    """Drop the cached singleton (tests / forced reconfiguration)."""
    global _broadcast_bus
    _broadcast_bus = None
