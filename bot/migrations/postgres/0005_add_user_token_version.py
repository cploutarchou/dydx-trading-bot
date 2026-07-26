"""Add token_version column to users for JWT revocation (logout-all).

Adds a security-stamp integer to the users table. The value is embedded as
``stv`` in every issued JWT and compared against the user's current value on
each authenticated request. ``logout-all`` bumps the value, invalidating all
previously issued tokens for that user.

Revision ID: 0005_user_token_version
Revises: 0004_runtime_state_tables
Create Date: 2026-07-26 00:00:00.000000

Change summary:
  - users.token_version : INTEGER NOT NULL DEFAULT 0

Forward safety checks:
  - Nullable-with-default integer add (server_default '0'); existing rows
    backfill to 0 automatically. Legacy JWTs without an ``stv`` claim are
    treated as 0 by the auth middleware, so they keep working.

Lock/performance risk: LOW — adding a nullable integer column with a server
default does not rewrite the table on PostgreSQL.

Downgrade plan: Drop the column. It holds only revocation metadata; loss only
means already-revoked sessions could no longer be tracked, which is acceptable
on rollback.

Verification:
  - ``alembic upgrade head`` adds the column when absent.
  - ``alembic downgrade -1`` then ``upgrade head`` is idempotent.
  - App boots and login/logout/logout-all work after upgrade.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_user_token_version"
down_revision: Union[str, Sequence[str], None] = "0004_runtime_state_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("users")}

    if "token_version" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "token_version",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("users")}

    if "token_version" in existing_columns:
        op.drop_column("users", "token_version")
