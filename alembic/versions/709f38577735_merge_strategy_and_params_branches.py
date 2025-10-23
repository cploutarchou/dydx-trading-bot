"""merge_strategy_and_params_branches

Revision ID: 709f38577735
Revises: a514cfd6926f, add_initial_amount
Create Date: 2025-10-23 21:48:33.032847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '709f38577735'
down_revision: Union[str, None] = ('a514cfd6926f', 'add_initial_amount')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
