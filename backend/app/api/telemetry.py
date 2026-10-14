"""小程序错误上报（docs/09 P0-5 / P1-11）：仅记日志，不落库，限流防刷。"""

import logging

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_db
from app.models import User
from app.schemas.serialize import ok
from app.services.rate_limit import check_rate

router = APIRouter(tags=["telemetry"])
logger = logging.getLogger("nswap.miniprogram")


@router.post("/telemetry/errors")
def report_error(
    payload: dict,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    if not check_rate(f"telemetry:{user.id}", 10, 60):
        return ok({"ok": False})  # 静默丢弃，不回 429（避免小程序侧噪音）
    message = str(payload.get("message") or "")[:500]
    stack = str(payload.get("stack") or "")[:1000]
    page = str(payload.get("page") or "")[:100]
    logger.warning(
        "miniprogram_error user=%s page=%s message=%s stack=%s",
        user.id, page, message, stack,
    )
    return ok({"ok": True})
