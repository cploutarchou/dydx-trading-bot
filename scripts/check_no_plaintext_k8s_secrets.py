#!/usr/bin/env python3
"""Fail when tracked k8s YAML contains obvious plaintext secret values."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = [REPO_ROOT / "deploy" / "k8s", REPO_ROOT / "deploy" / "k8s-next"]
SECRET_KEY_PATTERN = re.compile(
    r"^\s*(?P<key>"
    r"JWT_SECRET_KEY|SECRET_KEY|ENCRYPTION_KEY|BOT_API_TOKEN|DB_PASSWORD|"
    r"MARIADB_ROOT_PASSWORD|DB_ADMIN_PASSWORD|BREAK_GLASS_NEW_ROOT_PASSWORD"
    r")\s*:\s*(?P<value>.+?)\s*$"
)
PRIVATE_KEY_MARKER = "-----BEGIN PRIVATE KEY-----"
PLACEHOLDER_PREFIXES = (
    "<",
    "REPLACE",
    "PLACEHOLDER",
    "TODO",
    "CHANGE-ME",
    "CHANGE_ME",
    "example",
    "example-",
)


def iter_yaml_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for pattern in ("*.yaml", "*.yml"):
            files.extend(sorted(root.rglob(pattern)))
    return files


def looks_like_plaintext_secret(raw_value: str) -> bool:
    value = raw_value.strip()
    if not value:
        return False
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1].strip()
    if any(value.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES):
        return False
    if "${" in value or value.startswith("valueFrom"):
        return False
    if len(value) < 8:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=._-]+", value))


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = path.read_bytes().decode("utf-8", errors="ignore").splitlines()

    for idx, line in enumerate(lines, start=1):
        if PRIVATE_KEY_MARKER in line:
            findings.append(f"{path}:{idx}: private key material must not be committed")
            continue
        match = SECRET_KEY_PATTERN.match(line)
        if not match:
            continue
        if looks_like_plaintext_secret(match.group("value")):
            findings.append(
                f"{path}:{idx}: plaintext secret assignment for {match.group('key')}"
            )
    return findings


def main() -> int:
    files = iter_yaml_files()
    findings: list[str] = []
    for path in files:
        findings.extend(scan_file(path))

    if findings:
        print("Plaintext secrets detected in k8s YAML:\n", file=sys.stderr)
        for item in findings:
            print(f"- {item}", file=sys.stderr)
        print(
            "\nRemediate by replacing literal secret values with encrypted or referenced secrets.",
            file=sys.stderr,
        )
        return 1

    print("No plaintext k8s secrets detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
