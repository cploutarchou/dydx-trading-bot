#!/usr/bin/env python3
"""Backward-compatible wrapper around the repo-owned secure config editor."""

from __future__ import annotations

import argparse
import sys

from secure_config import edit_profile


def main() -> int:
    parser = argparse.ArgumentParser(description="Edit structured config JSON files")
    parser.add_argument(
        "--environment",
        choices=("development", "production"),
        required=True,
        help="Configuration profile to edit",
    )
    args = parser.parse_args()

    try:
        edit_profile(args.environment)
        print(f"Saved encrypted {args.environment} profile.")
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
