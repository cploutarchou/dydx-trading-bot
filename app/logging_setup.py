import logging
import sys
import threading
from typing import Optional

from constants import (
    ENVIRONMENT,
    LOG_LEVEL,
    LOKI_ENABLED,
    LOKI_LABELS,
    LOKI_PASSWORD,
    LOKI_PUSH_URL,
    LOKI_TENANT_ID,
    LOKI_USERNAME,
)

try:
    from logging_loki import LokiHandler  # type: ignore
except ImportError:  # pragma: no cover - dependency enforced via requirements
    LokiHandler = None  # type: ignore


class _LoggerStream:
    """Redirect writes to a logger at the configured level."""

    def __init__(
        self,
        logger: logging.Logger,
        level: int,
        fallback: Optional[object] = None,
    ) -> None:
        self._logger = logger
        self._level = level
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        self.encoding = "utf-8"
        self._fallback = fallback

    def write(self, message: str) -> None:
        if not message:
            return
        with self._lock:
            self._buffer.append(message)
            if "\n" in message:
                self.flush()

    def flush(self) -> None:
        with self._lock:
            if not self._buffer:
                return
            text = "".join(self._buffer)
            self._buffer.clear()
            for line in text.splitlines():
                trimmed = line.strip()
                if trimmed:
                    self._logger.log(self._level, trimmed)
        fallback_flush = getattr(self._fallback, "flush", None)
        if callable(fallback_flush):
            try:
                fallback_flush()
            except Exception:  # pragma: no cover - best-effort fallback
                pass

    def isatty(self) -> bool:  # pragma: no cover - compatibility shim
        return False

    def fileno(self) -> int:  # pragma: no cover - provide basic compatibility
        fallback_fileno = getattr(self._fallback, "fileno", None)
        if callable(fallback_fileno):
            result = fallback_fileno()
            if isinstance(result, int):
                return result
        raise OSError("LoggerStream does not have a file descriptor")


def _initialize_console_handler(level: int) -> logging.Handler:
    console_handler = logging.StreamHandler(sys.__stdout__)
    console_handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    return console_handler


def _initialize_loki_handler(level: int) -> Optional[logging.Handler]:
    if not (LOKI_ENABLED and LOKI_PUSH_URL):
        return None

    if LokiHandler is None:
        print("Loki handler unavailable. Install python-logging-loki to enable remote logging.")
        return None

    # Check environment to determine authentication requirements
    is_dev_environment = ENVIRONMENT in ("development", "dev")
    
    handler_kwargs = {
        "url": LOKI_PUSH_URL,
        "tags": LOKI_LABELS or {},
    }

    # Only add authentication for production environments
    if not is_dev_environment:
        if not (LOKI_USERNAME and LOKI_PASSWORD):
            print("Production environment detected but Loki credentials missing. Skipping remote handler.")
            return None
            
        placeholder_tokens = {"<your_grafana_api_token>", "changeme", ""}
        if LOKI_PASSWORD.strip().lower() in placeholder_tokens or "<" in LOKI_PASSWORD:
            print("Loki logging enabled but password appears to be a placeholder. Skipping remote handler.")
            return None
            
        handler_kwargs["auth"] = (LOKI_USERNAME, LOKI_PASSWORD)
        print("Production environment: Using authenticated Loki connection")
    else:
        print("Development environment: Using unauthenticated Loki connection")

    if LOKI_TENANT_ID:
        handler_kwargs["tenant_id"] = LOKI_TENANT_ID

    try:
        handler = LokiHandler(**handler_kwargs)  # type: ignore[arg-type]
        handler.setLevel(level)
        
        # Prevent recursion by filtering out urllib3 and requests loggers from going to Loki
        class NoRecursionFilter(logging.Filter):
            def filter(self, record):
                # Prevent urllib3, requests, and logging_loki logs from being sent to Loki
                return not any(record.name.startswith(prefix) for prefix in [
                    'urllib3', 'requests', 'logging_loki', 'http.client'
                ])
        
        handler.addFilter(NoRecursionFilter())
        print(f"Loki handler initialized for {ENVIRONMENT} environment")
    except Exception as exc:  # pragma: no cover - network failures
        print(f"Failed to initialize Loki handler: {exc}")
        return None
    return handler


def setup_logging() -> None:
    """Configure global logging and mirror stdout/stderr to the logger."""

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any pre-existing handlers to avoid duplicate logs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = _initialize_console_handler(level)
    root_logger.addHandler(console_handler)

    loki_handler = _initialize_loki_handler(level)
    if loki_handler is not None:
        root_logger.addHandler(loki_handler)

    # Mirror prints to logging so existing print statements are captured
    stdout_logger = logging.getLogger("stdout")
    stdout_logger.setLevel(level)
    stderr_logger = logging.getLogger("stderr")
    stderr_logger.setLevel(logging.ERROR)

    # NOTE: Commented out stdout/stderr redirection to avoid KeyboardInterrupt issues
    # If you need print() statements captured, use logger.info() instead of print()
    # sys.stdout = _LoggerStream(stdout_logger, level, fallback=sys.__stdout__)
    # sys.stderr = _LoggerStream(stderr_logger, logging.ERROR, fallback=sys.__stderr__)

    root_logger.debug("Logging initialized. Loki enabled: %s", LOKI_ENABLED)
