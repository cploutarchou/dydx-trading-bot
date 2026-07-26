"""Unit tests for ``src.shared.credentials_cipher``.

These tests cover the AES-GCM seal/open primitives, the block-level config
helpers, legacy plaintext passthrough, tamper/wrong-key detection, and the
write-guard gating (plaintext fallback vs. required mode).
"""

from __future__ import annotations

import base64
import copy
import json

import pytest

from src.shared import credentials_cipher as cc

KEY_A = base64.b64encode(bytes(range(32))).decode()
KEY_B = base64.b64encode(bytes(range(32, 64))).decode()


@pytest.fixture(autouse=True)
def _reset_cipher_state(monkeypatch):
    """Reset module-level key cache + warning state between tests."""
    monkeypatch.delenv(cc.ENV_KEY, raising=False)
    monkeypatch.delenv(cc.ENV_KEY_FILE, raising=False)
    monkeypatch.delenv(cc.ENV_REQUIRED, raising=False)
    cc._key_cache = None
    cc._no_key_warned_for.clear()
    yield
    cc._key_cache = None
    cc._no_key_warned_for.clear()


def _set_key(monkeypatch, key_b64: str = KEY_A):
    monkeypatch.setenv(cc.ENV_KEY, key_b64)
    cc._key_cache = None


def _sample_payload():
    return {
        "instance_name": "Bot",
        "credentials": {
            "chain_id": "dydx-testnet-4",
            "address": "dydx1abc",
            "mnemonic": "alpha beta gamma delta epsilon zeta eta theta",
        },
        "telegram": {"token": "tel-secret-token", "chat_id": "123456"},
        "trading_params": {"strategy": "cointegration", "is_testnet": True},
        "config_meta": {"schema_version": 2, "payload_hash": "deadbeef"},
    }


# --- availability / gating ---------------------------------------------------


def test_is_encryption_available_false_without_key():
    assert cc.is_encryption_available() is False


def test_is_encryption_available_true_with_key(monkeypatch):
    _set_key(monkeypatch)
    assert cc.is_encryption_available() is True


def test_is_encryption_available_false_for_malformed_key(monkeypatch, caplog):
    monkeypatch.setenv(cc.ENV_KEY, base64.b64encode(b"too-short").decode())
    cc._key_cache = None
    assert cc.is_encryption_available() is False


def test_is_encryption_required_flag(monkeypatch):
    assert cc.is_encryption_required() is False
    monkeypatch.setenv(cc.ENV_REQUIRED, "true")
    assert cc.is_encryption_required() is True


def test_wrong_key_length_raises(monkeypatch):
    monkeypatch.setenv(cc.ENV_KEY, base64.b64encode(b"short").decode())
    cc._key_cache = None
    with pytest.raises(cc.CredentialCipherError):
        cc._resolve_key()


# --- seal/open block helpers -------------------------------------------------


def test_seal_then_open_round_trips(monkeypatch):
    _set_key(monkeypatch)
    payload = _sample_payload()
    sealed = cc.seal_config_secrets(payload)
    assert sealed is not payload  # returns a copy

    opened = cc.open_config_secrets(sealed)
    assert opened == payload


def test_seal_replaces_secret_blocks_with_envelopes(monkeypatch):
    _set_key(monkeypatch)
    sealed = cc.seal_config_secrets(_sample_payload())
    assert "credentials" not in sealed
    assert "telegram" not in sealed
    assert "credentials_sealed" in sealed
    assert "telegram_sealed" in sealed


def test_seal_omits_plaintext_mnemonic(monkeypatch):
    _set_key(monkeypatch)
    sealed = cc.seal_config_secrets(_sample_payload())
    blob = json.dumps(sealed)
    assert "alpha beta gamma" not in blob
    assert "tel-secret-token" not in blob


def test_seal_preserves_non_secret_fields(monkeypatch):
    _set_key(monkeypatch)
    sealed = cc.seal_config_secrets(_sample_payload())
    assert sealed["instance_name"] == "Bot"
    assert sealed["trading_params"]["strategy"] == "cointegration"
    assert sealed["config_meta"]["schema_version"] == 2


def test_envelope_carries_key_id_and_version(monkeypatch):
    _set_key(monkeypatch)
    sealed = cc.seal_config_secrets(_sample_payload())
    env = sealed["credentials_sealed"]
    assert env["cipher"] == cc.CIPHER_NAME
    assert env["version"] == cc.CIPHER_VERSION
    assert env["key_id"] == cc._key_id(base64.b64decode(KEY_A))
    assert "nonce" in env and "ciphertext" in env


def test_empty_telegram_block_is_not_sealed(monkeypatch):
    _set_key(monkeypatch)
    payload = _sample_payload()
    payload["telegram"] = {}
    sealed = cc.seal_config_secrets(payload)
    assert "telegram_sealed" not in sealed
    assert sealed["telegram"] == {}
    # credentials still sealed
    assert "credentials_sealed" in sealed


def test_each_seal_uses_fresh_nonce(monkeypatch):
    _set_key(monkeypatch)
    sealed_a = cc.seal_config_secrets(_sample_payload())
    sealed_b = cc.seal_config_secrets(_sample_payload())
    assert (
            sealed_a["credentials_sealed"]["nonce"]
            != sealed_b["credentials_sealed"]["nonce"]
    )


