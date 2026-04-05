#!/usr/bin/env python3
"""Repo-owned secure config tooling backed by AES-256-GCM."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "config" / "profiles"
DEFAULT_KEY_FILE = ROOT / ".configkey.bin"
PLAINTEXT_SUFFIX = ".config.json"
ENCRYPTED_SUFFIX = ".config.enc.json"
RUN_JSON_PATH = ROOT / "run.json"
EXAMPLE_PROFILE_PATH = PROFILES_DIR / "example.config.json"
DEFAULT_BACKUP_KEY_FILE = ROOT / ".configkey.bin.bak"


def normalize_environment_name(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"prod", "production"}:
        return "production"
    return "development"


def resolve_environment() -> str:
    for key in ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV"):
        value = os.getenv(key, "").strip()
        if value:
            return normalize_environment_name(value)
    return "development"


def resolve_key_file(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()

    env_value = os.getenv("APP_CONFIG_KEY_FILE", "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()

    return DEFAULT_KEY_FILE


def require_key_file(path: Path) -> Path:
    if not path.exists():
        raise RuntimeError(
            f"Missing config key file: {path}. Run `make config-keygen` first "
            "or place the shared binary key in the repo root."
        )
    return path


def load_key(path: Path) -> bytes:
    require_key_file(path)
    key = path.read_bytes()
    if len(key) != 32:
        raise RuntimeError(f"Invalid config key length in {path}; expected 32 bytes")
    return key


def write_key(path: Path, key: bytes) -> None:
    path.write_bytes(key)
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def key_to_token(key: bytes) -> str:
    return base64.urlsafe_b64encode(key).decode("ascii").rstrip("=")


def token_to_key(token: str) -> bytes:
    padded = token.strip() + "=" * (-len(token.strip()) % 4)
    key = base64.urlsafe_b64decode(padded.encode("ascii"))
    if len(key) != 32:
        raise RuntimeError("Decoded token is not a valid 32-byte config key")
    return key


def resolve_plain_profile_path(environment: str) -> Path:
    return PROFILES_DIR / f"{environment}{PLAINTEXT_SUFFIX}"


def resolve_encrypted_profile_path(environment: str) -> Path:
    return PROFILES_DIR / f"{environment}{ENCRYPTED_SUFFIX}"


def resolve_profile_file(environment: str, explicit: str | None = None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Missing profile file: {candidate}")

    candidates = [
        resolve_encrypted_profile_path(environment),
        resolve_plain_profile_path(environment),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Missing profile file: {candidates[0]} (or fallback {candidates[1]})"
    )


def normalize_json_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True) + "\n"


def encrypt_payload(data: dict[str, Any], key: bytes) -> dict[str, Any]:
    plaintext = normalize_json_text(data).encode("utf-8")
    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(key).encrypt(nonce, plaintext, None)
    ciphertext = encrypted[:-16]
    tag = encrypted[-16:]
    return {
        "version": 1,
        "cipher": "AES-256-GCM",
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
    }


def decrypt_payload(payload: dict[str, Any], key: bytes) -> dict[str, Any]:
    try:
        nonce = base64.b64decode(str(payload["nonce"]))
        ciphertext = base64.b64decode(str(payload["ciphertext"]))
        tag = base64.b64decode(str(payload["tag"]))
    except KeyError as exc:
        raise RuntimeError(f"Encrypted config payload is missing field: {exc}") from exc

    plaintext = AESGCM(key).decrypt(nonce, ciphertext + tag, None)
    parsed = json.loads(plaintext.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError("Decrypted config must be a JSON object")
    return parsed


def load_json(path: Path, key_file: Path | None = None) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"Structured config at {path} must be a JSON object")

    if path.name.endswith(".enc.json") or {"cipher", "nonce", "ciphertext", "tag"} <= set(raw.keys()):
        key = load_key(resolve_key_file(str(key_file) if key_file else None))
        return decrypt_payload(raw, key)

    return raw


def load_runtime_json(environment: str, explicit_profile: str | None = None, key_file: Path | None = None) -> tuple[dict[str, Any], Path]:
    explicit_run = os.getenv("APP_RUN_CONFIG_FILE", "").strip()
    if explicit_run:
        candidate = Path(explicit_run).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Missing runtime config file: {candidate}")
        return load_json(candidate, key_file), candidate

    if RUN_JSON_PATH.exists():
        return load_json(RUN_JSON_PATH, key_file), RUN_JSON_PATH

    profile_path = resolve_profile_file(environment, explicit_profile)
    return load_json(profile_path, key_file), profile_path


def write_encrypted_json(path: Path, data: dict[str, Any], key_file: Path | None = None) -> None:
    key = load_key(resolve_key_file(str(key_file) if key_file else None))
    payload = encrypt_payload(data, key)
    path.write_text(normalize_json_text(payload), encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def resolve_editor() -> list[str]:
    for env_name in ("CODE_EDITOR", "VISUAL", "EDITOR"):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return shlex.split(raw)
    if shutil.which("code"):
        return ["code", "--wait"]
    if shutil.which("nano"):
        return ["nano"]
    if shutil.which("vim"):
        return ["vim"]
    raise RuntimeError("No editor found. Set CODE_EDITOR, VISUAL, or EDITOR.")


def edit_profile(environment: str, key_file: Path | None = None) -> None:
    profile_path = resolve_encrypted_profile_path(environment)
    if not profile_path.exists():
        if not EXAMPLE_PROFILE_PATH.exists():
            raise RuntimeError(f"Missing config template: {EXAMPLE_PROFILE_PATH}")
        parsed = json.loads(EXAMPLE_PROFILE_PATH.read_text(encoding="utf-8"))
        metadata = parsed.setdefault("metadata", {})
        metadata["environment"] = environment
        shared = parsed.setdefault("shared", {})
        shared["APP_ENV"] = environment
        shared["ENVIRONMENT"] = environment
        write_encrypted_json(profile_path, parsed, key_file)

    data = load_json(profile_path, key_file)
    editor = resolve_editor()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(normalize_json_text(data))

    try:
        result = subprocess.run([*editor, str(temp_path)], cwd=ROOT)
        if result.returncode != 0:
            raise RuntimeError("Editor exited with a non-zero status")
        updated = json.loads(temp_path.read_text(encoding="utf-8"))
        if not isinstance(updated, dict):
            raise RuntimeError("Updated profile must be a JSON object")
        write_encrypted_json(profile_path, updated, key_file)
    finally:
        temp_path.unlink(missing_ok=True)


def decrypt_to_path(environment: str, output: Path, key_file: Path | None = None, explicit_profile: str | None = None) -> Path:
    profile_path = resolve_profile_file(environment, explicit_profile)
    config = load_json(profile_path, key_file)
    output.write_text(normalize_json_text(config), encoding="utf-8")
    try:
        output.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return profile_path


def encrypt_plain_profile(environment: str, key_file: Path | None = None, source: Path | None = None) -> Path:
    plain_path = source or resolve_plain_profile_path(environment)
    if not plain_path.exists():
        raise RuntimeError(f"Missing plaintext profile: {plain_path}")
    parsed = json.loads(plain_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError("Plaintext profile must be a JSON object")
    encrypted_path = resolve_encrypted_profile_path(environment)
    write_encrypted_json(encrypted_path, parsed, key_file)
    return encrypted_path


def list_existing_encrypted_profiles() -> list[Path]:
    profiles: list[Path] = []
    for environment in ("development", "production"):
        profile_path = resolve_encrypted_profile_path(environment)
        if profile_path.exists():
            profiles.append(profile_path)
    return profiles


def rotate_key(
    current_key_file: Path,
    backup_key_file: Path | None = None,
    profiles: list[Path] | None = None,
) -> tuple[list[Path], Path, str]:
    old_key = load_key(current_key_file)
    target_profiles = profiles or list_existing_encrypted_profiles()
    if not target_profiles:
        raise RuntimeError(
            "No encrypted profiles found to rotate. Expected at least one *.config.enc.json file in config/profiles/."
        )

    decrypted_profiles: dict[Path, dict[str, Any]] = {}
    for profile_path in target_profiles:
        decrypted_profiles[profile_path] = load_json(profile_path, current_key_file)

    new_key = secrets.token_bytes(32)
    temp_files: list[tuple[Path, Path]] = []
    try:
        for profile_path, config in decrypted_profiles.items():
            temp_path = profile_path.with_name(profile_path.name + ".tmp")
            payload = encrypt_payload(config, new_key)
            temp_path.write_text(normalize_json_text(payload), encoding="utf-8")
            try:
                temp_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
            temp_files.append((profile_path, temp_path))

        backup_target = backup_key_file or DEFAULT_BACKUP_KEY_FILE
        if backup_target.resolve() == current_key_file.resolve():
            raise RuntimeError("Backup key path must be different from the active key path")

        if backup_target.exists():
            backup_target.unlink()
        backup_target.write_bytes(old_key)
        try:
            backup_target.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

        for profile_path, temp_path in temp_files:
            temp_path.replace(profile_path)

        write_key(current_key_file, new_key)
        return target_profiles, backup_target, key_to_token(new_key)
    finally:
        for _, temp_path in temp_files:
            temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Secure config tooling for the monorepo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    keygen = subparsers.add_parser("keygen", help="Generate the binary repo config key")
    keygen.add_argument("--output", default=str(DEFAULT_KEY_FILE))
    keygen.add_argument("--force", action="store_true")

    install_key = subparsers.add_parser("install-key", help="Install a binary key file from a printed token")
    install_key.add_argument("--token", required=True)
    install_key.add_argument("--output", default=str(DEFAULT_KEY_FILE))
    install_key.add_argument("--force", action="store_true")

    show_token = subparsers.add_parser("show-token", help="Print the base64 token for an existing key")
    show_token.add_argument("--key-file", default=str(DEFAULT_KEY_FILE))

    decrypt_cmd = subparsers.add_parser("decrypt", help="Decrypt a profile to a plaintext JSON file")
    decrypt_cmd.add_argument("--environment", choices=("development", "production"), required=True)
    decrypt_cmd.add_argument("--output", required=True)
    decrypt_cmd.add_argument("--config-file", default=None)
    decrypt_cmd.add_argument("--key-file", default=str(DEFAULT_KEY_FILE))

    encrypt_cmd = subparsers.add_parser("encrypt", help="Encrypt a plaintext profile file")
    encrypt_cmd.add_argument("--environment", choices=("development", "production"), required=True)
    encrypt_cmd.add_argument("--input", default=None)
    encrypt_cmd.add_argument("--key-file", default=str(DEFAULT_KEY_FILE))

    edit_cmd = subparsers.add_parser("edit", help="Decrypt, edit, and re-encrypt a profile")
    edit_cmd.add_argument("--environment", choices=("development", "production"), required=True)
    edit_cmd.add_argument("--key-file", default=str(DEFAULT_KEY_FILE))

    rotate_cmd = subparsers.add_parser(
        "rotate-key",
        help="Rotate the repo config key and re-encrypt all committed encrypted profiles",
    )
    rotate_cmd.add_argument("--key-file", default=str(DEFAULT_KEY_FILE))
    rotate_cmd.add_argument("--backup-key-file", default=str(DEFAULT_BACKUP_KEY_FILE))

    args = parser.parse_args()

    try:
        if args.command == "keygen":
            path = resolve_key_file(args.output)
            if path.exists() and not args.force:
                raise RuntimeError(
                    f"Config key already exists at {path}. Use --force only if you truly want to replace it."
                )
            key = secrets.token_bytes(32)
            write_key(path, key)
            token = key_to_token(key)
            print(f"Created {path}")
            print(f"Config token: {token}")
            return 0

        if args.command == "install-key":
            path = resolve_key_file(args.output)
            if path.exists() and not args.force:
                raise RuntimeError(
                    f"Config key already exists at {path}. Use --force only if you truly want to replace it."
                )
            key = token_to_key(args.token)
            write_key(path, key)
            print(f"Installed {path}")
            return 0

        if args.command == "show-token":
            key = load_key(resolve_key_file(args.key_file))
            print(key_to_token(key))
            return 0

        if args.command == "decrypt":
            output = Path(args.output).expanduser().resolve()
            profile = decrypt_to_path(
                args.environment,
                output,
                resolve_key_file(args.key_file),
                args.config_file,
            )
            print(f"Decrypted {profile} -> {output}")
            return 0

        if args.command == "encrypt":
            encrypted_path = encrypt_plain_profile(
                args.environment,
                resolve_key_file(args.key_file),
                Path(args.input).expanduser().resolve() if args.input else None,
            )
            print(f"Encrypted profile written to {encrypted_path}")
            return 0

        if args.command == "edit":
            edit_profile(args.environment, resolve_key_file(args.key_file))
            print(f"Saved encrypted {args.environment} profile")
            return 0

        if args.command == "rotate-key":
            profiles, backup_key, token = rotate_key(
                resolve_key_file(args.key_file),
                Path(args.backup_key_file).expanduser().resolve() if args.backup_key_file else None,
            )
            print("Rotated config key and re-encrypted profiles:")
            for profile in profiles:
                print(f"  - {profile}")
            print(f"Backup key: {backup_key}")
            print(f"New config token: {token}")
            return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
