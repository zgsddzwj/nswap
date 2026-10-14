"""图片存储抽象（docs/09 P0-1）。

容器无状态：生产必须用 cos 后端（腾讯云对象存储），否则重启/重新部署丢图。
本地开发默认 local 后端，零依赖。
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageBackend(Protocol):
    def save(self, data: bytes, ext: str) -> str:
        """保存图片，返回公网可访问的完整 URL。"""
        ...


def _object_key(ext: str) -> str:
    """对象 key 规范：uploads/{YYYYMM}/{uuid}{ext}（按月分目录便于生命周期管理）。"""
    month = datetime.utcnow().strftime("%Y%m")
    return f"uploads/{month}/{uuid.uuid4().hex}{ext}"


class LocalStorage:
    """容器本地盘（仅开发）：重启即丢，生产禁用。"""

    def __init__(self) -> None:
        self.root = settings.upload_dir

    def save(self, data: bytes, ext: str) -> str:
        os.makedirs(self.root, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(self.root, filename)
        with open(path, "wb") as f:
            f.write(data)
        return settings.public_base_url.rstrip("/") + f"/uploads/{filename}"


class CosStorage:
    """腾讯云对象存储（走 S3 兼容 API，boto3 实现；依赖全部有预编译 wheel）。

    返回 {cdn_domain 或 COS 默认域名}/{key}。
    """

    def __init__(self) -> None:
        import boto3  # 延迟导入：local 模式无需安装

        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://cos.{settings.cos_region}.myqcloud.com",
            aws_access_key_id=settings.cos_secret_id,
            aws_secret_access_key=settings.cos_secret_key,
            region_name=settings.cos_region,
            config=__import__("botocore.config", fromlist=["Config"]).Config(
                signature_version="s3v4", retries={"max_attempts": 3}
            ),
        )
        self.bucket = settings.cos_bucket

    def save(self, data: bytes, ext: str) -> str:
        key = _object_key(ext)
        content_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(ext, "application/octet-stream")
        self.client.put_object(Bucket=self.bucket, Body=data, Key=key, ContentType=content_type)
        domain = settings.cos_cdn_domain.strip().rstrip("/")
        if domain:
            return f"{domain}/{key}"
        return f"https://{self.bucket}.cos.{settings.cos_region}.myqcloud.com/{key}"


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """存储后端工厂（按配置单例）。"""
    global _storage
    if _storage is not None:
        return _storage
    if settings.storage_backend == "cos":
        if not (settings.cos_secret_id and settings.cos_secret_key and settings.cos_region and settings.cos_bucket):
            raise RuntimeError("STORAGE_BACKEND=cos 但 COS 配置不完整（SECRET_ID/SECRET_KEY/REGION/BUCKET）")
        _storage = CosStorage()
        logger.info("图片存储后端: cos bucket=%s", settings.cos_bucket)
    else:
        if settings.environment == "prod":
            logger.warning("生产环境使用 local 图片存储：容器重启将丢失全部图片！请配置 STORAGE_BACKEND=cos")
        _storage = LocalStorage()
    return _storage


def reset_storage_cache() -> None:
    """测试用：重置工厂单例。"""
    global _storage
    _storage = None
