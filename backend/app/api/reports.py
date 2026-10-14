from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_verified_user
from app.services.rate_limit import check_rate
from app.core.errors import bad_request, not_found
from app.models import Item, ItemMessage, Report, User
from app.schemas import ReportCreate
from app.schemas.serialize import ok

router = APIRouter(tags=["reports"])


@router.post("/reports")
def create_report(
    payload: ReportCreate,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    if not check_rate(f"report:{user.id}", 5, 60):
        from app.core.errors import too_many

        raise too_many("操作过于频繁，请稍后再试")

    if payload.target_type not in ("item", "message", "user"):
        raise bad_request("举报对象类型不合法")
    # 归属 = 被举报目标所属小区（谁的内容谁的小区处置，docs/07 §4.4）；超管全局兜底
    target_community_id: int | None = None
    if payload.target_type == "item":
        target = db.get(Item, payload.target_id)
        if target is None:
            raise not_found("举报对象不存在")
        target_community_id = target.community_id
    elif payload.target_type == "message":
        msg = db.get(ItemMessage, payload.target_id)
        if msg is None:
            raise not_found("举报对象不存在")
        item = db.get(Item, msg.item_id)
        target_community_id = item.community_id if item else None
    else:
        target = db.get(User, payload.target_id)
        if target is None:
            raise not_found("举报对象不存在")
        target_community_id = target.community_id
    db.add(
        Report(
            community_id=target_community_id,
            reporter_id=user.id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason=payload.reason.strip(),
            detail=payload.detail,
        )
    )
    db.commit()
    return ok({"ok": True})
