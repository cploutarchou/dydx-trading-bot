"""ClickHouse analytics writer adapter with safe no-op fallback."""

from __future__ import annotations

import atexit
import logging
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

try:  # pragma: no cover - optional dependency
    import clickhouse_connect
except Exception:  # pragma: no cover
    clickhouse_connect = None  # type: ignore[assignment]

from .analytics import AnalyticsWriter, NoopAnalyticsWriter

logger = logging.getLogger(__name__)

# DDL templates for auto-provisioned analytics tables.
# Uses MergeTree for simplicity; teams can tune engine/TTL per environment.
_BOT_EVENTS_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    event_date      Date,
    event_time      DateTime64(3, 'UTC'),
    bot_run_id      String,
    bot_id          String,
    event_type      LowCardinality(String),
    status          LowCardinality(String),
    strategy_id     Nullable(UInt64),
    worker_id       String,
    correlation_id  String,
    payload_attrs   String DEFAULT '{{}}'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (bot_id, bot_run_id, event_time, event_type)"""

_ORDER_EVENTS_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    event_date      Date,
    event_time      DateTime64(3, 'UTC'),
    order_id        String,
    trade_id        String DEFAULT '',
    bot_id          String,
    instance_id     String DEFAULT '',
    bot_run_id      String,
    market          String,
    side            LowCardinality(String),
    status          LowCardinality(String),
    event_type      LowCardinality(String),
    price           Nullable(Float64),
    size            Nullable(Float64),
    exchange_time   Nullable(DateTime64(3, 'UTC')),
    correlation_id  String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (bot_id, order_id, event_time)"""

_TRADE_EVENTS_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    event_date        Date,
    event_time        DateTime64(3, 'UTC'),
    trade_id          String,
    bot_id            String,
    instance_id       String DEFAULT '',
    pair1             String,
    pair2             String,
    side1             LowCardinality(String),
    side2             LowCardinality(String),
    status            LowCardinality(String),
    event_kind        LowCardinality(String),
    entry_price1      Float64 DEFAULT 0,
    entry_price2      Float64 DEFAULT 0,
    exit_price1       Nullable(Float64),
    exit_price2       Nullable(Float64),
    entry_size1       Float64 DEFAULT 0,
    entry_size2       Float64 DEFAULT 0,
    exit_size1        Nullable(Float64),
    exit_size2        Nullable(Float64),
    realized_pnl      Float64 DEFAULT 0,
    realized_pnl_pct  Float64 DEFAULT 0,
    closed_at         Nullable(DateTime64(3, 'UTC'))
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (bot_id, trade_id, event_time, event_kind)"""

_POSITION_SNAPSHOTS_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    snapshot_date       Date,
    snapshot_time       DateTime64(3, 'UTC'),
    position_id         String,
    bot_id              String,
    instance_id         String DEFAULT '',
    pair1               String,
    pair2               String,
    side1               LowCardinality(String),
    side2               LowCardinality(String),
    status              LowCardinality(String),
    event_kind          LowCardinality(String),
    entry_price1        Float64 DEFAULT 0,
    entry_price2        Float64 DEFAULT 0,
    current_price1      Nullable(Float64),
    current_price2      Nullable(Float64),
    entry_size1         Float64 DEFAULT 0,
    entry_size2         Float64 DEFAULT 0,
    current_size1       Nullable(Float64),
    current_size2       Nullable(Float64),
    unrealized_pnl      Float64 DEFAULT 0,
    unrealized_pnl_pct  Float64 DEFAULT 0,
    realized_pnl        Float64 DEFAULT 0,
    realized_pnl_pct    Float64 DEFAULT 0,
    z_score_entry       Nullable(Float64),
    z_score_current     Nullable(Float64),
    hedge_ratio         Nullable(Float64),
    correlation         Nullable(Float64),
    half_life           Nullable(Float64),
    funding_rate        Nullable(Float64),
    closed_at           Nullable(DateTime64(3, 'UTC'))
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (bot_id, position_id, snapshot_time, event_kind)"""

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

