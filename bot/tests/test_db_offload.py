"""Invariant tests for the DB offload seam (``src.infrastructure.db_offload``).

These pin the two properties that make the offload safe and correct:

1. The callable runs in a **different thread** than the awaiting event loop (so
   blocking sync DB work genuinely leaves the loop responsive).
2. The return value propagates, and any exception (including ``HTTPException``)
   propagates, so error-handling at the handler level is unchanged.

``run_db`` is a thin wrapper over ``starlette.concurrency.run_in_threadpool``;
these tests guard the wrapper's contract rather than Starlette's internals.
"""

import asyncio
import threading

import pytest
from fastapi import HTTPException

from src.infrastructure.db_offload import run_db


def test_run_db_executes_off_the_event_loop_thread():
    """The callable must run in a worker thread, not on the event loop thread."""
    loop_thread = threading.get_ident()
    seen = {}

    def record_thread():
        seen["worker"] = threading.get_ident()
        return "ok"

    result = asyncio.run(run_db(record_thread))

    assert result == "ok"
    assert seen["worker"] != loop_thread


def test_run_db_passes_args_and_returns_value():
    def add(a, b, c=0):
        return a + b + c

    assert asyncio.run(run_db(add, 1, 2, c=3)) == 6


def test_run_db_propagates_exception():
    def boom():
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        asyncio.run(run_db(boom))


def _raise_http_exception():
    raise HTTPException(status_code=404)


def test_run_db_propagates_http_exception():
    """HTTPExceptions raised in the worker propagate so handlers/FastAPI map them."""
    with pytest.raises(HTTPException) as exc:
        asyncio.run(run_db(_raise_http_exception))
    assert exc.value.status_code == 404
