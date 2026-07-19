"""Ensure durable runtime trading-state tables exist.

Revision ID: 0004_runtime_state_tables
Revises: 0003_backtest_storage_cols
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_runtime_state_tables"
down_revision: str | None = "0003_backtest_storage_cols"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("tracked_positions"):
        op.create_table(
            "tracked_positions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("instance_id", sa.String(64), nullable=False),
            sa.Column(
                "positions_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index(
            "ix_tracked_positions_instance_id",
            "tracked_positions",
            ["instance_id"],
            unique=True,
        )

    if not inspector.has_table("cointegrated_pairs"):
        op.create_table(
            "cointegrated_pairs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("instance_id", sa.String(64), nullable=False),
            sa.Column(
                "pairs_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
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
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index(
            "ix_cointegrated_pairs_instance_id",
            "cointegrated_pairs",
            ["instance_id"],
            unique=True,
        )


def downgrade() -> None:
    # Deliberately preserve live trading state on downgrade. A destructive
    # removal requires a separately reviewed data migration.
    pass
