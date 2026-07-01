"""Container entrypoint for bot background workers."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import List, Optional, Tuple

from src.shared.env_loader import load_repo_env

# Mandatory: Load structured config BEFORE importing project modules.
load_repo_env(__file__)

from src.shared.env_loader import load_file_env_values

DEFAULT_CELERY_QUEUES = "backtests,default,high_priority,scheduled"


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


def _parse_autoscale(raw_value: str) -> Optional[Tuple[int, int]]:
    value = (raw_value or "").strip()
    if not value:
        return None

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        return None

    try:
        maximum = int(parts[0])
        minimum = int(parts[1])
    except ValueError:
        return None

    if minimum < 0 or maximum < 1 or minimum > maximum:
        return None
    return maximum, minimum


def _celery_pool_args() -> List[str]:
    autoscale_raw = os.getenv("CELERY_AUTOSCALE", "")
    parsed_autoscale = _parse_autoscale(autoscale_raw)
    if autoscale_raw.strip() and parsed_autoscale is None:
        # Fail-safe: ignore malformed autoscale and keep worker booting with fixed pool size.
        sys.stderr.write(
            "[worker_entrypoint] Ignoring invalid CELERY_AUTOSCALE; expected 'max,min' with 0<=min<=max.\n"
        )
        sys.stderr.flush()

    if parsed_autoscale is not None:
        maximum, minimum = parsed_autoscale
        return ["--autoscale", f"{maximum},{minimum}"]

    return ["--concurrency", os.getenv("CELERY_CONCURRENCY", "10")]


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


def _run_nats_worker() -> int:
    """Run NATS JetStream consumer worker for Phase 4."""
    import asyncio
    import logging
    import signal
    
    from src.shared.logging_setup import setup_logging
    from src.infrastructure.workers.nats_backtest_consumer import (
        init_nats_backtest_consumers,
        shutdown_nats_backtest_consumers,
    )
    
    # Initialize Loguru bridge early so imports/logic are captured.
    setup_logging()
    
    load_file_env_values(override=True)
    
    # Set up standard logging
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting NATS JetStream consumer worker...")
    
    # Handle shutdown signals
    shutdown_event = asyncio.Event()
    
    def handle_shutdown(signame, _):
        logger.info(f"Received signal {signame}, shutting down...")
        shutdown_event.set()
    
    # Set up signal handlers
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    
    async def run():
        try:
            # Initialize NATS consumers
            handler = await init_nats_backtest_consumers()
            if not handler:
                logger.error("Failed to initialize NATS consumers")
                return 1
            
            logger.info("NATS backtest consumer started successfully")
            
            # Wait for shutdown signal
            await shutdown_event.wait()
            
            # Shutdown NATS consumers
            await shutdown_nats_backtest_consumers()
            
            return 0
            
        except asyncio.CancelledError:
            logger.info("NATS worker cancelled")
            await shutdown_nats_backtest_consumers()
            return 0
        except Exception as e:
            logger.error(f"NATS worker error: {e}")
            await shutdown_nats_backtest_consumers()
            return 1
    
    # Set up signal handlers
    try:
        signal.signal(signal.SIGINT, lambda s, f: handle_shutdown("SIGINT", f))
        signal.signal(signal.SIGTERM, lambda s, f: handle_shutdown("SIGTERM", f))
    except (ValueError, OSError) as e:
        logger.warning(f"Could not set signal handlers: {e}")
    
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        logger.error(f"NATS worker failed: {e}")
        return 1


def main() -> int:
    from src.shared.logging_setup import setup_logging

    # Initialize Loguru bridge early so imports/logic are captured.
    setup_logging()

    load_file_env_values(override=True)

    # Harden runtime env for libraries that consume node URL variables directly.
    _sanitize_node_url_env("DYDX_TESTNET_NODE_URL")
    _sanitize_node_url_env("DYDX_MAINNET_NODE_URL")

    mode = os.getenv("WORKER_MODE", "bot").strip().lower()
    
    # Phase 4: NATS JetStream consumer mode
    if mode in {"nats", "nats-worker", "nats-backtest", "backtest-nats"}:
        return _run_nats_worker()
    
    if mode in {"celery", "celery-backtest", "backtest-celery"}:
        argv = [
            "celery",
            "-A",
            "src.infrastructure.workers.celery_app:celery_app",
            "worker",
            "--loglevel",
            os.getenv("CELERY_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")).lower(),
            "--queues",
            os.getenv("CELERY_QUEUES", DEFAULT_CELERY_QUEUES),
            "-E",
        ]
        argv.extend(_celery_pool_args())

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
