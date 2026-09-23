"""Durable "entries halted" latch for the subaccount a runtime trades on.

When an emergency close fails, a leg may be open with no hedge. Opening more
pairs on top of that adds exposure the bot cannot account for, so new entries
stop until an operator has looked at the account and cleared the latch. Exits
and risk controls are not affected.

The doubt is about a subaccount's exposure, so that is the latch's scope:
``(network, address, subaccount_number)``. It is kept in two places.

* ``entry_halts`` table: survives a restart or a replaced pod, is visible to
  the API, and records who cleared it and why. Used by managed runtimes (the
  ones ``BotInstanceManager`` starts, which always have a database).
* A file next to the instance's tracked-position file: written first, so the
  latch holds even if the database is unreachable at that moment. It is the
  only store for a standalone run (``BOT_INSTANCE_ID`` unset).

Reading fails closed for managed runtimes: if the table cannot be read, the
state is unknown and entries wait for the next cycle.

Clearing it, after the account has been verified on the exchange, is done from
the UI / API (``POST /api/v1/bots/{instance_id}/entry-halt/clear``) or, for a
standalone run:

    python -m src.trading.entry_halt --clear
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import text as _sa_text
from sqlalchemy.exc import SQLAlchemyError

from src.trading import bot_agents_state

HALT_FILE_NAME = "entries_halted.json"
STANDALONE_INSTANCE_ID = "default"
UNVERIFIED_REASON = "entry halt state could not be verified"

# ``details["kind"]`` says why entries stopped. Halts recorded before kinds
# existed have none and were all set after a failed emergency close.
KIND_UNHEDGED_EXPOSURE = "unhedged_exposure"
KIND_MAX_DRAWDOWN = "max_drawdown"


@dataclass(frozen=True)
class HaltScope:
    """The subaccount whose exposure is in doubt, and who is asking."""

    instance_id: str
    network: str
    address: str
    subaccount_number: int

    def __post_init__(self) -> None:
        # The runtime that sets a halt and the API that shows and clears it build
        # the scope separately; one spelling keeps them on the same row.
        object.__setattr__(self, "network", str(self.network or "").strip().lower())
        object.__setattr__(self, "address", str(self.address or "").strip().lower())
        object.__setattr__(self, "subaccount_number", int(self.subaccount_number or 0))


_runtime_scope: Optional[HaltScope] = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def set_runtime_scope(scope: Optional[HaltScope]) -> None:
    """Declare the subaccount this process trades on.

    A managed runtime takes its network and wallet from its own instance
    config, not from ``src.constants`` (the global config), so it has to say
    which subaccount it is before the latch is read or set.
    """
    global _runtime_scope
    _runtime_scope = scope


def current_scope() -> HaltScope:
    """Scope of the runtime this process is."""
    if _runtime_scope is not None:
        return _runtime_scope

    from src import constants

    return HaltScope(
        instance_id=bot_agents_state._INSTANCE_ID,
        network=str(constants.MARKET_DATA_MODE).lower(),
        address=str(constants.DYDX_ADDRESS or ""),
        subaccount_number=int(constants.SUBACCOUNT_NUMBER),
    )


def _uses_database(scope: HaltScope) -> bool:
    return scope.instance_id != STANDALONE_INSTANCE_ID


# --------------------------------------------------------------------------- file


def halt_file_for(instance_id: str) -> Path:
    directory = bot_agents_state.BOT_AGENTS_PATH.parent
    if instance_id == STANDALONE_INSTANCE_ID:
        return directory / HALT_FILE_NAME
    return directory / f"entries_halted_{instance_id}.json"


def _write_halt_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(tmp_path, path)


def halt_kind(payload: Optional[Dict[str, Any]]) -> str:
    """Why a halt was set: ``details["kind"]``, else the one cause that existed
    before kinds were recorded."""
    details = payload.get("details") if isinstance(payload, dict) else None
    kind = details.get("kind") if isinstance(details, dict) else None
    return str(kind).strip() if kind else KIND_UNHEDGED_EXPOSURE


def _read_halt_file(path: Path) -> Optional[Dict[str, Any]]:
    """An unreadable latch file still halts entries: the file's existence is the
    signal, and failing open here would defeat its purpose."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Entry halt latch at {} is unreadable: {}", path, exc)
        return {"reason": "unreadable entry halt latch", "details": {}}
    return payload if isinstance(payload, dict) else {"reason": str(payload)}


