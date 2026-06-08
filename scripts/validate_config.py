#!/usr/bin/env python3
"""Validate DB/env-backed runtime configuration for local development."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOT_ROOT = REPO_ROOT / "bot"
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from src.shared.env_loader import load_repo_env  # noqa: E402


def check_file_exists(path: Path, description: str) -> bool:
    exists = path.exists()
    status = "OK" if exists else "MISSING"
    print(f"{status}: {description}: {path}")
    return exists


def check_env_vars() -> bool:
    db_vars = [
        "DATABASE_URL",
        "BOT_DATABASE_URL",
        "DB_HOST",
        "DB_HOST",
        "DB_NAME",
        "DB_NAME",
        "DB_USER",
        "DB_USER",
    ]
    redis_vars = ["REDIS_ENABLED", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD"]

    print("\nEnvironment:")
    db_set = [var for var in db_vars if os.getenv(var)]
    redis_set = [var for var in redis_vars if os.getenv(var)]

    print(f"  DB vars set: {len(db_set)}/{len(db_vars)}")
    print(f"  Redis vars set: {len(redis_set)}/{len(redis_vars)}")
    return bool(db_set)


def check_dataclasses() -> bool:
    try:
        from config.config import DydxConfig, config

        resolved = config()
        print("  DydxConfig class import: OK")
        status = "OK" if isinstance(resolved, DydxConfig) else "MISSING"
        environment = getattr(resolved, "environment", "unknown") if resolved else "unknown"
        print(f"  Config resolved: {status}")
        print(f"  Environment: {environment}")
        return isinstance(resolved, DydxConfig)
    except Exception as exc:
        print(f"  Config import failed: {exc}")
        return False


def check_database_config() -> bool:
    try:
        from src.infrastructure.database import DatabaseConfig

        diagnostics = DatabaseConfig().to_diagnostics()
        print("  DatabaseConfig import: OK")
        print(
            "  DB target: "
            f"{diagnostics['host']}:{diagnostics['port']}/{diagnostics['name']} "
            f"mode={diagnostics['cutover_mode']}"
        )
        return bool(diagnostics["host"] and diagnostics["name"])
    except Exception as exc:
        print(f"  DatabaseConfig failed: {exc}")
        return False


def check_deprecated_yaml_configs() -> bool:
    yaml_files = sorted((BOT_ROOT / "bot_states").glob("config_*.yaml"))
    if not yaml_files:
        print("  Deprecated runtime YAML configs: none")
        return True
    print(
        "  Deprecated runtime YAML configs found; run "
        "bot/.venv/bin/python scripts/migrate_yaml_configs_to_db.py before deleting them:"
    )
    for path in yaml_files:
        print(f"    {path}")
    return False


def main() -> int:
    load_repo_env(str(BOT_ROOT / "src" / "main_instance.py"))
    print("DB/env-backed runtime configuration validation\n")

    files_ok = all(
        [
            check_file_exists(
                REPO_ROOT / "config" / "profiles" / "development.config.enc.json",
                "development encrypted profile",
            ),
            check_file_exists(REPO_ROOT / "Makefile", "root Makefile"),
            check_file_exists(BOT_ROOT / "src" / "infrastructure" / "database.py", "bot DB layer"),
        ]
    )

    env_ok = check_env_vars()
    print("\nDataclasses:")
    dataclasses_ok = check_dataclasses()
    print("\nDatabase:")
    db_ok = check_database_config()
    print("\nDeprecated YAML:")
    yaml_ok = check_deprecated_yaml_configs()

    all_ok = files_ok and env_ok and dataclasses_ok and db_ok and yaml_ok
    print("\nSummary:")
    print(f"  Files: {'OK' if files_ok else 'FAILED'}")
    print(f"  DB env: {'OK' if env_ok else 'FAILED'}")
    print(f"  Config dataclasses: {'OK' if dataclasses_ok else 'FAILED'}")
    print(f"  Database config: {'OK' if db_ok else 'FAILED'}")
    print(f"  Deprecated YAML: {'OK' if yaml_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
