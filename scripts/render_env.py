#!/usr/bin/env python3
"""Compatibility helper to render a flat .env from the repo-owned encrypted config."""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

from secure_config import ROOT, load_json, normalize_environment_name, resolve_profile_file


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


def render_env_text(environment: str, profile_path: Path, config: dict[str, Any]) -> str:
    lines = [
        f"# Generated for {environment}",
        f"# Source profile: {profile_path.relative_to(ROOT)}",
        "# Edit the encrypted profile in config/profiles/ instead of editing this file directly.",
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
    parser = argparse.ArgumentParser(description="Render .env from a structured config profile")
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
        "--config-file",
        default=None,
        help="Optional explicit config JSON or encrypted config file",
    )
    args = parser.parse_args()

    try:
        environment = normalize_environment_name(args.environment)
        profile_path = resolve_profile_file(environment, args.config_file)
        config = load_json(profile_path)
        output_text = render_env_text(environment, profile_path, config)
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
