"""管理后台 JSON API（/api/admin/*），SPA 专用（docs/08 §4）。

与 SSR 路由（routes.py）功能对等：两级分权、服务端隔离、越权 403、admin_logs 留痕。
信封沿用 {code, message, data}；401=未登录、403=越权；分页 page/page_size/total。
"""

import logging
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import gen_invite_code, get_db
from app.core.errors import bad_request, forbidden, unauthorized
from app.core.security import hash_password, verify_password
from app.core.time import iso, utcnow
from app.models import (
    AdminLog,
    AdminUser,
    Announcement,
    Post,
    Community,
    Invite,
    Item,
    ItemMessage,
    Report,
    SecCheck,
    User,
    VerifyRequest,
)
from app.schemas import (
    AdminAnnouncementCreateRequest,
    AdminFaqCreateRequest,
    AdminFaqUpdateRequest,
    AdminAnnouncementUpdateRequest,
    AdminCommunityCreateRequest,
    AdminInviteCreateRequest,
    AdminLoginRequest,
    AdminPasswordChangeRequest,
    AdminReportHandleRequest,
    AdminVerifyRejectRequest,
)
from app.schemas.serialize import ok
from app.services.rate_limit import check_rate, get_failure_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-api"])

# 登录防爆破（docs/09 P0-2）
LOGIN_IP_LIMIT = 10        # 每 IP 5 分钟
LOGIN_IP_WINDOW = 300
LOGIN_FAIL_LIMIT = 5       # 同账号连续失败
LOGIN_LOCK_WINDOW = 900    # 锁定 15 分钟


# ---------- 鉴权与权限 ----------

def get_current_admin(request: Request, db: Session = Depends(get_db)):  # 返回 AdminUser（不加返回注解）
    admin_id = request.session.get("admin_id")
    if not admin_id:
        raise unauthorized("请先登录管理后台")
    admin = db.get(AdminUser, admin_id)
    if admin is None:
        raise unauthorized("登录状态已失效，请重新登录")
    return admin


def require_super(admin: AdminUser) -> None:
    if admin.community_id is not None:
        raise forbidden("仅平台超管可执行此操作")


def _own_community(db: Session, admin: AdminUser) -> Community | None:
    return db.get(Community, admin.community_id) if admin.community_id else None


def _log(db: Session, admin: AdminUser, action: str, target_type=None, target_id=None, detail=None) -> None:
    db.add(AdminLog(admin_id=admin.id, action=action, target_type=target_type, target_id=target_id, detail=detail))


def _paged(q, page: int, page_size: int) -> tuple:
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


