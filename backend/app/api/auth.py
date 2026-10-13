from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, touch_user
from app.models import User
from app.schemas import ProfileUpdate
from app.schemas.serialize import me_payload, ok

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """静默登录：openid 已由依赖自动建档，这里刷新活跃时间并返回档案。"""
    touch_user(user, db)
    return ok(me_payload(db, user))


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(me_payload(db, user))


@router.put("/me")
def update_me(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.nickname is not None:
        user.nickname = payload.nickname
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    if payload.unit is not None:
        user.unit = payload.unit
    db.commit()
    return ok(me_payload(db, user))
