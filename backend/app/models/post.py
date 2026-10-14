"""邻里墙与 FAQ（docs/10）：Phase 1 = FAQ；topic 帖为 Phase 2。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db import Base


class Post(Base):
    """帖子：type=faq（管理端发布，Phase 1）/ topic（住户发帖，Phase 2）。"""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), index=True)
    type: Mapped[str] = mapped_column(String(10), default="topic")  # topic|faq
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)  # topic=发帖住户
    published_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))  # faq 发布管理员
    title: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    images: Mapped[list | None] = mapped_column(JSON)  # Phase 2：≤3 张
    status: Mapped[str] = mapped_column(String(10), default="published")  # published|hidden
    sec_status: Mapped[str] = mapped_column(String(10), default="pass")  # pass|pending|fail
    pinned: Mapped[bool] = mapped_column(default=False)
    like_count: Mapped[int] = mapped_column(default=0)
    comment_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PostLike(Base):
    """帖子点赞（幂等唯一）。"""

    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_like"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