# --- legacy passthrough ------------------------------------------------------


def test_open_passes_through_legacy_plaintext(monkeypatch):
    _set_key(monkeypatch)  # key available but payload has no envelopes
    legacy = _sample_payload()
    assert cc.open_config_secrets(legacy) == legacy


def test_open_legacy_plaintext_without_key():
    # No key and no envelopes -> still returns plaintext unchanged.
    legacy = _sample_payload()
    assert cc.open_config_secrets(legacy) == legacy


def test_open_non_dict_returns_empty():
    assert cc.open_config_secrets(None) == {}  # type: ignore[arg-type]


def test_has_sealed_secrets_helper(monkeypatch):
    _set_key(monkeypatch)
    sealed = cc.seal_config_secrets(_sample_payload())
    assert cc.has_sealed_secrets(sealed) is True
    assert cc.has_sealed_secrets(_sample_payload()) is False


# --- failure modes -----------------------------------------------------------


def test_tamper_detection(monkeypatch):
    _set_key(monkeypatch)
    sealed = cc.seal_config_secrets(_sample_payload())
    ct = base64.b64decode(sealed["credentials_sealed"]["ciphertext"])
    tampered = bytearray(ct)
    tampered[0] ^= 0xFF
    sealed["credentials_sealed"]["ciphertext"] = base64.b64encode(bytes(tampered)).decode()
    with pytest.raises(cc.CredentialDecryptionError):
        cc.open_config_secrets(sealed)


def test_wrong_key_detected_via_key_id(monkeypatch):
    _set_key(monkeypatch, KEY_A)
    sealed = cc.seal_config_secrets(_sample_payload())
    # Rotate to a different key.
    _set_key(monkeypatch, KEY_B)
    with pytest.raises(cc.CredentialDecryptionError, match="key id"):
        cc.open_config_secrets(sealed)


def test_open_without_key_raises(monkeypatch):
    _set_key(monkeypatch)
    sealed = cc.seal_config_secrets(_sample_payload())
    monkeypatch.delenv(cc.ENV_KEY, raising=False)
    cc._key_cache = None
    with pytest.raises(cc.CredentialDecryptionError, match="no decryption key"):
        cc.open_config_secrets(sealed)


def test_malformed_envelope_raises(monkeypatch):
    _set_key(monkeypatch)
    with pytest.raises(cc.CredentialDecryptionError):
        cc.open_secret({"cipher": cc.CIPHER_NAME, "nonce": "x", "ciphertext": "y"})
    with pytest.raises(cc.CredentialDecryptionError):
        cc.open_secret({"cipher": "not-aesgcm"})


def test_open_drops_stale_plaintext_leftover(monkeypatch):
    _set_key(monkeypatch)
    payload = _sample_payload()
    sealed = cc.seal_config_secrets(payload)
    # Simulate a partially-written row carrying both stale plaintext and envelope.
    sealed["credentials"] = {"address": "stale", "mnemonic": "stale words"}
    opened = cc.open_config_secrets(sealed)
    assert opened["credentials"] == payload["credentials"]


# --- write guard (passthrough vs required) -----------------------------------


def test_seal_passthrough_when_no_key_not_required():
    payload = _sample_payload()
    assert cc.seal_config_secrets(payload) == payload


def test_seal_raises_when_required_but_no_key(monkeypatch):
    monkeypatch.setenv(cc.ENV_REQUIRED, "true")
    with pytest.raises(cc.CredentialEncryptionError):
        cc.seal_config_secrets(_sample_payload())


# --- low-level primitive -----------------------------------------------------


def test_seal_secret_open_secret_round_trip(monkeypatch):
    _set_key(monkeypatch)
    secret = {"mnemonic": "alpha beta gamma", "address": "dydx1abc"}
    opened = cc.open_secret(cc.seal_secret(secret))
    assert opened == secret


def test_seal_secret_without_key_raises():
    with pytest.raises(cc.CredentialEncryptionError):
        cc.seal_secret({"mnemonic": "alpha beta gamma"})


# --- key-file support --------------------------------------------------------


def test_key_file_resolution(tmp_path, monkeypatch):
    raw_key = bytes(range(32))
    key_file = tmp_path / "cred.key"
    key_file.write_bytes(base64.b64encode(raw_key))
    monkeypatch.setenv(cc.ENV_KEY_FILE, str(key_file))
    cc._key_cache = None
    assert cc.is_encryption_available() is True
    sealed = cc.seal_config_secrets(_sample_payload())
    assert cc.open_config_secrets(sealed) == _sample_payload()


def test_key_file_missing_raises(monkeypatch):
    monkeypatch.setenv(cc.ENV_KEY_FILE, "/nonexistent/cred.key")
    cc._key_cache = None
    with pytest.raises(cc.CredentialCipherError):
        cc._resolve_key()


def test_cache_invalidates_on_env_change(monkeypatch):
    _set_key(monkeypatch, KEY_A)
    assert cc._resolve_key() == base64.b64decode(KEY_A)
    _set_key(monkeypatch, KEY_B)
    assert cc._resolve_key() == base64.b64decode(KEY_B)
