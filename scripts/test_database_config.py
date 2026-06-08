#!/usr/bin/env python3
"""Smoke-test MariaDB connectivity using repository DB_* environment variables."""

from __future__ import annotations

import os
import sys

import pymysql


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def main() -> int:
    db_type = _env("DB_TYPE", "mysql").strip().lower()
    if db_type not in {"mysql", "mariadb"}:
        print("Unsupported DB_TYPE. This repository supports MariaDB/MySQL only.")
        return 2

    host = _env("DB_HOST", "127.0.0.1")
    port = int(_env("DB_PORT", "3306"))
    name = _env("DB_NAME", "dydx_bot")
    user = _env("DB_USER", "dydx_bot")
    password = _env("DB_PASSWORD", "")

    print("Testing MariaDB connectivity")
    print(f"  host={host}")
    print(f"  port={port}")
    print(f"  database={name}")
    print(f"  user={user}")

    try:
        with pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=name,
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=10,
            write_timeout=10,
            autocommit=True,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception as exc:
        print(f"MariaDB connectivity check failed: {exc}")
        return 1

    print("MariaDB connectivity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
