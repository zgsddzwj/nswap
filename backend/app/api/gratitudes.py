from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models import Gratitude, Item, User
from app.schemas.serialize import ok

router = APIRouter(tags=["gratitudes"])


@router.get("/gratitudes")
def list_gratitudes(
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Gratitude)
        .filter(Gratitude.sec_status == "pass")
        .order_by(Gratitude.id.desc())
        .limit(min(limit, 20))
        .all()
    )
    users = {u.id: u for u in db.query(User).filter(User.id.in_([g.user_id for g in rows]))}
    return ok(
        {
            "list": [
                {
                    "id": g.id,
                    "content": g.content,
                    "to_building": g.to_building,
                    "item_id": g.item_id,
                    "user": {
                        "nickname": (users[g.user_id].nickname if g.user_id in users else "邻居"),
                        "building": (users[g.user_id].building if g.user_id in users else ""),
                    },
                    "created_at": g.created_at.isoformat() + "Z",
                }
                for g in rows
            ]
        }
    )
