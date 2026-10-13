from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"), index=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(30), default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    building: Mapped[str] = mapped_column(String(20), default="")
    unit: Mapped[str] = mapped_column(String(20), default="")
    role: Mapped[str] = mapped_column(String(10), default="member")  # member|elder|admin
    status: Mapped[str] = mapped_column(String(10), default="active")  # active|banned
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)

    # 联系方式：用户主动填写，默认不开放。仅在轻会话内通过「交换」对交易对方可见，
    # 永不出现在任何列表/详情序列化中（见 schemas/serialize.py）。
    contact_wechat: Mapped[str] = mapped_column(String(64), default="")
    contact_phone: Mapped[str] = mapped_column(String(20), default="")
    contact_enabled: Mapped[bool] = mapped_column(default=False)

    # 信用统计缓存（credit.py 维护，只展示客观数据）
    sell_done: Mapped[int] = mapped_column(default=0)
    give_done: Mapped[int] = mapped_column(default=0)
    swap_done: Mapped[int] = mapped_column(default=0)
    review_good: Mapped[int] = mapped_column(default=0)
    review_mid: Mapped[int] = mapped_column(default=0)
    review_bad: Mapped[int] = mapped_column(default=0)
    thanks_count: Mapped[int] = mapped_column(default=0)
    violations: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def verified(self) -> bool:
        return self.verified_at is not None

    @property
    def trades_done(self) -> int:
        return self.sell_done + self.give_done + self.swap_done
