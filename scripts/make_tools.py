#!/usr/bin/env python3
"""Small cross-platform helpers used by the root Makefile."""

from __future__ import annotations

import re
import sys
from pathlib import Path


TARGET = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):.*?##\s+(.+?)\s*$")


def targets(makefile: Path) -> list[tuple[str, str]]:
    found: dict[str, str] = {}
    for line in makefile.read_text(encoding="utf-8").splitlines():
        match = TARGET.match(line)
        if match:
            found.setdefault(match.group(1), match.group(2))
    return sorted(found.items())


def show_help(makefile: Path) -> int:
    print("dYdX Trading Bot - Available Commands:\n")
    print("QUICK START - Choose Your Workflow")
    print("=" * 78)
    print("\nOPTION 1: Infrastructure Only (recommended for service development)")
    print("  1. make config-keygen")
    print("  2. make dev-config")
    print("  3. make dev")
    print("  4. make infra-up")
    print("  5. Run the frontend, backend, or bot locally")
    print("  6. make infra-down")
    print("\nOPTION 2: Full Stack (production-like integration testing)")
    print("  1. make config-keygen")
    print("  2. make dev-config")
    print("  3. make dev")
    print("  4. make stack-up-dev")
    print("  5. make stack-ps")
    print("  6. make stack-logs")
    print("  7. make stack-down")
    print("\nFull guide: LOCAL_SETUP_GUIDE.md\n")
    for name, description in targets(makefile):
        print(f"  {name:<30} {description}")
    print()
    return 0


def windows_check(bash_path: str) -> int:
    if sys.platform != "win32":
        print("windows-check is only needed on Windows.")
        return 0
    if bash_path and Path(bash_path).is_file():
        print(f"Recipe shell: {bash_path}")
        print("PowerShell target completion: make install-completion-powershell")
        return 0
    print("No compatible recipe shell was found.", file=sys.stderr)
    print("Install Git for Windows or MSYS2, or set WINDOWS_BASH explicitly.", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "help":
        return show_help(Path(sys.argv[2]))
    if len(sys.argv) >= 2 and sys.argv[1] == "windows-check":
        return windows_check(sys.argv[2] if len(sys.argv) >= 3 else "")
    print("Usage: make_tools.py help MAKEFILE | windows-check [BASH_PATH]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
