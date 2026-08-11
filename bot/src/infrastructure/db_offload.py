"""Offload blocking (synchronous) DB work off the asyncio event loop.

The bot service uses synchronous SQLAlchemy sessions everywhere; every
``session.query/execute/commit`` inside an ``async def`` route handler would
otherwise run on the event loop and stall every in-flight request and WebSocket
broadcast on that worker. ``run_db`` moves such work to a worker thread via
Starlette's threadpool.

Load-bearing invariant: the callable passed to ``run_db`` MUST own its full
``Session`` lifecycle — open it (via ``db.get_session()``), use it, and close it
in a ``finally`` — so no ``Session`` ever crosses the thread boundary. Sessions
are factory-created (``sessionmaker``, not scoped/thread-local) and are not
thread-safe, so a single worker thread must own one for its entire lifetime.
Return plain data (DTOs / dicts) across the seam, never live ORM objects that
could lazy-load back on the event loop.
"""

from typing import Any, Callable

from starlette.concurrency import run_in_threadpool


async def run_db(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a blocking (sync) DB callable in a worker thread, off the event loop.

    The callable must own its full ``Session`` lifecycle (open, use, close) so no
    session is shared across threads. Returns the callable's result; any exception
    it raises propagates to the caller.
    """
    return await run_in_threadpool(func, *args, **kwargs)
