import os
import sys
from pathlib import Path

import pytest


def _ensure_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_ROOT = REPO_ROOT / "bot"

_ensure_path(REPO_ROOT)
_ensure_path(BOT_ROOT)


# ============================================================================
# Import-time environment hermeticity (MUST run before any src import)
# ============================================================================
#
# The database manager singleton builds its engine at src-import time from the
# structured config (run.json exports BOT_DATABASE_URL etc. via load_repo_env),
# so fixture-level env patching is too late. With the local dev stack running,
# tests would otherwise connect to the shared dev Postgres (retry storms on
# auth failures, stale rows, and writes into live state). Point the suite at
# the same hermetic run config CI uses (.ci-run.json: no database section),
# and force the default DB to a closed port so connections fail fast and code
# falls back to the in-memory/file stores — the suite's supported mode.
_ci_run_config = REPO_ROOT / ".ci-run.json"
if _ci_run_config.exists() and not os.environ.get("BOT_TESTS_KEEP_RUN_CONFIG"):
    os.environ["APP_RUN_CONFIG_FILE"] = str(_ci_run_config)
os.environ.setdefault("DB_PORT", "5439")
os.environ.setdefault("BOT_DB_PORT", "5439")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("BOT_DATABASE_URL", None)


# ============================================================================
# Market-data shared (L2) cache isolation
# ============================================================================
#
# The Redis/Valkey-backed L2 cache in ``src/infrastructure/cache`` is shared
# state. Tests must stay deterministic regardless of Redis/Valkey contents, so
# the L2 is kept inert (Noop) by default. Tests that exercise the cache override
# ``src.trading.market_data.get_market_data_cache`` directly with their own
# double (their ``monkeypatch.setattr`` runs after this fixture's setup and so
# takes precedence within the same function-scoped monkeypatch).
@pytest.fixture(autouse=True)
def _isolate_shared_market_data_cache(monkeypatch):
    from src.infrastructure.cache import NoopMarketDataCache, reset_market_data_cache
    from src.trading import market_data

    reset_market_data_cache()
    monkeypatch.setattr(
        market_data, "get_market_data_cache", lambda: NoopMarketDataCache()
    )


# ============================================================================
# Circuit-breaker isolation
# ============================================================================
#
# The centralized breakers in ``src/infrastructure/resilience`` hold shared,
# stateful singletons. Left active across the suite, a failure-simulating test
# would trip a breaker and leave it OPEN for unrelated tests (cascading
# ``CircuitBreakerOpenError``). Defaulting them to disabled also keeps existing
# call-site tests deterministic: they see raw provider behavior exactly as
# before the breakers existed. Tests that exercise a breaker re-enable it with
# ``monkeypatch.setenv("<SERVICE>_CIRCUIT_ENABLED", "true")`` +
# ``resilience.reset_breakers()``.
@pytest.fixture(autouse=True)
def _isolate_circuit_breakers(monkeypatch):
    from src.infrastructure import resilience

    resilience.reset_breakers()
    for service in ("DYDX_INDEXER", "TELEGRAM", "LOKI"):
        monkeypatch.setenv(f"{service}_CIRCUIT_ENABLED", "false")


