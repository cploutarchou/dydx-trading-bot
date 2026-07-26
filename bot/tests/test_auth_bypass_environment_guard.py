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
