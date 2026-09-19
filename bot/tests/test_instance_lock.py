"""Single-writer advisory lock per trading instance."""

import os
from types import SimpleNamespace

import pytest

from src.trading.instance_lock import (
    InstanceAlreadyRunningError,
    InstanceLock,
    InstanceLockError,
    advisory_key,
)


class _FakeConnection:
    def __init__(self, engine):
        self._engine = engine
        self.closed = False

    def execute(self, statement, params=None):
        sql = str(statement)
        if self._engine.fail_next_execute:
            self._engine.fail_next_execute = False
            raise ConnectionError("server closed the connection unexpectedly")
        if "pg_try_advisory_lock" in sql:
            granted = self._engine.holder is None
            if granted:
                self._engine.holder = self
            return SimpleNamespace(scalar=lambda: granted)
        if "pg_locks" in sql:
            return SimpleNamespace(scalar=lambda: self._engine.holder is self)
        if "pg_advisory_unlock" in sql:
            if self._engine.holder is self:
                self._engine.holder = None
            return SimpleNamespace(scalar=lambda: True)
        raise AssertionError(f"unexpected SQL: {sql}")

    def detach(self):
        self.detached = True

    def commit(self):
        return None

    def close(self):
        self.closed = True
        if self._engine.holder is self:
            self._engine.holder = None


class _FakeEngine:
    def __init__(self, dialect="postgresql"):
        self.dialect = SimpleNamespace(name=dialect)
        self.holder = None
        self.fail_next_execute = False
        self.connections = []

    def connect(self):
        connection = _FakeConnection(self)
        self.connections.append(connection)
        return connection


def test_advisory_key_is_stable_signed_and_distinct():
    key = advisory_key("bot-1")

    assert key == advisory_key("bot-1")
    assert key != advisory_key("bot-2")
    assert -(2**63) <= key < 2**63


def test_second_process_for_the_same_instance_is_refused():
    engine = _FakeEngine()
    first = InstanceLock(engine, "bot-1")
    first.acquire()

    with pytest.raises(InstanceAlreadyRunningError):
        InstanceLock(engine, "bot-1").acquire()

    # The refused attempt must not leak its connection.
    assert engine.connections[-1].closed is True


def test_lock_connection_is_detached_from_the_pool():
    """A pooled connection survives close(), and the lock with it."""
    engine = _FakeEngine()
    InstanceLock(engine, "bot-1").acquire()

    assert getattr(engine.connections[0], "detached", False) is True


def test_release_lets_the_next_process_start():
    engine = _FakeEngine()
    first = InstanceLock(engine, "bot-1")
    first.acquire()
    first.release()

    InstanceLock(engine, "bot-1").acquire()


def test_ensure_held_retakes_the_lock_after_a_dropped_connection():
    engine = _FakeEngine()
    lock = InstanceLock(engine, "bot-1")
    lock.acquire()
    engine.holder = None  # PostgreSQL dropped the session and with it the lock
    engine.fail_next_execute = True

    lock.ensure_held()

    assert engine.holder is engine.connections[-1]
    assert len(engine.connections) == 2


def test_ensure_held_stops_trading_when_another_process_took_over():
    engine = _FakeEngine()
    lock = InstanceLock(engine, "bot-1")
    lock.acquire()
    # The connection died and a second process acquired the lock meanwhile.
    engine.holder = None
    usurper = InstanceLock(engine, "bot-1")
    usurper.acquire()

    with pytest.raises(InstanceAlreadyRunningError):
        lock.ensure_held()


def test_ensure_held_without_acquire_fails_closed():
    with pytest.raises(InstanceLockError):
        InstanceLock(_FakeEngine(), "bot-1").ensure_held()


def test_non_postgres_database_is_refused():
    with pytest.raises(InstanceLockError, match="PostgreSQL"):
        InstanceLock(_FakeEngine(dialect="sqlite"), "bot-1").acquire()


_REAL_DSN = os.getenv("INSTANCE_LOCK_TEST_DSN", "").strip()


@pytest.mark.skipif(not _REAL_DSN, reason="INSTANCE_LOCK_TEST_DSN is not set")
def test_real_postgres_enforces_one_holder_and_frees_on_disconnect():
    from sqlalchemy import create_engine

    engine = create_engine(_REAL_DSN)
    try:
        first = InstanceLock(engine, "bot-real-1")
        first.acquire()
        first.ensure_held()  # the pg_locks probe must find our own lock

        with pytest.raises(InstanceAlreadyRunningError):
            InstanceLock(engine, "bot-real-1").acquire()

        # A different instance id is independent.
        other = InstanceLock(engine, "bot-real-2")
        other.acquire()
        other.release()

        # Dropping the holder's connection (a crash) frees the lock.
        first._discard_connection()
        second = InstanceLock(engine, "bot-real-1")
        second.acquire()
        second.ensure_held()
        second.release()
    finally:
        engine.dispose()


# --- runtime wiring -----------------------------------------------------------


def _runtime(monkeypatch, engine, **env):
    import importlib

    main_instance = importlib.import_module("src.main_instance")
    for key in ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(main_instance.db, "get_engine", lambda: engine)
    bot = main_instance.BotInstance("bot-1")
    bot.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    return bot


def test_runtime_refuses_to_start_a_second_trader(monkeypatch):
    engine = _FakeEngine()
    first = _runtime(monkeypatch, engine, ENVIRONMENT="production")
    first._acquire_instance_lock()

    second = _runtime(monkeypatch, engine, ENVIRONMENT="production")
    with pytest.raises(InstanceAlreadyRunningError):
        second._acquire_instance_lock()

    first._release_instance_lock()
    second._acquire_instance_lock()
    assert second.instance_lock is not None


@pytest.mark.parametrize("env", [{}, {"ENVIRONMENT": "production"}])
def test_lock_is_mandatory_outside_dev_and_test(monkeypatch, env):
    bot = _runtime(monkeypatch, _FakeEngine(dialect="sqlite"), **env)

    with pytest.raises(InstanceLockError):
        bot._acquire_instance_lock()


def test_dev_run_without_postgres_continues_without_the_lock(monkeypatch):
    bot = _runtime(
        monkeypatch, _FakeEngine(dialect="sqlite"), ENVIRONMENT="development"
    )

    bot._acquire_instance_lock()

    assert bot.instance_lock is None


def test_a_held_lock_refuses_even_in_dev(monkeypatch):
    engine = _FakeEngine()
    _runtime(monkeypatch, engine, ENVIRONMENT="development")._acquire_instance_lock()

    with pytest.raises(InstanceAlreadyRunningError):
        _runtime(
            monkeypatch, engine, ENVIRONMENT="development"
        )._acquire_instance_lock()


def test_unreachable_database_stops_a_production_start(monkeypatch):
    class _DownEngine(_FakeEngine):
        def connect(self):
            raise ConnectionError("connection refused")

    bot = _runtime(monkeypatch, _DownEngine(), ENVIRONMENT="production")
    with pytest.raises(ConnectionError):
        bot._acquire_instance_lock()

    dev = _runtime(monkeypatch, _DownEngine(), ENVIRONMENT="development")
    dev._acquire_instance_lock()
    assert dev.instance_lock is None
