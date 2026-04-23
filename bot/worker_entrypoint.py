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


class _FilteredStderr:
    """Filter noisy upstream warnings that are safe to ignore in worker logs."""

    _DROP_TOKENS = (
        "Node URL should not contain http(s)://",
    )

    def __init__(self, stderr):
        self.stderr = stderr

    def write(self, message):
        if any(token in message for token in self._DROP_TOKENS):
            return
        self.stderr.write(message)
        self.stderr.flush()

    def flush(self):
        self.stderr.flush()

    def __getattr__(self, name):
        return getattr(self.stderr, name)


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

        # Run celery in-process so our stderr filter can suppress known noisy lines.
        original_stderr = sys.stderr
        sys.stderr = _FilteredStderr(original_stderr)
        try:
            from celery.__main__ import main as celery_main

            sys.argv = argv
            return int(celery_main() or 0)
        finally:
            sys.stderr = original_stderr

    return subprocess.call([sys.executable, "main.py"])


if __name__ == "__main__":
    raise SystemExit(main())

