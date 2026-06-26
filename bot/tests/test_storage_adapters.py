from __future__ import annotations

from pathlib import Path

from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.storage import (
    ClickHouseAnalyticsWriter,
    LocalArtifactStore,
    MinIOArtifactStore,
    NoopAnalyticsWriter,
)


class _FakeObjectResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def close(self) -> None:
        return None

    def release_conn(self) -> None:
        return None


class _FakeMinioClient:
    def __init__(self):
        self.buckets: set[str] = set()
        self.objects: dict[tuple[str, str], bytes] = {}

    def bucket_exists(self, bucket: str) -> bool:
        return bucket in self.buckets

    def make_bucket(self, bucket: str) -> None:
        self.buckets.add(bucket)

    def put_object(self, bucket: str, key: str, data, length: int, content_type: str):
        del content_type
        self.objects[(bucket, key)] = data.read(length)

    def get_object(self, bucket: str, key: str) -> _FakeObjectResponse:
        return _FakeObjectResponse(self.objects[(bucket, key)])

    def stat_object(self, bucket: str, key: str):
        if (bucket, key) not in self.objects:
            raise FileNotFoundError(key)
        return {"bucket": bucket, "key": key}


class _FailingMinioClient(_FakeMinioClient):
    def put_object(self, bucket: str, key: str, data, length: int, content_type: str):
        del bucket, key, data, length, content_type
        raise RuntimeError("simulated minio outage")


