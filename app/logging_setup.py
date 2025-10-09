import logging
import sys
import threading
import time
from typing import Dict, Optional

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

try:
    import importlib.util
    REQUESTS_AVAILABLE = importlib.util.find_spec("requests") is not None
except ImportError:
    REQUESTS_AVAILABLE = False


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


def send_to_loki_directly(
    message: str,
    level: str,
    labels: Dict[str, str],
    url: str,
    username: str,
    password: str,
) -> bool:
    """Send log directly to Loki with proper error handling."""

    if not REQUESTS_AVAILABLE:
        print("❌ Requests library not available for custom Loki implementation")
        return False

    # Use the URL directly - it already contains the full endpoint path
    endpoint = url

    # Create Loki payload with level as a stream label for proper filtering
    timestamp = str(int(time.time() * 1000000000))  # nanoseconds

    # Add level as a stream label so Grafana can filter by it
    stream_labels = labels.copy()
    stream_labels["level"] = level.lower()  # Use lowercase for consistency

    payload = {
        "streams": [
            {
                "stream": stream_labels,
                "values": [
                    [timestamp, message]
                ],  # Don't prefix with level since it's in labels now
            }
        ]
    }

    try:
        import requests

        response = requests.post(
            endpoint,
            json=payload,
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code in [200, 204]:
            # Only show debug messages in DEBUG mode
            if LOG_LEVEL.upper() == "DEBUG":
                print(f"✅ Custom Loki log sent: {response.status_code}")
            return True
        else:
            print(f"❌ Custom Loki error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Custom Loki send failed: {e}")
        return False


def create_loki_fallback_handler(
    url: str, username: str, password: str, labels: Dict[str, str]
) -> logging.Handler:
    """Create a custom Loki handler that actually reports errors."""

    class CustomLokiHandler(logging.Handler):
        def emit(self, record):
            try:
                message = self.format(record)
                level = record.levelname
                send_to_loki_directly(message, level, labels, url, username, password)
            except Exception as e:
                print(f"❌ Custom Loki handler error: {e}")

    handler = CustomLokiHandler()
    handler.setLevel(logging.INFO)

    # Add the same recursion filter
    class NoRecursionFilter(logging.Filter):
        def filter(self, record):
            blocked_prefixes = [
                "urllib3",
                "requests",
                "logging_loki",
                "http.client",
                "httpx",
                "httpcore",
            ]
            should_block = any(
                record.name.startswith(prefix) for prefix in blocked_prefixes
            )

            if should_block and LOG_LEVEL.upper() == "DEBUG":
                print(f"🚫 FILTERED LOG: {record.name} - {record.getMessage()[:100]}")

            return not should_block

    handler.addFilter(NoRecursionFilter())
    return handler


def validate_loki_config() -> bool:
    """Validate Loki configuration by testing the endpoint directly."""

    if not REQUESTS_AVAILABLE:
        print("⚠️  Requests library not available for Loki validation")
        return True  # Assume it works if we can't test

    try:
        import requests

        # Test the exact endpoint the app will use - LOKI_PUSH_URL already contains full path
        test_url = LOKI_PUSH_URL

        # Send minimal test payload for connectivity validation
        payload = {
            "streams": [
                {
                    "stream": {
                        "test": "validation",
                        "job": "loki-validation",
                        "level": "info",
                    },
                    "values": [
                        [str(int(time.time() * 1000000000)), "connectivity-test"]
                    ],
                }
            ]
        }

        response = requests.post(
            test_url, json=payload, auth=(LOKI_USERNAME, LOKI_PASSWORD), timeout=5
        )

        if response.status_code in [200, 204]:
            print("✅ Loki endpoint validation successful")
            return True
        else:
            print(f"❌ Loki validation failed: {response.status_code} {response.text}")
            return False

    except Exception as e:
        print(f"❌ Loki validation error: {e}")
        return False


def test_loki_handler(handler: logging.Handler) -> bool:
    """Test if the Loki handler actually works."""
    try:
        # Create a test record
        test_record = logging.LogRecord(
            name="loki_handler_test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="🧪 Handler connectivity test",
            args=(),
            exc_info=None,
        )

        # Try to emit the record
        handler.emit(test_record)

        # Give it a moment to process
        time.sleep(0.5)

        print("✅ Loki handler test completed (logging_loki doesn't report failures)")
        return True  # logging_loki doesn't report failures, assume success

    except Exception as e:
        print(f"❌ Loki handler test failed: {e}")
        return False


def _initialize_console_handler(level: int) -> logging.Handler:
    console_handler = logging.StreamHandler(sys.__stdout__)
    console_handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    return console_handler


def _initialize_loki_handler(level: int) -> Optional[logging.Handler]:
    if not LOKI_ENABLED:
        print("Loki logging disabled in configuration")
        return None

    if not LOKI_PUSH_URL:
        print("Loki URL not configured")
        return None

    # Check environment to determine authentication requirements
    is_production = ENVIRONMENT in ("production", "prod")

    print(f"🔧 Configuring Loki for {ENVIRONMENT} environment")
    print(f"📡 Loki endpoint: {LOKI_PUSH_URL}")

    # Authentication logic - always use auth when credentials are provided
    if LOKI_USERNAME and LOKI_PASSWORD:
        placeholder_tokens = {"<your_grafana_api_token>", "changeme", ""}
        if LOKI_PASSWORD.strip().lower() in placeholder_tokens:
            if is_production:
                print(
                    "❌ Production environment detected but placeholder credentials found. Skipping remote handler."
                )
                return None
            else:
                print(
                    "⚠️  Using placeholder credentials. Consider updating for better security."
                )

        print(
            f"🔐 {ENVIRONMENT.title()} environment: Using authenticated connection (user: {LOKI_USERNAME})"
        )

    else:
        if is_production:
            print(
                "❌ Production environment detected but Loki credentials missing. Skipping remote handler."
            )
            return None
        else:
            print(
                f"🚀 {ENVIRONMENT.title()} environment: Using unauthenticated connection"
            )

    if LOKI_TENANT_ID:
        print(f"🏢 Using tenant ID: {LOKI_TENANT_ID}")

    # First validate that the endpoint actually works
    print("🧪 Validating Loki endpoint connectivity...")
    if not validate_loki_config():
        print("⚠️  Loki validation failed, trying custom implementation...")
        return create_loki_fallback_handler(
            LOKI_PUSH_URL, LOKI_USERNAME, LOKI_PASSWORD, LOKI_LABELS or {}
        )

    # FORCE custom implementation since logging_loki fails silently
    print("🔧 Using custom Loki implementation (logging_loki has silent failures)")
    return create_loki_fallback_handler(
        LOKI_PUSH_URL, LOKI_USERNAME, LOKI_PASSWORD, LOKI_LABELS or {}
    )

    # Try to use the original logging_loki library (DISABLED - fails silently)
    if False and LokiHandler is not None:
        try:
            handler_kwargs = {
                "url": LOKI_PUSH_URL,
                "tags": LOKI_LABELS or {},
            }

            if LOKI_USERNAME and LOKI_PASSWORD:
                handler_kwargs["auth"] = (LOKI_USERNAME, LOKI_PASSWORD)

            if LOKI_TENANT_ID:
                handler_kwargs["tenant_id"] = LOKI_TENANT_ID

            handler = LokiHandler(**handler_kwargs)  # type: ignore[arg-type]
            handler.setLevel(level)

            # Enhanced recursion filter with debugging
            class NoRecursionFilter(logging.Filter):
                def filter(self, record):
                    blocked_prefixes = [
                        "urllib3",
                        "requests",
                        "logging_loki",
                        "http.client",
                        "httpx",
                        "httpcore",
                    ]
                    should_block = any(
                        record.name.startswith(prefix) for prefix in blocked_prefixes
                    )

                    if should_block and LOG_LEVEL.upper() == "DEBUG":
                        print(
                            f"🚫 FILTERED LOG: {record.name} - {record.getMessage()[:100]}"
                        )

                    return not should_block

            handler.addFilter(NoRecursionFilter())

            print(
                f"✅ Loki handler (logging_loki) initialized for {ENVIRONMENT} environment"
            )
            print(f"📊 Labels configured: {LOKI_LABELS}")

            # Test the handler immediately
            try:
                test_logger = logging.getLogger("loki_debug_test")
                test_logger.addHandler(handler)
                test_logger.info("🧪 LOKI HANDLER TEST - Handler created successfully")

                # Force emit a test record
                test_record = logging.LogRecord(
                    name="loki_immediate_test",
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg="🚀 IMMEDIATE TEST - Handler working",
                    args=(),
                    exc_info=None,
                )
                handler.emit(test_record)

                print("✅ Test logs sent via logging_loki handler")

            except Exception as debug_exc:
                print(f"❌ Loki handler test failed: {debug_exc}")
                print("   Falling back to custom implementation...")
                return create_loki_fallback_handler(
                    LOKI_PUSH_URL, LOKI_USERNAME, LOKI_PASSWORD, LOKI_LABELS or {}
                )

            return handler

        except Exception as exc:
            print(f"❌ Failed to initialize logging_loki handler: {exc}")
            print("   Using custom Loki implementation...")
            return create_loki_fallback_handler(
                LOKI_PUSH_URL, LOKI_USERNAME, LOKI_PASSWORD, LOKI_LABELS or {}
            )
    else:
        print("❌ logging_loki library unavailable. Using custom implementation.")
        return create_loki_fallback_handler(
            LOKI_PUSH_URL, LOKI_USERNAME, LOKI_PASSWORD, LOKI_LABELS or {}
        )


def setup_logging() -> None:
    """Enhanced logging setup with detailed Loki diagnostics."""

    print("🔧 Initializing logging system...")

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    # Suppress noisy third-party loggers BEFORE initializing handlers
    if level <= logging.DEBUG:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any pre-existing handlers to avoid duplicate logs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = _initialize_console_handler(level)
    root_logger.addHandler(console_handler)

    if LOKI_ENABLED:
        print(f"📡 Testing Loki connectivity to: {LOKI_PUSH_URL}")

        loki_handler = _initialize_loki_handler(level)
        if loki_handler is not None:
            root_logger.addHandler(loki_handler)

            # Send immediate success log
            root_logger.info(
                "🚀 Loki logging initialized - this message should appear in Grafana"
            )
            print(
                '✅ Loki logging active - check Grafana with query: {job="dydx-trading-bot"}'
            )
        else:
            print("❌ Loki handler creation failed - running with console logging only")
    else:
        print("ℹ️  Loki logging disabled in configuration")

    # Mirror prints to logging so existing print statements are captured
    stdout_logger = logging.getLogger("stdout")
    stdout_logger.setLevel(level)
    stderr_logger = logging.getLogger("stderr")
    stderr_logger.setLevel(logging.ERROR)

    # NOTE: Commented out stdout/stderr redirection to avoid KeyboardInterrupt issues
    # If you need print() statements captured, use logger.info() instead of print()
    # sys.stdout = _LoggerStream(stdout_logger, level, fallback=sys.__stdout__)
    # sys.stderr = _LoggerStream(stderr_logger, logging.ERROR, fallback=sys.__stderr__)

    root_logger.info("📊 Logging system initialized successfully")
    print(
        "🎯 Setup complete! All logs will now be sent to console and Loki (if enabled)"
    )
