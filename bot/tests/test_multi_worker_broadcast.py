"""Multi-worker integration test for the cross-worker WebSocket broadcast bus.

This is the harness IMPROVEMENTS.md item #1 ("Multi-worker tests") calls for: it
boots the canonical API app as **two real Uvicorn worker processes** sharing one
Redis/Valkey and one PostgreSQL, with ``WS_BROADCAST_ENABLED=true``, and proves
the property the unit suite cannot — that a ``broadcast_to_bot`` emitted on
worker A is delivered to a WebSocket client attached to worker B, exactly once,
without looping back.

Why opt-in: the app lifespan fail-safes without a reachable PostgreSQL (SQLite
is not a supported dialect), so this module needs real infrastructure. It skips
by default so `make test` stays hermetic.

Run it with::

    docker compose -f docker-compose.infra.yml up -d postgresql valkey
    make test-multiworker          # or:
    MULTIWORKER_TEST=1 .venv/bin/python -m pytest tests/test_multi_worker_broadcast.py -s

Configuration (all optional):
    MULTIWORKER_REDIS_URL     Redis/Valkey for the bus (default redis://localhost:6379/0)
    MULTIWORKER_DATABASE_URL  PostgreSQL URL the workers boot against. When set,
                              NO ephemeral database is created/dropped and the
                              workers run Alembic migrations against that URL —
                              point it at a scratch DB. When unset, an ephemeral
                              ``dydx_bot_mwtest_<pid>`` database is created and
                              dropped on the docker-compose.infra.yml local
                              Postgres (POSTGRES_HOST/PORT/USER/PASSWORD honored).
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]

# Synthetic backtest channel. Backtest channels send a DB-light initial frame
# (`backtest_progress` with status `not_found` for an unknown run id), which
# keeps this test focused on the bus rather than realtime schema details.
_WS_CHANNEL = "backtest-multiworker-test-run"
_READY_TIMEOUT_SECONDS = 180.0
_QUIET_WINDOW_SECONDS = 1.5

# Burst/load scenario sizing (the multi-replica load coverage that gates the
# broadcast-bus Phase 2 flip). Overridable so a flaky shared runner can be
# triaged without code changes; MULTIWORKER_BURST_MESSAGES=0 skips the scenario.
_BURST_CHANNELS = max(1, int(os.getenv("MULTIWORKER_BURST_CHANNELS", "3")))
_BURST_MESSAGES = max(0, int(os.getenv("MULTIWORKER_BURST_MESSAGES", "150")))
_BURST_RECV_TIMEOUT_SECONDS = 60.0
_ERROR_METRIC_KEYS = (
    "publish_errors",
    "decode_errors",
    "dispatch_errors",
    "dispatch_timeouts",
    "reconnects",
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


if not _env_flag("MULTIWORKER_TEST"):
    pytest.skip(
        "multi-worker harness is opt-in: set MULTIWORKER_TEST=1 with Redis/Valkey "
        "and PostgreSQL reachable (see `make test-multiworker` and the module "
        "docstring in tests/test_multi_worker_broadcast.py)",
        allow_module_level=True,
    )


# --------------------------------------------------------------------------- #
# Infrastructure probes (skip with an actionable message when absent)
# --------------------------------------------------------------------------- #


def _redis_url() -> str:
    return (
        os.getenv("MULTIWORKER_REDIS_URL", "").strip()
        or os.getenv("WS_BROADCAST_REDIS_URL", "").strip()
        or os.getenv("REDIS_URL", "").strip()
        or os.getenv("VALKEY_URL", "").strip()
        or "redis://localhost:6379/0"
    )


def _probe_redis(url: str) -> None:
    import redis as redis_sync

    try:
        client = redis_sync.Redis.from_url(
            url, socket_connect_timeout=1.5, socket_timeout=1.5
        )
        try:
            client.ping()
        finally:
            client.close()
    except Exception as exc:  # noqa: BLE001 - probe failure → actionable skip
        pytest.skip(
            f"Redis/Valkey unreachable at {url!r} ({exc!r}). Start it e.g. with "
            "`docker compose -f docker-compose.infra.yml up -d valkey`."
        )


@dataclass
class _PgTarget:
    """Where the workers' database lives and who owns its lifecycle."""

    url: str
    ephemeral_name: str | None  # set → harness created it and will drop it


