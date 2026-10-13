"""Web 管理后台：session 鉴权 + Jinja2 SSR。

多租户分权（docs/07 §5）：AdminUser.community_id 为 NULL 即平台超管（全局）；
非 NULL 即物业管理员（仅本小区，所有查询/写操作服务端强制隔离，越权 403）。
"""

import logging
import secrets
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.deps import gen_invite_code, get_db
from app.core.security import hash_password, verify_password
from app.core.time import utcnow
from app.models import (
    AdminLog,
    AdminUser,
    Announcement,
    Community,
    Invite,
    Item,
    ItemMessage,
    Report,
    SecCheck,
    User,
    VerifyRequest,
)

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/admin/templates")
templates.env.filters["zip"] = zip  # 原始模板 reports.html 使用 | zip（Jinja2 3.x 无此内置过滤器）
router = APIRouter(prefix="/admin", tags=["admin"])


# ---------- 会话与权限 ----------

def _auth_or_redirect(request: Request, db: Session) -> AdminUser | None:
    admin_id = request.session.get("admin_id")
    if not admin_id:
        return None
    return db.get(AdminUser, admin_id)


def _is_super(admin: AdminUser) -> bool:
    return admin.community_id is None


def _forbidden(msg: str = "没有权限执行此操作") -> HTMLResponse:
    return HTMLResponse(
        f'<div style="font-family:sans-serif;padding:40px"><h3>403</h3><p>{msg}</p>'
        '<a href="/admin">返回后台</a></div>',
        status_code=403,
    )


def _own_community(db: Session, admin: AdminUser) -> Community | None:
    return db.get(Community, admin.community_id) if admin.community_id else None


def log_action(db: Session, admin: AdminUser, action: str, target_type=None, target_id=None, detail=None):
    db.add(
        AdminLog(
            admin_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )


def _redirect(url: str, msg: str | None = None) -> RedirectResponse:
    if msg:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}msg={quote(msg)}"
    return RedirectResponse(url, status_code=303)


# ---------- 登录 ----------

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, msg: str | None = None):
    return templates.TemplateResponse(request, "login.html", {"msg": msg})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = db.query(AdminUser).filter(AdminUser.username == username.strip()).first()
    if admin is None or not verify_password(password, admin.password_hash):
        return templates.TemplateResponse(
            request, "login.html", {"msg": "用户名或密码错误"}, status_code=401
        )
    admin.last_login_at = utcnow()
    request.session["admin_id"] = admin.id
    db.commit()
    return _redirect("/admin")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return _redirect("/admin/login")


# ---------- 自助改密码 ----------

@router.get("/password", response_class=HTMLResponse)
def password_page(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    return templates.TemplateResponse(
        request, "password.html", {"request": request, "admin": admin, "msg": request.query_params.get("msg")}
    )


@router.post("/password")
def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    if not verify_password(old_password, admin.password_hash):
        return _redirect("/admin/password", "旧密码不正确")
    if len(new_password) < 8:
        return _redirect("/admin/password", "新密码至少 8 位")
    admin.password_hash = hash_password(new_password)
    log_action(db, admin, "change_password")
    db.commit()
    return _redirect("/admin/password", "密码已修改")


# ---------- 看板 ----------

@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    cid = admin.community_id  # None=超管全局

    def _users():
        q = db.query(User)
        return q.filter(User.community_id == cid) if cid else q

    def _items():
        q = db.query(Item)
        return q.filter(Item.community_id == cid) if cid else q

    stats = {
        "users": _users().count(),
        "verified": _users().filter(User.verified_at.is_not(None)).count(),
        "items": _items().filter(Item.status.in_(["on_sale", "reserved"])).count(),
        "trades_done": _items().filter(Item.status == "completed").count(),
        "pending_reports": db.query(Report).filter(
            Report.status == "pending",
            *( [Report.community_id == cid] if cid else [] ),
        ).count(),
        "pending_verify": db.query(VerifyRequest).filter(
            VerifyRequest.status == "pending",
            *( [VerifyRequest.community_id == cid] if cid else [] ),
        ).count(),
        "active_invites": db.query(Invite).filter(
            Invite.status == "active",
            *( [Invite.community_id == cid] if cid else [] ),
        ).count(),
    }
    recent_items = _items().order_by(Item.id.desc()).limit(8).all()
    recent_logs = db.query(AdminLog).filter(AdminLog.admin_id == admin.id).order_by(AdminLog.id.desc()).limit(8).all()
    communities_overview = None
    if cid is None:
        communities_overview = []
        for c in db.query(Community).order_by(Community.id).all():
            communities_overview.append(
                {
                    "community": c,
                    "users": db.query(User).filter(User.community_id == c.id).count(),
                    "items": db.query(Item).filter(
                        Item.community_id == c.id, Item.status.in_(["on_sale", "reserved"])
                    ).count(),
                    "admins": db.query(AdminUser).filter(AdminUser.community_id == c.id).count(),
                }
            )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "admin": admin,
            "stats": stats,
            "recent_items": recent_items,
            "recent_logs": recent_logs,
            "communities_overview": communities_overview,
            "msg": request.query_params.get("msg"),
        },
    )


