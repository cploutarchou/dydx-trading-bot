"""Bot-level max drawdown: halt new entries once the account fell too far.

The drawdown is measured on the equity of the subaccount a runtime trades on,
from the highest equity seen since the measurement began. Reaching the limit
latches the durable entry halt; open pairs are not closed. The peak has to
outlive the process, a clear has to start the measurement again, and anything
that makes the drawdown unknown has to keep entries shut.
"""

import asyncio

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.infrastructure import database
from src.trading import bot_agents_state, drawdown_guard, entry_halt, position_manager
from src.trading.entry_halt import HaltScope
from tests.test_entry_halt_durable import _DDL as ENTRY_HALTS_DDL

DRAWDOWN_PEAKS_DDL = """
CREATE TABLE drawdown_peaks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instance_id VARCHAR(64) NOT NULL,
  network VARCHAR(16) NOT NULL,
  address VARCHAR(128) NOT NULL,
  subaccount_number INTEGER NOT NULL DEFAULT 0,
  peak_equity FLOAT NOT NULL,
  peak_at DATETIME NOT NULL,
  baseline_at DATETIME NOT NULL,
  tripped_at DATETIME,
  updated_at DATETIME NOT NULL
)
"""

BOT = HaltScope("strategy-85-3", "testnet", "dydx1probe", 0)


class _Messenger:
    def __init__(self):
        self.errors = []

    def send_error_message(self, title, message, **kwargs):
        self.errors.append((title, message, kwargs))


class _Account:
    def __init__(self, equity):
        self.equity = equity
        self.error = None
        self.reads = 0

    async def read(self, _client):
        self.reads += 1
        if self.error is not None:
            raise self.error
        return {"equity": str(self.equity), "freeCollateral": "1000"}


@pytest.fixture
def store(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        connection.execute(text(ENTRY_HALTS_DDL))
        connection.execute(text(DRAWDOWN_PEAKS_DDL))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX uq_drawdown_peaks_scope ON drawdown_peaks "
                "(instance_id, network, address, subaccount_number)"
            )
        )
    monkeypatch.setattr(database.db, "get_session", sessionmaker(bind=engine))
    monkeypatch.setattr(
        bot_agents_state, "BOT_AGENTS_PATH", tmp_path / "bot_agents_x.json"
    )
    monkeypatch.setattr(entry_halt, "_runtime_scope", BOT)
    events = []
    monkeypatch.setattr(
        drawdown_guard,
        "persist_trade_activity_event",
        lambda event_type, message, **kwargs: events.append(
            (event_type, message, kwargs)
        ),
    )
    engine.events = events
    return engine


def _peaks(engine):
    with engine.connect() as connection:
        return [
            dict(row._mapping)
            for row in connection.execute(
                text("SELECT * FROM drawdown_peaks ORDER BY id")
            )
        ]


def _check(account, messenger, *, limit=2.0):
    return asyncio.run(
        drawdown_guard.check_entry_drawdown(
            object(),
            limit_pct=limit,
            messenger=messenger,
            scan_cycle_id="cycle-1",
            read_account=account.read,
        )
    )


def test_reaching_the_limit_is_a_breach_and_equity_above_the_peak_is_no_drawdown():
    at_limit = drawdown_guard.evaluate_drawdown(
        equity=980.0, peak_equity=1000.0, limit_pct=2.0
    )
    under = drawdown_guard.evaluate_drawdown(
        equity=980.1, peak_equity=1000.0, limit_pct=2.0
    )
    above = drawdown_guard.evaluate_drawdown(
        equity=1200.0, peak_equity=1000.0, limit_pct=2.0
    )

    assert (at_limit.allowed, round(at_limit.drawdown_pct, 6)) == (False, 2.0)
    assert under.allowed is True
    assert (above.allowed, above.drawdown_pct) == (True, 0.0)
    with pytest.raises(ValueError):
        drawdown_guard.evaluate_drawdown(equity=1.0, peak_equity=0.0, limit_pct=2.0)


def test_with_the_limit_at_zero_nothing_is_read_or_stored(monkeypatch):
    def _no_database():
        raise AssertionError("the database must not be touched")

    monkeypatch.setattr(database.db, "get_session", _no_database)
    account = _Account(1000.0)

    assert _check(account, _Messenger(), limit=0.0) is True
    assert account.reads == 0


def test_the_peak_starts_at_the_first_equity_and_only_moves_up(store):
    account, messenger = _Account(1000.0), _Messenger()

    assert _check(account, messenger) is True
    account.equity = 1100.0
    assert _check(account, messenger) is True
    account.equity = 1090.0
    assert _check(account, messenger) is True

    (row,) = _peaks(store)
    assert row["peak_equity"] == 1100.0
    assert row["tripped_at"] is None
    assert entry_halt.entries_halted(BOT) is None
    assert messenger.errors == []


