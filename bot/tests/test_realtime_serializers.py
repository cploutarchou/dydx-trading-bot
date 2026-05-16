from datetime import datetime, timezone
from types import SimpleNamespace

from src.api.realtime_serializers import serialize_realtime_position


def test_serialize_realtime_position_handles_nullable_numeric_fields():
    position = SimpleNamespace(
        position_id="pos-1",
        pair1="ETH-USD",
        pair2="BTC-USD",
        status=SimpleNamespace(value="OPEN"),
        side1="BUY",
        side2="SELL",
        entry_price1=100.0,
        entry_price2=200.0,
        current_price1=101.0,
        current_price2=199.0,
        current_size1=None,
        current_size2=None,
        unrealized_pnl=None,
        unrealized_pnl_pct=None,
        z_score_entry=None,
        z_score_current=None,
        entry_time=datetime.now(timezone.utc),
        updated_at=None,
    )

    payload = serialize_realtime_position(position)

    assert payload["current_size1"] == 0.0
    assert payload["current_size2"] == 0.0
    assert payload["unrealized_pnl"] == 0.0
    assert payload["unrealized_pnl_pct"] == 0.0
