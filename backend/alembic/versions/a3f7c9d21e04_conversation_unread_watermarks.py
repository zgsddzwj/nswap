"""conversation unread watermarks

会话未读红点（docs/12 P1-7）：双方各自的已读水位。

Revision ID: a3f7c9d21e04
Revises: e1b8d2f74c63
Create Date: 2026-10-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f7c9d21e04'
down_revision: Union[str, None] = 'e1b8d2f74c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversations',
        sa.Column('a_read_msg_id', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'conversations',
        sa.Column('b_read_msg_id', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('conversations', 'b_read_msg_id')
    op.drop_column('conversations', 'a_read_msg_id')
