import importlib
import threading
import time
from datetime import datetime, timezone

import pytest
import requests

import src.shared.notifications as notifications
from src.exceptions import CircuitBreakerOpenError
from src.shared.notifications import TelegramMessenger


def _load_notifications_module():
    return importlib.import_module("src.shared.notifications")


def test_startup_message_prefers_instance_account_address(monkeypatch):
    notifications = _load_notifications_module()
    messenger = notifications.TelegramMessenger()

    captured = {}

    def _fake_send_message(
        text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None
    ):
        captured["text"] = text
        captured["parse_mode"] = parse_mode
        captured["dedupe_key"] = dedupe_key
        captured["dedupe_window_seconds"] = dedupe_window_seconds
        return True

    monkeypatch.setattr(messenger, "send_message", _fake_send_message)

    account_address = "dydx16shv8n0j28djnjrcg0jxusmkf46umtzrepslsp"
    sent = messenger.send_startup_message(
        {
            "environment": "development",
            "is_testnet": True,
            "strategy": "cointegration",
            "account_address": account_address,
        }
    )

    assert sent is True
    assert (
        "https://www.mintscan.io/dydx-testnet/account/dydx16shv8n0j28djnjrcg0jxusmkf46umtzrepslsp"
        in captured["text"]
    )
    assert "dydx16sh..." in captured["text"]


def test_lifecycle_message_uses_explicit_runtime_context(monkeypatch):
    notifications = _load_notifications_module()
    messenger = notifications.TelegramMessenger(
        bot_token="token",
        chat_id="chat",
        instance_id="strategy-1-4",
        environment="development",
    )

    captured = {}

    def _fake_send_message(
        text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None
    ):
        captured["text"] = text
        captured["parse_mode"] = parse_mode
        captured["dedupe_key"] = dedupe_key
        captured["dedupe_window_seconds"] = dedupe_window_seconds
        return True

    monkeypatch.setattr(messenger, "send_message", _fake_send_message)

    sent = messenger.send_lifecycle_message(
        "restarted",
        {
            "instance_id": "strategy-1-4",
            "instance_name": "Aggressive",
            "strategy": "cointegration",
            "is_testnet": True,
            "account_address": "dydx16shv8n0j28djnjrcg0jxusmkf46umtzrepslsp",
            "operator": "admin",
            "details": "Runtime restarted successfully.",
            "reason": "Operator restart",
        },
        success=True,
    )

    assert sent is True
    assert "RUNTIME RESTARTED" in captured["text"]
    assert "Aggressive" in captured["text"]
    assert "admin" in captured["text"]
    assert "Operator restart" in captured["text"]
    assert "Runtime restarted successfully." in captured["text"]
    assert captured["dedupe_key"] == "lifecycle:restarted:strategy-1-4:success"


def test_trade_opened_message_supports_normalized_trade_payload_keys(monkeypatch):
    notifications = _load_notifications_module()
    messenger = notifications.TelegramMessenger()

    captured = {}

    def _fake_send_message(
        text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None
    ):
        captured["text"] = text
        captured["parse_mode"] = parse_mode
        captured["dedupe_key"] = dedupe_key
        captured["dedupe_window_seconds"] = dedupe_window_seconds
        return True

    monkeypatch.setattr(messenger, "send_message", _fake_send_message)

    sent = messenger.send_trade_opened_message(
        {
            "base_market": "IMX-USD",
            "quote_market": "ETH-USD",
            "base_side": "BUY",
            "quote_side": "SELL",
            "base_size": "10",
            "quote_size": "1.2",
            "z_score": -1.583,
            "hedge_ratio": 36.6416,
        }
    )

    assert sent is True
    assert "Pair:</b> IMX-USD / ETH-USD" in captured["text"]
    assert "• IMX-USD: BUY 10" in captured["text"]
    assert "• ETH-USD: SELL 1.2" in captured["text"]


