from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_verified_user
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
    if payload.target_type not in ("item", "message", "user"):
        raise bad_request("举报对象类型不合法")
    if payload.target_type == "item" and db.get(Item, payload.target_id) is None:
        raise not_found("举报对象不存在")
    if payload.target_type == "message" and db.get(ItemMessage, payload.target_id) is None:
        raise not_found("举报对象不存在")
    if payload.target_type == "user" and db.get(User, payload.target_id) is None:
        raise not_found("举报对象不存在")
    db.add(
        Report(
            community_id=user.community_id,
            reporter_id=user.id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason=payload.reason.strip(),
            detail=payload.detail,
        )
    )
    db.commit()
    return ok({"ok": True})
