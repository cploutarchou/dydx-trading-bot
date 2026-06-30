from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.storage import (
    ClickHouseAnalyticsWriter,
    LocalArtifactStore,
    MinIOArtifactStore,
    NoopAnalyticsWriter,
)
from src.shared.env_loader import find_repo_root


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
    monkeypatch.delenv("BACKTEST_CLICKHOUSE_HOST", raising=False)
    monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
    monkeypatch.delenv("BACKTEST_CLICKHOUSE_PASSWORD", raising=False)
    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
    monkeypatch.delenv("BACKTEST_CLICKHOUSE_USER", raising=False)
    monkeypatch.delenv("CLICKHOUSE_USER", raising=False)
    monkeypatch.delenv("BACKTEST_CLICKHOUSE_DATABASE", raising=False)
    monkeypatch.delenv("CLICKHOUSE_DATABASE", raising=False)
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


def test_backtest_repository_keeps_minio_disabled_without_master_artifact_flag(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("BACKTEST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("BACKTEST_ARTIFACT_STORAGE_ENABLED", "false")
    monkeypatch.setenv("BACKTEST_MINIO_ARTIFACTS_ENABLED", "true")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9010")

    store = BacktestRepository._build_artifact_store()

    assert isinstance(store, LocalArtifactStore)


def test_backtest_repository_enables_minio_when_both_new_flags_are_true(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("BACKTEST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("BACKTEST_ARTIFACT_STORAGE_ENABLED", "true")
    monkeypatch.setenv("BACKTEST_MINIO_ARTIFACTS_ENABLED", "true")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9010")
    monkeypatch.setenv("MINIO_BUCKET", "backtests")

    store = BacktestRepository._build_artifact_store()

    assert isinstance(store, MinIOArtifactStore)
    assert store.enabled is True


def test_backtest_repository_prefers_new_clickhouse_flag_over_legacy_alias(monkeypatch):
    monkeypatch.setenv("BACKTEST_CLICKHOUSE_WRITES_ENABLED", "false")
    monkeypatch.setenv("BACKTEST_CLICKHOUSE_ENABLED", "true")

    writer = BacktestRepository._build_analytics_writer()

    assert isinstance(writer, NoopAnalyticsWriter)


def test_backtest_repository_accepts_canonical_clickhouse_enabled_alias(monkeypatch):
    monkeypatch.delenv("BACKTEST_CLICKHOUSE_WRITES_ENABLED", raising=False)
    monkeypatch.delenv("BACKTEST_CLICKHOUSE_ENABLED", raising=False)
    monkeypatch.setenv("CLICKHOUSE_ENABLED", "true")
    monkeypatch.setenv("CLICKHOUSE_URL", "http://analytics:8123/dydx_analytics")

    writer = BacktestRepository._build_analytics_writer()

    assert isinstance(writer, ClickHouseAnalyticsWriter)
    assert writer.enabled is True
    assert writer.host == "analytics"
    assert writer.port == 8123
    assert writer.database == "dydx_analytics"


def test_backtest_repository_accepts_canonical_minio_enabled_alias(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("BACKTEST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.delenv("BACKTEST_ARTIFACT_STORAGE_ENABLED", raising=False)
    monkeypatch.delenv("BACKTEST_MINIO_ARTIFACTS_ENABLED", raising=False)
    monkeypatch.delenv("BACKTEST_MINIO_ENABLED", raising=False)
    monkeypatch.setenv("MINIO_ENABLED", "true")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9010")
    monkeypatch.setenv("MINIO_BUCKET", "backtests")

    store = BacktestRepository._build_artifact_store()

    assert isinstance(store, MinIOArtifactStore)
    assert store.enabled is True


def test_backtest_repository_resolves_relative_artifact_root_from_repo_root(
    monkeypatch,
):
    monkeypatch.setenv("BACKTEST_ARTIFACT_STORAGE_ENABLED", "false")
    monkeypatch.setenv("BACKTEST_ARTIFACTS_DIR", "tmp/backtest-artifacts-test")

    store = BacktestRepository._build_artifact_store()

    assert isinstance(store, LocalArtifactStore)
    expected_root = (
        find_repo_root(__file__) / "tmp" / "backtest-artifacts-test"
    ).resolve()
    assert store.root_dir == expected_root


def test_backtest_repository_resolves_clickhouse_batch_settings(monkeypatch):
    monkeypatch.setenv("BACKTEST_CLICKHOUSE_BATCH_SIZE", "250")
    monkeypatch.setenv("BACKTEST_CLICKHOUSE_FLUSH_INTERVAL_SECONDS", "2.5")

    batch_size, flush_interval_seconds = (
        BacktestRepository._resolve_clickhouse_batch_settings()
    )

    assert batch_size == 250
    assert flush_interval_seconds == 2.5


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


def test_clickhouse_writer_buffers_rows_until_batch_threshold():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={
            "client": client,
            "batch_size": 3,
            "flush_interval_seconds": 60,
        },
    )

    first_count = writer.write_rows(
        "backtest_trade_rows",
        [{"run_id": "r1", "trade_id": "t1"}, {"run_id": "r1", "trade_id": "t2"}],
    )
    second_count = writer.write_rows(
        "backtest_trade_rows",
        [{"run_id": "r1", "trade_id": "t3"}],
    )

    assert first_count == 0
    assert second_count == 3
    assert writer.get_buffer("backtest_trade_rows") == []
    assert len(client.inserts) == 3


def test_clickhouse_writer_flushes_pending_rows_when_forced():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={
            "client": client,
            "batch_size": 10,
            "flush_interval_seconds": 60,
        },
    )

    count = writer.write_rows(
        "backtest_trade_rows",
        [{"run_id": "r1", "trade_id": "t1"}, {"run_id": "r1", "trade_id": "t2"}],
    )
    flushed = writer.flush(force=True)

    assert count == 0
    assert flushed == {"backtest_trade_rows": 2}
    assert writer.get_buffer("backtest_trade_rows") == []
    assert len(client.inserts) == 2


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


def test_clickhouse_writer_provisions_equity_curve_and_strategy_metrics_tables():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={"client": client},
    )

    writer.write_rows(
        "backtest_equity_curve",
        [{"run_id": "r1", "point_time": "2026-01-01T00:00:00+00:00"}],
    )
    writer.write_rows(
        "strategy_metrics",
        [{"run_id": "r1", "metric_name": "sharpe_ratio", "metric_value": 1.2}],
    )

    assert any("backtest_equity_curve" in cmd for cmd in client.commands)
    assert any("strategy_metrics" in cmd for cmd in client.commands)


def test_clickhouse_writer_provisions_bot_events_table():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={"client": client},
    )

    writer.write_rows(
        "bot_events",
        [
            {
                "event_date": datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
                "event_time": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                "bot_run_id": "run-1",
                "bot_id": "77",
                "event_type": "bot_started",
                "status": "running",
                "strategy_id": 42,
                "worker_id": "strategy-1-101",
                "correlation_id": "corr-1",
                "payload_attrs": "{\"message\":\"started\"}",
            }
        ],
    )

    assert any("bot_events" in cmd for cmd in client.commands)


def test_clickhouse_writer_provisions_order_events_table():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={"client": client},
    )

    writer.write_rows(
        "order_events",
        [
            {
                "event_date": datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
                "event_time": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                "order_id": "entry-1",
                "trade_id": "live-abc123",
                "bot_id": "77",
                "instance_id": "strategy-1-101",
                "bot_run_id": "run-1",
                "market": "BTC-USD",
                "side": "BUY",
                "status": "filled",
                "event_type": "trade_entry_opened",
                "price": 100000.0,
                "size": 0.1,
                "exchange_time": datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                "correlation_id": "corr-1",
            }
        ],
    )

    assert any("order_events" in cmd for cmd in client.commands)
    assert any("instance_id" in cmd for cmd in client.commands)


def test_clickhouse_writer_provisions_trade_events_table():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={"client": client},
    )

    writer.write_rows(
        "trade_events",
        [
            {
                "event_date": datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
                "event_time": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                "trade_id": "live-abc123",
                "bot_id": "77",
                "instance_id": "strategy-1-101",
                "pair1": "BTC-USD",
                "pair2": "ETH-USD",
                "side1": "BUY",
                "side2": "SELL",
                "status": "open",
                "event_kind": "opened",
                "entry_price1": 100000.0,
                "entry_price2": 3000.0,
                "exit_price1": None,
                "exit_price2": None,
                "entry_size1": 0.1,
                "entry_size2": 2.0,
                "exit_size1": None,
                "exit_size2": None,
                "realized_pnl": 0.0,
                "realized_pnl_pct": 0.0,
                "closed_at": None,
            }
        ],
    )

    assert any("trade_events" in cmd for cmd in client.commands)
    assert any("instance_id" in cmd for cmd in client.commands)