# ----------------------------------------------------------------------- database


def _row_to_payload(row: Any) -> Dict[str, Any]:
    try:
        details = json.loads(row.details) if row.details else {}
    except (TypeError, ValueError):
        details = {"raw": str(row.details)}
    halted_at = row.halted_at
    return {
        "id": int(row.id),
        "instance_id": row.instance_id,
        "network": row.network,
        "address": row.address,
        "subaccount_number": int(row.subaccount_number),
        "reason": row.reason,
        "details": details if isinstance(details, dict) else {"raw": details},
        "halted_at": (
            halted_at.isoformat() if hasattr(halted_at, "isoformat") else str(halted_at)
        ),
    }


def _db_active_halt(scope: HaltScope) -> Optional[Dict[str, Any]]:
    """Active halt row for the scope. Raises when the table cannot be read."""
    from src.infrastructure.database import db

    session = db.get_session()
    try:
        row = session.execute(
            _sa_text(
                "SELECT id, instance_id, network, address, subaccount_number, "
                "reason, details, halted_at FROM entry_halts "
                "WHERE network = :network AND address = :address "
                "AND subaccount_number = :subaccount AND cleared_at IS NULL "
                "ORDER BY id LIMIT 1"
            ),
            {
                "network": scope.network,
                "address": scope.address,
                "subaccount": scope.subaccount_number,
            },
        ).fetchone()
        return _row_to_payload(row) if row is not None else None
    finally:
        session.close()


def _db_insert_halt(scope: HaltScope, reason: str, details: Dict[str, Any]) -> None:
    """Record the halt unless the scope already has an active one."""
    from src.infrastructure.database import db

    session = db.get_session()
    try:
        session.execute(
            _sa_text(
                "INSERT INTO entry_halts (instance_id, network, address, "
                "subaccount_number, reason, details, halted_at) "
                "SELECT :instance_id, :network, :address, :subaccount, :reason, "
                ":details, :halted_at WHERE NOT EXISTS ("
                "SELECT 1 FROM entry_halts WHERE network = :network "
                "AND address = :address AND subaccount_number = :subaccount "
                "AND cleared_at IS NULL)"
            ),
            {
                "instance_id": scope.instance_id,
                "network": scope.network,
                "address": scope.address,
                "subaccount": scope.subaccount_number,
                "reason": reason,
                "details": json.dumps(details, default=str),
                "halted_at": _utc_now(),
            },
        )
        session.commit()
    finally:
        session.close()


def _db_clear_halts(scope: HaltScope, cleared_by: str, note: str) -> int:
    from src.infrastructure.database import db

    session = db.get_session()
    try:
        result = session.execute(
            _sa_text(
                "UPDATE entry_halts SET cleared_at = :cleared_at, "
                "cleared_by = :cleared_by, clear_note = :note "
                "WHERE network = :network AND address = :address "
                "AND subaccount_number = :subaccount AND cleared_at IS NULL"
            ),
            {
                "cleared_at": _utc_now(),
                "cleared_by": cleared_by[:128],
                "note": note,
                "network": scope.network,
                "address": scope.address,
                "subaccount": scope.subaccount_number,
            },
        )
        session.commit()
        return int(getattr(result, "rowcount", 0) or 0)
    finally:
        session.close()


# ------------------------------------------------------------------------- public


