"""A shutdown signal must never abort a pair between its two legs."""

import asyncio
import importlib
import signal
from types import SimpleNamespace

import pytest

from src.trading import position_manager


@pytest.fixture(autouse=True)
def _fresh_entry_stop():
    position_manager.reset_entry_stop()
    yield
    position_manager.reset_entry_stop()


class _Messenger:
    def __init__(self):
        self.shutdown = []

    def send_shutdown_message(self, reason):
        self.shutdown.append(reason)

    def send_error_message(self, *args, **kwargs):
        raise AssertionError(f"unexpected error notification: {args}")


def _bot(**settings):
    main_instance = importlib.import_module("src.main_instance")
    bot = main_instance.BotInstance("bot-1")
    bot.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    bot.messenger = _Messenger()
    bot.client = object()
    bot.config = SimpleNamespace(
        botSettings=SimpleNamespace(
            manageExits=settings.get("manageExits", False),
            placeTrades=settings.get("placeTrades", True),
        )
    )
    return main_instance, bot


def _installed_handler(monkeypatch, bot):
    handlers = {}
    monkeypatch.setattr(signal, "signal", lambda sig, fn: handlers.__setitem__(sig, fn))
    bot.setup_signal_handlers()
    return handlers[signal.SIGTERM]


def test_first_signal_requests_a_stop_without_raising(monkeypatch):
    _main, bot = _bot()
    handler = _installed_handler(monkeypatch, bot)
    bot.running = True

    handler(signal.SIGTERM, None)  # must not raise into the running frame

    assert bot.running is False
    assert bot._shutdown_requested is True
    assert position_manager._ENTRY_STOP_REQUESTED is True


def test_second_signal_stops_immediately(monkeypatch):
    main_instance, bot = _bot()
    handler = _installed_handler(monkeypatch, bot)

    handler(signal.SIGTERM, None)
    with pytest.raises(main_instance.GracefulShutdownException):
        handler(signal.SIGTERM, None)


def test_signal_during_an_entry_lets_it_finish_and_opens_nothing_new(monkeypatch):
    main_instance, bot = _bot()
    handler = _installed_handler(monkeypatch, bot)
    events = []

    async def fake_open_positions(_client):
        events.append("entry-leg-1")
        handler(signal.SIGTERM, None)  # SIGTERM lands between the two legs
        events.append("entry-leg-2")

    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr(main_instance, "open_positions", fake_open_positions)
    monkeypatch.setattr(main_instance.asyncio, "sleep", fast_sleep)

    asyncio.run(bot.trading_loop())

    # The pair was completed, exactly one cycle ran, and the stop was reported.
    assert events == ["entry-leg-1", "entry-leg-2"]
    assert bot.messenger.shutdown and "bot-1" in bot.messenger.shutdown[0]


def test_shutdown_requested_during_startup_is_not_overwritten(monkeypatch):
    main_instance, bot = _bot()
    calls = []

    async def fake_open_positions(_client):
        calls.append("opened")

    monkeypatch.setattr(main_instance, "open_positions", fake_open_positions)
    bot.request_shutdown()

    asyncio.run(bot.trading_loop())

    assert calls == []


def test_entry_scan_stops_before_the_next_pair(monkeypatch):
    class _Pair:
        def __init__(self, payload):
            self._payload = payload

        def to_dict(self):
            return dict(self._payload)

    monkeypatch.setattr(
        position_manager.pair_storage,
        "load_pairs",
        lambda: [
            _Pair(
                {
                    "base_market": "DOT-USD",
                    "quote_market": "CRO-USD",
                    "hedge_ratio": 0.03,
                    "half_life": 10,
                }
            )
        ],
    )

    async def fake_get_markets(_client):
        return {"markets": {}}

    async def must_not_fetch(_client, _market):
        raise AssertionError("no pair may be evaluated after a shutdown request")

    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "get_candles_recent", must_not_fetch)
    monkeypatch.setattr(position_manager.entry_halt, "entries_halted", lambda: None)
    position_manager.request_entry_stop()

    asyncio.run(position_manager.open_positions(object()))
