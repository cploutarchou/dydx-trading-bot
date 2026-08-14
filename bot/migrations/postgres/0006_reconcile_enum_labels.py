"""Reconcile status-enum labels with what the ORM actually binds.

SQLAlchemy's ``Enum(PyEnum)`` binds the enum **names** (uppercase: 'OPEN',
'PENDING', 'RUNNING', ...), but the consolidated initial schema
(``0001_pg_initial``) created the PostgreSQL enum types with the Python enum
**values** (lowercase: 'open', 'pending', ...). Databases historically created
via ``create_all_tables`` therefore carry uppercase labels and work, while any
database built purely by migrations (fresh deployments, the multi-worker test
harness's ephemeral DB) rejects every ORM-bound label — breaking websocket
initial-state position queries, ``async_job_manager`` job persistence, and bot
lifecycle status writes. The legacy revision ``c9f4a7b2d1e3`` (not in the
consolidated chain) already assumed name-style labels when it added 'PENDING',
confirming names are canonical.

Revision ID: 0006_reconcile_enum_labels
Revises: 0005_user_token_version
Create Date: 2026-08-15 00:00:00.000000

Change summary:
  - For each drifted enum type (botstatusenum, jobstatusenum, tradestatusenum,
    positionstatusenum, alertseverityenum): ``ALTER TYPE ... ADD VALUE IF NOT
    EXISTS`` the uppercase NAME labels, then UPDATE every column using the type
    from the lowercase value label to the uppercase NAME label.
  - Columns are discovered dynamically from ``information_schema`` by
    ``udt_name`` so the migration stays correct even if a table was missed here.
  - PostgreSQL cannot DROP enum values, so the lowercase labels remain in the
    types forever (harmless — the application only binds names).

Forward safety checks:
  - Expand-only schema change (``ADD VALUE IF NOT EXISTS``); no table rewrite,
    no type replacement, no locks beyond brief catalog updates.
  - Fully idempotent: re-running no-ops (labels exist; no lowercase rows left).
  - Legacy (create_all-built) databases already have the NAME labels and no
    lowercase rows — every statement is a no-op there.

Lock/performance risk: LOW — enum ADD VALUE is a catalog-only change; the
row UPDATEs touch only rows still holding lowercase labels (at most the table's
row count, and these are control/status tables, not time-series). No batching
required at realistic sizes; the UPDATEs are single-statement and idempotent.

Downgrade plan:
  - Reverse the row UPDATEs (NAME → value) and re-add the lowercase labels via
    ``ADD VALUE IF NOT EXISTS`` (needed only on create_all-built databases that
    never had them). Not perfectly lossless in one respect: neither direction
    can remove the added labels (PostgreSQL limitation) — enum types
    permanently carry both casings after a round trip.

Verification:
  - ``alembic upgrade head`` on a fresh (migrations-only) database: every type
    contains both casings; ``SELECT ... WHERE status = 'OPEN'`` and ORM writes
    with ``JobStatusEnum.PENDING`` / ``BotStatusEnum.RUNNING`` succeed.
  - ``alembic downgrade -1`` then ``upgrade head`` round-trips cleanly.
  - On a legacy (create_all-built) database, every statement is a no-op.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_reconcile_enum_labels"
down_revision: Union[str, Sequence[str], None] = "0005_user_token_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# value label (migrations) → NAME label (what the ORM binds)
_LABEL_MAPS: dict[str, dict[str, str]] = {
    "botstatusenum": {
        "created": "CREATED",
        "starting": "STARTING",
        "running": "RUNNING",
        "stopping": "STOPPING",
        "stopped": "STOPPED",
        "error": "ERROR",
        "recovering": "RECOVERING",
        "degraded": "DEGRADED",
        "safeguarded": "SAFEGUARDED",
    },
    "jobstatusenum": {
        "pending": "PENDING",
        "running": "RUNNING",
        "completed": "COMPLETED",
        "failed": "FAILED",
        "cancelled": "CANCELLED",
    },
    "tradestatusenum": {
        "open": "OPEN",
        "closed": "CLOSED",
        "cancelled": "CANCELLED",
    },
    "positionstatusenum": {
        "open": "OPEN",
        "closed": "CLOSED",
        "liquidated": "LIQUIDATED",
    },
    "alertseverityenum": {
        "info": "INFO",
        "warning": "WARNING",
        "critical": "CRITICAL",
    },
}


def _columns_using_type(type_name: str) -> list[tuple[str, str]]:
    """Return (table, column) pairs whose type is ``type_name`` (public schema)."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND udt_name = :type_name"
        ),
        {"type_name": type_name},
    )
    return [(row[0], row[1]) for row in result]


def _apply(direction: str) -> None:
    """direction 'forward' → value→NAME; 'back' → NAME→value."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # enum types only exist on the PostgreSQL path

    for type_name, labels in _LABEL_MAPS.items():
        mapping = (
            labels if direction == "forward" else {v: k for k, v in labels.items()}
        )
        # Expand the type first, outside the migration transaction: PostgreSQL
        # forbids ADD VALUE inside a transaction block that later uses the type.
        with op.get_context().autocommit_block():
            for label in set(mapping.values()):
                op.execute(
                    sa.text(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{label}'")
                )
        # Then flip any rows still carrying the old casing.
        for table, column in _columns_using_type(type_name):
            for old, new in mapping.items():
                op.execute(
                    sa.text(
                        f'UPDATE "{table}" SET "{column}" = :new '
                        f'WHERE "{column}" = :old'
                    ).bindparams(old=old, new=new)
                )


def upgrade() -> None:
    _apply("forward")


def downgrade() -> None:
    _apply("back")