def _postgres_admin_connect():
    import psycopg2

    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "dydx_bot"),
        password=os.getenv("POSTGRES_PASSWORD", "change-me-db-password"),
        dbname="postgres",
        connect_timeout=2,
    )


def _ensure_database() -> _PgTarget:
    explicit = os.getenv("MULTIWORKER_DATABASE_URL", "").strip()
    if explicit:
        # Operator-managed scratch DB: used verbatim, never dropped by the harness.
        return _PgTarget(url=explicit, ephemeral_name=None)

    name = f"dydx_bot_mwtest_{os.getpid()}"
    try:
        admin = _postgres_admin_connect()
    except Exception as exc:  # noqa: BLE001 - probe failure → actionable skip
        pytest.skip(
            f"PostgreSQL unreachable on localhost ({exc!r}). Start it e.g. with "
            "`docker compose -f docker-compose.infra.yml up -d postgresql`, or "
            "point MULTIWORKER_DATABASE_URL at a scratch database."
        )
    try:
        with admin.cursor() as cur:
            admin.autocommit = True
            cur.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            cur.execute(f'CREATE DATABASE "{name}"')
    finally:
        admin.close()
    user = os.getenv("POSTGRES_USER", "dydx_bot")
    password = os.getenv("POSTGRES_PASSWORD", "change-me-db-password")
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    return _PgTarget(
        url=f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}",
        ephemeral_name=name,
    )


def _drop_database(name: str) -> None:
    try:
        admin = _postgres_admin_connect()
    except Exception:  # noqa: BLE001 - teardown must never mask the real result
        return
    try:
        with admin.cursor() as cur:
            admin.autocommit = True
            cur.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    except Exception:  # noqa: BLE001 - best-effort cleanup
        pass
    finally:
        admin.close()


# --------------------------------------------------------------------------- #
# Worker process harness
# --------------------------------------------------------------------------- #


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class WorkerProcess:
    name: str
    port: int
    process: subprocess.Popen
    log_path: Path

    def log_tail(self, lines: int = 30) -> str:
        try:
            content = self.log_path.read_text(errors="replace").splitlines()
        except OSError:
            return "<log unavailable>"
        return "\n".join(content[-lines:])

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"


