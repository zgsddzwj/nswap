"""自建服务器登录链路（docs/13 路线 C）：code2session 换 token、Bearer 鉴权、篡改拒绝。"""

from app.services import wechat

from tests.conftest import hdr


def _mock_code2session(monkeypatch, openid_prefix="o"):
    monkeypatch.setattr(
        wechat.client, "code2session", lambda code: {"openid": f"{openid_prefix}-{code}"}
    )


def test_code_login_issues_token_and_bearer_works(client, db, community, monkeypatch):
    _mock_code2session(monkeypatch)
    r = client.post("/api/auth/login", json={"code": "CODE1"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["token"]
    assert data["user"]["verified"] is False  # 首次登录 = 游客
    assert data["community"] is None

    # 用 token 访问 /api/me：同一用户
    r2 = client.get("/api/me", headers={"Authorization": f"Bearer {data['token']}"})
    assert r2.status_code == 200
    assert r2.json()["data"]["user"]["id"] == data["user"]["id"]

    # 再登录一次（同 code）不重复建档
    r3 = client.post("/api/auth/login", json={"code": "CODE1"})
    assert r3.json()["data"]["user"]["id"] == data["user"]["id"]


def test_code2session_failure_returns_401(client, db, community, monkeypatch):
    monkeypatch.setattr(
        wechat.client, "code2session", lambda code: {"errcode": 40029, "errmsg": "invalid code"}
    )
    r = client.post("/api/auth/login", json={"code": "BAD"})
    assert r.status_code == 401
    assert "重试" in r.json()["message"]


def test_tampered_token_rejected(client, db, community, monkeypatch):
    _mock_code2session(monkeypatch)
    token = client.post("/api/auth/login", json={"code": "CODE2"}).json()["data"]["token"]

    r = client.get("/api/me", headers={"Authorization": f"Bearer {token}x"})
    assert r.status_code == 401
    assert "登录" in r.json()["message"]

    r = client.get("/api/me", headers={"Authorization": "Bearer forged.value.here"})
    assert r.status_code == 401


def test_bearer_takes_priority_over_dev_header(client, db, community, users, monkeypatch):
    """同时携带 Bearer 与 X-DEV-OPENID 时以 Bearer 为准（自建模式不被开发头污染）。"""
    _mock_code2session(monkeypatch)
    data = client.post("/api/auth/login", json={"code": "CODE3"}).json()["data"]

    r = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {data['token']}", "X-DEV-OPENID": "dev_alice"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["user"]["id"] == data["user"]["id"]  # 而非 dev_alice
    assert r.json()["data"]["user"]["id"] != users["alice"].id


def test_no_code_login_still_works_for_cloud_and_dev(client, db, community, users):
    """云托管/本地模式兼容：无 code 走请求头身份（原行为），且同样返回 token。"""
    r = client.post("/api/auth/login", headers=hdr("dev_alice"))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user"]["id"] == users["alice"].id
    assert data["token"]

    # 无 body 的调用（前端云托管模式现状）也必须成功
    r2 = client.post("/api/auth/login", headers=hdr("dev_alice"))
    assert r2.status_code == 200


# ---------- 资料修改的内容安全（昵称先检后发 / 头像异步检测登记） ----------

def test_nickname_risk_rejected(client, db, community, users, monkeypatch):
    from app.services import wechat

    monkeypatch.setattr(wechat.client, "msg_sec_check", lambda *a, **k: "risk")
    r = client.put("/api/me", json={"nickname": "加V卖东西"}, headers=hdr("dev_alice"))
    assert r.status_code == 400
    assert "敏感" in r.json()["message"]


def test_nickname_api_error_fail_closed(client, db, community, users, monkeypatch):
    from app.services import wechat

    monkeypatch.setattr(wechat.client, "msg_sec_check", lambda *a, **k: "error")
    r = client.put("/api/me", json={"nickname": "正常昵称"}, headers=hdr("dev_alice"))
    assert r.status_code == 400
    assert "稍后再试" in r.json()["message"]


def test_nickname_pass_saved(client, db, community, users):
    r = client.put("/api/me", json={"nickname": "3栋小艾"}, headers=hdr("dev_alice"))
    assert r.status_code == 200
    assert r.json()["data"]["user"]["nickname"] == "3栋小艾"


def test_nickname_empty_rejected(client, db, community, users):
    r = client.put("/api/me", json={"nickname": "  "}, headers=hdr("dev_alice"))
    assert r.status_code == 400


def test_avatar_mock_mode_saves_directly(client, db, community, users):
    r = client.put(
        "/api/me", json={"avatar_url": "http://82.157.59.122/nswap/uploads/a.jpg"},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 200
    assert r.json()["data"]["user"]["avatar_url"].endswith("a.jpg")


def test_avatar_api_error_fail_closed(client, db, community, users, monkeypatch):
    from app.core.config import settings
    from app.services import wechat

    monkeypatch.setattr(settings, "wx_call_mode", "token")  # 测试环境默认 mock，先切 token 模式
    monkeypatch.setattr(wechat.client, "media_check_async", lambda *a, **k: None)
    old = client.get("/api/me", headers=hdr("dev_alice")).json()["data"]["user"]["avatar_url"]
    r = client.put(
        "/api/me", json={"avatar_url": "http://82.157.59.122/nswap/uploads/bad.jpg"},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 400
    # 原头像保持不变
    r2 = client.get("/api/me", headers=hdr("dev_alice"))
    assert r2.json()["data"]["user"]["avatar_url"] == old


def test_avatar_risk_callback_resets_avatar(client, db, community, users, monkeypatch):
    """token 模式：头像登记异步检测，回调 risk 时被清空 + 通知用户。"""
    from app.core.config import settings
    from app.services import wechat
    from app.services.sec_check import handle_media_check_result

    monkeypatch.setattr(settings, "wx_call_mode", "token")
    monkeypatch.setattr(wechat.client, "media_check_async", lambda *a, **k: "TRACE-AV")
    r = client.put(
        "/api/me", json={"avatar_url": "http://x/uploads/risky.jpg"}, headers=hdr("dev_alice")
    )
    assert r.status_code == 200
    handle_media_check_result(db, "TRACE-AV", {"suggest": "risky", "label": 20001})
    # 回调后头像被清空
    r2 = client.get("/api/me", headers=hdr("dev_alice"))
    assert r2.json()["data"]["user"]["avatar_url"] == ""
    r = client.get("/api/me", headers=hdr("dev_alice"))
    assert r.json()["data"]["user"]["avatar_url"] == ""
    # 用户收到重置通知
    notifs = client.get("/api/notifications?unread_only=true", headers=hdr("dev_alice")).json()["data"]["list"]
    assert any(n["type"] == "content_rejected" for n in notifs)
