"""Initial PostgreSQL schema — consolidated from all MariaDB revisions.

Revision ID: 0001_pg_initial
Revises:
Create Date: 2026-06-21 00:00:00.000000

This is the root revision for the PostgreSQL migration branch.  It creates
the full schema in one shot so that a fresh PostgreSQL deployment can be
brought up by running a single ``alembic upgrade head`` without replaying the
MariaDB history.

Key PostgreSQL differences from the MariaDB revisions:
- Enum types are native ``CREATE TYPE … AS ENUM`` objects, not VARCHAR+CHECK.
- JSON columns use ``JSONB`` for efficient indexing and containment queries.
- Boolean defaults use ``false``/``true`` SQL literals, not 0/1.
- ``SERIAL`` / ``BIGSERIAL`` replace ``AUTO_INCREMENT``.
- No ``ENGINE=InnoDB`` or ``INSERT IGNORE``; use ``ON CONFLICT DO NOTHING``.
- ``ALTER TABLE … DROP COLUMN IF EXISTS`` is safe in PostgreSQL 9.0+.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "0001_pg_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Enum type names
# ---------------------------------------------------------------------------

BOT_STATUS_ENUM = "botstatusenum"
JOB_STATUS_ENUM = "jobstatusenum"
TRADE_STATUS_ENUM = "tradestatusenum"
POSITION_STATUS_ENUM = "positionstatusenum"
ALERT_SEVERITY_ENUM = "alertseverityenum"

_bot_status = postgresql.ENUM(
    "created",
    "starting",
    "running",
    "stopping",
    "stopped",
    "error",
    "recovering",
    "degraded",
    "safeguarded",
    name=BOT_STATUS_ENUM,
)
_job_status = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
    name=JOB_STATUS_ENUM,
)
_trade_status = postgresql.ENUM(
    "open",
    "closed",
    "cancelled",
    name=TRADE_STATUS_ENUM,
)
_position_status = postgresql.ENUM(
    "open",
    "closed",
    "liquidated",
    name=POSITION_STATUS_ENUM,
)
_alert_severity = postgresql.ENUM(
    "info",
    "warning",
    "critical",
    name=ALERT_SEVERITY_ENUM,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _jsonb() -> sa.types.TypeDecorator:
    """Return a JSONB column type (PostgreSQL-native)."""
    return postgresql.JSONB(none_as_null=True)


def _now_utc() -> sa.text:
    # TIMESTAMPTZ stores an absolute instant; connections are configured with
    # timezone=UTC, so CURRENT_TIMESTAMP round-trips in UTC without invalid SQL.
    return sa.text("CURRENT_TIMESTAMP")


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Create the full schema from scratch on a clean PostgreSQL database."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # -- Enum types ----------------------------------------------------------
    _bot_status.create(bind, checkfirst=True)
    _job_status.create(bind, checkfirst=True)
    _trade_status.create(bind, checkfirst=True)
    _position_status.create(bind, checkfirst=True)
    _alert_severity.create(bind, checkfirst=True)

    # -- bot_instances -------------------------------------------------------
    if not inspector.has_table("bot_instances"):
        op.create_table(
            "bot_instances",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("instance_id", sa.String(50), nullable=False),
            sa.Column("network", sa.String(20), nullable=False),
            sa.Column("strategy", sa.String(50), nullable=False),
            sa.Column("config", _jsonb(), nullable=False, server_default="{}"),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "created",
                    "starting",
                    "running",
                    "stopping",
                    "stopped",
                    "error",
                    "recovering",
                    "degraded",
                    "safeguarded",
                    name=BOT_STATUS_ENUM,
                    create_type=False,
                ),
                nullable=False,
                server_default="created",
            ),
            sa.Column("process_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
        )
        op.create_index(
            "ix_bot_instances_instance_id",
            "bot_instances",
            ["instance_id"],
            unique=True,
        )

    # -- jobs ----------------------------------------------------------------
    if not inspector.has_table("jobs"):
        op.create_table(
            "jobs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("job_id", sa.String(64), nullable=False),
            sa.Column(
                "bot_id",
                sa.Integer(),
                sa.ForeignKey("bot_instances.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("job_type", sa.String(50), nullable=False),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "pending",
                    "running",
                    "completed",
                    "failed",
                    "cancelled",
                    name=JOB_STATUS_ENUM,
                    create_type=False,
                ),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("config", _jsonb(), nullable=True),
            sa.Column("result", _jsonb(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("error_traceback", sa.Text(), nullable=True),
            sa.Column("cancellation_reason", sa.Text(), nullable=True),
            sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("metadata_json", _jsonb(), nullable=False, server_default="{}"),
            sa.Column("process_id", sa.Integer(), nullable=True),
            sa.Column("execution_time_ms", sa.Integer(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            # Observability fields added in c9f4a7b2d1e3 (included from start on PG)
            sa.Column("supervisor_task_id", sa.String(128), nullable=True),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("worker_node", sa.String(64), nullable=True),
            sa.Column("queue_name", sa.String(64), nullable=True),
        )
        op.create_index("ix_jobs_job_id", "jobs", ["job_id"], unique=True)
        op.create_index("ix_jobs_bot_id", "jobs", ["bot_id"])
        op.create_index("ix_jobs_status", "jobs", ["status"])

    # -- trades --------------------------------------------------------------
    if not inspector.has_table("trades"):
        op.create_table(
            "trades",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "bot_id",
                sa.Integer(),
                sa.ForeignKey("bot_instances.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("trade_id", sa.String(100), nullable=False),
            sa.Column("pair1", sa.String(20), nullable=False),
            sa.Column("pair2", sa.String(20), nullable=False),
            sa.Column("side1", sa.String(10), nullable=False),
            sa.Column("side2", sa.String(10), nullable=False),
            sa.Column("entry_price1", sa.Float(), nullable=False),
            sa.Column("entry_price2", sa.Float(), nullable=False),
            sa.Column("exit_price1", sa.Float(), nullable=True),
            sa.Column("exit_price2", sa.Float(), nullable=True),
            sa.Column("entry_size1", sa.Float(), nullable=False),
            sa.Column("entry_size2", sa.Float(), nullable=False),
            sa.Column("exit_size1", sa.Float(), nullable=True),
            sa.Column("exit_size2", sa.Float(), nullable=True),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "open",
                    "closed",
                    "cancelled",
                    name=TRADE_STATUS_ENUM,
                    create_type=False,
                ),
                nullable=False,
                server_default="open",
            ),
            sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "realized_pnl_pct", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column("profit_loss", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "profit_loss_percentage", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column("unrealized_pnl", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "unrealized_pnl_pct", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_trades_trade_id", "trades", ["trade_id"])
        op.create_index("ix_trades_bot_id", "trades", ["bot_id"])

    # -- event_logs ----------------------------------------------------------
    if not inspector.has_table("event_logs"):
        op.create_table(
            "event_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bot_instance_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("details", _jsonb(), nullable=True),
            sa.Column("user_id", sa.String(128), nullable=True),
            sa.Column("related_job_id", sa.String(64), nullable=True),
            sa.Column("related_trade_id", sa.String(64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
        )
        op.create_index(
            "ix_event_logs_bot_instance_id", "event_logs", ["bot_instance_id"]
        )
        op.create_index("ix_event_logs_event_type", "event_logs", ["event_type"])
        op.create_index("ix_event_logs_created_at", "event_logs", ["created_at"])

    # -- backtest_strategies -------------------------------------------------
    if not inspector.has_table("backtest_strategies"):
        op.create_table(
            "backtest_strategies",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("category", sa.String(64), nullable=True),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("is_public", sa.Boolean(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "zscore_threshold", sa.Float(), nullable=False, server_default="1.5"
            ),
            sa.Column(
                "stats_window", sa.Integer(), nullable=False, server_default="21"
            ),
            sa.Column(
                "max_half_life", sa.Float(), nullable=False, server_default="24.0"
            ),
            sa.Column(
                "usd_per_trade", sa.Float(), nullable=False, server_default="10.0"
            ),
            sa.Column(
                "usd_min_collateral", sa.Float(), nullable=False, server_default="100.0"
            ),
            sa.Column(
                "close_at_zscore_cross",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column(
                "find_cointegrated_pairs",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column(
                "manage_exits", sa.Boolean(), nullable=False, server_default="true"
            ),
            sa.Column(
                "place_trades", sa.Boolean(), nullable=False, server_default="true"
            ),
            sa.Column(
                "abort_all_positions",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "max_positions", sa.Integer(), nullable=False, server_default="5"
            ),
            sa.Column(
                "max_drawdown_pct", sa.Float(), nullable=False, server_default="15.0"
            ),
            sa.Column(
                "stop_loss_pct", sa.Float(), nullable=False, server_default="3.0"
            ),
            sa.Column(
                "take_profit_pct", sa.Float(), nullable=False, server_default="8.0"
            ),
            sa.Column(
                "trailing_stop_pct", sa.Float(), nullable=False, server_default="2.0"
            ),
            sa.Column(
                "rebalance_interval_hours",
                sa.Integer(),
                nullable=False,
                server_default="24",
            ),
            sa.Column(
                "position_timeout_hours",
                sa.Integer(),
                nullable=False,
                server_default="72",
            ),
            sa.Column(
                "pair_selection_mode",
                sa.String(32),
                nullable=False,
                server_default="'liquidity'",
            ),
            sa.Column(
                "transaction_fee", sa.Float(), nullable=False, server_default="0.0005"
            ),
            sa.Column("slippage", sa.Float(), nullable=False, server_default="0.001"),
            sa.Column(
                "starting_balance", sa.Float(), nullable=False, server_default="1000.0"
            ),
            sa.Column(
                "candle_resolution",
                sa.String(32),
                nullable=False,
                server_default="'1HOUR'",
            ),
            sa.Column(
                "max_history_days", sa.Integer(), nullable=False, server_default="90"
            ),
            sa.Column("benchmark_symbol", sa.String(64), nullable=True),
            sa.Column(
                "risk_free_rate", sa.Float(), nullable=False, server_default="0.02"
            ),
            sa.Column(
                "initial_amount", sa.Float(), nullable=False, server_default="1000.0"
            ),
            sa.Column("usage_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )

    # -- strategy_version_history --------------------------------------------
    if not inspector.has_table("strategy_version_history"):
        op.create_table(
            "strategy_version_history",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "strategy_id",
                sa.Integer(),
                sa.ForeignKey("backtest_strategies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "version_number", sa.Integer(), nullable=False, server_default="1"
            ),
            sa.Column("change_description", sa.String(255), nullable=True),
            sa.Column("config_snapshot", _jsonb(), nullable=False, server_default="{}"),
            sa.Column("changes", _jsonb(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=_now_utc(),
            ),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("backtest_count", sa.Integer(), nullable=True),
            sa.Column("best_backtest_pnl", sa.Float(), nullable=True),
            sa.Column("average_backtest_pnl", sa.Float(), nullable=True),
        )
        op.create_index(
            "ix_strategy_version_history_strategy_id",
            "strategy_version_history",
            ["strategy_id"],
        )

    # -- backtest_runtime_runs -----------------------------------------------
    if not inspector.has_table("backtest_runtime_runs"):
        op.create_table(
            "backtest_runtime_runs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(64), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column(
                "status", sa.String(32), nullable=False, server_default="'pending'"
            ),
            sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("current_pair", sa.String(255), nullable=True),
            sa.Column("current_task", sa.String(64), nullable=True),
            sa.Column("total_pnl", sa.Float(), nullable=False, server_default="0"),
            sa.Column("win_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("sharpe_ratio", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "max_drawdown_pct", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("profit_factor", sa.Float(), nullable=False, server_default="0"),
            sa.Column("start_date", sa.String(32), nullable=True),
            sa.Column("end_date", sa.String(32), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("request_json", _jsonb(), nullable=False, server_default="{}"),
            sa.Column("trades_json", _jsonb(), nullable=False, server_default="[]"),
            sa.Column(
                "position_snapshots_json", _jsonb(), nullable=False, server_default="[]"
            ),
            sa.Column("daily_pnl_json", _jsonb(), nullable=False, server_default="[]"),
            sa.Column(
                "cancel_requested", sa.Boolean(), nullable=False, server_default="false"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("timeout_seconds", sa.Float(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            # artifact_refs and analytics metadata from sidecar writes (phase 7+)
            sa.Column("artifact_refs", _jsonb(), nullable=True),
            sa.Column(
                "analytics_rows_written",
                sa.Integer(),
                nullable=True,
                server_default="0",
            ),
        )
        op.create_index(
            "ix_backtest_runtime_runs_run_id",
            "backtest_runtime_runs",
            ["run_id"],
            unique=True,
        )
        op.create_index(
            "ix_backtest_runtime_runs_status", "backtest_runtime_runs", ["status"]
        )
        op.create_index(
            "ix_backtest_runtime_runs_created_at",
            "backtest_runtime_runs",
            ["created_at"],
        )
        op.create_index(
            "ix_backtest_runtime_runs_started_at",
            "backtest_runtime_runs",
            ["started_at"],
        )
        op.create_index(
            "ix_backtest_runtime_runs_completed_at",
            "backtest_runtime_runs",
            ["completed_at"],
        )
        op.create_index(
            "ix_backtest_runtime_runs_updated_at",
            "backtest_runtime_runs",
            ["updated_at"],
        )

    # -- backtest_run_requests -----------------------------------------------
    if not inspector.has_table("backtest_run_requests"):
        op.create_table(
            "backtest_run_requests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "run_id",
                sa.String(64),
                sa.ForeignKey("backtest_runtime_runs.run_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("request_json", _jsonb(), nullable=False, server_default="{}"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
        )
        op.create_index(
            "ix_backtest_run_requests_run_id",
            "backtest_run_requests",
            ["run_id"],
            unique=True,
        )

    # -- positions_realtime --------------------------------------------------
    if not inspector.has_table("positions_realtime"):
        op.create_table(
            "positions_realtime",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bot_instance_id", sa.Integer(), nullable=False),
            sa.Column("position_id", sa.String(100), nullable=False),
            sa.Column("pair1", sa.String(20), nullable=False),
            sa.Column("pair2", sa.String(20), nullable=False),
            sa.Column("side1", sa.String(10), nullable=False),
            sa.Column("side2", sa.String(10), nullable=False),
            sa.Column("entry_price1", sa.Float(), nullable=False),
            sa.Column("entry_price2", sa.Float(), nullable=False),
            sa.Column("current_price1", sa.Float(), nullable=True),
            sa.Column("current_price2", sa.Float(), nullable=True),
            sa.Column("entry_size1", sa.Float(), nullable=False),
            sa.Column("entry_size2", sa.Float(), nullable=False),
            sa.Column("current_size1", sa.Float(), nullable=True),
            sa.Column("current_size2", sa.Float(), nullable=True),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "open",
                    "closed",
                    "liquidated",
                    name=POSITION_STATUS_ENUM,
                    create_type=False,
                ),
                nullable=False,
                server_default="open",
            ),
            sa.Column("unrealized_pnl", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "unrealized_pnl_pct", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "realized_pnl_pct", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column("z_score_entry", sa.Float(), nullable=True),
            sa.Column("z_score_current", sa.Float(), nullable=True),
            sa.Column(
                "entry_time",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            # Cointegration metadata
            sa.Column("hedge_ratio", sa.Float(), nullable=True),
            sa.Column("correlation", sa.Float(), nullable=True),
            sa.Column("half_life", sa.Float(), nullable=True),
            # dYdX-specific
            sa.Column("funding_rate", sa.Float(), nullable=True),
            sa.Column("dydx_order_ids", _jsonb(), nullable=True),
            sa.Column("dydx_position_id", sa.String(100), nullable=True),
        )
        op.create_index(
            "ix_positions_realtime_bot_instance_id",
            "positions_realtime",
            ["bot_instance_id"],
        )
        op.create_index(
            "ix_positions_realtime_position_id", "positions_realtime", ["position_id"]
        )
        op.create_index(
            "ix_positions_realtime_dydx_position_id",
            "positions_realtime",
            ["dydx_position_id"],
        )

    # -- market_data_realtime ------------------------------------------------
    if not inspector.has_table("market_data_realtime"):
        op.create_table(
            "market_data_realtime",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bot_instance_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(20), nullable=False),
            sa.Column("current_price", sa.Float(), nullable=False),
            sa.Column("bid_price", sa.Float(), nullable=True),
            sa.Column("ask_price", sa.Float(), nullable=True),
            sa.Column("volume_24h", sa.Float(), nullable=True),
            sa.Column("volatility_24h", sa.Float(), nullable=True),
            sa.Column("rsi", sa.Float(), nullable=True),
            sa.Column("macd", sa.Float(), nullable=True),
            sa.Column("moving_avg_20", sa.Float(), nullable=True),
            sa.Column("moving_avg_50", sa.Float(), nullable=True),
            sa.Column("funding_rate", sa.Float(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
        )
        op.create_index(
            "ix_market_data_realtime_bot_instance_id",
            "market_data_realtime",
            ["bot_instance_id"],
        )
        op.create_index(
            "ix_market_data_realtime_symbol", "market_data_realtime", ["symbol"]
        )

    # -- bot_stats_realtime --------------------------------------------------
    if not inspector.has_table("bot_stats_realtime"):
        op.create_table(
            "bot_stats_realtime",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bot_instance_id", sa.Integer(), nullable=False),
            sa.Column(
                "total_open_positions", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "total_unrealized_pnl", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column(
                "total_unrealized_pnl_pct",
                sa.Float(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("daily_pnl", sa.Float(), nullable=False, server_default="0"),
            sa.Column("daily_pnl_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "daily_trades_opened", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "daily_trades_closed", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("daily_win_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_drawdown_session", sa.Float(), nullable=True),
            sa.Column(
                "current_drawdown", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column(
                "session_start",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
        )
        op.create_index(
            "ix_bot_stats_realtime_bot_instance_id",
            "bot_stats_realtime",
            ["bot_instance_id"],
            unique=True,
        )

    # -- alerts_realtime -----------------------------------------------------
    if not inspector.has_table("alerts_realtime"):
        op.create_table(
            "alerts_realtime",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bot_instance_id", sa.Integer(), nullable=False),
            sa.Column("alert_type", sa.String(50), nullable=False),
            sa.Column(
                "severity",
                postgresql.ENUM(
                    "info",
                    "warning",
                    "critical",
                    name=ALERT_SEVERITY_ENUM,
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("details", _jsonb(), nullable=True),
            sa.Column(
                "acknowledged", sa.Boolean(), nullable=False, server_default="false"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_alerts_realtime_bot_instance_id", "alerts_realtime", ["bot_instance_id"]
        )

    # -- tracked_positions ---------------------------------------------------
    if not inspector.has_table("tracked_positions"):
        op.create_table(
            "tracked_positions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("instance_id", sa.String(64), nullable=False),
            sa.Column("positions_json", _jsonb(), nullable=False, server_default="[]"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
        )
        op.create_index(
            "ix_tracked_positions_instance_id",
            "tracked_positions",
            ["instance_id"],
            unique=True,
        )

    # -- cointegrated_pairs --------------------------------------------------
    if not inspector.has_table("cointegrated_pairs"):
        op.create_table(
            "cointegrated_pairs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("instance_id", sa.String(64), nullable=False),
            sa.Column("pairs_json", _jsonb(), nullable=False, server_default="[]"),
            sa.Column("pairs_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "high_confidence_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "analyzed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_now_utc(),
            ),
        )
        op.create_index(
            "ix_cointegrated_pairs_instance_id",
            "cointegrated_pairs",
            ["instance_id"],
            unique=True,
        )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    """Drop all tables and enum types created by this revision."""

    # Drop tables in reverse FK dependency order
    for table in [
        "cointegrated_pairs",
        "tracked_positions",
        "alerts_realtime",
        "bot_stats_realtime",
        "market_data_realtime",
        "positions_realtime",
        "backtest_run_requests",
        "backtest_runtime_runs",
        "strategy_version_history",
        "backtest_strategies",
        "event_logs",
        "trades",
        "jobs",
        "bot_instances",
    ]:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {table} CASCADE"))  # noqa: S608

    # Drop enum types
    bind = op.get_bind()
    for enum in (
            _bot_status,
            _job_status,
            _trade_status,
            _position_status,
            _alert_severity,
    ):
        enum.drop(bind, checkfirst=True)
