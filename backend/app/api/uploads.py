import os
import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_active_user, get_db
from app.core.errors import bad_request
from app.models import User
from app.schemas.serialize import ok

router = APIRouter(tags=["uploads"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB


def save_upload(data: bytes, ext: str) -> str:
    """存储图片并返回相对路径。

    MVP 使用容器本地盘；迁移到云托管对象存储/COS 时只需替换此函数
    （把文件写入 COS 并返回公网 URL），调用方无感知。见 docs/05 第④步。
    """
    os.makedirs(settings.upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, filename)
    with open(path, "wb") as f:
        f.write(data)
    return f"/uploads/{filename}"


@router.post("/uploads")
async def upload_image(
    file: UploadFile,
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise bad_request("仅支持 jpg/png/webp 图片")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise bad_request("图片不能超过 5MB")
    if not data:
        raise bad_request("图片内容为空")
    path = save_upload(data, ext)
    url = settings.public_base_url.rstrip("/") + path
    return ok({"url": url})
