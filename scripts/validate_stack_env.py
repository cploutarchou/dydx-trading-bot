#!/usr/bin/env python3
"""Validate the shared repo-root .env file for dev/prod stack startup."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REQUIRED_KEYS = [
    "POSTGRES_PORT",
    "REDIS_PORT",
    "API_PORT",
    "PROXY_HTTP_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "SECRET_KEY",
    "API_BYPASS_AUTH",
    "ENVIRONMENT",
    "IS_TESTNET",
    "VITE_API_URL",
]

OPTIONAL_KEYS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "DYDX_TESTNET_ADDRESS",
    "DYDX_TESTNET_MNEMONIC",
    "DYDX_MAINNET_ADDRESS",
    "DYDX_MAINNET_MNEMONIC",
    "LOKI_ENABLED",
    "LOKI_URL",
    "LOKI_USERNAME",
    "LOKI_PASSWORD",
    "LOKI_TENANT_ID",
]


PLACEHOLDER_TOKENS = (
    "your_",
    "_here",
    "example",
    "changeme",
    "change-me",
    "placeholder",
    "${",
)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def is_placeholder(value: str) -> bool:
    if value is None:
        return True
    v = value.strip().lower()
    if not v:
        return True
    return any(token in v for token in PLACEHOLDER_TOKENS)


def validate_prod_rules(env: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for strict production validation."""
    errors: list[str] = []
    warnings: list[str] = []

    secret_key = env.get("SECRET_KEY", "")
    if is_placeholder(secret_key) or len(secret_key) < 32:
        errors.append(
            "SECRET_KEY must be set to a non-placeholder value with at least 32 characters"
        )

    api_bypass = env.get("API_BYPASS_AUTH", "false").strip().lower() == "true"
    if api_bypass:
        errors.append("API_BYPASS_AUTH must be false in production mode")

    is_testnet = env.get("IS_TESTNET", "true").strip().lower() == "true"
    if not is_testnet:
        mainnet_address = env.get("DYDX_MAINNET_ADDRESS", "")
        mainnet_mnemonic = env.get("DYDX_MAINNET_MNEMONIC", "")
        if is_placeholder(mainnet_address):
            errors.append(
                "DYDX_MAINNET_ADDRESS is required and must not be a placeholder when IS_TESTNET=false"
            )
        if is_placeholder(mainnet_mnemonic):
            errors.append(
                "DYDX_MAINNET_MNEMONIC is required and must not be a placeholder when IS_TESTNET=false"
            )
    else:
        warnings.append("IS_TESTNET=true; skipping mainnet credential checks")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate stack environment variables")
    parser.add_argument(
        "--strict-prod",
        action="store_true",
        help="Enable strict production checks (secure auth + live credential validation)",
    )
    args = parser.parse_args()

    env_path = Path(".env")
    if not env_path.exists():
        print("❌ Missing .env. Run: make stack-env", file=sys.stderr)
        return 1

    env = parse_env(env_path)

    missing = [k for k in REQUIRED_KEYS if k not in env]
    empty = [k for k in REQUIRED_KEYS if k in env and env[k] == ""]

    if missing or empty:
        print("❌ .env validation failed", file=sys.stderr)
        if missing:
            print(f"   Missing keys: {', '.join(missing)}", file=sys.stderr)
        if empty:
            print(f"   Empty keys: {', '.join(empty)}", file=sys.stderr)
        print("   Tip: copy defaults from .env.example", file=sys.stderr)
        return 1

    optional_empty = [k for k in OPTIONAL_KEYS if env.get(k, "") == ""]

    print("✅ .env contains all required keys")
    if optional_empty:
        print(
            "ℹ️ Optional keys not set (expected in non-live mode): "
            + ", ".join(optional_empty)
        )

    if args.strict_prod:
        prod_errors, prod_warnings = validate_prod_rules(env)
        for warning in prod_warnings:
            print(f"ℹ️ {warning}")
        if prod_errors:
            print("❌ Strict production validation failed", file=sys.stderr)
            for err in prod_errors:
                print(f"   - {err}", file=sys.stderr)
            return 1
        print("✅ Strict production validation passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
