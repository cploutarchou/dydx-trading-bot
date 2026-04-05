#!/usr/bin/env python3
"""Open structured config files in an editor and re-render the shared .env."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
ENVIRONMENTS_DIR = CONFIG_DIR / "environments"
SECRETS_DIR = CONFIG_DIR / "secrets"
RENDER_SCRIPT = ROOT / "scripts" / "render_env.py"


def resolve_editor() -> list[str]:
    for env_name in ("CODE_EDITOR", "VISUAL", "EDITOR"):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return shlex.split(raw)

    if shutil.which("code"):
        return ["code", "--wait"]
    if shutil.which("nano"):
        return ["nano"]
    if shutil.which("vim"):
        return ["vim"]

    raise RuntimeError(
        "No editor found. Set CODE_EDITOR, VISUAL, or EDITOR before running this command."
    )


def ensure_plain_secret_file(environment: str) -> Path:
    plain_secret = SECRETS_DIR / f"{environment}.secrets.json"
    if plain_secret.exists():
        return plain_secret

    example_secret = SECRETS_DIR / f"{environment}.secrets.example.json"
    if not example_secret.exists():
        raise RuntimeError(f"Missing secrets template: {example_secret}")

    plain_secret.write_text(example_secret.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Created {plain_secret.relative_to(ROOT)} from the example template.")
    return plain_secret


def run_command(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}")


def edit_with_editor(editor: list[str], *paths: Path) -> None:
    command = [*editor, *[str(path) for path in paths]]
    run_command(command)


def edit_secret_with_sops(secret_path: Path) -> None:
    if shutil.which("sops") is None:
        raise RuntimeError(
            f"SOPS is required to edit {secret_path.name}. Run `make install-sops` first."
        )
    run_command(["sops", str(secret_path)])


def render_env(environment: str) -> None:
    run_command(
        [
            sys.executable,
            str(RENDER_SCRIPT),
            "--environment",
            environment,
            "--output",
            str(ROOT / ".env"),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Edit structured config and re-render .env")
    parser.add_argument(
        "--environment",
        choices=("development", "production"),
        required=True,
        help="Configuration profile to edit",
    )
    args = parser.parse_args()

    profile_path = ENVIRONMENTS_DIR / f"{args.environment}.env.json"
    if not profile_path.exists():
        print(f"Missing environment profile: {profile_path}", file=sys.stderr)
        return 1

    encrypted_secret = SECRETS_DIR / f"{args.environment}.secrets.sops.json"
    editor = resolve_editor()

    try:
        if encrypted_secret.exists():
            print(
                f"Opening {profile_path.relative_to(ROOT)} in your editor, then editing "
                f"{encrypted_secret.relative_to(ROOT)} with SOPS."
            )
            edit_with_editor(editor, profile_path)
            edit_secret_with_sops(encrypted_secret)
        else:
            plain_secret = ensure_plain_secret_file(args.environment)
            print(
                f"Opening {profile_path.relative_to(ROOT)} and "
                f"{plain_secret.relative_to(ROOT)} in your editor."
            )
            edit_with_editor(editor, profile_path, plain_secret)

        render_env(args.environment)
        print(f"Rendered {Path('.env').resolve().relative_to(ROOT)} for {args.environment}.")
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
