"""At-rest encryption for credential-bearing fields in ``bot_instances.config``.

The ``bot_instances.config`` JSONB column historically stored wallet mnemonics
and Telegram tokens in plain text. This module seals those secret-bearing
sub-objects (``credentials`` and ``telegram``) into AES-256-GCM envelopes before
they reach the database, and opens them again on every read path.

Design notes
------------
* Reuses ``cryptography.hazmat.primitives.ciphers.aead.AESGCM`` (already a
  transitive dependency via ``python-jose[cryptography]`` and used by
  ``src/shared/env_loader.py`` for config-file encryption).
* Uses a **dedicated** key (``BOT_CREDENTIALS_ENCRYPTION_KEY`` /
  ``BOT_CREDENTIALS_ENCRYPTION_KEY_FILE``) — separate from the config-file key
  (``.configkey.bin``) because the rotation cadence and threat model differ.
* Rollout is non-breaking: with no key configured the module falls back to
  plaintext + a warning. Set ``BOT_CREDENTIALS_ENCRYPTION_REQUIRED=true`` to make
  writes fail loudly until a key is provisioned (fail-safe per AGENTS rule 4).
* Envelopes carry a ``key_id`` (first 8 hex chars of sha256(key)) so a wrong-key
  read fails with a clear message instead of a generic GCM error, and so future
  key-rotation support can select the correct key.
* Legacy plaintext rows pass through ``open_config_secrets`` unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

# --- Envelope / key constants ------------------------------------------------
CIPHER_NAME = "AESGCM"
CIPHER_VERSION = 1
KEY_BYTES = 32  # AES-256
NONCE_BYTES = 12  # 96-bit GCM nonce (recommended)

ENV_KEY = "BOT_CREDENTIALS_ENCRYPTION_KEY"  # base64-encoded KEY_BYTES
ENV_KEY_FILE = "BOT_CREDENTIALS_ENCRYPTION_KEY_FILE"  # raw KEY_BYTES file
ENV_REQUIRED = "BOT_CREDENTIALS_ENCRYPTION_REQUIRED"

# Sub-objects that contain secrets and are sealed as opaque envelopes.
SEALED_BLOCKS = ("credentials", "telegram")


# --- Exceptions --------------------------------------------------------------


from src.exceptions import (  # noqa: E402
    CredentialCipherError,
    CredentialDecryptionError,
    CredentialEncryptionError,
)

# Canonical definitions live in :mod:`src.exceptions` (under ``CredentialError``);
# re-imported here so existing ``from src.shared.credentials_cipher import ...``
# paths keep resolving to the same class objects.
from src.shared.environment import (  # noqa: E402
    is_explicit_dev_or_test_environment,
)

# --- Key resolution ----------------------------------------------------------

# Cache the parsed key, keyed on the raw env inputs so a change in env (e.g. in
# tests via monkeypatch, or an operator rotation) is picked up automatically.
_key_cache: Optional[tuple[str, bytes]] = None


def _read_key_file(path: str) -> bytes:
    try:
        raw = base64.b64decode(
            Path(path).read_bytes().strip(),
            validate=True,
        )
    except FileNotFoundError as exc:
        raise CredentialCipherError(
            f"Credentials encryption key file not found: {path}"
        ) from exc
    except (ValueError, OSError) as exc:
        raise CredentialCipherError(
            f"Credentials encryption key file '{path}' must be base64-encoded "
            f"{KEY_BYTES} bytes: {exc}"
        ) from exc
    return raw


def _resolve_key() -> Optional[bytes]:
    """Return the 32-byte credential key, or ``None`` if none is configured.

    Raises :class:`CredentialCipherError` if a key is present but malformed.
    """
    global _key_cache

    raw_env = os.getenv(ENV_KEY, "").strip()
    raw_file = os.getenv(ENV_KEY_FILE, "").strip()
    cache_key = f"{raw_env}\x1f{raw_file}"

    if _key_cache is not None and _key_cache[0] == cache_key:
        return _key_cache[1]

    candidate: Optional[bytes] = None
    try:
        if raw_env:
            candidate = base64.b64decode(raw_env, validate=True)
        elif raw_file:
            candidate = _read_key_file(raw_file)
    except (ValueError, OSError) as exc:
        raise CredentialCipherError(
            f"{ENV_KEY} must be base64-encoded {KEY_BYTES} bytes: {exc}"
        ) from exc

    if candidate is not None and len(candidate) != KEY_BYTES:
        raise CredentialCipherError(
            f"Credentials encryption key must be exactly {KEY_BYTES} bytes "
            f"(got {len(candidate)})"
        )

    _key_cache = (cache_key, candidate)  # type: ignore[assignment]
    return candidate


def is_encryption_available() -> bool:
    """True when a valid credential key is provisioned."""
    try:
        return _resolve_key() is not None
    except CredentialCipherError as exc:
        logger.error("Credentials encryption key is misconfigured: %s", exc)
        return False


def is_encryption_required() -> bool:
    """True when writes must fail if no key is provisioned.

    Plaintext storage of a signing mnemonic is a development convenience only.
    It is allowed solely in an explicit local/dev/test environment; an unset
    or production-like environment requires the key, and so does an explicit
    ``BOT_CREDENTIALS_ENCRYPTION_REQUIRED=true`` anywhere.
    """
    if os.getenv(ENV_REQUIRED, "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return not is_explicit_dev_or_test_environment()


# Tracks env states for which the no-key warning has already been emitted, so the
# periodic DB sync does not flood logs.
_no_key_warned_for: set[str] = set()


def _require_key_for_write() -> bytes:
    """Return the encryption key for a write, or ``b""`` for plaintext passthrough.

    Raises :class:`CredentialEncryptionError` when encryption is required but no
    key is present. Emits a no-key warning at most once per env configuration.
    """
    key = _resolve_key()
    if key is not None:
        return key

    if is_encryption_required():
        raise CredentialEncryptionError(
            "Credential encryption is required but no key is provisioned. "
            f"Set {ENV_KEY} (base64, {KEY_BYTES} bytes) or {ENV_KEY_FILE}."
        )

    raw_env = os.getenv(ENV_KEY, "").strip()
    raw_file = os.getenv(ENV_KEY_FILE, "").strip()
    cache_key = f"{raw_env}\x1f{raw_file}"
    if cache_key not in _no_key_warned_for:
        _no_key_warned_for.add(cache_key)
        logger.warning(
            "Credential encryption key is not provisioned; bot credentials will "
            "be stored in plain text. Set %s to enable encryption, or "
            "%s=true to refuse plaintext writes.",
            ENV_KEY,
            ENV_REQUIRED,
        )
    return b""


def _key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:8]


# --- Low-level seal/open -----------------------------------------------------


def seal_secret(plaintext: Any) -> Dict[str, Any]:
    """Encrypt a JSON-serializable object into an envelope dict.

    This is the low-level encrypt primitive and always requires a provisioned
    key. Plaintext-passthrough behaviour (when no key is configured) is handled
    by :func:`seal_config_secrets`, not here.
    """
    key = _resolve_key()
    if key is None:
        raise CredentialEncryptionError(
            "seal_secret requires a provisioned credential key."
        )
    encoded = json.dumps(plaintext, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return _encrypt_with_key(key, encoded)


def _encrypt_with_key(key: bytes, encoded: bytes) -> Dict[str, Any]:
    nonce = os.urandom(NONCE_BYTES)
    # AESGCM.encrypt returns ciphertext || tag.
    sealed = AESGCM(key).encrypt(nonce, encoded, None)
    return {
        "cipher": CIPHER_NAME,
        "version": CIPHER_VERSION,
        "key_id": _key_id(key),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(sealed).decode("ascii"),
    }


def open_secret(envelope: Any) -> Any:
    """Decrypt an envelope dict produced by :func:`seal_secret`.

    Raises :class:`CredentialDecryptionError` on tamper, malformed envelope, or
    key mismatch.
    """
    if not isinstance(envelope, dict) or envelope.get("cipher") != CIPHER_NAME:
        raise CredentialDecryptionError("Not an AESGCM credential envelope")
    key = _resolve_key()
    if key is None:
        raise CredentialDecryptionError(
            "Encrypted credential envelope present but no decryption key is "
            f"provisioned (set {ENV_KEY} / {ENV_KEY_FILE})."
        )

    envelope_key_id = str(envelope.get("key_id") or "")
    current_key_id = _key_id(key)
    if envelope_key_id and envelope_key_id != current_key_id:
        raise CredentialDecryptionError(
            f"Credential envelope was sealed with key id '{envelope_key_id}' but "
            f"the provisioned key id is '{current_key_id}'. Provide the matching "
            f"key or re-seal the credential."
        )

    try:
        nonce = base64.b64decode(str(envelope["nonce"]), validate=True)
        ciphertext = base64.b64decode(str(envelope["ciphertext"]), validate=True)
    except (KeyError, ValueError) as exc:
        raise CredentialDecryptionError(
            f"Credential envelope is malformed: {exc}"
        ) from exc

    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise CredentialDecryptionError(
            "Credential envelope failed authentication (tampered or wrong key)."
        ) from exc

    try:
        return json.loads(plaintext.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CredentialDecryptionError(
            f"Decrypted credential payload was not valid JSON: {exc}"
        ) from exc


# --- Block-level helpers (operate on config payloads) ------------------------


def _sealed_key(block: str) -> str:
    return f"{block}_sealed"


def seal_config_secrets(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``payload`` with secret blocks replaced by envelopes.

    Non-empty ``credentials``/``telegram`` blocks become ``credentials_sealed``/
    ``telegram_sealed`` envelopes and the plaintext blocks are removed. When no
    key is provisioned and encryption is not required, the payload is returned
    unchanged (plaintext passthrough). When encryption is required but no key is
    present, raises :class:`CredentialEncryptionError`.
    """
    sealed = dict(payload)
    key = _require_key_for_write()  # b"" → passthrough; raises if required+no key
    if not key:
        return sealed

    for block in SEALED_BLOCKS:
        value = sealed.get(block)
        if isinstance(value, dict) and value:
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            sealed[_sealed_key(block)] = _encrypt_with_key(key, encoded)
            sealed.pop(block, None)
        else:
            # Empty/missing block: ensure no stale envelope lingers.
            sealed.pop(_sealed_key(block), None)
    return sealed


