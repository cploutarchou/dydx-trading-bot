import pytest

from src.middleware import auth_middleware


def _set_environment(monkeypatch, value: str):
    for key in ("APP_CONFIG_ENV", "CONFIG_ENV", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENVIRONMENT", value)


@pytest.mark.parametrize("environment", ["production", "prod", "live", "mainnet"])
def test_auth_bypass_is_forbidden_in_production_like_environments(
    monkeypatch, environment
):
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    _set_environment(monkeypatch, environment)

    with pytest.raises(RuntimeError, match="API_BYPASS_AUTH=true is forbidden"):
        auth_middleware.validate_auth_bypass_configuration()


@pytest.mark.parametrize("environment", ["development", "dev", "local"])
def test_auth_bypass_is_allowed_in_explicit_development_environments(
    monkeypatch, environment
):
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    _set_environment(monkeypatch, environment)

    auth_middleware.validate_auth_bypass_configuration()
    assert auth_middleware.is_auth_bypass_enabled() is True


@pytest.mark.parametrize("environment", ["test", "testing", "ci"])
def test_auth_bypass_is_allowed_in_test_environments(monkeypatch, environment):
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    _set_environment(monkeypatch, environment)

    auth_middleware.validate_auth_bypass_configuration()
    assert auth_middleware.is_auth_bypass_enabled() is True


_ENVIRONMENT_KEYS = ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV")


def test_auth_bypass_is_forbidden_when_no_environment_is_set(monkeypatch):
    """An image that forgot to set its environment must not accept the bypass."""
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    for key in _ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)

    assert auth_middleware.is_auth_bypass_enabled() is False
    with pytest.raises(RuntimeError, match="API_BYPASS_AUTH=true is forbidden"):
        auth_middleware.validate_auth_bypass_configuration()


@pytest.mark.parametrize("production_key", ["ENVIRONMENT", "APP_ENV", "CONFIG_ENV"])
def test_development_label_cannot_override_a_production_label(
    monkeypatch, production_key
):
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    for key in _ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_CONFIG_ENV", "development")
    monkeypatch.setenv(production_key, "production")

    assert auth_middleware.is_auth_bypass_enabled() is False
    with pytest.raises(RuntimeError, match="API_BYPASS_AUTH=true is forbidden"):
        auth_middleware.validate_auth_bypass_configuration()


def test_unknown_environment_label_does_not_allow_bypass(monkeypatch):
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    for key in _ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "staging")

    assert auth_middleware.is_auth_bypass_enabled() is False


def test_bypass_stays_off_when_not_requested(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    auth_middleware.validate_auth_bypass_configuration()
    assert auth_middleware.is_auth_bypass_enabled() is False
