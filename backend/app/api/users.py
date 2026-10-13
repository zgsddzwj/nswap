from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import not_found
from app.models import Item, User
from app.schemas.serialize import item_cards, ok, user_summary

router = APIRouter(tags=["users"])


@router.get("/users/{user_id}")
def get_profile(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
            "user": user_summary(target, db, user),
            "items": item_cards(db, active_items, user),
        }
    )
