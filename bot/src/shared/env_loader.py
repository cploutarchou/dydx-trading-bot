from __future__ import annotations

import base64
import json
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PathLike = Union[str, Path]


def _is_structured_config_root(candidate: Path) -> bool:
    return (candidate / "config" / "profiles").exists() or (
            candidate / "run.json"
    ).exists()


def find_repo_root(anchor: PathLike) -> Path:
    current = Path(anchor).resolve()
    search_from = current.parent if current.is_file() else current

    for candidate in (search_from, *search_from.parents):
        if (
                (candidate / ".github").exists()
                and (candidate / "AGENTS.md").exists()
                and _is_structured_config_root(candidate)
        ):
            return candidate

    raise RuntimeError(
        f"Unable to locate monorepo root from {search_from}. Expected a parent with .github, AGENTS.md, and config/profiles or run.json."
    )


def _normalize_environment_name(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"prod", "production"}:
        return "production"
    return "development"


def _resolve_environment() -> str:
    for key in ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV"):
        value = os.getenv(key, "").strip()
        if value:
            return _normalize_environment_name(value)
    return "development"


def _resolve_key_file(repo_root: Path) -> Path:
    explicit = os.getenv("APP_CONFIG_KEY_FILE", "").strip()
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
    else:
        candidate = repo_root / ".configkey.bin"

    if not candidate.exists():
        raise RuntimeError(
            f"Missing config key file: {candidate}. Run `make config-keygen` or install the shared key first."
        )
    return candidate


def _decrypt_payload(payload: dict[str, Any], key: bytes) -> dict[str, Any]:
    try:
        nonce = base64.b64decode(str(payload["nonce"]))
        ciphertext = base64.b64decode(str(payload["ciphertext"]))
        tag = base64.b64decode(str(payload["tag"]))
    except KeyError as exc:
        raise RuntimeError(f"Encrypted config payload is missing field: {exc}") from exc

    plaintext = AESGCM(key).decrypt(nonce, ciphertext + tag, None)
    parsed = json.loads(plaintext.decode("utf-8"), object_pairs_hook=OrderedDict)
    if not isinstance(parsed, dict):
        raise RuntimeError("Structured config must be a JSON object")
    return parsed


def _load_json(path: Path, repo_root: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Structured config at {path} must be a JSON object")

    is_encrypted = path.name.endswith(".config.enc.json") or {
        "cipher",
        "nonce",
        "ciphertext",
        "tag",
    } <= set(parsed.keys())
    if not is_encrypted:
        return parsed

    key = _resolve_key_file(repo_root).read_bytes()
    if len(key) != 32:
        raise RuntimeError("Config key must be exactly 32 bytes")
    return _decrypt_payload(parsed, key)


def _resolve_profile_file(repo_root: Path, environment: str) -> Path:
    explicit_run = os.getenv("APP_RUN_CONFIG_FILE", "").strip()
    if explicit_run:
        candidate = Path(explicit_run).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise RuntimeError(f"Missing runtime config: {candidate}")

    run_json = repo_root / "run.json"
    if run_json.exists():
        return run_json

    explicit = os.getenv("APP_CONFIG_FILE", "").strip()
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise RuntimeError(f"Missing structured config profile: {candidate}")

    profiles_dir = repo_root / "config" / "profiles"
    candidates = [
        profiles_dir / f"{environment}.config.enc.json",
        profiles_dir / f"{environment}.config.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "Missing structured config profile: "
        f"{profiles_dir / f'{environment}.config.enc.json'}"
    )


def _normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))


def _flatten_env(node: dict[str, Any]) -> OrderedDict[str, str]:
    flattened: OrderedDict[str, str] = OrderedDict()

    def walk(value: Any) -> None:
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            if isinstance(child, dict):
                walk(child)
            else:
                flattened[key] = _normalize_scalar(child)

    for section, value in node.items():
        if section == "metadata":
            continue
        walk(value)
    return flattened


def load_file_env_values(override: bool = True) -> None:
    for key, path in list(os.environ.items()):
        if not key.endswith("_FILE"):
            continue

        target = key[:-5]
        if not target or not path.strip():
            continue
        if not override and os.getenv(target, "").strip():
            continue

        secret_path = Path(path).expanduser()
        # Skip if the file doesn't exist (e.g., VS Code debugger artifacts)
        if not secret_path.exists():
            continue
        os.environ[target] = secret_path.read_text(encoding="utf-8").rstrip("\r\n")


def load_repo_env(anchor: PathLike, override: bool = True) -> Path:
    load_file_env_values(override=override)
    repo_root = find_repo_root(anchor)
    environment = _resolve_environment()
    profile_path = _resolve_profile_file(repo_root, environment)
    config = _load_json(profile_path, repo_root)

    for key, value in _flatten_env(config).items():
        if override or key not in os.environ or os.environ[key] == "":
            os.environ[key] = value

    os.environ.setdefault("APP_CONFIG_ENV", environment)
    load_file_env_values(override=True)
    return profile_path
