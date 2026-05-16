"""Add missing positions_realtime metadata columns

Revision ID: a8d1e5c2b7f9
Revises: f2a9b7c4d1e2
Create Date: 2026-05-16 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8d1e5c2b7f9"
down_revision: Union[str, Sequence[str], None] = "f2a9b7c4d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("positions_realtime"):
        return

    columns = {column["name"] for column in inspector.get_columns("positions_realtime")}

    if "hedge_ratio" not in columns:
        op.add_column(
            "positions_realtime",
            sa.Column("hedge_ratio", sa.Float(), nullable=True),
        )

    if "correlation" not in columns:
        op.add_column(
            "positions_realtime",
            sa.Column("correlation", sa.Float(), nullable=True),
        )

    if "half_life" not in columns:
        op.add_column(
            "positions_realtime",
            sa.Column("half_life", sa.Float(), nullable=True),
        )

    if "funding_rate" not in columns:
        op.add_column(
            "positions_realtime",
            sa.Column("funding_rate", sa.Float(), nullable=True),
        )

    if "dydx_order_ids" not in columns:
        op.add_column(
            "positions_realtime",
            sa.Column("dydx_order_ids", sa.JSON(), nullable=True),
        )

    if "dydx_position_id" not in columns:
        op.add_column(
            "positions_realtime",
            sa.Column("dydx_position_id", sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("positions_realtime"):
        return

    columns = {column["name"] for column in inspector.get_columns("positions_realtime")}

    if "half_life" in columns:
        op.drop_column("positions_realtime", "half_life")

    if "funding_rate" in columns:
        op.drop_column("positions_realtime", "funding_rate")

    if "dydx_order_ids" in columns:
        op.drop_column("positions_realtime", "dydx_order_ids")

    if "dydx_position_id" in columns:
        op.drop_column("positions_realtime", "dydx_position_id")

    if "correlation" in columns:
        op.drop_column("positions_realtime", "correlation")

    if "hedge_ratio" in columns:
        op.drop_column("positions_realtime", "hedge_ratio")
