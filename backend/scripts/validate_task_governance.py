#!/usr/bin/env python3
"""Validate cross-service task governance consistency."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

SUMMARY_HEADER = "## Status Summary"
REQUIRED_SECTIONS = (
    "## Status Summary",
    "## Ongoing Update Protocol",
    "## Change Log",
    "## Change Log Template",
)
CHECKED_RE = re.compile(r"^\s*-\s*\[(x|X)\]\s+")
UNCHECKED_RE = re.compile(r"^\s*-\s*\[ \]\s+")
COMPLETED_RE = re.compile(r"^\s*-\s*Completed:\s*`(\d+)`\s*$")
PENDING_RE = re.compile(r"^\s*-\s*Pending:\s*`(\d+)`\s*$")
UPDATED_RE = re.compile(r"^\s*-\s*Last updated:\s*`\d{4}-\d{2}-\d{2}`\s*$")
NOTE_RE = re.compile(r"^\s*-\s*Note:\s+update these totals whenever any \[x\] or \[ \] task changes\.?\s*$")


@dataclass
class Counts:
    completed: int
    pending: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Tasks files to validate")
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


def extract_status_summary(lines: list[str]) -> Counts:
    try:
        summary_index = lines.index(SUMMARY_HEADER)
    except ValueError as exc:
        raise ValueError("Missing section: ## Status Summary") from exc

    window = lines[summary_index + 1 : summary_index + 8]
    completed_line = next((line for line in window if COMPLETED_RE.match(line)), None)
    pending_line = next((line for line in window if PENDING_RE.match(line)), None)
    updated_line = next((line for line in window if UPDATED_RE.match(line)), None)
    note_line = next((line for line in window if NOTE_RE.match(line)), None)

    if completed_line is None:
        raise ValueError("Missing or invalid Status Summary line: Completed")
    if pending_line is None:
        raise ValueError("Missing or invalid Status Summary line: Pending")
    if updated_line is None:
        raise ValueError("Missing or invalid Status Summary line: Last updated")
    if note_line is None:
        raise ValueError("Missing Status Summary note line")

    completed_match = COMPLETED_RE.match(completed_line)
    pending_match = PENDING_RE.match(pending_line)
    if completed_match is None or pending_match is None:
        raise ValueError("Status Summary counts could not be parsed")

    return Counts(
        completed=int(completed_match.group(1)),
        pending=int(pending_match.group(1)),
    )


def assert_contains(content: str, snippet: str, message: str) -> None:
    if snippet not in content:
        raise ValueError(message)


def validate_path(path: Path) -> Counts:
    if not path.exists():
        raise FileNotFoundError(f"Missing tasks file: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Empty tasks file: {path}")

    content = "\n".join(lines)
    for section in REQUIRED_SECTIONS:
        if section not in lines:
            raise ValueError(f"Missing required section '{section}' in {path}")

    summary = extract_status_summary(lines)
    actual = count_checkboxes(lines)
    if summary != actual:
        raise ValueError(
            "Status Summary mismatch in "
            f"{path}. Summary Completed/Pending={summary.completed}/{summary.pending}, "
            f"actual={actual.completed}/{actual.pending}. Run tasks-summary to fix."
        )

    posix_path = path.as_posix()
    if posix_path.endswith("/backend/tasks.md"):
        assert_contains(content, "../bot/tasks.md", "Missing ../bot/tasks.md link in backend tasks protocol")
        assert_contains(content, "../frontend/tasks.md", "Missing ../frontend/tasks.md link in backend tasks protocol")
    elif posix_path.endswith("/bot/tasks.md"):
        assert_contains(content, "../backend/tasks.md", "Missing ../backend/tasks.md link in bot tasks protocol")
        assert_contains(content, "../frontend/tasks.md", "Missing ../frontend/tasks.md link in bot tasks protocol")
        assert_contains(content, "./tasks.md", "Missing ./tasks.md link in bot tasks protocol")
    elif posix_path.endswith("/frontend/tasks.md"):
        assert_contains(content, "../backend/tasks.md", "Missing ../backend/tasks.md link in frontend tasks protocol")
        assert_contains(content, "../bot/tasks.md", "Missing ../bot/tasks.md link in frontend tasks protocol")
        assert_contains(content, "./tasks.md", "Missing ./tasks.md link in frontend tasks protocol")

    return actual


def main() -> int:
    args = parse_args()
    paths = [Path(p).resolve() for p in args.paths] if args.paths else default_paths()

    for path in paths:
        counts = validate_path(path)
        print(f"[OK] {path} governance validated (Completed={counts.completed}, Pending={counts.pending})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