# ============================================================================
# Backtest artifact-store isolation
# ============================================================================
#
# The local artifact fallback defaults to the shared runtime directory
# ``bot_states/backtest_artifacts``. Tests must never read or write that
# directory: doing so pollutes the working tree with generated run
# directories (the class of accidental artifact commits seen on master) and
# can couple tests to leftover artifacts from earlier runs. A test that wants
# a specific root sets BACKTEST_ARTIFACTS_DIR itself after this fixture.
@pytest.fixture(autouse=True)
def _isolate_backtest_artifact_store(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_ARTIFACTS_DIR", str(tmp_path / "backtest_artifacts"))


# ============================================================================
# Tracked-position store isolation (file mode)
# ============================================================================
#
# bot_agents_state persists tracked positions DB-first. With the local dev
# docker stack running (real Postgres on 5432) tests would otherwise read
# leftover rows from the shared database and — worse — writes/deletes
# (append/save/clear during exit and abort flows) would mutate the state of
# any live worker pointed at the same database. Force file mode suite-wide;
# a dedicated DB-mode test would override these with its own monkeypatch.
# ============================================================================
# Database hermeticity
# ============================================================================
#
# The suite's supported mode is "database unavailable" (that is exactly how
# CI runs it: repositories fall back to in-memory/file stores). With the
# local dev docker stack running, a real Postgres listens on 5432 and tests
# would silently read/write the SHARED dev database — stale rows break
# DB-backed tests and writes pollute (or worse, mutate) the running
# worker/API state. Point the default DB at a closed port; tests that
# deliberately exercise a real database opt back in via their own env.
# ============================================================================
# External artifact-backend isolation
# ============================================================================
#
# The structured config exports MINIO_ENABLED / BACKTEST_ARTIFACT_STORAGE_ENABLED
# / CLICKHOUSE_ENABLED into os.environ; with the local dev stack running,
# backtest persistence would write REAL artifacts to the dev MinIO/ClickHouse
# (slow, and pollutes shared infra). Tests exercise the local fallback stores;
# dedicated MinIO/ClickHouse tests inject their own doubles.
@pytest.fixture(autouse=True)
def _disable_external_artifact_backends(monkeypatch):
    for gate in (
        "BACKTEST_MINIO_ARTIFACTS_ENABLED",
        "BACKTEST_MINIO_ENABLED",
        "MINIO_ENABLED",
        "BACKTEST_ARTIFACT_STORAGE_ENABLED",
        "BACKTEST_CLICKHOUSE_WRITES_ENABLED",
        "BACKTEST_CLICKHOUSE_ENABLED",
        "CLICKHOUSE_ENABLED",
    ):
        monkeypatch.setenv(gate, "false")


@pytest.fixture(autouse=True)
def _hermetic_database(monkeypatch):
    monkeypatch.setenv("DB_PORT", "5439")
    monkeypatch.setenv("BOT_DB_PORT", "5439")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BOT_DATABASE_URL", raising=False)


@pytest.fixture(autouse=True)
def _force_file_mode_tracked_state(monkeypatch):
    from src.trading import bot_agents_state

    monkeypatch.setattr(bot_agents_state, "_db_load_positions", lambda: None)

    def _no_save(_positions):
        return None

    monkeypatch.setattr(bot_agents_state, "_db_save_positions", _no_save)

    def _no_delete():
        return None

    monkeypatch.setattr(bot_agents_state, "_db_delete_positions", _no_delete)


# ============================================================================
# Cross-worker WebSocket broadcast bus isolation
# ============================================================================
#
# The Redis pub/sub bus in ``src/infrastructure/broadcast`` fans WebSocket
# broadcasts across Uvicorn workers. Tests must stay deterministic regardless of
# Redis/Valkey state, so the bus is kept inert (Noop) by default — every
# ``broadcast_to_bot`` then behaves exactly as it did before the bus existed
# (local-only delivery). The accessor is patched at the *importer*
# (``src.api.websocket_server``), mirroring the market-data cache fixture above;
# a test's own function-scoped monkeypatch runs after this setup and so takes
# precedence when it wants to exercise a real/double bus.
@pytest.fixture(autouse=True)
def _isolate_broadcast_bus(monkeypatch):
    from src.infrastructure.broadcast import NoopBroadcastBus
    from src.infrastructure.broadcast import bus as broadcast_bus_module
    from src.infrastructure.broadcast import reset_broadcast_bus

    # Neutralize the factory decision itself, not just the env var:
    # ``bus.py`` imports WS_BROADCAST_ENABLED from constants BY VALUE at import
    # time, so patching the env after import has no effect on
    # ``_build_broadcast_bus`` — which matters now the default is ON
    # (Phase 2 flip). Patching the bus module's binding keeps every
    # ``get_broadcast_bus()`` caller (websocket_server, monitoring routes)
    # on the Noop bus for the duration of a test.
    monkeypatch.setattr(broadcast_bus_module, "WS_BROADCAST_ENABLED", False)
    monkeypatch.setenv("WS_BROADCAST_ENABLED", "false")
    reset_broadcast_bus()
    try:
        from src.api import websocket_server
    except ImportError:  # pragma: no cover - FastAPI/pydantic absent in stripped envs
        # The bus is already Noop via the patched flag + reset above; this guard
        # only affects stripped local envs (no pydantic_core) so non-FastAPI tests
        # can still run. CI has FastAPI, so the patch applies there. ``ImportError``
        # is intentionally narrow so a genuine regression in websocket_server.py
        # surfaces instead of being silently swallowed.
        return
    monkeypatch.setattr(
        websocket_server, "get_broadcast_bus", lambda: NoopBroadcastBus()
    )


# ============================================================================
# Portfolio drawdown peak-equity store isolation
# ============================================================================
#
# The Redis-backed peak-equity ratchet in ``src/trading/portfolio_risk.py`` is
# shared state. Tests must stay deterministic regardless of Redis/Valkey
# contents, so the store is kept inert (observe -> None, i.e. the drawdown
# check skips itself) by default. Tests exercising the real store inject their
# own double via ``monkeypatch.setattr(portfolio_risk, "get_peak_equity_store", ...)``
# (their function-scoped monkeypatch runs after this fixture's setup and so
# takes precedence).
@pytest.fixture(autouse=True)
def _isolate_portfolio_peak_store(monkeypatch):
    from src.trading import portfolio_risk

    class _InertPeakStore:
        async def observe(self, address, equity):  # pragma: no cover - inert
            del address, equity
            return None

    portfolio_risk.reset_peak_equity_store()
    monkeypatch.setattr(
        portfolio_risk,
        "get_peak_equity_store",
        lambda: _InertPeakStore(),
    )


# ============================================================================
# Portfolio multi-account enumeration isolation
# ============================================================================
#
# The aggregate portfolio checks enumerate distinct wallet addresses from the
# ``bot_instances`` table (DB reads + credential decryption) and then issue
# public indexer reads for the foreign accounts. Tests must stay hermetic, so
# the address cache is reset around every test and the aggregate limits are
# pinned to their default-off values — a stray BOT_PORTFOLIO_AGGREGATE_* env
# var cannot flip a test onto live enumeration/exchange paths. Tests
# exercising the aggregate path monkeypatch ``portfolio_risk.enumerate_portfolio_accounts``
# and the loader seam directly (their function-scoped monkeypatch runs after
# this fixture's setup and so takes precedence).
@pytest.fixture(autouse=True)
def _isolate_portfolio_accounts(monkeypatch):
    from src.trading import portfolio_accounts, portfolio_risk

    portfolio_accounts.reset_portfolio_account_cache()
    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS", 0)
    monkeypatch.setattr(
        portfolio_risk,
        "BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT",
        0.0,
    )
    yield
    portfolio_accounts.reset_portfolio_account_cache()


# ============================================================================
# Portfolio entry-guard default isolation
# ============================================================================
#
# ``BOT_PORTFOLIO_RISK_ENABLED`` is ON by default since the Phase B flip
# (2026-08-17). The guard module binds the constant by value at import, so an
# env-var patch is inert post-import — the module attribute is pinned to False
# here, mirroring the broadcast-bus constant patch above, so the suite stays
# hermetic under the new default (the guard would otherwise make live exchange
# reads from every open_positions test). Tests exercising the guard enable it
# explicitly via ``monkeypatch.setattr(portfolio_risk,
# "BOT_PORTFOLIO_RISK_ENABLED", True)`` — their function-scoped monkeypatch
# runs after this fixture's setup and so takes precedence.
@pytest.fixture(autouse=True)
def _isolate_portfolio_guard(monkeypatch):
    from src.trading import portfolio_risk

    monkeypatch.setattr(portfolio_risk, "BOT_PORTFOLIO_RISK_ENABLED", False)


# ============================================================================
# PostgreSQL database helper functions
# ============================================================================


def get_expected_db_dialect() -> str:
    """Return the expected database dialect for current environment."""
    db_type = os.getenv("DB_TYPE", "postgres").lower()
    if db_type in ("postgres", "postgresql"):
        return "postgresql"
    raise AssertionError(f"Unsupported test DB_TYPE: {db_type}")


def get_driver_name() -> str:
    """Return the Python driver name for the active test database."""
    return "psycopg2"


def assert_connection_string_valid(conn_str: str) -> None:
    """Assert connection string is valid for current database environment.

    Args:
        conn_str: Connection string to validate

    Raises:
        AssertionError: If connection string doesn't match expected dialect
    """
    dialect = get_expected_db_dialect()
    driver = get_driver_name()
    expected_prefix = f"{dialect}+{driver}://"
    assert conn_str.startswith(
        expected_prefix
    ), f"Expected {expected_prefix} in connection string, got: {conn_str}"


def assert_db_type_supported(db_type_str: str) -> None:
    """Assert db_type field contains supported value.

    Args:
        db_type_str: The db_type value from payload or config

    Raises:
        AssertionError: If db_type is not a supported database type
    """
    supported = ("postgres", "postgresql")
    assert (
        db_type_str in supported
    ), f"Unsupported db_type: {db_type_str}. Supported: {supported}"


def get_test_db_port() -> str:
    """Get the bot test PostgreSQL port."""
    return "5432"


def get_test_connection_string(
    user: str = "bot_user",
    password: str = "secret",
    host: str = "db-host",
    db_name: str = "bot_db",
) -> str:
    """Generate a test connection string for current database environment.

    Args:
        user: Database user
        password: Database password
        host: Database host
        db_name: Database name

    Returns:
        Full connection string with appropriate dialect and driver
    """
    port = get_test_db_port()
    return (
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
        "?sslmode=disable"
    )


# ============================================================================
# Indexer freshness guard isolation
# ============================================================================
#
# ``src/trading/indexer_freshness.py`` fails closed: a client whose indexer
# height cannot be read blocks entries. The entry-path tests drive
# ``open_positions`` and the runtime preflight with minimal client doubles that
# have no indexer height, so the guard is pinned OFF by default and its alert
# rate limiter is reset. Tests exercising the guard opt back in with
# ``monkeypatch.delenv``/``setenv`` (function-scoped monkeypatch runs after this
# fixture's setup and so takes precedence). The shipped default is pinned by
# ``test_the_guard_is_on_by_default``.
@pytest.fixture(autouse=True)
def _isolate_indexer_freshness_guard(monkeypatch):
    from src.trading import indexer_freshness

    monkeypatch.setenv(indexer_freshness.ENV_MAX_LAG_SECONDS, "0")
    monkeypatch.setattr(indexer_freshness, "_last_alert_at", None)


# Strategy drawdown limit and trailing stop isolation
# ============================================================================
#
# ``position_manager`` binds MAX_DRAWDOWN_PCT and TRAILING_STOP_PCT by value
# from the structured config, so a developer config with either set would make
# every open_positions test read account equity and a drawdown peak from the
# database. Both are pinned off and the drawdown alert rate limiter is reset.
# Tests exercising them set the attribute themselves (function-scoped
# monkeypatch runs after this fixture's setup and so takes precedence).
@pytest.fixture(autouse=True)
def _isolate_strategy_drawdown_and_trailing_stop(monkeypatch):
    from src.trading import drawdown_guard, position_manager

    monkeypatch.setattr(position_manager, "MAX_DRAWDOWN_PCT", 0.0)
    monkeypatch.setattr(position_manager, "TRAILING_STOP_PCT", 0.0)
    monkeypatch.setattr(drawdown_guard, "_last_alert_at", {})


# Cost + funding entry gate isolation
# ============================================================================
#
# ``COST_GATE_ENABLED`` is a runtime setting whose startup default comes from
# the environment, and runtime overrides are process-global. A developer
# environment with the gate on (or a test that left an override behind) would
# make every open_positions test price entries against funding rates the fakes
# do not carry. The default is pinned off and any leaked override removed;
# tests that exercise the gate set the override themselves via monkeypatch.
@pytest.fixture(autouse=True)
def _isolate_cost_gate_settings(monkeypatch):
    from src.trading import arbitrage_runtime_config

    monkeypatch.setitem(arbitrage_runtime_config._DEFAULTS, "COST_GATE_ENABLED", False)
    monkeypatch.delitem(
        arbitrage_runtime_config._overrides, "COST_GATE_ENABLED", raising=False
    )