def test_trade_opened_message_supports_pair_string_and_entry_size_keys(monkeypatch):
    notifications = _load_notifications_module()
    messenger = notifications.TelegramMessenger()

    captured = {}

    def _fake_send_message(
        text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None
    ):
        captured["text"] = text
        captured["parse_mode"] = parse_mode
        captured["dedupe_key"] = dedupe_key
        captured["dedupe_window_seconds"] = dedupe_window_seconds
        return True

    monkeypatch.setattr(messenger, "send_message", _fake_send_message)

    sent = messenger.send_trade_opened_message(
        {
            "pair": "DOT-USD / CRO-USD",
            "side1": "BUY",
            "side2": "SELL",
            "entry_size1": "8",
            "entry_size2": "145",
            "z_score": -1.731,
            "hedge_ratio": 0.0364,
        }
    )

    assert sent is True
    assert "Pair:</b> DOT-USD / CRO-USD" in captured["text"]
    assert "• DOT-USD: BUY 8" in captured["text"]
    assert "• CRO-USD: SELL 145" in captured["text"]


def test_trade_closed_message_supports_normalized_trade_payload_keys(monkeypatch):
    notifications = _load_notifications_module()
    messenger = notifications.TelegramMessenger()

    captured = {}

    def _fake_send_message(
        text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None
    ):
        captured["text"] = text
        captured["parse_mode"] = parse_mode
        captured["dedupe_key"] = dedupe_key
        captured["dedupe_window_seconds"] = dedupe_window_seconds
        return True

    monkeypatch.setattr(messenger, "send_message", _fake_send_message)

    sent = messenger.send_trade_closed_message(
        {
            "pair": "IMX-USD / ETH-USD",
            "base_market": "IMX-USD",
            "quote_market": "ETH-USD",
            "z_score": -0.741,
            "close_order_m1_id": "close-imx",
            "close_order_m2_id": "close-eth",
        },
        "Z-score reversion after orphan retry",
    )

    assert sent is True
    assert "Pair:</b> IMX-USD / ETH-USD" in captured["text"]
    assert "Final Z-Score:</b> -0.741" in captured["text"]
    assert "Reason:</b> Z-score reversion after orphan retry" in captured["text"]


def test_recovery_message_uses_non_critical_template(monkeypatch):
    notifications = _load_notifications_module()
    messenger = notifications.TelegramMessenger()

    captured = {}

    def _fake_send_message(
        text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None
    ):
        captured["text"] = text
        captured["parse_mode"] = parse_mode
        captured["dedupe_key"] = dedupe_key
        captured["dedupe_window_seconds"] = dedupe_window_seconds
        return True

    monkeypatch.setattr(messenger, "send_message", _fake_send_message)

    sent = messenger.send_recovery_message(
        "Recovered Orphaned Position Leg",
        "Submitted reduce-only close for orphaned MET-USD leg. Close order: oid-123",
        category="execution_orphan_recovery",
    )

    assert sent is True
    assert "RECOVERY ACTION APPLIED" in captured["text"]
    assert "Recovered Orphaned Position Leg" in captured["text"]
    assert "execution_orphan_recovery" in captured["text"]
    assert "CRITICAL ERROR" not in captured["text"]


# ---------------------------------------------------------------------------
# Unit coverage: env resolution, helpers, dedupe, transport, and wrappers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_messenger_class_state():
    saved_recent = dict(TelegramMessenger._recent_messages)
    saved_notice = TelegramMessenger._disabled_notice_logged
    TelegramMessenger._recent_messages.clear()
    TelegramMessenger._disabled_notice_logged = False
    yield
    TelegramMessenger._recent_messages.clear()
    TelegramMessenger._recent_messages.update(saved_recent)
    TelegramMessenger._disabled_notice_logged = saved_notice


