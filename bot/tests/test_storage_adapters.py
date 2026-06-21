from __future__ import annotations

from pathlib import Path

from src.infrastructure.storage import (
    ClickHouseAnalyticsWriter,
    LocalArtifactStore,
    MinIOArtifactStore,
    NoopAnalyticsWriter,
)


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


def test_clickhouse_writer_buffers_rows_when_enabled():
    writer = ClickHouseAnalyticsWriter(enabled=True)

    count = writer.write_rows(
        "backtest_trades", [{"trade_id": "t1"}, {"trade_id": "t2"}]
    )

    assert count == 2
    assert writer.get_buffer("backtest_trades") == [
        {"trade_id": "t1"},
        {"trade_id": "t2"},
    ]
