from types import SimpleNamespace

from src.infrastructure.persistence.repository_realtime import PositionRepository


def test_update_position_prices_calculates_two_leg_unrealized_pnl():
    position = SimpleNamespace(
        position_id="pos-1",
        side1="BUY",
        side2="SELL",
        entry_price1=100.0,
        entry_price2=50.0,
        entry_size1=2.0,
        entry_size2=3.0,
        current_size1=None,
        current_size2=None,
        current_price1=None,
        current_price2=None,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=0.0,
    )
    calls = {"commits": 0}

    class FakeQuery:
        def filter(self, *_args):
            return self

        def first(self):
            return position

    class FakeSession:
        def query(self, _model):
            return FakeQuery()

        def commit(self):
            calls["commits"] += 1

    repo = PositionRepository(FakeSession())

    repo.update_position_prices("pos-1", current_price1=110.0, current_price2=45.0)

    assert position.current_price1 == 110.0
    assert position.current_price2 == 45.0
    assert position.current_size1 == 2.0
    assert position.current_size2 == 3.0
    assert position.unrealized_pnl == 35.0
    assert position.unrealized_pnl_pct == 10.0
    assert calls["commits"] == 1
