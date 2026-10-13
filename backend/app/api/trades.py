"""交易闭环：约定 → 双向确认 → 互评 → 感谢。状态迁移集中守护。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_verified_user
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.time import parse_iso, utcnow
from app.models import Gratitude, Item, ItemWant, Review, Transaction, User
from app.schemas import ArrangeRequest, CancelRequest, GratitudeCreate, ReviewCreate
from app.schemas.serialize import ok, trade_dto
from app.services import credit
from app.services.notify import push_notification, send_subscribe
from app.services.sec_check import check_text

router = APIRouter(tags=["trades"])

PLACE_METHODS = {"face": "当面见面", "porch": "放门口自取", "lobby": "物业前台代交"}


def _get_trade(db: Session, trade_id: int, user: User) -> Transaction:
    trade = db.get(Transaction, trade_id)
    if trade is None:
        raise not_found("交易不存在")
    if user.id not in (trade.owner_id, trade.other_id) and user.role != "admin":
        raise forbidden("你不是交易参与方")
    return trade


@router.get("/trades")
def list_trades(
    status: str = Query(default="all"),
    cursor: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if status not in ("all", "ongoing", "completed", "cancelled"):
        raise bad_request("status 参数不合法")
    q = db.query(Transaction).filter(
        (Transaction.owner_id == user.id) | (Transaction.other_id == user.id)
    )
    if status == "ongoing":
        q = q.filter(Transaction.status.in_(["pending", "arranged"]))
    else:
        q = q.filter(Transaction.status == status)
    q = q.order_by(Transaction.id.desc())
    if cursor:
        q = q.filter(Transaction.id < cursor)
    trades = q.limit(limit + 1).all()
    next_cursor = trades[-1].id if len(trades) > limit else None
    trades = trades[:limit]
    return ok({"list": [trade_dto(db, t, user) for t in trades], "next_cursor": next_cursor})


@router.get("/trades/{trade_id}")
def get_trade(
    trade_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trade = _get_trade(db, trade_id, user)
    return ok(trade_dto(db, trade, user))


# PATCH 为 API 契约方法；PUT 别名供小程序端使用（wx.request 不支持 PATCH）
@router.put("/trades/{trade_id}/arrange")
@router.patch("/trades/{trade_id}/arrange")
def arrange_trade(
    trade_id: int,
    payload: ArrangeRequest,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    trade = _get_trade(db, trade_id, user)
    if trade.status not in ("pending", "arranged"):
        raise conflict("交易已结束，不能再约定")
    # 跨小区交易仅允许当面交接（放门口/物业前台对外小区住户不可行，docs/07 §4.5）
    owner_user = db.get(User, trade.owner_id)
    other_user = db.get(User, trade.other_id)
    if (
        owner_user
        and other_user
        and owner_user.community_id != other_user.community_id
        and payload.place_method != "face"
    ):
        raise bad_request("跨小区交换请选择当面交接")

    if payload.place_method not in PLACE_METHODS:
        raise bad_request("交接方式不合法")
    meet_time = parse_iso(payload.meet_time)
    if meet_time is None:
        raise bad_request("请填写约定时间")

    trade.place_method = payload.place_method
    trade.meet_time = meet_time
    trade.place_note = payload.place_note
    trade.status = "arranged"

    counterpart_id = trade.other_id if user.id == trade.owner_id else trade.owner_id
    counterpart = db.get(User, counterpart_id)
    item = db.get(Item, trade.item_id)
    push_notification(
        db,
        counterpart_id,
        "trade_arranged",
        "交接约定更新",
        f"「{item.title if item else '物品'}」约定：{PLACE_METHODS[payload.place_method]}，请查看详情",
        {"trade_id": trade.id},
    )
    send_subscribe(
        db,
        counterpart,
        "confirm",
        {"thing1": {"value": (item.title if item else "物品")[:20]}},
        page=f"pages/trade/index?id={trade.id}",
    )
    db.commit()
    return ok(trade_dto(db, trade, user))


@router.put("/trades/{trade_id}/confirm")
def confirm_trade(
    trade_id: int,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    trade = _get_trade(db, trade_id, user)
    if trade.status not in ("pending", "arranged"):
        raise conflict("交易已结束")
    if user.id == trade.owner_id:
        if trade.owner_confirmed:
            raise conflict("你已确认过")
        trade.owner_confirmed = True
    else:
        if trade.other_confirmed:
            raise conflict("你已确认过")
        trade.other_confirmed = True

    counterpart_id = trade.other_id if user.id == trade.owner_id else trade.owner_id
    counterpart = db.get(User, counterpart_id)

    if trade.owner_confirmed and trade.other_confirmed:
        # 双方确认 → 交易完成
        trade.status = "completed"
        trade.completed_at = utcnow()
        item = db.get(Item, trade.item_id)
        owner = db.get(User, trade.owner_id)
        other = db.get(User, trade.other_id)
        if item is not None:
            item.status = "completed"
            item.last_active_at = utcnow()
        if trade.want_id:
            want = db.get(ItemWant, trade.want_id)
            if want:
                want.status = "done"
        credit.on_trade_completed(db, trade, item, owner, other)
        for uid in (trade.owner_id, trade.other_id):
            push_notification(
                db,
                uid,
                "trade_completed",
                "交易完成，去评价吧",
                f"「{item.title if item else '物品'}」交接完成，别忘了给对方一个评价",
                {"trade_id": trade.id},
            )
        send_subscribe(
            db,
            counterpart,
            "confirm",
            {"thing1": {"value": "交易完成"}},
            page=f"pages/review/index?id={trade.id}",
        )
    else:
        item = db.get(Item, trade.item_id)
        push_notification(
            db,
            counterpart_id,
            "trade_confirmed",
            "对方已确认完成",
            f"「{item.title if item else '物品'}」对方已确认，待你确认后交易完成",
            {"trade_id": trade.id},
        )
        send_subscribe(
            db,
            counterpart,
            "confirm",
            {"thing1": {"value": (item.title if item else "物品")[:20]}},
            page=f"pages/trade/index?id={trade.id}",
        )
    db.commit()
    return ok(trade_dto(db, trade, user))


@router.put("/trades/{trade_id}/cancel")
def cancel_trade(
    trade_id: int,
    payload: CancelRequest,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    trade = _get_trade(db, trade_id, user)
    if trade.status not in ("pending", "arranged"):
        raise conflict("交易已结束，不能取消")
    item = db.get(Item, trade.item_id)
    trade.status = "cancelled"
    trade.cancelled_by = user.id
    trade.cancel_reason = payload.reason
    if item is not None:
        item.status = "on_sale"  # 回滚在售，其他 pending 意向可继续挑选
        item.last_active_at = utcnow()
    if trade.want_id:
        want = db.get(ItemWant, trade.want_id)
        if want:
            # 物品方取消 → 意向回到待选；意向方取消 → 意向作废
            want.status = "pending" if user.id == trade.owner_id else "rejected"
    credit.on_violation(db, user)  # 取消方记一次违约

    counterpart_id = trade.other_id if user.id == trade.owner_id else trade.owner_id
    push_notification(
        db,
        counterpart_id,
        "trade_cancelled",
        "交易已取消",
        f"「{item.title if item else '物品'}」的交易已被取消",
        {"trade_id": trade.id},
    )
    db.commit()
    return ok(trade_dto(db, trade, user))


@router.post("/trades/{trade_id}/review")
def review_trade(
    trade_id: int,
    payload: ReviewCreate,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    trade = _get_trade(db, trade_id, user)
    if trade.status != "completed":
        raise conflict("交易完成后才能评价")
    existing = (
        db.query(Review)
        .filter(Review.transaction_id == trade.id, Review.from_user_id == user.id)
        .first()
    )
    if existing:
        raise conflict("你已评价过")
    content = (payload.content or "").strip()
    if content:
        check_text(db, content, user, "text", trade.id)

    to_user_id = trade.other_id if user.id == trade.owner_id else trade.owner_id
    to_user = db.get(User, to_user_id)
    review = Review(
        transaction_id=trade.id,
        from_user_id=user.id,
        to_user_id=to_user_id,
        rating=payload.rating,
        content=content or None,
    )
    db.add(review)
    credit.on_review(db, review, to_user)
    push_notification(
        db,
        to_user_id,
        "review_received",
        "收到新评价",
        f"{user.nickname or '邻居'}给你评了{'满意' if payload.rating == 3 else '一般' if payload.rating == 2 else '不满意'}",
        {"trade_id": trade.id},
    )
    send_subscribe(
        db,
        to_user,
        "review",
        {"thing1": {"value": user.nickname or "邻居"}},
        page=f"pages/my-trades/index",
    )
    db.commit()
    return ok(trade_dto(db, trade, user))


@router.post("/trades/{trade_id}/gratitude")
def post_gratitude(
    trade_id: int,
    payload: GratitudeCreate,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    trade = _get_trade(db, trade_id, user)
    if trade.status != "completed":
        raise conflict("交易完成后才能发布感谢")
    item = db.get(Item, trade.item_id)
    # 收受方发布：sell/give/swap 物品为意向方，want 物品为求购者（owner）
    receiver_id = trade.owner_id if (item and item.type == "want") else trade.other_id
    if user.id != receiver_id:
        raise forbidden("只有收受方可以发布感谢")
    provider_id = trade.other_id if receiver_id == trade.owner_id else trade.owner_id
    provider = db.get(User, provider_id)
    existing = (
        db.query(Gratitude).filter(Gratitude.transaction_id == trade.id).first()
    )
    if existing:
        raise conflict("该交易已发布过感谢")

    check_text(db, payload.content, user, "text", trade.id)
    grat = Gratitude(
        community_id=trade.community_id,
        user_id=user.id,
        transaction_id=trade.id,
        item_id=trade.item_id,
        to_building=payload.to_building or (provider.building if provider else None),
        content=payload.content.strip(),
    )
    db.add(grat)
    if provider:
        credit.on_gratitude_thanked(db, provider)
        push_notification(
            db,
            provider.id,
            "gratitude_received",
            "收到一条感谢",
            payload.content[:40],
            {"trade_id": trade.id},
        )
    db.commit()
    return ok({"id": grat.id})
