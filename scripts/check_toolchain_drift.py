#!/usr/bin/env python3
"""Fail when the toolchain CI tests with differs from the one images ship with.

Compares:
- Go: the `go` directive in backend/go.mod (CI reads it via go-version-file)
  with the `golang:<major.minor>` builder tag in the backend Dockerfiles.
- Node: `node-version` in the frontend CI job with the `node:<major>` builder
  tag in docker/Dockerfile.frontend.

A test suite that is green on one compiler or runtime says nothing about a
binary built by another, so the two must move together.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GO_MOD = ROOT / "backend" / "go.mod"
GO_DOCKERFILES = [
    ROOT / "docker" / "Dockerfile.backend",
    ROOT / "docker" / "Dockerfile.backend-migrator",
]
NODE_DOCKERFILE = ROOT / "docker" / "Dockerfile.frontend"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "bot-quality.yml"


def _search(pattern: str, path: Path) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    if match is None:
        raise SystemExit(f"toolchain-drift: pattern {pattern!r} not found in {path}")
    return match.group(1)


def main() -> int:
    problems: list[str] = []

    go_tested = _search(r"^go (\d+\.\d+)", GO_MOD)
    for dockerfile in GO_DOCKERFILES:
        go_shipped = _search(r"^FROM golang:(\d+\.\d+)", dockerfile)
        if go_shipped != go_tested:
            problems.append(
                f"Go: {GO_MOD.relative_to(ROOT)} tests with {go_tested}, "
                f"{dockerfile.relative_to(ROOT)} builds with {go_shipped}"
            )

    node_tested = _search(r"node-version:\s*\"?(\d+)", CI_WORKFLOW)
    node_shipped = _search(r"^FROM node:(\d+)", NODE_DOCKERFILE)
    if node_shipped != node_tested:
        problems.append(
            f"Node: {CI_WORKFLOW.relative_to(ROOT)} tests with {node_tested}, "
            f"{NODE_DOCKERFILE.relative_to(ROOT)} builds with {node_shipped}"
        )

    if problems:
        print("toolchain-drift: tested and shipped toolchains differ:")
        for problem in problems:
            print(f"  - {problem}")
        print("Move both in the same change (go.mod / CI node-version / Dockerfile FROM).")
        return 1

    print(f"toolchain-drift: OK (Go {go_tested}, Node {node_tested})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
