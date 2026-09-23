"""Durable equity peak for the bot-level max drawdown limit.

A strategy's ``max_drawdown_pct`` halts new entries once the equity of the
subaccount its runtime trades on has fallen that far below its peak. The peak
has to outlive the process: kept in memory or in the pod's ``emptyDir``, a
restart or a replaced pod would measure from a lower level and give a bot that
is close to its limit its full allowance again.

Revision ID: 0008_drawdown_peaks
Revises: 0007_entry_halts
Create Date: 2026-09-23 00:00:00.000000

Change summary:
  - New table ``drawdown_peaks``: one row per runtime and subaccount
    ``(instance_id, network, address, subaccount_number)`` with the highest
    equity seen since the measurement began (``baseline_at``), when it was
    seen (``peak_at``) and when the guard halted entries (``tripped_at``).
  - Clearing a drawdown halt deletes the subaccount's rows, so the runtime
    measures again from the equity it sees next.

Forward safety checks:
  - Additive only: one new table and its indexes; no existing table is touched.
  - Guarded by ``has_table`` so it is a no-op where the table already exists.
  - Runtimes read the table only while their ``max_drawdown_pct`` is above 0.

Lock/performance risk: NONE. Creating an empty table takes no lock on any
existing relation. The table holds one row per runtime and subaccount.

Downgrade plan:
  - Drops the table. Runtimes with a drawdown limit then cannot read their peak
    and open no new pairs (fail closed) until the table is back. Stop them or
    set ``max_drawdown_pct`` to 0 first. The stored peaks are lost: after an
    upgrade again, each runtime measures from the equity it sees next.

Verification checklist:
  - ``alembic upgrade head`` from 0007 creates the table and both indexes.
  - ``alembic downgrade -1`` drops them cleanly.
  - A runtime with ``max_drawdown_pct`` > 0 writes one row on its first cycle.

Rollout and rollback notes:
  - Risk: Low. Run the bot migration Job before the new api image serves live
    runtimes, as with 0007.
  - Rollback: downgrade to ``0007_entry_halts`` after rolling the api image
    back; no data outside this table is affected.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_drawdown_peaks"
down_revision: Union[str, Sequence[str], None] = "0007_entry_halts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("drawdown_peaks"):
        return

    op.create_table(
        "drawdown_peaks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.String(64), nullable=False),
        sa.Column("network", sa.String(16), nullable=False),
        sa.Column("address", sa.String(128), nullable=False),
        sa.Column(
            "subaccount_number", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("peak_equity", sa.Float(), nullable=False),
        sa.Column("peak_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tripped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_drawdown_peaks_scope",
        "drawdown_peaks",
        ["instance_id", "network", "address", "subaccount_number"],
        unique=True,
    )
    op.create_index(
        "ix_drawdown_peaks_subaccount",
        "drawdown_peaks",
        ["network", "address", "subaccount_number"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("drawdown_peaks"):
        return
    op.drop_index("ix_drawdown_peaks_subaccount", table_name="drawdown_peaks")
    op.drop_index("uq_drawdown_peaks_scope", table_name="drawdown_peaks")
    op.drop_table("drawdown_peaks")
