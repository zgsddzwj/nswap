"""响应 DTO 构造器（与 docs/04-API契约 一致）。"""

from sqlalchemy.orm import Session

from app.core.time import iso
from app.models import (
    Community,
    Conversation,
    DmMessage,
    Item,
    ItemImage,
    ItemWant,
    Notification,
    Transaction,
    User,
)

ITEM_TYPES = {"sell", "give", "swap", "want"}
CATEGORIES = {"baby", "book", "appliance", "furniture", "clothing", "digital", "sports", "kitchen", "other"}
CONDITIONS = {"brand_new", "like_new", "good", "used", "worn"}


def ok(data=None):
    return {"code": 0, "message": "ok", "data": data}


# ---------- 多社区隐私规则（docs/07 §4.8） ----------
# 唯一规则：viewer 与目标不同小区 → building 输出空串 + 补 community_name。无例外。


def _community_name(db: Session, community_id: int | None) -> str:
    if not community_id:
        return ""
    c = db.get(Community, community_id)
    return c.name if c else ""


def _same_community(viewer: User | None, community_id: int | None) -> bool:
    if viewer is None or community_id is None:
        return False
    return viewer.community_id == community_id


def _building_for(viewer: User | None, owner: User) -> str:
    return owner.building if _same_community(viewer, owner.community_id) else ""


# ---------- user ----------

def user_stats(u: User) -> dict:
    return {
        "sell_done": u.sell_done,
        "give_done": u.give_done,
        "swap_done": u.swap_done,
        "review_good": u.review_good,
        "review_mid": u.review_mid,
        "review_bad": u.review_bad,
        "thanks_count": u.thanks_count,
        "violations": u.violations,
    }


def user_summary(u: User, db: Session | None = None, viewer: User | None = None) -> dict:
    return {
        "id": u.id,
        "nickname": u.nickname,
        "avatar_url": u.avatar_url,
        "building": _building_for(viewer, u) if db is not None else u.building,
        "community_name": _community_name(db, u.community_id) if db is not None else "",
        "verified": u.verified,
        "role": u.role,
        "stats": user_stats(u),
        "created_at": iso(u.created_at),
    }


def me_payload(db: Session, user: User) -> dict:
    community = None
    if user.community_id:
        c = db.get(Community, user.community_id)
        if c:
            community = {
                "id": c.id,
                "name": c.name,
                "city": c.city,
                "district": c.district,
                "verified_count": db.query(User).filter(
                    User.community_id == c.id, User.verified_at.is_not(None)
                ).count(),
                "item_count": db.query(Item).filter(
                    Item.community_id == c.id, Item.status.in_(["on_sale", "reserved"])
                ).count(),
            }
    unread = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.read.is_(False)
    ).count()
    return {"user": _me_user(user), "community": community, "unread_count": unread}


def _me_user(u: User) -> dict:
    return {
        "id": u.id,
        "nickname": u.nickname,
        "avatar_url": u.avatar_url,
        "building": u.building,
        "unit": u.unit,
        "role": u.role,
        "verified": u.verified,
        "status": u.status,
        "stats": user_stats(u),
        "created_at": iso(u.created_at),
    }


# ---------- item ----------

def _visible_images(db: Session, item_ids: list[int]) -> dict[int, list[str]]:
    if not item_ids:
        return {}
    rows = (
        db.query(ItemImage)
        .filter(ItemImage.item_id.in_(item_ids), ItemImage.sec_status.in_(["pass", "pending"]))
        .order_by(ItemImage.item_id, ItemImage.sort_order, ItemImage.id)
        .all()
    )
    result: dict[int, list[str]] = {}
    for r in rows:
        result.setdefault(r.item_id, []).append(r.url)
    return result


def item_card(db: Session, item: Item, images: list[str] | None, viewer: User | None) -> dict:
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "price_cents": item.price_cents,
        "negotiable": item.negotiable,
        "category": item.category,
        "condition": item.condition,
        "building": item.building if _same_community(viewer, item.community_id) else "",
        "community_name": _community_name(db, item.community_id),
        "status": item.status,
        "cover": images[0] if images else None,
        "want_count": item.want_count,
        "view_count": item.view_count,
        "created_at": iso(item.created_at),
        "last_active_at": iso(item.last_active_at),
        "is_mine": viewer is not None and item.user_id == viewer.id,
    }


def item_cards(db: Session, items: list[Item], viewer: User | None) -> list[dict]:
    images_map = _visible_images(db, [i.id for i in items])
    return [item_card(db, i, images_map.get(i.id), viewer) for i in items]


