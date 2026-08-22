"""Tests for startup configuration validation (src/shared/config_validation.py).

Unit-tests the validator directly with monkeypatched env — no TestClient / app
import, so the import-time/startup behavior of the service is never exercised here.
"""

from __future__ import annotations

import logging

import pytest

from src.exceptions import ConfigurationError
from src.shared.config_validation import (
    _collect_config_problems,
    validate_startup_config,
)

# Every env var the validator reads. Cleared per-test for isolation.
_ENV_VARS = [
    "APP_CONFIG_ENV",
    "CONFIG_ENV",
    "ENVIRONMENT",
    "APP_ENV",
    "API_BYPASS_AUTH",
    "BOT_API_TOKEN",
    "BOT_API_TOKENS",
    "BACKTEST_WORKER_BACKEND",
    "CELERY_BROKER_URL",
    "CELERY_BROKER",
    "REDIS_URL",
    "VALKEY_URL",
    "IS_TESTNET",
    "BOT_PLACE_TRADES",
    "DYDX_CHAIN_ADDRESS",
    "dydx_chain_address",
    "BOT_DYDX_ADDRESS",
    "DYDX_CHAIN_SECRET",
    "dydx_chain_secret",
    "BOT_DYDX_SECRET",
    "MNEMONIC",
    "BOT_API_PORT",
    "BOT_DB_PORT",
    "DB_PORT",
    "POSTGRES_PORT",
    "BOT_DB_HOST",
    "DB_HOST",
    "POSTGRES_HOST",
    "BOT_DB_PASSWORD",
    "DB_PASSWORD",
    "POSTGRES_PASSWORD",
    "STARTUP_CONFIG_VALIDATION",
]


