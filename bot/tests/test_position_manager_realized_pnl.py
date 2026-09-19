"""Realised P&L is computed from fills when a pair is closed."""

import asyncio
from decimal import Decimal

from src.trading import position_manager


def _position():
    return {
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "order_id_m1": "entry-1",
        "order_id_m2": "entry-2",
        "order_m1_side": "BUY",
        "order_m2_side": "SELL",
        "order_m1_price": "100",
        "order_m2_price": "50",
        "order_m1_size": "2",
        "order_m2_size": "4",
    }


def _close(monkeypatch, fills_by_order, position=None):
    async def fake_get_order_fills(_client, order_id, market=None):
        value = fills_by_order[order_id]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(position_manager, "get_order_fills", fake_get_order_fills)
    position = position or _position()
    realized = asyncio.run(
        position_manager._realized_pnl_for_closed_pair(
            object(),
            position,
            exit_price_m1="110",
            exit_price_m2="45",
            exit_size_m1="2",
            exit_size_m2="4",
            close_order_m1_id="close-1",
            close_order_m2_id="close-2",
        )
    )
    return realized, position


def test_net_pnl_subtracts_the_fees_of_all_four_orders(monkeypatch):
    realized, position = _close(
        monkeypatch,
        {
            "entry-1": [{"fee": "0.05"}],
            "entry-2": [{"fee": "0.05"}],
            "close-1": [{"fee": "0.03"}, {"fee": "0.03"}],
            "close-2": [{"fee": "0.04"}],
        },
    )

    assert realized.gross == Decimal("40.000000")
    assert realized.fees == Decimal("0.200000")
    assert realized.net == Decimal("39.800000")
    assert realized.fees_complete is True
    assert position["realized_pnl"] == "39.800000"
    assert position["realized_pnl_fees_complete"] is True


def test_unreadable_entry_fees_are_flagged(monkeypatch):
    realized, position = _close(
        monkeypatch,
        {
            "entry-1": ConnectionError("indexer down"),
            "entry-2": [],
            "close-1": [{"fee": "0.06"}],
            "close-2": [{"fee": "0.04"}],
        },
    )

    assert realized.net == Decimal("39.900000")
    assert realized.fees_complete is False
    assert position["realized_pnl_fees_complete"] is False


def test_unusable_entry_data_records_nothing(monkeypatch):
    broken = _position()
    broken["order_m1_price"] = ""

    realized, position = _close(
        monkeypatch,
        {key: [] for key in ("entry-1", "entry-2", "close-1", "close-2")},
        position=broken,
    )

    assert realized is None
    assert "realized_pnl" not in position
