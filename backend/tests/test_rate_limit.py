"""生产化加固：限流/登录防爆破/存储抽象（docs/09 P0-1/P0-2）。"""

import io

import pytest
from PIL import Image

from app.core.config import settings
from app.services import rate_limit
from app.services.rate_limit import MemoryRateLimiter
from app.services.storage import LocalStorage, get_storage, reset_storage_cache
from tests.conftest import hdr, make_admin, publish


@pytest.fixture()
def enable_rate_limit(monkeypatch):
    """打开限流并重置计数（其余用例默认关闭）。"""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    rate_limit.get_rate_limiter().reset()
    rate_limit.get_failure_tracker()._fail.clear()
    yield
    rate_limit.get_rate_limiter().reset()
    rate_limit.get_failure_tracker()._fail.clear()


# ---------------- 限流器单元 ----------------

def test_memory_limiter_window():
    limiter = MemoryRateLimiter()
    assert all(limiter.hit("k", 3, 60) for _ in range(3))
    assert limiter.hit("k", 3, 60) is False  # 第 4 次超限
    limiter.reset("k")
    assert limiter.hit("k", 3, 60) is True


def test_failure_tracker():
    t = rate_limit.FailureTracker()
    for i in range(5):
        assert t.record("u", 900) == i + 1
    assert t.count("u", 900) == 5
    t.clear("u")
    assert t.count("u", 900) == 0


# ---------------- 登录防爆破 ----------------

def test_login_lockout_after_failures(client, db, enable_rate_limit):
    make_admin(db)
    for i in range(5):
        r = client.post("/api/admin/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401, f"第 {i + 1} 次失败应为 401"
    # 第 6 次：即使密码正确也被锁定
    r = client.post("/api/admin/auth/login", json={"username": "admin", "password": "nswap123"})
    assert r.status_code == 401
    assert "锁定" in r.json()["message"]
    # 手动清除锁定后可正常登录
    rate_limit.get_failure_tracker().clear("login:admin")
    rate_limit.get_rate_limiter().reset()
    r = client.post("/api/admin/auth/login", json={"username": "admin", "password": "nswap123"})
    assert r.status_code == 200


def test_login_ip_rate_limit(client, db, enable_rate_limit, monkeypatch):
    from app.api.admin import api as admin_api

    monkeypatch.setattr(admin_api, "LOGIN_IP_LIMIT", 3)
    make_admin(db)
    for _ in range(3):
        client.post("/api/admin/auth/login", json={"username": "admin", "password": "wrong"})
    r = client.post("/api/admin/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 429


# ---------------- 写接口限流 ----------------

def test_upload_rate_limit(client, db, community, users, enable_rate_limit, monkeypatch):
    from app.api import uploads as uploads_api

    monkeypatch.setattr(uploads_api, "UPLOAD_RATE_LIMIT", 2)
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (14, 122, 90)).save(buf, format="PNG")
    png = buf.getvalue()
    for i in range(2):
        r = client.post(
            "/api/uploads",
            files={"file": ("a.png", png, "image/png")},
            headers=hdr("dev_alice"),
        )
        assert r.status_code == 200, f"第 {i + 1} 次上传应成功"
    r = client.post(
        "/api/uploads",
        files={"file": ("a.png", png, "image/png")},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 429


def test_global_rate_limit(client, db, enable_rate_limit, monkeypatch):
    from app.core import middleware

    monkeypatch.setattr(middleware, "GLOBAL_RATE_LIMIT", 5)
    codes = [
        client.get("/api/items", headers=hdr("dev_alice")).status_code for _ in range(6)
    ]
    assert codes[-1] == 429
    # 豁免路径不受影响
    assert client.get("/healthz").status_code == 200


# ---------------- 存储抽象 ----------------

def test_storage_local_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "public_base_url", "http://example.test")
    reset_storage_cache()
    storage = get_storage()
    assert isinstance(storage, LocalStorage)
    url = storage.save(b"data", ".png")
    assert url.startswith("http://example.test/uploads/")
    filename = url.rsplit("/", 1)[-1]
    assert (tmp_path / filename).read_bytes() == b"data"
    reset_storage_cache()


def test_storage_cos_requires_config(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "cos")
    monkeypatch.setattr(settings, "cos_secret_id", "")
    reset_storage_cache()
    with pytest.raises(RuntimeError, match="COS 配置不完整"):
        get_storage()
    reset_storage_cache()


def test_upload_uses_storage_abstraction(client, db, community, users, monkeypatch):
    """上传入口走存储抽象（FakeBackend 注入验证），且处理管线已生效。"""
    import io as _io

    from PIL import Image

    from app.api import uploads as uploads_api

    seen: dict = {}

    class FakeStorage:
        def save(self, data: bytes, ext: str) -> str:
            seen["data"], seen["ext"] = data, ext
            return "https://fake-cdn.test/uploads/x.png"

    monkeypatch.setattr(uploads_api, "get_storage", lambda: FakeStorage())
    buf = _io.BytesIO()
    Image.new("RGB", (60, 40), (20, 30, 40)).save(buf, format="PNG")
    r = client.post(
        "/api/uploads",
        files={"file": ("a.png", buf.getvalue(), "image/png")},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 200
    assert r.json()["data"]["url"] == "https://fake-cdn.test/uploads/x.png"
    # 管线验证：EXIF 清除后以 JPEG/PNG 落盘，尺寸保持
    assert seen["ext"] in (".png", ".jpg")
    img = Image.open(_io.BytesIO(seen["data"]))
    assert img.size == (60, 40)
    assert not (img.info.get("exif"))


def test_request_id_header(client, db, community):
    r = client.get("/healthz")
    assert len(r.headers.get("x-request-id", "")) == 16
