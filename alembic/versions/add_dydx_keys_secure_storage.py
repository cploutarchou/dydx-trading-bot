"""Add DYDXKey table for secure key storage

Revision ID: add_dydx_keys_table
Revises: a0293f2df788
Create Date: 2025-10-20

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_dydx_keys_table"
down_revision = "a0293f2df788"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM type for network
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE network_enum AS ENUM ('testnet', 'mainnet');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create DYDXKey table
    op.create_table(
        "dydx_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("network", sa.String(50), nullable=False),  # testnet or mainnet
        sa.Column("chain_address", sa.String(255), nullable=False),
        sa.Column(
            "encrypted_secret", sa.Text(), nullable=False
        ),  # Encrypted with Fernet
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "network", name="uq_user_network_keys"),
    )
    op.create_index(
        op.f("ix_dydx_keys_user_id"), "dydx_keys", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_dydx_keys_network"), "dydx_keys", ["network"], unique=False
    )


def downgrade() -> None:
    op.drop_table("dydx_keys")
    op.execute("DROP TYPE IF EXISTS network_enum;")
