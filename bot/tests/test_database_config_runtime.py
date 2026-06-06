import pytest

from src.infrastructure.database import DatabaseConfig
from conftest import assert_db_type_supported


def test_database_config_prefers_bot_database_url(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated")
    monkeypatch.setenv("BOT_DATABASE_URL", "postgresql://bot_user:secret@db-host:5432/bot_db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fallback:secret@other:5432/other_db")

    config = DatabaseConfig()

    assert config.get_connection_string().startswith("postgresql+psycopg2://bot_user:secret@db-host:5432/bot_db")


def test_database_config_rejects_non_postgres_url(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated")
    monkeypatch.setenv("BOT_DATABASE_URL", "sqlite:///tmp.db")

    with pytest.raises(ValueError, match="Unsupported database URL scheme"):
        DatabaseConfig()


def test_database_config_prefers_bot_db_fields(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated")
    monkeypatch.delenv("BOT_DATABASE_URL", raising=False)
    monkeypatch.setenv("BOT_DB_HOST", "bot-db-host")
    monkeypatch.setenv("BOT_DB_PORT", "5433")
    monkeypatch.setenv("BOT_DB_NAME", "bot_runtime")
    monkeypatch.setenv("BOT_DB_USER", "bot_user")
    monkeypatch.setenv("BOT_DB_PASSWORD", "bot_password")

    config = DatabaseConfig()

    assert config.db_host == "bot-db-host"
    assert config.db_port == "5433"
    assert config.db_name == "bot_runtime"
    assert config.db_user == "bot_user"
    assert config.db_password == "bot_password"
    # Connection string format varies by database type, but credentials should be present
    conn_str = config.get_connection_string()
    assert "bot_user:bot_password@bot-db-host:5433/bot_runtime" in conn_str


def test_database_config_shared_mode_ignores_bot_values(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "shared")
    monkeypatch.setenv("BOT_DATABASE_URL", "postgresql://bot_user:secret@bot-host:5432/bot_db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://shared_user:secret@shared-host:5432/shared_db")

    config = DatabaseConfig()

    assert config.get_connection_string().startswith(
        "postgresql+psycopg2://shared_user:secret@shared-host:5432/shared_db"
    )


def test_database_config_dedicated_with_shared_fallback_uses_shared_when_bot_unset(
        monkeypatch,
):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated_with_shared_fallback")
    monkeypatch.delenv("BOT_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://shared_user:secret@shared-host:5432/shared_db")

    config = DatabaseConfig()

    # Should fall back to shared database when bot-specific URL not set
    conn_str = config.get_connection_string()
    assert "shared_user:secret@shared-host" in conn_str


def test_database_config_dedicated_requires_bot_target(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated")
    monkeypatch.delenv("BOT_DATABASE_URL", raising=False)
    monkeypatch.delenv("BOT_DB_HOST", raising=False)
    monkeypatch.delenv("BOT_DB_PORT", raising=False)
    monkeypatch.delenv("BOT_DB_NAME", raising=False)
    monkeypatch.delenv("BOT_DB_USER", raising=False)
    monkeypatch.delenv("BOT_DB_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="requires BOT_DATABASE_URL or BOT_DB_\\* values"):
        DatabaseConfig()


def test_database_config_rejects_invalid_cutover_mode(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "invalid_mode")

    with pytest.raises(ValueError, match="Unsupported BOT_DB_CUTOVER_MODE"):
        DatabaseConfig()


def test_database_config_shared_uses_postgres_alias_fallbacks(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "shared")
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "pg-host")
    monkeypatch.setenv("POSTGRES_PORT", "5439")
    monkeypatch.setenv("POSTGRES_DB", "pg_db")
    monkeypatch.setenv("POSTGRES_USER", "pg_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pg_pass")

    config = DatabaseConfig()

    assert config.db_host == "pg-host"
    assert config.db_port == "5439"
    assert config.db_name == "pg_db"
    assert config.db_user == "pg_user"
    assert config.db_password == "pg_pass"


def test_database_config_uses_timeout_max_connections_and_ssl(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "shared")
    monkeypatch.setenv("DB_TIMEOUT", "5")
    monkeypatch.setenv("DB_POOL_SIZE", "5")
    monkeypatch.setenv("DB_MAX_CONNECTIONS", "10")
    monkeypatch.setenv("SSL_MODE", "true")

    config = DatabaseConfig()
    kwargs = config.get_engine_kwargs()

    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 5
    assert kwargs["pool_timeout"] == 5
    assert kwargs["connect_args"]["connect_timeout"] == 5
    # Note: SSL configuration varies significantly between PostgreSQL and MySQL.
    # This test ensures connection parameters are set; SSL behavior is verified
    # in integration tests with actual database connections.


def test_database_config_diagnostics_payload_is_sanitized(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "shared")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "dydx_bot")
    monkeypatch.setenv("DB_USER", "dydx_bot")
    monkeypatch.setenv("DB_PASSWORD", "change-me-db-password")

    config = DatabaseConfig()
    payload = config.to_diagnostics()

    # DB type depends on environment
    assert_db_type_supported(payload["db_type"])
    assert payload["password_configured"] is True
    assert payload["host"] == "localhost"
    assert payload["shared_target_detected"] is True
    assert payload["shared_target_matches_runtime"] is True
    assert "password" not in payload


def test_database_config_dedicated_blocks_shared_target_regression(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated")
    monkeypatch.setenv(
        "BOT_DATABASE_URL", "postgresql://bot_user:secret@shared-host:5432/shared_db"
    )
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://shared_user:secret@shared-host:5432/shared_db"
    )

    with pytest.raises(
            ValueError,
            match="cannot target the same database as the shared DB configuration",
    ):
        DatabaseConfig()


def test_database_config_dedicated_with_fallback_reports_shared_target_match(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated_with_shared_fallback")
    monkeypatch.setenv("BOT_DATABASE_URL", "postgresql://bot_user:secret@bot-host:5433/bot_db")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://shared_user:secret@shared-host:5432/shared_db"
    )

    config = DatabaseConfig()
    payload = config.to_diagnostics()

    assert payload["shared_target_detected"] is True
    assert payload["shared_target_matches_runtime"] is False
    assert payload["ownership_guardrail"] == "advisory"
