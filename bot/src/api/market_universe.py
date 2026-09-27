"""Market universe for the perpetual markets route.

The indexer's ``perpetualMarkets`` map lists every market the chain has ever
had, keyed by ticker, most of them in ``FINAL_SETTLEMENT``. The route used to
hand callers the first N tickers alphabetically, which on mainnet meant mostly
settled markets and no SOL-USD. This module turns the raw map into typed
records and selects the tradable universe: active markets only unless asked
otherwise, sorted by 24 h volume, capped only after sorting.

Pure: no I/O, no clock, no env reads.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

ACTIVE_STATUS = "ACTIVE"
UNKNOWN_STATUS = "UNKNOWN"


@dataclass(frozen=True)
class MarketRecord:
    """One perpetual market with the indexer metrics the pickers and filters need."""

    ticker: str
    status: str
    volume_24h: Optional[float]
    open_interest: Optional[float]
    open_interest_usd: Optional[float]
    next_funding_rate: Optional[float]
    oracle_price: Optional[float]
    trades_24h: Optional[int]
    # The indexer's ``priceChange24H`` as given: the 24 h change of the oracle
    # price in quote currency (observed on mainnet: BTC-USD oraclePrice 84350,
    # priceChange24H 273.98913), not a percentage. Consumers wanting a percent
    # divide by ``oracle_price - price_change_24h``.
    price_change_24h: Optional[float]

    @property
    def is_active(self) -> bool:
        return self.status == ACTIVE_STATUS


def _to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _to_int(value: Any) -> Optional[int]:
    parsed = _to_float(value)
    return None if parsed is None else int(parsed)


def normalize_market_records(raw_map: Any) -> List[MarketRecord]:
    """Turn the indexer's ``markets`` map into one record per non-empty ticker.

    Every metric is parsed defensively: a missing or unparseable value becomes
    ``None`` rather than a guess. Open interest arrives in base units, so the
    USD figure is derived from the oracle price when both are present.
    """
    if not isinstance(raw_map, Mapping):
        return []
    records: List[MarketRecord] = []
    for key, info in raw_map.items():
        ticker = str(key).strip()
        if not ticker:
            continue
        details: Mapping[str, Any] = info if isinstance(info, Mapping) else {}
        status = str(details.get("status") or "").strip().upper() or UNKNOWN_STATUS
        open_interest = _to_float(details.get("openInterest"))
        oracle_price = _to_float(details.get("oraclePrice"))
        open_interest_usd = (
            open_interest * oracle_price
            if open_interest is not None and oracle_price is not None
            else None
        )
        records.append(
            MarketRecord(
                ticker=ticker,
                status=status,
                volume_24h=_to_float(details.get("volume24H")),
                open_interest=open_interest,
                open_interest_usd=open_interest_usd,
                next_funding_rate=_to_float(details.get("nextFundingRate")),
                oracle_price=oracle_price,
                trades_24h=_to_int(details.get("trades24H")),
                price_change_24h=_to_float(details.get("priceChange24H")),
            )
        )
    return records


def _sort_key(record: MarketRecord) -> Tuple[bool, float, str]:
    # Highest volume first, unknown volume last, ticker as the tie-break so
    # the order is stable from one call to the next.
    return (record.volume_24h is None, -(record.volume_24h or 0.0), record.ticker)


def select_market_universe(
    records: Iterable[MarketRecord],
    *,
    include_settled: bool = False,
    cap: Optional[int] = None,
) -> List[MarketRecord]:
    """Active markets by 24 h volume, or every market, capped after sorting."""
    chosen = [record for record in records if include_settled or record.is_active]
    chosen.sort(key=_sort_key)
    if cap is not None and cap > 0:
        chosen = chosen[:cap]
    return chosen


def market_universe_payload(
    records: Iterable[MarketRecord],
    *,
    include_settled: bool,
    cap: Optional[int],
    source: str,
) -> Dict[str, Any]:
    """Response body for the route: tickers first, details beside them."""
    all_records = list(records)
    selected = select_market_universe(
        all_records, include_settled=include_settled, cap=cap
    )
    active_total = sum(1 for record in all_records if record.is_active)
    return {
        "markets": [record.ticker for record in selected],
        "market_details": [asdict(record) for record in selected],
        "count": len(selected),
        "source": source,
        "include_settled": include_settled,
        "active_total": active_total,
        "inactive_total": len(all_records) - active_total,
    }
