"""Web 管理后台：session 鉴权 + Jinja2 SSR。"""

import logging
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.deps import gen_invite_code, get_db
from app.core.security import verify_password
from app.core.time import utcnow
from app.models import (
    AdminLog,
    AdminUser,
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
router = APIRouter(prefix="/admin", tags=["admin"])


# ---------- 会话 ----------

def _auth_or_redirect(request: Request, db: Session) -> AdminUser | None:
    admin_id = request.session.get("admin_id")
    if not admin_id:
        return None
    return db.get(AdminUser, admin_id)


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


# ---------- 看板 ----------

@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    stats = {
        "users": db.query(User).count(),
        "verified": db.query(User).filter(User.verified_at.is_not(None)).count(),
        "items": db.query(Item).filter(Item.status.in_(["on_sale", "reserved"])).count(),
        "trades_done": db.query(Item).filter(Item.status == "completed").count(),
        "pending_reports": db.query(Report).filter(Report.status == "pending").count(),
        "pending_verify": db.query(VerifyRequest)
        .filter(VerifyRequest.status == "pending")
        .count(),
        "active_invites": db.query(Invite).filter(Invite.status == "active").count(),
    }
    recent_items = db.query(Item).order_by(Item.id.desc()).limit(8).all()
    recent_logs = db.query(AdminLog).order_by(AdminLog.id.desc()).limit(8).all()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "admin": admin,
            "stats": stats,
            "recent_items": recent_items,
            "recent_logs": recent_logs,
            "msg": request.query_params.get("msg"),
        },
    )


# ---------- 邀请码 ----------

@router.get("/invites", response_class=HTMLResponse)
def invites_page(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    community = db.query(Community).order_by(Community.id).first()
    rows = db.query(Invite).order_by(Invite.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "invites.html",
        {
            "request": request,
            "admin": admin,
            "invites": rows,
            "community": community,
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
    db: Session = Depends(get_db),
):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    community = db.query(Community).order_by(Community.id).first()
    if community is None:
        return _redirect("/admin/invites", "请先初始化社区（scripts/seed.py）")
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
    log_action(db, admin, "create_invites", "invite", None, f"{building} x{count}")
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
    if invite and invite.status == "active":
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
    if status:
        q = q.filter(Item.status == status)
    if type:
        q = q.filter(Item.type == type)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(Item.title.like(like))
    rows = q.order_by(Item.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "items.html",
        {
            "request": request,
            "admin": admin,
            "items": rows,
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
    if item:
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
    if status:
        q = q.filter(Report.status == status)
    rows = q.order_by(Report.id.desc()).limit(100).all()
    reporters = {u.id: u for u in db.query(User).filter(User.id.in_([r.reporter_id for r in rows]))}
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
    if report is None or report.status != "pending":
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
    query = db.query(User).order_by(User.id.desc()).limit(100)
    if q:
        like = f"%{q.strip()}%"
        query = db.query(User).filter(User.nickname.like(like)).order_by(User.id.desc()).limit(100)
    verify_requests = (
        db.query(VerifyRequest).filter(VerifyRequest.status == "pending").order_by(VerifyRequest.id.desc()).all()
    )
    vr_users = {u.id: u for u in db.query(User).filter(User.id.in_([v.user_id for v in verify_requests]))}
    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "request": request,
            "admin": admin,
            "users": query.all(),
            "verify_requests": verify_requests,
            "vr_users": vr_users,
            "q": q,
            "msg": request.query_params.get("msg"),
        },
    )


@router.post("/users/{user_id}/ban")
def ban_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    u = db.get(User, user_id)
    if u:
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
    if u:
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
    if u:
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
    if vr and vr.status == "pending":
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
    if vr and vr.status == "pending":
        vr.status = "rejected"
        vr.handled_by = admin.id
        vr.handled_at = utcnow()
        vr.note = note
        log_action(db, admin, "reject_verify", "verify_request", vr_id, note)
        db.commit()
    return _redirect("/admin/users", "已驳回")


# ---------- 内容安全记录 ----------

@router.get("/sec-checks", response_class=HTMLResponse)
def sec_checks_page(request: Request, db: Session = Depends(get_db)):
    admin = _auth_or_redirect(request, db)
    if admin is None:
        return _redirect("/admin/login")
    rows = db.query(SecCheck).order_by(SecCheck.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "sec_checks.html",
        {"request": request, "admin": admin, "checks": rows,
         "msg": request.query_params.get("msg")},
    )
