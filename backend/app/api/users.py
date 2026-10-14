from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import forbidden, not_found
from app.models import Item, User
from app.schemas.serialize import community_names, item_cards, ok, user_summary

router = APIRouter(tags=["users"])


@router.get("/users/{user_id}")
def get_profile(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.community_id:
        raise forbidden("完成小区验证后查看内容")
    target = db.get(User, user_id)
    if target is None:
        raise not_found("用户不存在")
    active_items = (
        db.query(Item)
        .filter(
            Item.user_id == target.id,
            Item.status.in_(["on_sale", "reserved"]),
        )
        .order_by(Item.last_active_at.desc())
        .limit(20)
        .all()
    )
    return ok(
        {
            "user": user_summary(target, db, user, community_names(db, [target.community_id])),
            "items": item_cards(db, active_items, user),
        }
    )
