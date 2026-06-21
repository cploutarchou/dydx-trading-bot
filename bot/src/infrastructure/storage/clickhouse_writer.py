"""Placeholder ClickHouse analytics writer adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .analytics import AnalyticsWriter, NoopAnalyticsWriter


class ClickHouseAnalyticsWriter(AnalyticsWriter):
    """Feature-flagged analytics adapter with a safe no-op fallback path."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        fallback: AnalyticsWriter | None = None,
        database: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ):
        self.enabled = enabled
        self.fallback = fallback or NoopAnalyticsWriter()
        self.database = database or "default"
        self.host = host or "localhost"
        self.port = port or 9000
        self._buffer: dict[str, list[dict[str, Any]]] = {}

    def write_rows(self, table_name: str, rows: Sequence[Mapping[str, Any]]) -> int:
        if not self.enabled:
            return self.fallback.write_rows(table_name, rows)
        materialized = [dict(row) for row in rows]
        if not materialized:
            return 0
        self._buffer.setdefault(table_name, []).extend(materialized)
        return len(materialized)

    def get_buffer(self, table_name: str) -> list[dict[str, Any]]:
        return list(self._buffer.get(table_name, []))
