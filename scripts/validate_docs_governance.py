#!/usr/bin/env python3
"""Validate documentation governance for canonical docs.

Checks:
1) Canonical docs exist.
2) Local markdown links resolve.
3) Temporary handoff/task notes do not live outside approved archival paths.
4) Documentation governance policy file includes required checklist/rules sections.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = REPO_ROOT / "docs" / "DOCUMENTATION_GOVERNANCE.md"
ARCHIVE_DIR = REPO_ROOT / "docs" / "archive"

CANONICAL_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "IMPROVEMENTS.md",
    REPO_ROOT / "docs" / "README.md",
    REPO_ROOT / "docs" / "PLATFORM.md",
    REPO_ROOT / "docs" / "DEVELOPMENT.md",
    REPO_ROOT / "docs" / "OPERATIONS.md",
    REPO_ROOT / "docs" / "CI_CD_STRATEGY.md",
    REPO_ROOT / "frontend" / "README.md",
    REPO_ROOT / "backend" / "README.md",
    REPO_ROOT / "bot" / "README.md",
    REPO_ROOT / "config" / "README.md",
]

SCAN_GLOBS = [
    "README.md",
    "IMPROVEMENTS.md",
    "docs/**/*.md",
    "frontend/README.md",
    "backend/README.md",
    "bot/README.md",
    "config/README.md",
]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TEMP_DOC_RE = re.compile(r"(handoff|temporary|temp|tmp|task[-_]?note|working[-_]?notes)", re.IGNORECASE)


def gather_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in SCAN_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file():
                files.add(path.resolve())
    return sorted(files)


def normalize_link(raw: str) -> str:
    link = raw.strip()
    if link.startswith("<") and link.endswith(">"):
        link = link[1:-1].strip()
    return link


def is_external(link: str) -> bool:
    return link.startswith(("http://", "https://", "mailto:", "tel:"))


def resolve_local_link(source_file: Path, link: str) -> Path | None:
    target = link.split("#", 1)[0].split("?", 1)[0].strip()
    if not target:
        return None

    # Absolute filesystem paths are allowed if they exist or map into this repo.
    if target.startswith("/"):
        abs_path = Path(target)
        if abs_path.exists():
            return abs_path

        repo_relative = target.lstrip("/")
        mapped = REPO_ROOT / repo_relative
        if mapped.exists():
            return mapped.resolve()

        marker = "/dydx-trading-bot/"
        if marker in target:
            suffix = target.split(marker, 1)[1]
            mapped = REPO_ROOT / suffix
            if mapped.exists():
                return mapped.resolve()
        return mapped.resolve()

    resolved = (source_file.parent / target).resolve()
    return resolved


def validate_links(files: list[Path]) -> list[str]:
    failures: list[str] = []

    for file in files:
        text = file.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw_link = normalize_link(match.group(1))
            if not raw_link or is_external(raw_link) or raw_link.startswith("#"):
                continue

            resolved = resolve_local_link(file, raw_link)
            if resolved is None:
                continue
            if not resolved.exists():
                failures.append(f"{file.relative_to(REPO_ROOT)} -> missing link target: {raw_link}")

    return failures


def validate_temp_docs_archived() -> list[str]:
    failures: list[str] = []
    approved_prefixes = [ARCHIVE_DIR.resolve()]

    for md in REPO_ROOT.rglob("*.md"):
        rel = md.relative_to(REPO_ROOT)
        rel_posix = rel.as_posix()

        if rel_posix.startswith((".github/", "backend/.github/", "bot/.github/", "frontend/.github/", "memories/")):
            continue

        if TEMP_DOC_RE.search(md.name):
            md_resolved = md.resolve()
            if not any(str(md_resolved).startswith(str(prefix)) for prefix in approved_prefixes):
                failures.append(
                    f"{rel_posix} appears temporary/handoff-oriented and must live under docs/archive/"
                )

    return failures


def validate_policy_file() -> list[str]:
    failures: list[str] = []
    if not POLICY_FILE.exists():
        return ["docs/DOCUMENTATION_GOVERNANCE.md is missing"]

    content = POLICY_FILE.read_text(encoding="utf-8")
    required_sections = [
        "## Documentation Update Checklist",
        "## Canonical Documentation Link Validation",
        "## Archival Rules",
    ]

    for section in required_sections:
        if section not in content:
            failures.append(f"docs/DOCUMENTATION_GOVERNANCE.md missing section: {section}")

    return failures


def main() -> int:
    failures: list[str] = []

    missing = [str(path.relative_to(REPO_ROOT)) for path in CANONICAL_DOCS if not path.exists()]
    if missing:
        failures.extend([f"Missing canonical doc: {item}" for item in missing])

    files = gather_files()
    failures.extend(validate_links(files))
    failures.extend(validate_temp_docs_archived())
    failures.extend(validate_policy_file())

    if failures:
        print("[FAIL] Documentation governance validation failed:")
        for item in failures:
            print(f" - {item}")
        return 1

    print(f"[OK] Documentation governance validated across {len(files)} markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
