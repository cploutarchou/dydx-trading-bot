import asyncio
import importlib
from types import SimpleNamespace

import pytest


def _load_main_instance_module():
    return importlib.import_module("src.main_instance")


class _FakeMessenger:
    def __init__(self):
        self.errors = []

    def send_error_message(self, *args, **kwargs):
        self.errors.append((args, kwargs))


def test_run_initial_setup_accepts_dict_success(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None
    )
    bot.messenger = _FakeMessenger()
    bot.client = object()
    bot.config = SimpleNamespace(
        botSettings=SimpleNamespace(
            abortAllPositions=False,
            findCointegratedPairs=True,
        )
    )

    async def _fake_construct_market_prices(_client):
        return "prices"

    monkeypatch.setattr(
        main_instance, "construct_market_prices", _fake_construct_market_prices
    )
    monkeypatch.setattr(
        main_instance, "store_cointegration_results", lambda _df: {"success": True}
    )

    asyncio.run(bot.run_initial_setup())

    assert bot.messenger.errors == []


def test_run_initial_setup_raises_when_storage_reports_failure(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None
    )
    bot.messenger = _FakeMessenger()
    bot.client = object()
    bot.config = SimpleNamespace(
        botSettings=SimpleNamespace(
            abortAllPositions=False,
            findCointegratedPairs=True,
        )
    )

    async def _fake_construct_market_prices(_client):
        return "prices"

    monkeypatch.setattr(
        main_instance, "construct_market_prices", _fake_construct_market_prices
    )
    monkeypatch.setattr(
        main_instance,
        "store_cointegration_results",
        lambda _df: {"success": False, "error": "disk full"},
    )

    try:
        asyncio.run(bot.run_initial_setup())
    except RuntimeError as exc:
        assert "Failed to save cointegration results: disk full" in str(exc)
    else:
        raise AssertionError(
            "run_initial_setup should raise when storage reports failure"
        )

    assert len(bot.messenger.errors) == 1


def test_run_initial_setup_reports_exception_type_when_message_is_blank(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None
    )
    bot.messenger = _FakeMessenger()
    bot.client = object()
    bot.config = SimpleNamespace(
        botSettings=SimpleNamespace(
            abortAllPositions=False,
            findCointegratedPairs=True,
        )
    )

    class BlankSetupError(Exception):
        def __str__(self):
            return ""

    async def _fake_construct_market_prices(_client):
        raise BlankSetupError()

    monkeypatch.setattr(
        main_instance, "construct_market_prices", _fake_construct_market_prices
    )

    try:
        asyncio.run(bot.run_initial_setup())
    except BlankSetupError:
        pass
    else:
        raise AssertionError("run_initial_setup should raise original setup exception")

    assert len(bot.messenger.errors) == 1
    args, _kwargs = bot.messenger.errors[0]
    assert "BlankSetupError (no detail provided)" in args[1]


def _sample_db_runtime_config(selected_markets):
    return {
        "instance_name": "Runtime Strategy",
        "credentials": {
            "chain_id": "dydx-testnet-4",
            "address": "dydx1testaddress",
            "mnemonic": "test mnemonic",
        },
        "telegram": {"token": "", "chat_id": ""},
        "trading_params": {
            "is_testnet": True,
            "subaccount_number": 0,
            "capital_allocation_usd": 0.0,
            "find_cointegrated_pairs": False,
            "manage_exits": False,
            "place_trades": False,
            "abort_all_positions": False,
            "resolution_timeframe": "5MINS",
            "strategy": "cointegration",
            "stats_window": 21,
            "max_half_life": 24,
            "zscore_threshold": 1.5,
            "usd_per_trade": 10.0,
            "usd_min_collateral": 100.0,
            "close_at_zscore_cross": True,
            "max_positions": 5,
            "max_drawdown_pct": 0.0,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
            "trailing_stop_pct": 0.0,
            "rebalance_interval_hours": 24,
            "position_timeout_hours": 72,
            "selected_markets": selected_markets,
        },
        "backtesting_params": {},
    }


def test_load_config_uses_database_contract(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    db_payload = _sample_db_runtime_config(["ETH-USD", "AVAX-USD"])

    monkeypatch.setattr(bot, "_load_config_data_from_db", lambda: db_payload)

    bot.load_config()

    assert bot.config.botSettings.selectedMarkets == ["ETH-USD", "AVAX-USD"]
    assert bot.config.botSettings.resolutionTimeframe == "5MINS"


def test_load_config_fast_fails_when_db_missing(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999", config_file="/tmp/ignored.yaml")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(bot, "_load_config_data_from_db", lambda: None)

    with pytest.raises(RuntimeError, match="DB-backed runtime config is required"):
        bot.load_config()


def test_load_config_warns_when_deprecated_config_path_is_supplied(monkeypatch):
    main_instance = _load_main_instance_module()
    warning_messages = []
    bot = main_instance.BotInstance("strategy-1-999", config_file="/tmp/ignored.yaml")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: warning_messages.append(
            args[0] if args else ""
        ),
        error=lambda *args, **kwargs: None,
    )

    db_payload = _sample_db_runtime_config(["ETH-USD", "AVAX-USD"])

    monkeypatch.setattr(bot, "_load_config_data_from_db", lambda: db_payload)

    bot.load_config()

    assert any("Ignoring deprecated runtime config file path" in msg for msg in warning_messages)


def test_load_config_warns_when_db_metadata_hash_is_stale(monkeypatch):
    main_instance = _load_main_instance_module()
    warning_messages = []
    bot = main_instance.BotInstance("strategy-1-999", config_file="/tmp/ignored.yaml")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: warning_messages.append(
            args[0] if args else ""
        ),
        error=lambda *args, **kwargs: None,
    )

    db_payload = _sample_db_runtime_config(["ETH-USD", "AVAX-USD"])
    db_payload["_config_meta"] = {"payload_hash": "deadbeef"}

    monkeypatch.setattr(bot, "_load_config_data_from_db", lambda: db_payload)

    bot.load_config()

    assert any(
        "Runtime config metadata hash mismatch" in msg for msg in warning_messages
    )
