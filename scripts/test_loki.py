#!/usr/bin/env python3
"""Send test log records through the DB/env-backed runtime logging config."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOT_ROOT = REPO_ROOT / "bot"
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from src.shared.env_loader import load_repo_env  # noqa: E402


def test_loki_connection(environment: str = "development") -> None:
    os.environ["ENVIRONMENT"] = environment
    os.environ["APP_CONFIG_ENV"] = environment
    load_repo_env(str(BOT_ROOT / "src" / "main_instance.py"))

    from src.shared.logging_setup import setup_logging

    print(f"\nTesting Loki connection with environment: {environment}")
    print("=" * 50)

    setup_logging()
    logger = logging.getLogger("test_loki")

    logger.debug("DEBUG: Loki connection debug test")
    logger.info("INFO: Loki connection info test")
    logger.warning("WARNING: Loki connection warning test")
    logger.error("ERROR: Loki connection error test")
    logger.info(
        "Trading bot Loki context test",
        extra={"market": "BTC-USD", "action": "test", "environment": environment},
    )
    print("Test logs emitted. Check Loki for delivery if LOKI_ENABLED=true.")


if __name__ == "__main__":
    selected_environment = sys.argv[1] if len(sys.argv) > 1 else "development"
    if selected_environment not in {"development", "dev", "production", "prod"}:
        print("Usage: python test_loki.py [development|production]")
        raise SystemExit(1)

    test_loki_connection(selected_environment)
