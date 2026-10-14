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
    # 旧记录 openid 已腾出：同微信再次使用 → 自动重新建档为全新游客（注销=重置）
    me = client.get("/api/me", headers=hdr("dev_alice")).json()["data"]
    assert me["user"]["verified"] is False and me["community"] is None  # 全新游客
    assert me["user"]["id"] != alice.id
    assert me["user"]["nickname"] != f"已注销用户{alice.id}"

    # 已注销账号的确认参数再提交 → 403 纵深防御（直接以旧 openid 查库场景）
    # 无法从 API 触达旧账号（openid 已改名），由数据库层保证

    # 对方视角：交易仍在，对手方昵称显示已注销
    trades = client.get("/api/trades?status=ongoing", headers=hdr("dev_bob")).json()["data"]["list"]
    assert len(trades) == 1
    assert trades[0]["counterpart"]["nickname"] == f"已注销用户{alice.id}"
    assert trades[0]["counterpart"]["building"] == "3栋"  # 同小区楼栋正常显示（隐藏规则按小区）


def test_deleted_user_can_rejoin_as_new_guest(client, db, community, users):
    """注销=重置（docs/09 修订）：同微信可凭新邀请码重新加入，成为全新账号。"""
    from app.models import Invite

    db.add(Invite(community_id=community.id, code="YQ-DEL00001", kind="normal", building="1栋"))
    db.commit()
    client.post("/api/me/delete", json={"confirm": "注销"}, headers=hdr("dev_carol"))
    r = client.post("/api/community/join", json={"code": "YQ-DEL00001"}, headers=hdr("dev_carol"))
    assert r.status_code == 200
    me = r.json()["data"]
    assert me["user"]["verified"] is True and me["user"]["id"] != users["carol"].id
    # 旧账号保持匿名化且不再可用（openid 已改名，数据层隔离）
    old = users["carol"]
    db.expire_all()
    assert old.status == "deleted" and old.openid.startswith("deleted:")
