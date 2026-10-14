import base64
import os
import uuid

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_active_user, get_db
from app.core.errors import bad_request
from app.models import User
from app.schemas.serialize import ok
from app.services.rate_limit import check_rate
from app.services.storage import get_storage

router = APIRouter(tags=["uploads"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB

UPLOAD_RATE_LIMIT = 20  # 每用户每分钟上传次数（docs/09 P0-2）


def _check_upload_rate(user: User) -> None:
    if not check_rate(f"upload:{user.id}", UPLOAD_RATE_LIMIT, 60):
        from app.core.errors import too_many

        raise too_many("上传过于频繁，请稍后再试")


def save_upload(data: bytes, ext: str) -> str:
    """保存图片并返回完整公网 URL（存储后端由 STORAGE_BACKEND 决定，docs/09 P0-1）。"""
    return get_storage().save(data, ext)


@router.post("/uploads")
async def upload_image(
    file: UploadFile,
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    _check_upload_rate(user)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise bad_request("仅支持 jpg/png/webp 图片")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise bad_request("图片不能超过 5MB")
    if not data:
        raise bad_request("图片内容为空")
    return ok({"url": save_upload(data, ext)})


class Base64Upload(BaseModel):
    """JSON base64 上传通道。

    云托管场景：wx.cloud.callContainer 会注入 X-WX-OPENID，而 wx.uploadFile
    直连公网域名无法注入身份，小程序在生产环境改走此端点上传。
    """

    filename: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


@router.post("/uploads/base64")
def upload_image_base64(
    payload: Base64Upload,
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    _check_upload_rate(user)
    ext = os.path.splitext(payload.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise bad_request("仅支持 jpg/png/webp 图片")
    try:
        data = base64.b64decode(payload.content, validate=True)
    except Exception:
        raise bad_request("图片内容不合法")
    if not data:
        raise bad_request("图片内容为空")
    if len(data) > MAX_SIZE:
        raise bad_request("图片不能超过 5MB")
    return ok({"url": save_upload(data, ext)})
