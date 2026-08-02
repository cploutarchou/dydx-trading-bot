"""Shared request-validation helpers for trading API inputs.

Pure functions only — no config/constant imports — so this module is safe to
import from any layer without triggering environment load-order concerns
(see AGENTS.md rule #1). Intended for reuse across the Pydantic request models
in ``src/infrastructure/domain`` and ``src/api/server.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, List, Optional

ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
"""Regex a model field can attach so callers get a clean 422 on bad date shapes."""

DEFAULT_MAX_MARKETS = 200
"""Sane upper bound on the number of selected markets/pairs per request."""


def validate_iso_date_range(start: Optional[str], end: Optional[str]) -> None:
    """Ensure ``end_date`` is not before ``start_date``.

    Both values are expected to already match ``YYYY-MM-DD`` (enforced by the
    field's ``pattern`` constraint). Raises ``ValueError`` if either value
    cannot be parsed or if ``end < start``. ``ValueError`` is chosen so it
    surfaces through Pydantic ``model_validator`` as a standard 422.
    """

    if not start or not end:
        # Missing values are handled by the model's required-field / pattern
        # constraints; nothing to compare here.
        return

    try:
        start_d = datetime.strptime(start, "%Y-%m-%d").date()
        end_d = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError as exc:  # malformed date despite the pattern guard
        raise ValueError(
            f"start_date/end_date must be YYYY-MM-DD; received start={start!r}, "
            f"end={end!r}"
        ) from exc

    if end_d < start_d:
        raise ValueError(f"end_date ({end}) must not be before start_date ({start})")


def normalize_market_list(
    values: Optional[Iterable[Any]],
    *,
    max_items: int = DEFAULT_MAX_MARKETS,
) -> List[str]:
    """Normalize a list of market/pair symbols.

    Strips whitespace, upper-cases, drops empties and duplicates, and caps the
    result at ``max_items``. Mirrors the long-standing ``_normalize_string_list``
    semantics in ``src/api/server.py`` but lives here for cross-module reuse.
    """

    normalized: List[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = str(raw or "").strip().upper()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
        if len(normalized) >= max_items:
            break
    return normalized


def years_between(start: str, end: str) -> float:
    """Convenience helper: fractional years between two ``YYYY-MM-DD`` dates.

    Returns ``0.0`` if either value is falsy. Raises ``ValueError`` on a bad
    parse so callers can surface it as a validation error.
    """

    if not start or not end:
        return 0.0
    start_d = datetime.strptime(start, "%Y-%m-%d").date()
    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    if end_d < start_d:
        raise ValueError(f"end_date ({end}) must not be before start_date ({start})")
    return (end_d - start_d).days / 365.25


__all__ = [
    "DEFAULT_MAX_MARKETS",
    "ISO_DATE_PATTERN",
    "normalize_market_list",
    "validate_iso_date_range",
    "years_between",
]