class _FakeResponse:
    def __init__(self, status_code=200, text="ok", json_payload=None, json_error=False):
        self.status_code = status_code
        self.text = text
        self._json_payload = json_payload or {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("no json body")
        return self._json_payload


def _install_post(monkeypatch, outcomes, sleeps):
    calls = []

    def _fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(notifications.requests, "post", _fake_post)
    monkeypatch.setattr(
        notifications.time, "sleep", lambda seconds: sleeps.append(seconds)
    )
    return calls


def _capture_transport(messenger):
    captured = {}

    def _fake_send_request(method, data):
        captured["method"] = method
        captured["text"] = data["text"]
        captured["data"] = data
        return True

    messenger._send_request = _fake_send_request
    return captured


class _RecordingMessenger:
    def __init__(self, enabled=True, send_result=True):
        self.enabled = enabled
        self.send_result = send_result
        self.calls = []

    def send_message(
        self, text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None
    ):
        self.calls.append(
            ("send_message", text, parse_mode, dedupe_key, dedupe_window_seconds)
        )
        return self.send_result

    def send_startup_message(self, config_info):
        self.calls.append(("startup", config_info))
        return True

    def send_error_message(
        self, error_type, error_details, is_critical=False, category=None
    ):
        self.calls.append(("error", error_type, error_details, is_critical, category))
        return True

    def send_trade_opened_message(self, trade_info):
        self.calls.append(("trade_opened", trade_info))
        return True

    def send_trade_closed_message(self, trade_info, reason="Z-score reversion"):
        self.calls.append(("trade_closed", trade_info, reason))
        return True

    def send_cointegration_results(
        self, pairs_found, analysis_time, high_confidence_pairs=0
    ):
        self.calls.append(
            ("cointegration", pairs_found, analysis_time, high_confidence_pairs)
        )
        return True

    def send_account_status(self, account_info, is_testnet=True):
        self.calls.append(("account_status", account_info, is_testnet))
        return True

    def send_daily_summary(self, summary_info):
        self.calls.append(("daily_summary", summary_info))
        return True

    def send_lifecycle_message(self, action, lifecycle_info, success=True):
        self.calls.append(("lifecycle", action, lifecycle_info, success))
        return True

    def send_shutdown_message(self, reason="Manual stop"):
        self.calls.append(("shutdown", reason))
        return True


def test_constructor_uses_explicit_credentials():
    messenger = TelegramMessenger(bot_token="tok-1", chat_id="chat-1")
    assert messenger.enabled is True
    assert messenger.base_url == "https://api.telegram.org/bottok-1"
    assert messenger.bot_token == "tok-1"
    assert messenger.chat_id == "chat-1"


def test_constructor_reads_env_credentials(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "env-chat")
    messenger = TelegramMessenger()
    assert messenger.enabled is True
    assert messenger.bot_token == "env-token"
    assert messenger.chat_id == "env-chat"


def test_constructor_blank_env_falls_back_to_constants(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "   ")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    monkeypatch.setattr(notifications, "TELEGRAM_TOKEN", "const-token")
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", "const-chat")
    messenger = TelegramMessenger()
    assert messenger.enabled is True
    assert messenger.bot_token == "const-token"
    assert messenger.chat_id == "const-chat"


def test_constructor_disabled_without_credentials(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(notifications, "TELEGRAM_TOKEN", "")
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", "")

    TelegramMessenger._disabled_notice_logged = False
    messenger = TelegramMessenger()
    assert messenger.enabled is False
    assert TelegramMessenger._disabled_notice_logged is True

    TelegramMessenger(bot_token="half", chat_id=None)
    assert TelegramMessenger(bot_token=None, chat_id="").enabled is False


def test_escape_html_escapes_markup():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    assert messenger._escape_html('<b>&"x"') == "&lt;b&gt;&amp;&quot;x&quot;"


def test_instance_prefix_sources(monkeypatch):
    monkeypatch.delenv("BOT_INSTANCE_ID", raising=False)
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    assert messenger._instance_prefix() == ""

    messenger.instance_id = "bot <1>"
    prefix = messenger._instance_prefix()
    assert "Instance:</b> bot &lt;1&gt;" in prefix

    messenger.instance_id = ""
    monkeypatch.setenv("BOT_INSTANCE_ID", "env-instance")
    assert "env-instance" in messenger._instance_prefix()


def test_environment_prefix_sources(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    assert "development" in messenger._environment_prefix()

    messenger.environment = "Production "
    assert "production" in messenger._environment_prefix()

    messenger.environment = ""
    monkeypatch.setenv("ENVIRONMENT", "STAGING")
    assert "staging" in messenger._environment_prefix()


def test_truncate_text_limits():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    short = "x" * 100
    assert messenger._truncate_text(short) == short
    exact = "y" * 3900
    assert messenger._truncate_text(exact) == exact

    long_text = "z" * 5000
    truncated = messenger._truncate_text(long_text)
    assert truncated.endswith("\n\n<i>[message truncated]</i>")
    assert truncated == "z" * (3900 - 24) + "\n\n<i>[message truncated]</i>"

    padded = "a" * 3870 + " " * 10 + "b" * 200
    stripped = messenger._truncate_text(padded)
    prefix = stripped.split("\n\n<i>")[0]
    assert prefix == "a" * 3870


def test_resolve_account_address_sources(monkeypatch):
    monkeypatch.setattr(notifications, "DYDX_ADDRESS", "dydx1constant")
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    assert messenger._resolve_account_address("dydx1explicit ") == "dydx1explicit"
    assert messenger._resolve_account_address("   ") == "dydx1constant"
    assert messenger._resolve_account_address(None) == "dydx1constant"


def test_format_account_link_variants():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    assert messenger._format_account_link("", True) == "Unavailable"

    address = "dydx16shv8n0j28djnjrcg0jxusmkf46umtzrepslsp"
    abbreviated = f"{address[:8]}...{address[-6:]}"

    testnet = messenger._format_account_link(address, True)
    assert f"https://www.mintscan.io/dydx-testnet/account/{address}" in testnet
    assert abbreviated in testnet

    mainnet = messenger._format_account_link(address, False)
    assert f"https://www.mintscan.io/dydx/account/{address}" in mainnet

    short = messenger._format_account_link("short", False)
    assert ">short</a>" in short


def test_safe_env_int_matrix(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    monkeypatch.delenv("TELEGRAM_TEST_INT", raising=False)
    assert messenger._safe_env_int("TELEGRAM_TEST_INT", 7) == 7
    monkeypatch.setenv("TELEGRAM_TEST_INT", "42")
    assert messenger._safe_env_int("TELEGRAM_TEST_INT", 7) == 42
    monkeypatch.setenv("TELEGRAM_TEST_INT", "-5")
    assert messenger._safe_env_int("TELEGRAM_TEST_INT", 7) == 0
    monkeypatch.setenv("TELEGRAM_TEST_INT", "garbage")
    assert messenger._safe_env_int("TELEGRAM_TEST_INT", 7) == 7
    monkeypatch.setenv("TELEGRAM_TEST_INT", "")
    assert messenger._safe_env_int("TELEGRAM_TEST_INT", 7) == 7


def test_normalize_error_category_matrix():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    assert messenger._normalize_error_category(None, "ValueError") == "valueerror"
    assert messenger._normalize_error_category("Data Sync!!", "") == "data_sync"
    assert messenger._normalize_error_category(None, None) == "general"
    assert messenger._normalize_error_category("  ", "") == "general"


def test_resolve_error_dedupe_window_matrix(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    for name in (
        "TELEGRAM_ERROR_DEDUPE_SECONDS_CRITICAL",
        "TELEGRAM_ERROR_DEDUPE_SECONDS_NETWORK",
        "TELEGRAM_ERROR_DEDUPE_SECONDS_DEFAULT",
    ):
        monkeypatch.delenv(name, raising=False)

    assert messenger._resolve_error_dedupe_window_seconds("network", True) == 0
    monkeypatch.setenv("TELEGRAM_ERROR_DEDUPE_SECONDS_CRITICAL", "30")
    assert messenger._resolve_error_dedupe_window_seconds("network", True) == 30

    assert messenger._resolve_error_dedupe_window_seconds("network", False) == 120
    monkeypatch.setenv("TELEGRAM_ERROR_DEDUPE_SECONDS_NETWORK", "45")
    assert messenger._resolve_error_dedupe_window_seconds("network", False) == 45
    monkeypatch.setenv("TELEGRAM_ERROR_DEDUPE_SECONDS_NETWORK", "garbage")
    assert messenger._resolve_error_dedupe_window_seconds("network", False) == 120

    monkeypatch.setenv("TELEGRAM_ERROR_DEDUPE_SECONDS_DEFAULT", "200")
    assert messenger._resolve_error_dedupe_window_seconds("other", False) == 200


def test_should_skip_duplicate_lifecycle():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    assert messenger._should_skip_duplicate("key", 0) is False
    assert messenger._should_skip_duplicate("", 60) is False

    assert messenger._should_skip_duplicate("key", 60) is False
    assert messenger._should_skip_duplicate("key", 60) is True

    TelegramMessenger._recent_messages["key"] = time.time() - 61
    assert messenger._should_skip_duplicate("key", 60) is False


def test_send_request_blocking_disabled_short_circuits(monkeypatch):
    messenger = TelegramMessenger(bot_token="", chat_id="")
    sleeps = []
    calls = _install_post(monkeypatch, [_FakeResponse(200)], sleeps)
    assert messenger._send_request_blocking("sendMessage", {"text": "x"}) is False
    assert calls == []
    assert sleeps == []


def test_send_request_blocking_success(monkeypatch):
    messenger = TelegramMessenger(bot_token="tok", chat_id="chat")
    sleeps = []
    calls = _install_post(monkeypatch, [_FakeResponse(200)], sleeps)
    payload = {"chat_id": "chat", "text": "hello"}
    assert messenger._send_request_blocking("sendMessage", payload) is True
    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.telegram.org/bottok/sendMessage"
    assert calls[0]["json"] == payload
    assert calls[0]["timeout"] == 15
    assert sleeps == []


def test_send_request_blocking_bot_chat_403(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="bot-chat")
    sleeps = []
    calls = _install_post(
        monkeypatch,
        [_FakeResponse(403, "Forbidden: bot can't send messages to bots")],
        sleeps,
    )
    assert messenger._send_request_blocking("sendMessage", {}) is False
    assert len(calls) == 1
    assert sleeps == []


def test_send_request_blocking_transient_429_honors_retry_after(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    calls = _install_post(
        monkeypatch,
        [
            _FakeResponse(429, json_payload={"parameters": {"retry_after": 7}}),
            _FakeResponse(200),
        ],
        sleeps,
    )
    assert messenger._send_request_blocking("sendMessage", {}) is True
    assert len(calls) == 2
    assert sleeps == [7.0]


def test_send_request_blocking_429_bad_json_uses_backoff(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    calls = _install_post(
        monkeypatch,
        [_FakeResponse(429, json_error=True), _FakeResponse(200)],
        sleeps,
    )
    assert messenger._send_request_blocking("sendMessage", {}) is True
    assert sleeps == [0.5]


def test_send_request_blocking_transient_exhausted(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    calls = _install_post(monkeypatch, [_FakeResponse(503)] * 3, sleeps)
    assert messenger._send_request_blocking("sendMessage", {}) is False
    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]


def test_send_request_blocking_non_transient_fails_fast(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    calls = _install_post(monkeypatch, [_FakeResponse(400, "bad request")], sleeps)
    assert messenger._send_request_blocking("sendMessage", {}) is False
    assert len(calls) == 1
    assert sleeps == []


def test_send_request_blocking_circuit_open(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    calls = _install_post(monkeypatch, [_FakeResponse(200)], sleeps)

    def _open_breaker(name, func, *args, **kwargs):
        raise CircuitBreakerOpenError(name)

    monkeypatch.setattr(notifications.resilience, "call", _open_breaker)
    assert messenger._send_request_blocking("sendMessage", {}) is False
    assert calls == []
    assert sleeps == []


def test_send_request_blocking_request_exception_retries(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    calls = _install_post(
        monkeypatch,
        [
            requests.exceptions.RequestException("boom"),
            requests.exceptions.RequestException("boom again"),
            _FakeResponse(200),
        ],
        sleeps,
    )
    assert messenger._send_request_blocking("sendMessage", {}) is True
    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]


def test_send_request_blocking_request_exception_exhausted(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    calls = _install_post(
        monkeypatch,
        [requests.exceptions.RequestException("down")] * 3,
        sleeps,
    )
    assert messenger._send_request_blocking("sendMessage", {}) is False
    assert len(calls) == 3


def test_send_request_blocking_retry_env_overrides(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    monkeypatch.setenv("TELEGRAM_SEND_RETRIES", "2")
    calls = _install_post(monkeypatch, [_FakeResponse(500)] * 2, sleeps)
    assert messenger._send_request_blocking("sendMessage", {}) is False
    assert len(calls) == 2
    assert sleeps == [0.5]


def test_send_request_blocking_retry_env_garbage_falls_back(monkeypatch):
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sleeps = []
    monkeypatch.setenv("TELEGRAM_SEND_RETRIES", "not-a-number")
    calls = _install_post(monkeypatch, [_FakeResponse(500)] * 3, sleeps)
    assert messenger._send_request_blocking("sendMessage", {}) is False
    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]


def test_send_request_without_loop_delegates_to_blocking():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    calls = []

    def _fake_blocking(method, data):
        calls.append((method, data))
        return True

    messenger._send_request_blocking = _fake_blocking
    assert messenger._send_request("sendMessage", {"text": "x"}) is True
    assert calls == [("sendMessage", {"text": "x"})]


@pytest.mark.asyncio
async def test_send_request_with_running_loop_offloads_to_thread():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    sent = threading.Event()
    calls = []

    def _fake_blocking(method, data):
        calls.append((method, data))
        sent.set()
        return True

    messenger._send_request_blocking = _fake_blocking
    result = messenger._send_request("sendMessage", {"text": "async"})
    assert result is True
    assert sent.wait(timeout=2.0)
    assert calls[0][0] == "sendMessage"


def test_send_message_disabled_returns_false():
    messenger = TelegramMessenger(bot_token="", chat_id="")
    assert messenger.send_message("hello") is False


def test_send_message_dedupe_skips_repeat():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)
    assert (
        messenger.send_message("one", dedupe_key="k", dedupe_window_seconds=60) is True
    )
    assert (
        messenger.send_message("two", dedupe_key="k", dedupe_window_seconds=60) is False
    )
    assert captured["text"] == "one"


def test_send_message_default_dedupe_window_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_DEDUPE_SECONDS", "60")
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    _capture_transport(messenger)
    assert messenger.send_message("one", dedupe_key="env-k") is True
    assert "env-k" in TelegramMessenger._recent_messages
    assert messenger.send_message("two", dedupe_key="env-k") is False


def test_send_message_truncates_and_builds_payload():
    messenger = TelegramMessenger(bot_token="t", chat_id="chat-9")
    captured = _capture_transport(messenger)
    long_text = "a" * 5000
    assert messenger.send_message(long_text, parse_mode="Markdown") is True
    assert captured["method"] == "sendMessage"
    assert captured["data"]["chat_id"] == "chat-9"
    assert captured["data"]["parse_mode"] == "Markdown"
    assert captured["data"]["disable_web_page_preview"] is True
    assert len(captured["text"]) <= 3904
    assert captured["text"].endswith("\n\n<i>[message truncated]</i>")


def test_startup_message_environment_detection(monkeypatch):
    monkeypatch.setattr(notifications, "DYDX_ADDRESS", "dydx1constant")
    messenger = TelegramMessenger(
        bot_token="t", chat_id="c", instance_id="i1", environment="production"
    )
    captured = _capture_transport(messenger)

    assert (
        messenger.send_startup_message(
            {"environment": "unknown", "is_testnet": True, "strategy": "cointegration"}
        )
        is True
    )
    assert "DEVELOPMENT" in captured["text"]
    assert "🧪 TESTNET" in captured["text"]
    assert "Testnet" in captured["text"]
    assert "Cointegration" in captured["text"]
    assert "dydx-testnet/account/dydx1constant" in captured["text"]

    messenger.send_startup_message(
        {"environment": "production", "is_testnet": False, "strategy": "arb"}
    )
    assert "PRODUCTION" in captured["text"]
    assert "🔴 MAINNET" in captured["text"]
    assert "Mainnet" in captured["text"]

    messenger.send_startup_message({"environment": "staging", "is_testnet": True})
    assert "STAGING" in captured["text"]
    assert "⚙️" in captured["text"]


def test_lifecycle_message_titles_and_failure_override():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)

    assert messenger.send_lifecycle_message("start", {"strategy": "arb"}) is True
    assert "RUNTIME STARTED" in captured["text"]
    assert "RUNTIME STARTED FAILED" not in captured["text"]

    messenger.send_lifecycle_message("restart", {"strategy": "arb"}, success=False)
    assert "RUNTIME RESTARTED FAILED" in captured["text"]

    messenger.send_lifecycle_message("deploy", {"strategy": "arb"})
    assert "RUNTIME UPDATED" in captured["text"]

    messenger.send_lifecycle_message("error", {"strategy": "arb"}, success=False)
    assert "RUNTIME ACTION FAILED" in captured["text"]
    assert "RUNTIME ACTION FAILED FAILED" not in captured["text"]


def test_error_message_severity_and_dedupe(monkeypatch):
    for name in (
        "TELEGRAM_ERROR_DEDUPE_SECONDS_CRITICAL",
        "TELEGRAM_ERROR_DEDUPE_SECONDS_DEFAULT",
    ):
        monkeypatch.delenv(name, raising=False)
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)

    assert messenger.send_error_message("ValueError", "boom", is_critical=True) is True
    assert "CRITICAL ERROR" in captured["text"]
    assert messenger.send_error_message("ValueError", "boom", is_critical=True) is True

    assert (
        messenger.send_error_message("ConnError", "reset", category="Data / Sync!")
        is True
    )
    assert "⚠️" in captured["text"]
    assert "data_sync" in captured["text"]
    assert (
        messenger.send_error_message("ConnError", "reset", category="Data / Sync!")
        is False
    )


def test_trade_opened_message_direct_keys_and_pair_split():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)

    assert (
        messenger.send_trade_opened_message(
            {
                "market_1": "BTC-USD",
                "market_2": "ETH-USD",
                "side_1": "BUY",
                "side_2": "SELL",
                "size_1": 2,
                "size_2": 3,
                "z_score": 1.23456,
                "hedge_ratio": 0.5,
            }
        )
        is True
    )
    assert "📈" in captured["text"]
    assert "BTC-USD / ETH-USD" in captured["text"]
    assert "Z-Score:</b> 1.235" in captured["text"]
    assert "Hedge Ratio:</b> 0.5000" in captured["text"]
    assert "• BTC-USD: BUY 2" in captured["text"]
    assert "• ETH-USD: SELL 3" in captured["text"]

    messenger.send_trade_opened_message({"market_1": "BTC-USD", "pair": "BTC/ETH"})
    assert "BTC-USD / ETH" in captured["text"]

    messenger.send_trade_opened_message({})
    assert "Unknown / Unknown" in captured["text"]


def test_trade_closed_message_zscore_parsing_and_reasons():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)

    assert (
        messenger.send_trade_closed_message(
            {"pair": "BTC/ETH", "current_zscore": "1.5"}, "Manual close"
        )
        is True
    )
    assert "Final Z-Score:</b> 1.500" in captured["text"]
    assert "👨‍💼" in captured["text"]

    messenger.send_trade_closed_message({"pair": "BTC/ETH", "current_zscore": "nan?"})
    assert "Final Z-Score:</b> 0.000" in captured["text"]

    messenger.send_trade_closed_message({"pair": "BTC/ETH"}, "Take profit")
    assert "✅" in captured["text"]

    messenger.send_trade_closed_message({"pair": "BTC/ETH", "final_z_score": -0.25})
    assert "Final Z-Score:</b> -0.250" in captured["text"]


def test_cointegration_results_branches():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)

    assert (
        messenger.send_cointegration_results(5, 2.56, high_confidence_pairs=2) is True
    )
    assert "🎯" in captured["text"]
    assert "(40%)" in captured["text"]
    assert "2.6 seconds" in captured["text"]

    messenger.send_cointegration_results(4, 1.02)
    assert "📊" in captured["text"]

    messenger.send_cointegration_results(0, 0.5)
    assert "⚠️" in captured["text"]
    assert "No suitable pairs found" in captured["text"]


def test_account_status_balance_thresholds():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)

    assert (
        messenger.send_account_status(
            {"balance": 150, "available_balance": 75.5, "open_positions": 3},
            is_testnet=False,
        )
        is True
    )
    assert "✅" in captured["text"]
    assert "$150.00" in captured["text"]
    assert "$75.50" in captured["text"]
    assert "Open Positions:</b> 3" in captured["text"]

    messenger.send_account_status({"balance": 75})
    assert "⚠️" in captured["text"]
    messenger.send_account_status({"balance": 10})
    assert "🚨" in captured["text"]


def test_daily_summary_content():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)
    assert (
        messenger.send_daily_summary(
            {"trades_opened": 2, "trades_closed": 1, "active_positions": 0}
        )
        is True
    )
    assert "Trades Opened:</b> 2" in captured["text"]
    assert "Trades Closed:</b> 1" in captured["text"]
    assert "Active Positions:</b> 0" in captured["text"]
    assert datetime.now(timezone.utc).strftime("%Y-%m-%d") in captured["text"]


def test_shutdown_message_escapes_reason():
    messenger = TelegramMessenger(bot_token="t", chat_id="c")
    captured = _capture_transport(messenger)
    assert messenger.send_shutdown_message("<script>alert(1)</script>") is True
    assert "&lt;script&gt;" in captured["text"]
    assert "<script>" not in captured["text"]


def test_legacy_send_message_result_mapping(monkeypatch):
    fake = _RecordingMessenger(enabled=True, send_result=True)
    monkeypatch.setattr(notifications, "_messenger", fake)

    assert notifications.send_message("hi") == "sent"
    assert fake.calls[-1][0] == "send_message"
    assert fake.calls[-1][2] == "Markdown"

    fake.send_result = False
    assert notifications.send_message("hi") == "failed"

    fake.enabled = False
    assert notifications.send_message("hi") == "no-token"


def test_module_wrapper_delegation(monkeypatch):
    fake = _RecordingMessenger()
    monkeypatch.setattr(notifications, "_messenger", fake)

    assert (
        notifications.send_startup_notification({"environment": "development"}) is True
    )
    assert fake.calls[-1][0] == "startup"

    assert (
        notifications.send_error_notification("ValueError", "boom", True, category="x")
        is True
    )
    assert fake.calls[-1] == ("error", "ValueError", "boom", True, "x")

    assert notifications.send_analysis_notification(5, 1.5) is True
    assert fake.calls[-1][0] == "cointegration"

    assert (
        notifications.send_account_notification({"balance": 1}, is_testnet=False)
        is True
    )
    assert fake.calls[-1] == ("account_status", {"balance": 1}, False)

    assert notifications.send_daily_summary({"trades_opened": 1}) is True
    assert fake.calls[-1][0] == "daily_summary"

    assert notifications.send_lifecycle_notification("stop", {}, success=False) is True
    assert fake.calls[-1] == ("lifecycle", "stop", {}, False)

    assert notifications.send_shutdown_notification("done") is True
    assert fake.calls[-1] == ("shutdown", "done")


def test_send_trade_notification_dispatch(monkeypatch):
    fake = _RecordingMessenger()
    monkeypatch.setattr(notifications, "_messenger", fake)

    assert notifications.send_trade_notification("opened", {"pair": "BTC/ETH"}) is True
    assert fake.calls[-1] == ("trade_opened", {"pair": "BTC/ETH"})

    assert (
        notifications.send_trade_notification(
            "closed", {"pair": "BTC/ETH"}, reason="Manual close"
        )
        is True
    )
    assert fake.calls[-1] == ("trade_closed", {"pair": "BTC/ETH"}, "Manual close")

    assert notifications.send_trade_notification("paused", {}) is False
    assert fake.calls[-1][0] == "trade_closed"
