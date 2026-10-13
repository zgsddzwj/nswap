from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_verified_user
from app.core.errors import bad_request, forbidden, not_found, too_many
from app.core.time import iso, utcnow
from app.models import ContactExchange, Conversation, DmMessage, User
from app.schemas import ContentPayload
from app.schemas.serialize import conversation_dto, ok
from app.services.notify import push_notification
from app.services.sec_check import check_text

router = APIRouter(tags=["chat"])

# 交换查看额度：每会员每日可发起的联系方式交换次数（防爬取防骚扰）
DAILY_CONTACT_LIMIT = 3


@router.get("/conversations")
def list_conversations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    convs = (
        db.query(Conversation)
        .filter((Conversation.user_a == user.id) | (Conversation.user_b == user.id))
        .order_by(Conversation.id.desc())
        .all()
    )
    return ok({"list": [conversation_dto(db, c, user) for c in convs]})


def _get_conv(db: Session, conv_id: int, user: User) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None:
        raise not_found("会话不存在")
    if user.id not in (conv.user_a, conv.user_b):
        raise forbidden("你不是会话参与者")
    return conv


@router.get("/conversations/{conv_id}/messages")
def list_messages(
    conv_id: int,
    since: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_conv(db, conv_id, user)
    q = db.query(DmMessage).filter(DmMessage.conversation_id == conv.id)
    if since:
        q = q.filter(DmMessage.id > since).order_by(DmMessage.id.asc())
        rows = q.limit(100).all()
    else:
        rows = (
            q.order_by(DmMessage.id.desc()).limit(50).all()
        )
        rows = list(reversed(rows))
    return ok(
        {
            "list": [
                {
                    "id": m.id,
                    "sender_id": m.sender_id,
                    "content": m.content,
                    "created_at": iso(m.created_at),
                }
                for m in rows
            ]
        }
    )


@router.post("/conversations/{conv_id}/messages")
def send_message(
    conv_id: int,
    payload: ContentPayload,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    conv = _get_conv(db, conv_id, user)
    check_text(db, payload.content, user, "text", None)
    msg = DmMessage(
        conversation_id=conv.id, sender_id=user.id, content=payload.content.strip()
    )
    db.add(msg)
    conv.last_message_at = utcnow()
    counterpart_id = conv.user_b if conv.user_a == user.id else conv.user_a
    push_notification(
        db,
        counterpart_id,
        "chat_message",
        "收到新消息",
        f"{user.nickname or '邻居'}：{payload.content[:30]}",
        {"conversation_id": conv.id},
    )
    db.commit()
    return ok(
        {
            "id": msg.id,
            "sender_id": msg.sender_id,
            "content": msg.content,
            "created_at": iso(msg.created_at),
        }
    )


# ---------------- 联系方式交换（会员=已验证住户；默认不开放；限次；双向留痕） ----------------


def _contact_of(u: User) -> dict:
    return {"wechat": u.contact_wechat or None, "phone": u.contact_phone or None}


def _quota_left(db: Session, user: User) -> int:
    """今日剩余交换额度（按 UTC 日重置）。"""
    day_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    used = (
        db.query(ContactExchange)
        .filter(
            ContactExchange.initiator_id == user.id,
            ContactExchange.created_at >= day_start,
        )
        .count()
    )
    return max(0, DAILY_CONTACT_LIMIT - used)


def _exchange_dto(counterpart: User, exchanged: bool, remaining: int) -> dict:
    has_contact = counterpart.contact_enabled and (
        counterpart.contact_wechat or counterpart.contact_phone
    )
    return {
        "exchanged": exchanged,
        "remaining_today": remaining,
        "counterpart": {
            "id": counterpart.id,
            "nickname": counterpart.nickname,
            "building": counterpart.building,
        },
        # 未交换、或对方未开放/未填写时恒为 None：任何接口都不泄露联系方式
        "contact": _contact_of(counterpart) if exchanged and has_contact else None,
    }


@router.get("/conversations/{conv_id}/contact")
def contact_status(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """会话的联系方式交换状态（是否已交换、剩余额度）。"""
    conv = _get_conv(db, conv_id, user)
    counterpart = db.get(User, conv.user_b if conv.user_a == user.id else conv.user_a)
    exchange = (
        db.query(ContactExchange).filter(ContactExchange.conversation_id == conv.id).first()
    )
    return ok(_exchange_dto(counterpart, exchange is not None, _quota_left(db, user)))


@router.post("/conversations/{conv_id}/contact")
def exchange_contact(
    conv_id: int,
    user: User = Depends(get_verified_user),  # 会员资格：已验证住户
    db: Session = Depends(get_db),
):
    """发起联系方式交换：消耗发起方 1 次当日额度，双向解锁并互发通知，幂等。"""
    conv = _get_conv(db, conv_id, user)
    counterpart = db.get(User, conv.user_b if conv.user_a == user.id else conv.user_a)
    if counterpart is None:
        raise not_found("对方不存在")

    exchange = (
        db.query(ContactExchange).filter(ContactExchange.conversation_id == conv.id).first()
    )
    if exchange is not None:
        # 幂等：同会话不重复扣额度
        return ok(_exchange_dto(counterpart, True, _quota_left(db, user)))

    if not counterpart.contact_enabled or not (
        counterpart.contact_wechat or counterpart.contact_phone
    ):
        raise bad_request("对方暂未开放联系方式，可以在会话里留言沟通")

    remaining = _quota_left(db, user)
    if remaining <= 0:
        raise too_many(f"今日交换次数已用完（每日 {DAILY_CONTACT_LIMIT} 次），明天再来")

    db.add(ContactExchange(conversation_id=conv.id, initiator_id=user.id))
    push_notification(
        db,
        counterpart.id,
        "contact_exchanged",
        "你与邻居交换了联系方式",
        f"{user.nickname or '邻居'} 在交换中查看了你的联系方式，请注意隐私安全",
        {"conversation_id": conv.id},
    )
    db.commit()
    return ok(_exchange_dto(counterpart, True, remaining - 1))
