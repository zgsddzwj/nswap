from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_verified_user
from app.core.errors import not_found
from app.core.time import iso, utcnow
from app.models import Item, ItemMessage, User
from app.schemas import ItemMessageCreate
from app.schemas.serialize import community_names, ok, user_summary
from app.services.notify import push_notification
from app.services.sec_check import check_text

router = APIRouter(tags=["item-messages"])


@router.get("/items/{item_id}/messages")
def list_messages(
    item_id: int,
    cursor: int | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)
    if item is None:
        raise not_found()
    q = db.query(ItemMessage).filter(
        ItemMessage.item_id == item_id, ItemMessage.status == "visible"
    )
    is_privileged = user.role == "admin" or item.user_id == user.id
    if not is_privileged:
        q = q.filter(ItemMessage.sec_status == "pass")
    q = q.order_by(ItemMessage.id.desc())
    if cursor:
        q = q.filter(ItemMessage.id < cursor)
    rows = q.limit(limit + 1).all()
    next_cursor = rows[-1].id if len(rows) > limit else None
    rows = rows[:limit]
    users = {u.id: u for u in db.query(User).filter(User.id.in_([m.user_id for m in rows]))}
    names = community_names(db, [u.community_id for u in users.values()])  # 循环外一次查询
    return ok(
        {
            "list": [
                {
                    "id": m.id,
                    "content": m.content,
                    "sec_status": m.sec_status,
                    "created_at": iso(m.created_at),
                    "user": user_summary(users[m.user_id], db, user, names)
                    if m.user_id in users else None,
                }
                for m in reversed(rows)
            ],
            "next_cursor": next_cursor,
        }
    )


@router.post("/items/{item_id}/messages")
def create_message(
    item_id: int,
    payload: ItemMessageCreate,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)
    if item is None:
        raise not_found()
    sec_status = check_text(db, payload.content, user, "text", None)
    msg = ItemMessage(
        item_id=item_id,
        user_id=user.id,
        content=payload.content.strip(),
        sec_status=sec_status,
    )
    db.add(msg)
    item.last_active_at = utcnow()
    if item.user_id != user.id:
        push_notification(
            db,
            item.user_id,
            "item_message",
            "物品收到新留言",
            f"{user.nickname or '一位邻居'}在「{item.title}」留言",
            {"item_id": item.id},
        )
    db.commit()
    return ok(
        {
            "id": msg.id,
            "content": msg.content,
            "sec_status": msg.sec_status,
            "created_at": iso(msg.created_at),
            "user": user_summary(user, db, user),
        }
    )