def _spawn_worker(
    name: str,
    port: int,
    redis_url: str,
    db_url: str,
    log_dir: Path,
    run_config_file: Path,
) -> WorkerProcess:
    log_path = log_dir / f"worker_{name}.log"
    env = os.environ.copy()
    env.update(
        {
            # Canonical launcher semantics (load_repo_env first) with an explicit,
            # test-safe configuration; PRESERVE_PROCESS_ENV keeps the profile
            # files from overriding the values below. APP_RUN_CONFIG_FILE points
            # at a metadata-only profile so no repo profile values leak in.
            "APP_RUN_CONFIG_FILE": str(run_config_file),
            "APP_CONFIG_PRESERVE_PROCESS_ENV": "1",
            "ENVIRONMENT": "test",
            "APP_CONFIG_ENV": "test",
            "API_BYPASS_AUTH": "true",
            "STARTUP_CONFIG_VALIDATION": "skip",
            "BOT_API_HOST": "127.0.0.1",
            "BOT_API_PORT": str(port),
            # The system under test: the bus is ON and pointed at the shared Redis.
            "WS_BROADCAST_ENABLED": "true",
            "WS_BROADCAST_REDIS_URL": redis_url,
            # Same-URL BOT_DATABASE_URL/DATABASE_URL family; ephemeral scratch DB.
            "BOT_DATABASE_URL": db_url,
            "DATABASE_URL": db_url,
            # Keep optional integrations quiet; the bus is the subject here.
            "MARKET_DATA_CACHE_ENABLED": "false",
            "BACKTEST_CLICKHOUSE_WRITES_ENABLED": "false",
            "BACKTEST_MINIO_ARTIFACTS_ENABLED": "false",
            "PYTHONUNBUFFERED": "1",
        }
    )
    log_file = log_path.open("w")
    process = subprocess.Popen(
        [sys.executable, "-m", "src.api.start_api"],
        cwd=str(BOT_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return WorkerProcess(name=name, port=port, process=process, log_path=log_path)


def _wait_for_ready(worker: WorkerProcess) -> None:
    import httpx

    deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
    last_error = "worker never started"
    while time.monotonic() < deadline:
        if worker.process.poll() is not None:
            pytest.fail(
                f"worker {worker.name} exited with code "
                f"{worker.process.returncode} before becoming ready.\n"
                f"--- log tail ---\n{worker.log_tail()}"
            )
        try:
            resp = httpx.get(worker.url("/ready"), timeout=2.0)
            if resp.status_code == 200:
                return
            last_error = f"/ready returned {resp.status_code}"
        except httpx.HTTPError as exc:
            last_error = repr(exc)
        time.sleep(0.5)
    pytest.fail(
        f"worker {worker.name} not ready within {_READY_TIMEOUT_SECONDS:.0f}s "
        f"({last_error}).\n--- log tail ---\n{worker.log_tail()}"
    )


@dataclass
class Cluster:
    workers: list  # list[WorkerProcess]; index 0 = "A", index 1 = "B"

    @property
    def a(self) -> WorkerProcess:
        return self.workers[0]

    @property
    def b(self) -> WorkerProcess:
        return self.workers[1]


@pytest.fixture(scope="module")
def cluster():
    redis_url = _redis_url()
    _probe_redis(redis_url)
    db_target = _ensure_database()

    with tempfile.TemporaryDirectory(prefix="mwtest_logs_") as log_dirname:
        log_dir = Path(log_dirname)
        # Metadata-only structured profile: flattens to zero env keys, so the
        # workers' configuration comes exclusively from the explicit env below.
        run_config_file = log_dir / "run.config.json"
        run_config_file.write_text(
            json.dumps({"metadata": {"name": "multiworker-test"}}), encoding="utf-8"
        )
        workers: list[WorkerProcess] = []
        try:
            # Staggered startup: worker A migrates the empty ephemeral schema;
            # worker B starts only after A is ready so the two never race Alembic
            # DDL on the same fresh database.
            for name in ("a", "b"):
                worker = _spawn_worker(
                    name,
                    _free_port(),
                    redis_url,
                    db_target.url,
                    log_dir,
                    run_config_file,
                )
                workers.append(worker)
                _wait_for_ready(worker)
            yield Cluster(workers=workers)
        finally:
            for worker in workers:
                worker.process.terminate()
            for worker in workers:
                try:
                    worker.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    worker.process.kill()
                    worker.process.wait(timeout=10)
            if db_target.ephemeral_name:
                _drop_database(db_target.ephemeral_name)


def _bus_health(worker: WorkerProcess) -> dict:
    import httpx

    resp = httpx.get(worker.url("/api/v1/monitoring/ws-broadcast"), timeout=5.0)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True, body
    return body["data"]


def _publish_test_broadcast(worker: WorkerProcess, channel: str) -> str:
    import httpx

    resp = httpx.post(
        worker.url("/api/v1/monitoring/ws-broadcast/publish"),
        json={"channel": channel},
        timeout=5.0,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True, body
    return str(body["data"]["test_id"])


# --------------------------------------------------------------------------- #
# The scenarios
# --------------------------------------------------------------------------- #


def test_workers_report_healthy_distinct_bus_identities(cluster):
    """Both workers run a live Redis-backed bus with distinct worker identities
    (distinct identities are what makes origin-tagged self-suppression work)."""
    health_a = _bus_health(cluster.a)
    health_b = _bus_health(cluster.b)

    for label, health in (("a", health_a), ("b", health_b)):
        assert health["enabled"] is True, (label, health)
        assert health["backend"] == "redis", (label, health)
        assert health["healthy"] is True, (label, health)
        assert health["listening"] is True, (label, health)

    assert health_a["worker_id"] != health_b["worker_id"]


def test_broadcast_on_worker_a_reaches_worker_b_exactly_once(cluster):
    """The headline property: publish on A → the client attached to B receives
    the exact message once; the client on A receives it once (local delivery)
    and neither sees a loop-back duplicate."""

    async def _scenario() -> None:
        from websockets.asyncio.client import connect

        urls = [
            f"ws://127.0.0.1:{w.port}/ws/bots/{_WS_CHANNEL}" for w in cluster.workers
        ]
        async with (
            connect(urls[0], open_timeout=15) as ws_a,
            connect(urls[1], open_timeout=15) as ws_b,
        ):
            # Drain the initial frame both workers send on connect (a
            # backtest_progress "not_found" status for the synthetic run id).
            for ws in (ws_a, ws_b):
                initial = json.loads(await asyncio.wait_for(ws.recv(), timeout=15.0))
                assert initial["type"] == "backtest_progress", initial
                assert initial["status"] == "not_found", initial

            test_id = await asyncio.to_thread(
                _publish_test_broadcast, cluster.a, _WS_CHANNEL
            )

            async def _recv_broadcast_test(ws) -> dict:
                # Tolerate unrelated interleaved frames, but only briefly.
                for _ in range(5):
                    message = json.loads(
                        await asyncio.wait_for(ws.recv(), timeout=10.0)
                    )
                    if message.get("type") == "broadcast_test":
                        return message
                raise AssertionError("no broadcast_test frame received")

            # Worker B received it cross-worker via the Redis bus.
            got_b = await _recv_broadcast_test(ws_b)
            assert got_b["data"]["test_id"] == test_id
            assert got_b["bot_instance_id"] == _WS_CHANNEL

            # Worker A received it exactly once via its own local delivery.
            got_a = await _recv_broadcast_test(ws_a)
            assert got_a["data"]["test_id"] == test_id

            # No loop-back: after one delivery per client, the channel stays
            # quiet (a re-published echo would surface here as a duplicate).
            for ws in (ws_a, ws_b):
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(ws.recv(), timeout=_QUIET_WINDOW_SECONDS)

            # Reverse direction: B → A also crosses the bus (no half-broken
            # subscription hiding behind the A→B success).
            test_id_b = await asyncio.to_thread(
                _publish_test_broadcast, cluster.b, _WS_CHANNEL
            )
            got_a_rev = await _recv_broadcast_test(ws_a)
            assert got_a_rev["data"]["test_id"] == test_id_b
            # B's own local delivery of the reverse publish lands on ws_b once.
            got_b_local = await _recv_broadcast_test(ws_b)
            assert got_b_local["data"]["test_id"] == test_id_b

            # Still exactly once per client in either direction: both channels
            # are now quiet (any re-published echo would surface here).
            for ws in (ws_a, ws_b):
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(ws.recv(), timeout=_QUIET_WINDOW_SECONDS)

    try:
        asyncio.run(_scenario())
    except Exception:
        # Surfacing worker logs is the only way to debug server-side closes.
        for worker in cluster.workers:
            print(
                f"\n[multiworker] worker {worker.name} (port {worker.port}) "
                f"log tail:\n{worker.log_tail(40)}"
            )
        raise


def test_burst_publish_cross_worker_delivery_under_load(cluster):
    """Burst/load coverage at the two-real-worker topology level.

    Publishes a rapid burst of ``broadcast_test`` messages across multiple
    synthetic channels, alternating the *publishing* worker per channel (so
    both the A→B and B→A cross-worker paths carry sustained load), while one
    WebSocket client per channel is attached to EACH worker. Asserts the
    properties the Phase 2 default-flip depends on:

    - exactly-once delivery to every client (local and cross-worker);
    - per-channel publish-order preserved end-to-end (single publisher per
      channel keeps Redis ordering deterministic);
    - no duplicates/echoes afterwards (quiet window);
    - zero bus error counters and ZERO reconnects across the burst (a
      listener flap silently drops messages — the bug class this harness
      already caught once — so ``reconnects`` must not move at all).
    """
    if _BURST_MESSAGES == 0:
        pytest.skip("MULTIWORKER_BURST_MESSAGES=0 — burst scenario disabled")

    channels = [f"{_WS_CHANNEL}-burst-{i}" for i in range(_BURST_CHANNELS)]
    per_channel = [
        _BURST_MESSAGES // _BURST_CHANNELS
        + (1 if i < _BURST_MESSAGES % _BURST_CHANNELS else 0)
        for i in range(_BURST_CHANNELS)
    ]
    assert sum(per_channel) == _BURST_MESSAGES
    # Round-robin schedule: channel index for each of the _BURST_MESSAGES
    # publishes (first channels absorb the remainder, matching per_channel).
    schedule = [seq % _BURST_CHANNELS for seq in range(_BURST_MESSAGES)]

    # Channel i is published by worker A when i is even, B when odd: both
    # cross-worker directions carry load while each channel keeps a single
    # publisher (deterministic per-channel Redis ordering).
    publisher_for = {
        c: cluster.a if i % 2 == 0 else cluster.b for i, c in enumerate(channels)
    }
    count_for = dict(zip(channels, per_channel))

    async def _scenario() -> None:
        from websockets.asyncio.client import connect

        # One client per channel per worker: 2 * len(channels) connections,
        # each of which must see its channel's burst exactly once, in order.
        clients: dict = {}  # (channel, worker_idx) -> websockets connection
        try:
            for c in channels:
                for idx, worker in enumerate(cluster.workers):
                    ws = await connect(
                        f"ws://127.0.0.1:{worker.port}/ws/bots/{c}", open_timeout=15
                    )
                    clients[(c, idx)] = ws
            # Drain the initial backtest_progress frame each connection gets.
            for ws in clients.values():
                initial = json.loads(await asyncio.wait_for(ws.recv(), timeout=15.0))
                assert initial["type"] == "backtest_progress", initial

            metrics_before = {
                worker.name: _bus_health(worker)["metrics"]
                for worker in cluster.workers
            }

            # Rapid sequential burst: round-robin across channels so the shared
            # ws:broadcast listener on each worker sees interleaved traffic.
            published_ids: dict[str, list[str]] = {c: [] for c in channels}
            for channel_idx in schedule:
                c = channels[channel_idx]
                test_id = await asyncio.to_thread(
                    _publish_test_broadcast, publisher_for[c], c
                )
                published_ids[c].append(test_id)

            # Collect every client's frames; each must see exactly its
            # channel's messages, in publish order, with no foreign frames.
            async def _collect(c: str, idx: int) -> list[str]:
                ws = clients[(c, idx)]
                expected = count_for[c]
                ids: list[str] = []
                deadline = time.monotonic() + _BURST_RECV_TIMEOUT_SECONDS
                while len(ids) < expected:
                    remaining = deadline - time.monotonic()
                    assert remaining > 0, (
                        f"client (channel={c}, worker={idx}) received only "
                        f"{len(ids)}/{expected} frames before timeout"
                    )
                    message = json.loads(
                        await asyncio.wait_for(ws.recv(), timeout=remaining)
                    )
                    assert (
                        message["type"] == "broadcast_test"
                    ), f"unexpected frame on burst channel {c}: {message}"
                    assert message["bot_instance_id"] == c, message
                    ids.append(str(message["data"]["test_id"]))
                return ids

            results = await asyncio.gather(
                *(
                    _collect(c, idx)
                    for c in channels
                    for idx in range(len(cluster.workers))
                )
            )
            flat = {
                (c, idx): ids
                for (c, idx), ids in zip(
                    [(c, idx) for c in channels for idx in range(len(cluster.workers))],
                    results,
                )
            }
            for c in channels:
                for idx in range(len(cluster.workers)):
                    path = (
                        "local"
                        if publisher_for[c] is cluster.workers[idx]
                        else "cross-worker"
                    )
                    assert flat[(c, idx)] == published_ids[c], (
                        f"{path} delivery on channel {c} (worker {idx}) diverged "
                        f"from publish order (duplicates, loss, or reorder)"
                    )

            # Quiet window: no duplicates or echoes beyond the exact burst.
            for ws in clients.values():
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(ws.recv(), timeout=_QUIET_WINDOW_SECONDS)

            metrics_after = {
                worker.name: _bus_health(worker)["metrics"]
                for worker in cluster.workers
            }
            for worker in cluster.workers:
                before, after = metrics_before[worker.name], metrics_after[worker.name]
                expected_published = sum(
                    count_for[c] for c in channels if publisher_for[c] is worker
                )
                assert after["published"] - before["published"] == expected_published, (
                    worker.name,
                    before,
                    after,
                )
                for key in _ERROR_METRIC_KEYS:
                    assert after[key] - before[key] == 0, (
                        worker.name,
                        key,
                        before,
                        after,
                    )
        finally:
            for ws in clients.values():
                await ws.close()

    try:
        asyncio.run(_scenario())
    except Exception:
        # Surfacing worker logs is the only way to debug server-side closes.
        for worker in cluster.workers:
            print(
                f"\n[multiworker] worker {worker.name} (port {worker.port}) "
                f"log tail:\n{worker.log_tail(40)}"
            )
        raise
