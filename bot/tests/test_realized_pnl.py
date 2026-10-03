"""Realised P&L: side-aware, net of fees, exact decimal arithmetic."""

from decimal import Decimal

import pytest

from src.trading.realized_pnl import (
    RealizedPnlInputError,
    compute_pair_realized_pnl,
    sum_fill_fees,
)


def _pair(**overrides):
    base = dict(
        side1="BUY",
        entry_price1="100",
        exit_price1="110",
        size1="2",
        side2="SELL",
        entry_price2="50",
        exit_price2="45",
        size2="4",
    )
    base.update(overrides)
    return base


def test_long_and_short_legs_are_signed_correctly():
    result = compute_pair_realized_pnl(**_pair())

    # long: (110-100)*2 = 20 ; short: (50-45)*4 = 20
    assert result.gross == Decimal("40.000000")
    assert result.net == Decimal("40.000000")


def test_losing_trade_is_negative():
    result = compute_pair_realized_pnl(**_pair(exit_price1="90", exit_price2="55"))

    assert result.net == Decimal("-40.000000")


def test_reversed_sides_flip_the_sign():
    """The old close_trade hard-coded leg 1 long / leg 2 short."""
    result = compute_pair_realized_pnl(**_pair(side1="SELL", side2="BUY"))

    assert result.gross == Decimal("-40.000000")


def test_fees_of_all_four_orders_are_subtracted():
    fees = [Decimal("0.05"), Decimal("0.05"), Decimal("0.06"), Decimal("0.04")]

    result = compute_pair_realized_pnl(**_pair(), fees=fees)

    assert result.fees == Decimal("0.200000")
    assert result.net == Decimal("39.800000")
    assert result.fees_complete is True
    # entry notional = 100*2 + 50*4 = 400
    assert result.net_pct == Decimal("9.950000")


def test_unknown_fee_is_flagged_not_guessed():
    result = compute_pair_realized_pnl(
        **_pair(), fees=[Decimal("0.05"), None, Decimal("0.06"), None]
    )

    assert result.fees == Decimal("0.110000")
    assert result.fees_complete is False


def test_no_binary_float_drift():
    result = compute_pair_realized_pnl(
        **_pair(entry_price1="0.1", exit_price1="0.3", size1="3", exit_price2="50")
    )

    # float: (0.3-0.1)*3 = 0.6000000000000001
    assert result.gross == Decimal("0.600000")


def test_storage_rounding_is_half_even_at_six_places():
    result = compute_pair_realized_pnl(
        **_pair(entry_price1="1", exit_price1="1.0000005", size1="1", exit_price2="50")
    )

    assert result.gross == Decimal("0.000000")  # 0.0000005 -> half-even -> 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"side1": ""},
        {"side2": "LONG"},
        {"exit_price1": None},
        {"entry_price2": "abc"},
        {"size1": "0"},
        {"exit_price2": "nan"},
    ],
)
def test_invalid_inputs_raise_instead_of_producing_a_number(overrides):
    with pytest.raises(RealizedPnlInputError):
        compute_pair_realized_pnl(**_pair(**overrides))


def test_sum_fill_fees_handles_rebates_and_missing_fields():
    assert sum_fill_fees([{"fee": "0.10"}, {"fee": "-0.02"}, {"size": "1"}]) == Decimal(
        "0.08"
    )
    assert sum_fill_fees([{"size": "1"}, "junk"]) is None
    assert sum_fill_fees([]) is None
