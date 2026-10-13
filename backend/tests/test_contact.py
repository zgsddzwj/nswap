"""联系方式交换：默认不开放、会员（已验证）限次交换、幂等、双向留痕。"""

import pytest

from tests.conftest import hdr, publish


def _enable_contact(client, openid, wechat="wang_weixin", phone="13800138000"):
    r = client.put(
        "/api/me/contact",
        json={"contact_enabled": True, "contact_wechat": wechat, "contact_phone": phone},
        headers=hdr(openid),
    )
    assert r.status_code == 200
    return r.json()["data"]


def _make_conversation(client, item_owner="dev_alice", wanter="dev_bob", title="测试物品"):
    """发布→意向→接受，产生会话；返回 conversation_id。"""
    r = publish(client, item_owner, title=title)
    assert r.status_code == 200
    item_id = r.json()["data"]["id"]
    r = client.post(
        f"/api/items/{item_id}/wants", json={"message": "想要"}, headers=hdr(wanter)
    )
    assert r.status_code == 200
    want_id = r.json()["data"]["id"]
    r = client.put(
        f"/api/wants/{want_id}", json={"action": "accept"}, headers=hdr(item_owner)
    )
    assert r.status_code == 200
    return r.json()["data"]["conversation_id"]


def test_contact_settings_validation(client, db, community, users):
    # 微信号格式校验
    r = client.put(
        "/api/me/contact",
        json={"contact_enabled": True, "contact_wechat": "不合法!!", "contact_phone": ""},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 400
    # 手机号格式校验
    r = client.put(
        "/api/me/contact",
        json={"contact_enabled": True, "contact_wechat": "", "contact_phone": "123"},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 400
    # 开启但什么都没填 → 拒绝
    r = client.put(
        "/api/me/contact",
        json={"contact_enabled": True, "contact_wechat": "", "contact_phone": ""},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 400
    # 正常开启
    data = _enable_contact(client, "dev_alice")
    assert data["contact_enabled"] is True
    # 只读自己的设置
    r = client.get("/api/me/contact", headers=hdr("dev_alice"))
    assert r.json()["data"]["contact_wechat"] == "wang_weixin"


def test_exchange_requires_counterpart_opt_in(client, db, community, users):
    conv_id = _make_conversation(client)
    # alice 从未开放联系方式 → bob 交换被拒（且不提示任何联系方式）
    r = client.post(f"/api/conversations/{conv_id}/contact", headers=hdr("dev_bob"))
    assert r.status_code == 400
    # alice 开放后即可交换
    _enable_contact(client, "dev_alice")
    r = client.post(f"/api/conversations/{conv_id}/contact", headers=hdr("dev_bob"))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["exchanged"] is True
    assert data["contact"]["wechat"] == "wang_weixin"
    assert data["counterpart"]["nickname"] == "3栋-小艾"


def test_exchange_idempotent_and_notifies(client, db, community, users):
    conv_id = _make_conversation(client)
    _enable_contact(client, "dev_alice")

    r1 = client.post(f"/api/conversations/{conv_id}/contact", headers=hdr("dev_bob"))
    assert r1.status_code == 200
    remaining_first = r1.json()["data"]["remaining_today"]

    # 同会话重复请求：幂等，不再扣额度
    r2 = client.post(f"/api/conversations/{conv_id}/contact", headers=hdr("dev_bob"))
    assert r2.status_code == 200
    assert r2.json()["data"]["remaining_today"] == remaining_first

    # 双向解锁：alice 也能看到 bob 的联系方式（bob 未开放则 contact 为 None）
    r = client.get(f"/api/conversations/{conv_id}/contact", headers=hdr("dev_alice"))
    data = r.json()["data"]
    assert data["exchanged"] is True

    # 被查看方收到通知且知道是谁
    notifs = client.get(
        "/api/notifications?unread_only=true", headers=hdr("dev_alice")
    ).json()["data"]["list"]
    assert any(n["type"] == "contact_exchanged" for n in notifs)

    # 未交换前 GET 状态不泄露联系方式
    conv2 = _make_conversation(client, title="测试物品2")
    r = client.get(f"/api/conversations/{conv2}/contact", headers=hdr("dev_bob"))
    data = r.json()["data"]
    assert data["exchanged"] is False and data["contact"] is None


def test_daily_quota_limit(client, db, community, users):
    _enable_contact(client, "dev_alice")
    convs = [_make_conversation(client, title=f"额度物品{i}") for i in range(4)]

    for i, conv_id in enumerate(convs[:3]):
        r = client.post(f"/api/conversations/{conv_id}/contact", headers=hdr("dev_bob"))
        assert r.status_code == 200, f"第 {i + 1} 次交换应成功"
        assert r.json()["data"]["remaining_today"] == 3 - (i + 1)

    # 第 4 次：当日额度用尽 → 429
    r = client.post(f"/api/conversations/{convs[3]}/contact", headers=hdr("dev_bob"))
    assert r.status_code == 429

    # alice 未发起过交换：额度未消耗。她对已交换过的会话再请求 → 幂等不扣额度（剩 3）
    _enable_contact(client, "dev_bob")
    r = client.post(f"/api/conversations/{convs[0]}/contact", headers=hdr("dev_alice"))
    assert r.status_code == 200
    assert r.json()["data"]["remaining_today"] == 3

    # alice 对未交换过的会话发起 → 正常扣 1 次额度（剩 2）
    r = client.post(f"/api/conversations/{convs[3]}/contact", headers=hdr("dev_alice"))
    assert r.status_code == 200
    assert r.json()["data"]["remaining_today"] == 2


def test_contact_hidden_from_other_serializers(client, db, community, users):
    """隐私底线：联系方式绝不出现在任何既有序列化（主页/物品详情/会话列表）。"""
    _enable_contact(client, "dev_alice")
    conv_id = _make_conversation(client)
    client.post(f"/api/conversations/{conv_id}/contact", headers=hdr("dev_bob"))

    alice_id = client.get("/api/me", headers=hdr("dev_alice")).json()["data"]["user"]["id"]
    profile = client.get(f"/api/users/{alice_id}", headers=hdr("dev_bob")).json()["data"]
    assert "contact_wechat" not in profile["user"]
    assert "wang_weixin" not in str(profile)

    convs = client.get("/api/conversations", headers=hdr("dev_bob")).json()["data"]["list"]
    assert "wang_weixin" not in str(convs)
