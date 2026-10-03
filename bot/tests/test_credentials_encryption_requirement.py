"""Plaintext credential storage is a dev/test convenience only."""

import pytest

from src.shared import credentials_cipher as cc
from src.shared import environment

_ENV_KEYS = environment.ENVIRONMENT_VARIABLES


def _set_env(monkeypatch, **values):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv(cc.ENV_REQUIRED, raising=False)
    monkeypatch.delenv(cc.ENV_KEY, raising=False)
    monkeypatch.delenv(cc.ENV_KEY_FILE, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("label", ["development", "dev", "local", "test", "ci"])
def test_plaintext_is_allowed_only_in_explicit_dev_or_test(monkeypatch, label):
    _set_env(monkeypatch, ENVIRONMENT=label)

    assert cc.is_encryption_required() is False


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"ENVIRONMENT": "production"},
        {"APP_ENV": "prod"},
        {"ENVIRONMENT": "staging"},
        {"APP_CONFIG_ENV": "development", "APP_ENV": "prod"},
    ],
)
def test_encryption_is_required_everywhere_else(monkeypatch, env):
    _set_env(monkeypatch, **env)

    assert cc.is_encryption_required() is True


def test_explicit_requirement_wins_in_development(monkeypatch):
    _set_env(monkeypatch, ENVIRONMENT="development")
    monkeypatch.setenv(cc.ENV_REQUIRED, "true")

    assert cc.is_encryption_required() is True


def test_write_without_a_key_is_refused_outside_dev(monkeypatch):
    _set_env(monkeypatch, ENVIRONMENT="production")
    cc._key_cache = None

    with pytest.raises(cc.CredentialEncryptionError):
        cc._require_key_for_write()


def test_write_without_a_key_passes_through_in_dev(monkeypatch):
    _set_env(monkeypatch, ENVIRONMENT="development")
    cc._key_cache = None

    assert cc._require_key_for_write() == b""
