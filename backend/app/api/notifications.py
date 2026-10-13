from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_verified_user
from app.core.errors import bad_request
from app.models import MsgSubscription, Notification, User
from app.schemas import ReadRequest, SubscribeRequest
from app.schemas.serialize import me_payload, notification_dto, ok

router = APIRouter(tags=["notifications"])

TEMPLATE_KEYS = {"want", "accepted", "confirm", "review"}


@router.get("/notifications")
def list_notifications(
    unread_only: bool = Query(default=False),
    cursor: int | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.read.is_(False))
    q = q.order_by(Notification.id.desc())
    if cursor:
        q = q.filter(Notification.id < cursor)
    rows = q.limit(limit + 1).all()
    next_cursor = rows[-1].id if len(rows) > limit else None
    rows = rows[:limit]
    return ok(
        {"list": [notification_dto(n) for n in rows], "next_cursor": next_cursor}
    )


@router.post("/notifications/read")
def mark_read(
    payload: ReadRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.ids:
        db.query(Notification).filter(
            Notification.user_id == user.id, Notification.id.in_(payload.ids)
        ).update({"read": True}, synchronize_session=False)
    db.commit()
    return ok({"ok": True})


@router.post("/notifications/read-all")
def mark_all_read(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.read.is_(False)
    ).update({"read": True}, synchronize_session=False)
    db.commit()
    return ok({"ok": True})


@router.post("/notifications/subscribe")
def record_subscribe(
    payload: SubscribeRequest,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    if payload.template_key not in TEMPLATE_KEYS:
        raise bad_request("模板类型不合法")
    db.add(
        MsgSubscription(user_id=user.id, template_key=payload.template_key)
    )
    db.commit()
    return ok({"ok": True})


@router.get("/me/unread")
def unread_count(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return ok({"unread_count": me_payload(db, user)["unread_count"]})
