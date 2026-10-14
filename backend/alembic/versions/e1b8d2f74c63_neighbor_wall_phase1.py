"""neighbor wall phase 1

FAQ 墙（docs/10 Phase 1）：posts（type=faq）与 post_likes 点赞表。
type 字段预留 topic（邻里墙 Phase 2，NEIGHBOR_WALL_ENABLED 控制）。

Revision ID: e1b8d2f74c63
Revises: d9a4c1f83b72
Create Date: 2026-10-14 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1b8d2f74c63'
down_revision: Union[str, None] = 'd9a4c1f83b72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('community_id', sa.Integer(), nullable=False,
                  comment='所属小区（FAQ/帖子按小区隔离）'),
        sa.Column('type', sa.String(length=10), nullable=False, server_default='topic',
                  comment='topic|faq；faq 仅管理端发布'),
        sa.Column('user_id', sa.Integer(), nullable=True,
                  comment='发帖住户（topic）；faq 为 NULL'),
        sa.Column('published_by', sa.Integer(), nullable=True,
                  comment='faq 发布管理员（留痕）'),
        sa.Column('title', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('images', sa.JSON(), nullable=True,
                  comment='图片 URL 列表（Phase 2，≤3）'),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='published',
                  comment='published|hidden'),
        sa.Column('sec_status', sa.String(length=10), nullable=False, server_default='pass',
                  comment='pass|pending|fail；faq 免审默认 pass'),
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('like_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('comment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_active_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['published_by'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_posts_community_id', 'posts', ['community_id'])
    op.create_index('ix_posts_user_id', 'posts', ['user_id'])

    op.create_table(
        'post_likes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'user_id', name='uq_post_like'),
    )
    op.create_index('ix_post_likes_post_id', 'post_likes', ['post_id'])
    op.create_index('ix_post_likes_user_id', 'post_likes', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_post_likes_user_id', table_name='post_likes')
    op.drop_index('ix_post_likes_post_id', table_name='post_likes')
    op.drop_table('post_likes')
    op.drop_index('ix_posts_user_id', table_name='posts')
    op.drop_index('ix_posts_community_id', table_name='posts')
    op.drop_table('posts')
