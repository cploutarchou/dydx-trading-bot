import importlib.util
import logging
import sys
import time
from typing import Any, Dict, Mapping

from loguru import logger

from src.constants import (
    ENVIRONMENT,
    LOG_LEVEL,
    LOKI_ENABLED,
    LOKI_LABELS,
    LOKI_PASSWORD,
    LOKI_PUSH_URL,
    LOKI_USERNAME,
)

REQUESTS_AVAILABLE = importlib.util.find_spec("requests") is not None
_LOGGING_CONFIGURED = False
_LOKI_DYNAMIC_LABEL_FIELDS = (
    "market",
    "resolution",
    "timeframe",
    "fetch_type",
)


class InterceptHandler(logging.Handler):
    """Route standard logging records through Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level_name = logger.level(record.levelname).name
        except ValueError:
            level_name = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level_name,
            record.getMessage(),
        )


def _log_level() -> str:
    return str(LOG_LEVEL or "INFO").upper()


def _is_development() -> bool:
    return str(ENVIRONMENT or "development").lower() == "development"


def _effective_log_level() -> str:
    configured = _log_level()
    if _is_development() and configured not in {"TRACE", "DEBUG"}:
        return "DEBUG"
    return configured


def _suppress_noisy_libraries() -> None:
    logging.getLogger("dydx_v4_client").setLevel(logging.WARNING)
    if _effective_log_level() == "DEBUG":
        for name in (
            "urllib3",
            "urllib3.connectionpool",
            "requests",
            "httpx",
            "httpcore",
        ):
            logging.getLogger(name).setLevel(logging.WARNING)


def _configure_standard_logging_bridge(level: int) -> None:
    intercept = InterceptHandler()
    logging.root.handlers = [intercept]
    logging.root.setLevel(level)

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "sqlalchemy",
        "alembic",
    ):
        std_logger = logging.getLogger(name)
        std_logger.handlers = [intercept]
        std_logger.propagate = False


def _configure_console_sink(level: str) -> None:
    stream = sys.__stdout__ or sys.stdout
    is_tty = bool(getattr(stream, "isatty", lambda: False)())
    is_colored_local = _is_development() and is_tty
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>module={name}</cyan> | "
        "<blue>func={function}</blue> | "
        "<magenta>line={line}</magenta> | "
        "<yellow>process={process.id}</yellow> | "
        "<dim>trace_id={extra[trace_id]}</dim> | "
        "{message}"
        if is_colored_local
        else "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | module={name} | func={function} | line={line} | process={process.id} | trace_id={extra[trace_id]} | {message}"
    )

    logger.remove()

    def _console_sink(message: Any) -> None:
        stream.write(str(message))

    logger.add(
        _console_sink,
        level=level,
        backtrace=False,
        diagnose=False,
        enqueue=True,
        colorize=is_colored_local,
        format=console_format,
    )


def send_to_loki_directly(
    message: str,
    level: str,
    labels: Dict[str, str],
    url: str,
    username: str,
    password: str,
) -> bool:
    """Send one record to Loki via HTTP API."""

    if not REQUESTS_AVAILABLE:
        return False

    timestamp = str(int(time.time() * 1_000_000_000))
    stream_labels = dict(labels)
    stream_labels["level"] = level.lower()
    payload = {
        "streams": [
            {
                "stream": stream_labels,
                "values": [[timestamp, message]],
            }
        ]
    }

    try:
        import requests

        response = requests.post(
            url,
            json=payload,
            auth=(username, password) if username or password else None,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return response.status_code in {200, 204}
    except Exception:
        return False


def _configure_loki_sink(level: str) -> None:
    if not LOKI_ENABLED or not LOKI_PUSH_URL:
        logger.info("Loki logging disabled")
        return

    is_production = ENVIRONMENT in ("production", "prod")
    if is_production and not (LOKI_USERNAME and LOKI_PASSWORD):
        logger.warning("Loki credentials missing in production; skipping Loki sink")
        return

    labels = LOKI_LABELS or {}

    def _build_stream_labels(extra: Mapping[str, Any]) -> Dict[str, str]:
        stream_labels = dict(labels)
        for field in _LOKI_DYNAMIC_LABEL_FIELDS:
            value = extra.get(field)
            if value is None:
                continue
            value_str = str(value).strip()
            if value_str:
                stream_labels[field] = value_str
        return stream_labels

    def _loki_sink(message: Any) -> None:
        record = message.record
        text = str(message).rstrip("\n")
        stream_labels = _build_stream_labels(record.get("extra", {}))
        ok = send_to_loki_directly(
            message=text,
            level=record["level"].name,
            labels=stream_labels,
            url=LOKI_PUSH_URL,
            username=LOKI_USERNAME,
            password=LOKI_PASSWORD,
        )
        if not ok and _log_level() == "DEBUG":
            logger.debug("Loki sink delivery failed")

    logger.add(_loki_sink, level=level, enqueue=True, backtrace=False, diagnose=False)
    logger.info("Loki sink configured")


def setup_logging() -> None:
    """Configure Loguru and bridge stdlib logging to it."""

    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    # Ensure trace_id is always present in extra so format strings never raise KeyError
    logger.configure(extra={"trace_id": ""})

    level_name = _effective_log_level()
    level = getattr(logging, level_name, logging.INFO)

    _configure_console_sink(level_name)
    _configure_standard_logging_bridge(level)
    _suppress_noisy_libraries()
    _configure_loki_sink(level_name)

    if _is_development():
        logger.debug("Development mode verbose logging enabled")
    logger.info("Logging initialized with Loguru bridge")
    _LOGGING_CONFIGURED = True
