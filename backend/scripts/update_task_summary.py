#!/usr/bin/env python3
"""Update task summary counts for backend, bot, and frontend task files."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SUMMARY_HEADER = "## Status Summary"
SUMMARY_NOTE = "- Note: update these totals whenever any [x] or [ ] task changes."
CHECKED_RE = re.compile(r"^\s*-\s*\[(x|X)\]\s+")
UNCHECKED_RE = re.compile(r"^\s*-\s*\[ \]\s+")


@dataclass
class Counts:
    completed: int
    pending: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Tasks files to update")
    return parser.parse_args()


def default_paths() -> list[Path]:
    backend_root = Path(__file__).resolve().parents[1]
    repo_root = backend_root.parent
    return [
        backend_root / "tasks.md",
        repo_root / "bot" / "tasks.md",
        repo_root / "frontend" / "tasks.md",
    ]


def count_checkboxes(lines: list[str]) -> Counts:
    completed = sum(1 for line in lines if CHECKED_RE.match(line))
    pending = sum(1 for line in lines if UNCHECKED_RE.match(line))
    return Counts(completed=completed, pending=pending)


def build_summary_block(counts: Counts) -> list[str]:
    today = date.today().isoformat()
    return [
        SUMMARY_HEADER,
        f"- Completed: `{counts.completed}`",
        f"- Pending: `{counts.pending}`",
        f"- Last updated: `{today}`",
        SUMMARY_NOTE,
        "",
    ]


def replace_summary_block(lines: list[str], summary_block: list[str]) -> list[str]:
    try:
        start = lines.index(SUMMARY_HEADER)
    except ValueError:
        insert_at = 2 if len(lines) > 1 and lines[1] == "" else 1
        return [*lines[:insert_at], *summary_block, *lines[insert_at:]]

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    return [*lines[:start], *summary_block, *lines[end:]]


def update_status_summary(path: Path) -> Counts:
    if not path.exists():
        raise FileNotFoundError(f"Missing tasks file: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Empty tasks file: {path}")

    counts = count_checkboxes(lines)
    updated_lines = replace_summary_block(lines, build_summary_block(counts))
    path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return counts


def main() -> int:
    args = parse_args()
    paths = [Path(p).resolve() for p in args.paths] if args.paths else default_paths()

    for path in paths:
        counts = update_status_summary(path)
        print(f"[OK] {path} -> Completed: {counts.completed}, Pending: {counts.pending}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
