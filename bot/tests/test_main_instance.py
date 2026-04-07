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
    bot.logger = SimpleNamespace(info=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
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

    monkeypatch.setattr(main_instance, "construct_market_prices", _fake_construct_market_prices)
    monkeypatch.setattr(main_instance, "store_cointegration_results", lambda _df: {"success": True})

    asyncio.run(bot.run_initial_setup())

    assert bot.messenger.errors == []


def test_run_initial_setup_raises_when_storage_reports_failure(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999")
    bot.logger = SimpleNamespace(info=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
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

    monkeypatch.setattr(main_instance, "construct_market_prices", _fake_construct_market_prices)
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
        raise AssertionError("run_initial_setup should raise when storage reports failure")

    assert len(bot.messenger.errors) == 1


def test_run_initial_setup_reports_exception_type_when_message_is_blank(monkeypatch):
    main_instance = _load_main_instance_module()
    bot = main_instance.BotInstance("strategy-1-999")
    bot.logger = SimpleNamespace(info=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
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

    monkeypatch.setattr(main_instance, "construct_market_prices", _fake_construct_market_prices)

    try:
        asyncio.run(bot.run_initial_setup())
    except BlankSetupError:
        pass
    else:
        raise AssertionError("run_initial_setup should raise original setup exception")

    assert len(bot.messenger.errors) == 1
    args, _kwargs = bot.messenger.errors[0]
    assert "BlankSetupError (no detail provided)" in args[1]