def test_reaching_the_limit_halts_new_entries_and_says_why(store):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)

    account.equity = 979.0
    assert _check(account, messenger) is False

    halt = entry_halt.entries_halted(BOT)
    assert halt is not None
    assert entry_halt.halt_kind(halt) == entry_halt.KIND_MAX_DRAWDOWN
    assert halt["details"]["peak_equity"] == 1000.0
    assert halt["details"]["equity"] == 979.0
    assert halt["details"]["drawdown_pct"] == pytest.approx(2.1)
    assert "max drawdown reached" in halt["reason"]
    (row,) = _peaks(store)
    assert row["tripped_at"] is not None
    ((title, message, kwargs),) = messenger.errors
    assert title == "CRITICAL: New entries halted (max drawdown)"
    assert kwargs["is_critical"] is True
    assert "open positions keep their exits" in message
    ((event_type, _message, event),) = store.events
    assert event_type == "trade_entries_halted"
    assert event["details"]["kind"] == "max_drawdown"


def test_the_peak_survives_a_restart_and_a_lost_pod(store):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)

    # A replaced pod loses bot_states/ (an emptyDir); the peak is in the table.
    for path in bot_agents_state.BOT_AGENTS_PATH.parent.iterdir():
        path.unlink()
    account.equity = 979.0

    assert _check(account, messenger) is False
    assert entry_halt.entries_halted(BOT) is not None


def test_clearing_the_halt_measures_again_from_current_equity(store):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)
    account.equity = 979.0
    _check(account, messenger)

    cleared = entry_halt.clear_entry_halt(
        cleared_by="ops", note="reviewed the account", scope=BOT
    )

    assert cleared == 1
    assert _peaks(store) == []
    # No immediate re-halt from the old peak: 979 is the new starting point.
    assert _check(account, messenger) is True
    account.equity = 975.0
    assert _check(account, messenger) is True
    (row,) = _peaks(store)
    assert row["peak_equity"] == 979.0
    assert entry_halt.entries_halted(BOT) is None


def test_clearing_another_kind_of_halt_leaves_the_peak_alone(store):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)
    entry_halt.halt_entries(
        "emergency close failed for AVAX-USD / FIL-USD",
        {"kind": entry_halt.KIND_UNHEDGED_EXPOSURE},
        scope=BOT,
    )

    entry_halt.clear_entry_halt(cleared_by="ops", scope=BOT)

    (row,) = _peaks(store)
    assert row["peak_equity"] == 1000.0
    account.equity = 979.0
    assert _check(account, messenger) is False


def test_a_drawdown_halt_is_not_cleared_when_the_reset_cannot_be_stored(
    store, monkeypatch
):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)
    account.equity = 979.0
    _check(account, messenger)

    def _reset_fails(_scope):
        raise OperationalError("DELETE", {}, Exception("database is down"))

    monkeypatch.setattr(drawdown_guard, "reset_baselines", _reset_fails)

    with pytest.raises(OperationalError):
        entry_halt.clear_entry_halt(cleared_by="ops", scope=BOT)
    assert entry_halt.entries_halted(BOT) is not None


def test_a_halt_that_disappeared_without_a_clear_is_set_again(store):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)
    account.equity = 979.0
    _check(account, messenger)

    # The halt never reached the database and the pod holding its file is gone.
    with store.begin() as connection:
        connection.execute(text("DELETE FROM entry_halts"))
    entry_halt.halt_file_for(BOT.instance_id).unlink()
    # Equity even came back: without an operator clear, entries stay halted.
    account.equity = 1000.0

    assert _check(account, messenger) is False
    halt = entry_halt.entries_halted(BOT)
    assert halt is not None
    assert halt["details"]["reasserted"] is True
    assert "no operator has cleared it" in halt["reason"]


def test_a_halt_that_could_not_be_stored_never_restarts_the_measurement(
    store, monkeypatch
):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)
    persist_halt = entry_halt.halt_entries

    def _cannot_persist(reason, details=None, *, scope=None):
        raise RuntimeError("the entry halt could NOT be recorded (database: down)")

    monkeypatch.setattr(entry_halt, "halt_entries", _cannot_persist)
    account.equity = 979.0

    assert _check(account, messenger) is False
    assert _check(account, messenger) is False
    (row,) = _peaks(store)
    assert (row["peak_equity"], row["tripped_at"]) == (1000.0, None)
    # The critical alert names the failure, once per interval.
    assert len(messenger.errors) == 1
    assert "could NOT be recorded" in messenger.errors[0][1]

    # Once the halt can be stored, the next cycle sets it, still measured from
    # the original peak.
    monkeypatch.setattr(entry_halt, "halt_entries", persist_halt)
    assert _check(account, messenger) is False
    assert entry_halt.entries_halted(BOT) is not None


