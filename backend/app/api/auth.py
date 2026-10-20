import re

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, get_or_create_user, resolve_openid, touch_user
from app.core.errors import bad_request, conflict, unauthorized
from app.core.security import create_auth_token
from app.core.time import utcnow
from app.models import AdminLog, SecCheck, User
from app.schemas import ContactSettings, LoginRequest, ProfileUpdate
from app.schemas.serialize import me_payload, ok
from app.services.sec_check import check_text, register_avatar_check
from app.services.wechat import client as wechat_client

router = APIRouter(tags=["auth"])

WECHAT_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
PHONE_RE = re.compile(r"^1\d{10}$")


@router.post("/auth/login")
def login(
    payload: LoginRequest | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_wx_openid: str | None = Header(default=None, alias="X-WX-OPENID"),
    x_dev_openid: str | None = Header(default=None, alias="X-DEV-OPENID"),
):
    """登录（三模式统一入口，docs/13 路线 C）：

    - 带 code（自建服务器）：wx.login 临时 code → code2session 换真实 openid → 签发 token
    - 不带 code（云托管/本地开发）：身份由请求头注入，行为与原来一致

    两种路径都返回 token（云托管模式前端可忽略）。
    """
    code = (payload.code or "").strip() if payload and payload.code else ""
    if code:
        session = wechat_client.code2session(code)
        openid = str((session or {}).get("openid") or "")
        if not openid:
            # code 一次性且 5 分钟有效：前端收到此错误应重新 wx.login 再试
            raise unauthorized("微信登录失败，请重试")
    else:
        openid = resolve_openid(authorization, x_wx_openid, x_dev_openid)
    user = get_or_create_user(db, openid)
    touch_user(user, db)
    return ok({"token": create_auth_token(openid), **me_payload(db, user)})


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
        nickname = payload.nickname.strip()
        if not nickname:
            raise bad_request("昵称不能为空")
        # 昵称展示给所有邻居（物品卡/留言/会话），属 UGC：先检后发；
        # 接口异常同样拒绝（fail-closed，与 docs/03 §2.3 文本策略一致）
        status = check_text(db, nickname, user, "text", user.id)
        if status != "pass":
            raise bad_request("当前无法校验昵称，请稍后再试")
        user.nickname = nickname
    if payload.avatar_url is not None:
        avatar = payload.avatar_url.strip()
        if avatar and avatar != user.avatar_url:
            # 头像展示给所有邻居，属 UGC 图片：登记异步检测；
            # 接口不可用时拒绝变更（fail-closed），mock 模式直接放行
            if not register_avatar_check(db, user, avatar):
                raise bad_request("头像暂时无法校验，请稍后再试")
        user.avatar_url = avatar
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
    # 3) 状态标记 + 腾出 openid（改名留痕）：同微信再次使用将自动重新建档为
    #    全新游客（注销=重置，行业惯例）；滥用由邀请码准入制兜底（docs/09 修订）
    user.openid = f"deleted:{user.id}:{user.openid}"
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
