"""Shared per-request endpoint timing/observability helpers.

Extracted from ``src/api/server.py`` so that route modules (e.g.
``src/api/v1/celery_admin.py``) can emit the same ``endpoint_perf`` logs and
``X-Endpoint-Duration-Ms`` headers without importing from the monolithic server
module (which would create a circular import).

Leaf module: depends only on the stdlib and loguru — safe to import from any layer.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from loguru import logger


def payload_size_bytes(payload: Any) -> int:
    """Best-effort serialized size of a response payload in bytes (-1 on failure)."""
    try:
        return len(json.dumps(payload, default=str, separators=(",", ":")))
    except Exception:
        return -1


def log_endpoint_timing(
    endpoint: str,
    started_at: float,
    payload: Any,
    *,
    cache_hit: bool = False,
    payload_items: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit a structured ``endpoint_perf`` log line for a request."""
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    size_bytes = payload_size_bytes(payload)
    details: Dict[str, Any] = {
        "endpoint": endpoint,
        "duration_ms": round(elapsed_ms, 2),
        "cache_hit": cache_hit,
        "payload_bytes": size_bytes,
    }
    if payload_items is not None:
        details["payload_items"] = int(payload_items)
    if extra:
        details.update(extra)

    logger.info(
        "endpoint_perf endpoint={} duration_ms={} cache_hit={} payload_bytes={} payload_items={} details={}",
        details["endpoint"],
        details["duration_ms"],
        details["cache_hit"],
        details["payload_bytes"],
        details.get("payload_items", -1),
        details,
    )


def endpoint_perf_headers(
    started_at: float, *, cache_hit: Optional[bool] = None
) -> Dict[str, str]:
    """Build response headers carrying endpoint duration (and optional cache-hit)."""
    elapsed_ms = max(0.0, (time.perf_counter() - started_at) * 1000.0)
    headers: Dict[str, str] = {"X-Endpoint-Duration-Ms": f"{elapsed_ms:.2f}"}
    if cache_hit is not None:
        headers["X-Cache-Hit"] = "1" if cache_hit else "0"
    return headers


__all__ = ["endpoint_perf_headers", "log_endpoint_timing", "payload_size_bytes"]
