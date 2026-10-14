"""production hardening

docs/09：协议同意与注销字段、公告置顶、性能复合索引。

Revision ID: d9a4c1f83b72
Revises: c5f8d3e27a91
Create Date: 2026-10-13 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9a4c1f83b72'
down_revision: Union[str, None] = 'c5f8d3e27a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- P0-4 合规：协议同意 + 注销软删除 ----
    op.add_column('users', sa.Column('agreed_terms_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column(
        'agreed_terms_version', sa.String(length=10), nullable=False, server_default=''))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    # ---- P1-10 公告置顶 ----
    op.add_column('announcements', sa.Column(
        'pinned', sa.Boolean(), nullable=False, server_default=sa.false()))

    # ---- P1-8 性能复合索引（热查询路径）----
    # feed：WHERE community_id=? AND status IN (...) ORDER BY last_active_at DESC
    op.create_index(
        'ix_items_feed', 'items', ['community_id', 'status', 'last_active_at'])
    # 我的发布：WHERE user_id=? AND status=?
    op.create_index('ix_items_user_status', 'items', ['user_id', 'status'])
    # 未读通知：WHERE user_id=? AND read=false ORDER BY id
    op.create_index('ix_notifications_unread', 'notifications', ['user_id', 'read', 'id'])
    # 聊天轮询：WHERE conversation_id=? AND id>?
    op.create_index('ix_dm_messages_conv', 'dm_messages', ['conversation_id', 'id'])
    # 留言板：WHERE item_id=? AND status=?
    op.create_index('ix_item_messages_board', 'item_messages', ['item_id', 'status', 'id'])
    # 审计日志：WHERE admin_id=? ORDER BY id
    op.create_index('ix_admin_logs_admin', 'admin_logs', ['admin_id', 'id'])


def downgrade() -> None:
    op.drop_index('ix_admin_logs_admin', table_name='admin_logs')
    op.drop_index('ix_item_messages_board', table_name='item_messages')
    op.drop_index('ix_dm_messages_conv', table_name='dm_messages')
    op.drop_index('ix_notifications_unread', table_name='notifications')
    op.drop_index('ix_items_user_status', table_name='items')
    op.drop_index('ix_items_feed', table_name='items')
    op.drop_column('announcements', 'pinned')
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'agreed_terms_version')
    op.drop_column('users', 'agreed_terms_at')
