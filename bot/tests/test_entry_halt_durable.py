"""The entry halt has to outlive the process that set it.

It used to be one JSON file shared by every runtime in the bot-api pod, stored
in an ``emptyDir``: replacing the pod removed it, so a bot halted after a failed
emergency close would open new pairs again after any deploy.
"""

import asyncio
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.infrastructure import database
from src.trading import bot_agents_state, entry_halt, position_manager
from src.trading.entry_halt import HaltScope

_DDL = """
CREATE TABLE entry_halts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instance_id VARCHAR(64) NOT NULL,
  network VARCHAR(16) NOT NULL,
  address VARCHAR(128) NOT NULL,
  subaccount_number INTEGER NOT NULL DEFAULT 0,
  reason TEXT NOT NULL,
  details TEXT NOT NULL DEFAULT '{}',
  halted_at DATETIME NOT NULL,
  cleared_at DATETIME,
  cleared_by VARCHAR(128),
  clear_note TEXT
)
"""

BOT_1 = HaltScope("strategy-85-1", "testnet", "dydx1probe", 0)


@pytest.fixture
def store(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        connection.execute(text(_DDL))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX uq_entry_halts_active_scope ON entry_halts "
                "(network, address, subaccount_number) WHERE cleared_at IS NULL"
            )
        )
    monkeypatch.setattr(database.db, "get_session", sessionmaker(bind=engine))
    monkeypatch.setattr(
        bot_agents_state, "BOT_AGENTS_PATH", tmp_path / "bot_agents_x.json"
    )
    monkeypatch.setattr(entry_halt, "_runtime_scope", None)
    return engine


def _rows(engine):
    with engine.connect() as connection:
        return [
            dict(row._mapping)
            for row in connection.execute(text("SELECT * FROM entry_halts ORDER BY id"))
        ]


def _lose_the_pod(scope):
    """What replacing the bot-api pod does to the emptyDir."""
    entry_halt.halt_file_for(scope.instance_id).unlink()


def test_a_halt_survives_losing_the_pod(store):
    entry_halt.halt_entries(
        "emergency close failed for AVAX-USD / FIL-USD",
        {"market_1": "AVAX-USD", "market_2": "FIL-USD"},
        scope=BOT_1,
    )
    _lose_the_pod(BOT_1)

    halt = entry_halt.entries_halted(BOT_1)

    assert halt is not None
    assert halt["reason"] == "emergency close failed for AVAX-USD / FIL-USD"
    assert halt["details"] == {"market_1": "AVAX-USD", "market_2": "FIL-USD"}
    assert halt["instance_id"] == "strategy-85-1"
    assert "unverified" not in halt


def test_a_halt_covers_the_subaccount_and_nothing_else(store):
    entry_halt.halt_entries("leg may be open", scope=BOT_1)
    _lose_the_pod(BOT_1)

    same_subaccount = HaltScope("strategy-85-2", "testnet", "dydx1probe", 0)
    assert entry_halt.entries_halted(same_subaccount) is not None

    for elsewhere in (
        HaltScope("strategy-85-3", "testnet", "dydx1probe", 1),
        HaltScope("strategy-85-4", "mainnet", "dydx1probe", 0),
        HaltScope("strategy-99-1", "testnet", "dydx1other", 0),
    ):
        assert entry_halt.entries_halted(elsewhere) is None, elsewhere


def test_the_first_reason_is_kept(store):
    entry_halt.halt_entries("first failure", scope=BOT_1)
    entry_halt.halt_entries("second failure", scope=BOT_1)

    rows = _rows(store)
    assert [row["reason"] for row in rows] == ["first failure"]


def test_clearing_records_who_and_why_and_resumes_entries(store):
    entry_halt.halt_entries("leg may be open", scope=BOT_1)

    cleared = entry_halt.clear_entry_halt(
        cleared_by="chris", note="checked on chain: flat", scope=BOT_1
    )

    assert cleared == 1
    assert entry_halt.entries_halted(BOT_1) is None
    assert not entry_halt.halt_file_for("strategy-85-1").exists()
    (row,) = _rows(store)
    assert row["cleared_by"] == "chris"
    assert row["clear_note"] == "checked on chain: flat"
    assert row["cleared_at"] is not None

    # A later failure on the same subaccount latches again.
    entry_halt.halt_entries("another failure", scope=BOT_1)
    assert entry_halt.entries_halted(BOT_1)["reason"] == "another failure"
    assert len(_rows(store)) == 2


