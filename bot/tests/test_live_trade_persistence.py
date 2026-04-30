"""Focused tests for live trade persistence wiring."""

from types import SimpleNamespace

from src.trading import trade_persistence


def test_live_trade_open_and_close_use_existing_trade_and_realtime_repositories(
        monkeypatch,
):
    calls = {"create_trade": [], "create_position": [], "update_exit": [], "close_position": []}

    class FakeTrades:
        def get_by_position_id(self, _trade_id):
            return None

        def create_trade(self, **kwargs):
            calls["create_trade"].append(kwargs)

        def update_trade_exit(self, *args, **kwargs):
            calls["update_exit"].append((args, kwargs))

    class FakeBots:
        def get_by_instance_id(self, instance_id):
            assert instance_id == "strategy-1-101"
            return SimpleNamespace(id=77)

    class FakePositions:
        def get_position_by_id(self, _position_id):
            return None

        def create_position(self, **kwargs):
            calls["create_position"].append(kwargs)

        def close_position(self, position_id):
            calls["close_position"].append(position_id)

    class FakeUOW:
        def __init__(self, _session):
            self.bots = FakeBots()
            self.trades = FakeTrades()

    class FakeRealtimeUOW:
        def __init__(self, _session):
            self.positions = FakePositions()

    class FakeSession:
        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.setenv("BOT_INSTANCE_ID", "strategy-1-101")
    monkeypatch.setattr(trade_persistence, "_db_persistence_enabled", lambda: True)
    monkeypatch.setattr(trade_persistence.db, "get_session", lambda: FakeSession())
    monkeypatch.setattr(trade_persistence, "UnitOfWork", FakeUOW)
    monkeypatch.setattr(trade_persistence, "UnitOfWorkRealtime", FakeRealtimeUOW)

    position = {
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "order_id_m1": "m1-order",
        "order_id_m2": "m2-order",
        "order_m1_side": "BUY",
        "order_m2_side": "SELL",
        "order_m1_size": "0.1",
        "order_m2_size": "2.0",
        "order_m1_price": "100000.0",
        "order_m2_price": "3000.0",
    }

    trade_id = trade_persistence.persist_live_trade_opened(position)
    closed_trade_id = trade_persistence.persist_live_trade_closed(
        position,
        exit_price1="101000.0",
        exit_price2="2900.0",
        exit_size1="0.1",
        exit_size2="2.0",
    )

    assert trade_id == closed_trade_id
    assert calls["create_trade"][0]["bot_id"] == 77
    assert calls["create_trade"][0]["trade_id"] == trade_id
    assert calls["create_trade"][0]["pair1"] == "BTC-USD"
    assert calls["create_trade"][0]["side2"] == "SELL"
    assert calls["create_position"][0]["bot_instance_id"] == 77
    assert calls["create_position"][0]["position_id"] == trade_id
    assert calls["update_exit"][0][0] == (trade_id,)
    assert calls["update_exit"][0][1]["exit_price1"] == 101000.0
    assert calls["close_position"] == [trade_id]


def test_trade_activity_event_persists_for_runtime_instance(monkeypatch):
    calls = {"events": []}

    class FakeBots:
        def get_by_instance_id(self, instance_id):
            assert instance_id == "strategy-1-101"
            return SimpleNamespace(id=77)

    class FakeEvents:
        def log_event(self, **kwargs):
            calls["events"].append(kwargs)

    class FakeUOW:
        def __init__(self, _session):
            self.bots = FakeBots()
            self.events = FakeEvents()

    class FakeSession:
        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.setenv("BOT_INSTANCE_ID", "strategy-1-101")
    monkeypatch.setattr(trade_persistence, "_db_persistence_enabled", lambda: True)
    monkeypatch.setattr(trade_persistence.db, "get_session", lambda: FakeSession())
    monkeypatch.setattr(trade_persistence, "UnitOfWork", FakeUOW)

    ok = trade_persistence.persist_trade_activity_event(
        "trade_entry_attempt_started",
        "Entry attempt for BTC-USD / ETH-USD",
        details={"market_1": "BTC-USD", "market_2": "ETH-USD"},
        related_trade_id="live-abcd1234",
    )

    assert ok is True
    assert len(calls["events"]) == 1
    assert calls["events"][0]["bot_instance_id"] == 77
    assert calls["events"][0]["event_type"] == "trade_entry_attempt_started"
    assert calls["events"][0]["related_trade_id"] == "live-abcd1234"
