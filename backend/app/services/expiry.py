"""定时扫描：沉底与归档（APScheduler 每日触发，也可手动调用）。"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models import Item
from app.services.notify import push_notification

logger = logging.getLogger(__name__)

SINK_AFTER_DAYS = 14      # 无互动沉底
ARCHIVE_AFTER_DAYS = 30   # 沉底后再 30 天未处理 → 归档


def run_expiry_scan(db: Session) -> dict:
    now = utcnow()
    sink_before = now - timedelta(days=SINK_AFTER_DAYS)
    archive_before = now - timedelta(days=SINK_AFTER_DAYS + ARCHIVE_AFTER_DAYS)

    # on_sale → sunk
    to_sink = (
        db.query(Item)
        .filter(Item.status == "on_sale", Item.last_active_at < sink_before)
        .all()
    )
    for item in to_sink:
        item.status = "sunk"
        push_notification(
            db,
            item.user_id,
            "item_sunk",
            "你的物品已沉底",
            f"「{item.title}」14天无互动已从首页沉底，续期可重新上架",
            {"item_id": item.id},
        )

    # sunk → archived
    archived = (
        db.query(Item)
        .filter(Item.status == "sunk", Item.last_active_at < archive_before)
        .update({"status": "archived"}, synchronize_session=False)
    )

    db.commit()
    result = {"sunk": len(to_sink), "archived": archived}
    logger.info("expiry scan: %s", result)
    return result
