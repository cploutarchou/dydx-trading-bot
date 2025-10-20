"""Add strategy versioning support

Revision ID: add_strategy_versioning
Revises: 75a750665dd7
Create Date: 2025-10-20 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_strategy_versioning"
down_revision: Union[str, None] = "75a750665dd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create strategy_version_history table
    op.create_table(
        "strategy_version_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("change_reason", sa.String(500), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("previous_version_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["backtest_strategies.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["previous_version_id"], ["strategy_version_history.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("idx_version_strategy"),
        "strategy_version_history",
        ["strategy_id"],
        unique=False,
    )
    op.create_index(
        op.f("idx_version_created"),
        "strategy_version_history",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("idx_version_strategy_number"),
        "strategy_version_history",
        ["strategy_id", "version_number"],
        unique=True,
    )

    # Add strategy_version_id column to backtest_runs
    op.add_column(
        "backtest_runs",
        sa.Column("strategy_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_backtest_runs_strategy_version",
        "backtest_runs",
        "strategy_version_history",
        ["strategy_version_id"],
        ["id"],
    )
    op.create_index(
        op.f("idx_backtest_runs_strategy_version"),
        "backtest_runs",
        ["strategy_version_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index for strategy_version_id
    op.drop_index(
        op.f("idx_backtest_runs_strategy_version"), table_name="backtest_runs"
    )
    # Drop foreign key
    op.drop_constraint(
        "fk_backtest_runs_strategy_version", "backtest_runs", type_="foreignkey"
    )
    # Drop strategy_version_id column
    op.drop_column("backtest_runs", "strategy_version_id")

    # Drop strategy_version_history table
    op.drop_index(
        op.f("idx_version_strategy_number"), table_name="strategy_version_history"
    )
    op.drop_index(op.f("idx_version_created"), table_name="strategy_version_history")
    op.drop_index(op.f("idx_version_strategy"), table_name="strategy_version_history")
    op.drop_table("strategy_version_history")
