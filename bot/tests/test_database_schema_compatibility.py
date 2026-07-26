from contextlib import contextmanager
from typing import cast

from sqlalchemy.engine import Engine
from src.infrastructure.database import DatabaseManager


class _FakeConnection:
    def __init__(self):
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))

        class _Result:
            @staticmethod
            def scalar():
                return None

        return _Result()


class _FakeEngine:
    def __init__(self, connection):
        self._connection = connection

    @contextmanager
    def begin(self):
        yield self._connection


class _FakeInspector:
    def __init__(self, columns):
        self._columns = columns

    def has_table(self, table_name):
        return table_name == "positions_realtime"

    def get_columns(self, table_name):
        if table_name == "positions_realtime":
            return [{"name": c} for c in self._columns]
        return []


def _make_manager_with_inspector(monkeypatch, columns):
    fake_connection = _FakeConnection()
    fake_engine = _FakeEngine(fake_connection)
    fake_inspector = _FakeInspector(columns)

    manager = DatabaseManager.__new__(DatabaseManager)
    monkeypatch.setattr(
        manager,
        "get_engine",
        lambda: cast(Engine, fake_engine),
    )

    monkeypatch.setattr("src.infrastructure.database.inspect", lambda _: fake_inspector)

    return manager, fake_connection


def test_ensure_schema_compatibility_adds_missing_realtime_metadata_columns(
        monkeypatch,
):
    manager, connection = _make_manager_with_inspector(
        monkeypatch,
        columns={
            "id",
            "bot_instance_id",
            "position_id",
            "pair1",
            "pair2",
            "status",
        },
    )

    manager.ensure_schema_compatibility()

    statements = "\n".join(connection.statements)
    assert "ADD COLUMN hedge_ratio DOUBLE PRECISION" in statements
    assert "ADD COLUMN correlation DOUBLE PRECISION" in statements
    assert "ADD COLUMN half_life DOUBLE PRECISION" in statements
    assert "ADD COLUMN funding_rate DOUBLE PRECISION" in statements
    assert "ADD COLUMN dydx_order_ids JSON" in statements
    assert "ADD COLUMN dydx_position_id VARCHAR(100)" in statements


def test_ensure_schema_compatibility_skips_existing_realtime_metadata_columns(
        monkeypatch,
):
    manager, connection = _make_manager_with_inspector(
        monkeypatch,
        columns={
            "id",
            "bot_instance_id",
            "position_id",
            "pair1",
            "pair2",
            "status",
            "hedge_ratio",
            "correlation",
            "half_life",
            "funding_rate",
            "dydx_order_ids",
            "dydx_position_id",
        },
    )

    manager.ensure_schema_compatibility()

    assert connection.statements == []
