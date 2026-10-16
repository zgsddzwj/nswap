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
