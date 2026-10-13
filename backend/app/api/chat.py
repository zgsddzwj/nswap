from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_verified_user
from app.core.errors import forbidden, not_found
from app.core.time import iso, utcnow
from app.models import Conversation, DmMessage, User
from app.schemas import ContentPayload
from app.schemas.serialize import conversation_dto, ok
from app.services.notify import push_notification
from app.services.sec_check import check_text

router = APIRouter(tags=["chat"])


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
