"""通知：站内通知为基准（必达），微信订阅消息为增强（有配额才发）。"""

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utcnow
from app.models import MsgSubscription, Notification, User
from app.services.wechat import client

logger = logging.getLogger(__name__)


def push_notification(
    db: Session,
    user_id: int,
    type_: str,
    title: str,
    content: str = "",
    payload: dict | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=type_,
            title=title,
            content=content,
            payload=payload or {},
        )
    )


def send_subscribe(
    db: Session, user: User, template_key: str, fields: dict[str, str], page: str | None = None
) -> None:
    """消耗一次订阅配额发送模板消息；无配额/无模板时静默跳过。"""
    tpl_id = getattr(settings, f"msg_tpl_{template_key}", "")
    if settings.wx_call_mode == "mock" or not tpl_id:
        return
    sub = (
        db.query(MsgSubscription)
        .filter(
            MsgSubscription.user_id == user.id,
            MsgSubscription.template_key == template_key,
            MsgSubscription.used_at.is_(None),
        )
        .first()
    )
    if sub is None:
        return
    client.send_subscribe_message(user.openid, tpl_id, fields, page)
    sub.used_at = utcnow()