_BACKTEST_EQUITY_CURVE_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    run_id          String,
    point_time      String,
    equity          Float64 DEFAULT 0,
    cash            Nullable(Float64),
    drawdown_pct    Nullable(Float64),
    created_at      DateTime64(3, 'UTC') DEFAULT now64()
) ENGINE = MergeTree()
ORDER BY (run_id, point_time)"""

_STRATEGY_METRICS_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    run_id          String,
    metric_name     LowCardinality(String),
    metric_value    Float64 DEFAULT 0,
    strategy_id     Nullable(UInt64),
    scope           LowCardinality(String) DEFAULT 'backtest',
    metric_time     DateTime64(3, 'UTC') DEFAULT now64()
) ENGINE = MergeTree()
ORDER BY (run_id, metric_name, metric_time)"""

_WORKER_METRICS_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    metric_time     DateTime64(3, 'UTC'),
    worker_id       String,
    worker_type     LowCardinality(String),
    queue_name      LowCardinality(String),
    metric_name     LowCardinality(String),
    metric_value    Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(metric_time)
ORDER BY (worker_type, worker_id, metric_time, metric_name)"""

_API_REQUEST_EVENTS_DDL = """\
CREATE TABLE IF NOT EXISTS `{db}`.`{table}` (
    event_date      Date,
    event_time      DateTime64(3, 'UTC'),
    service         LowCardinality(String),
    route           String,
    method          LowCardinality(String),
    status_code     UInt16,
    latency_ms      UInt32,
    user_id         Nullable(String),
    correlation_id  String,
    rate_limited    UInt8 DEFAULT 0
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (service, route, event_time, status_code)"""

_TABLE_DDL: dict[str, str] = {
    "bot_event_rows": _BOT_EVENTS_DDL,
    "bot_events": _BOT_EVENTS_DDL,
    "order_event_rows": _ORDER_EVENTS_DDL,
    "order_events": _ORDER_EVENTS_DDL,
    "trade_event_rows": _TRADE_EVENTS_DDL,
    "trade_events": _TRADE_EVENTS_DDL,
    "position_snapshot_rows": _POSITION_SNAPSHOTS_DDL,
    "position_snapshots": _POSITION_SNAPSHOTS_DDL,
    "backtest_trade_rows": _BACKTEST_TRADES_DDL,
    "backtest_trades": _BACKTEST_TRADES_DDL,
    "backtest_daily_pnl_rows": _BACKTEST_DAILY_PNL_DDL,
    "backtest_daily_pnl": _BACKTEST_DAILY_PNL_DDL,
    "backtest_position_snapshot_rows": _BACKTEST_POSITION_SNAPSHOTS_DDL,
    "backtest_position_snapshots": _BACKTEST_POSITION_SNAPSHOTS_DDL,
    "backtest_equity_curve_rows": _BACKTEST_EQUITY_CURVE_DDL,
    "backtest_equity_curve": _BACKTEST_EQUITY_CURVE_DDL,
    "strategy_metric_rows": _STRATEGY_METRICS_DDL,
    "strategy_metrics": _STRATEGY_METRICS_DDL,
    "worker_metrics": _WORKER_METRICS_DDL,
    "worker_metric_rows": _WORKER_METRICS_DDL,
    "api_request_events": _API_REQUEST_EVENTS_DDL,
    "api_request_event_rows": _API_REQUEST_EVENTS_DDL,
}

_TABLE_ALTERS: dict[str, tuple[str, ...]] = {
    "order_event_rows": (
        "ALTER TABLE `{db}`.`{table}` ADD COLUMN IF NOT EXISTS instance_id String DEFAULT '' AFTER bot_id",
    ),
    "order_events": (
        "ALTER TABLE `{db}`.`{table}` ADD COLUMN IF NOT EXISTS instance_id String DEFAULT '' AFTER bot_id",
    ),
    "trade_event_rows": (
        "ALTER TABLE `{db}`.`{table}` ADD COLUMN IF NOT EXISTS instance_id String DEFAULT '' AFTER bot_id",
    ),
    "trade_events": (
        "ALTER TABLE `{db}`.`{table}` ADD COLUMN IF NOT EXISTS instance_id String DEFAULT '' AFTER bot_id",
    ),
    "position_snapshot_rows": (
        "ALTER TABLE `{db}`.`{table}` ADD COLUMN IF NOT EXISTS instance_id String DEFAULT '' AFTER bot_id",
    ),
    "position_snapshots": (
        "ALTER TABLE `{db}`.`{table}` ADD COLUMN IF NOT EXISTS instance_id String DEFAULT '' AFTER bot_id",
    ),
}


class ClickHouseAnalyticsWriter(AnalyticsWriter):
    """Feature-flagged ClickHouse adapter with a safe no-op fallback path.

    When enabled, rows are written to ClickHouse over HTTP using
    ``clickhouse-connect``. Rows can be buffered in-memory and flushed by batch
    size or flush interval. On any connection or write error the writer falls
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
        self.batch_size = self._coerce_positive_int(
            self.extra_config.get("batch_size"), default=1
        )
        self.flush_interval_seconds = self._coerce_non_negative_float(
            self.extra_config.get("flush_interval_seconds"),
            default=0.0,
        )
        self._buffering_enabled = (
            self.batch_size > 1 or self.flush_interval_seconds > 0
        )
        self._provisioned: set[str] = set()
        self._buffers: dict[str, list[dict[str, Any]]] = {}
        self._buffer_started_at: dict[str, float] = {}
        self._lock = threading.Lock()
        self._client = self._build_client()
        if self._buffering_enabled:
            atexit.register(self.close)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_positive_int(raw: Any, *, default: int) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        return max(1, value)

    @staticmethod
    def _coerce_non_negative_float(raw: Any, *, default: float) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return default
        return max(0.0, value)

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
            for alter_template in _TABLE_ALTERS.get(table_name, ()):
                self._client.command(
                    alter_template.format(db=self.database, table=table_name)
                )
            self._provisioned.add(table_name)
        except Exception as exc:
            logger.warning(
                "ClickHouse DDL provisioning failed for %s: %s", table_name, exc
            )

    def _insert_rows(
        self,
        table_name: str,
        rows: Sequence[Mapping[str, Any]],
    ) -> int:
        if self._client is None:
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

    def _buffer_due(self, table_name: str, now: float) -> bool:
        buffered = self._buffers.get(table_name) or []
        if not buffered:
            return False
        if len(buffered) >= self.batch_size:
            return True
        if self.flush_interval_seconds <= 0:
            return False
        started_at = self._buffer_started_at.get(table_name, now)
        return (now - started_at) >= self.flush_interval_seconds

    def _flush_one_locked(
        self, table_name: str, *, force: bool = False, now: float | None = None
    ) -> int:
        timestamp = time.monotonic() if now is None else now
        if not force and not self._buffer_due(table_name, timestamp):
            return 0

        buffered = self._buffers.get(table_name) or []
        if not buffered:
            return 0

        count = self._insert_rows(table_name, buffered)
        self._buffers.pop(table_name, None)
        self._buffer_started_at.pop(table_name, None)
        return count

    # ------------------------------------------------------------------
    # AnalyticsWriter interface
    # ------------------------------------------------------------------

    def write_rows(self, table_name: str, rows: Sequence[Mapping[str, Any]]) -> int:
        if not self.enabled or self._client is None:
            return self.fallback.write_rows(table_name, rows)

        materialized = [dict(row) for row in rows]
        if not materialized:
            return 0

        if not self._buffering_enabled:
            return self._insert_rows(table_name, materialized)

        with self._lock:
            buffer = self._buffers.setdefault(table_name, [])
            if not buffer:
                self._buffer_started_at[table_name] = time.monotonic()
            buffer.extend(materialized)
            return self._flush_one_locked(table_name)

    def flush(
        self, table_name: str | None = None, *, force: bool = False
    ) -> dict[str, int]:
        if not self._buffering_enabled:
            return {}

        with self._lock:
            now = time.monotonic()
            table_names = [table_name] if table_name else list(self._buffers.keys())
            flushed: dict[str, int] = {}
            for current_table in table_names:
                count = self._flush_one_locked(current_table, force=force, now=now)
                if count > 0:
                    flushed[current_table] = count
            return flushed

    # ------------------------------------------------------------------
    # Test / debug helpers
    # ------------------------------------------------------------------

    def get_buffer(self, table_name: str) -> list[dict[str, Any]]:
        """Return a copy of the pending in-memory buffer for tests/debugging."""
        with self._lock:
            return [dict(row) for row in self._buffers.get(table_name, [])]
