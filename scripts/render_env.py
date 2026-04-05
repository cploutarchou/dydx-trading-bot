#!/usr/bin/env python3
"""Render the shared repo-root .env from structured JSON config sources."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENTS_DIR = ROOT / "config" / "environments"
SECRETS_DIR = ROOT / "config" / "secrets"


def load_json(path: Path) -> dict[str, Any]:
    if path.name.endswith(".sops.json"):
        if shutil.which("sops") is None:
            raise RuntimeError(
                f"sops is required to decrypt {path}, but it is not installed"
            )
        result = subprocess.run(
            ["sops", "-d", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout, object_pairs_hook=OrderedDict)

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = OrderedDict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_secret_file(environment: str, explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).resolve()
        return candidate if candidate.exists() else None

    candidates = [
        SECRETS_DIR / f"{environment}.secrets.sops.json",
        SECRETS_DIR / f"{environment}.secrets.json",
        SECRETS_DIR / f"{environment}.secrets.example.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))


def collect_env_entries(tree: dict[str, Any]) -> OrderedDict[str, list[tuple[str, str]]]:
    sections: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()

    def walk(section: str, node: Any) -> None:
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if isinstance(value, dict):
                walk(section, value)
            else:
                sections.setdefault(section, []).append((key, normalize_scalar(value)))

    for section, values in tree.items():
        if section == "metadata" or not isinstance(values, dict):
            continue
        walk(section, values)

    return sections


def render_env_text(
    environment: str,
    profile_path: Path,
    secret_path: Path | None,
    config: dict[str, Any],
) -> str:
    lines = [
        f"# Generated for {environment}",
        f"# Base profile: {profile_path.relative_to(ROOT)}",
        f"# Secrets layer: {secret_path.relative_to(ROOT) if secret_path else 'none'}",
        "# Edit the JSON sources in config/ instead of editing this file directly.",
        "",
    ]

    for section, entries in collect_env_entries(config).items():
        title = section.replace("_", " ").title()
        lines.append(f"# {title}")
        for key, value in entries:
            lines.append(f"{key}={value}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render root .env from JSON profiles")
    parser.add_argument(
        "--environment",
        choices=["development", "production"],
        default="development",
        help="Environment profile to render",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / ".env"),
        help="Output file path",
    )
    parser.add_argument(
        "--secrets-file",
        default=None,
        help="Optional explicit secrets JSON or SOPS JSON file",
    )
    args = parser.parse_args()

    profile_path = ENVIRONMENTS_DIR / f"{args.environment}.env.json"
    if not profile_path.exists():
        print(f"Missing environment profile: {profile_path}", file=sys.stderr)
        return 1

    try:
        config = load_json(profile_path)
        secret_path = resolve_secret_file(args.environment, args.secrets_file)
        if secret_path is not None:
            config = deep_merge(config, load_json(secret_path))
        output_text = render_env_text(args.environment, profile_path, secret_path, config)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to render env: {exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")
    print(f"Rendered {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
