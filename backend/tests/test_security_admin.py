"""内容安全（risk 拒绝 / error 降级隐藏）、mediaCheck 回调、过期扫描、admin 后台。"""

from datetime import timedelta

from app.core.time import utcnow
from app.models import Item, ItemImage, SecCheck
from app.services.expiry import run_expiry_scan
from tests.conftest import hdr, make_admin, make_user, publish


def test_text_risk_rejected(client, db, community, users, monkeypatch):
    from app.services import wechat

    monkeypatch.setattr(wechat.client, "msg_sec_check", lambda *a, **k: "risk")
    r = publish(client, "dev_alice", title="违规内容")
    assert r.status_code == 400
    assert "敏感" in r.json()["message"]


def test_text_error_degrades_to_pending_hidden(client, db, community, users, monkeypatch):
    from app.services import wechat

    monkeypatch.setattr(wechat.client, "msg_sec_check", lambda *a, **k: "error")
    r = publish(client, "dev_alice", title="降级内容")
    assert r.status_code == 200
    item_id = r.json()["data"]["id"]

    # 他人 feed 不可见（fail-closed），作者自己可见
    feed = client.get("/api/items", headers=hdr("dev_bob")).json()["data"]["list"]
    assert all(i["id"] != item_id for i in feed)
    mine = client.get("/api/items?mine=true", headers=hdr("dev_alice")).json()["data"]["list"]
    assert any(i["id"] == item_id for i in mine)


def test_media_check_callback_hides_image(client, db, community, users):
    r = publish(client, "dev_alice", title="带图物品")
    item_id = r.json()["data"]["id"]

    img = ItemImage(item_id=item_id, url="http://x/1.jpg", sec_status="pending", trace_id="TRACE-1")
    db.add(img)
    db.add(SecCheck(trace_id="TRACE-1", target_type="image", target_id=None, status="processing"))
    db.commit()
    img_id = img.id
    db.query(SecCheck).filter(SecCheck.trace_id == "TRACE-1").update({"target_id": img_id})
    db.commit()

    xml = (
        "<xml><ToUserName><![CDATA[gh_x]]></ToUserName>"
        "<FromUserName><![CDATA[oX]]></FromUserName>"
        "<CreateTime>1700000000</CreateTime>"
        "<MsgType><![CDATA[event]]></MsgType>"
        "<Event><![CDATA[wxa_media_check]]></Event>"
        "<trace_id><![CDATA[TRACE-1]]></trace_id>"
        "<result><![CDATA[{\"suggest\":\"risky\",\"label\":20001}]]></result>"
        "</xml>"
    )
    r = client.post(
        "/api/wechat/callback", content=xml, headers={"Content-Type": "text/xml"}
    )
    assert r.status_code == 200
    db.expire_all()
    img = db.get(ItemImage, img_id)
    assert img.sec_status == "fail"

    # GET 验证
    r = client.get("/api/wechat/callback?echostr=123456")
    assert r.text == "123456"


def test_expiry_scan(client, db, community, users):
    u = make_user(db, "dev_old", "2栋", "老用户")
    item1 = Item(
        community_id=community.id, user_id=u.id, type="give", title="沉底物品",
        category="other", building="2栋", status="on_sale",
        last_active_at=utcnow() - timedelta(days=20),
    )
    item2 = Item(
        community_id=community.id, user_id=u.id, type="give", title="归档物品",
        category="other", building="2栋", status="sunk",
        last_active_at=utcnow() - timedelta(days=50),
    )
    db.add_all([item1, item2])
    db.commit()

    result = run_expiry_scan(db)
    assert result["sunk"] >= 1 and result["archived"] >= 1
    db.refresh(item1)
    db.refresh(item2)
    assert item1.status == "sunk"
    assert item2.status == "archived"


def test_report_and_admin_flow(client, db, community, users):
    # 用户举报物品
    r = publish(client, "dev_alice", title="被举报物品")
    item_id = r.json()["data"]["id"]
    r = client.post(
        "/api/reports",
        json={"target_type": "item", "target_id": item_id, "reason": "疑似违禁品"},
        headers=hdr("dev_bob"),
    )
    assert r.status_code == 200

    # 管理后台登录
    make_admin(db)
    r = client.post(
        "/admin/login", data={"username": "admin", "password": "nswap123"}, follow_redirects=False
    )
    assert r.status_code == 303

    # 举报处置：resolve + 自动下架
    r = client.post(
        "/admin/reports/1", data={"decision": "resolve", "apply_action": "true", "note": "已下架"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.expire_all()
    item = db.get(Item, item_id)
    assert item.status == "archived"

    # 生成邀请码（超管需显式选择目标小区）
    r = client.post(
        "/admin/invites",
        data={"building": "9栋", "count": "3", "days": "14", "batch_note": "测试批次",
              "community_id": str(community.id)},
        follow_redirects=False,
    )
    assert r.status_code == 303
    from app.models import Invite

    assert db.query(Invite).filter(Invite.building == "9栋").count() == 3

    # 错误密码登录失败
    client.cookies.clear()
    r = client.post(
        "/admin/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False
    )
    assert r.status_code == 401


def test_banned_user_blocked(client, db, community, users):
    r = publish(client, "dev_alice", title="封禁前物品")
    assert r.status_code == 200
    users["alice"].status = "banned"
    db.commit()
    r = publish(client, "dev_alice", title="封禁后物品")
    assert r.status_code == 403
