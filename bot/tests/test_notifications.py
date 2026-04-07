import importlib


def _load_notifications_module():
    return importlib.import_module("src.shared.notifications")


def test_startup_message_prefers_instance_account_address(monkeypatch):
    notifications = _load_notifications_module()
    messenger = notifications.TelegramMessenger()

    captured = {}

    def _fake_send_message(text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None):
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
    assert "https://www.mintscan.io/dydx-testnet/account/dydx16shv8n0j28djnjrcg0jxusmkf46umtzrepslsp" in captured["text"]
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

    def _fake_send_message(text, parse_mode="HTML", dedupe_key=None, dedupe_window_seconds=None):
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
