"""Realised P&L of a closed pair trade.

Definition (owner decision, 2026-09-19): net of trading fees, computed from
fills. Per leg the price P&L is ``(exit - entry) * size`` for a long leg
(entered with BUY) and ``(entry - exit) * size`` for a short leg (entered with
SELL), using the fill VWAPs already recorded for entry and exit. Trading fees
of all four orders are subtracted. Funding payments are NOT part of this
number. All arithmetic is ``Decimal``; results are rounded half-even to six
decimal places for storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any, Iterable, Optional

_STORAGE_QUANTUM = Decimal("0.000001")


class RealizedPnlInputError(ValueError):
    """A price, size or side needed for the calculation is missing or invalid."""


@dataclass(frozen=True)
class RealizedPnl:
    gross: Decimal
    fees: Decimal
    net: Decimal
    net_pct: Decimal
    fees_complete: bool


def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RealizedPnlInputError(f"{field} is not a number: {value!r}") from exc
    if not number.is_finite():
        raise RealizedPnlInputError(f"{field} is not finite: {value!r}")
    return number


def _leg_pnl(side: Any, entry: Any, exit_: Any, size: Any, leg: str) -> Decimal:
    normalized = str(side or "").strip().upper()
    if normalized not in {"BUY", "SELL"}:
        raise RealizedPnlInputError(f"{leg} entry side must be BUY or SELL: {side!r}")
    entry_price = _decimal(entry, f"{leg} entry price")
    exit_price = _decimal(exit_, f"{leg} exit price")
    quantity = abs(_decimal(size, f"{leg} size"))
    if entry_price <= 0 or exit_price <= 0 or quantity <= 0:
        raise RealizedPnlInputError(f"{leg} prices and size must be positive")
    move = exit_price - entry_price
    return (move if normalized == "BUY" else -move) * quantity


def sum_fill_fees(fills: Iterable[Any]) -> Optional[Decimal]:
    """Total fee of an order's fills; ``None`` when no fill carries a fee.

    A negative fee is a maker rebate and reduces the total.
    """
    total = Decimal("0")
    seen = False
    for fill in fills:
        if not isinstance(fill, dict):
            continue
        raw = fill.get("fee")
        if raw in (None, ""):
            continue
        try:
            total += Decimal(str(raw))
        except InvalidOperation:
            continue
        seen = True
    return total if seen else None


def compute_pair_realized_pnl(
    *,
    side1: Any,
    entry_price1: Any,
    exit_price1: Any,
    size1: Any,
    side2: Any,
    entry_price2: Any,
    exit_price2: Any,
    size2: Any,
    fees: Iterable[Optional[Decimal]] = (),
) -> RealizedPnl:
    """Net realised P&L of the pair. ``fees`` holds one entry per order;
    ``None`` marks an order whose fee could not be read."""
    gross = _leg_pnl(side1, entry_price1, exit_price1, size1, "leg 1") + _leg_pnl(
        side2, entry_price2, exit_price2, size2, "leg 2"
    )
    fee_list = list(fees)
    known_fees = sum((fee for fee in fee_list if fee is not None), Decimal("0"))
    fees_complete = bool(fee_list) and all(fee is not None for fee in fee_list)
    net = gross - known_fees
    entry_notional = abs(_decimal(entry_price1, "leg 1 entry price")) * abs(
        _decimal(size1, "leg 1 size")
    ) + abs(_decimal(entry_price2, "leg 2 entry price")) * abs(
        _decimal(size2, "leg 2 size")
    )
    net_pct = (
        (net / entry_notional * Decimal("100")) if entry_notional else Decimal("0")
    )

    def _store(value: Decimal) -> Decimal:
        return value.quantize(_STORAGE_QUANTUM, rounding=ROUND_HALF_EVEN)

    return RealizedPnl(
        gross=_store(gross),
        fees=_store(known_fees),
        net=_store(net),
        net_pct=_store(net_pct),
        fees_complete=fees_complete,
    )
