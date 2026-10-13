import logging

from sqlalchemy.orm import Session

from app.core.errors import bad_request
from app.models import ItemImage, Item, SecCheck, User
from app.services.wechat import client

logger = logging.getLogger(__name__)


def check_text(
    db: Session, content: str, user: User, target_type: str, target_id: int | None = None
) -> str:
    """文本先检后发。

    返回 sec_status：
    - pass   正常展示
    - pending 接口异常降级（fail-closed）：仅作者与管理员可见，待人工处置
    - risk   直接抛 400（调用方不落库/不展示）
    """
    result = client.msg_sec_check(content, user.openid)
    if result == "risk":
        raise bad_request("内容包含敏感信息，请修改后重试")
    if result == "error":
        db.add(
            SecCheck(
                target_type=target_type,
                target_id=target_id,
                status="error",
                detail={"reason": "msg_sec_check unavailable", "content_head": content[:50]},
            )
        )
        return "pending"
    return "pass"


def register_item_images(db: Session, item: Item, urls: list[str], owner: User) -> None:
    """为物品登记图片并发起异步检测（先发后撤：pending 即展示，回调 risk 立即隐藏）。"""
    for order, url in enumerate(urls):
        img = ItemImage(item_id=item.id, url=url, sort_order=order, sec_status="pending")
        db.add(img)
        db.flush()
        trace_id = client.media_check_async(url, owner.openid)
        if trace_id is None:
            img.sec_status = "pass"
        else:
            img.trace_id = trace_id
            db.add(
                SecCheck(
                    trace_id=trace_id,
                    target_type="image",
                    target_id=img.id,
                    status="processing",
                )
            )


def handle_media_check_result(db: Session, trace_id: str, result: dict) -> None:
    """mediaCheckAsync 回调处理：按 trace_id 回写图片 sec_status。"""
    check = db.query(SecCheck).filter(SecCheck.trace_id == trace_id).first()
    suggest = result.get("suggest", "pass")
    new_status = "ok" if suggest == "pass" else "risk"
    if check:
        check.status = new_status
        check.detail = result
        if check.target_type == "image" and check.target_id:
            img = db.get(ItemImage, check.target_id)
            if img:
                img.sec_status = "pass" if suggest == "pass" else "fail"
    db.commit()
    logger.info("media_check callback trace=%s suggest=%s", trace_id, suggest)
