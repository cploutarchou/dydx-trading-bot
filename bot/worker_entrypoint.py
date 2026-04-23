"""Container entrypoint for bot background workers."""

from __future__ import annotations

import os
import subprocess
import sys


def _sanitize_node_url_env(var_name: str) -> None:
    raw = os.getenv(var_name, "")
    if not raw:
        return

    value = raw.strip()
    lowered = value.lower()
    if lowered.startswith("http://"):
        os.environ[var_name] = value[len("http://") :]
        return
    if lowered.startswith("https://"):
        os.environ[var_name] = value[len("https://") :]
        return


def main() -> int:
    # Harden runtime env for libraries that consume node URL variables directly.
    _sanitize_node_url_env("DYDX_TESTNET_NODE_URL")
    _sanitize_node_url_env("DYDX_MAINNET_NODE_URL")

    mode = os.getenv("WORKER_MODE", "bot").strip().lower()
    if mode in {"celery", "celery-backtest", "backtest-celery"}:
        argv = [
            "celery",
            "-A",
            "src.infrastructure.workers.celery_app:celery_app",
            "worker",
            "--loglevel",
            os.getenv("CELERY_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")).lower(),
            "--queues",
            os.getenv("CELERY_QUEUES", "celery"),
            "--concurrency",
            os.getenv("CELERY_CONCURRENCY", "1"),
        ]
        return subprocess.call(argv)

    return subprocess.call([sys.executable, "main.py"])


if __name__ == "__main__":
    raise SystemExit(main())

