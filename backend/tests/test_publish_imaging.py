"""发布体验优化（docs/11）：智能分类 + 图片处理管线（水印/EXIF 清除）。"""

import io
from datetime import datetime

from PIL import Image

from app.core.config import settings
from app.models import Item, User
from app.services.categorize import guess_category
from app.services.imaging import process_image
from tests.conftest import hdr, publish


def _png(exif: bytes | None = None, color=(120, 60, 30), size=(80, 60)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color)
    if exif:
        # 构造带 GPS 信息的 EXIF（模拟 iPhone 原图）
        exif_dict = {"0th": {306: "2026:10:14 12:00:00"}, "GPS": {1: 30.0, 2: (20, 0, 0), 3: "N"}}
        import piexif  # noqa: 仅在安装了 piexif 的环境生效

        try:
            exif_bytes = piexif.dump(exif_dict)
        except Exception:
            exif_bytes = exif
        img.save(buf, format="JPEG", exif=exif_bytes)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------- 智能分类（发布免选） ----------------

def test_guess_category_rules():
    assert guess_category("好孩子婴儿推车 九成新") == "baby"
    assert guess_category("儿童绘本 20 册") == "book"
    assert guess_category("小米空气净化器") == "appliance"
    assert guess_category("宜家书架 九成新") == "furniture"
    assert guess_category("iPhone 12 128G") == "digital"
    assert guess_category("篮球 九成新") == "sports"
    assert guess_category("空气炸锅 便宜出") == "kitchen"
    assert guess_category("随缘出个东西", "") == "other"


def test_publish_without_category_auto_guessed(client, db, community, users):
    # 前端不再传 category → 后端按标题自动识别
    r = client.post(
        "/api/items",
        json={"type": "sell", "title": "好孩子婴儿推车 九成新", "description": "宝宝长大了",
              "condition": "like_new", "price_cents": 15000, "images": []},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 200
    assert r.json()["data"]["category"] == "baby"

    # 无关键词 → other
    r = client.post(
        "/api/items",
        json={"type": "give", "title": "随缘出个东西", "description": "", "images": []},
        headers=hdr("dev_alice"),
    )
    assert r.json()["data"]["category"] == "other"

    # 编辑同样自动识别（改为含绘本的关键词，形态改赠送以免价格校验）
    item_id = client.get("/api/items?mine=true", headers=hdr("dev_alice")).json()["data"]["list"][0]["id"]
    r = client.put(
        f"/api/items/{item_id}",
        json={"type": "give", "title": "出一批儿童绘本", "description": "",
              "images": []},
        headers=hdr("dev_alice"),
    )
    assert r.json()["data"]["category"] == "book"


# ---------------- 图片管线：EXIF 清除 + 水印 ----------------

def _upload(client, data: bytes, filename: str = "photo.jpg"):
    return client.post(
        "/api/uploads", files={"file": (filename, data, "image/jpeg")}, headers=hdr("dev_alice")
    )


def test_upload_strips_exif_and_keeps_size(client, db, community, users):
    # 用 piexif 构造含 GPS 坐标的合法 EXIF（模拟 iPhone 原图）
    import piexif

    buf = io.BytesIO()
    img = Image.new("RGB", (120, 80), (50, 80, 60))
    exif_dict = {
        "0th": {piexif.ImageIFD.Make: b"TestMake"},
        "GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N", piexif.GPSIFD.GPSLatitude: ((30, 1), (20, 1), (0, 1))},
    }
    exif_bytes = piexif.dump(exif_dict)
    img.save(buf, format="JPEG", exif=exif_bytes)
    original = buf.getvalue()
    assert b"TestMake" in original  # 构造成功

    r = _upload(client, original)
    assert r.status_code == 200
    url = r.json()["data"]["url"]

    # 从存储后端取回落盘文件（本地后端：uploads 目录）
    from app.core.config import settings

    filename = url.rsplit("/", 1)[-1]
    with open(f"{settings.upload_dir}/{filename}", "rb") as f:
        stored = f.read()

    out = Image.open(io.BytesIO(stored))
    assert not out.info.get("exif"), "落盘图片必须无 EXIF（隐私）"
    assert b"TestMake" not in stored
    assert out.size == (120, 80)  # 尺寸保持


def test_upload_adds_watermark(client, db, community, users):
    original = _png_no_watermark()
    r = _upload(client, original)
    assert r.status_code == 200
    url = r.json()["data"]["url"]
    from app.core.config import settings

    filename = url.rsplit("/", 1)[-1]
    with open(f"{settings.upload_dir}/{filename}", "rb") as f:
        stored = Image.open(io.BytesIO(f.read())).convert("RGB")

    src = Image.open(io.BytesIO(original)).convert("RGB")
    # 水印画在右下角：比对右下角区域与原图必然不同（非白底条件下）
    w, h = src.size
    region_src = src.crop((w - 40, h - 24, w, h))
    region_out = stored.crop((w - 40, h - 24, w, h))
    diff = sum(
        1
        for x in range(region_src.size[0])
        for y in range(region_src.size[1])
        if region_src.getpixel((x, y)) != region_out.getpixel((x, y))
    )
    assert diff > 0, "右下角应存在水印像素变化"


def _png_no_watermark() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 120), (140, 60, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_corrupt_image_rejected(client, db, community, users):
    r = _upload(client, b"not-an-image-at-all")
    assert r.status_code == 400
    assert "无法识别" in r.json()["message"]


def test_upload_heic_converted(client, db, community, users):
    """HEIC 兼容：处理管线应转成 JPEG 落盘（有 pillow-heif 才测）。"""
    from app.services.imaging import HEIF_SUPPORTED

    if not HEIF_SUPPORTED:
        pytest.skip("pillow-heif 未安装")
    heic_buf = io.BytesIO()
    Image.new("RGB", (60, 40), (10, 100, 90)).save(heic_buf, format="HEIF")
    r = _upload(client, heic_buf.getvalue(), filename="photo.heic")
    assert r.status_code == 200
    assert r.json()["data"]["url"].endswith(".jpg")
