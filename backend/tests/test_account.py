"""账号注销与协议同意记录（docs/09 P0-4）。"""

from app.core.config import settings
from tests.conftest import hdr, publish


def test_agree_terms(client, db, community, users):
    # 版本不符 → 400
    r = client.post("/api/me/agree", json={"version": "1999-01"}, headers=hdr("dev_alice"))
    assert r.status_code == 400
    # 正确版本 → 记录
    r = client.post("/api/me/agree", json={"version": settings.terms_version}, headers=hdr("dev_alice"))
    assert r.status_code == 200
    me = client.get("/api/me", headers=hdr("dev_alice")).json()["data"]
    assert me["user"]["agreed_terms_version"] == settings.terms_version
    assert me["terms_version"] == settings.terms_version
    db.expire_all()
    assert users["alice"].agreed_terms_at is not None


def test_delete_requires_confirm(client, db, community, users):
    r = client.post("/api/me/delete", json={"confirm": "delete"}, headers=hdr("dev_bob"))
    assert r.status_code == 400
    assert db.get(type(users["bob"]), users["bob"].id).status == "active"


def test_delete_account_anonymizes_and_keeps_trades(client, db, community, users):
    # 先制造一笔交易：alice 发布 → bob 意向 → alice 接受
    assert publish(client, "dev_alice", title="注销测试物品").status_code == 200
    item = db.query(__import__("app.models", fromlist=["Item"]).Item).filter_by(title="注销测试物品").first()
    want = client.post(
        f"/api/items/{item.id}/wants", json={"message": "想要"}, headers=hdr("dev_bob")
    ).json()["data"]
    client.put(f"/api/wants/{want['id']}", json={"action": "accept"}, headers=hdr("dev_alice"))
    # 设置联系方式
    client.put(
        "/api/me/contact",
        json={"contact_enabled": True, "contact_wechat": "alice_wx", "contact_phone": ""},
        headers=hdr("dev_alice"),
    )

    # 注销 alice
    r = client.post("/api/me/delete", json={"confirm": "注销"}, headers=hdr("dev_alice"))
    assert r.status_code == 200

    db.expire_all()
    alice = db.get(type(users["alice"]), users["alice"].id)
    assert alice.status == "deleted" and alice.deleted_at is not None
    assert alice.nickname == f"已注销用户{alice.id}"
    assert alice.contact_wechat == "" and alice.contact_enabled is False
    # 物品已归档
    assert db.get(type(item), item.id).status == "archived"
    # 注销后任何接口 403
    assert client.get("/api/me", headers=hdr("dev_alice")).status_code == 403
    assert publish(client, "dev_alice", title="x").status_code == 403
    # 重复注销 → 403（deleted 状态被 deps 拦截）
    assert client.post("/api/me/delete", json={"confirm": "注销"}, headers=hdr("dev_alice")).status_code == 403

    # 对方视角：交易仍在，对手方昵称显示已注销
    trades = client.get("/api/trades?status=ongoing", headers=hdr("dev_bob")).json()["data"]["list"]
    assert len(trades) == 1
    assert trades[0]["counterpart"]["nickname"] == f"已注销用户{alice.id}"
    assert trades[0]["counterpart"]["building"] == "3栋"  # 同小区楼栋正常显示（隐藏规则按小区）


def test_deleted_user_cannot_rejoin(client, db, community, users):
    client.post("/api/me/delete", json={"confirm": "注销"}, headers=hdr("dev_carol"))
    # 已注销账号无法通过邀请码重新加入
    from app.models import Invite

    db.add(Invite(community_id=community.id, code="YQ-DEL00001", kind="normal", building="1栋"))
    db.commit()
    r = client.post("/api/community/join", json={"code": "YQ-DEL00001"}, headers=hdr("dev_carol"))
    assert r.status_code == 403
