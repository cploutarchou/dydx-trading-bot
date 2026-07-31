"""Concurrency-safe helpers for per-instance tracked-position state.

DB is the primary store; the JSON file is kept as a fallback for environments
without a reachable database.
"""

import asyncio
import contextlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

# ---------------------------------------------------------------------------
# Instance identity
# ---------------------------------------------------------------------------

_INSTANCE_ID: str = os.getenv("BOT_INSTANCE_ID", "default")


# ---------------------------------------------------------------------------
# File-based paths (fallback)
# ---------------------------------------------------------------------------


def _resolve_bot_agents_path() -> Path:
    configured_path = os.getenv("BOT_AGENTS_FILE", "bot_states/bot_agents.json")
    resolved = configured_path.replace("{instance_id}", _INSTANCE_ID)
    path = Path(resolved)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


BOT_AGENTS_PATH = _resolve_bot_agents_path()
_BOT_AGENTS_ASYNC_LOCK = asyncio.Lock()
_BOT_AGENTS_THREAD_LOCK = threading.RLock()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _db_load_positions() -> Optional[List[Dict[str, Any]]]:
    """Read tracked positions from the database.

    Returns:
        List of positions if a DB row exists for this instance.
        None if no row found (triggers file fallback) or if DB is unavailable.
    """
    try:
        from src.infrastructure.database import db

        session = db.get_session()
        try:
            result = session.execute(
                _sa_text(
                    "SELECT positions_json FROM tracked_positions WHERE instance_id = :iid"
                ),
                {"iid": _INSTANCE_ID},
            ).fetchone()
            if result is None:
                return None  # No row yet; fall back to file for backward compat
            data = result[0]
            return data if isinstance(data, list) else []
        finally:
            session.close()
    except Exception as exc:
        logger.debug("DB load tracked positions failed ({}); using file fallback", exc)
        return None  # None signals "use file fallback"


def _db_save_positions(positions: List[Dict[str, Any]]) -> bool:
    """Upsert tracked positions into the database. Returns True on success."""
    try:
        from src.infrastructure.database import db

        session = db.get_session()
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            existing = session.execute(
                _sa_text("SELECT id FROM tracked_positions WHERE instance_id = :iid"),
                {"iid": _INSTANCE_ID},
            ).fetchone()
            if existing:
                session.execute(
                    _sa_text(
                        "UPDATE tracked_positions "
                        "SET positions_json = :pj, updated_at = :ua "
                        "WHERE instance_id = :iid"
                    ),
                    {"pj": json.dumps(positions), "ua": now, "iid": _INSTANCE_ID},
                )
            else:
                session.execute(
                    _sa_text(
                        "INSERT INTO tracked_positions (instance_id, positions_json, updated_at) "
                        "VALUES (:iid, :pj, :ua)"
                    ),
                    {"iid": _INSTANCE_ID, "pj": json.dumps(positions), "ua": now},
                )
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as exc:
        logger.debug("DB save tracked positions failed ({}); falling back to file", exc)
        return False


def _sa_text(sql: str):
    from sqlalchemy import text

    return text(sql)


# ---------------------------------------------------------------------------
# File I/O (fallback)
# ---------------------------------------------------------------------------


def position_identity(position: Dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(position.get("order_id_m1", "")),
        str(position.get("order_id_m2", "")),
        str(position.get("market_1", "")),
        str(position.get("market_2", "")),
    )


def _read_bot_agents_unlocked() -> List[Dict[str, Any]]:
    try:
        with BOT_AGENTS_PATH.open("r", encoding="utf-8") as open_positions_file:
            loaded = json.load(open_positions_file)
        return loaded if isinstance(loaded, list) else []
    except Exception:
        logger.debug("No existing {} found; starting fresh", BOT_AGENTS_PATH)
        return []


def _write_bot_agents_unlocked(positions: List[Dict[str, Any]]) -> None:
    BOT_AGENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = BOT_AGENTS_PATH.with_name(f".{BOT_AGENTS_PATH.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(positions, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, BOT_AGENTS_PATH)


@contextlib.contextmanager
def _bot_agents_file_lock():
    BOT_AGENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = BOT_AGENTS_PATH.with_name(f".{BOT_AGENTS_PATH.name}.lock")
    with lock_path.open("a", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def load_tracked_positions() -> List[Dict[str, Any]]:
    async with _BOT_AGENTS_ASYNC_LOCK:
        db_result = _db_load_positions()
        if db_result is not None:
            return db_result
        # DB unavailable — fall through to file
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                return _read_bot_agents_unlocked()


async def append_tracked_position(position: Dict[str, Any]) -> None:
    async with _BOT_AGENTS_ASYNC_LOCK:
        # Load current state (DB preferred)
        db_result = _db_load_positions()
        if db_result is not None:
            positions = db_result
        else:
            with _BOT_AGENTS_THREAD_LOCK:
                with _bot_agents_file_lock():
                    positions = _read_bot_agents_unlocked()

        position_ids = {position_identity(item) for item in positions}
        if position_identity(position) not in position_ids:
            positions.append(position)

        # Write to both DB and file
        _db_save_positions(positions)
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                _write_bot_agents_unlocked(positions)


async def save_processed_positions(
    original_positions: List[Dict[str, Any]],
    remaining_positions: List[Dict[str, Any]],
) -> None:
    """Atomically save processed positions while preserving concurrent appends."""
    processed_ids = {position_identity(item) for item in original_positions}
    async with _BOT_AGENTS_ASYNC_LOCK:
        # Load current state to capture any concurrent additions
        db_current = _db_load_positions()
        if db_current is not None:
            current_positions = db_current
        else:
            with _BOT_AGENTS_THREAD_LOCK:
                with _bot_agents_file_lock():
                    current_positions = _read_bot_agents_unlocked()

        concurrent_additions = [
            item
            for item in current_positions
            if position_identity(item) not in processed_ids
        ]
        merged = remaining_positions + concurrent_additions

        # Write to both DB and file
        if merged:
            _db_save_positions(merged)
        else:
            _db_delete_positions()
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                _write_bot_agents_unlocked(merged)


def _db_delete_positions() -> bool:
    """Delete the tracked positions row for this instance. Returns True on success."""
    try:
        from src.infrastructure.database import db

        session = db.get_session()
        try:
            session.execute(
                _sa_text("DELETE FROM tracked_positions WHERE instance_id = :iid"),
                {"iid": _INSTANCE_ID},
            )
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as exc:
        logger.debug(
            "DB delete tracked positions failed ({}); falling back to file", exc
        )
        return False


async def clear_tracked_positions() -> None:
    """Atomically clear tracked positions for the current instance."""
    async with _BOT_AGENTS_ASYNC_LOCK:
        # Delete DB row (no row = no positions) and clear file
        _db_delete_positions()
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                _write_bot_agents_unlocked([])
