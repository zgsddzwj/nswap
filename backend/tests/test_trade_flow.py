"""交易闭环状态机：意向→接受→约定→双向确认→互评→感谢；取消回滚。"""

from tests.conftest import hdr, publish


def _setup_give_item(client):
    r = publish(client, "dev_alice", type="give", title="儿童绘本20册",
                price_cents=None, condition=None, category="book")
    assert r.status_code == 200
    return r.json()["data"]["id"]


def _want(client, openid, item_id, message="我家娃正需要"):
    r = client.post(
        f"/api/items/{item_id}/wants", json={"message": message}, headers=hdr(openid)
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


def test_full_give_trade_flow(client, db, community, users):
    item_id = _setup_give_item(client)

    # bob 提交意向 → alice 收到通知
    want_id = _want(client, "dev_bob", item_id)
    notifs = client.get(
        "/api/notifications?unread_only=true", headers=hdr("dev_alice")
    ).json()["data"]["list"]
    assert any(n["type"] == "want_received" for n in notifs)

    # alice 接受 → 产生交易与会话，物品转已预约
    r = client.put(f"/api/wants/{want_id}", json={"action": "accept"}, headers=hdr("dev_alice"))
    assert r.status_code == 200
    trade_id = r.json()["data"]["trade_id"]

    detail = client.get(f"/api/items/{item_id}", headers=hdr("dev_carol")).json()["data"]
    assert detail["status"] == "reserved"
    assert detail["can_want"] is False

    # 第三人无法再提交意向
    r = client.post(
        f"/api/items/{item_id}/wants", json={"message": "我也想要"}, headers=hdr("dev_carol")
    )
    assert r.status_code == 409

    # bob 约定交接
    r = client.patch(
        f"/api/trades/{trade_id}/arrange",
        json={"place_method": "porch", "meet_time": "2026-10-20T12:00:00Z"},
        headers=hdr("dev_bob"),
    )
    assert r.json()["data"]["status"] == "arranged"

    # 双向确认
    client.put(f"/api/trades/{trade_id}/confirm", headers=hdr("dev_alice"))
    r = client.put(f"/api/trades/{trade_id}/confirm", headers=hdr("dev_bob"))
    assert r.json()["data"]["status"] == "completed"

    # 重复确认被拒
    r = client.put(f"/api/trades/{trade_id}/confirm", headers=hdr("dev_bob"))
    assert r.status_code == 409

    # 双方互评
    r = client.post(
        f"/api/trades/{trade_id}/review",
        json={"rating": 3, "content": "书很新，谢谢"},
        headers=hdr("dev_bob"),
    )
    assert r.status_code == 200
    r = client.post(
        f"/api/trades/{trade_id}/review", json={"rating": 3}, headers=hdr("dev_alice")
    )
    assert r.status_code == 200
    # 重复评价被拒
    r = client.post(
        f"/api/trades/{trade_id}/review", json={"rating": 3}, headers=hdr("dev_alice")
    )
    assert r.status_code == 409

    # 感谢帖：give 物品的收受方是 bob
    r = client.post(
        f"/api/trades/{trade_id}/gratitude",
        json={"content": "感谢3栋邻居送的书！"},
        headers=hdr("dev_bob"),
    )
    assert r.status_code == 200
    # 物品方不能发感谢
    r = client.post(
        f"/api/trades/{trade_id}/gratitude",
        json={"content": "不客气"},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 403

    # 信用统计：alice 送出+1、被感谢+1、好评+1
    me = client.get("/api/me", headers=hdr("dev_alice")).json()["data"]["user"]
    assert me["stats"]["give_done"] == 1
    assert me["stats"]["thanks_count"] == 1
    assert me["stats"]["review_good"] == 1

    # bob 的交易列表包含已完成交易
    trades = client.get("/api/trades?status=completed", headers=hdr("dev_bob")).json()["data"]["list"]
    assert any(t["id"] == trade_id for t in trades)

    # 感谢帖进入首页横滑
    grat = client.get("/api/gratitudes", headers=hdr("dev_carol")).json()["data"]["list"]
    assert any("感谢" in g["content"] for g in grat)


def test_cancel_rolls_back_and_records_violation(client, db, community, users):
    item_id = _setup_give_item(client)
    want_id = _want(client, "dev_bob", item_id)

    r = client.put(f"/api/wants/{want_id}", json={"action": "accept"}, headers=hdr("dev_alice"))
    trade_id = r.json()["data"]["trade_id"]

    # bob（意向方）取消 → 记违约、物品回滚在售、意向作废
    r = client.put(
        f"/api/trades/{trade_id}/cancel", json={"reason": "临时有事"}, headers=hdr("dev_bob")
    )
    assert r.json()["data"]["status"] == "cancelled"

    detail = client.get(f"/api/items/{item_id}", headers=hdr("dev_carol")).json()["data"]
    assert detail["status"] == "on_sale"
    assert detail["can_want"] is True

    me = client.get("/api/me", headers=hdr("dev_bob")).json()["data"]["user"]
    assert me["stats"]["violations"] == 1

    # 已结束交易不能再确认/取消
    r = client.put(f"/api/trades/{trade_id}/confirm", headers=hdr("dev_alice"))
    assert r.status_code == 409
    r = client.put(f"/api/trades/{trade_id}/cancel", json={"reason": "x"}, headers=hdr("dev_alice"))
    assert r.status_code == 409


def test_owner_cancel_returns_want_to_pending(client, db, community, users):
    item_id = _setup_give_item(client)
    want_id = _want(client, "dev_bob", item_id)
    client.put(f"/api/wants/{want_id}", json={"action": "accept"}, headers=hdr("dev_alice"))
    trade_id = client.get("/api/trades?status=ongoing", headers=hdr("dev_alice")).json()["data"]["list"][0]["id"]

    # alice（物品方）取消 → 意向回到待选，alice 可再次接受同一意向
    client.put(f"/api/trades/{trade_id}/cancel", json={"reason": "家人要用"}, headers=hdr("dev_alice"))
    wants = client.get(f"/api/items/{item_id}/wants", headers=hdr("dev_alice")).json()["data"]["list"]
    assert wants[0]["status"] == "pending"

    # bob 的意向仍在队列中，bob 重复提交被拒（已有待处理意向）
    r = client.post(
        f"/api/items/{item_id}/wants", json={"message": "还想试试"}, headers=hdr("dev_bob")
    )
    assert r.status_code == 409

    # alice 重新接受
    r = client.put(f"/api/wants/{want_id}", json={"action": "accept"}, headers=hdr("dev_alice"))
    assert r.status_code == 200


def test_want_with_bid_and_chat(client, db, community, users):
    r = publish(client, "dev_alice", title="婴儿推车", price_cents=15000, negotiable=True, category="baby")
    item_id = r.json()["data"]["id"]

    r = client.post(
        f"/api/items/{item_id}/wants",
        json={"message": "可以便宜点吗", "bid_cents": 12000},
        headers=hdr("dev_bob"),
    )
    assert r.status_code == 200
    want_id = r.json()["data"]["id"]
    wants = client.get(f"/api/items/{item_id}/wants", headers=hdr("dev_alice")).json()["data"]["list"]
    assert wants[0]["bid_cents"] == 12000

    # bob 不能查看意向列表
    r = client.get(f"/api/items/{item_id}/wants", headers=hdr("dev_bob"))
    assert r.status_code == 403

    # 接受后双方可会话
    r = client.put(f"/api/wants/{want_id}", json={"action": "accept"}, headers=hdr("dev_alice"))
    conv_id = r.json()["data"]["conversation_id"]
    r = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "明天下午3点楼下见？"},
        headers=hdr("dev_bob"),
    )
    assert r.status_code == 200
    msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=hdr("dev_alice")).json()["data"]["list"]
    assert any(m["content"] == "明天下午3点楼下见？" for m in msgs)

    # 会话列表
    convs = client.get("/api/conversations", headers=hdr("dev_alice")).json()["data"]["list"]
    assert any(c["id"] == conv_id for c in convs)
