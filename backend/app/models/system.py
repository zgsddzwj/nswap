from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"), index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(10))  # item|message|user
    target_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    # pending|resolved|dismissed
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    handle_note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)


class SecCheck(Base):
    __tablename__ = "sec_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(10))  # text|image
    target_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="processing")  # processing|ok|risk|error
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(String(200), default="")
    payload: Mapped[dict | None] = mapped_column(JSON)
    read: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MsgSubscription(Base):
    """一次性订阅消息授权配额（wx.requestSubscribeMessage accept 后记录）"""
    __tablename__ = "msg_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    template_key: Mapped[str] = mapped_column(String(20))  # want|accepted|confirm|review
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(30), default="")
    # NULL=平台超管（全局）；非 NULL=物业管理员（仅管本小区）
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class Announcement(Base):
    """物业公告：仅本小区住户可见（小程序只读，管理后台发布/删除）"""

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    published_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    pinned: Mapped[bool] = mapped_column(default=False)  # 置顶（docs/09 P1-10）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str | None] = mapped_column(String(20))
    target_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