def test_local_artifact_store_round_trip(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")

    ref = store.put_text("runs/run-123/log.txt", "hello world")

    assert ref.startswith("file:")
    assert store.exists("runs/run-123/log.txt") is True
    assert store.read_text("runs/run-123/log.txt") == "hello world"
    assert Path(ref.replace("file://", "")).read_text() == "hello world"


def test_minio_artifact_store_uses_local_fallback_when_disabled(tmp_path):
    fallback = LocalArtifactStore(tmp_path / "local")
    store = MinIOArtifactStore(
        bucket="backtests",
        enabled=False,
        fallback=fallback,
        endpoint_url="http://minio:9000",
    )

    ref = store.put_bytes("artifacts/raw.bin", b"payload")

    assert ref.startswith("file:")
    assert fallback.read_bytes("artifacts/raw.bin") == b"payload"
    assert (
        store.reference_for("artifacts/raw.bin") == "s3://backtests/artifacts/raw.bin"
    )


def test_noop_analytics_writer_discards_rows():
    writer = NoopAnalyticsWriter()

    assert writer.write_rows("backtest_trades", [{"id": 1}]) == 0


def test_clickhouse_writer_enabled_without_server_falls_back_to_noop():
    # When enabled=True but no real ClickHouse server and no injected client,
    # the writer must fall back gracefully rather than raising.
    writer = ClickHouseAnalyticsWriter(enabled=True)

    # _client will be None because localhost:8123 is unavailable in CI
    count = writer.write_rows(
        "backtest_trades", [{"trade_id": "t1"}, {"trade_id": "t2"}]
    )

    # Noop fallback returns 0 — the important invariant is no exception raised
    assert count == 0
    assert writer.get_buffer("backtest_trades") == []


def test_minio_artifact_store_writes_and_reads_with_enabled_client(tmp_path):
    fallback = LocalArtifactStore(tmp_path / "local")
    client = _FakeMinioClient()
    store = MinIOArtifactStore(
        bucket="backtests",
        enabled=True,
        fallback=fallback,
        endpoint_url="http://minio:9000",
        extra_config={
            "client": client,
            "auto_create_bucket": True,
        },
    )

    ref = store.put_bytes("backtests/run-1/result.json", b'{"ok":true}')

    assert ref == "s3://backtests/backtests/run-1/result.json"
    assert store.exists("backtests/run-1/result.json") is True
    assert store.read_bytes("backtests/run-1/result.json") == b'{"ok":true}'
    assert fallback.exists("backtests/run-1/result.json") is False


def test_minio_artifact_store_falls_back_when_enabled_client_fails(tmp_path):
    fallback = LocalArtifactStore(tmp_path / "local")
    store = MinIOArtifactStore(
        bucket="backtests",
        enabled=True,
        fallback=fallback,
        endpoint_url="http://minio:9000",
        extra_config={"client": _FailingMinioClient()},
    )

    ref = store.put_bytes("run-2/out.bin", b"payload")

    assert ref.startswith("file:")
    assert fallback.read_bytes("run-2/out.bin") == b"payload"


def test_backtest_repository_resolves_minio_endpoint_aliases(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9010")
    monkeypatch.setenv("S3_ENDPOINT", "http://localhost:9010")

    assert BacktestRepository._resolve_minio_endpoint() == "http://localhost:9010"


def test_backtest_repository_resolves_clickhouse_url_alias(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_URL", "http://analytics:8123/dydx_analytics")

    host, port, secure, database, username, password = (
        BacktestRepository._resolve_clickhouse_target()
    )

    assert host == "analytics"
    assert port == 8123
    assert secure is False
    assert database == "dydx_analytics"
    assert username == "default"
    assert password == ""


# ---------------------------------------------------------------------------
# ClickHouse analytics writer — real implementation tests
# ---------------------------------------------------------------------------


class _FakeClickHouseClient:
    """Minimal test double that records inserts and DDL commands."""

    def __init__(self):
        self.commands: list[str] = []
        self.inserts: list[dict] = []

    def command(self, sql: str) -> None:
        self.commands.append(sql)

    def insert(self, *, table: str, data: list, column_names: list) -> None:
        for row_values in data:
            self.inserts.append(dict(zip(column_names, row_values)))


class _FailingClickHouseClient(_FakeClickHouseClient):
    def insert(self, *, table: str, data: list, column_names: list) -> None:
        raise RuntimeError("simulated clickhouse outage")


def test_clickhouse_writer_inserts_rows_with_real_client():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={"client": client},
    )

    count = writer.write_rows(
        "backtest_trade_rows",
        [{"run_id": "r1", "trade_id": "t1"}, {"run_id": "r1", "trade_id": "t2"}],
    )

    assert count == 2
    assert len(client.inserts) == 2
    assert client.inserts[0]["run_id"] == "r1"
    assert client.inserts[1]["trade_id"] == "t2"


def test_clickhouse_writer_provisions_known_table_on_first_write():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={"client": client},
    )

    writer.write_rows(
        "backtest_daily_pnl_rows", [{"run_id": "r1", "date": "2026-01-01"}]
    )

    assert any("backtest_daily_pnl_rows" in cmd for cmd in client.commands)


def test_clickhouse_writer_does_not_reprovision_on_subsequent_writes():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={"client": client},
    )

    writer.write_rows("backtest_trade_rows", [{"run_id": "r1"}])
    writer.write_rows("backtest_trade_rows", [{"run_id": "r2"}])

    # DDL should only be issued once
    ddl_count = sum(1 for cmd in client.commands if "backtest_trade_rows" in cmd)
    assert ddl_count == 1


def test_clickhouse_writer_falls_back_on_insert_error():
    client = _FailingClickHouseClient()
    fallback = NoopAnalyticsWriter()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        fallback=fallback,
        extra_config={"client": client},
    )

    # Should not raise; falls back silently
    count = writer.write_rows("backtest_trade_rows", [{"run_id": "r1"}])

    # Noop fallback returns 0; the writer delegates on failure
    assert count == 0


def test_clickhouse_writer_uses_noop_fallback_when_disabled():
    writer = ClickHouseAnalyticsWriter(enabled=False)

    count = writer.write_rows("backtest_trade_rows", [{"run_id": "r1"}])

    assert count == 0
    assert writer._client is None


def test_clickhouse_writer_get_buffer_returns_empty_list():
    """get_buffer is a compatibility shim; always returns []."""
    writer = ClickHouseAnalyticsWriter(
        enabled=True, extra_config={"client": _FakeClickHouseClient()}
    )

    assert writer.get_buffer("backtest_trade_rows") == []
