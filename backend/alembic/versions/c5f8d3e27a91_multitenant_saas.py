"""multitenant saas

多社区 SaaS：communities 加城市/状态维度、admin_users 加租户归属、新增物业公告表。
详设见 docs/07-多社区SaaS详设.md。

Revision ID: c5f8d3e27a91
Revises: b7d2e4a91c58
Create Date: 2026-10-13 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5f8d3e27a91'
down_revision: Union[str, None] = 'b7d2e4a91c58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('communities', sa.Column(
        'city', sa.String(length=50), nullable=False, server_default='',
        comment='同城维度（管理端创建必填，空值不出现在同城）'))
    op.add_column('communities', sa.Column(
        'district', sa.String(length=50), nullable=False, server_default=''))
    op.add_column('communities', sa.Column(
        'status', sa.String(length=10), nullable=False, server_default='active',
        comment='active|suspended'))
    op.create_index('ix_communities_city', 'communities', ['city'])

    op.add_column('admin_users', sa.Column(
        'community_id', sa.Integer(), nullable=True,
        comment='NULL=平台超管；非 NULL=物业管理员（仅本小区）'))
    op.create_foreign_key(
        'fk_admin_users_community_id', 'admin_users', 'communities',
        ['community_id'], ['id'])
    op.create_index('ix_admin_users_community_id', 'admin_users', ['community_id'])

    op.create_table(
        'announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('community_id', sa.Integer(), nullable=False,
                  comment='仅本小区住户可见'),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('published_by', sa.Integer(), nullable=True,
                  comment='发布管理员（留痕）'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id']),
        sa.ForeignKeyConstraint(['published_by'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_announcements_community_id', 'announcements', ['community_id'])


def downgrade() -> None:
    op.drop_index('ix_announcements_community_id', table_name='announcements')
    op.drop_table('announcements')
    op.drop_index('ix_admin_users_community_id', table_name='admin_users')
    op.drop_constraint('fk_admin_users_community_id', 'admin_users', type_='foreignkey')
    op.drop_column('admin_users', 'community_id')
    op.drop_index('ix_communities_city', table_name='communities')
    op.drop_column('communities', 'status')
    op.drop_column('communities', 'district')
    op.drop_column('communities', 'city')
