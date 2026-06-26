#!/usr/bin/env python3
"""Validate the structured JSON config profile used by the app stack."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from secure_config import load_json, normalize_environment_name, resolve_profile_file

REQUIRED_KEYS = [
    "DB_PORT",
    "REDIS_PORT",
    "API_PORT",
    "PROXY_HTTP_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "SECRET_KEY",
    "API_BYPASS_AUTH",
    "ENVIRONMENT",
    "IS_TESTNET",
    "VITE_API_URL",
]

OPTIONAL_KEYS = [
    "LOKI_ENABLED",
    "LOKI_URL",
    "LOKI_USERNAME",
    "LOKI_PASSWORD",
    "LOKI_TENANT_ID",
]

RECOMMENDED_INFRA_KEYS = [
    "DATABASE_URL",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "REDIS_URL",
    "REDIS_HOST",
    "REDIS_PORT",
    "VALKEY_HOST",
    "VALKEY_PORT",
    "NATS_URL",
    "NATS_MONITORING_URL",
    "CLICKHOUSE_URL",
    "CLICKHOUSE_HOST",
    "CLICKHOUSE_PORT",
    "MINIO_ENDPOINT",
    "MINIO_CONSOLE_URL",
    "MINIO_BUCKET",
    "S3_ENDPOINT",
    "S3_REGION",
    "S3_FORCE_PATH_STYLE",
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


def flatten_config(tree: dict) -> dict[str, str]:
    flattened: dict[str, str] = {}

    def walk(node: object) -> None:
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if isinstance(value, dict):
                walk(value)
                continue
            if value is None:
                flattened[key] = ""
            elif isinstance(value, bool):
                flattened[key] = "true" if value else "false"
            elif isinstance(value, (int, float, str)):
                flattened[key] = str(value)
            else:
                flattened[key] = str(value)

    for section, value in tree.items():
        if section == "metadata":
            continue
        walk(value)

    return flattened


def load_structured_environment(environment: str) -> tuple[dict[str, str], Path]:
    profile_path = resolve_profile_file(environment, None)
    config = load_json(profile_path)
    return flatten_config(config), profile_path


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
    if is_testnet:
        warnings.append("IS_TESTNET=true; live trading credentials are expected from encrypted app settings")

    return errors, warnings


def validate_bot_db_rules(env: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for bot runtime DB cutover validation."""
    errors: list[str] = []
    warnings: list[str] = []

    cutover_mode = env.get("BOT_DB_CUTOVER_MODE", "shared").strip().lower()
    dedicated_url = env.get("BOT_DATABASE_URL", "").strip()
    dedicated_fields = [
        "BOT_DB_HOST",
        "BOT_DB_PORT",
        "BOT_DB_NAME",
        "BOT_DB_USER",
        "BOT_DB_PASSWORD",
    ]
    missing_dedicated_fields = [key for key in dedicated_fields if not env.get(key, "").strip()]

    if cutover_mode == "dedicated":
        if not dedicated_url and missing_dedicated_fields:
            errors.append(
                "BOT_DB_CUTOVER_MODE=dedicated requires BOT_DATABASE_URL or all BOT_DB_* connection fields"
            )
    elif cutover_mode == "dedicated_with_shared_fallback":
        if not dedicated_url and missing_dedicated_fields:
            warnings.append(
                "BOT_DB_CUTOVER_MODE=dedicated_with_shared_fallback is set but BOT_DATABASE_URL/BOT_DB_* are absent; bot will fall back to shared DB settings"
            )
    elif cutover_mode not in ("", "shared"):
        errors.append(
            "BOT_DB_CUTOVER_MODE must be one of shared, dedicated, or dedicated_with_shared_fallback"
        )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate structured stack configuration")
    parser.add_argument(
        "--environment",
        choices=("development", "production"),
        default=normalize_environment_name(
            os.getenv("APP_CONFIG_ENV")
            or os.getenv("CONFIG_ENV")
            or os.getenv("ENVIRONMENT")
            or os.getenv("APP_ENV")
            or "development"
        ),
        help="Structured config environment profile to validate",
    )
    parser.add_argument(
        "--strict-prod",
        action="store_true",
        help="Enable strict production checks (secure auth + live credential validation)",
    )
    args = parser.parse_args()

    try:
        env, profile_path = load_structured_environment(args.environment)
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"❌ Failed to load structured config: {exc}", file=sys.stderr)
        return 1

    missing = [k for k in REQUIRED_KEYS if k not in env]
    empty = [k for k in REQUIRED_KEYS if k in env and env[k] == ""]

    if missing or empty:
        print("❌ Structured config validation failed", file=sys.stderr)
        if missing:
            print(f"   Missing keys: {', '.join(missing)}", file=sys.stderr)
        if empty:
            print(f"   Empty keys: {', '.join(empty)}", file=sys.stderr)
        print(
            "   Tip: edit config/profiles with `make dev-config` or `make prod-config`",
            file=sys.stderr,
        )
        return 1

    optional_empty = [k for k in OPTIONAL_KEYS if env.get(k, "") == ""]
    missing_recommended = [k for k in RECOMMENDED_INFRA_KEYS if env.get(k, "") == ""]

    print(f"✅ Structured config is valid: {profile_path}")
    if optional_empty:
        print(
            "ℹ️ Optional keys not set (expected in non-live mode): "
            + ", ".join(optional_empty)
        )
    if missing_recommended:
        print(
            "ℹ️ Recommended local infrastructure keys not set: "
            + ", ".join(missing_recommended)
        )

    bot_db_errors, bot_db_warnings = validate_bot_db_rules(env)
    for warning in bot_db_warnings:
        print(f"ℹ️ {warning}")
    if bot_db_errors:
        print("❌ Bot DB validation failed", file=sys.stderr)
        for err in bot_db_errors:
            print(f"   - {err}", file=sys.stderr)
        return 1

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
