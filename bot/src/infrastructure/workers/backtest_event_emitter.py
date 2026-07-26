"""Durable backtest event emitter (Phase 2 producer side).

Emits canonical backtest lifecycle/progress events to NATS JetStream on
``backtest.event.<action>`` so a backend projector can drive the user-facing
push feed from durable transport instead of (or alongside) Redis pub/sub.

The envelope and payload shapes deliberately mirror the backend contract
(``backend/internal/nats`` Envelope and ``backend/internal/services``
BacktestEvent / BacktestEventProjector) so the backend can decode and project
bot-emitted events unchanged.

Fail-closed: any connect/publish error is logged and swallowed. Event emission
must never break backtest execution. Dormant unless NATS is enabled.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Maps the Celery task status vocabulary to the canonical event actions consumed
# by the backend projector (BacktestEventAction*). "cancelled" is projected as a
# terminal failed event with a distinct error code.
STATUS_TO_EVENT: dict[str, str] = {
    "started": "started",
    "progress": "progress",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "failed",
}

_SCHEMA_VERSION = "1"
_PRODUCER_SERVICE = "bot-worker"

# JetStream stream covering backtest lifecycle/progress events. Subjects use the
# ">" wildcard (matches nested actions too) to stay consistent with the
# bot-side consumer's BACKTEST_EVENTS config; only the bot emits events, so this
# is the single owner of the stream definition.
_EVENT_STREAM_NAME = "BACKTEST_EVENTS"
_EVENT_STREAM_SUBJECTS = ["backtest.event.>"]
_EVENT_STREAM_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days


async def _ensure_event_stream(js: Any) -> None:
    """Idempotently ensure the BACKTEST_EVENTS stream exists (limits retention)."""
    try:
        await js.stream_info(_EVENT_STREAM_NAME)
        return
    except Exception:
        pass  # Not found; create below.
    try:
        import nats.api as nats_api  # type: ignore[import-untyped]
    except Exception:
        nats_api = None
    try:
        kwargs: dict[str, Any] = {
            "name": _EVENT_STREAM_NAME,
            "subjects": _EVENT_STREAM_SUBJECTS,
            "retention": "limits",
            "storage": "file",
            "max_age": _EVENT_STREAM_MAX_AGE_SECONDS,
        }
        if nats_api is not None:
            kwargs["retention"] = nats_api.RetentionPolicy.LIMITS
            kwargs["storage"] = nats_api.StorageType.FILE
        await js.add_stream(**kwargs)
        logger.info("backtest_event_stream_created name=%s", _EVENT_STREAM_NAME)
    except Exception as exc:
        logger.debug("backtest_event_stream_ensure_failed error=%r", exc)


def _is_enabled() -> bool:
    return os.getenv("NATS_ENABLED", "true").lower() == "true" or (
            os.getenv("BOT_COMMAND_BUS_ENABLED", "true").lower() == "true"
    )


def _servers() -> list[str]:
    url = os.getenv("NATS_URL") or os.getenv("NATS_SERVER_URL") or "nats://localhost:4222"
    return [url]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_envelope(
        *,
        run_id: str,
        event: str,
        progress: float,
        current_pair: str,
        error_code: Optional[str],
        error_message: Optional[str],
) -> tuple[dict[str, Any], str]:
    """Return (envelope_dict, msg_id) for a backtest event."""
    occurred_at = _utcnow_iso()
    # Stable Msg-Id for terminal events so retries/redelivery dedupe; unique for
    # non-terminal progress events.
    if event in ("completed", "failed"):
        msg_id = f"backtest:{run_id}:{event}"
    else:
        msg_id = f"backtest:{run_id}:{event}:{uuid.uuid4()}"

    payload = {
        "run_id": run_id,
        "event": event,
        "progress": float(progress),
        "phase": event,
        "current_pair": current_pair,
        "error_code": error_code,
        "error_message": error_message,
        "occurred_at": occurred_at,
    }
    envelope = {
        "message_id": msg_id,
        "idempotency_key": msg_id,
        "correlation_id": f"backtest-run-{run_id}",
        "causation_id": f"backtest:{run_id}",
        "owner_type": "backtest",
        "owner_id": run_id,
        "occurred_at": occurred_at,
        "producer_service": _PRODUCER_SERVICE,
        "schema_version": _SCHEMA_VERSION,
        "subject": f"backtest.event.{event}",
        "payload": payload,
    }
    return envelope, msg_id


async def publish_backtest_event(
        *,
        run_id: str,
        status: str,
        progress: float = 0.0,
        current_pair: str = "",
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
) -> Optional[str]:
    """Publish a durable backtest event to JetStream. Returns the msg_id or None.

    Fail-closed: never raises into the caller. Returns None when disabled or on
    any publish error.
    """
    if not _is_enabled():
        return None
    event = STATUS_TO_EVENT.get(status)
    if event is None:
        logger.debug("backtest_event_emit_skip unknown_status=%s run_id=%s", status, run_id)
        return None
    # Terminal failed events require an error code per the projector contract.
    if event == "failed" and not error_code:
        error_code = "BACKTEST_FAILED"

    envelope, msg_id = _build_envelope(
        run_id=run_id,
        event=event,
        progress=progress,
        current_pair=current_pair,
        error_code=error_code,
        error_message=error_message,
    )
    subject = envelope["subject"]
    data = json.dumps(envelope).encode()

    try:
        import nats  # type: ignore[import-untyped]
    except Exception as exc:  # pragma: no cover - exercised when nats.py absent
        logger.debug("backtest_event_emit_skip nats_unavailable error=%r", exc)
        return None

    nc = None
    try:
        nc = await nats.connect(servers=_servers(), connect_timeout=5, max_reconnect_attempts=-1)
        js = nc.jetstream()
        await _ensure_event_stream(js)
        await js.publish(subject, data, headers={"Msg-Id": msg_id})
        logger.info(
            "backtest_event_emitted run_id=%s event=%s subject=%s msg_id=%s",
            run_id, event, subject, msg_id,
        )
        return msg_id
    except Exception as exc:
        logger.debug("backtest_event_emit_failed run_id=%s event=%s error=%r", run_id, event, exc)
        return None
    finally:
        if nc is not None:
            try:
                await nc.drain()
            except Exception:
                pass


def emit_backtest_event_sync(
        *,
        run_id: str,
        status: str,
        progress: float = 0.0,
        current_pair: str = "",
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
) -> Optional[str]:
    """Sync wrapper for callers not already running an asyncio loop.

    Each call runs a fresh event loop (a short-lived connection). Use the async
    ``publish_backtest_event`` directly from code already inside a loop.
    """
    try:
        return asyncio.run(
            publish_backtest_event(
                run_id=run_id,
                status=status,
                progress=progress,
                current_pair=current_pair,
                error_code=error_code,
                error_message=error_message,
            )
        )
    except RuntimeError:
        # Already inside a running loop (rare for this sync wrapper): skip
        # rather than risk nesting loops.
        logger.debug("backtest_event_emit_sync_skip nested_loop run_id=%s", run_id)
        return None


__all__ = [
    "STATUS_TO_EVENT",
    "publish_backtest_event",
    "emit_backtest_event_sync",
]
