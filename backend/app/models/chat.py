from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db import Base


class Conversation(Base):
    """轻会话：意向被接受时自动创建（一个物品+一对用户唯一）"""
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("item_id", "user_a", "user_b", name="uq_conv_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    user_a: Mapped[int] = mapped_column(ForeignKey("users.id"))  # 物品方
    user_b: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 意向方
    want_id: Mapped[int | None] = mapped_column(ForeignKey("item_wants.id"))
    # 双方各自的已读水位（读到的最大 dm_messages.id）：> 水位且非本人发的 = 未读
    a_read_msg_id: Mapped[int] = mapped_column(default=0)
    b_read_msg_id: Mapped[int] = mapped_column(default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DmMessage(Base):
    __tablename__ = "dm_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ContactExchange(Base):
    """联系方式交换：会话内发起，一次交换双向解锁，绑定会话全程留痕（一会话一条）。"""

    __tablename__ = "contact_exchanges"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), unique=True, index=True
    )
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
