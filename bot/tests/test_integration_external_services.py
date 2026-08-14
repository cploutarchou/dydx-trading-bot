"""Opt-in integration tests for the external-service topology (IMPROVEMENTS.md item #4).

Exercises the REAL infrastructure the bot depends on — Redis/Valkey (shared L2
market-data cache + WebSocket broadcast bus), Celery (a real worker subprocess
over a real broker), and the public dYdX v4 indexer — instead of the unit
suite's in-memory fakes. These are the seams unit tests cannot reach: actual
socket semantics, pub/sub delivery, worker startup, and external contracts.

Opt-in so `make test` stays hermetic. Run with::

    docker compose -f docker-compose.infra.yml up -d valkey
    make test-integration          # or:
    INTEGRATION_TEST=1 .venv/bin/python -m pytest tests/test_integration_external_services.py -vv -s

The Redis tests run against a DEDICATED scratch database (default
``redis://localhost:6379/15``, override with ``INTEGRATION_REDIS_URL``) so a
running dev cache/broker is never touched; the Celery worker uses its own
scratch broker/result DBs (``redis://localhost:6379/14``, override with
``INTEGRATION_CELERY_BROKER_URL``). The dYdX indexer test reads the public
mainnet markets endpoint (override with ``DYDX_INTEGRATION_INDEXER_URL``) and
skips with an actionable message when outbound network is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]

_WORKER_READY_TIMEOUT_SECONDS = 120.0
_WORKER_NAME = "bot-integration-test"


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


if not _env_flag("INTEGRATION_TEST"):
    pytest.skip(
        "external-service integration tests are opt-in: set INTEGRATION_TEST=1 "
        "with Redis/Valkey reachable (see `make test-integration` and the module "
        "docstring in tests/test_integration_external_services.py)",
        allow_module_level=True,
    )


def _redis_url() -> str:
    return (
        os.getenv("INTEGRATION_REDIS_URL", "").strip()
        or "redis://localhost:6379/15"  # dedicated scratch DB (never the dev cache)
    )


def _celery_broker_url() -> str:
    return (
        os.getenv("INTEGRATION_CELERY_BROKER_URL", "").strip()
        or "redis://localhost:6379/14"  # scratch broker, isolated from dev workers
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


# --------------------------------------------------------------------------- #
# Redis/Valkey — shared L2 market-data cache
# --------------------------------------------------------------------------- #


def test_redis_market_data_cache_roundtrip():
    """The real RedisMarketDataCache round-trips payloads through Valkey."""
    from src.infrastructure.cache.market_cache import RedisMarketDataCache

    url = _redis_url()
    _probe_redis(url)

    async def _scenario() -> None:
        import redis.asyncio as aioredis

        # Start from a clean scratch DB (a crashed prior run may have left keys).
        cleanup_client = aioredis.from_url(url)
        cache = RedisMarketDataCache(url=url, ttl_candles=60, ttl_markets=60)
        try:
            await cleanup_client.flushdb()

            health = await cache.health()
            assert health == {
                "enabled": True,
                "backend": "redis",
                "healthy": True,
                "error": None,
            }, health

            # Markets: miss → write → hit → overwritten value wins.
            marker = f"integration-{time.time_ns()}"
            assert await cache.get_markets() is None
            await cache.set_markets({"marker": marker}, ttl_seconds=60)
            assert await cache.get_markets() == {"marker": marker}
            await cache.set_markets({"marker": "overwritten"}, ttl_seconds=60)
            assert await cache.get_markets() == {"marker": "overwritten"}

            # Candles: write → read-back preserves the payload shape the
            # runtime serializes (startedAt/rows contract is a plain dict).
            payload = {
                "startedAt": "2026-08-15T00:00:00Z",
                "rows": [{"open": "1", "close": "2"}],
            }
            await cache.set_candles("INTEG-USD", "1MIN", payload, ttl_seconds=60)
            assert await cache.get_candles("INTEG-USD", "1MIN") == payload
            assert await cache.get_candles("INTEG-USD", "5MIN") is None
        finally:
            # Leave the scratch DB clean.
            try:
                await cache.aclose()
                await cleanup_client.flushdb()
            finally:
                await cleanup_client.aclose()

    asyncio.run(_scenario())


# --------------------------------------------------------------------------- #
# Redis/Valkey — cross-worker WebSocket broadcast bus (real pub/sub sockets)
# --------------------------------------------------------------------------- #


def test_broadcast_bus_real_pubsub_delivery_and_self_suppression():
    """Two real bus instances over one Valkey: cross-instance delivery works
    and self-originated publishes are suppressed (no loop-back)."""
    from src.infrastructure.broadcast import RedisBroadcastBus

    url = _redis_url()
    _probe_redis(url)

    async def _scenario() -> None:
        bus_a = RedisBroadcastBus(url=url, socket_timeout=1.0, worker_id="integ-A")
        bus_b = RedisBroadcastBus(url=url, socket_timeout=1.0, worker_id="integ-B")
        received: list[tuple[str, dict]] = []

        async def _dispatch(channel_id: str, message: dict) -> None:
            received.append((channel_id, message))

        try:
            await bus_a.start(_dispatch)
            # Give the subscriber a moment to SUBSCRIBE before publishing.
            for _ in range(50):
                health = await bus_a.health()
                if health.get("subscribed"):
                    break
                await asyncio.sleep(0.1)
            assert (await bus_a.health())["subscribed"] is True

            # B → A: delivered cross-instance via real pub/sub.
            await bus_b.publish("chan-1", {"hello": "from-b"})
            await _wait_received(received)
            assert received[-1] == ("chan-1", {"hello": "from-b"})

            # A → A: self-origin suppression (already delivered locally when
            # publishing; the subscriber must not echo it back).
            received.clear()
            await bus_a.publish("chan-1", {"hello": "from-a"})
            await asyncio.sleep(1.0)
            assert received == []
        finally:
            await bus_a.aclose()
            await bus_b.aclose()

    asyncio.run(_scenario())


async def _wait_received(received: list) -> None:
    deadline = time.monotonic() + 5.0
    while not received and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert received, "no pub/sub message delivered within 5s"


# --------------------------------------------------------------------------- #
# Celery — real worker subprocess over a real broker
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def celery_worker():
    """Boot a real (solo-pool) Celery worker on the scratch broker and wait
    until it answers control pings."""
    broker = _celery_broker_url()
    _probe_redis(broker)

    with tempfile.TemporaryDirectory(prefix="integ_celery_") as tmp:
        log_path = Path(tmp) / "worker.log"
        # Metadata-only structured profile: the worker's config comes entirely
        # from the explicit env below (same convention as the multi-worker
        # harness).
        run_config = Path(tmp) / "run.config.json"
        run_config.write_text(
            json.dumps({"metadata": {"name": "integration-test"}}), encoding="utf-8"
        )

        env = os.environ.copy()
        env.update(
            {
                "APP_RUN_CONFIG_FILE": str(run_config),
                "APP_CONFIG_PRESERVE_PROCESS_ENV": "1",
                "ENVIRONMENT": "test",
                "APP_CONFIG_ENV": "test",
                "CELERY_BROKER_URL": broker,
                "CELERY_RESULT_BACKEND": broker,
                # Keep optional integrations quiet; the broker path is the subject.
                "MARKET_DATA_CACHE_ENABLED": "false",
                "BACKTEST_CLICKHOUSE_WRITES_ENABLED": "false",
                "BACKTEST_MINIO_ARTIFACTS_ENABLED": "false",
                "PYTHONUNBUFFERED": "1",
            }
        )

        # The TEST process's own celery_app client must talk to the same
        # scratch broker: celery_app loads the repo profile at import, so pin
        # the env before the (cached) first import and restore afterwards.
        saved_env = {
            name: os.environ.get(name)
            for name in (
                "APP_RUN_CONFIG_FILE",
                "APP_CONFIG_PRESERVE_PROCESS_ENV",
                "CELERY_BROKER_URL",
                "CELERY_RESULT_BACKEND",
            )
        }
        os.environ.update(
            {
                "APP_RUN_CONFIG_FILE": str(run_config),
                "APP_CONFIG_PRESERVE_PROCESS_ENV": "1",
                "CELERY_BROKER_URL": broker,
                "CELERY_RESULT_BACKEND": broker,
            }
        )

        log_file = log_path.open("w")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "src.infrastructure.workers.celery_app:celery_app",
                "worker",
                "--loglevel=WARNING",
                "--pool=solo",
                "--without-gossip",
                "--without-mingle",
                f"--hostname={_WORKER_NAME}",
            ],
            cwd=str(BOT_ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            yield _wait_for_worker_ping(process, log_path)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            for name, value in saved_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def _wait_for_worker_ping(process, log_path: Path) -> str:
    """Poll ``celery_app.control.ping`` until the spawned worker replies."""
    from src.infrastructure.workers.celery_app import celery_app

    deadline = time.monotonic() + _WORKER_READY_TIMEOUT_SECONDS
    last_error = "worker never started"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(
                f"celery worker exited with code {process.returncode} before "
                f"answering pings.\n--- log tail ---\n{_log_tail(log_path)}"
            )
        try:
            replies = celery_app.control.ping(timeout=2.0)
            if replies:
                return str(replies)
        except Exception as exc:  # noqa: BLE001 - probe failure → keep polling
            last_error = repr(exc)
        time.sleep(1.0)
    pytest.fail(
        f"celery worker did not answer control pings within "
        f"{_WORKER_READY_TIMEOUT_SECONDS:.0f}s ({last_error}).\n"
        f"--- log tail ---\n{_log_tail(log_path)}"
    )


def _log_tail(log_path: Path, lines: int = 30) -> str:
    try:
        content = log_path.read_text(errors="replace").splitlines()
    except OSError:
        return "<log unavailable>"
    return "\n".join(content[-lines:])


def test_celery_worker_answers_control_ping(celery_worker):
    """A real Celery worker booted on the real broker answers control pings —
    exercising broker connection, worker startup, and the control channel in
    both directions."""
    replies = celery_worker
    assert "pong" in replies


def test_celery_worker_registers_project_tasks(celery_worker):
    """The spawned worker registers the project's task modules (backtests,
    scheduled sync, monitoring) — the registration contract the API's startup
    probe and Flower rely on."""
    from src.infrastructure.workers.celery_app import celery_app

    registered = celery_app.control.inspect(timeout=10.0).registered()
    assert registered, "inspect().registered() returned no replies"
    tasks = [name for entry in registered.values() for name in entry]
    # Task names are custom (@task(name=...)): the backtest runner and the
    # scheduled market-sync producer are the two core registrations.
    assert "backtests.run" in tasks, tasks
    assert any("sync_market" in name for name in tasks), tasks


# --------------------------------------------------------------------------- #
# dYdX v4 indexer — public read-only contract
# --------------------------------------------------------------------------- #


def test_dydx_indexer_public_markets_contract():
    """The public dYdX v4 indexer serves the perpetual-markets contract the
    bot's market-data layer depends on (skips when offline)."""
    import httpx

    base = (
        os.getenv("DYDX_INTEGRATION_INDEXER_URL", "").strip()
        or "https://indexer.dydx.trade"
    ).rstrip("/")
    try:
        response = httpx.get(f"{base}/v4/perpetualMarkets", timeout=15.0)
    except httpx.HTTPError as exc:
        pytest.skip(f"dYdX indexer unreachable at {base!r} ({exc!r}) — offline?")

    assert response.status_code == 200, response.text[:200]
    markets = response.json().get("markets", {})
    assert "BTC-USD" in markets, sorted(markets)[:10]
    btc = markets["BTC-USD"]
    assert btc.get("ticker") == "BTC-USD", btc.get("ticker")
    assert btc.get("status") in {"ACTIVE", "PAUSED"}, btc.get("status")
    assert btc.get("oraclePrice"), str(btc)[:200]
