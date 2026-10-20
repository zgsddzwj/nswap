"""want images

换物意向附图：item_wants.images JSON（≤3 张，仅物品方可见）。

Revision ID: b8e4d0c33f15
Revises: a3f7c9d21e04
Create Date: 2026-10-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e4d0c33f15'
down_revision: Union[str, None] = 'a3f7c9d21e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('item_wants', sa.Column('images', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('item_wants', 'images')
