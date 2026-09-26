"""Unit tests for the pure cost + funding entry gate (src/trading/entry_cost_gate.py)."""

import dataclasses
import itertools
from decimal import Decimal

import pytest

from src.infrastructure.use_cases.backtest_history import _resolution_to_minutes
from src.trading import entry_cost_gate as gate
from src.trading.entry_cost_gate import (
    REASON_COST_INPUTS_INVALID,
    REASON_EDGE_LT_COST,
    REASON_FUNDING_SAME_SIDE,
    FundingInputs,
    evaluate_entry_cost,
)

TAU = 0.00001


def _inputs(**overrides):
    """Valid baseline: N = 50 + 1*50 = 100, travel 2|z| = 4, sigma 0.5.

    edge = 4 * 0.5 / 100 = 0.02; cost = 2*0.0005 + 2*0.0005 = 0.002.
    """
    base = dict(
        z_entry=-2.0,
        z_exit=-2.0,
        spread_std=0.5,
        price_1=50.0,
        price_2=50.0,
        hedge_ratio=1.0,
        taker_fee=0.0005,
        slippage_per_fill=0.0005,
        multiple=2.5,
        funding=None,
    )
    base.update(overrides)
    return base


def _funding(rate_1="0", rate_2="0", **overrides):
    values = dict(
        rate_market_1=rate_1,
        rate_market_2=rate_2,
        half_life_bars=10,
        resolution="1HOUR",
        max_hold_hours=72,
        same_side_threshold=TAU,
    )
    values.update(overrides)
    return FundingInputs(**values)


# --- model ------------------------------------------------------------------


def test_accepts_when_edge_covers_cost_and_reports_breakdown():
    decision = evaluate_entry_cost(**_inputs())

    assert decision.accepted is True
    assert decision.reason is None
    assert decision.edge_frac == Decimal("0.02")
    assert decision.fee_frac == Decimal("0.0010")
    assert decision.slippage_frac == Decimal("0.0010")
    assert decision.funding_frac == Decimal(0)
    assert decision.hold_hours == Decimal(0)
    assert decision.multiple == Decimal("2.5")
    assert decision.cost_frac == Decimal("0.0020")


def test_edge_uses_beta_weighted_notional_and_mirror_exit_level():
    # N = |p1| + |beta * p2| = 40 + 0.5 * 80 = 80; travel = 1.5 - (-1.5) = 3.
    decision = evaluate_entry_cost(
        **_inputs(
            z_entry=1.5,
            z_exit=gate.ladder_exit_z(1.5, close_at_zscore_cross=True),
            spread_std=0.2,
            price_1=40.0,
            price_2=80.0,
            hedge_ratio=-0.5,
        )
    )
    assert decision.edge_frac == Decimal(3) * Decimal("0.2") / Decimal(80)


def test_boundary_edge_equal_to_multiple_times_cost_is_accepted():
    # edge = 4 * 0.1 / 100 = 0.004 = 2 * (0.001 + 0.001) exactly.
    at_boundary = evaluate_entry_cost(**_inputs(spread_std="0.1", multiple=2))
    assert at_boundary.edge_frac == Decimal("0.004")
    assert at_boundary.edge_frac == at_boundary.multiple * at_boundary.cost_frac
    assert at_boundary.accepted is True

    below = evaluate_entry_cost(**_inputs(spread_std="0.0999", multiple=2))
    assert below.accepted is False
    assert below.reason == REASON_EDGE_LT_COST


def test_edge_lt_cost_rejection_keeps_the_breakdown():
    decision = evaluate_entry_cost(**_inputs(spread_std=0.01))

    assert decision.accepted is False
    assert decision.reason == REASON_EDGE_LT_COST
    fields = decision.log_fields()
    assert fields["edge_frac"] == pytest.approx(0.0004)
    assert fields["fee_frac"] == pytest.approx(0.001)
    assert fields["slippage_frac"] == pytest.approx(0.001)
    assert fields["multiple"] == pytest.approx(2.5)


def test_fee_and_slippage_follow_the_backtest_round_trip_convention():
    # Backtest per-trade cost: usd * (fee + slippage) * 2.
    usd, fee, slip = 10.0, 0.0005, 0.0007
    decision = evaluate_entry_cost(**_inputs(taker_fee=fee, slippage_per_fill=slip))
    assert float(decision.fee_frac + decision.slippage_frac) * usd == pytest.approx(
        usd * (fee + slip) * 2.0
    )


def test_slippage_bps_conversion():
    assert gate.slippage_bps_to_fraction(5) == Decimal("0.0005")
    assert gate.slippage_bps_to_fraction("12.5") == Decimal("0.00125")
    with pytest.raises(gate.CostInputError):
        gate.slippage_bps_to_fraction(None)