def has_sealed_secrets(payload: Dict[str, Any]) -> bool:
    """True if ``payload`` carries any ``<block>_sealed`` envelope."""
    return any(_sealed_key(block) in payload for block in SEALED_BLOCKS)


def open_config_secrets(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``payload`` with secret envelopes decrypted in place.

    Envelopes are decrypted back to their ``credentials``/``telegram`` blocks and
    the ``<block>_sealed`` keys are removed. Legacy plaintext rows (no envelopes)
    pass through unchanged. Raises :class:`CredentialDecryptionError` only when an
    envelope is present but cannot be opened.
    """
    if not isinstance(payload, dict) or not has_sealed_secrets(payload):
        return dict(payload) if isinstance(payload, dict) else {}

    opened = dict(payload)
    for block in SEALED_BLOCKS:
        envelope = opened.pop(_sealed_key(block), None)
        if envelope is None:
            continue
        decrypted = open_secret(envelope)
        # Prefer the decrypted envelope over any stale plaintext leftover.
        opened[block] = decrypted
    return opened


__all__ = [
    "CIPHER_NAME",
    "CIPHER_VERSION",
    "KEY_BYTES",
    "NONCE_BYTES",
    "ENV_KEY",
    "ENV_KEY_FILE",
    "ENV_REQUIRED",
    "SEALED_BLOCKS",
    "CredentialCipherError",
    "CredentialEncryptionError",
    "CredentialDecryptionError",
    "is_encryption_available",
    "is_encryption_required",
    "seal_secret",
    "open_secret",
    "seal_config_secrets",
    "open_config_secrets",
    "has_sealed_secrets",
]