def test_clearing_when_nothing_is_set_reports_zero(store):
    assert entry_halt.clear_entry_halt(scope=BOT_1) == 0


def test_an_unreadable_table_means_halted_for_a_managed_runtime(store, monkeypatch):
    def _down():
        raise ConnectionError("database unavailable")

    monkeypatch.setattr(database.db, "get_session", _down)

    halt = entry_halt.entries_halted(BOT_1)

    assert halt == {
        "reason": entry_halt.UNVERIFIED_REASON,
        "details": {},
        "unverified": True,
    }


def test_the_file_holds_the_halt_when_the_database_is_down(store, monkeypatch):
    def _down():
        raise ConnectionError("database unavailable")

    monkeypatch.setattr(database.db, "get_session", _down)

    entry_halt.halt_entries("leg may be open", scope=BOT_1)

    halt = entry_halt.entries_halted(BOT_1)
    assert halt["reason"] == "leg may be open"
    assert (
        json.loads(entry_halt.halt_file_for("strategy-85-1").read_text())[
            "subaccount_number"
        ]
        == 0
    )


def test_a_halt_that_cannot_be_stored_anywhere_raises(store, monkeypatch):
    def _down():
        raise ConnectionError("database unavailable")

    def _read_only(_path, _payload):
        raise OSError("read-only file system")

    monkeypatch.setattr(database.db, "get_session", _down)
    monkeypatch.setattr(entry_halt, "_write_halt_file", _read_only)

    with pytest.raises(
        RuntimeError, match="could NOT be recorded.*read-only.*database unavailable"
    ):
        entry_halt.halt_entries("leg may be open", scope=BOT_1)


def test_a_standalone_run_never_needs_the_database(store, monkeypatch):
    def _must_not_be_called():
        raise AssertionError("a standalone run has no database")

    monkeypatch.setattr(database.db, "get_session", _must_not_be_called)
    standalone = HaltScope(
        entry_halt.STANDALONE_INSTANCE_ID, "testnet", "dydx1probe", 0
    )

    assert entry_halt.entries_halted(standalone) is None
    entry_halt.halt_entries("leg may be open", scope=standalone)
    assert entry_halt.entries_halted(standalone)["reason"] == "leg may be open"
    assert entry_halt.halt_file_for("default").name == "entries_halted.json"
    assert entry_halt.clear_entry_halt(scope=standalone) == 1


def test_open_positions_opens_nothing_on_an_unverified_halt(monkeypatch):
    def _must_not_load_pairs():
        raise AssertionError("no pair may be considered while the halt is unknown")

    monkeypatch.setattr(
        position_manager.entry_halt,
        "entries_halted",
        lambda: {"reason": entry_halt.UNVERIFIED_REASON, "unverified": True},
    )
    monkeypatch.setattr(
        position_manager.pair_storage, "load_pairs", _must_not_load_pairs
    )

    asyncio.run(position_manager.open_positions(object()))


def test_a_managed_runtime_halts_the_subaccount_of_its_own_instance_config(
    store, monkeypatch
):
    """The runtime's wallet comes from its instance config, not src.constants.

    If the latch were scoped from the global config, the API (which scopes by the
    instance's credentials) could neither show nor clear the halt.
    """
    from src import constants

    monkeypatch.setattr(constants, "DYDX_ADDRESS", "dydx1globalconfigwallet")
    monkeypatch.setattr(constants, "MARKET_DATA_MODE", "MAINNET")
    entry_halt.set_runtime_scope(HaltScope("strategy-85-1", "testnet", "dydx1probe", 0))

    entry_halt.halt_entries("emergency close failed")

    (row,) = _rows(store)
    assert (row["network"], row["address"], row["subaccount_number"]) == (
        "testnet",
        "dydx1probe",
        0,
    )
    # What the API builds from the instance's credentials finds that very halt.
    _lose_the_pod(BOT_1)
    api_scope = HaltScope("strategy-85-1", "testnet", "dydx1probe", 0)
    assert entry_halt.entries_halted(api_scope)["reason"] == "emergency close failed"
    assert entry_halt.clear_entry_halt(cleared_by="chris", scope=api_scope) == 1
    assert entry_halt.entries_halted() is None


def test_scope_spelling_cannot_split_one_subaccount_into_two(store):
    entry_halt.halt_entries(
        "emergency close failed",
        scope=HaltScope("strategy-85-1", "TESTNET", " DYDX1Probe ", 0),
    )
    _lose_the_pod(BOT_1)

    assert entry_halt.entries_halted(BOT_1)["reason"] == "emergency close failed"
