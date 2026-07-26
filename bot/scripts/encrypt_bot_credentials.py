#!/usr/bin/env python3
"""Encrypt (or decrypt) credential blocks stored in ``bot_instances.config``.

This is the one-time admin backfill for the at-rest credential-encryption
feature. After deploying the encryption-aware code and provisioning a key
(``BOT_CREDENTIALS_ENCRYPTION_KEY`` / ``BOT_CREDENTIALS_ENCRYPTION_KEY_FILE``),
run this script to seal existing plaintext rows:

    python scripts/encrypt_bot_credentials.py            # encrypt all unsealed rows
    python scripts/encrypt_bot_credentials.py --dry-run  # preview only

The script is **idempotent**: rows that already carry sealed envelopes are
left untouched, so it is safe to re-run.

Rollback
--------
Before reverting to a pre-encryption code revision, restore plaintext rows with:

    python scripts/encrypt_bot_credentials.py --decrypt

This opens the sealed envelopes (requires the same key) and writes plaintext
``credentials``/``telegram`` blocks back, so the old code can read them again.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src.shared.env_loader import load_repo_env

load_repo_env(__file__)

from loguru import logger

from src.infrastructure.database import db
from src.infrastructure.persistence.repository import UnitOfWork
from src.shared.credentials_cipher import (
    has_sealed_secrets,
    is_encryption_available,
    open_config_secrets,
    seal_config_secrets,
)


def _row_summary(instance_id: str, config: Dict[str, Any]) -> str:
    sealed = has_sealed_secrets(config)
    has_plain_credentials = isinstance(config.get("credentials"), dict) and bool(
        config.get("credentials")
    )
    state = "sealed" if sealed else ("plaintext" if has_plain_credentials else "empty")
    return f"{instance_id} ({state})"


def _process(mode: str, dry_run: bool, instance_filter: Optional[str]) -> Dict[str, int]:
    counts = {"scanned": 0, "changed": 0, "skipped": 0, "errors": 0}

    session = db.get_session()
    try:
        uow = UnitOfWork(session)
        bots = uow.bots.get_all()
        for bot in bots:
            counts["scanned"] += 1
            instance_id = getattr(bot, "instance_id", "<unknown>")
            if instance_filter and instance_id != instance_filter:
                continue

            config = dict(getattr(bot, "config", None) or {})

            if mode == "encrypt":
                if has_sealed_secrets(config):
                    counts["skipped"] += 1
                    logger.info("SKIP (already sealed): {}", _row_summary(instance_id, config))
                    continue
                if not (
                        isinstance(config.get("credentials"), dict) and config.get("credentials")
                ):
                    counts["skipped"] += 1
                    logger.info(
                        "SKIP (no plaintext credentials): {}",
                        _row_summary(instance_id, config),
                    )
                    continue
                new_config = seal_config_secrets(config)
            else:  # decrypt
                if not has_sealed_secrets(config):
                    counts["skipped"] += 1
                    logger.info(
                        "SKIP (not sealed): {}", _row_summary(instance_id, config)
                    )
                    continue
                new_config = open_config_secrets(config)

            logger.info(
                "{} {}: {}",
                "WOULD UPDATE" if dry_run else "UPDATE",
                mode,
                _row_summary(instance_id, config),
            )
            if dry_run:
                counts["changed"] += 1
                continue

            try:
                bot.config = new_config
                session.commit()
                counts["changed"] += 1
            except Exception as exc:  # noqa: BLE001 — operator-facing tool
                logger.error("FAILED {} {}: {}", mode, instance_id, exc)
                session.rollback()
                counts["errors"] += 1
    finally:
        session.close()

    return counts


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--decrypt",
        action="store_true",
        help="Restore plaintext credentials (rollback before reverting code).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    parser.add_argument(
        "--instance-id",
        default=None,
        help="Only process a single bot instance (for testing).",
    )
    args = parser.parse_args(argv)

    mode = "decrypt" if args.decrypt else "encrypt"

    if not is_encryption_available():
        logger.error(
            "No credential encryption key is provisioned. Set "
            "BOT_CREDENTIALS_ENCRYPTION_KEY / BOT_CREDENTIALS_ENCRYPTION_KEY_FILE "
            "before running this script (mode={}).",
            mode,
        )
        return 2

    logger.info(
        "Credential backfill starting (mode={}, dry_run={}, filter={})",
        mode,
        args.dry_run,
        args.instance_id or "all",
    )

    counts = _process(mode, args.dry_run, args.instance_id)

    logger.info(
        "Credential backfill complete: scanned={scanned} changed={changed} "
        "skipped={skipped} errors={errors}",
        **counts,
    )
    return 0 if counts["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
