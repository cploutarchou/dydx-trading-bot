"""Concurrency-safe helpers for per-instance tracked-position state."""

import asyncio
import contextlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


def _resolve_bot_agents_path() -> Path:
    configured_path = os.getenv("BOT_AGENTS_FILE", "bot_agents.json")
    instance_id = os.getenv("BOT_INSTANCE_ID", "default")
    resolved = configured_path.replace("{instance_id}", instance_id)
    path = Path(resolved)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


BOT_AGENTS_PATH = _resolve_bot_agents_path()
_BOT_AGENTS_ASYNC_LOCK = asyncio.Lock()
_BOT_AGENTS_THREAD_LOCK = threading.RLock()


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


async def load_tracked_positions() -> List[Dict[str, Any]]:
    async with _BOT_AGENTS_ASYNC_LOCK:
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                return _read_bot_agents_unlocked()


async def append_tracked_position(position: Dict[str, Any]) -> None:
    async with _BOT_AGENTS_ASYNC_LOCK:
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                positions = _read_bot_agents_unlocked()
                position_ids = {position_identity(item) for item in positions}
                if position_identity(position) not in position_ids:
                    positions.append(position)
                _write_bot_agents_unlocked(positions)


async def save_processed_positions(
        original_positions: List[Dict[str, Any]],
        remaining_positions: List[Dict[str, Any]],
) -> None:
    """Atomically save processed positions while preserving concurrent appends."""
    processed_ids = {position_identity(item) for item in original_positions}
    async with _BOT_AGENTS_ASYNC_LOCK:
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                current_positions = _read_bot_agents_unlocked()
                concurrent_additions = [
                    item
                    for item in current_positions
                    if position_identity(item) not in processed_ids
                ]
                _write_bot_agents_unlocked(remaining_positions + concurrent_additions)


async def clear_tracked_positions() -> None:
    """Atomically clear tracked positions for the current instance."""
    async with _BOT_AGENTS_ASYNC_LOCK:
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                _write_bot_agents_unlocked([])
