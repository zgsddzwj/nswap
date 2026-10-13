from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db import Base


class Community(Base):
    __tablename__ = "communities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Invite(Base):
    """邀请码：normal=管理后台按楼栋批量生成；vouch=老住户担保码（同时仅 1 个未用）"""
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(10), default="normal")  # normal | vouch
    building: Mapped[str] = mapped_column(String(20), default="")
    batch_note: Mapped[str] = mapped_column(String(100), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10), default="active")  # active|used|revoked
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Vouch(Base):
    """担保关系：vouch 码被使用时落一条记录"""
    __tablename__ = "vouches"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    voucher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vouchee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invite_id: Mapped[int] = mapped_column(ForeignKey("invites.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VerifyRequest(Base):
    """人工验证申请：业主凭证图片由超管在后台审核"""
    __tablename__ = "verify_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"))
    building: Mapped[str] = mapped_column(String(20))
    unit: Mapped[str] = mapped_column(String(20), default="")
    proof_image: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending|approved|rejected
    note: Mapped[str] = mapped_column(String(200), default="")
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
