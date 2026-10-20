import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import bad_request
from app.models import ItemImage, Item, SecCheck, User
from app.services.notify import push_notification
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
    """为物品登记图片并发起异步检测（先发后撤：pending 即展示，回调 risk 立即隐藏）。

    mock 模式直接置 pass；token/cloud 模式下接口不可用（无 trace_id）时保持 pending
    并落 SecCheck(error) 记录，进入管理端待审队列——不得静默放行（fail-closed）。
    """
    for order, url in enumerate(urls):
        img = ItemImage(item_id=item.id, url=url, sort_order=order, sec_status="pending")
        db.add(img)
        db.flush()
        if settings.wx_call_mode == "mock":
            img.sec_status = "pass"
            continue
        trace_id = client.media_check_async(url, owner.openid)
        if trace_id is None:
            db.add(
                SecCheck(
                    target_type="image",
                    target_id=img.id,
                    status="error",
                    detail={"reason": "media_check_async unavailable", "url_head": url[:60]},
                )
            )
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


def register_avatar_check(db: Session, user: User, url: str) -> bool:
    """头像异步内容检测（头像展示给所有邻居，属 UGC 图片）。

    返回 True=已登记或无需检测（可保存）；False=检测接口不可用（调用方 fail-closed 拒绝）。
    回调 risk 时由 handle_media_check_result 重置头像。
    """
    if settings.wx_call_mode == "mock":
        return True
    trace_id = client.media_check_async(url, user.openid)
    if trace_id is None:
        db.add(
            SecCheck(
                target_type="avatar",
                target_id=user.id,
                status="error",
                detail={"reason": "media_check_async unavailable", "url_head": url[:60]},
            )
        )
        return False
    db.add(
        SecCheck(trace_id=trace_id, target_type="avatar", target_id=user.id, status="processing")
    )
    return True


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
        elif check.target_type == "avatar" and check.target_id:
            if suggest != "pass":
                # 用 UPDATE 语句而非对象赋值：不受会话身份缓存影响，且天然防并发覆盖
                db.query(User).filter(User.id == check.target_id).update(
                    {"avatar_url": ""}, synchronize_session=False
                )
                push_notification(
                    db,
                    check.target_id,
                    "content_rejected",
                    "头像已被重置",
                    "你设置的头像未通过内容安全检测，已恢复默认头像",
                    {"type": "avatar"},
                )
    db.commit()
    logger.info("media_check callback trace=%s suggest=%s", trace_id, suggest)
