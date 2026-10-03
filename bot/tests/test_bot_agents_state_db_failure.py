"""A failed database write must never make reads lose tracked positions."""

import asyncio

import pytest

from src.trading import bot_agents_state as state


class _FlakyDatabase:
    """In-memory stand-in for the tracked_positions row."""

    def __init__(self):
        self.row = None
        self.fail_writes = False
        self.write_attempts = 0

    def load(self):
        return None if self.row is None else list(self.row)

    def save(self, positions):
        self.write_attempts += 1
        if self.fail_writes:
            return False
        self.row = list(positions)
        return True

    def delete(self):
        self.write_attempts += 1
        if self.fail_writes:
            return False
        self.row = None
        return True


@pytest.fixture
def database(monkeypatch, tmp_path):
    fake = _FlakyDatabase()
    monkeypatch.setattr(state, "BOT_AGENTS_PATH", tmp_path / "bot_agents.json")
    monkeypatch.setattr(state, "_db_load_positions", fake.load)
    monkeypatch.setattr(state, "_db_save_positions", fake.save)
    monkeypatch.setattr(state, "_db_delete_positions", fake.delete)
    return fake


def _position(market_1):
    return {
        "market_1": market_1,
        "market_2": "ETH-USD",
        "order_id_m1": f"{market_1}-m1",
        "order_id_m2": f"{market_1}-m2",
    }


def test_position_appended_during_a_database_outage_is_not_lost(database):
    asyncio.run(state.append_tracked_position(_position("BTC-USD")))
    database.fail_writes = True

    asyncio.run(state.append_tracked_position(_position("SOL-USD")))

    # The database row is now older than the file. Reading it would drop SOL.
    assert [p["market_1"] for p in database.row] == ["BTC-USD"]
    loaded = asyncio.run(state.load_tracked_positions())
    assert [p["market_1"] for p in loaded] == ["BTC-USD", "SOL-USD"]
    assert state._db_is_stale() is True


def test_next_successful_write_resynchronises_the_database(database):
    database.fail_writes = True
    asyncio.run(state.append_tracked_position(_position("BTC-USD")))
    database.fail_writes = False

    asyncio.run(state.append_tracked_position(_position("SOL-USD")))

    assert [p["market_1"] for p in database.row] == ["BTC-USD", "SOL-USD"]
    assert state._db_is_stale() is False


def test_stale_marker_survives_a_restart(database):
    database.fail_writes = True
    asyncio.run(state.append_tracked_position(_position("BTC-USD")))

    # A new process sees the marker on disk and keeps reading the file.
    assert state._db_stale_marker_path().exists()
    database.row = []  # whatever the database says is not trusted
    loaded = asyncio.run(state.load_tracked_positions())
    assert [p["market_1"] for p in loaded] == ["BTC-USD"]


def test_failed_delete_does_not_resurrect_closed_positions(database):
    asyncio.run(state.append_tracked_position(_position("BTC-USD")))
    database.fail_writes = True

    asyncio.run(state.clear_tracked_positions())

    assert database.row is not None  # the delete failed
    assert asyncio.run(state.load_tracked_positions()) == []


def test_healthy_database_stays_the_read_source(database):
    asyncio.run(state.append_tracked_position(_position("BTC-USD")))

    assert state._db_is_stale() is False
    assert [p["market_1"] for p in asyncio.run(state.load_tracked_positions())] == [
        "BTC-USD"
    ]