def test_an_unreadable_equity_keeps_entries_shut_and_alerts_once(store):
    account, messenger = _Account(1000.0), _Messenger()
    account.error = httpx.ConnectError("indexer unreachable")

    assert _check(account, messenger) is False
    assert _check(account, messenger) is False

    assert len(messenger.errors) == 1
    title, message, kwargs = messenger.errors[0]
    assert title == "Entries paused: drawdown cannot be measured"
    assert kwargs["is_critical"] is False
    assert _peaks(store) == []


@pytest.mark.parametrize("equity", [0.0, -5.0, "nan"])
def test_a_non_positive_or_unusable_equity_keeps_entries_shut(store, equity):
    assert _check(_Account(equity), _Messenger()) is False
    assert _peaks(store) == []


def test_an_unreadable_peak_keeps_entries_shut(store, monkeypatch):
    def _down():
        raise OperationalError("SELECT", {}, Exception("database is down"))

    monkeypatch.setattr(database.db, "get_session", _down)

    assert _check(_Account(1000.0), _Messenger()) is False


def test_each_runtime_and_subaccount_has_its_own_peak(store, monkeypatch):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)

    other_subaccount = HaltScope("strategy-85-3", "testnet", "dydx1probe", 2)
    monkeypatch.setattr(entry_halt, "_runtime_scope", other_subaccount)
    account.equity = 500.0
    assert _check(account, messenger) is True

    peaks = {row["subaccount_number"]: row["peak_equity"] for row in _peaks(store)}
    assert peaks == {0: 1000.0, 2: 500.0}


def test_a_standalone_run_keeps_its_peak_in_a_file(store, monkeypatch):
    standalone = HaltScope("default", "testnet", "dydx1probe", 0)
    monkeypatch.setattr(entry_halt, "_runtime_scope", standalone)

    def _no_database():
        raise AssertionError("a standalone run has no database")

    monkeypatch.setattr(database.db, "get_session", _no_database)
    account, messenger = _Account(1000.0), _Messenger()

    assert _check(account, messenger) is True
    assert drawdown_guard.state_file_for("default").exists()
    account.equity = 979.0
    assert _check(account, messenger) is False
    assert entry_halt.entries_halted(standalone) is not None

    assert entry_halt.clear_entry_halt(cleared_by="cli", scope=standalone) == 1
    assert not drawdown_guard.state_file_for("default").exists()
    assert _check(account, messenger) is True


def test_open_positions_opens_nothing_once_the_limit_is_reached(store, monkeypatch):
    account = _Account(1000.0)
    monkeypatch.setattr(position_manager, "MAX_DRAWDOWN_PCT", 2.0)
    monkeypatch.setattr(position_manager, "get_account", account.read)
    monkeypatch.setattr(position_manager, "TelegramMessenger", _Messenger)
    loaded = []
    monkeypatch.setattr(
        position_manager.pair_storage, "load_pairs", lambda: loaded.append(1) or []
    )

    asyncio.run(position_manager.open_positions(object()))
    assert loaded == [1]

    account.equity = 979.0
    asyncio.run(position_manager.open_positions(object()))
    asyncio.run(position_manager.open_positions(object()))

    # The breach cycle and every cycle after it stop before any pair is read.
    assert loaded == [1]
    assert entry_halt.entries_halted(BOT) is not None


def test_the_preflight_statement_reads_the_recorded_peak(store):
    account, messenger = _Account(1000.0), _Messenger()
    _check(account, messenger)

    fresh = drawdown_guard.preflight_drawdown_warning(
        HaltScope("strategy-85-9", "testnet", "dydx1probe", 0),
        equity=1000.0,
        limit_pct=2.0,
    )
    recorded = drawdown_guard.preflight_drawdown_warning(
        BOT, equity=985.0, limit_pct=2.0
    )
    breached = drawdown_guard.preflight_drawdown_warning(
        BOT, equity=979.0, limit_pct=2.0
    )

    assert "$20.00 below its peak" in fresh
    assert "peak $1,000.00" in recorded and "halt below $980.00" in recorded
    assert "halts new entries on its first cycle" in breached
    assert (
        drawdown_guard.preflight_drawdown_warning(BOT, equity=979.0, limit_pct=0.0)
        is None
    )
