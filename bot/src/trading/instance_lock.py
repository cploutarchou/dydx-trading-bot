"""Single-writer guarantee for one trading instance.

Two processes trading the same instance id on the same account double every
order. Deployment discipline (one replica, Recreate) only covers the cluster
rollout; this lock covers every other way a second process can appear (manual
start, a supervisor restart racing an old process, a second host).

The lock is a PostgreSQL session-level advisory lock held on a dedicated
connection for the life of the process. It is released by PostgreSQL itself
when the process or its connection dies, so a crash never leaves a stale lock.
Because a dropped connection also drops the lock, the holder re-checks it every
cycle and must stop trading when it can no longer prove it holds it.

Session-level advisory locks require a direct PostgreSQL connection; they do
not survive a transaction-pooling proxy.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.exceptions import TradingError

_LOCK_NAMESPACE = "dydx-trading-bot:instance:"

# What a broken database connection raises: driver/SQLAlchemy errors and socket
# level failures. Anything else is a programming error and must surface.
_CONNECTION_ERRORS = (SQLAlchemyError, OSError)


class InstanceLockError(TradingError):
    """The single-writer lock could not be taken or is no longer held."""


class InstanceAlreadyRunningError(InstanceLockError):
    """Another process holds the lock for this instance id."""


def advisory_key(instance_id: str) -> int:
    """Stable signed 64-bit key for ``pg_try_advisory_lock``."""
    digest = hashlib.blake2b(
        f"{_LOCK_NAMESPACE}{instance_id}".encode("utf-8"), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big", signed=True)


class InstanceLock:
    """Holds the advisory lock for one instance id on a dedicated connection."""

    def __init__(self, engine: Any, instance_id: str) -> None:
        self._engine = engine
        self._instance_id = instance_id
        self._key = advisory_key(instance_id)
        self._connection: Optional[Any] = None

    @property
    def supported(self) -> bool:
        return str(getattr(self._engine.dialect, "name", "")) == "postgresql"

    def acquire(self) -> None:
        """Take the lock or raise. Never returns without holding it."""
        if not self.supported:
            raise InstanceLockError(
                "the single-writer lock needs PostgreSQL; refusing to trade on "
                f"dialect '{getattr(self._engine.dialect, 'name', 'unknown')}'"
            )
        connection = self._engine.connect()
        acquired = False
        try:
            # Take the connection out of the pool. A pooled connection is only
            # returned on close(), not closed: the session (and the lock) would
            # live on and could be handed to unrelated code. Detached, close()
            # ends the session and PostgreSQL releases the lock.
            connection.detach()
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": self._key}
                ).scalar()
            )
            # Leave no transaction open on the connection that holds the lock.
            connection.commit()
        finally:
            if not acquired:
                connection.close()
        if not acquired:
            raise InstanceAlreadyRunningError(
                f"instance '{self._instance_id}' is already running in another "
                "process; refusing to start a second trader"
            )
        self._connection = connection
        logger.info("Single-writer lock acquired for instance {}", self._instance_id)

    def ensure_held(self) -> None:
        """Prove the lock is still held, re-taking it once if the connection died.

        Raises :class:`InstanceLockError` when the lock cannot be proven, which
        the trading loop treats as a reason to stop.
        """
        if self._connection is None:
            raise InstanceLockError("single-writer lock was never acquired")
        try:
            held = self._connection.execute(
                # pg_locks splits a bigint advisory key into its high (classid)
                # and low (objid) 32 bits, with objsubid = 1.
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_locks "
                    "WHERE locktype = 'advisory' AND pid = pg_backend_pid() "
                    "AND granted AND objsubid = 1 "
                    "AND classid::bigint = :high AND objid::bigint = :low)"
                ),
                {
                    "high": (self._key >> 32) & 0xFFFFFFFF,
                    "low": self._key & 0xFFFFFFFF,
                },
            ).scalar()
            self._connection.commit()
            if held:
                return
            logger.critical(
                "Single-writer lock for {} is no longer held on its connection",
                self._instance_id,
            )
        except _CONNECTION_ERRORS as exc:
            logger.critical(
                "Single-writer lock connection for {} failed: {}",
                self._instance_id,
                exc,
            )
        self._discard_connection()
        # One attempt to take it back. If another process took over in the
        # meantime this raises InstanceAlreadyRunningError and trading stops.
        self.acquire()

    def release(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": self._key}
            )
            self._connection.commit()
        except _CONNECTION_ERRORS as exc:
            # Closing the connection releases the lock anyway.
            logger.warning("Advisory unlock failed for {}: {}", self._instance_id, exc)
        self._discard_connection()

    def _discard_connection(self) -> None:
        connection, self._connection = self._connection, None
        if connection is None:
            return
        try:
            connection.close()
        except _CONNECTION_ERRORS as exc:
            logger.debug("Closing the lock connection failed: {}", exc)
