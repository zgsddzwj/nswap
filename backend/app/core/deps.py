import hashlib
import secrets
from datetime import timedelta

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import forbidden, unauthorized
from app.core.time import utcnow
from app.db import SessionLocal
from app.models import Item, User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_openid(x_wx_openid: str | None, x_dev_openid: str | None) -> str | None:
    if x_wx_openid:
        return x_wx_openid
    if settings.env == "dev" and x_dev_openid:
        return x_dev_openid
    if settings.env == "dev":
        return "dev-default-openid"
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    x_wx_openid: str | None = Header(default=None, alias="X-WX-OPENID"),
    x_dev_openid: str | None = Header(default=None, alias="X-DEV-OPENID"),
) -> User:
    openid = _extract_openid(x_wx_openid, x_dev_openid)
    if not openid:
        raise unauthorized()
    user = db.query(User).filter(User.openid == openid).first()
    if user is not None and (user.status == "deleted" or user.deleted_at is not None):
        raise forbidden("账号已注销")
    if user is None:
        # 静默登录：首次访问自动建档为游客（未验证）
        user = User(openid=openid, nickname=f"邻居{secrets.token_hex(2)}")
        db.add(user)
        db.commit()
        db.refresh(user)
    request.state.user_id = user.id
    return user


def get_verified_user(user: User = Depends(get_current_user)) -> User:
    if user.status == "banned":
        raise forbidden("账号已被封禁，如有疑问请联系管理员")
    if user.verified_at is None:
        raise forbidden("请先完成小区验证")
    return user


def get_active_user(user: User = Depends(get_current_user)) -> User:
    if user.status == "banned":
        raise forbidden("账号已被封禁，如有疑问请联系管理员")
    if user.status == "deleted" or user.deleted_at is not None:
        raise forbidden("账号已注销")
    return user


def touch_user(user: User, db: Session) -> None:
    user.last_active_at = utcnow()
    db.commit()


# ---------- 频控工具 ----------

def count_today_items(db: Session, user: User) -> int:
    start = utcnow() - timedelta(days=1)
    return (
        db.query(Item)
        .filter(Item.user_id == user.id, Item.created_at >= start)
        .count()
    )


def count_active_items(db: Session, user: User) -> int:
    return (
        db.query(Item)
        .filter(Item.user_id == user.id, Item.status.in_(["on_sale", "reserved"]))
        .count()
    )


# ---------- 邀请码 ----------

def gen_invite_code(prefix: str) -> str:
    raw = secrets.token_hex(4).upper()  # 8 位
    return f"{prefix}-{raw}"


def checksum_tag(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:6]
