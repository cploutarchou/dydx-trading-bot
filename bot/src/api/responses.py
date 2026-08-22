"""Shared API response helpers.

Extracted from ``src/api/server.py`` so that route modules (e.g.
``src/api/v1/*.py``) can build the standardized envelope without importing from
the monolithic server module (which would create a circular import: server
imports the router, the router imports the helper).

This is a **leaf** module: it depends only on the stdlib, FastAPI response
primitives, and ``src.shared.time_utils`` — safe to import from any layer.
"""

from __future__ import annotations

import contextvars
from typing import Any, Dict, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from src.shared.time_utils import utc_now_iso

# Per-request trace id. Set by the trace-logging middleware in ``src/api/server.py``
# (``trace_id_ctx.set(...)``) and read here by ``api_response``. Kept in this shared
# module so both server.py and extracted routers reference the same ContextVar object.
trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)

# Never expose raw exceptions/DB internals in client-facing 5xx responses.
INTERNAL_ERROR_MESSAGE = "Internal server error"


def api_response(
    success: bool,
    data: Any = None,
    message: str = "",
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    """Standardized API response envelope.

    Returns a ``JSONResponse`` shaped as
    ``{success, message, data, timestamp, trace_id}``. For any ``status_code >= 500``
    the message is replaced with :data:`INTERNAL_ERROR_MESSAGE` so internal details
    are never leaked to clients.
    """
    if status_code >= 500:
        message = INTERNAL_ERROR_MESSAGE
    trace_id = trace_id_ctx.get()
    response_data = {
        "success": success,
        "message": message,
        "data": data,
        "timestamp": utc_now_iso(),
        "trace_id": trace_id,
    }
    response = JSONResponse(
        content=jsonable_encoder(response_data),
        status_code=status_code,
    )
    for header_name, header_value in (headers or {}).items():
        response.headers[header_name] = str(header_value)
    return response


__all__ = ["INTERNAL_ERROR_MESSAGE", "api_response", "trace_id_ctx"]
