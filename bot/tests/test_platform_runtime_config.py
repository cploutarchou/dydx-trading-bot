from __future__ import annotations

from config.config import ConfigurationManager


def test_configuration_manager_builds_valkey_settings_from_canonical_aliases(
    monkeypatch,
):
    manager = ConfigurationManager()
    monkeypatch.setenv("VALKEY_ENABLED", "true")
    monkeypatch.setenv("VALKEY_HOST", "valkey.internal")
    monkeypatch.setenv("VALKEY_PORT", "6382")
    monkeypatch.setenv("VALKEY_DB", "5")
    monkeypatch.setenv("VALKEY_PASSWORD", "cache-secret")
    monkeypatch.setenv("VALKEY_SSL", "true")
    monkeypatch.setenv("VALKEY_TIMEOUT", "7")
    monkeypatch.setenv("VALKEY_CACHE_TTL_SECONDS", "90")
    monkeypatch.setenv("VALKEY_MAX_CONNECTIONS", "23")

    settings = manager._build_valkey_settings_from_env()

    assert settings.enabled is True
    assert settings.host == "valkey.internal"
    assert settings.port == 6382
    assert settings.db == 5
    assert settings.password == "cache-secret"
    assert settings.ssl is True
    assert settings.timeout == 7
    assert settings.cache_ttl_seconds == 90
    assert settings.max_connections == 23


def test_configuration_manager_builds_nats_clickhouse_and_minio_settings(
    monkeypatch,
):
    manager = ConfigurationManager()
    monkeypatch.setenv("NATS_ENABLED", "true")
    monkeypatch.setenv("NATS_URL", "nats://nats.internal:4222")
    monkeypatch.setenv("NATS_MONITORING_URL", "http://nats.internal:8222")
    monkeypatch.setenv("NATS_STREAM_PREFIX", "platform")
    monkeypatch.setenv("BOT_COMMAND_BUS_ENABLED", "true")
    monkeypatch.setenv(
        "CLICKHOUSE_URL",
        "https://analytics:8124/dydx_analytics",
    )
    monkeypatch.setenv("CLICKHOUSE_ENABLED", "true")
    monkeypatch.setenv("CLICKHOUSE_USER", "analytics-user")
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "analytics-pass")
    monkeypatch.setenv("BACKTEST_CLICKHOUSE_BATCH_SIZE", "250")
    monkeypatch.setenv("BACKTEST_CLICKHOUSE_FLUSH_INTERVAL_SECONDS", "2.5")
    monkeypatch.setenv("BACKTEST_ARTIFACT_STORAGE_ENABLED", "true")
    monkeypatch.setenv("MINIO_ENDPOINT", "https://minio.internal:9000")
    monkeypatch.setenv("MINIO_BUCKET", "backtest-artifacts")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio-access")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio-secret")

    nats = manager._build_nats_settings_from_env()
    clickhouse = manager._build_clickhouse_settings_from_env()
    minio = manager._build_minio_settings_from_env()

    assert nats.enabled is True
    assert nats.url == "nats://nats.internal:4222"
    assert nats.monitoring_url == "http://nats.internal:8222"
    assert nats.stream_prefix == "platform"
    assert nats.command_bus_enabled is True

    assert clickhouse.enabled is True
    assert clickhouse.host == "analytics"
    assert clickhouse.port == 8124
    assert clickhouse.database == "dydx_analytics"
    assert clickhouse.user == "analytics-user"
    assert clickhouse.password == "analytics-pass"
    assert clickhouse.secure is True
    assert clickhouse.batch_size == 250
    assert clickhouse.flush_interval_seconds == 2.5

    assert minio.enabled is True
    assert minio.endpoint == "https://minio.internal:9000"
    assert minio.bucket == "backtest-artifacts"
    assert minio.access_key == "minio-access"
    assert minio.secret_key == "minio-secret"
    assert minio.secure is True
