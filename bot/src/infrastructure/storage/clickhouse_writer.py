"""ClickHouse analytics writer adapter with safe no-op fallback."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

try:  # pragma: no cover - optional dependency
    import clickhouse_connect
except Exception:  # pragma: no cover
    clickhouse_connect = None  # type: ignore[assignment]

from .analytics import AnalyticsWriter, NoopAnalyticsWriter

logger = logging.getLogger(__name__)

# DDL templates for auto-provisioned backtest analytics tables.
# Uses MergeTree for simplicity; teams can tune engine/TTL per environment.
_BACKTEST_TRADES_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    run_id           String,
    trade_id         String,
    pair1            String,
    pair2            String,
    side1            String,
    side2            String,
    entry_price1     Float64 DEFAULT 0,
    entry_price2     Float64 DEFAULT 0,
    exit_price1      Nullable(Float64),
    exit_price2      Nullable(Float64),
    entry_size1      Float64 DEFAULT 0,
    entry_size2      Float64 DEFAULT 0,
    realized_pnl     Float64 DEFAULT 0,
    realized_pnl_pct Float64 DEFAULT 0,
    status           String DEFAULT '',
    created_at       DateTime64(3, 'UTC') DEFAULT now64()
) ENGINE = MergeTree()
ORDER BY (run_id, created_at)"""

_BACKTEST_DAILY_PNL_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    run_id          String,
    date            String,
    pnl             Float64 DEFAULT 0,
    cumulative_pnl  Float64 DEFAULT 0,
    drawdown        Float64 DEFAULT 0,
    created_at      DateTime64(3, 'UTC') DEFAULT now64()
) ENGINE = MergeTree()
ORDER BY (run_id, date)"""

_BACKTEST_POSITION_SNAPSHOTS_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    run_id          String,
    snapshot_time   String,
    pair1           String DEFAULT '',
    pair2           String DEFAULT '',
    unrealized_pnl  Float64 DEFAULT 0,
    z_score         Nullable(Float64),
    created_at      DateTime64(3, 'UTC') DEFAULT now64()
) ENGINE = MergeTree()
ORDER BY (run_id, snapshot_time)"""

_TABLE_DDL: dict[str, str] = {
    "backtest_trade_rows": _BACKTEST_TRADES_DDL,
    "backtest_trades": _BACKTEST_TRADES_DDL,
    "backtest_daily_pnl_rows": _BACKTEST_DAILY_PNL_DDL,
    "backtest_daily_pnl": _BACKTEST_DAILY_PNL_DDL,
    "backtest_position_snapshot_rows": _BACKTEST_POSITION_SNAPSHOTS_DDL,
    "backtest_position_snapshots": _BACKTEST_POSITION_SNAPSHOTS_DDL,
}


class ClickHouseAnalyticsWriter(AnalyticsWriter):
    """Feature-flagged ClickHouse adapter with a safe no-op fallback path.

    When enabled, rows are written immediately to ClickHouse over HTTP using
    ``clickhouse-connect``.  On any connection or write error the writer falls
    back to the configured ``fallback`` (default: ``NoopAnalyticsWriter``).

    Tables for known backtest analytics streams are auto-provisioned via DDL on
    the first write; unknown table names are written without DDL provisioning.

    Configuration is passed through ``extra_config`` so the constructor
    signature remains stable as new options are added.  A test double can be
    injected via ``extra_config["client"]`` to bypass real network calls.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        fallback: AnalyticsWriter | None = None,
        database: str | None = None,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        secure: bool = False,
        extra_config: dict[str, Any] | None = None,
    ):
        self.enabled = enabled
        self.fallback = fallback or NoopAnalyticsWriter()
        self.database = database or "default"
        self.host = host or "localhost"
        self.port = port or 8123  # ClickHouse HTTP interface default
        self.username = username or "default"
        self.password = password or ""
        self.secure = secure
        self.extra_config = dict(extra_config or {})
        self._provisioned: set[str] = set()
        self._client = self._build_client()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_client(self) -> Any | None:
        if not self.enabled:
            return None

        injected = self.extra_config.get("client")
        if injected is not None:
            return injected

        if clickhouse_connect is None:  # pragma: no cover
            logger.warning(
                "ClickHouse adapter enabled but clickhouse-connect is not installed; "
                "install it with: pip install clickhouse-connect"
            )
            return None

        try:
            return clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database=self.database,
                secure=self.secure,
            )
        except Exception as exc:
            logger.warning(
                "ClickHouse connection failed; writes will use fallback: %s", exc
            )
            return None

    def _ensure_table(self, table_name: str) -> None:
        """Run DDL for *table_name* on the first write if a template is known."""
        if self._client is None or table_name in self._provisioned:
            return
        ddl_template = _TABLE_DDL.get(table_name)
        if ddl_template is None:
            # Unknown table — skip DDL but still attempt the insert.
            self._provisioned.add(table_name)
            return
        try:
            self._client.command(
                ddl_template.format(db=self.database, table=table_name)
            )
            self._provisioned.add(table_name)
        except Exception as exc:
            logger.warning(
                "ClickHouse DDL provisioning failed for %s: %s", table_name, exc
            )

    # ------------------------------------------------------------------
    # AnalyticsWriter interface
    # ------------------------------------------------------------------

    def write_rows(self, table_name: str, rows: Sequence[Mapping[str, Any]]) -> int:
        if not self.enabled or self._client is None:
            return self.fallback.write_rows(table_name, rows)

        materialized = [dict(row) for row in rows]
        if not materialized:
            return 0

        self._ensure_table(table_name)

        try:
            column_names = list(materialized[0].keys())
            data = [[row.get(col) for col in column_names] for row in materialized]
            self._client.insert(
                table=f"{self.database}.{table_name}",
                data=data,
                column_names=column_names,
            )
            return len(materialized)
        except Exception as exc:
            logger.warning(
                "ClickHouse write failed for %s; using fallback: %s",
                table_name,
                exc,
            )
            return self.fallback.write_rows(table_name, rows)

    # ------------------------------------------------------------------
    # Test / debug helpers
    # ------------------------------------------------------------------

    def get_buffer(self, table_name: str) -> list[dict[str, Any]]:
        """No-op compatibility shim — the real writer has no in-memory buffer.

        The buffer concept was present in the placeholder implementation.  Real
        code should not depend on this method.  It exists only so that tests
        that were written against the placeholder continue to pass.
        """
        del table_name
        return []
