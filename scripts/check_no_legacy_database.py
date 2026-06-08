#!/usr/bin/env python3
"""Fail if active repository files contain legacy PostgreSQL patterns."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"postgres",
        r"postgresql",
        r"psql\b",
        r"pg_isready",
        r"pg_dump",
        r"lib/pq",
        r"psycopg",
        r"asyncpg",
        r"\bpgx\b",
        r"\b5432\b",
    )
]
SQL_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\bON\s+CONFLICT\b",
        r"\bRETURNING\b",
        r"\bILIKE\b",
        r"\bBIGSERIAL\b",
        r"\bSERIAL\b",
        r"\bJSONB\b",
        r"\bTIMESTAMPTZ\b",
        r"\bpg_",
    )
]
PLACEHOLDER_PATTERN = re.compile(r"\$[0-9]+\b")

ALLOWLIST_PREFIXES = (
    "backend/migrations/postgres/",
    "bot/migrations/versions/",
)

ALLOWLIST_FILES = {
    "docs/database-migration-audit.md",
    "docs/database-migrations.md",
    "docs/postgresql-removal-audit.md",
    "scripts/check_no_legacy_database.py",
    "backend/go.sum",
}

SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "venv",
}


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(4096)
    except OSError:
        return True


def _allowed(relative: str) -> bool:
    return relative in ALLOWLIST_FILES or any(
        relative.startswith(prefix) for prefix in ALLOWLIST_PREFIXES
    )


def main() -> int:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if _allowed(relative) or _is_binary(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(f"{relative}:{line_number}: {line.strip()}")
                continue
            if path.suffix in {".go", ".sql", ".py"}:
                if any(pattern.search(line) for pattern in SQL_PATTERNS):
                    findings.append(f"{relative}:{line_number}: {line.strip()}")
                    continue
            if path.suffix in {".go", ".sql"} and "$2a$" not in line:
                if PLACEHOLDER_PATTERN.search(line):
                    findings.append(f"{relative}:{line_number}: {line.strip()}")

    if findings:
        print("Active legacy PostgreSQL patterns found:")
        for item in findings[:200]:
            print(item)
        if len(findings) > 200:
            print(f"... {len(findings) - 200} additional findings omitted")
        return 1

    print("No active PostgreSQL patterns found outside the documented allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
