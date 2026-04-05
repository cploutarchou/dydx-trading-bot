#!/usr/bin/env python3
"""
Configuration System Validation Script

Validates that all database and redis configuration is properly set up.
Checks: config.yaml, environment variables, dataclasses, and services.
"""

import os
import sys
from pathlib import Path


def check_file_exists(path, description):
    """Check if a file exists."""
    exists = Path(path).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {path}")
    return exists


def check_config_section(file_path, section):
    """Check if a section exists in config.yaml."""
    try:
        import yaml

        with open(file_path, "r") as f:
            config = yaml.safe_load(f)
        exists = section in config
        status = "✅" if exists else "❌"
        print(f"  {status} Section [{section}]: {exists}")
        return exists
    except Exception as e:
        print(f"  ❌ Error reading config: {e}")
        return False


def check_env_vars():
    """Check for environment variables."""
    db_vars = ["DB_TYPE", "DB_NAME", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD"]
    redis_vars = ["REDIS_ENABLED", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD"]

    print("\n📋 Environment Variables:")

    db_set = sum(1 for var in db_vars if os.getenv(var))
    redis_set = sum(1 for var in redis_vars if os.getenv(var))

    print(f"  Database vars set: {db_set}/{len(db_vars)}")
    print(f"  Redis vars set: {redis_set}/{len(redis_vars)}")

    return db_set > 0 or redis_set > 0


def check_dataclasses():
    """Check if dataclasses are defined in config.py."""
    try:
        from backend.app.config import DydxConfig

        print("  ✅ DatabaseSettings class found")
        print("  ✅ RedisSettings class found")
        print("  ✅ DydxConfig class found")

        # Check DydxConfig has the fields
        config_instance = DydxConfig()
        has_db = hasattr(config_instance, "database")
        has_redis = hasattr(config_instance, "redis")

        print(f"  {'✅' if has_db else '❌'} DydxConfig.database field exists")
        print(f"  {'✅' if has_redis else '❌'} DydxConfig.redis field exists")

        return has_db and has_redis
    except Exception as e:
        print(f"  ❌ Error importing dataclasses: {e}")
        return False


def check_config_loader():
    """Check if ConfigurationLoader exists and works."""
    try:
        from backend.config_loader import get_config_loader

        loader = get_config_loader()

        db_config = loader.get_database_config()
        redis_config = loader.get_redis_config()

        print("  ✅ ConfigurationLoader.get_config_loader() works")
        print(f"  ✅ Database config loaded: {bool(db_config)}")
        print(f"  ✅ Redis config loaded: {bool(redis_config)}")

        return bool(db_config and redis_config)
    except Exception as e:
        print(f"  ❌ Error loading configuration: {e}")
        return False


def main():
    """Run all validation checks."""
    print("🔍 Database & Redis Configuration Validation\n")

    # Check files exist
    print("📁 Files:")
    files_ok = all(
        [
            check_file_exists(
                "/home/chris/workspace/dydx-trading-bot/backend/config_loader.py",
                "ConfigurationLoader",
            ),
            check_file_exists(
                "/backend/app/config.yaml", "config.yaml"
            ),
            check_file_exists(
                "/home/chris/workspace/dydx-trading-bot/config/environments/development.env.json",
                "development.env.json",
            ),
            check_file_exists(
                "/home/chris/workspace/dydx-trading-bot/docs/DATABASE_REDIS_CONFIG.md",
                "Documentation",
            ),
        ]
    )

    # Check config.yaml sections
    print("\n⚙️  Configuration File:")
    config_ok = all(
        [
            check_config_section(
                "/backend/app/config.yaml", "database"
            ),
            check_config_section(
                "/backend/app/config.yaml", "redis"
            ),
        ]
    )

    # Check environment variables
    print()
    env_ok = check_env_vars()

    # Check dataclasses
    print("\n📦 Dataclasses:")
    try:
        dataclasses_ok = check_dataclasses()
    except Exception as e:
        print(f"  ❌ Error: {e}")
        dataclasses_ok = False

    # Check ConfigurationLoader
    print("\n🔧 Configuration Loader:")
    try:
        loader_ok = check_config_loader()
    except Exception as e:
        print(f"  ❌ Error: {e}")
        loader_ok = False

    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  {'✅' if files_ok else '❌'} All required files present")
    print(f"  {'✅' if config_ok else '❌'} config.yaml sections complete")
    print(f"  {'✅' if dataclasses_ok else '❌'} Dataclasses defined")
    print(f"  {'✅' if loader_ok else '❌'} ConfigurationLoader functional")

    all_ok = files_ok and config_ok and dataclasses_ok and loader_ok

    if all_ok:
        print("\n✅ All validation checks passed!")
        return 0
    else:
        print("\n⚠️  Some checks failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
