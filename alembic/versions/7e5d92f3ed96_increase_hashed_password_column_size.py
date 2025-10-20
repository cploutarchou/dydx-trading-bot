"""increase_hashed_password_column_size

Revision ID: 7e5d92f3ed96
Revises: c4fd4922843f
Create Date: 2025-10-20 20:16:50.817707

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e5d92f3ed96"
down_revision: Union[str, None] = "c4fd4922843f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite-compatible migration: use batch_alter_table for column type change
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "hashed_password",
            existing_type=sa.VARCHAR(length=255),
            type_=sa.String(length=500),
            existing_nullable=False,
        )


def downgrade() -> None:
    # SQLite-compatible migration: use batch_alter_table for column type change
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "hashed_password",
            existing_type=sa.String(length=500),
            type_=sa.VARCHAR(length=255),
            existing_nullable=False,
        )