def _page_args(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return max(1, page), min(page_size, 100)


def _page_payload(rows: list, total: int, page: int, page_size: int) -> dict:
    return ok({"list": rows, "total": total, "page": page, "page_size": page_size})


def _community_name_map(db: Session, ids: list) -> dict:
    ids = [i for i in ids if i]
    if not ids:
        return {}
    return {c.id: c.name for c in db.query(Community).filter(Community.id.in_(ids)).all()}


def admin_dto(db: Session, admin: AdminUser) -> dict:
    community = None
    if admin.community_id:
        c = db.get(Community, admin.community_id)
        if c:
            community = {"id": c.id, "name": c.name, "city": c.city}
    return {
        "id": admin.id,
        "username": admin.username,
        "name": admin.name,
        "role": "super" if admin.community_id is None else "community",
        "community": community,
    }


# ---------- auth ----------

@router.post("/auth/login")
def login(request: Request, payload: AdminLoginRequest, db: Session = Depends(get_db)):
    from app.core.middleware import _client_ip
    from app.core.errors import too_many

    ip = _client_ip(request)
    if not check_rate(f"login:ip:{ip}", LOGIN_IP_LIMIT, LOGIN_IP_WINDOW):
        raise too_many("尝试过于频繁，请 5 分钟后再试")

    username = payload.username.strip()
    tracker = get_failure_tracker()
    if tracker.count(f"login:{username}", LOGIN_LOCK_WINDOW) >= LOGIN_FAIL_LIMIT:
        raise unauthorized("失败次数过多，账号已临时锁定 15 分钟")

    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        fails = tracker.record(f"login:{username}", LOGIN_LOCK_WINDOW)
        if admin is not None:
            _log(db, admin, "login_failed", "admin", admin.id, f"fail={fails} ip={ip}")
            db.commit()
        else:
            logger.warning("login_failed unknown username=%s ip=%s", username, ip)
        raise unauthorized("用户名或密码错误")
    tracker.clear(f"login:{username}")
    admin.last_login_at = utcnow()
    request.session["admin_id"] = admin.id
    db.commit()
    return ok(admin_dto(db, admin))


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return ok({"ok": True})


@router.get("/auth/me")
def me(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    return ok(admin_dto(db, admin))


# ---------- stats ----------

@router.get("/stats")
def stats(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    cid = admin.community_id

    def _users():
        q = db.query(User)
        return q.filter(User.community_id == cid) if cid else q

    def _items():
        q = db.query(Item)
        return q.filter(Item.community_id == cid) if cid else q

    data = {
        "users": _users().count(),
        "verified": _users().filter(User.verified_at.is_not(None)).count(),
        "items": _items().filter(Item.status.in_(["on_sale", "reserved"])).count(),
        "trades_done": _items().filter(Item.status == "completed").count(),
        "pending_reports": db.query(Report).filter(
            Report.status == "pending", *([Report.community_id == cid] if cid else [])
        ).count(),
        "pending_verify": db.query(VerifyRequest).filter(
            VerifyRequest.status == "pending", *([VerifyRequest.community_id == cid] if cid else [])
        ).count(),
        "active_invites": db.query(Invite).filter(
            Invite.status == "active", *([Invite.community_id == cid] if cid else [])
        ).count(),
    }
    if cid is None:
        data["communities_overview"] = [
            {
                "id": c.id,
                "name": c.name,
                "city": c.city,
                "status": c.status,
                "users": db.query(User).filter(User.community_id == c.id).count(),
                "items": db.query(Item).filter(
                    Item.community_id == c.id, Item.status.in_(["on_sale", "reserved"])
                ).count(),
                "admins": db.query(AdminUser).filter(AdminUser.community_id == c.id).count(),
            }
            for c in db.query(Community).order_by(Community.id).all()
        ]
    return ok(data)


# ---------- 邀请码 ----------

def _invite_dto(inv: Invite, names: dict) -> dict:
    return {
        "id": inv.id,
        "code": inv.code,
        "kind": inv.kind,
        "building": inv.building,
        "batch_note": inv.batch_note,
        "status": inv.status,
        "used_by": inv.used_by,
        "expires_at": iso(inv.expires_at) if inv.expires_at else None,
        "community_id": inv.community_id,
        "community_name": names.get(inv.community_id, str(inv.community_id)),
        "created_at": iso(inv.created_at),
    }


@router.get("/invites")
def list_invites(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    page, page_size = _page_args(page, page_size)
    q = db.query(Invite)
    if admin.community_id:
        q = q.filter(Invite.community_id == admin.community_id)
    if status:
        q = q.filter(Invite.status == status)
    q = q.order_by(Invite.id.desc())
    rows, total = _paged(q, page, page_size)
    names = _community_name_map(db, [r.community_id for r in rows])
    return _page_payload([_invite_dto(r, names) for r in rows], total, page, page_size)


@router.post("/invites")
def create_invites(
    payload: AdminInviteCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if admin.community_id:
        community = _own_community(db, admin)
        if community is None:
            raise bad_request("账号未绑定小区，请联系平台")
    else:
        community = db.get(Community, payload.community_id or 0)
        if community is None:
            raise bad_request("请选择目标小区")
    created = []
    for _ in range(payload.count):
        code = gen_invite_code("YQ")
        db.add(
            Invite(
                community_id=community.id,
                code=code,
                kind="normal",
                building=payload.building.strip(),
                batch_note=payload.batch_note.strip(),
                expires_at=utcnow() + timedelta(days=payload.days),
            )
        )
        created.append(code)
    _log(db, admin, "create_invites", "invite", None, f"{community.name} {payload.building} x{payload.count}")
    db.commit()
    return ok({"created": created, "community_id": community.id, "community_name": community.name})


@router.post("/invites/{invite_id}/revoke")
def revoke_invite(invite_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    inv = db.get(Invite, invite_id)
    if inv is None:
        raise bad_request("邀请码不存在")
    if admin.community_id and inv.community_id != admin.community_id:
        raise forbidden("只能操作本小区的邀请码")
    if inv.status == "active":
        inv.status = "revoked"
        _log(db, admin, "revoke_invite", "invite", inv.id)
        db.commit()
    return ok({"ok": True})


# ---------- 公告 ----------

def _announcement_dto(a: Announcement, names: dict, publishers: dict) -> dict:
    pub = publishers.get(a.published_by)
    return {
        "id": a.id,
        "title": a.title,
        "content": a.content,
        "community_id": a.community_id,
        "community_name": names.get(a.community_id, str(a.community_id)),
        "published_by_name": (pub.name or pub.username) if pub else None,
        "pinned": a.pinned,
        "created_at": iso(a.created_at),
    }


@router.get("/announcements")
def list_announcements(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    page, page_size = _page_args(page, page_size)
    q = db.query(Announcement)
    if admin.community_id:
        q = q.filter(Announcement.community_id == admin.community_id)
    q = q.order_by(Announcement.pinned.desc(), Announcement.id.desc())
    rows, total = _paged(q, page, page_size)
    names = _community_name_map(db, [r.community_id for r in rows])
    pubs = {
        a.id: a
        for a in db.query(AdminUser)
        .filter(AdminUser.id.in_([r.published_by for r in rows if r.published_by]))
        .all()
    }
    return _page_payload([_announcement_dto(r, names, pubs) for r in rows], total, page, page_size)


@router.post("/announcements")
def create_announcement(
    payload: AdminAnnouncementCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if admin.community_id:
        community = _own_community(db, admin)
        if community is None:
            raise bad_request("账号未绑定小区，请联系平台")
    else:
        community = db.get(Community, payload.community_id or 0)
        if community is None:
            raise bad_request("请选择目标小区")
    a = Announcement(
        community_id=community.id, title=payload.title.strip(),
        content=payload.content.strip(), published_by=admin.id,
    )
    db.add(a)
    db.flush()
    _log(db, admin, "create_announcement", "community", community.id, a.title)
    db.commit()
    return ok({"id": a.id})


@router.put("/announcements/{announcement_id}")
def update_announcement(
    announcement_id: int,
    payload: AdminAnnouncementUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    a = db.get(Announcement, announcement_id)
    if a is None:
        raise bad_request("公告不存在")
    if admin.community_id and a.community_id != admin.community_id:
        raise forbidden("只能编辑本小区的公告")
    if payload.title is not None:
        a.title = payload.title.strip()
    if payload.content is not None:
        a.content = payload.content.strip()
    if payload.pinned is not None:
        a.pinned = payload.pinned
    _log(db, admin, "update_announcement", "announcement", a.id, a.title)
    db.commit()
    return ok({"ok": True})


@router.delete("/announcements/{announcement_id}")
def delete_announcement(
    announcement_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    a = db.get(Announcement, announcement_id)
    if a is None:
        raise bad_request("公告不存在")
    if admin.community_id and a.community_id != admin.community_id:
        raise forbidden("只能删除本小区的公告")
    _log(db, admin, "delete_announcement", "announcement", a.id, a.title)
    db.delete(a)
    db.commit()
    return ok({"ok": True})


# ---------- 内容巡查 ----------

def _item_admin_dto(it: Item, names: dict, owner: User | None) -> dict:
    return {
        "id": it.id,
        "title": it.title,
        "type": it.type,
        "status": it.status,
        "building": it.building,
        "owner_nickname": owner.nickname if owner else None,
        "community_id": it.community_id,
        "community_name": names.get(it.community_id, str(it.community_id)),
        "created_at": iso(it.created_at),
    }


@router.get("/items")
def list_items(
    status: str | None = None,
    type: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    page, page_size = _page_args(page, page_size)
    q = db.query(Item)
    if admin.community_id:
        q = q.filter(Item.community_id == admin.community_id)
    if status:
        q = q.filter(Item.status == status)
    if type:
        q = q.filter(Item.type == type)
    if keyword:
        q = q.filter(Item.title.like(f"%{keyword.strip()}%"))
    q = q.order_by(Item.id.desc())
    rows, total = _paged(q, page, page_size)
    names = _community_name_map(db, [r.community_id for r in rows])
    owners = {u.id: u for u in db.query(User).filter(User.id.in_([r.user_id for r in rows])).all()}
    return _page_payload([_item_admin_dto(r, names, owners.get(r.user_id)) for r in rows], total, page, page_size)


@router.post("/items/{item_id}/off")
def force_off_item(item_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    it = db.get(Item, item_id)
    if it is None:
        raise bad_request("物品不存在")
    if admin.community_id and it.community_id != admin.community_id:
        raise forbidden("只能处置本小区的内容")
    it.status = "archived"
    _log(db, admin, "force_off_shelf", "item", it.id, it.title)
    db.commit()
    return ok({"ok": True})


# ---------- 举报处置 ----------

def _report_dto(db: Session, r: Report, names: dict, reporters: dict) -> dict:
    if r.target_type == "item":
        t = db.get(Item, r.target_id)
        target_text = f"物品#{r.target_id} {t.title if t else '(已删除)'}"
    elif r.target_type == "message":
        t = db.get(ItemMessage, r.target_id)
        target_text = f"留言#{r.target_id} {(t.content[:30] if t else '(已删除)')}"
    else:
        t = db.get(User, r.target_id)
        target_text = f"用户#{r.target_id} {(t.nickname if t else '(已删除)')}"
    rep = reporters.get(r.reporter_id)
    return {
        "id": r.id,
        "target_type": r.target_type,
        "target_id": r.target_id,
        "target_text": target_text,
        "reason": r.reason,
        "detail": r.detail,
        "status": r.status,
        "note": r.handle_note,
        "community_id": r.community_id,
        "community_name": names.get(r.community_id) if r.community_id else "无归属",
        "reporter": {"id": r.reporter_id, "nickname": rep.nickname if rep else None},
        "created_at": iso(r.created_at),
        "handled_at": iso(r.handled_at) if r.handled_at else None,
    }


@router.get("/reports")
def list_reports(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    page, page_size = _page_args(page, page_size)
    q = db.query(Report)
    if admin.community_id:
        q = q.filter(Report.community_id == admin.community_id)
    if status:
        q = q.filter(Report.status == status)
    q = q.order_by(Report.id.desc())
    rows, total = _paged(q, page, page_size)
    names = _community_name_map(db, [r.community_id for r in rows])
    reporters = {u.id: u for u in db.query(User).filter(User.id.in_([r.reporter_id for r in rows])).all()}
    return _page_payload([_report_dto(db, r, names, reporters) for r in rows], total, page, page_size)


@router.post("/reports/{report_id}")
def handle_report(
    report_id: int,
    payload: AdminReportHandleRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    report = db.get(Report, report_id)
    if report is None:
        raise bad_request("举报不存在")
    if admin.community_id and report.community_id != admin.community_id:
        raise forbidden("只能处置本小区的举报")
    if report.status != "pending":
        raise bad_request("该举报已处理")
    if payload.decision == "dismiss":
        report.status = "dismissed"
    elif payload.decision == "resolve":
        report.status = "resolved"
        if payload.apply_action:
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
    else:
        raise bad_request("decision 不合法")
    report.handled_by = admin.id
    report.handled_at = utcnow()
    report.handle_note = payload.note
    _log(db, admin, f"report_{payload.decision}", "report", report.id, payload.note)
    db.commit()
    return ok({"ok": True})


# ---------- 用户管理 ----------

def _user_admin_dto(u: User, names: dict) -> dict:
    return {
        "id": u.id,
        "nickname": u.nickname,
        "building": u.building,
        "unit": u.unit,
        "community_id": u.community_id,
        "community_name": names.get(u.community_id) if u.community_id else "未加入",
        "role": u.role,
        "verified": u.verified,
        "status": u.status,
        "trades_done": u.trades_done,
        "violations": u.violations,
        "created_at": iso(u.created_at),
    }


def _user_in_scope(admin: AdminUser, u: User | None) -> bool:
    if u is None:
        return False
    return admin.community_id is None or u.community_id == admin.community_id


@router.get("/users")
def list_users(
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    page, page_size = _page_args(page, page_size)
    query = db.query(User)
    if admin.community_id:
        query = query.filter(User.community_id == admin.community_id)
    if q:
        query = query.filter(User.nickname.like(f"%{q.strip()}%"))
    query = query.order_by(User.id.desc())
    rows, total = _paged(query, page, page_size)
    names = _community_name_map(db, [r.community_id for r in rows])
    return _page_payload([_user_admin_dto(r, names) for r in rows], total, page, page_size)


@router.post("/users/{user_id}/ban")
def ban_user(user_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not _user_in_scope(admin, u):
        raise forbidden("只能管理本小区的用户")
    u.status = "banned"
    _log(db, admin, "ban_user", "user", user_id, u.nickname)
    db.commit()
    return ok({"ok": True})


@router.post("/users/{user_id}/unban")
def unban_user(user_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not _user_in_scope(admin, u):
        raise forbidden("只能管理本小区的用户")
    u.status = "active"
    _log(db, admin, "unban_user", "user", user_id)
    db.commit()
    return ok({"ok": True})


@router.post("/users/{user_id}/elder")
def toggle_elder(user_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not _user_in_scope(admin, u):
        raise forbidden("只能管理本小区的用户")
    u.role = "member" if u.role == "elder" else "elder"
    _log(db, admin, "toggle_elder", "user", user_id, u.role)
    db.commit()
    return ok({"ok": True})


# ---------- 人工验证审批 ----------

@router.get("/verify-requests")
def list_verify_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    page, page_size = _page_args(page, page_size)
    q = db.query(VerifyRequest).filter(VerifyRequest.status == "pending")
    if admin.community_id:
        q = q.filter(VerifyRequest.community_id == admin.community_id)
    q = q.order_by(VerifyRequest.id.desc())
    rows, total = _paged(q, page, page_size)
    applicants = {u.id: u for u in db.query(User).filter(User.id.in_([r.user_id for r in rows])).all()}
    names = _community_name_map(db, [r.community_id for r in rows])
    return _page_payload(
        [
            {
                "id": r.id,
                "user": {
                    "id": r.user_id,
                    "nickname": applicants[r.user_id].nickname if r.user_id in applicants else None,
                },
                "building": r.building,
                "unit": r.unit,
                "proof_image": r.proof_image,
                "community_id": r.community_id,
                "community_name": names.get(r.community_id) if r.community_id else "无归属",
                "created_at": iso(r.created_at),
            }
            for r in rows
        ],
        total,
        page,
        page_size,
    )


@router.post("/verify-requests/{vr_id}/approve")
def approve_verify(vr_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    vr = db.get(VerifyRequest, vr_id)
    if vr is None:
        raise bad_request("申请不存在")
    if admin.community_id and vr.community_id != admin.community_id:
        raise forbidden("只能审批本小区的申请")
    if vr.status != "pending":
        raise bad_request("该申请已处理")
    vr.status = "approved"
    vr.handled_by = admin.id
    vr.handled_at = utcnow()
    u = db.get(User, vr.user_id)
    if u:
        u.community_id = vr.community_id
        u.building = vr.building
        u.unit = vr.unit
        u.verified_at = utcnow()
    _log(db, admin, "approve_verify", "verify_request", vr_id)
    db.commit()
    return ok({"ok": True})


@router.post("/verify-requests/{vr_id}/reject")
def reject_verify(
    vr_id: int,
    payload: AdminVerifyRejectRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    vr = db.get(VerifyRequest, vr_id)
    if vr is None:
        raise bad_request("申请不存在")
    if admin.community_id and vr.community_id != admin.community_id:
        raise forbidden("只能审批本小区的申请")
    if vr.status != "pending":
        raise bad_request("该申请已处理")
    vr.status = "rejected"
    vr.handled_by = admin.id
    vr.handled_at = utcnow()
    vr.note = payload.note
    _log(db, admin, "reject_verify", "verify_request", vr_id, payload.note)
    db.commit()
    return ok({"ok": True})


# ---------- 小区管理（仅超管） ----------

@router.get("/communities")
def list_communities(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    require_super(admin)
    rows = []
    for c in db.query(Community).order_by(Community.id).all():
        admins = db.query(AdminUser).filter(AdminUser.community_id == c.id).all()
        rows.append(
            {
                "id": c.id,
                "name": c.name,
                "city": c.city,
                "district": c.district,
                "address": c.address,
                "status": c.status,
                "users": db.query(User).filter(User.community_id == c.id).count(),
                "items": db.query(Item).filter(Item.community_id == c.id).count(),
                "admins": [{"username": a.username, "name": a.name} for a in admins],
                "created_at": iso(c.created_at),
            }
        )
    return ok({"list": rows})


@router.post("/communities")
def create_community(
    payload: AdminCommunityCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    require_super(admin)
    username = payload.admin_username.strip()
    if db.query(AdminUser).filter(AdminUser.username == username).first():
        raise bad_request("物业账号用户名已存在")
    c = Community(
        name=payload.name.strip(), city=payload.city.strip(),
        district=payload.district.strip(), address=payload.address.strip(),
    )
    db.add(c)
    db.flush()
    db.add(
        AdminUser(
            username=username,
            password_hash=hash_password(payload.admin_password),
            name=payload.admin_name.strip() or f"{c.name}物业",
            community_id=c.id,
        )
    )
    _log(db, admin, "create_community", "community", c.id, f"{c.name}({c.city})")
    db.commit()
    return ok({"id": c.id})


@router.post("/communities/{community_id}/toggle-status")
def toggle_community(community_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    require_super(admin)
    c = db.get(Community, community_id)
    if c is None:
        raise bad_request("小区不存在")
    c.status = "suspended" if c.status == "active" else "active"
    _log(db, admin, "toggle_community", "community", c.id, c.status)
    db.commit()
    return ok({"status": c.status})


@router.post("/communities/{community_id}/reset-password")
def reset_password(community_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    import secrets

    require_super(admin)
    c = db.get(Community, community_id)
    if c is None:
        raise bad_request("小区不存在")
    new_password = secrets.token_urlsafe(9)
    for a in db.query(AdminUser).filter(AdminUser.community_id == community_id).all():
        a.password_hash = hash_password(new_password)
    _log(db, admin, "reset_community_password", "community", community_id)
    db.commit()
    return ok({"new_password": new_password})


# ---------- 内容安全记录（仅超管） ----------

@router.get("/sec-checks")
def list_sec_checks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    require_super(admin)
    page, page_size = _page_args(page, page_size)
    q = db.query(SecCheck).order_by(SecCheck.id.desc())
    rows, total = _paged(q, page, page_size)
    return _page_payload(
        [
            {
                "id": r.id,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "status": r.status,
                "detail": r.detail,
                "created_at": iso(r.created_at),
            }
            for r in rows
        ],
        total,
        page,
        page_size,
    )


# ---------- 改密码 ----------

@router.post("/password")
def change_password(
    payload: AdminPasswordChangeRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, admin.password_hash):
        raise bad_request("旧密码不正确")
    admin.password_hash = hash_password(payload.new_password)
    _log(db, admin, "change_password")
    db.commit()
    return ok({"ok": True})


# ---------- 操作日志（docs/09 P1-6） ----------

@router.get("/logs")
def list_logs(
    action: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """物业仅看自己的操作；超管看全部（含操作者）。"""
    page, page_size = _page_args(page, page_size)
    q = db.query(AdminLog)
    if admin.community_id:
        q = q.filter(AdminLog.admin_id == admin.id)
    if action:
        q = q.filter(AdminLog.action == action)
    q = q.order_by(AdminLog.id.desc())
    rows, total = _paged(q, page, page_size)
    admins = {a.id: a for a in db.query(AdminUser).filter(AdminUser.id.in_([r.admin_id for r in rows])).all()}
    return _page_payload(
        [
            {
                "id": r.id,
                "admin_id": r.admin_id,
                "admin_name": (admins[r.admin_id].name or admins[r.admin_id].username) if r.admin_id in admins else f"#{r.admin_id}",
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "detail": r.detail,
                "created_at": iso(r.created_at),
            }
            for r in rows
        ],
        total,
        page,
        page_size,
    )


# ---------- 待审内容处置闭环（docs/09 P1-7） ----------

def _pending_items(db: Session, admin: AdminUser, page: int, page_size: int):
    q = db.query(Item).filter(Item.sec_status == "pending")
    if admin.community_id:
        q = q.filter(Item.community_id == admin.community_id)
    return _paged(q.order_by(Item.id.desc()), page, page_size)


def _pending_messages(db: Session, admin: AdminUser, page: int, page_size: int):
    q = db.query(ItemMessage).filter(ItemMessage.sec_status == "pending")
    if admin.community_id:
        q = q.join(Item, ItemMessage.item_id == Item.id).filter(Item.community_id == admin.community_id)
    return _paged(q.order_by(ItemMessage.id.desc()), page, page_size)


@router.get("/pending-content")
def list_pending_content(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """文本审核异常降级（pending）的物品与留言：仅作者与管理员可见，需人工放行/拒绝。"""
    page, page_size = _page_args(page, page_size)
    items, items_total = _pending_items(db, admin, page, page_size)
    messages, messages_total = _pending_messages(db, admin, page, page_size)
    names = _community_name_map(db, [i.community_id for i in items])
    authors = {u.id: u for u in db.query(User).filter(
        User.id.in_([i.user_id for i in items] + [m.user_id for m in messages])
    ).all()}
    item_titles = {i.id: i.title for i in db.query(Item).filter(
        Item.id.in_([m.item_id for m in messages])
    ).all()}
    return ok(
        {
            "items": [
                {
                    "id": i.id,
                    "title": i.title,
                    "author_nickname": authors[i.user_id].nickname if i.user_id in authors else None,
                    "community_name": names.get(i.community_id, str(i.community_id)),
                    "created_at": iso(i.created_at),
                }
                for i in items
            ],
            "items_total": items_total,
            "messages": [
                {
                    "id": m.id,
                    "content": m.content,
                    "item_id": m.item_id,
                    "item_title": item_titles.get(m.item_id),
                    "author_nickname": authors[m.user_id].nickname if m.user_id in authors else None,
                    "created_at": iso(m.created_at),
                }
                for m in messages
            ],
            "messages_total": messages_total,
        }
    )


@router.post("/pending-content/{kind}/{content_id}/approve")
def approve_pending(
    kind: str, content_id: int,
    admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db),
):
    obj, owner_id = _get_pending(db, admin, kind, content_id)
    obj.sec_status = "pass"
    _log(db, admin, f"approve_{kind}", kind, content_id)
    db.commit()
    return ok({"ok": True})


@router.post("/pending-content/{kind}/{content_id}/reject")
def reject_pending(
    kind: str, content_id: int,
    admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db),
):
    from app.services.notify import push_notification

    obj, owner_id = _get_pending(db, admin, kind, content_id)
    obj.sec_status = "fail"  # 标记审核失败：移出待审队列且不再展示
    if kind == "item":
        obj.status = "archived"
        title = obj.title
    else:
        obj.status = "hidden"
        title = obj.content[:30]
    push_notification(
        db, owner_id, "content_rejected", "内容未通过审核",
        f"你的内容「{title}」未通过审核，已{'下架' if kind == 'item' else '隐藏'}",
        {},
    )
    _log(db, admin, f"reject_{kind}", kind, content_id, title)
    db.commit()
    return ok({"ok": True})


def _get_pending(db: Session, admin: AdminUser, kind: str, content_id: int):
    if kind == "item":
        obj = db.get(Item, content_id)
        community_id = obj.community_id if obj else None
    elif kind == "message":
        obj = db.get(ItemMessage, content_id)
        item = db.get(Item, obj.item_id) if obj else None
        community_id = item.community_id if item else None
    else:
        raise bad_request("kind 不合法")
    if obj is None:
        raise bad_request("内容不存在")
    if admin.community_id and community_id != admin.community_id:
        raise forbidden("只能处置本小区的内容")
    if obj.sec_status != "pending":
        raise bad_request("该内容不在待审状态")
    return obj, obj.user_id


# ---------- 导出（docs/09 P1-10） ----------

def _csv_response(rows: list[list], headers: list[str], filename: str):
    from fastapi.responses import Response

    lines = [",".join(headers)]
    for row in rows:
        cells = []
        for v in row:
            text = "" if v is None else str(v)
            if any(c in text for c in [",", '"', "\n"]):
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        lines.append(",".join(cells))
    body = "\ufeff" + "\n".join(lines)  # BOM：Excel 打开中文不乱码
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/invites/export")
def export_invites(
    status: str | None = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Invite)
    if admin.community_id:
        q = q.filter(Invite.community_id == admin.community_id)
    if status:
        q = q.filter(Invite.status == status)
    rows = q.order_by(Invite.id.desc()).limit(5000).all()
    names = _community_name_map(db, [r.community_id for r in rows])
    return _csv_response(
        [[r.code, r.building, r.batch_note, r.status, names.get(r.community_id, ""),
          iso(r.expires_at) if r.expires_at else "", iso(r.created_at)] for r in rows],
        ["邀请码", "楼栋", "批次备注", "状态", "小区", "过期时间", "创建时间"],
        "invites.csv",
    )


@router.get("/users/export")
def export_users(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(User)
    if admin.community_id:
        q = q.filter(User.community_id == admin.community_id)
    rows = q.order_by(User.id.desc()).limit(5000).all()
    names = _community_name_map(db, [r.community_id for r in rows])
    return _csv_response(
        [[r.id, r.nickname, r.building, r.unit, names.get(r.community_id, "未加入"),
          r.role, "是" if r.verified else "否", r.status, r.trades_done, r.violations,
          iso(r.created_at)] for r in rows],
        ["ID", "昵称", "楼栋", "单元", "小区", "角色", "已验证", "状态", "完成交易", "违约", "注册时间"],
        "users.csv",
    )


# ---------- 看板趋势（docs/09 P1-10） ----------

@router.get("/stats/trend")
def stats_trend(
    days: int = Query(default=14, ge=1, le=90),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func

    cid = admin.community_id
    start = utcnow() - timedelta(days=days - 1)
    start_day = start.replace(hour=0, minute=0, second=0, microsecond=0)

    def _daily(model, ts_col, extra=None):
        q = db.query(func.date(ts_col), func.count()).filter(ts_col >= start_day)
        if cid and hasattr(model, "community_id"):
            q = q.filter(model.community_id == cid)
        if extra is not None:
            q = q.filter(extra)
        return {str(d): c for d, c in q.group_by(func.date(ts_col)).all()}

    users_daily = _daily(User, User.created_at)
    items_daily = _daily(Item, Item.created_at)
    trades_daily = _daily(Item, Item.created_at, Item.status == "completed")

    series = []
    for i in range(days):
        day = (start_day + timedelta(days=i)).date().isoformat()
        series.append({
            "date": day,
            "users": users_daily.get(day, 0),
            "items": items_daily.get(day, 0),
            "trades": trades_daily.get(day, 0),
        })
    return ok({"series": series})


# ---------- FAQ 管理（docs/10 Phase 1：仅管理端发布，住户只读+点赞） ----------

def _faq_admin_dto(p: Post, names: dict, publishers: dict) -> dict:
    pub = publishers.get(p.published_by)
    return {
        "id": p.id,
        "title": p.title,
        "content": p.content,
        "pinned": p.pinned,
        "like_count": p.like_count,
        "community_id": p.community_id,
        "community_name": names.get(p.community_id, str(p.community_id)),
        "published_by_name": (pub.name or pub.username) if pub else None,
        "created_at": iso(p.created_at),
    }


@router.get("/faqs")
def admin_list_faqs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    page, page_size = _page_args(page, page_size)
    q = db.query(Post).filter(Post.type == "faq")
    if admin.community_id:
        q = q.filter(Post.community_id == admin.community_id)
    q = q.order_by(Post.pinned.desc(), Post.id.desc())
    rows, total = _paged(q, page, page_size)
    names = _community_name_map(db, [r.community_id for r in rows])
    pubs = {
        a.id: a
        for a in db.query(AdminUser)
        .filter(AdminUser.id.in_([r.published_by for r in rows if r.published_by]))
        .all()
    }
    return _page_payload([_faq_admin_dto(r, names, pubs) for r in rows], total, page, page_size)


@router.post("/faq")
def admin_create_faq(
    payload: AdminFaqCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if admin.community_id:
        community = _own_community(db, admin)
        if community is None:
            raise bad_request("账号未绑定小区，请联系平台")
    else:
        community = db.get(Community, payload.community_id or 0)
        if community is None:
            raise bad_request("请选择目标小区")
    p = Post(
        community_id=community.id,
        type="faq",
        published_by=admin.id,
        title=payload.title.strip(),
        content=payload.content.strip(),
        pinned=payload.pinned,
    )
    db.add(p)
    db.flush()
    _log(db, admin, "create_faq", "post", p.id, p.title)
    db.commit()
    return ok({"id": p.id})


@router.put("/faq/{faq_id}")
def admin_update_faq(
    faq_id: int,
    payload: AdminFaqUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    p = db.get(Post, faq_id)
    if p is None or p.type != "faq":
        raise bad_request("常见问题不存在")
    if admin.community_id and p.community_id != admin.community_id:
        raise forbidden("只能编辑本小区的 FAQ")
    if payload.title is not None:
        p.title = payload.title.strip()
    if payload.content is not None:
        p.content = payload.content.strip()
    if payload.pinned is not None:
        p.pinned = payload.pinned
    _log(db, admin, "update_faq", "post", p.id, p.title)
    db.commit()
    return ok({"ok": True})


@router.delete("/faq/{faq_id}")
def admin_delete_faq(
    faq_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    p = db.get(Post, faq_id)
    if p is None or p.type != "faq":
        raise bad_request("常见问题不存在")
    if admin.community_id and p.community_id != admin.community_id:
        raise forbidden("只能删除本小区的 FAQ")
    _log(db, admin, "delete_faq", "post", p.id, p.title)
    db.delete(p)
    db.commit()
    return ok({"ok": True})
