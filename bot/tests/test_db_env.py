"""Canonical DB env-alias resolution (src/shared/db_env.py).

Pins the documented precedence — full chains ``BOT_DB_* > DB_* > POSTGRES_*``,
shared-only chains ``DB_* > POSTGRES_*`` — and the persistence-configured
predicate so the inline chains that previously drifted across six call sites
cannot regress.
"""

import pytest

from src.shared.db_env import (
    any_db_connection_configured,
    db_env_source,
    db_env_value,
    db_field_sources,
    shared_db_env_value,
)

ALL_FIELDS = ("name", "user", "password", "host", "port")

FULL_CHAINS = {
    "name": ("BOT_DB_NAME", "DB_NAME", "POSTGRES_DB"),
    "user": ("BOT_DB_USER", "DB_USER", "POSTGRES_USER"),
    "password": ("BOT_DB_PASSWORD", "DB_PASSWORD", "POSTGRES_PASSWORD"),
    "host": ("BOT_DB_HOST", "DB_HOST", "POSTGRES_HOST"),
    "port": ("BOT_DB_PORT", "DB_PORT", "POSTGRES_PORT"),
}

SHARED_CHAINS = {
    field: tuple(name for name in chain if not name.startswith("BOT_"))
    for field, chain in FULL_CHAINS.items()
}


@pytest.fixture(autouse=True)
def _clear_db_env(monkeypatch):
    """Isolate every test from the host/CI database environment."""
    for chain in FULL_CHAINS.values():
        for name in chain:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("BOT_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_full_chain_prefers_bot_family_first(field, monkeypatch):
    bot, shared, legacy = FULL_CHAINS[field]
    monkeypatch.setenv(bot, "bot-value")
    monkeypatch.setenv(shared, "shared-value")
    monkeypatch.setenv(legacy, "legacy-value")

    assert db_env_value(field) == "bot-value"
    assert db_env_source(field) == bot


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_full_chain_falls_through_to_postgres_family(field, monkeypatch):
    _, shared, legacy = FULL_CHAINS[field]
    monkeypatch.setenv(legacy, "legacy-value")

    assert db_env_value(field) == "legacy-value"
    assert db_env_source(field) == legacy


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_shared_chain_ignores_bot_family(field, monkeypatch):
    bot, shared, legacy = FULL_CHAINS[field]
    monkeypatch.setenv(bot, "bot-value")
    monkeypatch.setenv(shared, "shared-value")

    assert shared_db_env_value(field) == "shared-value"
    assert db_env_source(field, shared_only=True) == shared


def test_shared_chain_falls_through_to_postgres_family(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "pg-host")

    assert shared_db_env_value("host", "fallback") == "pg-host"


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_unset_field_returns_default_and_null_source(field):
    assert db_env_value(field, "the-default") == "the-default"
    assert shared_db_env_value(field, "shared-default") == "shared-default"
    assert db_env_source(field) is None


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_whitespace_only_values_count_as_unset(field, monkeypatch):
    bot, _, _ = FULL_CHAINS[field]
    monkeypatch.setenv(bot, "   ")

    assert db_env_value(field, "default") == "default"
    assert db_env_source(field) is None


def test_raw_value_is_returned_unstripped(monkeypatch):
    monkeypatch.setenv("DB_HOST", "  spaced-host  ")

    assert db_env_value("host") == "  spaced-host  "


def test_unknown_field_raises_key_error():
    with pytest.raises(KeyError, match="Unknown database env field"):
        db_env_value("nonexistent")


def test_field_sources_reports_provenance_without_values(monkeypatch):
    monkeypatch.setenv("DB_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_PORT", "5433")

    sources = db_field_sources()

    assert sources["host"] == "DB_HOST"
    assert sources["port"] == "POSTGRES_PORT"
    assert sources["name"] is None
    assert sources["user"] is None
    assert sources["password"] is None


def test_any_db_connection_configured_detects_url_variables(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/d")

    assert any_db_connection_configured() is True


def test_any_db_connection_configured_detects_every_family(monkeypatch):
    # Every alias family member — including POSTGRES_* and non-host fields —
    # counts; the legacy inline predicates missed the POSTGRES_* family.
    for chain in FULL_CHAINS.values():
        for name in chain:
            monkeypatch.setenv(name, "set")
            assert any_db_connection_configured() is True
            monkeypatch.delenv(name, raising=False)


def test_any_db_connection_configured_false_when_nothing_set():
    assert any_db_connection_configured() is False


def test_any_db_connection_configured_ignores_whitespace(monkeypatch):
    monkeypatch.setenv("BOT_DATABASE_URL", "  ")
    monkeypatch.setenv("DB_HOST", " ")

    assert any_db_connection_configured() is False


def test_database_config_shared_mode_does_not_leak_bot_fields(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "shared")
    monkeypatch.setenv("BOT_DB_HOST", "bot-only-host")
    monkeypatch.setenv("DB_HOST", "shared-host")

    from src.infrastructure.database import DatabaseConfig

    config = DatabaseConfig()

    assert config.db_host == "shared-host"


def test_database_config_diagnostics_expose_field_sources(monkeypatch):
    monkeypatch.setenv("BOT_DB_CUTOVER_MODE", "shared")
    monkeypatch.setenv("POSTGRES_HOST", "pg-host")

    from src.infrastructure.database import DatabaseConfig

    payload = DatabaseConfig().to_diagnostics()

    assert payload["field_sources"]["host"] == "POSTGRES_HOST"