# ---------- 邀请码 ----------

@router.get("/invites", response_class=HTMLResponse)
def invites_page(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    q = db.query(Invite)
    if admin.community_id:
        q = q.filter(Invite.community_id == admin.community_id)
    rows = q.order_by(Invite.id.desc()).limit(100).all()
    communities = None
    if _is_super(admin):
        communities = db.query(Community).order_by(Community.id).all()
    community = _own_community(db, admin)
    community_names = {c.id: c.name for c in db.query(Community).all()}
    return templates.TemplateResponse(
        request,
        "invites.html",
        {
            "request": request,
            "admin": admin,
            "invites": rows,
            "community": community,
            "communities": communities,
            "community_names": community_names,
            "msg": request.query_params.get("msg"),
        },
    )


@router.post("/invites")
def create_invites(
    request: Request,
    building: str = Form(...),
    count: int = Form(...),
    days: int = Form(default=14),
    batch_note: str = Form(default=""),
    community_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    if _is_super(admin):
        community = db.get(Community, community_id or 0)
        if community is None:
            return _redirect("/admin/invites", "请选择目标小区")
    else:
        community = _own_community(db, admin)
        if community is None:
            return _redirect("/admin/invites", "账号未绑定小区，请联系平台")
    count = max(1, min(count, 100))
    days = max(1, min(days, 90))
    created = []
    for _ in range(count):
        code = gen_invite_code("YQ")
        db.add(
            Invite(
                community_id=community.id,
                code=code,
                kind="normal",
                building=building.strip(),
                batch_note=batch_note.strip(),
                expires_at=utcnow() + timedelta(days=days),
            )
        )
        created.append(code)
    log_action(db, admin, "create_invites", "invite", None, f"{community.name} {building} x{count}")
    db.commit()
    return _redirect("/admin/invites", f"已生成 {count} 个邀请码")


@router.post("/invites/{invite_id}/revoke")
def revoke_invite(
    invite_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    invite = db.get(Invite, invite_id)
    if invite is None:
        return _redirect("/admin/invites", "邀请码不存在")
    if not _is_super(admin) and invite.community_id != admin.community_id:
        return _forbidden("只能操作本小区的邀请码")
    if invite.status == "active":
        invite.status = "revoked"
        log_action(db, admin, "revoke_invite", "invite", invite.id)
        db.commit()
    return _redirect("/admin/invites", "已作废")


# ---------- 内容巡查 ----------

@router.get("/items", response_class=HTMLResponse)
def admin_items(
    request: Request,
    status: str = "",
    type: str = "",
    keyword: str = "",
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    q = db.query(Item)
    if admin.community_id:
        q = q.filter(Item.community_id == admin.community_id)
    if status:
        q = q.filter(Item.status == status)
    if type:
        q = q.filter(Item.type == type)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(Item.title.like(like))
    rows = q.order_by(Item.id.desc()).limit(100).all()
    community_names = {c.id: c.name for c in db.query(Community).all()}
    return templates.TemplateResponse(
        request,
        "items.html",
        {
            "request": request,
            "admin": admin,
            "items": rows,
            "community_names": community_names,
            "filters": {"status": status, "type": type, "keyword": keyword},
            "msg": request.query_params.get("msg"),
        },
    )


@router.post("/items/{item_id}/off")
def force_off_shelf(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    item = db.get(Item, item_id)
    if item is None:
        return _redirect("/admin/items", "物品不存在")
    if not _is_super(admin) and item.community_id != admin.community_id:
        return _forbidden("只能处置本小区的内容")
    item.status = "archived"
    log_action(db, admin, "force_off_shelf", "item", item.id, item.title)
    db.commit()
    return _redirect("/admin/items", "已强制下架")


# ---------- 举报处置 ----------

@router.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request, status: str = "pending", db: Session = Depends(get_db)
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    q = db.query(Report)
    if admin.community_id:
        q = q.filter(Report.community_id == admin.community_id)
    if status:
        q = q.filter(Report.status == status)
    rows = q.order_by(Report.id.desc()).limit(100).all()
    reporters = {u.id: u for u in db.query(User).filter(User.id.in_([r.reporter_id for r in rows]))}
    community_names = {c.id: c.name for c in db.query(Community).all()}
    targets = []
    for r in rows:
        if r.target_type == "item":
            t = db.get(Item, r.target_id)
            targets.append(f"物品#{r.target_id} {t.title if t else '(已删除)'}")
        elif r.target_type == "message":
            t = db.get(ItemMessage, r.target_id)
            targets.append(f"留言#{r.target_id} {(t.content[:30] if t else '(已删除)')}")
        else:
            t = db.get(User, r.target_id)
            targets.append(f"用户#{r.target_id} {(t.nickname if t else '(已删除)')}")
    return templates.TemplateResponse(
        request,
        "reports.html",
        {
            "request": request,
            "admin": admin,
            "reports": rows,
            "targets": targets,
            "reporters": reporters,
            "community_names": community_names,
            "status": status,
            "msg": request.query_params.get("msg"),
        },
    )


@router.post("/reports/{report_id}")
def handle_report(
    report_id: int,
    request: Request,
    decision: str = Form(...),
    apply_action: bool = Form(default=False),
    note: str = Form(default=""),
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    report = db.get(Report, report_id)
    if report is None:
        return _redirect("/admin/reports", "举报不存在")
    if not _is_super(admin) and report.community_id != admin.community_id:
        return _forbidden("只能处置本小区的举报")
    if report.status != "pending":
        return _redirect("/admin/reports", "该举报已处理")
    if decision == "dismiss":
        report.status = "dismissed"
    else:
        report.status = "resolved"
        if apply_action:
            if report.target_type == "item":
                t = db.get(Item, report.target_id)
                if t:
                    t.status = "archived"
            elif report.target_type == "message":
                t = db.get(ItemMessage, report.target_id)
                if t:
                    t.status = "hidden"
            elif report.target_type == "user":
                t = db.get(User, report.target_id)
                if t:
                    t.status = "banned"
    report.handled_by = admin.id
    report.handled_at = utcnow()
    report.handle_note = note
    log_action(db, admin, f"report_{decision}", "report", report.id, note)
    db.commit()
    return _redirect("/admin/reports", "已处理")


# ---------- 用户管理 ----------

@router.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request, q: str = "", db: Session = Depends(get_db)
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    query = db.query(User)
    if admin.community_id:
        query = query.filter(User.community_id == admin.community_id)
    if q:
        query = query.filter(User.nickname.like(f"%{q.strip()}%"))
    query = query.order_by(User.id.desc()).limit(100)
    vr_q = db.query(VerifyRequest).filter(VerifyRequest.status == "pending")
    if admin.community_id:
        vr_q = vr_q.filter(VerifyRequest.community_id == admin.community_id)
    verify_requests = vr_q.order_by(VerifyRequest.id.desc()).all()
    vr_users = {u.id: u for u in db.query(User).filter(User.id.in_([v.user_id for v in verify_requests]))}
    community_names = {c.id: c.name for c in db.query(Community).all()}
    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "request": request,
            "admin": admin,
            "users": query.all(),
            "verify_requests": verify_requests,
            "vr_users": vr_users,
            "community_names": community_names,
            "q": q,
            "msg": request.query_params.get("msg"),
        },
    )


def _user_in_scope(admin: AdminUser, u: User | None) -> bool:
    if u is None:
        return False
    return _is_super(admin) or u.community_id == admin.community_id


@router.post("/users/{user_id}/ban")
def ban_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    u = db.get(User, user_id)
    if not _user_in_scope(admin, u):
        return _forbidden("只能管理本小区的用户")
    u.status = "banned"
    log_action(db, admin, "ban_user", "user", user_id, u.nickname)
    db.commit()
    return _redirect("/admin/users", "已封禁")


@router.post("/users/{user_id}/unban")
def unban_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    u = db.get(User, user_id)
    if not _user_in_scope(admin, u):
        return _forbidden("只能管理本小区的用户")
    u.status = "active"
    log_action(db, admin, "unban_user", "user", user_id)
    db.commit()
    return _redirect("/admin/users", "已解封")


@router.post("/users/{user_id}/elder")
def toggle_elder(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    u = db.get(User, user_id)
    if not _user_in_scope(admin, u):
        return _forbidden("只能管理本小区的用户")
    u.role = "member" if u.role == "elder" else "elder"
    log_action(db, admin, "toggle_elder", "user", user_id, u.role)
    db.commit()
    return _redirect("/admin/users", "角色已更新")


@router.post("/verify-requests/{vr_id}/approve")
def approve_verify(vr_id: int, request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    vr = db.get(VerifyRequest, vr_id)
    if vr is None:
        return _redirect("/admin/users", "申请不存在")
    if not _is_super(admin) and vr.community_id != admin.community_id:
        return _forbidden("只能审批本小区的申请")
    if vr.status == "pending":
        vr.status = "approved"
        vr.handled_by = admin.id
        vr.handled_at = utcnow()
        u = db.get(User, vr.user_id)
        if u:
            u.community_id = vr.community_id
            u.building = vr.building
            u.unit = vr.unit
            u.verified_at = utcnow()
        log_action(db, admin, "approve_verify", "verify_request", vr_id)
        db.commit()
    return _redirect("/admin/users", "已通过验证")


@router.post("/verify-requests/{vr_id}/reject")
def reject_verify(vr_id: int, request: Request, note: str = Form(default=""), db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    vr = db.get(VerifyRequest, vr_id)
    if vr is None:
        return _redirect("/admin/users", "申请不存在")
    if not _is_super(admin) and vr.community_id != admin.community_id:
        return _forbidden("只能审批本小区的申请")
    if vr.status == "pending":
        vr.status = "rejected"
        vr.handled_by = admin.id
        vr.handled_at = utcnow()
        vr.note = note
        log_action(db, admin, "reject_verify", "verify_request", vr_id, note)
        db.commit()
    return _redirect("/admin/users", "已驳回")


# ---------- 内容安全记录（平台级，仅超管） ----------

@router.get("/sec-checks", response_class=HTMLResponse)
def sec_checks_page(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    if not _is_super(admin):
        return _forbidden("内容安全记录仅平台超管可见")
    rows = db.query(SecCheck).order_by(SecCheck.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "sec_checks.html",
        {"request": request, "admin": admin, "checks": rows,
         "msg": request.query_params.get("msg")},
    )


# ---------- 公告管理 ----------

@router.get("/announcements", response_class=HTMLResponse)
def announcements_page(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    q = db.query(Announcement)
    if admin.community_id:
        q = q.filter(Announcement.community_id == admin.community_id)
    rows = q.order_by(Announcement.id.desc()).limit(100).all()
    communities = None
    if _is_super(admin):
        communities = db.query(Community).filter(Community.status == "active").all()
    community_names = {c.id: c.name for c in db.query(Community).all()}
    publishers = {a.id: a for a in db.query(AdminUser).filter(AdminUser.id.in_([r.published_by for r in rows if r.published_by]))}
    return templates.TemplateResponse(
        request,
        "announcements.html",
        {
            "request": request,
            "admin": admin,
            "announcements": rows,
            "communities": communities,
            "community_names": community_names,
            "publishers": publishers,
            "msg": request.query_params.get("msg"),
        },
    )


@router.post("/announcements")
def create_announcement(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    community_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    if _is_super(admin):
        community = db.get(Community, community_id or 0)
        if community is None:
            return _redirect("/admin/announcements", "请选择目标小区")
    else:
        community = _own_community(db, admin)
        if community is None:
            return _redirect("/admin/announcements", "账号未绑定小区，请联系平台")
    title = title.strip()
    content = content.strip()
    if not title or not content:
        return _redirect("/admin/announcements", "标题和内容不能为空")
    if len(title) > 100:
        return _redirect("/admin/announcements", "标题不能超过 100 字")
    # 不走微信 msgSecCheck：该接口要求终端用户 openid，而公告由可信管理员发布；
    # 问责靠 admin_logs 留痕（设计修订，docs/07 §4.6）
    db.add(
        Announcement(
            community_id=community.id, title=title, content=content, published_by=admin.id
        )
    )
    log_action(db, admin, "create_announcement", "community", community.id, title)
    db.commit()
    return _redirect("/admin/announcements", "公告已发布")


@router.post("/announcements/{announcement_id}/delete")
def delete_announcement(
    announcement_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    a = db.get(Announcement, announcement_id)
    if a is None:
        return _redirect("/admin/announcements", "公告不存在")
    if not _is_super(admin) and a.community_id != admin.community_id:
        return _forbidden("只能删除本小区的公告")
    log_action(db, admin, "delete_announcement", "announcement", a.id, a.title)
    db.delete(a)
    db.commit()
    return _redirect("/admin/announcements", "已删除")


# ---------- 小区管理（仅超管） ----------

def _require_super_admin(admin: AdminUser) -> HTMLResponse | None:
    if not _is_super(admin):
        return _forbidden("仅平台超管可访问")
    return None


@router.get("/communities", response_class=HTMLResponse)
def communities_page(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    if err := _require_super_admin(admin):
        return err
    rows = []
    for c in db.query(Community).order_by(Community.id).all():
        rows.append(
            {
                "community": c,
                "users": db.query(User).filter(User.community_id == c.id).count(),
                "items": db.query(Item).filter(Item.community_id == c.id).count(),
                "admins": db.query(AdminUser).filter(AdminUser.community_id == c.id).all(),
            }
        )
    return templates.TemplateResponse(
        request,
        "communities.html",
        {
            "request": request,
            "admin": admin,
            "rows": rows,
            "msg": request.query_params.get("msg"),
        },
    )


@router.post("/communities")
def create_community(
    request: Request,
    name: str = Form(...),
    city: str = Form(...),
    district: str = Form(default=""),
    address: str = Form(default=""),
    admin_username: str = Form(...),
    admin_name: str = Form(default=""),
    admin_password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    if err := _require_super_admin(admin):
        return err
    name, city = name.strip(), city.strip()
    username = admin_username.strip()
    if not name or not city:
        return _redirect("/admin/communities", "名称和城市必填")
    if len(admin_password) < 8:
        return _redirect("/admin/communities", "物业账号初始密码至少 8 位")
    if db.query(AdminUser).filter(AdminUser.username == username).first():
        return _redirect("/admin/communities", "物业账号用户名已存在")
    community = Community(
        name=name, city=city, district=district.strip(), address=address.strip()
    )
    db.add(community)
    db.flush()
    db.add(
        AdminUser(
            username=username,
            password_hash=hash_password(admin_password),
            name=admin_name.strip() or f"{name}物业",
            community_id=community.id,
        )
    )
    log_action(db, admin, "create_community", "community", community.id, f"{name}({city})")
    db.commit()
    return _redirect("/admin/communities", f"小区「{name}」已开通")


@router.post("/communities/{community_id}/toggle-status")
def toggle_community_status(
    community_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    if err := _require_super_admin(admin):
        return err
    c = db.get(Community, community_id)
    if c:
        c.status = "suspended" if c.status == "active" else "active"
        log_action(db, admin, "toggle_community", "community", c.id, c.status)
        db.commit()
    return _redirect("/admin/communities", "状态已更新")


@router.post("/communities/{community_id}/reset-password")
def reset_community_admin_password(
    community_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    if err := _require_super_admin(admin):
        return err
    c = db.get(Community, community_id)
    if c is None:
        return _redirect("/admin/communities", "小区不存在")
    new_password = secrets.token_urlsafe(9)  # 约 12 位，一次性展示
    for a in db.query(AdminUser).filter(AdminUser.community_id == community_id).all():
        a.password_hash = hash_password(new_password)
    log_action(db, admin, "reset_community_password", "community", community_id)
    db.commit()
    return templates.TemplateResponse(
        request,
        "communities.html",
        {
            "request": request,
            "admin": admin,
            "rows": [
                {
                    "community": cc,
                    "users": db.query(User).filter(User.community_id == cc.id).count(),
                    "items": db.query(Item).filter(Item.community_id == cc.id).count(),
                    "admins": db.query(AdminUser).filter(AdminUser.community_id == cc.id).all(),
                }
                for cc in db.query(Community).order_by(Community.id).all()
            ],
            "new_password": new_password,
            "reset_for": c.name,
            "msg": None,
        },
    )
