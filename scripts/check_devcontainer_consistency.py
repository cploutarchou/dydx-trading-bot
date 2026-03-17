#!/usr/bin/env python3
"""Validate service devcontainer consistency for monorepo policy enforcement."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIRS = ("bot", "frontend", "backend")
ROOT_DOCS_TO_SCAN = (
    "README.md",
    ".github/copilot-instructions.md",
)


def _extract_devcontainer_script_paths(command: object) -> List[str]:
    """Extract .devcontainer/* script paths from devcontainer lifecycle commands."""
    if command is None:
        return []

    if isinstance(command, list):
        blob = " ".join(str(item) for item in command)
    else:
        blob = str(command)

    return re.findall(r"(\.devcontainer/[\w./-]+)", blob)


def _validate_devcontainer_json(service_root: Path, errors: List[str]) -> None:
    devcontainer_dir = service_root / ".devcontainer"
    devcontainer_json = devcontainer_dir / "devcontainer.json"

    if not devcontainer_json.exists():
        errors.append(f"Missing devcontainer config: {devcontainer_json}")
        return

    try:
        data = json.loads(devcontainer_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {devcontainer_json}: {exc}")
        return

    build = data.get("build")
    if isinstance(build, dict):
        dockerfile = build.get("dockerfile")
        if dockerfile:
            dockerfile_path = devcontainer_dir / dockerfile
            if not dockerfile_path.exists():
                errors.append(
                    f"Missing build.dockerfile for {service_root.name}: {dockerfile_path}"
                )

        compose_file = build.get("dockerComposeFile")
        if compose_file:
            compose_path = devcontainer_dir / compose_file
            if not compose_path.exists():
                errors.append(
                    f"Missing build.dockerComposeFile for {service_root.name}: {compose_path}"
                )

    compose_file = data.get("dockerComposeFile")
    if compose_file:
        compose_paths: Iterable[str]
        if isinstance(compose_file, list):
            compose_paths = [str(item) for item in compose_file]
        else:
            compose_paths = [str(compose_file)]

        for relative_path in compose_paths:
            compose_path = devcontainer_dir / relative_path
            if not compose_path.exists():
                errors.append(
                    f"Missing dockerComposeFile for {service_root.name}: {compose_path}"
                )

    lifecycle_keys = (
        "initializeCommand",
        "onCreateCommand",
        "updateContentCommand",
        "postCreateCommand",
        "postStartCommand",
        "postAttachCommand",
    )
    for key in lifecycle_keys:
        for relative_path in _extract_devcontainer_script_paths(data.get(key)):
            script_path = service_root / relative_path
            if not script_path.exists():
                errors.append(
                    f"Missing script referenced by {service_root.name} {key}: {script_path}"
                )


def _validate_root_doc_refs(errors: List[str]) -> None:
    disallowed_patterns = (
        re.compile(r"\broot\s+`?\.devcontainer/?`?", re.IGNORECASE),
        re.compile(r"optional:\s*root\s+`?\.devcontainer/?`?", re.IGNORECASE),
    )

    for relative_doc in ROOT_DOCS_TO_SCAN:
        doc_path = ROOT / relative_doc
        if not doc_path.exists():
            continue
        content = doc_path.read_text(encoding="utf-8")
        for pattern in disallowed_patterns:
            if pattern.search(content):
                errors.append(
                    f"Disallowed root devcontainer reference in {relative_doc}: {pattern.pattern}"
                )


def main() -> int:
    errors: List[str] = []

    root_devcontainer = ROOT / ".devcontainer"
    if root_devcontainer.exists():
        errors.append(
            "Root .devcontainer directory exists but policy requires service-only devcontainers"
        )

    for service in SERVICE_DIRS:
        _validate_devcontainer_json(ROOT / service, errors)

    _validate_root_doc_refs(errors)

    if errors:
        print("❌ Devcontainer consistency checks failed:")
        for idx, err in enumerate(errors, start=1):
            print(f"  {idx}. {err}")
        return 1

    print("✅ Devcontainer consistency checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
