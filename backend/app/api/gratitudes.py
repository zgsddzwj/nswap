from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models import Gratitude, Item, User
from app.schemas.serialize import _community_name, ok

router = APIRouter(tags=["gratitudes"])


@router.get("/gratitudes")
def list_gratitudes(
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Gratitude)
        .filter(
            Gratitude.sec_status == "pass",
            # 多社区：首页感谢区仅展示本小区（跨小区感谢对邻里氛围无意义）
            Gratitude.community_id == user.community_id,
        )
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
                        "community_name": (
                            _community_name(db, g.community_id) if g.user_id in users else ""
                        ),
                    },
                    "created_at": g.created_at.isoformat() + "Z",
                }
                for g in rows
            ]
        }
    )