def test_clickhouse_writer_provisions_position_snapshots_table():
    client = _FakeClickHouseClient()
    writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={"client": client},
    )

    writer.write_rows(
        "position_snapshots",
        [
            {
                "snapshot_date": datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
                "snapshot_time": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                "position_id": "live-pos-1",
                "bot_id": "77",
                "instance_id": "strategy-1-101",
                "pair1": "BTC-USD",
                "pair2": "ETH-USD",
                "side1": "BUY",
                "side2": "SELL",
                "status": "open",
                "event_kind": "mark_to_market",
                "entry_price1": 100000.0,
                "entry_price2": 3000.0,
                "current_price1": 101000.0,
                "current_price2": 2900.0,
                "entry_size1": 0.1,
                "entry_size2": 2.0,
                "current_size1": 0.1,
                "current_size2": 2.0,
                "unrealized_pnl": 300.0,
                "unrealized_pnl_pct": 1.5,
                "realized_pnl": 0.0,
                "realized_pnl_pct": 0.0,
                "z_score_entry": 2.1,
                "z_score_current": 0.8,
                "hedge_ratio": 0.6,
                "correlation": 0.9,
                "half_life": 12.0,
                "funding_rate": 0.001,
                "closed_at": None,
            }
        ],
    )

    assert any("position_snapshots" in cmd for cmd in client.commands)
    assert any("instance_id" in cmd for cmd in client.commands)


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
    """get_buffer remains empty when no rows are buffered."""
    writer = ClickHouseAnalyticsWriter(
        enabled=True, extra_config={"client": _FakeClickHouseClient()}
    )

    assert writer.get_buffer("backtest_trade_rows") == []
