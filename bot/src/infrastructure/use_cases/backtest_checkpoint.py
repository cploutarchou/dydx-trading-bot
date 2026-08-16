"""Durable per-pair checkpoints for long-running backtests.

A checkpoint captures everything needed to resume an interrupted run without
re-processing completed pairs:

- the post-prioritization ordered pair plan (``pair_plan``),
- how many leading pairs of that plan are complete (``completed_pairs_count``),
- the accumulated per-pair outputs (trades / snapshots / daily PnL) and the
  running scalar accumulators they feed.

Pairs are independent and every final metric is a pure function of the union of
per-pair outputs plus ``initial_balance``, so a resumed run produces the same
result as an uninterrupted one (trade ids keep their sequence because the
simulation offset continues from ``len(all_trades)``).

Storage rides the existing backtest artifact store (local dir or MinIO) as a
self-contained ``backtests/<run_id>/checkpoint.json`` sidecar. The file is
written at the same cadence as the heavy progress persist and is deleted when a
run reaches a terminal ``completed``/``cancelled`` state; ``failed``/``timeout``
runs keep it so transient retries and startup auto-recovery can resume.

All helpers are fail-open: any missing, corrupt, or mismatched checkpoint logs a
warning and yields ``None`` so execution falls back to today's from-scratch
behavior. Checkpointing is gated by ``BACKTEST_CHECKPOINT_ENABLED`` (default
on) as the single rollback lever.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.storage.artifacts import ArtifactStore

logger = logging.getLogger(__name__)

CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_FILE_NAME = "checkpoint.json"

# Narrow failure envelope shared by every checkpoint IO helper: filesystem
# errors, malformed JSON/payloads (JSONDecodeError is a ValueError), and
# strict-mode MinIO rejections (RuntimeError). Never broad — the ratchet gates.
_CHECKPOINT_IO_ERRORS = (OSError, ValueError, RuntimeError, TypeError)

_checkpoint_store: Optional[ArtifactStore] = None


def checkpoints_enabled() -> bool:
    """``BACKTEST_CHECKPOINT_ENABLED`` (default on) — single rollback lever."""
    raw = os.getenv("BACKTEST_CHECKPOINT_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def get_checkpoint_store() -> ArtifactStore:
    """Resolve (and cache) the shared backtest artifact store."""
    global _checkpoint_store
    if _checkpoint_store is None:
        _checkpoint_store = BacktestRepository.build_artifact_store()
    return _checkpoint_store


def reset_checkpoint_store() -> None:
    """Reset the cached store (tests / env changes)."""
    global _checkpoint_store
    _checkpoint_store = None


def _checkpoint_key(run_id: str) -> str:
    clean_run_id = str(run_id).strip().strip("/")
    if not clean_run_id or "/" in clean_run_id or ".." in clean_run_id:
        raise ValueError(f"invalid run id for checkpoint key: {run_id!r}")
    return f"backtests/{clean_run_id}/{CHECKPOINT_FILE_NAME}"


def _sanitize_pair_plan(pair_plan: Sequence[Sequence[str]]) -> List[List[str]]:
    sanitized: List[List[str]] = []
    for pair in pair_plan:
        if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)):
            raise ValueError("pair plan entries must be two-element sequences")
        items = list(pair)
        if len(items) != 2 or not all(isinstance(m, str) and m for m in items):
            raise ValueError("pair plan entries must be [market_a, market_b] strings")
        sanitized.append(items)
    if not sanitized:
        raise ValueError("pair plan must not be empty")
    return sanitized


def build_checkpoint(
    *,
    run_id: str,
    payload_hash: str,
    pair_plan: Sequence[Sequence[str]],
    completed_pairs_count: int,
    trades: Sequence[Dict[str, Any]],
    position_snapshots: Sequence[Dict[str, Any]],
    daily_pnl: Dict[str, float],
    running_total_pnl: float,
    running_winners: int,
    running_gross_profit: float,
    running_gross_loss: float,
) -> Dict[str, Any]:
    """Build a schema-v1 checkpoint payload (pure)."""
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "run_id": str(run_id),
        "payload_hash": str(payload_hash),
        "completed_pairs_count": int(completed_pairs_count),
        "pair_plan": _sanitize_pair_plan(pair_plan),
        "accumulators": {
            "trades": [dict(trade) for trade in trades],
            "position_snapshots": [dict(snap) for snap in position_snapshots],
            "daily_pnl": {str(day): float(pnl) for day, pnl in daily_pnl.items()},
            "running_total_pnl": float(running_total_pnl),
            "running_winners": int(running_winners),
            "running_gross_profit": float(running_gross_profit),
            "running_gross_loss": float(running_gross_loss),
        },
    }


def save_checkpoint(store: ArtifactStore, payload: Dict[str, Any]) -> bool:
    """Persist the checkpoint. Best-effort: never raises, returns success."""
    try:
        run_id = str(payload["run_id"])
        store.put_json(_checkpoint_key(run_id), payload)
        return True
    except _CHECKPOINT_IO_ERRORS as exc:
        logger.warning(
            "Failed to persist backtest checkpoint for run %s: %s",
            payload.get("run_id"),
            exc,
        )
        return False


def _coerce_accumulators(
    raw: Any,
) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, float]]]:
    if not isinstance(raw, dict):
        return None
    trades = raw.get("trades")
    snapshots = raw.get("position_snapshots")
    daily = raw.get("daily_pnl")
    if not isinstance(trades, list) or not isinstance(snapshots, list):
        return None
    if not all(isinstance(trade, dict) for trade in trades):
        return None
    if not all(isinstance(snap, dict) for snap in snapshots):
        return None
    if not isinstance(daily, dict):
        return None
    coerced_daily: Dict[str, float] = {}
    for day, pnl in daily.items():
        if not isinstance(day, str):
            return None
        coerced_daily[day] = float(pnl)  # TypeError/ValueError on malformed
    return (
        [dict(trade) for trade in trades],
        [dict(snap) for snap in snapshots],
        coerced_daily,
    )


def load_checkpoint(
    store: ArtifactStore,
    run_id: str,
    *,
    expected_payload_hash: str,
) -> Optional[Dict[str, Any]]:
    """Load and validate the checkpoint for ``run_id``.

    Returns a normalized checkpoint dict or ``None`` (missing, corrupt, or
    mismatched — each logged at warning so operators can see why a resume was
    skipped). Never raises.
    """
    key = ""
    try:
        key = _checkpoint_key(run_id)
        if not store.exists(key):
            return None
        payload = json.loads(store.read_text(key))
    except _CHECKPOINT_IO_ERRORS as exc:
        logger.warning(
            "Backtest checkpoint for run %s unreadable (%s); starting fresh",
            run_id,
            exc,
        )
        return None

    def _invalid(reason: str) -> None:
        logger.warning(
            "Backtest checkpoint for run %s ignored (%s); starting fresh",
            run_id,
            reason,
        )

    if not isinstance(payload, dict):
        _invalid("payload is not an object")
        return None
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        _invalid(f"schema version {payload.get('schema_version')!r}")
        return None
    if payload.get("run_id") != str(run_id):
        _invalid("run id mismatch")
        return None
    if not isinstance(payload.get("payload_hash"), str):
        _invalid("missing payload hash")
        return None
    if payload["payload_hash"] != str(expected_payload_hash):
        _invalid("payload hash mismatch (request changed since checkpoint)")
        return None

    try:
        pair_plan = _sanitize_pair_plan(payload.get("pair_plan") or ())
    except ValueError as exc:
        _invalid(str(exc))
        return None

    try:
        completed = int(payload.get("completed_pairs_count") or 0)
    except (TypeError, ValueError):
        _invalid("completed_pairs_count not an integer")
        return None
    if completed < 0 or completed > len(pair_plan):
        _invalid("completed_pairs_count out of range")
        return None

    try:
        accumulators = _coerce_accumulators(payload.get("accumulators"))
    except (TypeError, ValueError):
        accumulators = None
    if accumulators is None:
        _invalid("accumulators malformed")
        return None
    trades, snapshots, daily_pnl = accumulators

    scalars: Dict[str, float] = {}
    raw_scalar = payload["accumulators"]
    for field in (
        "running_total_pnl",
        "running_gross_profit",
        "running_gross_loss",
    ):
        try:
            scalars[field] = float(raw_scalar[field])
        except (KeyError, TypeError, ValueError):
            _invalid(f"accumulator {field} malformed")
            return None
    try:
        running_winners = int(raw_scalar["running_winners"])
    except (KeyError, TypeError, ValueError):
        _invalid("accumulator running_winners malformed")
        return None

    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "run_id": str(run_id),
        "payload_hash": payload["payload_hash"],
        "pair_plan": pair_plan,
        "completed_pairs_count": completed,
        "trades": trades,
        "position_snapshots": snapshots,
        "daily_pnl": daily_pnl,
        "running_total_pnl": scalars["running_total_pnl"],
        "running_winners": running_winners,
        "running_gross_profit": scalars["running_gross_profit"],
        "running_gross_loss": scalars["running_gross_loss"],
    }


def delete_checkpoint(store: ArtifactStore, run_id: str) -> bool:
    """Best-effort checkpoint removal after terminal states. Never raises."""
    try:
        return bool(store.delete(_checkpoint_key(run_id)))
    except _CHECKPOINT_IO_ERRORS as exc:
        logger.warning(
            "Failed to delete backtest checkpoint for run %s: %s", run_id, exc
        )
        return False