@pytest.fixture(autouse=True)
def clean_config_env(monkeypatch):
    """Clear every var the validator reads so tests start from a known state."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


def _run(**env) -> list[str]:
    """Helper: set env vars, return collected problems, then clean up."""
    import os

    for key, value in env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        return _collect_config_problems()
    finally:
        for key in env:
            os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# _collect_config_problems
# ---------------------------------------------------------------------------


def test_no_problems_in_dev_with_empty_config():
    # Development env (no production marker) with everything default → no problems.
    assert _run() == []


def test_production_missing_token_when_auth_not_bypassed():
    problems = _run(APP_CONFIG_ENV="production")
    assert any("BOT_API_TOKEN" in p for p in problems), problems


def test_production_skips_token_check_when_bypass_enabled():
    # API_BYPASS_AUTH=true → the token requirement is skipped (the separate
    # startup guard in server.py is what rejects bypass-in-prod).
    problems = _run(APP_CONFIG_ENV="production", API_BYPASS_AUTH="true")
    assert not any("BOT_API_TOKEN" in p for p in problems), problems


def test_production_with_token_set_no_auth_problem():
    problems = _run(APP_CONFIG_ENV="production", BOT_API_TOKEN="t-ok")
    assert not any("BOT_API_TOKEN" in p for p in problems), problems


def test_celery_backend_requires_broker():
    problems = _run(BACKTEST_WORKER_BACKEND="celery")
    assert any("broker" in p for p in problems), problems


def test_celery_backend_satisfied_by_redis_url():
    problems = _run(
        BACKTEST_WORKER_BACKEND="celery", REDIS_URL="redis://localhost:6379/1"
    )
    assert not any("broker" in p for p in problems), problems


def test_asyncio_backend_does_not_require_broker():
    problems = _run(BACKTEST_WORKER_BACKEND="asyncio")
    assert not any("broker" in p for p in problems), problems


def test_live_mainnet_requires_dydx_credentials():
    problems = _run(IS_TESTNET="false", BOT_PLACE_TRADES="true")
    assert any("signing material" in p for p in problems), problems


def test_live_testnet_does_not_require_mainnet_credentials():
    # IS_TESTNET=true (default) → mainnet creds not required even if placing trades.
    problems = _run(IS_TESTNET="true", BOT_PLACE_TRADES="true")
    assert not any("signing material" in p for p in problems), problems


def test_live_mainnet_satisfied_by_mnemonic():
    problems = _run(IS_TESTNET="false", BOT_PLACE_TRADES="true", MNEMONIC="x" * 32)
    assert not any("signing material" in p for p in problems), problems


def test_bad_port_format_flagged():
    problems = _run(BOT_API_PORT="not-a-port")
    assert any("BOT_API_PORT" in p and "not a valid integer" in p for p in problems)


def test_port_out_of_range_flagged():
    problems = _run(BOT_DB_PORT="99999")
    assert any("out of range" in p for p in problems)


def test_valid_port_accepted():
    problems = _run(BOT_API_PORT="8889", BOT_DB_PORT="5432")
    assert not any("port" in p.lower() for p in problems), problems


def test_production_all_default_db_flagged():
    problems = _run(APP_CONFIG_ENV="production", BOT_API_TOKEN="t-ok")
    assert any("all-default" in p for p in problems), problems


def test_production_db_with_host_not_flagged():
    problems = _run(
        APP_CONFIG_ENV="production", BOT_API_TOKEN="t-ok", BOT_DB_HOST="db.internal"
    )
    assert not any("all-default" in p for p in problems), problems


def test_multiple_problems_collected_not_fail_fast():
    # Production + no token + celery-without-broker + bad port → 3+ distinct problems.
    problems = _run(
        APP_CONFIG_ENV="production",
        BACKTEST_WORKER_BACKEND="celery",
        BOT_API_PORT="bogus",
    )
    assert len(problems) >= 3
    joined = "\n".join(problems)
    assert "BOT_API_TOKEN" in joined
    assert "broker" in joined
    assert "BOT_API_PORT" in joined


# ---------------------------------------------------------------------------
# validate_startup_config — raise / warn / skip behavior
# ---------------------------------------------------------------------------


def test_strict_raises_in_production():
    os_env = {"APP_CONFIG_ENV": "production"}  # no token
    for k, v in os_env.items():
        import os

        os.environ[k] = v
    try:
        with pytest.raises(ConfigurationError) as exc:
            validate_startup_config()
        assert "BOT_API_TOKEN" in str(exc.value)
    finally:
        import os

        for k in os_env:
            os.environ.pop(k, None)


def test_development_warns_does_not_raise(caplog):
    with caplog.at_level(logging.WARNING):
        validate_startup_config()  # dev env, empty config → no problems actually
    # Dev with empty config has no problems → no warning. Force a problem:
    import os

    os.environ["BACKTEST_WORKER_BACKEND"] = "celery"  # missing broker → 1 problem
    try:
        with caplog.at_level(logging.WARNING):
            validate_startup_config()  # dev → warn, not raise
        assert any("broker" in r.getMessage() for r in caplog.records)
    finally:
        os.environ.pop("BACKTEST_WORKER_BACKEND", None)


def test_explicit_strict_raises_even_in_development():
    import os

    os.environ["STARTUP_CONFIG_VALIDATION"] = "strict"
    os.environ["BACKTEST_WORKER_BACKEND"] = "celery"  # forces a problem
    try:
        with pytest.raises(ConfigurationError):
            validate_startup_config()
    finally:
        os.environ.pop("STARTUP_CONFIG_VALIDATION", None)
        os.environ.pop("BACKTEST_WORKER_BACKEND", None)


def test_skip_bypasses_even_with_problems():
    import os

    os.environ["STARTUP_CONFIG_VALIDATION"] = "skip"
    os.environ["APP_CONFIG_ENV"] = "production"  # would normally raise
    try:
        validate_startup_config()  # must not raise
    finally:
        os.environ.pop("STARTUP_CONFIG_VALIDATION", None)
        os.environ.pop("APP_CONFIG_ENV", None)
