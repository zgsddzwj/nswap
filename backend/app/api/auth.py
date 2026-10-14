import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, touch_user
from app.core.errors import bad_request, conflict
from app.core.time import utcnow
from app.models import AdminLog, User
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


@router.post("/me/agree")
def agree_terms(
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """记录协议同意（版本+时间，docs/09 P0-4）。"""
    version = str(payload.get("version") or "").strip()
    if version != settings.terms_version:
        raise bad_request("协议版本已更新，请刷新后重新阅读")
    user.agreed_terms_at = utcnow()
    user.agreed_terms_version = version
    db.commit()
    return ok({"ok": True, "agreed_terms_version": version})


@router.post("/me/delete")
def delete_account(
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """账号注销（docs/09 P0-4）：匿名化 + 下架，保留交易记录（对方权益）。

    需二次确认：请求体 {"confirm": "注销"}。
    """
    if str(payload.get("confirm") or "") != "注销":
        raise bad_request("请二次确认后提交注销")
    if user.status == "deleted" or user.deleted_at is not None:
        raise conflict("账号已注销")
    # 1) 匿名化
    user.nickname = f"已注销用户{user.id}"
    user.avatar_url = ""
    user.contact_wechat = ""
    user.contact_phone = ""
    user.contact_enabled = False
    # 2) 下架在架物品；拒绝待处理意向
    from app.models import Item, ItemWant

    db.query(Item).filter(
        Item.user_id == user.id, Item.status.in_(["on_sale", "sunk", "reserved"])
    ).update({"status": "archived"}, synchronize_session=False)
    db.query(ItemWant).filter(
        ItemWant.user_id == user.id, ItemWant.status == "pending"
    ).update({"status": "rejected"}, synchronize_session=False)
    # 3) 状态标记（openid 保留：防止重新注册复用；登录时被 403 拦截）
    user.status = "deleted"
    user.deleted_at = utcnow()
    db.add(
        AdminLog(
            admin_id=1,  # 系统操作（超管占位）；业务审计以 action 为准
            action="user_self_delete",
            target_type="user",
            target_id=user.id,
        )
    )
    db.commit()
    return ok({"ok": True})
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
