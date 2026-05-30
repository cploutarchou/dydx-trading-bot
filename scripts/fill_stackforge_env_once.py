#!/usr/bin/env python3
"""One-time safe filler for .env.stackforge placeholder fields.

Behavior:
- Updates ONLY known placeholder values.
- Generates strong random secrets for required secret fields.
- Supports domain overrides via CLI flags.
- Creates a timestamped backup before writing.
- Idempotent: re-running after fields are real values makes no changes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import secrets
import sys
from pathlib import Path

PLACEHOLDER_TOKENS = (
    "replace-with",
    "change-me",
    "example.com",
    "__required",
)

DEFAULT_APP_DOMAIN = "executionlab.io"
DEFAULT_API_DOMAIN = "api.executionlab.io"


def is_placeholder(value: str) -> bool:
    v = (value or "").strip().lower()
    return any(token in v for token in PLACEHOLDER_TOKENS)


def generate_secret(length: int = 48) -> str:
    # URL-safe and typically > requested entropy budget.
    return secrets.token_urlsafe(length)


def parse_env_lines(lines: list[str]) -> list[tuple[str | None, str]]:
    parsed: list[tuple[str | None, str]] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not line or line.lstrip().startswith("#") or "=" not in line:
            parsed.append((None, line))
            continue
        key, value = line.split("=", 1)
        parsed.append((key.strip(), value))
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill .env.stackforge placeholders one time")
    parser.add_argument(
        "--env-file",
        default=".env.stackforge",
        help="Target env file path (default: .env.stackforge)",
    )
    parser.add_argument(
        "--app-domain",
        default=DEFAULT_APP_DOMAIN,
        help=f"Frontend domain if APP_DOMAIN is placeholder (default: {DEFAULT_APP_DOMAIN})",
    )
    parser.add_argument(
        "--api-domain",
        default=DEFAULT_API_DOMAIN,
        help=f"API domain if API_DOMAIN is placeholder (default: {DEFAULT_API_DOMAIN})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file).resolve()
    if not env_path.exists():
        print(f"❌ Env file not found: {env_path}", file=sys.stderr)
        return 1

    original_text = env_path.read_text(encoding="utf-8")
    parsed = parse_env_lines(original_text.splitlines())

    updates: dict[str, str] = {}

    secret_fields = (
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "ENCRYPTION_KEY",
    )

    for key, value in parsed:
        if key is None:
            continue
        if key in secret_fields and is_placeholder(value):
            updates[key] = generate_secret(48)
        elif key == "APP_DB_PASSWORD" and is_placeholder(value):
            updates[key] = generate_secret(32)
        elif key == "APP_DOMAIN" and is_placeholder(value):
            updates[key] = args.app_domain.strip()
        elif key == "API_DOMAIN" and is_placeholder(value):
            updates[key] = args.api_domain.strip()

    if not updates:
        print("✅ No placeholder fields found. Nothing to change.")
        return 0

    rendered: list[str] = []
    for key, value in parsed:
        if key is None:
            rendered.append(value)
            continue
        new_value = updates.get(key, value)
        rendered.append(f"{key}={new_value}")

    new_text = "\n".join(rendered) + "\n"

    print("Planned updates:")
    for k in sorted(updates.keys()):
        print(f"- {k}: updated")

    if args.dry_run:
        print("\n(dry-run) No files were written.")
        return 0

    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = env_path.with_suffix(env_path.suffix + f".bak.{ts}")
    backup.write_text(original_text, encoding="utf-8")
    env_path.write_text(new_text, encoding="utf-8")

    print(f"✅ Updated {env_path}")
    print(f"🗂️ Backup created: {backup}")
    print("⚠️ Secrets were generated locally. Store them securely.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
