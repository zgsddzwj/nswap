"""add contact exchange

用户联系方式字段（默认不开放）+ 会话内联系方式交换记录表。

Revision ID: b7d2e4a91c58
Revises: f91b070d8b1d
Create Date: 2026-10-13 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d2e4a91c58'
down_revision: Union[str, None] = 'f91b070d8b1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('contact_wechat', sa.String(length=64), nullable=False,
                  server_default='', comment='微信号（用户主动填写，默认不开放）'),
    )
    op.add_column(
        'users',
        sa.Column('contact_phone', sa.String(length=20), nullable=False,
                  server_default='', comment='手机号（用户主动填写，默认不开放）'),
    )
    op.add_column(
        'users',
        sa.Column('contact_enabled', sa.Boolean(), nullable=False,
                  server_default=sa.false(), comment='是否允许通过会话交换查看'),
    )
    op.create_table(
        'contact_exchanges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False,
                  comment='绑定会话：仅交易双方可见，一会话一条（幂等）'),
        sa.Column('initiator_id', sa.Integer(), nullable=False,
                  comment='发起方（消耗当日额度）'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.ForeignKeyConstraint(['initiator_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id'),
    )
    op.create_index(
        'ix_contact_exchanges_conversation_id', 'contact_exchanges', ['conversation_id']
    )
    op.create_index(
        'ix_contact_exchanges_initiator_id', 'contact_exchanges', ['initiator_id']
    )


def downgrade() -> None:
    op.drop_index('ix_contact_exchanges_initiator_id', table_name='contact_exchanges')
    op.drop_index('ix_contact_exchanges_conversation_id', table_name='contact_exchanges')
    op.drop_table('contact_exchanges')
    op.drop_column('users', 'contact_enabled')
    op.drop_column('users', 'contact_phone')
    op.drop_column('users', 'contact_wechat')
