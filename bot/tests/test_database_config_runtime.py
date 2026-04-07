import pytest

from src.infrastructure.database import DatabaseConfig


def test_database_config_prefers_bot_database_url(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated")
    monkeypatch.setenv("BOT_DATABASE_URL", "postgresql://bot_user:secret@db-host:5432/bot_db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fallback:secret@other:5432/other_db")

    config = DatabaseConfig()

    assert config.get_connection_string().startswith("postgresql+psycopg2://bot_user:secret@db-host:5432/bot_db")


def test_database_config_rejects_non_postgres_url(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "dedicated")
    monkeypatch.setenv("BOT_DATABASE_URL", "sqlite:///tmp.db")

    with pytest.raises(ValueError, match="Only PostgreSQL URLs are supported"):
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
    assert config.get_connection_string() == (
        "postgresql+psycopg2://bot_user:bot_password@bot-db-host:5433/bot_runtime"
    )


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

    assert config.get_connection_string().startswith(
        "postgresql+psycopg2://shared_user:secret@shared-host:5432/shared_db"
    )


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


