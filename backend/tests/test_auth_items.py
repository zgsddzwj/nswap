"""鉴权、发布校验、频控、feed 与详情。"""

from app.models import Invite
from tests.conftest import hdr, make_user, publish


def test_login_auto_creates_guest(client, community, users):
    r = client.post("/api/auth/login", headers=hdr("dev_new"))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user"]["verified"] is False
    assert data["community"] is None  # 未验证用户无社区归属
    r = client.get("/api/community/info", headers=hdr("dev_new"))
    info = r.json()["data"]
    assert info["joined"] is False and info["name"] == ""  # 未加入小区返回空结构（docs/07 §4.7）
    # 先由已验证住户发布一件物品
    assert publish(client, "dev_alice", type="give", title="免费绘本",
                   price_cents=None, condition=None, category="book").status_code == 200
    # 游客：本小区 feed 为空，同城 feed 可见全部
    r = client.get("/api/items?scope=community", headers=hdr("dev_new"))
    assert r.json()["data"]["list"] == []
    r = client.get("/api/items?scope=city", headers=hdr("dev_new"))
    assert len(r.json()["data"]["list"]) == 1


def test_guest_cannot_publish(client, db, community):
    client.post("/api/auth/login", headers=hdr("dev_guest"))
    r = publish(client, "dev_guest")
    assert r.status_code == 403


def test_publish_and_feed(client, db, community, users):
    r = publish(client, "dev_alice", type="give", title="免费绘本", price_cents=None, condition=None, category="book")
    assert r.status_code == 200
    item_id = r.json()["data"]["id"]

    r = client.get("/api/items", headers=hdr("dev_bob"))
    data = r.json()["data"]
    assert any(i["id"] == item_id for i in data["list"])
    card = next(i for i in data["list"] if i["id"] == item_id)
    assert card["type"] == "give" and card["price_cents"] is None

    # 类型筛选
    r = client.get("/api/items?type=sell", headers=hdr("dev_bob"))
    assert all(i["type"] == "sell" for i in r.json()["data"]["list"])

    # 关键词搜索
    r = client.get("/api/items?keyword=绘本", headers=hdr("dev_bob"))
    assert any(i["id"] == item_id for i in r.json()["data"]["list"])


def test_publish_validation(client, db, community, users):
    # sell 缺价格
    r = publish(client, "dev_alice", price_cents=None)
    assert r.status_code == 400
    # swap 缺 want_desc
    r = publish(client, "dev_alice", type="swap", price_cents=None, want_desc=None)
    assert r.status_code == 400


def test_daily_publish_limit(client, db, community, users):
    for i in range(5):
        r = publish(client, "dev_alice", title=f"物品{i}")
        assert r.status_code == 200
    r = publish(client, "dev_alice", title="第6件")
    assert r.status_code == 429


def test_item_message_board(client, db, community, users):
    r = publish(client, "dev_alice", title="留言测试")
    item_id = r.json()["data"]["id"]
    r = client.post(
        f"/api/items/{item_id}/messages", json={"content": "还有吗"}, headers=hdr("dev_bob")
    )
    assert r.status_code == 200
    r = client.get(f"/api/items/{item_id}/messages", headers=hdr("dev_carol"))
    msgs = r.json()["data"]["list"]
    assert any(m["content"] == "还有吗" for m in msgs)


def test_invite_join_flow(client, db, community, users):
    db.add(Invite(community_id=community.id, code="YQ-TEST01", kind="normal", building="6栋"))
    db.commit()
    client.post("/api/auth/login", headers=hdr("dev_new"))
    r = client.post("/api/community/join", json={"code": "yq-test01"}, headers=hdr("dev_new"))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user"]["verified"] is True
    assert data["user"]["building"] == "6栋"
    # 邀请码一次性
    r = client.post("/api/community/join", json={"code": "YQ-TEST01"}, headers=hdr("dev_new2"))
    assert r.status_code == 404


def test_renew_cooldown(client, db, community, users):
    r = publish(client, "dev_alice", title="续期测试")
    item_id = r.json()["data"]["id"]
    r = client.post(f"/api/items/{item_id}/renew", headers=hdr("dev_alice"))
    assert r.status_code == 200
    r = client.post(f"/api/items/{item_id}/renew", headers=hdr("dev_alice"))
    assert r.status_code == 429


def test_favorite_flow(client, db, community, users):
    r = publish(client, "dev_alice", title="收藏测试")
    item_id = r.json()["data"]["id"]
    r = client.post(f"/api/items/{item_id}/favorite", headers=hdr("dev_bob"))
    assert r.status_code == 200
    r = client.get("/api/favorites", headers=hdr("dev_bob"))
    assert any(i["id"] == item_id for i in r.json()["data"]["list"])
    r = client.delete(f"/api/items/{item_id}/favorite", headers=hdr("dev_bob"))
    assert r.status_code == 200
    r = client.get("/api/favorites", headers=hdr("dev_bob"))
    assert not r.json()["data"]["list"]
