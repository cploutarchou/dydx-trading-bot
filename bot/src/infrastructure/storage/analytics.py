"""Analytics writer interfaces and no-op fallback."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any


class AnalyticsWriter(ABC):
    """Write analytical backtest rows to an external engine."""

    @abstractmethod
    def write_rows(self, table_name: str, rows: Sequence[Mapping[str, Any]]) -> int:
        """Write rows and return the count accepted by the destination."""


class NoopAnalyticsWriter(AnalyticsWriter):
    """Fallback writer that intentionally discards analytics rows."""

    def write_rows(self, table_name: str, rows: Sequence[Mapping[str, Any]]) -> int:
        del table_name, rows
        return 0
