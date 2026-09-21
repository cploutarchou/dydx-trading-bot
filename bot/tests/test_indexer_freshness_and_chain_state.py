"""The runtime must not open pairs on a stale indexer, and must be able to ask
the chain itself whether a market is flat.

Both come from the 2026-09-21 staging incident: the public dYdX testnet indexer
was 19 hours behind, so a bot could not find the order it had just placed and
raised a critical "leg may be open" alert for a position that never existed.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.trading import account_manager, indexer_freshness, position_manager

NOW = datetime(2026, 9, 21, 17, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _guard_enabled(monkeypatch):
    # conftest pins the guard off for the rest of the suite; these tests want
    # the shipped behaviour.
    monkeypatch.delenv(indexer_freshness.ENV_MAX_LAG_SECONDS, raising=False)


def test_the_guard_is_on_by_default():
    assert indexer_freshness.max_lag_seconds() == 120.0


def _client_with_indexer_height(payload):
    async def get_height():
        if isinstance(payload, Exception):
            raise payload
        return payload

    return SimpleNamespace(
        indexer=SimpleNamespace(utility=SimpleNamespace(get_height=get_height))
    )


def _check(payload, **env):
    return asyncio.run(
        indexer_freshness.check_indexer_freshness(
            _client_with_indexer_height(payload), now=NOW
        )
    )


def test_a_current_indexer_does_not_block_entries():
    fresh = {"height": "100", "time": (NOW - timedelta(seconds=5)).isoformat()}

    assert _check(fresh) is None


def test_a_stale_indexer_blocks_entries_and_says_how_stale():
    stale = {"height": "86810091", "time": "2026-09-20T22:06:30.697Z"}

    staleness = _check(stale)

    assert staleness is not None
    assert staleness.lag_seconds == pytest.approx(18 * 3600 + 53 * 60 + 29.303)
    assert "18.9 h behind" in staleness.describe()
    assert "86810091" in staleness.describe()


def test_an_unreadable_indexer_height_blocks_entries():
    for payload in (
        ConnectionError("down"),
        {"height": "1"},
        {"time": "garbage"},
        None,
    ):
        staleness = _check(payload)

        assert staleness is not None, payload
        assert staleness.lag_seconds is None
        assert "could not be verified" in staleness.describe()


def test_the_check_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("BOT_INDEXER_MAX_LAG_SECONDS", "0")

    assert _check({"height": "1", "time": "2020-01-01T00:00:00Z"}) is None


def test_the_limit_is_configurable(monkeypatch):
    five_minutes_old = {"height": "1", "time": (NOW - timedelta(minutes=5)).isoformat()}

    assert _check(five_minutes_old) is not None
    monkeypatch.setenv("BOT_INDEXER_MAX_LAG_SECONDS", "600")
    assert _check(five_minutes_old) is None


def test_the_operator_alert_is_rate_limited(monkeypatch):
    monkeypatch.setattr(indexer_freshness, "_last_alert_at", None)

    assert indexer_freshness.should_alert(now=NOW) is True
    assert indexer_freshness.should_alert(now=NOW + timedelta(minutes=10)) is False
    assert indexer_freshness.should_alert(now=NOW + timedelta(minutes=31)) is True


def test_open_positions_opens_nothing_while_the_indexer_is_stale(monkeypatch):
    alerts = []

    class RecordingMessenger:
        def send_error_message(self, title, details, is_critical=False, category=None):
            alerts.append((title, is_critical))

    def _must_not_load_pairs():
        raise AssertionError("no pair may be considered on a stale indexer")

    monkeypatch.setattr(position_manager.entry_halt, "entries_halted", lambda: None)
    monkeypatch.setattr(position_manager, "TelegramMessenger", RecordingMessenger)
    monkeypatch.setattr(
        position_manager.pair_storage, "load_pairs", _must_not_load_pairs
    )
    monkeypatch.setattr(indexer_freshness, "_last_alert_at", None)
    stale = {"height": "86810091", "time": "2026-09-20T22:06:30.697Z"}

    asyncio.run(position_manager.open_positions(_client_with_indexer_height(stale)))
    asyncio.run(position_manager.open_positions(_client_with_indexer_height(stale)))

    # Blocked both cycles, reported once, and never as a critical alert.
    assert alerts == [("Entries paused: dYdX indexer is stale", False)]


# --- the chain's own answer ---------------------------------------------------


def _chain_client(*, heights, positions, clob_pair_perpetual_id=7, fail=None):
    remaining = list(heights)

    async def latest_block_height():
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    async def get_clob_pair(pair_id):
        assert pair_id == 7
        if fail == "clob_pair":
            raise ConnectionError("node down")
        return SimpleNamespace(
            perpetual_clob_metadata=SimpleNamespace(perpetual_id=clob_pair_perpetual_id)
        )

    async def get_subaccount(address, number):
        assert (address, number) == ("dydx1probe", 0)
        return SimpleNamespace(
            perpetual_positions=[
                SimpleNamespace(perpetual_id=pid, quantums_decoded=quantums)
                for pid, quantums in positions.items()
            ]
        )

    return SimpleNamespace(
        node=SimpleNamespace(
            latest_block_height=latest_block_height,
            get_clob_pair=get_clob_pair,
            get_subaccount=get_subaccount,
        )
    )


def _verify(monkeypatch, client, **kwargs):
    async def fake_markets(_client, ticker):
        return {"markets": {ticker: {"clobPairId": "7"}}}

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(
        account_manager, "_get_perpetual_markets_with_metrics", fake_markets
    )
    monkeypatch.setattr(
        account_manager, "_resolve_client_address", lambda _c: "dydx1probe"
    )
    monkeypatch.setattr(account_manager, "_resolve_subaccount_number", lambda: 0)
    monkeypatch.setattr(account_manager.asyncio, "sleep", _fast_sleep)
    return asyncio.run(
        account_manager.verify_flat_on_chain(
            client, "AVAX-USD", not_before_height=1011, **kwargs
        )
    )


def test_flat_on_chain_when_the_node_lists_no_position_in_the_market(monkeypatch):
    # The real account on 2026-09-21: nine old positions, none of them AVAX (7).
    client = _chain_client(heights=[1012], positions={0: 1000000, 4: 4000000})

    assert _verify(monkeypatch, client) is True


def test_not_flat_when_the_node_lists_a_position_in_the_market(monkeypatch):
    client = _chain_client(heights=[1012], positions={7: 800000})

    assert _verify(monkeypatch, client) is False


def test_the_read_waits_for_the_entry_order_to_expire(monkeypatch):
    client = _chain_client(heights=[1009, 1011, 1012], positions={})

    assert _verify(monkeypatch, client) is True


def test_not_flat_when_the_chain_never_passes_the_expiry_height(monkeypatch):
    client = _chain_client(heights=[1005], positions={})

    assert _verify(monkeypatch, client, max_wait_seconds=0.0) is False


def test_not_flat_when_the_chain_cannot_be_read(monkeypatch):
    client = _chain_client(heights=[1012], positions={}, fail="clob_pair")

    assert _verify(monkeypatch, client) is False
