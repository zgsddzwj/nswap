from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db import Base


class Transaction(Base):
    """交易单：预约、约定、双向确认。payment 字段为 V2 线上支付预留。"""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    want_id: Mapped[int | None] = mapped_column(ForeignKey("item_wants.id"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    other_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    place_method: Mapped[str | None] = mapped_column(String(10))  # face|porch|lobby
    meet_time: Mapped[datetime | None] = mapped_column(DateTime)
    place_note: Mapped[str | None] = mapped_column(String(100))

    owner_confirmed: Mapped[bool] = mapped_column(default=False)
    other_confirmed: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    # pending|arranged|completed|cancelled
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    payment: Mapped[str | None] = mapped_column(String(50))  # V2 预留

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("transaction_id", "from_user_id", name="uq_review_once"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 3满意 2一般 1不满意
    content: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Gratitude(Base):
    """感谢帖：交易完成后可发布，展示在首页横滑区"""
    __tablename__ = "gratitudes"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    to_building: Mapped[str | None] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(String(200))
    sec_status: Mapped[str] = mapped_column(String(10), default="pass")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