def halt_entries(
    reason: str,
    details: Optional[Dict[str, Any]] = None,
    *,
    scope: Optional[HaltScope] = None,
) -> None:
    """Set the latch. Keeps the first reason if it is already set.

    The file is written first so the latch holds even when the database is
    down. Raises only if neither store could take it.
    """
    scope = scope or current_scope()
    payload = {
        "halted_at": _utc_now().isoformat(),
        "reason": reason,
        "details": details or {},
        "instance_id": scope.instance_id,
        "network": scope.network,
        "address": scope.address,
        "subaccount_number": scope.subaccount_number,
    }

    stored = False
    failures = []
    path = halt_file_for(scope.instance_id)
    try:
        if not path.exists():
            _write_halt_file(path, payload)
        stored = True
    except OSError as exc:
        failures.append(f"latch file: {exc}")
        logger.error("Could not write the entry halt latch file {}: {}", path, exc)

    if _uses_database(scope):
        try:
            _db_insert_halt(scope, reason, details or {})
            stored = True
        # Broad on purpose: this runs in the emergency path just before the
        # critical alert, and the file above already holds the latch.
        except Exception as exc:
            failures.append(f"database: {exc}")
            logger.error(
                "Could not record the entry halt in the database ({}); the latch "
                "file holds it until this pod is replaced",
                exc,
            )

    if not stored:
        raise RuntimeError(
            f"the entry halt could NOT be recorded ({'; '.join(failures)})"
        )
    logger.critical(
        "New entries halted for {} subaccount {} ({}): {}",
        scope.network,
        scope.subaccount_number,
        scope.instance_id,
        reason,
    )


def entries_halted(scope: Optional[HaltScope] = None) -> Optional[Dict[str, Any]]:
    """Return the latch payload when entries are halted, else ``None``.

    Fails closed: a managed runtime that cannot read the table does not know
    whether it was halted before a restart, so it reports an unverified halt
    and opens nothing this cycle.
    """
    scope = scope or current_scope()
    from_file = _read_halt_file(halt_file_for(scope.instance_id))
    if from_file is not None:
        return from_file
    if not _uses_database(scope):
        return None
    try:
        return _db_active_halt(scope)
    except (SQLAlchemyError, OSError, RuntimeError) as exc:
        logger.warning("Entry halt state could not be read: {}", exc)
        return {"reason": UNVERIFIED_REASON, "details": {}, "unverified": True}


def clear_entry_halt(
    *,
    cleared_by: str = "operator",
    note: str = "",
    scope: Optional[HaltScope] = None,
) -> int:
    """Operator reset. Returns how many halts were cleared.

    The database is cleared before the file: if the database is unreachable the
    file stays, so the halt is never half-cleared into an unrecorded state.

    Clearing a drawdown halt also restarts the drawdown measurement from the
    equity the runtime sees next; otherwise the next cycle would measure from
    the old peak and halt again at once. That reset runs first, so a failed
    reset leaves the halt in place.
    """
    scope = scope or current_scope()
    path = halt_file_for(scope.instance_id)
    kinds: set[str] = set()
    file_payload = _read_halt_file(path)
    if file_payload is not None:
        kinds.add(halt_kind(file_payload))
    if _uses_database(scope):
        active = _db_active_halt(scope)
        if active is not None:
            kinds.add(halt_kind(active))
    if KIND_MAX_DRAWDOWN in kinds:
        from src.trading import drawdown_guard

        drawdown_guard.reset_baselines(scope)

    cleared = 0
    if _uses_database(scope):
        cleared += _db_clear_halts(scope, cleared_by, note)

    if path.exists():
        path.unlink()
        cleared = max(cleared, 1)

    if cleared:
        logger.warning(
            "Entry halt for {} subaccount {} cleared by {}{}",
            scope.network,
            scope.subaccount_number,
            cleared_by,
            f": {note}" if note else "",
        )
    return cleared


def _main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--clear", action="store_true", help="remove the latch")
    parser.add_argument("--note", default="", help="what was verified")
    args = parser.parse_args()
    if args.clear:
        cleared = clear_entry_halt(cleared_by="cli", note=args.note)
        print("cleared" if cleared else "no latch set")
        return 0
    state = entries_halted()
    print(
        json.dumps(state, indent=2, default=str) if state else "entries are not halted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
