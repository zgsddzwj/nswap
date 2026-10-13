from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import (
    gen_invite_code,
    get_active_user,
    get_current_user,
    get_db,
)
from app.core.errors import bad_request, conflict, not_found, too_many
from app.core.time import utcnow
from app.models import Community, Invite, User, VerifyRequest, Vouch
from app.schemas import JoinRequest, ManualApplyRequest
from app.schemas.serialize import me_payload, ok

router = APIRouter(tags=["community"])


def get_default_community(db: Session) -> Community:
    c = db.query(Community).order_by(Community.id).first()
    if c is None:
        raise not_found("社区未初始化，请联系管理员")
    return c


@router.get("/community/info")
def community_info(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    c = get_default_community(db)
    buildings = [
        r[0]
        for r in db.query(Invite.building).filter(Invite.building != "").distinct().all()
    ]
    for u in db.query(User.building).filter(User.building != "").distinct().all():
        if u[0] not in buildings:
            buildings.append(u[0])
    return ok(
        {
            "id": c.id,
            "name": c.name,
            "address": c.address,
            "verified_count": db.query(User)
            .filter(User.community_id == c.id, User.verified_at.is_not(None))
            .count(),
            "item_count": 0,
            "buildings": sorted(buildings),
        }
    )


@router.post("/community/join")
def join_by_code(
    payload: JoinRequest,
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    if user.verified_at is not None:
        raise conflict("你已完成小区验证")
    invite = (
        db.query(Invite)
        .filter(Invite.code == payload.code.strip().upper())
        .with_for_update()
        .first()
    )
    if invite is None or invite.status != "active":
        raise not_found("邀请码不存在或已失效")
    if invite.expires_at and invite.expires_at < utcnow():
        raise not_found("邀请码已过期，请联系发放人")
    if invite.used_by is not None:
        raise not_found("邀请码已被使用")

    community = db.get(Community, invite.community_id)
    user.community_id = invite.community_id
    user.building = invite.building or user.building
    user.verified_at = utcnow()
    invite.status = "used"
    invite.used_by = user.id
    invite.used_at = utcnow()
    if invite.kind == "vouch" and invite.created_by:
        db.add(
            Vouch(
                community_id=invite.community_id,
                voucher_id=invite.created_by,
                vouchee_id=user.id,
                invite_id=invite.id,
            )
        )
    db.commit()
    return ok(me_payload(db, user))


@router.post("/community/vouch-invite")
def create_vouch_invite(
    user: User = Depends(get_active_user), db: Session = Depends(get_db)
):
    """老住户担保码：已验证 + 完成≥1笔交易 + 名下无未用担保码。"""
    if user.verified_at is None:
        raise bad_request("请先完成小区验证")
    if user.trades_done < 1:
        raise bad_request("完成一笔交换后即可为新邻居担保")
    existing = (
        db.query(Invite)
        .filter(Invite.kind == "vouch", Invite.created_by == user.id, Invite.status == "active")
        .first()
    )
    if existing:
        raise too_many("你已有一个未使用的担保码，用掉后再生成")
    code = gen_invite_code("DB")
    invite = Invite(
        community_id=user.community_id,
        code=code,
        kind="vouch",
        building=user.building,
        created_by=user.id,
        expires_at=utcnow() + timedelta(days=14),
    )
    db.add(invite)
    db.commit()
    return ok({"code": code, "expires_at": invite.expires_at.isoformat() + "Z"})


@router.post("/community/manual-apply")
def manual_apply(
    payload: ManualApplyRequest,
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    if user.verified_at is not None:
        raise conflict("你已完成小区验证")
    pending = (
        db.query(VerifyRequest)
        .filter(VerifyRequest.user_id == user.id, VerifyRequest.status == "pending")
        .first()
    )
    if pending:
        raise conflict("你已提交过申请，请耐心等待管理员审核")
    community = get_default_community(db)
    db.add(
        VerifyRequest(
            user_id=user.id,
            community_id=community.id,
            building=payload.building,
            unit=payload.unit,
            proof_image=payload.proof_image,
        )
    )
    db.commit()
    return ok({"status": "pending"})
