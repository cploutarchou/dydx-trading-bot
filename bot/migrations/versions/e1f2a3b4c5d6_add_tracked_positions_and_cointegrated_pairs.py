"""Add tracked_positions and cointegrated_pairs tables

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tables for DB-backed position and cointegration state."""
    op.create_table(
        "tracked_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instance_id", sa.String(length=64), nullable=False),
        sa.Column("positions_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tracked_positions_instance_id"),
        "tracked_positions",
        ["instance_id"],
        unique=True,
    )

    op.create_table(
        "cointegrated_pairs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instance_id", sa.String(length=64), nullable=False),
        sa.Column("pairs_json", sa.JSON(), nullable=False),
        sa.Column("pairs_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_confidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("analyzed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cointegrated_pairs_instance_id"),
        "cointegrated_pairs",
        ["instance_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove tracked_positions and cointegrated_pairs tables."""
    op.drop_index(
        op.f("ix_cointegrated_pairs_instance_id"), table_name="cointegrated_pairs"
    )
    op.drop_table("cointegrated_pairs")
    op.drop_index(
        op.f("ix_tracked_positions_instance_id"), table_name="tracked_positions"
    )
    op.drop_table("tracked_positions")
