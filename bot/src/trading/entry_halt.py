"""Persisted "entries halted" latch for one trading instance.

When an emergency close fails, a leg may be open with no hedge. Opening more
pairs on top of that adds exposure the bot cannot account for, so new entries
stop until an operator has looked at the account and cleared the latch. Exits
and risk controls are not affected.

The latch lives next to the instance's tracked-position file, so it is scoped
to the instance and survives a restart.

Clearing it, after the account has been verified on the exchange:

    python -m src.trading.entry_halt --clear
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from src.trading import bot_agents_state

HALT_FILE_NAME = "entries_halted.json"


def _halt_path() -> Path:
    return bot_agents_state.BOT_AGENTS_PATH.with_name(HALT_FILE_NAME)


def halt_entries(reason: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Set the latch. Keeps the first reason if it is already set."""
    path = _halt_path()
    if path.exists():
        return
    payload = {
        "halted_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "details": details or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(tmp_path, path)
    logger.critical("New entries halted for this instance: {}", reason)


def entries_halted() -> Optional[Dict[str, Any]]:
    """Return the latch payload when entries are halted, else ``None``.

    An unreadable latch file still halts entries: the file's existence is the
    signal, and failing open here would defeat its purpose.
    """
    path = _halt_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Entry halt latch at {} is unreadable: {}", path, exc)
        return {"reason": "unreadable entry halt latch", "details": {}}
    return payload if isinstance(payload, dict) else {"reason": str(payload)}


def clear_entry_halt() -> bool:
    """Operator reset. Returns True when a latch was removed."""
    path = _halt_path()
    if not path.exists():
        return False
    path.unlink()
    logger.warning("Entry halt latch cleared by operator")
    return True


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--clear", action="store_true", help="remove the latch")
    args = parser.parse_args()
    if args.clear:
        print("cleared" if clear_entry_halt() else "no latch set")
        return 0
    state = entries_halted()
    print(json.dumps(state, indent=2) if state else "entries are not halted")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
