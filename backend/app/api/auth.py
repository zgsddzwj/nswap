import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, touch_user
from app.core.errors import bad_request
from app.models import User
from app.schemas import ContactSettings, ProfileUpdate
from app.schemas.serialize import me_payload, ok

router = APIRouter(tags=["auth"])

WECHAT_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
PHONE_RE = re.compile(r"^1\d{10}$")


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


def _contact_dto(user: User) -> dict:
    return {
        "contact_enabled": user.contact_enabled,
        "contact_wechat": user.contact_wechat or "",
        "contact_phone": user.contact_phone or "",
    }


@router.get("/me/contact")
def get_my_contact(user: User = Depends(get_current_user)):
    """我自己的联系方式设置（仅本人可见）。"""
    return ok(_contact_dto(user))


@router.put("/me/contact")
def update_my_contact(
    payload: ContactSettings,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wechat = payload.contact_wechat.strip()
    phone = payload.contact_phone.strip()
    if wechat and not WECHAT_RE.fullmatch(wechat):
        raise bad_request("微信号格式不对（6-20 位字母、数字、下划线或减号）")
    if phone and not PHONE_RE.fullmatch(phone):
        raise bad_request("手机号格式不对")
    if payload.contact_enabled and not (wechat or phone):
        raise bad_request("开启交换前请至少填写一种联系方式")
    user.contact_wechat = wechat
    user.contact_phone = phone
    user.contact_enabled = payload.contact_enabled
    db.commit()
    return ok(_contact_dto(user))
