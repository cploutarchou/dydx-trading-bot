"""New entries stop after a failed emergency close until an operator clears the latch."""

import asyncio

import pandas as pd
import pytest

from src.exceptions import UnhedgedExposureError
from src.trading import bot_agents_state, entry_halt, position_manager


class _Pair:
    def __init__(self, payload):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


@pytest.fixture
def instance_state(monkeypatch, tmp_path):
    """Point the per-instance state (and with it the latch) at a temp dir."""
    monkeypatch.setattr(
        bot_agents_state, "BOT_AGENTS_PATH", tmp_path / "bot_agents.json"
    )
    position_manager._ENTRY_FAILURE_STATE.clear()
    yield tmp_path
    # The failing agents above leave per-pair backoff entries behind; other
    # test modules scan the same pairs and would be skipped by the cooldown.
    position_manager._ENTRY_FAILURE_STATE.clear()


def _wire_two_pair_scan(monkeypatch, agent_cls):
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
            ),
            _Pair(
                {
                    "base_market": "XLM-USD",
                    "quote_market": "ZEN-USD",
                    "hedge_ratio": 0.04,
                    "half_life": 12,
                }
            ),
        ],
    )

    async def fake_get_markets(_client):
        market = {"tickSize": "0.0001", "stepSize": "1", "oraclePrice": "1.0"}
        return {
            "markets": {
                name: dict(market)
                for name in ("DOT-USD", "CRO-USD", "XLM-USD", "ZEN-USD")
            }
        }

    async def fake_get_candles_recent(_client, market):
        if market in {"DOT-USD", "XLM-USD"}:
            return pd.Series([1.2, 1.21, 1.22])
        return pd.Series([0.07, 0.068, 0.067])

    async def fake_is_open_positions(_client, _market):
        return False

    async def fake_get_account(_client):
        return {"freeCollateral": "10000"}

    monkeypatch.setattr(position_manager, "get_markets", fake_get_markets)
    monkeypatch.setattr(position_manager, "get_candles_recent", fake_get_candles_recent)
    monkeypatch.setattr(
        position_manager, "calculate_zscore", lambda _spread: pd.Series([2.0])
    )
    monkeypatch.setattr(position_manager, "is_open_positions", fake_is_open_positions)
    monkeypatch.setattr(position_manager, "get_account", fake_get_account)
    monkeypatch.setattr(position_manager, "BotAgent", agent_cls)


def test_latch_round_trip_and_first_reason_is_kept(instance_state):
    assert entry_halt.entries_halted() is None

    entry_halt.halt_entries("first failure", {"market_1": "BTC-USD"})
    entry_halt.halt_entries("second failure")

    state = entry_halt.entries_halted()
    assert state is not None
    assert state["reason"] == "first failure"
    assert state["details"] == {"market_1": "BTC-USD"}

    # clear_entry_halt() reports how many halts it cleared.
    assert entry_halt.clear_entry_halt() == 1
    assert entry_halt.entries_halted() is None
    assert entry_halt.clear_entry_halt() == 0


def test_unreadable_latch_still_halts(instance_state):
    (instance_state / entry_halt.HALT_FILE_NAME).write_text("{not json", "utf-8")

    assert entry_halt.entries_halted() is not None


def test_unhedged_exposure_halts_the_scan_and_later_cycles(monkeypatch, instance_state):
    constructed = []

    class UnhedgedAgent:
        def __init__(self, _client, **kwargs):
            constructed.append(kwargs.get("market_1"))

        async def open_trades(self):
            raise UnhedgedExposureError("Failed emergency closure for DOT-USD")

    _wire_two_pair_scan(monkeypatch, UnhedgedAgent)

    asyncio.run(position_manager.open_positions(object()))

    # The second pair in the same cycle must not be attempted.
    assert constructed == ["DOT-USD"]
    state = entry_halt.entries_halted()
    assert state is not None and "DOT-USD" in state["reason"]

    # Following cycles do not even load pairs.
    def _must_not_load():
        raise AssertionError("pairs must not be loaded while entries are halted")

    monkeypatch.setattr(position_manager.pair_storage, "load_pairs", _must_not_load)
    asyncio.run(position_manager.open_positions(object()))
    assert constructed == ["DOT-USD"]


def test_ordinary_entry_failure_does_not_halt(monkeypatch, instance_state):
    constructed = []

    class LaggingAgent:
        def __init__(self, _client, **kwargs):
            constructed.append(kwargs.get("market_1"))

        async def open_trades(self):
            raise RuntimeError("simulated indexer lag")

    _wire_two_pair_scan(monkeypatch, LaggingAgent)

    asyncio.run(position_manager.open_positions(object()))

    assert constructed == ["DOT-USD", "XLM-USD"]
    assert entry_halt.entries_halted() is None


def test_entries_resume_after_the_operator_clears_the_latch(
    monkeypatch, instance_state
):
    entry_halt.halt_entries("manual test")
    constructed = []

    class RecordingAgent:
        def __init__(self, _client, **kwargs):
            constructed.append(kwargs.get("market_1"))

        async def open_trades(self):
            raise RuntimeError("stop here")

    _wire_two_pair_scan(monkeypatch, RecordingAgent)

    asyncio.run(position_manager.open_positions(object()))
    assert constructed == []

    entry_halt.clear_entry_halt()
    asyncio.run(position_manager.open_positions(object()))
    assert constructed == ["DOT-USD", "XLM-USD"]


def test_operator_is_alerted_even_when_the_halt_cannot_be_stored(
    monkeypatch, instance_state
):
    """If neither latch store takes the halt, the alert is the only thing left
    between the operator and more entries, so it must still be sent and the
    scan must still stop."""
    constructed = []
    alerts = []

    class UnhedgedAgent:
        def __init__(self, _client, **kwargs):
            constructed.append(kwargs.get("market_1"))

        async def open_trades(self):
            raise UnhedgedExposureError("Failed emergency closure for DOT-USD")

    class RecordingMessenger:
        def send_error_message(self, title, message, **kwargs):
            alerts.append((title, message, kwargs))

    def _read_only(_path, _payload):
        raise OSError("read-only file system")

    _wire_two_pair_scan(monkeypatch, UnhedgedAgent)
    monkeypatch.setattr(position_manager, "TelegramMessenger", RecordingMessenger)
    monkeypatch.setattr(entry_halt, "_write_halt_file", _read_only)

    asyncio.run(position_manager.open_positions(object()))

    assert constructed == ["DOT-USD"]
    assert entry_halt.entries_halted() is None
    assert len(alerts) == 1
    title, message, kwargs = alerts[0]
    assert title == "CRITICAL: New entries halted"
    assert "could NOT be recorded" in message
    assert "read-only file system" in message
    assert kwargs["is_critical"] is True
