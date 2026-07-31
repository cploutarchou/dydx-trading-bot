import importlib


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
