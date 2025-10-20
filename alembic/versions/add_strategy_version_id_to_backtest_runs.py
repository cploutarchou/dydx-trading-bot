"""add_strategy_version_id_to_backtest_runs

Revision ID: 9f8g7h6i5j4k
Revises: 8a1b2c3d4e5f
Create Date: 2025-10-20 20:33:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f8g7h6i5j4k"
down_revision: Union[str, None] = "8a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add strategy_version_id column to backtest_runs table."""
    with op.batch_alter_table("backtest_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "strategy_version_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_backtest_runs_strategy_version_id",
            "strategy_version_history",
            ["strategy_version_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_backtest_runs_strategy_version_id",
            ["strategy_version_id"],
        )


def downgrade() -> None:
    """Remove strategy_version_id column from backtest_runs table."""
    with op.batch_alter_table("backtest_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_backtest_runs_strategy_version_id")
        batch_op.drop_constraint(
            "fk_backtest_runs_strategy_version_id", type_="foreignkey"
        )
        batch_op.drop_column("strategy_version_id")
