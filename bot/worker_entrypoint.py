"""Container entrypoint for bot background workers."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
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

