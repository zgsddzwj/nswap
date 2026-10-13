from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_verified_user
from app.core.errors import not_found
from app.models import Favorite, Item, User
from app.schemas.serialize import item_cards, ok

router = APIRouter(tags=["favorites"])


@router.post("/items/{item_id}/favorite")
def add_favorite(
    item_id: int,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    if db.get(Item, item_id) is None:
        raise not_found()
    existing = (
        db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.item_id == item_id).first()
    )
    if existing is None:
        db.add(Favorite(user_id=user.id, item_id=item_id))
        db.commit()
    return ok({"ok": True})


@router.delete("/items/{item_id}/favorite")
def remove_favorite(
    item_id: int,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.item_id == item_id).delete()
    db.commit()
    return ok({"ok": True})


@router.get("/favorites")
def list_favorites(
    cursor: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Favorite).filter(Favorite.user_id == user.id).order_by(Favorite.id.desc())
    if cursor:
        q = q.filter(Favorite.id < cursor)
    favs = q.limit(limit + 1).all()
    next_cursor = favs[-1].id if len(favs) > limit else None
    favs = favs[:limit]
    items = [db.get(Item, f.item_id) for f in favs]
    items = [i for i in items if i is not None]
    return ok({"list": item_cards(db, items, user), "next_cursor": next_cursor})
