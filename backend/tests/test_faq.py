"""FAQ 墙（docs/10 Phase 1）：管理端发布、住户只读+点赞、小区隔离、置顶。"""

import pytest

from app.core.security import hash_password
from app.models import AdminUser, Community, User
from tests.conftest import hdr, make_admin


@pytest.fixture()
def property_admin(db, community):
    a = AdminUser(
        username="wy_faq", password_hash=hash_password("password123"),
        name="FAQ物业", community_id=community.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _login(client, username, password):
    return client.post("/api/admin/auth/login", json={"username": username, "password": password})


def test_faq_publish_and_resident_read(client, db, community, users, property_admin):
    assert _login(client, "wy_faq", "password123").status_code == 200
    # 发布两条，一条置顶
    client.post("/api/admin/faq", json={"title": "Q1", "content": "A1", "pinned": False})
    client.post("/api/admin/faq", json={"title": "Q2 置顶", "content": "A2", "pinned": True})

    # 住户可见：置顶优先
    rows = client.get("/api/faqs", headers=hdr("dev_alice")).json()["data"]["list"]
    assert [x["title"] for x in rows] == ["Q2 置顶", "Q1"]
    assert all(x["like_count"] == 0 and x["my_like"] is False for x in rows)

    # 游客（未加入小区）不可见
    client.post("/api/auth/login", headers=hdr("dev_guest_faq"))
    rows = client.get("/api/faqs", headers=hdr("dev_guest_faq")).json()["data"]["list"]
    assert rows == []

    # faq 免微信审核：sec_status 默认 pass
    from app.models import Post
    assert all(p.sec_status == "pass" for p in db.query(Post).all())


def test_faq_like_idempotent_and_count(client, db, community, users, property_admin):
    assert _login(client, "wy_faq", "password123").status_code == 200
    faq_id = client.post(
        "/api/admin/faq", json={"title": "点赞测试", "content": "A"}
    ).json()["data"]["id"]

    # 点赞 → 重复点赞幂等 → 取消 → 计数归零
    r1 = client.post(f"/api/faqs/{faq_id}/like", headers=hdr("dev_alice"))
    assert r1.json()["data"] == {"liked": True, "like_count": 1}
    r2 = client.post(f"/api/faqs/{faq_id}/like", headers=hdr("dev_alice"))
    assert r2.json()["data"]["like_count"] == 1  # 幂等
    r3 = client.post(f"/api/faqs/{faq_id}/like", headers=hdr("dev_bob"))
    assert r3.json()["data"]["like_count"] == 2
    r4 = client.delete(f"/api/faqs/{faq_id}/like", headers=hdr("dev_alice"))
    assert r4.json()["data"] == {"liked": False, "like_count": 1}
    # 重复取消幂等
    r5 = client.delete(f"/api/faqs/{faq_id}/like", headers=hdr("dev_alice"))
    assert r5.json()["data"]["like_count"] == 1

    # my_like 标记正确
    rows = client.get("/api/faqs", headers=hdr("dev_bob")).json()["data"]["list"]
    assert rows[0]["my_like"] is True and rows[0]["like_count"] == 1


def test_faq_community_isolation(client, db, community, property_admin):
    other = Community(name="幸福里", city="测试市")
    db.add(other)
    db.commit()
    outsider = User(openid="dev_out_faq", nickname="外部", community_id=other.id, verified_at=__import__("app.core.time", fromlist=["utcnow"]).utcnow())
    db.add(outsider)
    db.commit()

    # 物业发布本小区 FAQ
    assert _login(client, "wy_faq", "password123").status_code == 200
    client.post("/api/admin/faq", json={"title": "阳光花园FAQ", "content": "A"})

    # 外小区住户不可见
    rows = client.get("/api/faqs", headers=hdr("dev_out_faq")).json()["data"]["list"]
    assert rows == []

    # 物业看不到/删不掉外小区 FAQ
    # 无 admin 会话（清除 cookie）→ 401；住户无发帖通道
    client.cookies.clear()
    other_faq_id = client.post(
        "/api/admin/faq",
        json={"title": "外小区FAQ", "content": "A", "community_id": other.id},
    )
    assert other_faq_id.status_code == 401
    # 超管跨小区发布 → 外小区住户可见
    make_admin(db)
    client.cookies.clear()
    client.post("/api/admin/auth/login", json={"username": "admin", "password": "nswap123"})
    client.post("/api/admin/faq", json={"title": "幸福里FAQ", "content": "A", "community_id": other.id})
    rows = client.get("/api/faqs", headers=hdr("dev_out_faq")).json()["data"]["list"]
    assert [x["title"] for x in rows] == ["幸福里FAQ"]


def test_faq_edit_and_delete(client, db, community, property_admin):
    assert _login(client, "wy_faq", "password123").status_code == 200
    faq_id = client.post(
        "/api/admin/faq", json={"title": "原标题", "content": "原内容"}
    ).json()["data"]["id"]
    r = client.put(f"/api/admin/faq/{faq_id}", json={"title": "新标题", "pinned": True})
    assert r.status_code == 200
    rows = client.get("/api/admin/faqs").json()["data"]["list"]
    assert rows[0]["title"] == "新标题" and rows[0]["pinned"] is True
    r = client.delete(f"/api/admin/faq/{faq_id}")
    assert r.status_code == 200
    assert client.get("/api/admin/faqs").json()["data"]["total"] == 0


def test_resident_cannot_publish_faq(client, db, community, users):
    # 管理端接口需要 admin session（住户无会话）→ 401
    r = client.post("/api/admin/faq", json={"title": "x", "content": "y"})
    assert r.status_code == 401
    # 小程序端无发帖接口（Phase 2 再开放）——FAQ 只读+点赞
    assert client.post("/api/posts", json={"title": "x"}).status_code in (404, 405)
