"""Cost and funding entry gate for pairs-arbitrage entries.

One pure decision function shared by the live entry path
(``position_manager.open_positions``) and the backtest
(``service_backtest.BacktestService._simulate_pair``). It performs no I/O,
reads no clock and no environment; every input is passed in. Arithmetic is
done in :class:`~decimal.Decimal` so the same inputs always give the same
decision.

Model. Every term is a fraction of the gross pair notional
``N = |p1| + |beta * p2|`` (the normalisation the backtest P&L uses):

* ``edge_frac = (|z_entry| - z_exit) * sigma_spread / N``, where ``z_exit``
  is the level the exit ladder's z-score rung closes at, measured on the
  entry side's axis (see :func:`ladder_exit_z`).
* ``fee_frac = 2 * taker_fee`` and ``slippage_frac = 2 * slippage_per_fill``:
  the round-trip convention of the backtest's per-trade ``fee_cost``.
* ``funding_frac = max(0, w_long * r_long - w_short * r_short) * hold_hours``
  with beta weights ``w1 = |p1| / N`` and ``w2 = |beta * p2| / N``. A positive
  dYdX funding rate means longs pay shorts, so the long leg pays ``r_long``
  and the short leg pays ``-r_short``. Funding received never lowers the cost.
* ``hold_hours = min(half_life_bars * bar_hours, max_hold_hours)`` where the
  cap applies only when it is positive (the position timeout).

Evaluation order, one reason per rejection:

1. ``cost_inputs_invalid``: any input missing, unparseable or non-finite,
   ``z_entry == 0``, ``sigma <= 0``, a price ``<= 0``, ``N <= 0``, no z-score
   exit level, or (when funding is modelled) a missing funding rate.
2. ``funding_same_side``: both legs pay funding, that is
   ``r_long > tau`` and ``r_short < -tau``. Same-sign rates alone mean the
   pair's funding is hedged and never reject.
3. ``edge_lt_cost``: ``edge_frac < multiple * (fee_frac + slippage_frac +
   funding_frac)``. An edge exactly at the boundary is accepted.

``edge_frac`` is a model estimate of the spread capture, not a forecast of
realised P&L.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

REASON_COST_INPUTS_INVALID = "cost_inputs_invalid"
REASON_FUNDING_SAME_SIDE = "funding_same_side"
REASON_EDGE_LT_COST = "edge_lt_cost"
REJECTION_REASONS = (
    REASON_COST_INPUTS_INVALID,
    REASON_FUNDING_SAME_SIDE,
    REASON_EDGE_LT_COST,
)

# dYdX v4 base-tier taker fee per fill (0.05%). The backtest's default
# ``transaction_fee`` and the live gate's default taker fee are both this one
# constant so the two cost models cannot drift apart.
DEFAULT_TAKER_FEE = 0.0005

# Default required edge-to-cost ratio and its clamp. The bounds for the other
# settings are engineering sanity rails, not business values: they are wide on
# purpose because clamping a cost input down loosens the gate.
DEFAULT_EDGE_MULTIPLE = 2.5
EDGE_MULTIPLE_BOUNDS = (1.0, 20.0)
TAKER_FEE_BOUNDS = (0.0, 0.01)
SLIPPAGE_BPS_BOUNDS = (0.0, 1000.0)
FUNDING_THRESHOLD_BOUNDS = (0.0, 0.01)

# Candle duration per normalised dYdX resolution (``market_data.normalize_resolution``).
# An unknown resolution is an invalid input here; it never falls back to 1 hour.
RESOLUTION_HOURS: Dict[str, Decimal] = {
    "1MIN": Decimal(1) / Decimal(60),
    "5MINS": Decimal(5) / Decimal(60),
    "15MINS": Decimal(15) / Decimal(60),
    "30MINS": Decimal(30) / Decimal(60),
    "1HOUR": Decimal(1),
    "4HOURS": Decimal(4),
    "1DAY": Decimal(24),
}

_ZERO = Decimal(0)
_TWO = Decimal(2)
_BPS = Decimal(10000)


class CostInputError(ValueError):
    """An input the gate cannot price. Always mapped to ``cost_inputs_invalid``."""


def _dec(value: Any, field: str) -> Decimal:
    """Convert to a finite Decimal via ``str`` (never via binary float math)."""
    if value is None or isinstance(value, bool):
        raise CostInputError(f"{field} is missing")
    try:
        parsed = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise CostInputError(f"{field} is not a number: {value!r}") from exc
    if not parsed.is_finite():
        raise CostInputError(f"{field} is not finite: {value!r}")
    return parsed


def clamp_setting(value: Any, bounds: tuple[float, float], fallback: float) -> float:
    """Clamp a runtime setting into ``bounds``.

    Unparseable or non-finite values (``"nan"``, ``"inf"``) take ``fallback``,
    which is itself clamped, so a bad override can never disable a check.
    """
    lower, upper = bounds
    try:
        parsed = _dec(value, "setting")
    except CostInputError:
        parsed = _dec(fallback, "fallback")
    return float(min(max(parsed, Decimal(str(lower))), Decimal(str(upper))))


def clamp_edge_multiple(value: Any) -> float:
    return clamp_setting(value, EDGE_MULTIPLE_BOUNDS, DEFAULT_EDGE_MULTIPLE)


def slippage_bps_to_fraction(bps: Any) -> Decimal:
    """Convert per-fill slippage in basis points to a fraction of notional."""
    return _dec(bps, "slippage_bps") / _BPS


def ladder_exit_z(z_entry: Any, *, close_at_zscore_cross: bool) -> Optional[float]:
    """Level, on the entry side's axis, where the exit ladder's z rung closes.

    ``position_manager._resolve_exit_reason`` (and the backtest mirror of it)
    closes on the z-score only once z has crossed zero AND reached at least the
    entry magnitude on the other side, so the rung fires at the mirror level
    ``-|z_entry|``. The spread travel it assumes is therefore ``2 * |z_entry|``
    standard deviations, twice an exit-at-mean estimate. Stop-loss,
    take-profit, trailing stop and timeout sit above this rung and can close
    earlier, so the resulting edge is an upper bound on the capture.

    Returns ``None`` when the rung is disabled: there is then no z level to
    estimate the edge from, and the gate fails closed.
    """
    if not close_at_zscore_cross:
        return None
    try:
        return -abs(float(z_entry))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class FundingInputs:
    """Funding inputs for the live gate. The backtest has no funding history
    and passes no ``FundingInputs`` at all (funding is not modelled there).

    ``rate_market_1`` / ``rate_market_2`` are the markets' hourly
    ``nextFundingRate`` values as served by the indexer (decimal strings);
    ``None`` means the market object carried no rate.
    """

    rate_market_1: Any
    rate_market_2: Any
    half_life_bars: Any
    resolution: Any
    max_hold_hours: Any
    same_side_threshold: Any


@dataclass(frozen=True)
class EntryCostDecision:
    accepted: bool
    reason: Optional[str]
    edge_frac: Optional[Decimal]
    fee_frac: Optional[Decimal]
    slippage_frac: Optional[Decimal]
    funding_frac: Optional[Decimal]
    hold_hours: Optional[Decimal]
    multiple: Optional[Decimal]
    detail: str = ""

    @property
    def cost_frac(self) -> Optional[Decimal]:
        if (
            self.fee_frac is None
            or self.slippage_frac is None
            or self.funding_frac is None
        ):
            return None
        return self.fee_frac + self.slippage_frac + self.funding_frac

    def log_fields(self) -> Dict[str, Optional[float]]:
        """Cost breakdown as floats for logs and diagnostics."""

        def _f(value: Optional[Decimal]) -> Optional[float]:
            return None if value is None else float(value)

        return {
            "edge_frac": _f(self.edge_frac),
            "fee_frac": _f(self.fee_frac),
            "slippage_frac": _f(self.slippage_frac),
            "funding_frac": _f(self.funding_frac),
            "hold_hours": _f(self.hold_hours),
            "multiple": _f(self.multiple),
        }


def invalid_decision(detail: str) -> EntryCostDecision:
    """A ``cost_inputs_invalid`` rejection carrying ``detail``."""
    return EntryCostDecision(
        accepted=False,
        reason=REASON_COST_INPUTS_INVALID,
        edge_frac=None,
        fee_frac=None,
        slippage_frac=None,
        funding_frac=None,
        hold_hours=None,
        multiple=None,
        detail=detail,
    )


def expected_hold_hours(
    *, half_life_bars: Any, resolution: Any, max_hold_hours: Any
) -> Decimal:
    """``min(half_life_bars * bar_hours, max_hold_hours)``; a cap ``<= 0`` means none.

    ``half_life_bars`` is in candles: the pair's half-life is regressed on
    per-bar spread differences (``cointegration.half_life_mean_reversion``).
    """
    half_life = _dec(half_life_bars, "half_life")
    if half_life <= _ZERO:
        raise CostInputError(f"half_life must be positive, got {half_life}")
    key = str(resolution or "").strip().upper()
    if key not in RESOLUTION_HOURS:
        raise CostInputError(f"unknown candle resolution {resolution!r}")
    hold = half_life * RESOLUTION_HOURS[key]
    cap = _dec(max_hold_hours, "max_hold_hours")
    if cap > _ZERO:
        hold = min(hold, cap)
    return hold


def evaluate_entry_cost(
    *,
    z_entry: Any,
    z_exit: Any,
    spread_std: Any,
    price_1: Any,
    price_2: Any,
    hedge_ratio: Any,
    taker_fee: Any,
    slippage_per_fill: Any,
    multiple: Any,
    funding: Optional[FundingInputs],
) -> EntryCostDecision:
    """Decide whether an entry's modelled edge covers its round-trip cost.

    The long leg follows the entry rule shared by live and backtest: z < 0
    buys market 1 and sells market 2; z > 0 sells market 1 and buys market 2.
    ``slippage_per_fill`` is a fraction of notional (not bps).
    """
    try:
        z = _dec(z_entry, "z_entry")
        if z == _ZERO:
            raise CostInputError("z_entry is zero: no entry direction")
        if z_exit is None:
            raise CostInputError("no z-score exit level (z-score exit disabled)")
        z_out = _dec(z_exit, "z_exit")
        sigma = _dec(spread_std, "spread_std")
        if sigma <= _ZERO:
            raise CostInputError(f"spread_std must be positive, got {sigma}")
        p1 = _dec(price_1, "price_1")
        p2 = _dec(price_2, "price_2")
        if p1 <= _ZERO or p2 <= _ZERO:
            raise CostInputError("prices must be positive")
        beta = _dec(hedge_ratio, "hedge_ratio")
        leg_1 = abs(p1)
        leg_2 = abs(beta * p2)
        notional = leg_1 + leg_2
        if notional <= _ZERO:
            raise CostInputError("pair notional must be positive")
        fee = _dec(taker_fee, "taker_fee")
        slip = _dec(slippage_per_fill, "slippage_per_fill")
        if fee < _ZERO or slip < _ZERO:
            raise CostInputError("fee and slippage must be non-negative")
        mult = _dec(clamp_edge_multiple(_dec(multiple, "multiple")), "multiple")

        funding_frac = _ZERO
        hold_hours = _ZERO
        pays_both = False
        if funding is not None:
            rate_1 = _dec(funding.rate_market_1, "nextFundingRate market_1")
            rate_2 = _dec(funding.rate_market_2, "nextFundingRate market_2")
            tau = _dec(funding.same_side_threshold, "funding_same_side_threshold")
            if tau < _ZERO:
                raise CostInputError("funding threshold must be non-negative")
            hold_hours = expected_hold_hours(
                half_life_bars=funding.half_life_bars,
                resolution=funding.resolution,
                max_hold_hours=funding.max_hold_hours,
            )
            if z < _ZERO:
                r_long, w_long, r_short, w_short = rate_1, leg_1, rate_2, leg_2
            else:
                r_long, w_long, r_short, w_short = rate_2, leg_2, rate_1, leg_1
            pays_both = r_long > tau and r_short < -tau
            hourly = (w_long * r_long - w_short * r_short) / notional
            funding_frac = max(_ZERO, hourly) * hold_hours
    except (CostInputError, ValueError, TypeError, InvalidOperation) as exc:
        return invalid_decision(str(exc))

    edge = (abs(z) - z_out) * sigma / notional
    fee_frac = _TWO * fee
    slippage_frac = _TWO * slip

    if pays_both:
        return EntryCostDecision(
            accepted=False,
            reason=REASON_FUNDING_SAME_SIDE,
            edge_frac=edge,
            fee_frac=fee_frac,
            slippage_frac=slippage_frac,
            funding_frac=funding_frac,
            hold_hours=hold_hours,
            multiple=mult,
            detail="both legs pay funding above the threshold",
        )

    required = mult * (fee_frac + slippage_frac + funding_frac)
    accepted = not edge < required
    return EntryCostDecision(
        accepted=accepted,
        reason=None if accepted else REASON_EDGE_LT_COST,
        edge_frac=edge,
        fee_frac=fee_frac,
        slippage_frac=slippage_frac,
        funding_frac=funding_frac,
        hold_hours=hold_hours,
        multiple=mult,
    )
