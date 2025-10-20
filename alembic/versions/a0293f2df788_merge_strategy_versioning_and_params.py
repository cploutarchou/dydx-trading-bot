"""merge strategy versioning and params

Revision ID: a0293f2df788
Revises: add_strategy_versioning, add_strategy_params
Create Date: 2025-10-20 19:31:24.470350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0293f2df788'
down_revision: Union[str, None] = ('add_strategy_versioning', 'add_strategy_params')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
