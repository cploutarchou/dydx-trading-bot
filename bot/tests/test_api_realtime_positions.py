import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from src.api import server


def _json_body(response):
    return json.loads(response.body.decode("utf-8"))


def test_current_positions_resolves_strategy_instance_id(monkeypatch):
    calls = {}

    class FakeSession:
        def close(self):
            calls["closed"] = True

    class FakeCoreUow:
        def __init__(self, session):
            assert isinstance(session, FakeSession)

            class Bots:
                def get_by_instance_id(self, instance_id):
                    calls["resolved_instance_id"] = instance_id
                    return SimpleNamespace(id=42)

            self.bots = Bots()

    class FakePositions:
        def get_open_positions(self, bot_instance_id):
            calls["queried_bot_id"] = bot_instance_id
            return [
                SimpleNamespace(
                    position_id="pos-1",
                    pair1="AVAX-USD",
                    pair2="MNT-USD",
                    status=SimpleNamespace(value="OPEN"),
                    side1="SELL",
                    side2="BUY",
                    entry_price1=10.0,
                    entry_price2=2.0,
                    current_price1=9.5,
                    current_price2=2.1,
                    current_size1=1.1,
                    current_size2=10.0,
                    unrealized_pnl=3.25,
                    unrealized_pnl_pct=1.2,
                    z_score_entry=2.04,
                    z_score_current=1.7,
                    entry_time=datetime.now(timezone.utc),
                    updated_at=None,
                )
            ]

    class FakeRealtimeUow:
        def __init__(self, session):
            assert isinstance(session, FakeSession)
            self.positions = FakePositions()

    monkeypatch.setattr(server.db, "get_session", lambda: FakeSession())
    monkeypatch.setattr(server, "UnitOfWork", FakeCoreUow)
    monkeypatch.setattr(server, "UnitOfWorkRealtime", FakeRealtimeUow)

    response = asyncio.run(
        server.get_current_positions(
            "strategy-1-2",
            current_user=SimpleNamespace(username="operator"),
        )
    )
    payload = _json_body(response)

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["count"] == 1
    assert payload["data"]["positions"][0]["pair1"] == "AVAX-USD"
    assert calls["resolved_instance_id"] == "strategy-1-2"
    assert calls["queried_bot_id"] == 42
    assert calls["closed"] is True
