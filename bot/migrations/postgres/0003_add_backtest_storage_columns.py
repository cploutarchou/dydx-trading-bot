"""Add artifact_refs and analytics_rows_written columns to backtest_runtime_runs.

These columns were added to the initial schema definition as phase 7+ sidecar-write
metadata, but databases created before that update need them added via migration.

Revision ID: 0003_backtest_storage_cols
Revises: 0002_artifact_refs
Create Date: 2026-06-28 00:00:00.000000

Lock risk: LOW — both columns are nullable additions; no table rewrite required.

Downgrade plan: Drop both columns. No data loss concern as they are optional metadata.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_backtest_storage_cols"
down_revision: Union[str, Sequence[str], None] = "0002_artifact_refs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonb() -> sa.types.TypeDecorator:
    return postgresql.JSONB(none_as_null=True)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("backtest_runtime_runs"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("backtest_runtime_runs")}

    if "artifact_refs" not in existing_columns:
        op.add_column(
            "backtest_runtime_runs",
            sa.Column("artifact_refs", _jsonb(), nullable=True),
        )

    if "analytics_rows_written" not in existing_columns:
        op.add_column(
            "backtest_runtime_runs",
            sa.Column(
                "analytics_rows_written",
                sa.Integer(),
                nullable=True,
                server_default="0",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("backtest_runtime_runs"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("backtest_runtime_runs")}

    if "analytics_rows_written" in existing_columns:
        op.drop_column("backtest_runtime_runs", "analytics_rows_written")

    if "artifact_refs" in existing_columns:
        op.drop_column("backtest_runtime_runs", "artifact_refs")

