"""Unit coverage for src/infrastructure/database.py.

Pool helpers, the ConnectionPoolMonitor, DatabaseConfig projection methods,
and a fork-isolated DatabaseManager (built via object.__new__ so the shared
singleton is never touched). No real database connections are made.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import src.infrastructure.database as database
from src.infrastructure.database import (
    ConnectionPoolMonitor,
    DatabaseConfig,
    DatabaseManager,
    _pool_metric,
    _resolve_pool_max_overflow,
)


def _fresh_manager(**attrs):
    """Build a DatabaseManager without triggering the singleton or __init__."""
    manager = object.__new__(DatabaseManager)
    manager._engine = None
    manager._session_factory = None
    manager._pool_monitor = None
    manager.config = None
    for key, value in attrs.items():
        setattr(manager, key, value)
    return manager


class _FakePool:
    """QueuePool-shaped stand-in exposing stat callables and _max_overflow."""

    def __init__(self, size=5, checkedout=2, overflow=1, max_overflow=10):
        self._size = size
        self._checkedout = checkedout
        self._overflow = overflow
        self._max_overflow = max_overflow

    def size(self):
        return self._size

    def checkedout(self):
        return self._checkedout

    def overflow(self):
        return self._overflow


# --- pool helpers --------------------------------------------------------------


def test_pool_metric_variants():
    assert _pool_metric(_FakePool(), "size") == 5
    # Non-callable attributes yield None by design (base Pool lacks stat methods).
    assert _pool_metric(SimpleNamespace(size=7), "size") is None
    assert _pool_metric(SimpleNamespace(), "missing") is None
    assert _pool_metric(None, "size") is None


def test_resolve_pool_max_overflow_matrix():
    assert _resolve_pool_max_overflow(_FakePool(max_overflow=10), 5) == 10
    assert _resolve_pool_max_overflow(_FakePool(max_overflow=None), 4) == 4

    class _CallablePool:
        _max_overflow = 7

        def max_overflow(self):
            return 99  # callable form wins when larger

    assert _resolve_pool_max_overflow(_CallablePool(), 0) == 99

    class _GarbagePool:
        max_overflow = "junk"
        _max_overflow = None

    assert _resolve_pool_max_overflow(_GarbagePool(), -3) == 0
    assert _resolve_pool_max_overflow(None, 0) == 0


# --- ConnectionPoolMonitor -------------------------------------------------------


def _monitor(**kwargs):
    defaults = dict(
        alert_threshold_percentage=80.0,
        monitoring_interval_seconds=0,
        configured_max_overflow=0,
    )
    defaults.update(kwargs)
    return ConnectionPoolMonitor(**defaults)


def _collect(monitor, pool):
    monitor._pool = pool
    monitor._collect_metrics()


def test_pool_monitor_collect_metrics_utilization():
    monitor = _monitor()
    _collect(monitor, _FakePool(size=10, checkedout=9, overflow=1, max_overflow=0))
    metric = monitor._metrics_history[-1]
    assert metric["pool_size"] == 10
    assert metric["checked_out"] == 9
    assert metric["available"] == 1
    assert metric["max_size"] == 10
    assert metric["utilization_percentage"] == pytest.approx(90.0)

    # Zero-capacity pools report 0% utilization instead of dividing by zero.
    empty = _monitor()
    _collect(empty, _FakePool(size=0, checkedout=0, overflow=0, max_overflow=0))
    assert empty._metrics_history[-1]["utilization_percentage"] == 0.0

    # A None pool and a raising pool are logged, not raised.
    none_pool = _monitor()
    none_pool._pool = None
    none_pool._collect_metrics()
    assert not none_pool._metrics_history


def test_pool_monitor_alerts_and_cooldown():
    monitor = _monitor(alert_threshold_percentage=80.0)
    _collect(monitor, _FakePool(size=10, checkedout=9, overflow=0, max_overflow=0))
    monitor._check_alerts()
    assert monitor._last_alert_time is not None

    # Cooldown suppresses a second alert even if the condition persists.
    first_alert_time = monitor._last_alert_time
    monitor._check_alerts()
    assert monitor._last_alert_time == first_alert_time

    # Failure-rate alert: five recent failures trip independently.
    failure_monitor = _monitor()
    _collect(
        failure_monitor, _FakePool(size=10, checkedout=1, overflow=0, max_overflow=0)
    )
    for _ in range(5):
        failure_monitor.record_connection_failure(RuntimeError("conn refused"))
    failure_monitor._check_alerts()
    assert failure_monitor._last_alert_time is not None

    # Empty history and stale failure windows do not alert.
    quiet = _monitor()
    quiet._check_alerts()
    assert quiet._last_alert_time is None
    stale = _monitor()
    _collect(stale, _FakePool(size=10, checkedout=1, overflow=0, max_overflow=0))
    with stale._lock:
        stale._connection_failures.extend(
            [datetime.utcnow() - timedelta(minutes=10) for _ in range(6)]
        )
    stale._check_alerts()
    assert stale._last_alert_time is None


def test_pool_monitor_current_metrics_and_history():
    monitor = _monitor()
    empty = monitor.get_current_metrics()
    assert empty == {"status": "no_metrics", "monitoring_active": False}

    monitor.record_connection_failure(RuntimeError("boom"))
    monitor.record_connection_timeout(1.5)
    _collect(monitor, _FakePool(size=10, checkedout=5, overflow=0, max_overflow=0))
    _collect(monitor, _FakePool(size=10, checkedout=2, overflow=0, max_overflow=0))

    metrics = monitor.get_current_metrics()
    assert metrics["status"] == "monitoring"
    assert metrics["pool_size"] == 10
    assert metrics["checked_out"] == 2
    assert metrics["utilization_percentage"] == 20.0
    assert metrics["max_utilization_percentage"] == 50.0
    assert metrics["min_utilization_percentage"] == 20.0
    assert metrics["recent_failures_5min"] == 1
    assert metrics["recent_timeouts_5min"] == 1
    assert metrics["total_metrics_samples"] == 2
    assert metrics["alert_thresholds"]["utilization_percentage"] == 80.0

    history = monitor.get_metrics_history(limit=1)
    assert len(history) == 1
    assert isinstance(history[0]["timestamp"], str)


def test_pool_monitor_health_status_matrix():
    monitor = _monitor()
    assert monitor.get_health_status() == {
        "status": "unknown",
        "message": "No metrics collected yet",
    }

    _collect(monitor, _FakePool(size=10, checkedout=5, overflow=0, max_overflow=0))
    assert monitor.get_health_status()["status"] == "healthy"

    warning = _monitor()
    _collect(warning, _FakePool(size=10, checkedout=7, overflow=0, max_overflow=0))
    assert warning.get_health_status()["status"] == "warning"  # 70% of 80% threshold

    critical = _monitor()
    _collect(critical, _FakePool(size=10, checkedout=9, overflow=0, max_overflow=0))
    assert critical.get_health_status()["status"] == "critical"

    failures = _monitor()
    _collect(failures, _FakePool(size=10, checkedout=1, overflow=0, max_overflow=0))
    for _ in range(3):
        failures.record_connection_failure(RuntimeError("x"))
    health = failures.get_health_status()
    assert health["status"] == "critical"
    assert "Connection failures" in health["message"]


def test_pool_monitor_start_stop_and_loop(monkeypatch):
    monitor = _monitor(monitoring_interval_seconds=0)
    pool = _FakePool()
    monitor.start_monitoring(pool, engine_name="unit")
    assert monitor._monitoring_active is True

    # Double start warns and keeps the original thread.
    first_thread = monitor._monitoring_thread
    monitor.start_monitoring(pool, engine_name="unit")
    assert monitor._monitoring_thread is first_thread

    monitor.stop_monitoring()
    assert monitor._monitoring_active is False
    assert monitor._monitoring_thread is None
    monitor.stop_monitoring()  # idempotent

    # Drive one iteration of the loop deterministically: sleep disables the loop.
    loop_monitor = _monitor()
    loop_monitor._pool = _FakePool(size=4, checkedout=2, overflow=0, max_overflow=0)
    loop_monitor._monitoring_active = True

    def _stop_during_sleep(seconds):
        loop_monitor._monitoring_active = False

    monkeypatch.setattr(database.time, "sleep", _stop_during_sleep)
    loop_monitor._monitor_pool()
    assert loop_monitor._metrics_history

    # A raising collect is logged and the loop keeps sleeping (then stops).
    exploding = _monitor()
    exploding._pool = None
    exploding._monitoring_active = True
    calls = {"count": 0}

    def _count_and_stop(seconds):
        calls["count"] += 1
        exploding._monitoring_active = False

    monkeypatch.setattr(database.time, "sleep", _count_and_stop)
    exploding._collect_metrics = lambda: (_ for _ in ()).throw(
        RuntimeError("pool gone")
    )
    exploding._monitor_pool()
    assert calls["count"] >= 1


# --- DatabaseConfig projections ----------------------------------------------------


def test_database_config_connection_string_and_engine_kwargs(monkeypatch):
    for name in (
        "DATABASE_URL",
        "BOT_DATABASE_URL",
        "DB_HOST",
        "BOT_DB_HOST",
        "DB_SSLMODE",
        "DB_TIMEOUT",
        "DB_POOL_SIZE",
        "DB_MAX_OVERFLOW",
        "DB_ECHO",
    ):
        monkeypatch.delenv(name, raising=False)

    with_url = DatabaseConfig()
    with_url.database_url = "postgresql://u:p@h:5432/custom"
    assert with_url.get_connection_string() == "postgresql://u:p@h:5432/custom"

    config = DatabaseConfig()
    config.database_url = None
    config.ssl_mode = True
    config.timeout_seconds = 7
    built = config.get_connection_string()
    assert built.startswith("postgresql+psycopg2://")
    assert "sslmode=require" in built
    assert "connect_timeout=7" in built
    assert "timezone" in built  # url-encoded inside the options query param

    config.ssl_mode = False
    assert "sslmode=disable" in config.get_connection_string()

    kwargs = config.get_engine_kwargs()
    assert kwargs["pool_size"] == config.pool_size
    assert kwargs["max_overflow"] == config.max_overflow
    assert kwargs["pool_pre_ping"] == config.pool_pre_ping
    assert kwargs["connect_args"]["connect_timeout"] == config.timeout_seconds
    assert kwargs["connect_args"]["options"] == "-c timezone=UTC"
    assert kwargs["echo"] is False and kwargs["future"] is True


def test_database_config_to_diagnostics_shape(monkeypatch):
    for name in ("DATABASE_URL", "BOT_DATABASE_URL", "DB_HOST", "BOT_DB_HOST"):
        monkeypatch.delenv(name, raising=False)
    config = DatabaseConfig()
    diagnostics = config.to_diagnostics()
    assert diagnostics["db_type"] == config.db_type
    assert diagnostics["pool_size"] == config.pool_size
    assert diagnostics["max_overflow"] == config.max_overflow
    assert diagnostics["password_configured"] is bool(config.db_password)
    assert diagnostics["max_connections"] == config.pool_size + config.max_overflow
    assert diagnostics["ownership_guardrail"] in {"enforced", "advisory"}


# --- DatabaseManager -----------------------------------------------------------------


class _RecordingSession:
    """Session stand-in usable as a context manager."""

    def __init__(self, *, execute_error=None):
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self._execute_error = execute_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def execute(self, statement):
        if self._execute_error is not None:
            raise self._execute_error
        self.executed.append(str(statement))
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closes += 1


class _FakeEngine:
    def __init__(self, *, tables=(), columns=None, connect_error=None, pool=None):
        self.tables = set(tables)
        self._columns = columns or {}
        self._connect_error = connect_error
        self.disposed = 0
        self.begin_calls = 0
        self.pool = pool

    def dispose(self):
        self.disposed += 1

    def begin(self):
        self.begin_calls += 1
        engine = self

        class _Connection:
            def execute(self, statement):
                if engine._connect_error is not None:
                    raise engine._connect_error
                return None

        class _Begin:
            def __enter__(self):
                return _Connection()

            def __exit__(self, *args):
                return False

        return _Begin()


def _fake_inspector(engine):
    engine_ref = engine

    class _Inspector:
        def has_table(self, name):
            return name in engine_ref.tables

        def get_table_names(self):
            return sorted(engine_ref.tables)

        def get_columns(self, table):
            return engine_ref._columns.get(table, [])

    return _Inspector()


def test_manager_fork_reset_variants():
    idle = _fresh_manager()
    idle._after_fork_child_reset()  # no engine: no-op

    engine = _FakeEngine()
    healthy = _fresh_manager(_engine=engine)
    healthy._after_fork_child_reset()
    assert engine.disposed == 1

    class _ExplodingEngine(_FakeEngine):
        def dispose(self):
            raise RuntimeError("dispose failed")

    failing = _fresh_manager(_engine=_ExplodingEngine())
    failing._after_fork_child_reset()  # logged, not raised


def test_manager_get_engine_and_session_lazy_init():
    manager = _fresh_manager()
    initialized = []
    lazy_engine = _FakeEngine()

    def _lazy_initialize():
        initialized.append(True)
        manager._engine = lazy_engine

    manager._initialize = _lazy_initialize
    assert manager.get_engine() is lazy_engine  # lazy init path
    assert initialized == [True]

    broken = _fresh_manager()
    broken._initialize = lambda: None  # init that fails to set the engine
    with pytest.raises(RuntimeError, match="engine is not initialized"):
        broken.get_engine()

    uninitialized = _fresh_manager()
    uninitialized._initialize = lambda: None
    with pytest.raises(RuntimeError, match="session factory"):
        uninitialized.get_session()

    factory_calls = []
    session = object()
    manager._session_factory = lambda: (factory_calls.append(1), session)[1]
    assert manager.get_session() is session
    assert len(factory_calls) == 1


def test_manager_session_scope_commit_and_rollback():
    session = _RecordingSession()
    manager = _fresh_manager()
    manager.get_session = lambda: session

    with manager.session_scope():
        pass
    assert session.commits == 1
    assert session.closes == 1

    with pytest.raises(RuntimeError, match="body failed"):
        with manager.session_scope():
            raise RuntimeError("body failed")
    assert session.rollbacks == 1
    assert session.closes == 2


def test_manager_create_and_drop_tables(monkeypatch):
    import internal.domain as domain

    calls = []
    fake_base = SimpleNamespace(
        metadata=SimpleNamespace(
            create_all=lambda bind: calls.append(("create", bind)),
            drop_all=lambda bind: calls.append(("drop", bind)),
        )
    )
    monkeypatch.setattr(domain, "Base", fake_base)
    engine = _FakeEngine()
    manager = _fresh_manager(_engine=engine)

    manager.create_all_tables()
    manager.drop_all_tables()
    assert calls == [("create", engine), ("drop", engine)]


def test_manager_health_check_paths():
    ok_session = _RecordingSession()
    manager = _fresh_manager()
    manager.get_session = lambda: ok_session
    assert manager.health_check() is True
    assert ok_session.executed == ["SELECT 1"]

    recorded = []
    failing_session = _RecordingSession(execute_error=RuntimeError("db down"))
    failing = _fresh_manager()
    failing.get_session = lambda: failing_session
    failing._pool_monitor = SimpleNamespace(
        record_connection_failure=lambda error: recorded.append(error)
    )
    assert failing.health_check() is False
    assert recorded and isinstance(recorded[0], RuntimeError)


def test_manager_verify_required_tables(monkeypatch):
    required = {
        "bot_instances",
        "jobs",
        "event_logs",
        "trades",
        "backtest_runtime_runs",
        "tracked_positions",
        "cointegrated_pairs",
    }
    engine = _FakeEngine(tables=required)
    manager = _fresh_manager(_engine=engine)
    monkeypatch.setattr(database, "inspect", lambda bindable: _fake_inspector(engine))
    result = manager.verify_required_tables()
    assert result["missing"] == []
    assert result["required"] == sorted(required)

    incomplete_engine = _FakeEngine(tables={"bot_instances"})
    incomplete = _fresh_manager(_engine=incomplete_engine)
    monkeypatch.setattr(
        database, "inspect", lambda bindable: _fake_inspector(incomplete_engine)
    )
    with pytest.raises(RuntimeError, match="missing required tables"):
        incomplete.verify_required_tables()


def test_manager_schema_compatibility_applies_fixes(monkeypatch):
    engine = _FakeEngine(
        tables={"bot_instances", "backtest_strategies", "positions_realtime"},
        columns={
            "backtest_strategies": [{"name": "id"}],  # pair_selection_mode missing
            "positions_realtime": [{"name": "id"}],  # all compat columns missing
        },
    )
    manager = _fresh_manager(_engine=engine)
    monkeypatch.setattr(database, "inspect", lambda bindable: _fake_inspector(engine))
    manager.ensure_schema_compatibility()
    assert engine.begin_calls == 1

    # jobs.bot_id NOT NULL -> dropped; backtest_runtime_runs columns added.
    jobs_engine = _FakeEngine(
        tables={"jobs", "backtest_runtime_runs"},
        columns={
            "jobs": [{"name": "bot_id", "nullable": False}],
            "backtest_runtime_runs": [{"name": "id"}],
        },
    )
    jobs_manager = _fresh_manager(_engine=jobs_engine)
    monkeypatch.setattr(
        database, "inspect", lambda bindable: _fake_inspector(jobs_engine)
    )
    jobs_manager.ensure_schema_compatibility()
    assert jobs_engine.begin_calls == 1


def test_manager_build_alembic_config_escapes_url(monkeypatch):
    monkeypatch.setattr(
        database,
        "DatabaseConfig",
        lambda: SimpleNamespace(
            get_connection_string=lambda: "postgresql://u:p%40ss@h:5432/db?x=%2F1"
        ),
    )
    config = database.db._build_alembic_config()
    assert config is not None
    # get_main_option re-interpolates %% back to single percent signs.
    url = config.get_main_option("sqlalchemy.url")
    assert url == "postgresql://u:p%40ss@h:5432/db?x=%2F1"


def test_manager_alembic_baseline_and_migrations(monkeypatch):
    stamped = []
    upgraded = []
    monkeypatch.setattr(
        database.command, "stamp", lambda config, revision: stamped.append(revision)
    )
    monkeypatch.setattr(
        database.command, "upgrade", lambda config, target: upgraded.append(target)
    )
    monkeypatch.setattr(
        database,
        "DatabaseConfig",
        lambda: SimpleNamespace(get_connection_string=lambda: "sqlite://"),
    )

    # Already versioned: no stamp, straight to upgrade in run_pending_migrations.
    versioned_engine = _FakeEngine(tables={"alembic_version"})
    manager = _fresh_manager(_engine=versioned_engine)
    monkeypatch.setattr(
        database, "inspect", lambda bindable: _fake_inspector(versioned_engine)
    )
    assert manager.ensure_alembic_baseline() == "already-versioned"
    manager.run_pending_migrations()
    assert stamped == []
    assert upgraded == ["head"]

    # Legacy schema without alembic_version: stamped at the baseline.
    legacy_engine = _FakeEngine(tables={"bot_instances", "backtest_strategies"})
    legacy = _fresh_manager(_engine=legacy_engine)
    monkeypatch.setattr(
        database, "inspect", lambda bindable: _fake_inspector(legacy_engine)
    )
    assert legacy.ensure_alembic_baseline() == "stamped"
    assert stamped == ["0003_backtest_storage_cols"]

    # Empty schema: bootstrap migrations from base.
    empty_engine = _FakeEngine(tables=set())
    empty = _fresh_manager(_engine=empty_engine)
    monkeypatch.setattr(
        database, "inspect", lambda bindable: _fake_inspector(empty_engine)
    )
    upgraded.clear()
    assert empty.ensure_alembic_baseline() == "skipped-core-schema-not-detected"
    empty.run_pending_migrations()
    assert upgraded == ["head"]

    # Legacy core schema + fake stamp (no table created): migrations skip
    # with the legacy-schema warning instead of upgrading blindly.
    upgraded.clear()
    stale_engine = _FakeEngine(tables={"bot_instances", "backtest_strategies"})
    stale = _fresh_manager(_engine=stale_engine)
    monkeypatch.setattr(
        database, "inspect", lambda bindable: _fake_inspector(stale_engine)
    )
    stale.run_pending_migrations()
    assert upgraded == []


def test_manager_pool_accessors_and_diagnostics():
    unmonitored = _fresh_manager()
    assert unmonitored.get_pool_metrics()["status"] == "not_monitored"
    assert unmonitored.get_pool_health_status()["status"] == "unknown"
    assert unmonitored.get_pool_metrics_history() == []

    monitor = _monitor()
    _collect(monitor, _FakePool(size=10, checkedout=5, overflow=0, max_overflow=0))
    monitored = _fresh_manager(
        _engine=_FakeEngine(pool=_FakePool(size=10, checkedout=5)),
        _pool_monitor=monitor,
        config=SimpleNamespace(
            to_diagnostics=lambda: {"db_type": "postgresql"}, max_overflow=0
        ),
    )
    diagnostics = monitored.get_diagnostics()
    assert diagnostics["database"]["db_type"] == "postgresql"
    assert diagnostics["pool_info"]["pool_class"] == "_FakePool"
    assert diagnostics["pool_info"]["size"] == 10
    assert diagnostics["pool_info"]["checked_out"] == 5

    broken = _fresh_manager()
    broken.get_engine = lambda: (_ for _ in ()).throw(RuntimeError("no engine"))
    broken_diagnostics = broken.get_diagnostics()
    assert "error" in broken_diagnostics["pool_info"]


def test_manager_register_fork_hook_guards(monkeypatch):
    manager = _fresh_manager()
    manager._fork_hook_registered = True
    manager._register_fork_hook()  # already registered: no-op

    fresh = _fresh_manager()
    monkeypatch.delattr("os.register_at_fork", raising=False)
    fresh._register_fork_hook()  # no hook support: no-op
    assert fresh._fork_hook_registered is False
