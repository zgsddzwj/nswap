"""物业公告：仅本小区住户可见（小程序只读，管理后台发布/删除）。docs/07 §4.6"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.time import iso
from app.schemas.serialize import ok
from app.models import Announcement, User

router = APIRouter(tags=["announcements"])


@router.get("/announcements")
def list_announcements(
    cursor: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.community_id:
        return ok({"list": [], "next_cursor": None})
    q = db.query(Announcement).filter(Announcement.community_id == user.community_id)
    if cursor:
        q = q.filter(Announcement.id < cursor)
    rows = q.order_by(Announcement.pinned.desc(), Announcement.id.desc()).limit(limit).all()
    next_cursor = rows[-1].id if len(rows) == limit else None
    return ok(
        {
            "list": [
                {"id": a.id, "title": a.title, "content": a.content, "created_at": iso(a.created_at)}
                for a in rows
            ],
            "next_cursor": next_cursor,
        }
    )
