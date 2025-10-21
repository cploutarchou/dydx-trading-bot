"""Add initial_amount field to BacktestStrategy

Revision ID: add_initial_amount
Revises: a0293f2df788
Create Date: 2025-10-21 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_initial_amount"
down_revision: Union[str, None] = "a0293f2df788"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add initial_amount column to backtest_strategies table."""
    op.add_column(
        "backtest_strategies",
        sa.Column(
            "initial_amount",
            sa.Float(),
            nullable=False,
            server_default="1000.0",
            comment="Initial investment amount (USD) allocated to this strategy",
        ),
    )


def downgrade() -> None:
    """Remove initial_amount column from backtest_strategies table."""
    op.drop_column("backtest_strategies", "initial_amount")
