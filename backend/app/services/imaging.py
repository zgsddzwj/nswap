"""图片处理管线（docs/11）：EXIF 清除（隐私）+ 平台水印 + HEIC 兼容。

上传的所有图片统一经过本管线：
1. 兼容 HEIC（iPhone 原图）→ 转 JPEG
2. EXIF 转置（按方向摆正）后**清除全部 EXIF**（含 GPS 坐标/设备信息——
   与"不采集定位"的承诺一致，防止住户位置经原图泄露）
3. 右下角加半透明 "nswap" 平台水印（防盗图、脱离平台的截图可溯源）
"""

import io

from PIL import Image, ImageDraw, ImageFont

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:  # pragma: no cover
    HEIF_SUPPORTED = False

HEIC_EXTS = {".heic", ".heif"}
WATERMARK_TEXT = "nswap"


def _load_font(size: int):
    """优先取系统黑体；找不到退回默认字体。"""
    import os

    for path in (
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux CI/容器
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def process_image(data: bytes, ext: str) -> tuple[bytes, str]:
    """处理上传图片，返回 (处理后字节, 规范化扩展名)。

    无法识别的图片直接抛错（调用方转为 400）——不做宽松降级，
    保证 EXIF 清除与水印不因降级而失效。
    """
    ext = ext.lower()
    if ext in HEIC_EXTS and not HEIF_SUPPORTED:
        raise ValueError("HEIC 解码组件未安装")

    img = Image.open(io.BytesIO(data))
    # 按方向摆正（读取 EXIF orientation 后转置），并丢弃全部 EXIF
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img)

    if ext in HEIC_EXTS:
        ext = ".jpg"  # HEIC 统一转 JPEG

    has_alpha = img.mode in ("RGBA", "LA")
    if has_alpha:
        img = img.convert("RGBA")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # ---- 水印：右下角半透明平台标识 ----
    watermark = _watermark_layer(img.size)
    if has_alpha:
        img = Image.alpha_composite(img, watermark)
    else:
        img = Image.alpha_composite(img.convert("RGBA"), watermark).convert("RGB")

    buf = io.BytesIO()
    if ext == ".png":
        img.save(buf, format="PNG")
    elif ext == ".webp":
        img.save(buf, format="WEBP")
    else:
        ext = ".jpg"
        img.save(buf, format="JPEG", quality=88)
    return buf.getvalue(), ext


def _watermark_layer(size: tuple[int, int]) -> Image.Image:
    """生成与原图同尺寸的透明水印图层（右下角）。"""
    width, height = size
    font_size = max(16, min(width // 22, 48))
    font = _load_font(font_size)
    text = WATERMARK_TEXT

    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    try:
        box = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = box[2] - box[0], box[3] - box[1]
    except Exception:  # pragma: no cover
        text_w, text_h = font_size * len(text) * 0.6, font_size

    padding = max(8, width // 60)
    x, y = width - text_w - padding - font_size // 3, height - text_h - padding - font_size // 2
    # 细描边（深色）+ 半透明白字，浅底深底都可见
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 90))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 150))
    return layer
