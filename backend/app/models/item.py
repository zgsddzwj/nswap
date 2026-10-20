from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        Index("ix_items_feed", "community_id", "status", "last_active_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(10))  # sell|give|swap|want
    title: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), default="other")
    condition: Mapped[str | None] = mapped_column(String(20))  # brand_new|like_new|good|used|worn
    price_cents: Mapped[int | None] = mapped_column(Integer)
    negotiable: Mapped[bool] = mapped_column(default=False)  # 可小刀
    want_desc: Mapped[str | None] = mapped_column(String(200))  # 想换什么/想要什么
    bid_cents: Mapped[int | None] = mapped_column(Integer)  # 求购出价预算
    building: Mapped[str] = mapped_column(String(20), default="")

    status: Mapped[str] = mapped_column(String(12), default="on_sale", index=True)
    # on_sale|reserved|completed|archived|sunk
    sec_status: Mapped[str] = mapped_column(String(10), default="pass")  # pass|pending|fail

    view_count: Mapped[int] = mapped_column(default=0)
    want_count: Mapped[int] = mapped_column(default=0)
    last_renewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ItemImage(Base):
    __tablename__ = "item_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(default=0)
    sec_status: Mapped[str] = mapped_column(String(10), default="pending")  # pending|pass|fail
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ItemWant(Base):
    """意向：对 sell/give/swap 物品是「我想要」；对 want 物品是「我可以提供」。"""
    __tablename__ = "item_wants"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(String(300))
    bid_cents: Mapped[int | None] = mapped_column(Integer)
    swap_offer: Mapped[str | None] = mapped_column(String(200))
    # 换物意向附图（我方用于交换的物品照片，≤3 张；仅物品方可见，URL 为公网上传图）
    images: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    # pending|accepted|rejected|done
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_favorite"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ItemMessage(Base):
    """物品公开留言板"""
    __tablename__ = "item_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(String(300))
    sec_status: Mapped[str] = mapped_column(String(10), default="pass")
    status: Mapped[str] = mapped_column(String(10), default="visible")  # visible|hidden
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
