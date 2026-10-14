"""管理后台运营工具：操作日志/待审内容闭环/导出/趋势/公告编辑（docs/09 P1-6/7/10）。"""

import pytest

from app.core.security import hash_password
from app.models import AdminUser, Announcement, Community, Item, ItemMessage, User
from tests.conftest import hdr, make_admin, publish


@pytest.fixture()
def property_admin(db, community):
    a = AdminUser(
        username="wy_tools", password_hash=hash_password("password123"),
        name="测试物业", community_id=community.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _login(client, username, password):
    return client.post("/api/admin/auth/login", json={"username": username, "password": password})


# ---------------- 操作日志（P1-6） ----------------

def test_admin_logs_scoped(client, db, community, users, property_admin):
    make_admin(db)
    # 物业做一次操作（生成邀请码）
    assert _login(client, "wy_tools", "password123").status_code == 200
    client.post("/api/admin/invites", json={"building": "1栋", "count": 1, "days": 7})
    rows = client.get("/api/admin/logs").json()["data"]["list"]
    assert rows and all(r["action"] == "create_invites" for r in rows)
    assert all(r["admin_name"] == "测试物业" for r in rows)

    # 超管看全部（含物业的操作）
    client.cookies.clear()
    assert _login(client, "admin", "nswap123").status_code == 200
    all_rows = client.get("/api/admin/logs").json()["data"]["list"]
    assert any(r["admin_name"] == "测试物业" for r in all_rows)


# ---------------- 待审内容闭环（P1-7） ----------------

def test_pending_content_approve_and_reject(client, db, community, users, property_admin):
    # 造两条 pending 内容（模拟 msgSecCheck 异常降级）
    assert publish(client, "dev_alice", title="待审物品").status_code == 200
    item = db.query(Item).filter_by(title="待审物品").first()
    item.sec_status = "pending"
    assert publish(client, "dev_bob", title="留言来源物").status_code == 200
    src = db.query(Item).filter_by(title="留言来源物").first()
    msg = ItemMessage(item_id=src.id, user_id=users["alice"].id, content="待审留言", sec_status="pending")
    db.add(msg)
    db.commit()

    assert _login(client, "wy_tools", "password123").status_code == 200
    data = client.get("/api/admin/pending-content").json()["data"]
    assert data["items_total"] == 1 and data["messages_total"] == 1
    assert data["items"][0]["title"] == "待审物品"

    # 放行物品 → pass（列表可见）
    r = client.post(f"/api/admin/pending-content/item/{item.id}/approve")
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Item, item.id).sec_status == "pass"

    # 拒绝留言 → hidden + 作者收通知
    r = client.post(f"/api/admin/pending-content/message/{msg.id}/reject")
    assert r.status_code == 200
    db.expire_all()
    assert db.get(ItemMessage, msg.id).status == "hidden"
    notifs = client.get("/api/notifications?unread_only=true", headers=hdr("dev_alice")).json()["data"]["list"]
    assert any(n["type"] == "content_rejected" for n in notifs)
    # 重复处置 → 400
    assert client.post(f"/api/admin/pending-content/message/{msg.id}/reject").status_code == 400


def test_pending_content_cross_community_forbidden(client, db, community, users, property_admin):
    other = Community(name="幸福里", city="测试市")
    db.add(other)
    db.commit()
    outsider = User(openid="dev_out", nickname="外部", community_id=other.id, verified_at=__import__("app.core.time", fromlist=["utcnow"]).utcnow())
    db.add(outsider)
    db.commit()
    item = Item(community_id=other.id, user_id=outsider.id, type="give", title="外小区待审",
                category="other", building="1栋", status="on_sale", sec_status="pending")
    db.add(item)
    db.commit()
    assert _login(client, "wy_tools", "password123").status_code == 200
    assert client.get("/api/admin/pending-content").json()["data"]["items_total"] == 0  # 物业看不到
    assert client.post(f"/api/admin/pending-content/item/{item.id}/approve").status_code == 403


# ---------------- 导出与趋势（P1-10） ----------------

def test_export_csv(client, db, community, users):
    make_admin(db)
    assert publish(client, "dev_alice", title="导出物品").status_code == 200
    assert _login(client, "admin", "nswap123").status_code == 200

    r = client.get("/api/admin/users/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.decode("utf-8").startswith("\ufeff")  # BOM 防乱码
    assert "昵称" in r.content.decode("utf-8")

    client.post("/api/admin/invites", json={"building": "2栋", "count": 2, "days": 7, "community_id": community.id})
    r = client.get("/api/admin/invites/export")
    body = r.content.decode("utf-8")
    assert "邀请码" in body and body.count("\n") >= 2


def test_stats_trend(client, db, community, users):
    make_admin(db)
    assert publish(client, "dev_alice", title="趋势物品").status_code == 200
    assert _login(client, "admin", "nswap123").status_code == 200
    series = client.get("/api/admin/stats/trend?days=7").json()["data"]["series"]
    assert len(series) == 7
    assert sum(x["items"] for x in series) >= 1
    assert {"date", "users", "items", "trades"} <= set(series[0])


# ---------------- 公告编辑与置顶（P1-10） ----------------

def test_announcement_edit_and_pin_order(client, db, community, users, property_admin):
    assert _login(client, "wy_tools", "password123").status_code == 200
    r1 = client.post("/api/admin/announcements", json={"title": "普通公告", "content": "内容A"})
    r2 = client.post("/api/admin/announcements", json={"title": "待置顶", "content": "内容B"})
    a2_id = r2.json()["data"]["id"]

    # 编辑 + 置顶
    r = client.put(f"/api/admin/announcements/{a2_id}", json={"title": "置顶公告", "pinned": True})
    assert r.status_code == 200
    rows = client.get("/api/admin/announcements").json()["data"]["list"]
    assert rows[0]["title"] == "置顶公告" and rows[0]["pinned"] is True  # 置顶排最前

    # 小程序端公告列表同样置顶优先
    mini = client.get("/api/announcements", headers=hdr("dev_alice")).json()["data"]["list"]
    assert mini[0]["title"] == "置顶公告"