def item_detail(db: Session, item: Item, viewer: User | None) -> dict:
    images = _visible_images(db, [item.id]).get(item.id, [])
    seller = db.get(User, item.user_id)
    data = item_card(db, item, images, viewer)
    data.update(
        {
            "description": item.description,
            "want_desc": item.want_desc,
            "bid_cents": item.bid_cents,
            "images": images,
            "message_count": _message_count(db, item.id),
            "seller": user_summary(seller, db, viewer) if seller else None,
        }
    )
    if viewer is None:
        data.update({"is_favorite": False, "my_want": None, "can_want": False,
                     "can_want_reason": "请先完成小区验证", "active_trade_id": None})
        return data

    from app.models import Favorite  # noqa: 避免循环导入集中

    data["is_favorite"] = (
        db.query(Favorite).filter(Favorite.user_id == viewer.id, Favorite.item_id == item.id).first()
        is not None
    )
    my_want = (
        db.query(ItemWant)
        .filter(
            ItemWant.item_id == item.id,
            ItemWant.user_id == viewer.id,
            ItemWant.status.in_(["pending", "accepted"]),
        )
        .first()
    )
    data["my_want"] = {"id": my_want.id, "status": my_want.status} if my_want else None
    data["can_want"], data["can_want_reason"] = _can_want(item, viewer, my_want)
    active_trade = (
        db.query(Transaction)
        .filter(
            Transaction.item_id == item.id,
            Transaction.status.in_(["pending", "arranged"]),
        )
        .first()
    )
    data["active_trade_id"] = active_trade.id if active_trade else None
    return data


def _message_count(db: Session, item_id: int) -> int:
    from app.models import ItemMessage

    return (
        db.query(ItemMessage)
        .filter(ItemMessage.item_id == item_id, ItemMessage.status == "visible")
        .count()
    )


def _can_want(item: Item, viewer: User, my_want) -> tuple[bool, str]:
    if viewer.verified_at is None:
        return False, "请先完成小区验证"
    if item.user_id == viewer.id:
        return False, "这是你自己发布的"
    if item.status != "on_sale":
        return False, "该物品当前不接受新意向"
    if my_want is not None:
        return False, "你已提交过意向，请等待回应"
    return True, ""


# ---------- trade ----------

def trade_dto(db: Session, trade: Transaction, viewer: User) -> dict:
    from app.models import Gratitude, Review

    item = db.get(Item, trade.item_id)
    my_role = "owner" if trade.owner_id == viewer.id else "other"
    counterpart_id = trade.other_id if my_role == "owner" else trade.owner_id
    counterpart = db.get(User, counterpart_id)
    owner_user = db.get(User, trade.owner_id)
    other_user = db.get(User, trade.other_id)
    cross_community = bool(
        owner_user and other_user and owner_user.community_id != other_user.community_id
    )
    want = db.get(ItemWant, trade.want_id) if trade.want_id else None
    reviews = db.query(Review).filter(Review.transaction_id == trade.id).all()
    my_review = next((r for r in reviews if r.from_user_id == viewer.id), None)
    grat = db.query(Gratitude).filter(Gratitude.transaction_id == trade.id).first()
    cover = _visible_images(db, [item.id]).get(item.id, []) if item else []
    return {
        "id": trade.id,
        "status": trade.status,
        "item": (
            {
                "id": item.id,
                "title": item.title,
                "cover": cover[0] if cover else None,
                "type": item.type,
                "status": item.status,
            }
            if item
            else None
        ),
        "counterpart": user_summary(counterpart, db, viewer) if counterpart else None,
        "my_role": my_role,
        "cross_community": cross_community,
        "want": (
            {"message": want.message, "bid_cents": want.bid_cents, "swap_offer": want.swap_offer}
            if want
            else None
        ),
        "place_method": trade.place_method,
        "meet_time": iso(trade.meet_time),
        "place_note": trade.place_note,
        "owner_confirmed": trade.owner_confirmed,
        "other_confirmed": trade.other_confirmed,
        "my_confirmed": trade.owner_confirmed if my_role == "owner" else trade.other_confirmed,
        "cancel_reason": trade.cancel_reason,
        "reviews": [
            {"from_user_id": r.from_user_id, "rating": r.rating, "content": r.content}
            for r in reviews
        ],
        "my_review": (
            {"rating": my_review.rating, "content": my_review.content} if my_review else None
        ),
        "gratitude": {"content": grat.content} if grat else None,
        "created_at": iso(trade.created_at),
        "completed_at": iso(trade.completed_at),
    }


# ---------- chat ----------

def conversation_dto(db: Session, conv: Conversation, viewer: User) -> dict:
    item = db.get(Item, conv.item_id)
    counterpart_id = conv.user_b if conv.user_a == viewer.id else conv.user_a
    counterpart = db.get(User, counterpart_id)
    last = (
        db.query(DmMessage)
        .filter(DmMessage.conversation_id == conv.id)
        .order_by(DmMessage.id.desc())
        .first()
    )
    cover = _visible_images(db, [item.id]).get(item.id, []) if item else []
    return {
        "id": conv.id,
        "item": (
            {"id": item.id, "title": item.title, "cover": cover[0] if cover else None,
             "type": item.type, "status": item.status}
            if item
            else None
        ),
        "counterpart": user_summary(counterpart, db, viewer) if counterpart else None,
        "last_message": (
            {"content": last.content, "created_at": iso(last.created_at), "sender_id": last.sender_id}
            if last
            else None
        ),
        "updated_at": iso(conv.last_message_at or conv.created_at),
    }


def notification_dto(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "content": n.content,
        "payload": n.payload or {},
        "read": n.read,
        "created_at": iso(n.created_at),
    }
