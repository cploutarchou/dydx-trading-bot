from __future__ import annotations

from pathlib import Path

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

    ref = store.put_bytes("backtests/run-1/result.json", b"{\"ok\":true}")

    assert ref == "s3://backtests/backtests/run-1/result.json"
    assert store.exists("backtests/run-1/result.json") is True
    assert store.read_bytes("backtests/run-1/result.json") == b"{\"ok\":true}"
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