# --- exit level ---------------------------------------------------------------


@pytest.mark.parametrize("z", [2.5, -2.5])
def test_ladder_exit_z_is_the_mirror_level(z):
    assert gate.ladder_exit_z(z, close_at_zscore_cross=True) == -2.5


def test_ladder_exit_z_is_none_without_a_zscore_exit_or_with_bad_z():
    assert gate.ladder_exit_z(2.0, close_at_zscore_cross=False) is None
    assert gate.ladder_exit_z(None, close_at_zscore_cross=True) is None
    assert gate.ladder_exit_z("abc", close_at_zscore_cross=True) is None


def test_no_zscore_exit_level_fails_closed():
    decision = evaluate_entry_cost(**_inputs(z_exit=None))
    assert decision.reason == REASON_COST_INPUTS_INVALID
    assert "exit" in decision.detail


# --- funding ----------------------------------------------------------------


def test_funding_cost_is_beta_weighted_and_scaled_by_hold_hours():
    # z < 0: long market 1. hourly = (50 * 0.0001 - 50 * 0) / 100 = 0.00005.
    decision = evaluate_entry_cost(
        **_inputs(funding=_funding(rate_1="0.0001", rate_2="0"))
    )
    assert decision.hold_hours == Decimal(10)
    assert decision.funding_frac == Decimal("0.0005")
    assert decision.accepted is True


def test_funding_received_never_lowers_the_cost():
    # Long leg receives (negative rate), short leg receives (positive rate).
    decision = evaluate_entry_cost(
        **_inputs(funding=_funding(rate_1="-0.001", rate_2="0.001"))
    )
    assert decision.funding_frac == Decimal(0)
    assert decision.cost_frac == Decimal("0.0020")


def test_funding_cost_can_push_an_entry_below_the_required_edge():
    # Long leg pays 0.0004/h, short leg is flat (not both paying): no overlay,
    # but funding_frac = 0.5 * 0.0004 * 10 = 0.002 doubles the cost.
    decision = evaluate_entry_cost(
        **_inputs(
            spread_std=0.15,
            funding=_funding(rate_1="0.0004", rate_2="0"),
        )
    )
    assert decision.funding_frac == Decimal("0.0020")
    # edge 0.006 < 2.5 * 0.004
    assert decision.reason == REASON_EDGE_LT_COST


_ABOVE = "0.00002"
_BELOW_NEG = "-0.00002"
_SMALL_POS = "0.000005"
_SMALL_NEG = "-0.000005"
_RATES = [_ABOVE, _SMALL_POS, "0", _SMALL_NEG, _BELOW_NEG, str(TAU), str(-TAU)]


@pytest.mark.parametrize("r_long, r_short", list(itertools.product(_RATES, repeat=2)))
@pytest.mark.parametrize("z_entry", [-2.0, 2.0])
def test_funding_same_side_truth_table(r_long, r_short, z_entry):
    """Reject only when the long leg's rate > tau AND the short leg's rate < -tau."""
    # z < 0 longs market 1; z > 0 longs market 2.
    if z_entry < 0:
        rate_1, rate_2 = r_long, r_short
    else:
        rate_1, rate_2 = r_short, r_long
    decision = evaluate_entry_cost(
        **_inputs(
            z_entry=z_entry,
            z_exit=-abs(z_entry),
            funding=_funding(rate_1=rate_1, rate_2=rate_2),
        )
    )
    both_pay = Decimal(r_long) > Decimal(str(TAU)) and Decimal(r_short) < -Decimal(
        str(TAU)
    )
    if both_pay:
        assert decision.reason == REASON_FUNDING_SAME_SIDE
    else:
        # Same-sign rates are a hedged pair; the generous edge here accepts.
        assert decision.reason is None
        assert decision.accepted is True


def test_same_sign_rates_are_hedged_and_never_rejected_for_funding():
    for rate in ("0.01", "-0.01"):
        decision = evaluate_entry_cost(
            **_inputs(funding=_funding(rate_1=rate, rate_2=rate))
        )
        assert decision.reason != REASON_FUNDING_SAME_SIDE
        # Equal weights and equal rates: long pays what short receives.
        assert decision.funding_frac == Decimal(0)


def test_hold_hours_cap_and_resolution():
    assert gate.expected_hold_hours(
        half_life_bars=100, resolution="1HOUR", max_hold_hours=72
    ) == Decimal(72)
    assert gate.expected_hold_hours(
        half_life_bars=100, resolution="1HOUR", max_hold_hours=0
    ) == Decimal(100)
    assert gate.expected_hold_hours(
        half_life_bars=10, resolution="4HOURS", max_hold_hours=72
    ) == Decimal(40)
    assert gate.expected_hold_hours(
        half_life_bars=12, resolution="5MINS", max_hold_hours=72
    ) == Decimal(1)


