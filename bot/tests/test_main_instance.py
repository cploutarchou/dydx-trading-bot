import asyncio
import importlib
from types import SimpleNamespace


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


def _sample_runtime_config(selected_markets):
    return {
        "is_testnet": True,
        "environment": "development",
        "telegram": {"token": "", "chat_id": ""},
        "botSettings": {
            "strategy": "cointegration",
            "resolutionTimeframe": "5MINS",
            "selectedMarkets": selected_markets,
        },
        "dydx_testnet": {
            "dydx_chain_address": "dydx1testaddress",
            "dydx_chain_secret": "test mnemonic",
        },
        "dydx_mainnet": {"dydx_chain_address": "", "dydx_chain_secret": ""},
    }


def test_load_config_prefers_database_over_file(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999", config_file="/tmp/ignored.yaml")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    db_payload = _sample_runtime_config(["ETH-USD", "AVAX-USD"])
    file_payload = _sample_runtime_config(["BTC-USD"])
    cache_refresh_calls = []

    monkeypatch.setattr(bot, "_load_config_data_from_db", lambda: db_payload)
    monkeypatch.setattr(bot, "_load_config_data_from_file", lambda: file_payload)
    monkeypatch.setattr(
        bot,
        "_refresh_config_file_cache",
        lambda payload: cache_refresh_calls.append(payload),
    )

    bot.load_config()

    assert bot.config.botSettings.selectedMarkets == ["ETH-USD", "AVAX-USD"]
    assert bot.config.botSettings.resolutionTimeframe == "5MINS"
    assert len(cache_refresh_calls) == 1


def test_load_config_falls_back_to_file_when_db_missing(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999", config_file="/tmp/ignored.yaml")
    bot.logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    file_payload = _sample_runtime_config(["BTC-USD", "ETH-USD"])
    cache_refresh_calls = []

    monkeypatch.setattr(bot, "_load_config_data_from_db", lambda: None)
    monkeypatch.setattr(bot, "_load_config_data_from_file", lambda: file_payload)
    monkeypatch.setattr(
        bot,
        "_refresh_config_file_cache",
        lambda payload: cache_refresh_calls.append(payload),
    )

    bot.load_config()

    assert bot.config.botSettings.selectedMarkets == ["BTC-USD", "ETH-USD"]
    assert bot.config.botSettings.resolutionTimeframe == "5MINS"
    assert cache_refresh_calls == []


def test_load_config_warns_when_db_and_file_hashes_differ(monkeypatch):
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

    db_payload = _sample_runtime_config(["ETH-USD", "AVAX-USD"])
    file_payload = _sample_runtime_config(["BTC-USD", "ETH-USD"])

    monkeypatch.setattr(bot, "_load_config_data_from_db", lambda: db_payload)
    monkeypatch.setattr(bot, "_load_config_data_from_file", lambda: file_payload)
    monkeypatch.setattr(bot, "_refresh_config_file_cache", lambda _payload: None)

    bot.load_config()

    assert any("Runtime config cache drift detected" in msg for msg in warning_messages)


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

    db_payload = _sample_runtime_config(["ETH-USD", "AVAX-USD"])
    db_payload["_config_meta"] = {"payload_hash": "deadbeef"}

    monkeypatch.setattr(bot, "_load_config_data_from_db", lambda: db_payload)
    monkeypatch.setattr(bot, "_load_config_data_from_file", lambda: db_payload)
    monkeypatch.setattr(bot, "_refresh_config_file_cache", lambda _payload: None)

    bot.load_config()

    assert any(
        "Runtime config metadata hash mismatch" in msg for msg in warning_messages
    )
