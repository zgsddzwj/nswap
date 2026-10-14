"""邻里墙与 FAQ（docs/10）：Phase 1 = FAQ（管理端发布，住户只读+点赞）。

type=topic（住户发帖）为 Phase 2，NEIGHBOR_WALL_ENABLED 控制，本期不开放。
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_active_user, get_db
from app.core.errors import bad_request
from app.core.time import iso, utcnow
from app.models import Post, PostLike, User
from app.schemas.serialize import ok
from app.services.rate_limit import check_rate

router = APIRouter(tags=["faq"])

LIKE_RATE_LIMIT = 30  # 每用户每分钟点赞次数


def _faq_dto(p: Post, names: dict, liked_ids: set[int]) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "content": p.content,
        "pinned": p.pinned,
        "like_count": p.like_count,
        "my_like": p.id in liked_ids,
        "created_at": iso(p.created_at),
    }


@router.get("/faqs")
def list_faqs(
    cursor: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """本小区 FAQ 列表：置顶优先 → 最新；住户只读（游客/未加入返回空列表）。"""
    if not user.community_id:
        return ok({"list": [], "next_cursor": None})
    q = db.query(Post).filter(
        Post.community_id == user.community_id,
        Post.type == "faq",
        Post.status == "published",
        Post.sec_status == "pass",
    )
    if cursor:
        q = q.filter(Post.id < cursor)
    rows = q.order_by(Post.pinned.desc(), Post.id.desc()).limit(limit).all()
    liked_ids: set[int] = set()
    if rows:
        liked_rows = (
            db.query(PostLike.post_id)
            .filter(
                PostLike.user_id == user.id,
                PostLike.post_id.in_([p.id for p in rows]),
            )
            .all()
        )
        liked_ids = {r[0] for r in liked_rows}
    from app.schemas.serialize import community_names

    names = community_names(db, [p.community_id for p in rows])
    return ok(
        {
            "list": [_faq_dto(p, names, liked_ids) for p in rows],
            "next_cursor": rows[-1].id if len(rows) == limit else None,
        }
    )


def _get_published_faq(db: Session, faq_id: int, user: User) -> Post:
    p = db.get(Post, faq_id)
    if (
        p is None
        or p.type != "faq"
        or p.status != "published"
        or p.sec_status != "pass"
        or p.community_id != user.community_id
    ):
        raise bad_request("常见问题不存在")
    return p


@router.post("/faqs/{faq_id}/like")
def like_faq(faq_id: int, user: User = Depends(get_active_user), db: Session = Depends(get_db)):
    faq = _get_published_faq(db, faq_id, user)
    if not check_rate(f"faq_like:{user.id}", LIKE_RATE_LIMIT, 60):
        from app.core.errors import too_many

        raise too_many("操作过于频繁，请稍后再试")
    exists = (
        db.query(PostLike)
        .filter(PostLike.post_id == faq.id, PostLike.user_id == user.id)
        .first()
    )
    if exists is None:
        db.add(PostLike(post_id=faq.id, user_id=user.id))
        faq.like_count += 1
        db.commit()
    return ok({"liked": True, "like_count": faq.like_count})


@router.delete("/faqs/{faq_id}/like")
def unlike_faq(faq_id: int, user: User = Depends(get_active_user), db: Session = Depends(get_db)):
    faq = _get_published_faq(db, faq_id, user)
    like = (
        db.query(PostLike)
        .filter(PostLike.post_id == faq.id, PostLike.user_id == user.id)
        .first()
    )
    if like:
        db.delete(like)
        faq.like_count = max(0, faq.like_count - 1)
        db.commit()
    return ok({"liked": False, "like_count": faq.like_count})
