import pytest

from src.shared.notifications import TelegramMessenger


@pytest.fixture(autouse=True)
def _reset_dedupe_cache():
    TelegramMessenger._recent_messages.clear()


def test_send_message_deduplicates_with_window(monkeypatch):
    messenger = TelegramMessenger()
    messenger.enabled = True
    messenger.chat_id = "1"

    calls = {"count": 0}

    def _fake_send(_method, _data):
        calls["count"] += 1
        return True

    monkeypatch.setattr(messenger, "_send_request", _fake_send)

    assert messenger.send_message("hello", dedupe_key="k1", dedupe_window_seconds=60) is True
    assert messenger.send_message("hello", dedupe_key="k1", dedupe_window_seconds=60) is False
    assert calls["count"] == 1


def test_send_error_message_escapes_html_and_adds_context(monkeypatch):
    monkeypatch.setenv("BOT_INSTANCE_ID", "bot-1")
    monkeypatch.setenv("ENVIRONMENT", "development")

    messenger = TelegramMessenger()
    messenger.enabled = True

    captured = {"text": ""}

    def _fake_send_message(text, **_kwargs):
        captured["text"] = text
        return True

    monkeypatch.setattr(messenger, "send_message", _fake_send_message)

    assert (
        messenger.send_error_message("Bad <Type>", "failed with <raw> payload", is_critical=False)
        is True
    )
    assert "Bad &lt;Type&gt;" in captured["text"]
    assert "failed with &lt;raw&gt; payload" in captured["text"]
    assert "<b>Instance:</b> bot-1" in captured["text"]


def test_noncritical_error_dedupes_by_category(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ERROR_DEDUPE_SECONDS_DEFAULT", "60")

    messenger = TelegramMessenger()
    messenger.enabled = True
    messenger.chat_id = "1"

    calls = {"count": 0}

    def _fake_send(_method, _data):
        calls["count"] += 1
        return True

    monkeypatch.setattr(messenger, "_send_request", _fake_send)

    assert messenger.send_error_message("Trade Entry Error", "leg-1 failed", category="execution") is True
    assert messenger.send_error_message("Trade Entry Error", "leg-2 failed", category="execution") is False
    assert calls["count"] == 1


def test_critical_errors_send_immediately_by_default(monkeypatch):
    messenger = TelegramMessenger()
    messenger.enabled = True
    messenger.chat_id = "1"

    calls = {"count": 0}

    def _fake_send(_method, _data):
        calls["count"] += 1
        return True

    monkeypatch.setattr(messenger, "_send_request", _fake_send)

    assert messenger.send_error_message("Critical Failure", "first", is_critical=True) is True
    assert messenger.send_error_message("Critical Failure", "second", is_critical=True) is True
    assert calls["count"] == 2


def test_error_category_env_override_applies(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ERROR_DEDUPE_SECONDS_DEFAULT", "120")
    monkeypatch.setenv("TELEGRAM_ERROR_DEDUPE_SECONDS_EXECUTION", "5")

    messenger = TelegramMessenger()
    messenger.enabled = True

    captured = {"window": None, "key": ""}

    def _fake_send_message(_text, **kwargs):
        captured["window"] = kwargs.get("dedupe_window_seconds")
        captured["key"] = kwargs.get("dedupe_key", "")
        return True

    monkeypatch.setattr(messenger, "send_message", _fake_send_message)

    assert messenger.send_error_message("Trade Error", "details", category="execution") is True
    assert captured["window"] == 5
    assert captured["key"] == "error:normal:execution"


def test_send_message_truncates_long_payload(monkeypatch):
    messenger = TelegramMessenger()
    messenger.enabled = True
    messenger.chat_id = "1"

    captured = {"text": ""}

    def _fake_send(_method, data):
        captured["text"] = data["text"]
        return True

    monkeypatch.setattr(messenger, "_send_request", _fake_send)

    huge_text = "x" * 5000
    assert messenger.send_message(huge_text) is True
    assert len(captured["text"]) < 4100
    assert "[message truncated]" in captured["text"]