def test_resolution_hours_match_the_backtest_candle_durations():
    for key, hours in gate.RESOLUTION_HOURS.items():
        assert hours * 60 == Decimal(_resolution_to_minutes(key)), key


# --- fail closed ------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"z_entry": float("nan")},
        {"z_entry": float("inf")},
        {"z_entry": None},
        {"z_entry": 0.0},
        {"z_exit": float("nan")},
        {"spread_std": 0.0},
        {"spread_std": -0.1},
        {"spread_std": float("nan")},
        {"price_1": 0.0},
        {"price_2": -1.0},
        {"price_1": float("nan")},
        {"hedge_ratio": float("inf")},
        {"hedge_ratio": "abc"},
        {"taker_fee": -0.0001},
        {"slippage_per_fill": None},
        {"multiple": float("nan")},
        {"multiple": True},
        {"funding": _funding(rate_1=None)},
        {"funding": _funding(rate_2="")},
        {"funding": _funding(rate_1="not-a-rate")},
        {"funding": _funding(rate_1="NaN")},
        {"funding": _funding(half_life_bars=0)},
        {"funding": _funding(half_life_bars=float("nan"))},
        {"funding": _funding(resolution="2HOURS")},
        {"funding": _funding(resolution=None)},
        {"funding": _funding(max_hold_hours=None)},
        {"funding": _funding(same_side_threshold=-0.1)},
    ],
)
def test_invalid_inputs_reject_as_cost_inputs_invalid(overrides):
    decision = evaluate_entry_cost(**_inputs(**overrides))

    assert decision.accepted is False
    assert decision.reason == REASON_COST_INPUTS_INVALID
    assert decision.detail
    assert decision.edge_frac is None and decision.cost_frac is None


def test_evaluation_order_invalid_then_funding_then_edge():
    both_pay = _funding(rate_1="0.001", rate_2="-0.001")
    # Invalid input wins over both-legs-pay funding.
    assert (
        evaluate_entry_cost(**_inputs(spread_std=0, funding=both_pay)).reason
        == REASON_COST_INPUTS_INVALID
    )
    # Both-legs-pay funding wins over a too-small edge.
    assert (
        evaluate_entry_cost(**_inputs(spread_std=0.0001, funding=both_pay)).reason
        == REASON_FUNDING_SAME_SIDE
    )


# --- clamping and determinism -------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (0.5, 1.0),
        (1.0, 1.0),
        (2.5, 2.5),
        (20.0, 20.0),
        (50, 20.0),
        ("3", 3.0),
        ("nan", gate.DEFAULT_EDGE_MULTIPLE),
        ("inf", gate.DEFAULT_EDGE_MULTIPLE),
        (None, gate.DEFAULT_EDGE_MULTIPLE),
        ("abc", gate.DEFAULT_EDGE_MULTIPLE),
    ],
)
def test_edge_multiple_clamp(raw, expected):
    assert gate.clamp_edge_multiple(raw) == expected


def test_gate_applies_the_multiple_clamp():
    assert evaluate_entry_cost(**_inputs(multiple=100)).multiple == Decimal(20)
    assert evaluate_entry_cost(**_inputs(multiple=0.1)).multiple == Decimal(1)


def test_clamp_setting_bounds_and_fallback():
    assert gate.clamp_setting(-5, gate.SLIPPAGE_BPS_BOUNDS, 5.0) == 0.0
    assert gate.clamp_setting(5000, gate.SLIPPAGE_BPS_BOUNDS, 5.0) == 1000.0
    assert gate.clamp_setting("inf", gate.TAKER_FEE_BOUNDS, 0.0005) == 0.0005
    # A fallback outside the bounds is clamped too.
    assert gate.clamp_setting("nan", gate.FUNDING_THRESHOLD_BOUNDS, 1.0) == 0.01


def test_decision_is_deterministic_and_immutable():
    kwargs = _inputs(funding=_funding(rate_1="0.00003", rate_2="-0.000001"))
    first = evaluate_entry_cost(**kwargs)
    second = evaluate_entry_cost(**kwargs)
    assert first == second

    # String and float spellings of the same numbers give the same decision.
    as_strings = {
        key: (str(value) if isinstance(value, float) else value)
        for key, value in kwargs.items()
    }
    assert evaluate_entry_cost(**as_strings) == first

    with pytest.raises(dataclasses.FrozenInstanceError):
        first.accepted = False  # type: ignore[misc]
