#!/usr/bin/env python3
"""Render repo-root run.json from the encrypted monorepo config profile."""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

from secure_config import (
    ROOT,
    decrypt_to_path,
    normalize_environment_name,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render root run.json from a structured config profile")
    parser.add_argument(
        "--environment",
        choices=("development", "production"),
        default=normalize_environment_name(
            os.getenv("APP_CONFIG_ENV")
            or os.getenv("CONFIG_ENV")
            or os.getenv("ENVIRONMENT")
            or os.getenv("APP_ENV")
            or "development"
        ),
        help="Environment profile to decrypt",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "run.json"),
        help="Output file path",
    )
    parser.add_argument(
        "--config-file",
        default=None,
        help="Optional explicit encrypted config profile",
    )
    args = parser.parse_args()

    try:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path = decrypt_to_path(
            args.environment,
            output_path,
            explicit_profile=args.config_file,
        )
        try:
            output_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        print(f"Rendered {output_path} from {profile_path}")
        return 0
    except Exception as exc:
        print(f"Failed to render run.json: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
