"""Durable "entries halted" latch.

When an emergency close fails, a position leg may be open without its hedge and
the runtime stops opening new pairs until an operator has verified the account.
That latch was a single JSON file in ``bot_states/``: shared by every runtime
in the process, invisible to operators, clearable only from a shell, and on
Kubernetes it lived in an ``emptyDir``, so replacing the pod silently removed
it. It becomes a table so that it survives restarts, is scoped to the
subaccount whose exposure is in doubt, and keeps a record of who cleared it.

Revision ID: 0007_entry_halts
Revises: 0006_reconcile_enum_labels
Create Date: 2026-09-22 00:00:00.000000

Change summary:
  - New table ``entry_halts``. A row with ``cleared_at IS NULL`` is an active
    halt for ``(network, address, subaccount_number)``.
  - Partial unique index so a subaccount has at most one active halt (the first
    reason is the one that is kept, as with the file).

Forward safety checks:
  - Additive only: one new table and its indexes; no existing table is touched.
  - Guarded by ``has_table`` so it is a no-op where the table already exists.

Lock/performance risk: NONE — creating an empty table takes no lock on any
existing relation. The table holds a handful of rows.

Downgrade plan:
  - Drops the table. Active halts are lost with it, so check for rows with
    ``cleared_at IS NULL`` before downgrading a database that serves live
    runtimes.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_entry_halts"
down_revision: Union[str, Sequence[str], None] = "0006_reconcile_enum_labels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("entry_halts"):
        return

    op.create_table(
        "entry_halts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.String(64), nullable=False),
        sa.Column("network", sa.String(16), nullable=False),
        sa.Column("address", sa.String(128), nullable=False),
        sa.Column(
            "subaccount_number", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("halted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_by", sa.String(128), nullable=True),
        sa.Column("clear_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_entry_halts_instance_id", "entry_halts", ["instance_id"])
    op.create_index(
        "uq_entry_halts_active_scope",
        "entry_halts",
        ["network", "address", "subaccount_number"],
        unique=True,
        postgresql_where=sa.text("cleared_at IS NULL"),
        sqlite_where=sa.text("cleared_at IS NULL"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("entry_halts"):
        return
    op.drop_index("uq_entry_halts_active_scope", table_name="entry_halts")
    op.drop_index("ix_entry_halts_instance_id", table_name="entry_halts")
    op.drop_table("entry_halts")
