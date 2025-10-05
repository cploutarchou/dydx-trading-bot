import logging
import sys
import threading
from typing import Optional

from constants import (
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
    if not (LOKI_ENABLED and LOKI_PUSH_URL and LOKI_USERNAME and LOKI_PASSWORD):
        return None

    placeholder_tokens = {"<your_grafana_api_token>", "changeme", ""}
    if LOKI_PASSWORD.strip().lower() in placeholder_tokens or "<" in LOKI_PASSWORD:
        logging.getLogger(__name__).warning(
            "Loki logging enabled but password appears to be a placeholder. Skipping remote handler."
        )
        return None
    if LokiHandler is None:
        logging.getLogger(__name__).warning(
            "Loki handler unavailable. Install python-logging-loki to enable remote logging."
        )
        return None

    handler_kwargs = {
        "url": LOKI_PUSH_URL,
        "auth": (LOKI_USERNAME, LOKI_PASSWORD),
        "level": level,
        "version": "1",
        "tags": LOKI_LABELS or {},
        "timeout": 10,
    }

    if LOKI_TENANT_ID:
        handler_kwargs["tenant_id"] = LOKI_TENANT_ID

    try:
        handler = LokiHandler(**handler_kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - network failures
        logging.getLogger(__name__).error(
            "Failed to initialize Loki handler: %s", exc, exc_info=True
        )
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

    sys.stdout = _LoggerStream(stdout_logger, level, fallback=sys.__stdout__)
    sys.stderr = _LoggerStream(stderr_logger, logging.ERROR, fallback=sys.__stderr__)

    root_logger.debug("Logging initialized. Loki enabled: %s", LOKI_ENABLED)