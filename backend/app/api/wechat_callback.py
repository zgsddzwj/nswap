"""微信消息推送回调：服务器验证（GET）+ mediaCheckAsync 结果推送（POST）。

云托管部署时，mp 后台「消息推送」URL 配置为：
https://<云托管域名>/api/wechat/callback（明文模式）
"""

import json
import logging
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.services.sec_check import handle_media_check_result

logger = logging.getLogger(__name__)

router = APIRouter(tags=["wechat"])


@router.get("/wechat/callback")
def verify(
    signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    nonce: str = Query(default=""),
    echostr: str = Query(default=""),
):
    """服务器有效性验证：原样返回 echostr。"""
    return PlainTextResponse(echostr or "nswap")


def _parse_xml(body: bytes) -> dict:
    try:
        root = ET.fromstring(body)
        return {child.tag: (child.text or "").strip() for child in root}
    except ET.ParseError:
        return {}


@router.post("/wechat/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    msg: dict = {}
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        try:
            msg = json.loads(body)
        except json.JSONDecodeError:
            msg = {}
    else:
        msg = _parse_xml(body)

    if not msg:
        return PlainTextResponse("success")

    event = msg.get("Event", "")
    if event == "wxa_media_check":
        trace_id = msg.get("trace_id", "")
        raw_result = msg.get("result", "{}")
        try:
            result = json.loads(raw_result) if isinstance(raw_result, str) else (raw_result or {})
        except json.JSONDecodeError:
            result = {}
        if trace_id:
            handle_media_check_result(db, trace_id, result)
    else:
        logger.info("wechat callback unhandled event: %s", event)

    return PlainTextResponse("success")
