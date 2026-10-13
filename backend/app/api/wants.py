from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_verified_user
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.time import iso, utcnow
from app.models import Conversation, Item, ItemWant, Notification, Transaction, User
from app.schemas import WantAction, WantCreate
from app.schemas.serialize import ok, user_summary
from app.services.notify import push_notification, send_subscribe
from app.services.sec_check import check_text

router = APIRouter(tags=["wants"])


def _get_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise not_found()
    return item


@router.post("/items/{item_id}/wants")
def create_want(
    item_id: int,
    payload: WantCreate,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    item = _get_item(db, item_id)
    if item.user_id == user.id:
        raise bad_request("不能对自己发布的物品表达意向")
    if item.status != "on_sale":
        raise conflict("该物品当前不接受新意向")
    existing = (
        db.query(ItemWant)
        .filter(
            ItemWant.item_id == item.id,
            ItemWant.user_id == user.id,
            ItemWant.status.in_(["pending", "accepted"]),
        )
        .first()
    )
    if existing:
        raise conflict("你已提交过意向，请等待回应")
    if payload.bid_cents is not None and payload.bid_cents <= 0:
        raise bad_request("出价不合法")

    check_text(db, payload.message, user, "text", None)
    want = ItemWant(
        item_id=item.id,
        user_id=user.id,
        message=payload.message.strip(),
        bid_cents=payload.bid_cents,
        swap_offer=payload.swap_offer,
        status="pending",
    )
    db.add(want)
    item.want_count += 1
    item.last_active_at = utcnow()

    owner = db.get(User, item.user_id)
    push_notification(
        db,
        owner.id,
        "want_received",
        "收到新意向",
        f"{user.nickname or '一位邻居'}想要「{item.title}」",
        {"item_id": item.id},
    )
    send_subscribe(
        db,
        owner,
        "want",
        {"thing1": {"value": item.title[:20]}, "thing2": {"value": (user.nickname or "邻居")[:20]}},
        page=f"pages/detail/index?id={item.id}",
    )
    db.flush()
    # 回填 want_id 供通知直达意向管理页
    notif = (
        db.query(Notification)
        .filter(Notification.user_id == owner.id)
        .order_by(Notification.id.desc())
        .first()
    )
    if notif and notif.type == "want_received":
        notif.payload = {"item_id": item.id, "want_id": want.id}
    db.commit()
    return ok({"id": want.id, "status": want.status})


@router.get("/items/{item_id}/wants")
def list_wants(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_item(db, item_id)
    if item.user_id != user.id and user.role != "admin":
        raise forbidden("只有物品主人可以查看意向")
    wants = (
        db.query(ItemWant)
        .filter(ItemWant.item_id == item.id)
        .order_by(ItemWant.created_at.desc())
        .all()
    )
    users = {u.id: u for u in db.query(User).filter(User.id.in_([w.user_id for w in wants]))}
    return ok(
        {
            "list": [
                {
                    "id": w.id,
                    "message": w.message,
                    "bid_cents": w.bid_cents,
                    "swap_offer": w.swap_offer,
                    "status": w.status,
                    "created_at": iso(w.created_at),
                    "user": user_summary(users[w.user_id], db, user) if w.user_id in users else None,
                }
                for w in wants
            ]
        }
    )


@router.put("/wants/{want_id}")
def handle_want(
    want_id: int,
    payload: WantAction,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    want = db.get(ItemWant, want_id)
    if want is None:
        raise not_found("意向不存在")
    item = db.get(Item, want.item_id)
    if item is None:
        raise not_found()
    if item.user_id != user.id:
        raise forbidden("只有物品主人可以处理意向")
    if want.status != "pending":
        raise conflict("该意向已处理过")

    if payload.action == "reject":
        want.status = "rejected"
        push_notification(
            db,
            want.user_id,
            "want_rejected",
            "意向未通过",
            f"「{item.title}」的主人选择了其他邻居",
            {"item_id": item.id},
        )
        db.commit()
        return ok({"ok": True})
    if payload.action != "accept":
        raise bad_request("action 仅支持 accept/reject")

    # 接受意向：物品转已预约（停止新意向）、建会话、建交易单
    if item.status != "on_sale":
        raise conflict("物品当前状态不可接受意向")
    want.status = "accepted"
    item.status = "reserved"
    item.last_active_at = utcnow()

    conv = (
        db.query(Conversation)
        .filter(
            Conversation.item_id == item.id,
            Conversation.user_a == item.user_id,
            Conversation.user_b == want.user_id,
        )
        .first()
    )
    if conv is None:
        conv = Conversation(
            community_id=item.community_id,
            item_id=item.id,
            user_a=item.user_id,
            user_b=want.user_id,
            want_id=want.id,
        )
        db.add(conv)
        db.flush()

    trade = Transaction(
        community_id=item.community_id,
        item_id=item.id,
        want_id=want.id,
        conversation_id=conv.id,
        owner_id=item.user_id,
        other_id=want.user_id,
        status="pending",
    )
    db.add(trade)
    db.flush()

    wanter = db.get(User, want.user_id)
    push_notification(
        db,
        wanter.id,
        "want_accepted",
        "你的意向被选中了",
        f"「{item.title}」的主人选择了你，去聊聊交接方式吧",
        {"item_id": item.id, "trade_id": trade.id},
    )
    send_subscribe(
        db,
        wanter,
        "accepted",
        {"thing1": {"value": item.title[:20]}},
        page=f"pages/trade/index?id={trade.id}",
    )
    db.commit()
    return ok({"trade_id": trade.id, "conversation_id": conv.id})


@router.delete("/wants/{want_id}")
def withdraw_want(
    want_id: int,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    want = db.get(ItemWant, want_id)
    if want is None:
        raise not_found("意向不存在")
    if want.user_id != user.id:
        raise forbidden("只能撤回自己的意向")
    if want.status != "pending":
        raise conflict("该意向已被处理，不能撤回")
    want.status = "rejected"
    item = db.get(Item, want.item_id)
    if item and item.want_count > 0:
        item.want_count -= 1
    db.commit()
    return ok({"ok": True})
