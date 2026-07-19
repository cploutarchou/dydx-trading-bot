"""Add artifact reference registry for durable artifact ownership metadata.

Revision ID: 0002_artifact_refs
Revises: 0001_pg_initial
Create Date: 2026-06-27 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_artifact_refs"
down_revision: Union[str, Sequence[str], None] = "0001_pg_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonb() -> sa.types.TypeDecorator:
    return postgresql.JSONB(none_as_null=True)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("artifact_references"):
        op.create_table(
            "artifact_references",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("owner_type", sa.String(length=64), nullable=False),
            sa.Column("owner_id", sa.String(length=128), nullable=False),
            sa.Column("bucket", sa.String(length=128), nullable=False),
            sa.Column("object_key", sa.String(length=512), nullable=False),
            sa.Column("content_type", sa.String(length=255), nullable=False),
            sa.Column(
                "size_bytes", sa.BigInteger(), nullable=False, server_default="0"
            ),
            sa.Column("checksum", sa.String(length=128), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", _jsonb(), nullable=True),
            sa.UniqueConstraint(
                "bucket",
                "object_key",
                name="uq_artifact_references_bucket_object",
            ),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("artifact_references")}
    if "ix_artifact_references_owner_type" not in indexes:
        op.create_index(
            "ix_artifact_references_owner_type",
            "artifact_references",
            ["owner_type"],
            unique=False,
        )
    if "ix_artifact_references_owner_id" not in indexes:
        op.create_index(
            "ix_artifact_references_owner_id",
            "artifact_references",
            ["owner_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("artifact_references"):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("artifact_references")}
    if "ix_artifact_references_owner_id" in indexes:
        op.drop_index(
            "ix_artifact_references_owner_id", table_name="artifact_references"
        )
    if "ix_artifact_references_owner_type" in indexes:
        op.drop_index(
            "ix_artifact_references_owner_type", table_name="artifact_references"
        )
    op.drop_table("artifact_references")
