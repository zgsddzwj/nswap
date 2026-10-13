"""多社区 SaaS：feed 双 scope、跨小区隐私、举报归属、公告隔离、admin 分权。"""

import pytest

from app.core.security import hash_password
from app.core.time import utcnow
from app.models import AdminUser, Announcement, Community, Invite, Item, Report, User, VerifyRequest
from tests.conftest import hdr, make_admin, publish


def make_community(db, name="幸福里", city="测试市"):
    c = Community(name=name, city=city, district="高新区")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def make_community_user(db, c, openid, building="1栋", nickname=None):
    u = User(
        openid=openid,
        nickname=nickname or openid,
        building=building,
        community_id=c.id,
        verified_at=utcnow(),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u



@pytest.fixture()
def community2(db):
    return make_community(db)


@pytest.fixture()
def dave(db, community2):
    return make_community_user(db, community2, "dev_dave", "2栋", "2栋-大伟")


# ---------------- feed 双 scope 与跨小区隐私 ----------------

def test_feed_scopes_and_cross_privacy(client, db, community, users, community2, dave):
    assert publish(client, "dev_alice", title="本小区物品").status_code == 200
    assert publish(client, "dev_dave", title="外小区物品").status_code == 200

    # 本小区 scope：只见本小区
    feed = client.get("/api/items?scope=community", headers=hdr("dev_bob")).json()["data"]
    titles = [x["title"] for x in feed["list"]]
    assert "本小区物品" in titles and "外小区物品" not in titles

    # 同城 scope：两小区都可见；跨小区卡 building 空 + community_name
    feed = client.get("/api/items?scope=city", headers=hdr("dev_bob")).json()["data"]
    cards = {x["title"]: x for x in feed["list"]}
    assert {"本小区物品", "外小区物品"} <= set(cards)
    assert cards["外小区物品"]["building"] == ""
    assert cards["外小区物品"]["community_name"] == "幸福里"
    assert cards["本小区物品"]["building"] == "3栋"
    assert cards["本小区物品"]["community_name"] == "阳光花园"

    # item_detail：bob 看 dave 的物品 → seller building 隐藏
    det = client.get(f"/api/items/{cards['外小区物品']['id']}", headers=hdr("dev_bob")).json()["data"]
    assert det["seller"]["building"] == "" and det["seller"]["community_name"] == "幸福里"
    assert det["community_name"] == "幸福里"

    # 停用小区不出现在同城
    community2.status = "suspended"
    db.commit()
    feed = client.get("/api/items?scope=city", headers=hdr("dev_bob")).json()["data"]
    assert all(x["title"] != "外小区物品" for x in feed["list"])


def test_city_excludes_empty_city(client, db, community, users):
    """city 为空的老小区不出现在同城（回填前的历史数据）。"""
    assert publish(client, "dev_alice", title="无城物品").status_code == 200
    community.city = ""
    db.commit()
    feed = client.get("/api/items?scope=city", headers=hdr("dev_bob")).json()["data"]
    assert all(x["title"] != "无城物品" for x in feed["list"])
    # 本小区 scope 不受影响
    feed = client.get("/api/items?scope=community", headers=hdr("dev_bob")).json()["data"]
    assert any(x["title"] == "无城物品" for x in feed["list"])


def test_profile_cross_building_hidden(client, db, community, users, community2, dave):
    # 跨小区查看主页：building 隐藏 + community_name
    r = client.get(f"/api/users/{dave.id}", headers=hdr("dev_alice")).json()["data"]
    assert r["user"]["building"] == "" and r["user"]["community_name"] == "幸福里"
    # 同小区查看：building 正常
    alice = client.get("/api/me", headers=hdr("dev_alice")).json()["data"]["user"]
    r = client.get(f"/api/users/{alice['id']}", headers=hdr("dev_bob")).json()["data"]
    assert r["user"]["building"] == "3栋"


# ---------------- 邀请码/人工审核绑定正确小区 ----------------

def test_join_binds_invite_community(client, db, community, community2):
    inv = Invite(community_id=community2.id, code="YQ-XFLE0001", kind="normal", building="5栋")
    db.add(inv)
    db.commit()
    r = client.post("/api/community/join", json={"code": "yq-xfle0001"}, headers=hdr("dev_new2"))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user"]["verified"] is True
    assert data["community"]["name"] == "幸福里"


def test_manual_apply_requires_community(client, db, community, community2):
    r = client.post(
        "/api/community/manual-apply",
        json={"building": "1栋", "unit": "", "proof_image": "http://x/p.jpg"},
        headers=hdr("dev_new3"),
    )
    assert r.status_code == 422  # community_id 必填
    r = client.post(
        "/api/community/manual-apply",
        json={"community_id": community2.id, "building": "1栋", "unit": "",
              "proof_image": "http://x/p.jpg"},
        headers=hdr("dev_new3"),
    )
    assert r.status_code == 200
    vr = db.query(VerifyRequest).order_by(VerifyRequest.id.desc()).first()
    assert vr.community_id == community2.id
    # 停用小区拒绝
    community2.status = "suspended"
    db.commit()
    r = client.post(
        "/api/community/manual-apply",
        json={"community_id": community2.id, "building": "1栋", "unit": "",
              "proof_image": "http://x/p.jpg"},
        headers=hdr("dev_new4"),
    )
    assert r.status_code == 400


def test_public_communities_search(client, db, community, community2):
    r = client.get("/api/communities?keyword=幸福", headers=hdr("dev_alice"))
    rows = r.json()["data"]["list"]
    assert [x["name"] for x in rows] == ["幸福里"]
    assert "address" not in rows[0]  # 公开接口不暴露精确地址


# ---------------- 举报归属（R2） ----------------

def test_report_attributed_to_target_community(client, db, community, users, community2, dave):
    assert publish(client, "dev_dave", title="被举报的外小区物品").status_code == 200
    item = db.query(Item).filter(Item.title == "被举报的外小区物品").first()
    r = client.post(
        "/api/reports",
        json={"target_type": "item", "target_id": item.id, "reason": "涉嫌虚假"},
        headers=hdr("dev_alice"),  # 举报人在 community1
    )
    assert r.status_code == 200
    report = db.query(Report).order_by(Report.id.desc()).first()
    assert report.community_id == community2.id  # 归属被举报内容的小区


# ---------------- 跨小区交接方式（R4） ----------------

def test_arrange_cross_community_face_only(client, db, community, users, community2, dave):
    assert publish(client, "dev_dave", title="跨小区交易品").status_code == 200
    item = db.query(Item).filter(Item.title == "跨小区交易品").first()
    want = client.post(
        f"/api/items/{item.id}/wants", json={"message": "想要"}, headers=hdr("dev_alice")
    ).json()["data"]
    acc = client.put(
        f"/api/wants/{want['id']}", json={"action": "accept"}, headers=hdr("dev_dave")
    ).json()["data"]
    tid = acc["trade_id"]
    # porch → 400
    r = client.patch(
        f"/api/trades/{tid}/arrange",
        json={"place_method": "porch", "meet_time": "2026-10-20T12:00:00Z"},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 400
    # face → 成功
    r = client.patch(
        f"/api/trades/{tid}/arrange",
        json={"place_method": "face", "meet_time": "2026-10-20T12:00:00Z"},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 200


# ---------------- 公告隔离 ----------------

def test_announcements_isolation(client, db, community, users, community2, dave):
    db.add(Announcement(community_id=community.id, title="阳光花园公告", content="周六交换日"))
    db.add(Announcement(community_id=community2.id, title="幸福里公告", content="停水通知"))
    db.commit()
    rows = client.get("/api/announcements", headers=hdr("dev_alice")).json()["data"]["list"]
    assert [x["title"] for x in rows] == ["阳光花园公告"]
    rows = client.get("/api/announcements", headers=hdr("dev_dave")).json()["data"]["list"]
    assert [x["title"] for x in rows] == ["幸福里公告"]
    # 游客为空
    client.post("/api/auth/login", headers=hdr("dev_guest2"))
    rows = client.get("/api/announcements", headers=hdr("dev_guest2")).json()["data"]["list"]
    assert rows == []


# ---------------- 管理后台分权（R3） ----------------

@pytest.fixture()
def property_admin(db, community):
    a = AdminUser(
        username="wy_test", password_hash=hash_password("password123"),
        name="测试物业", community_id=community.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _login_admin(client, username, password):
    return client.post(
        "/admin/login", data={"username": username, "password": password}, follow_redirects=False
    )


def test_property_admin_scoped(client, db, community, community2, users, dave, property_admin):
    assert _login_admin(client, "wy_test", "password123").status_code == 303
    # 页面只见本小区数据
    html = client.get("/admin/invites").text
    assert "阳光花园" in html and "幸福里" not in html
    html = client.get("/admin/users").text
    assert "2栋-大伟" not in html
    # 手输超管页面 → 403
    assert client.get("/admin/communities").status_code == 403
    assert client.get("/admin/sec-checks").status_code == 403
    # 跨小区写操作 → 403
    r = client.post(f"/admin/users/{dave.id}/ban", follow_redirects=False)
    assert r.status_code == 403


def test_super_admin_global_view(client, db, community, community2, users, dave, property_admin):
    make_admin(db)
    assert _login_admin(client, "admin", "nswap123").status_code == 303
    html = client.get("/admin/communities").text
    assert "阳光花园" in html and "幸福里" in html
    html = client.get("/admin/users").text
    assert "2栋-大伟" in html  # 超管全局可见
    # 超管创建小区 + 物业账号
    r = client.post(
        "/admin/communities",
        data={"name": "翡翠湾", "city": "测试市", "district": "", "address": "",
              "admin_username": "wy_fcw", "admin_name": "翡翠湾物业", "admin_password": "password456"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    c = db.query(Community).filter(Community.name == "翡翠湾").first()
    assert c is not None and c.city == "测试市"
    a = db.query(AdminUser).filter(AdminUser.username == "wy_fcw").first()
    assert a is not None and a.community_id == c.id


def test_admin_announcements_and_password(client, db, community, property_admin):
    assert _login_admin(client, "wy_test", "password123").status_code == 303
    # 物业发布公告（自动绑定本小区）
    r = client.post(
        "/admin/announcements",
        data={"title": "本周六交换日", "content": "9:00 小区广场"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    ann = db.query(Announcement).order_by(Announcement.id.desc()).first()
    assert ann.community_id == community.id and ann.title == "本周六交换日"
    # 删除
    r = client.post(f"/admin/announcements/{ann.id}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert db.query(Announcement).count() == 0
    # 自助改密码
    r = client.post(
        "/admin/password",
        data={"old_password": "password123", "new_password": "newpass456"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert _login_admin(client, "wy_test", "newpass456").status_code == 303
