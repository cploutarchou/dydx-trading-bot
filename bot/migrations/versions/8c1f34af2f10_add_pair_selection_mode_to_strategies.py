"""Add pair selection mode to strategies

Revision ID: 8c1f34af2f10
Revises: 64bafb411810
Create Date: 2026-03-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c1f34af2f10"
down_revision: Union[str, Sequence[str], None] = "64bafb411810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    if not inspector.has_table("backtest_strategies"):
        return

    columns = {column["name"] for column in inspector.get_columns("backtest_strategies")}
    if "pair_selection_mode" in columns:
        return

    if dialect == "sqlite":
        op.add_column(
            "backtest_strategies",
            sa.Column(
                "pair_selection_mode",
                sa.String(length=32),
                nullable=False,
                server_default="liquidity",
            ),
        )
        return

    op.add_column(
        "backtest_strategies",
        sa.Column(
            "pair_selection_mode",
            sa.String(length=32),
            nullable=True,
            server_default="liquidity",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE backtest_strategies "
            "SET pair_selection_mode = 'liquidity' "
            "WHERE pair_selection_mode IS NULL"
        )
    )
    op.alter_column(
        "backtest_strategies",
        "pair_selection_mode",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("backtest_strategies"):
        return

    columns = {column["name"] for column in inspector.get_columns("backtest_strategies")}
    if "pair_selection_mode" not in columns:
        return

    op.drop_column("backtest_strategies", "pair_selection_mode")
