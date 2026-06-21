#!/usr/bin/env python3
"""Scan repository files for database pattern policy violations."""

from __future__ import annotations

import re
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERN_SETS = {
    "postgres": [
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
    ],
    "mariadb": [
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bmariadb\b",
            r"\bmysql\b",
            r"mysqladmin",
            r"pymysql",
            r"go-sql-driver/mysql",
            r"\b3306\b",
            r"\bMYSQL_[A-Z0-9_]+\b",
            r"\bDB_TYPE\s*[:=]\s*[\"']?(?:mysql|mariadb)\b",
            r"\bBOT_DB_TYPE\s*[:=]\s*[\"']?(?:mysql|mariadb)\b",
        )
    ],
}
SQL_PATTERN_SETS = {
    "postgres": [
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
    ],
    "mariadb": [
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bAUTO_INCREMENT\b",
            r"\bENGINE\s*=\s*InnoDB\b",
            r"\bON\s+DUPLICATE\s+KEY\s+UPDATE\b",
        )
    ],
}
PLACEHOLDER_PATTERN = re.compile(r"\$[0-9]+\b")

ALLOWLIST_PREFIXES = {
    "postgres": (
        "backend/migrations/postgres/",
        "bot/migrations/versions/",
    ),
    "mariadb": (),
}

ALLOWLIST_FILES = {
    "postgres": {
        "docs/database-migration-audit.md",
        "docs/database-migrations.md",
        "docs/postgresql-removal-audit.md",
        "scripts/check_no_legacy_database.py",
        "backend/go.sum",
    },
    "mariadb": {
        "scripts/check_no_legacy_database.py",
    },
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


def _allowed(relative: str, mode: str) -> bool:
    return relative in ALLOWLIST_FILES[mode] or any(
        relative.startswith(prefix) for prefix in ALLOWLIST_PREFIXES[mode]
    )


def _parse_args() -> Namespace:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("postgres", "mariadb"),
        default="postgres",
        help="Pattern mode to scan for.",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Limit scan to a file or directory relative to repo root. Repeatable.",
    )
    return parser.parse_args()


def _iter_target_files(paths: list[str]) -> list[Path]:
    if not paths:
        candidates = list(ROOT.rglob("*"))
    else:
        candidates = []
        for item in paths:
            target = (ROOT / item).resolve()
            if not target.exists():
                print(f"Scan target does not exist: {item}")
                continue
            if target.is_file():
                candidates.append(target)
                continue
            candidates.extend(target.rglob("*"))
    return [path for path in candidates if path.is_file()]


def main() -> int:
    args = _parse_args()
    findings: list[str] = []
    patterns = PATTERN_SETS[args.mode]
    sql_patterns = SQL_PATTERN_SETS[args.mode]

    for path in _iter_target_files(args.path):
        relative = path.relative_to(ROOT).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if _allowed(relative, args.mode) or _is_binary(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if any(pattern.search(line) for pattern in patterns):
                findings.append(f"{relative}:{line_number}: {line.strip()}")
                continue
            if path.suffix in {".go", ".sql", ".py"}:
                if any(pattern.search(line) for pattern in sql_patterns):
                    findings.append(f"{relative}:{line_number}: {line.strip()}")
                    continue
            if (
                args.mode == "postgres"
                and path.suffix in {".go", ".sql"}
                and "$2a$" not in line
            ):
                if PLACEHOLDER_PATTERN.search(line):
                    findings.append(f"{relative}:{line_number}: {line.strip()}")

    if findings:
        print(f"Active {args.mode} patterns found:")
        for item in findings[:200]:
            print(item)
        if len(findings) > 200:
            print(f"... {len(findings) - 200} additional findings omitted")
        return 1

    if args.path:
        targets = ", ".join(args.path)
        print(f"No active {args.mode} patterns found in selected paths: {targets}")
    else:
        print(f"No active {args.mode} patterns found outside the documented allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
