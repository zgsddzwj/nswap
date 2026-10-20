"""P1 批次修复的回归测试：物品图 fail-closed、会话未读、凭证图鉴权读取。"""

import io

from PIL import Image

from app.models import SecCheck
from tests.conftest import hdr, make_admin, publish


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 100, 100)).save(buf, format="JPEG")
    return buf.getvalue()


def test_item_image_api_error_fail_closed(client, db, community, users, monkeypatch):
    """token 模式下检测接口不可用：图片保持 pending（先发后撤），并落 error 记录进待审。"""
    from app.core.config import settings
    from app.services import wechat

    monkeypatch.setattr(settings, "wx_call_mode", "token")
    monkeypatch.setattr(wechat.client, "media_check_async", lambda *a, **k: None)
    url = "http://82.157.59.122/nswap/uploads/x.jpg"
    r = publish(client, "dev_alice", title="降级图片", images=[url])
    assert r.status_code == 200
    assert r.json()["data"]["images"] == [url]  # 仍展示（先发后撤）
    assert (
        db.query(SecCheck)
        .filter(SecCheck.status == "error", SecCheck.target_type == "image")
        .count()
        >= 1
    )


def test_item_image_normal_registration(client, db, community, users, monkeypatch):
    """token 模式正常路径：图片 pending + trace_id 登记。"""
    from app.core.config import settings
    from app.services import wechat

    monkeypatch.setattr(settings, "wx_call_mode", "token")
    monkeypatch.setattr(wechat.client, "media_check_async", lambda *a, **k: "TRACE-IMG")
    r = publish(client, "dev_alice", title="正常图片", images=["http://x/y.jpg"])
    assert r.status_code == 200
    row = db.query(SecCheck).filter(SecCheck.trace_id == "TRACE-IMG").first()
    assert row is not None and row.target_type == "image"


def test_conversation_unread_flow(client, db, community, users):
    """未读计数：对方发消息 unread+1；我查看后归零。"""
    r = publish(client, "dev_alice", title="未读测试")
    item_id = r.json()["data"]["id"]
    r = client.post(f"/api/items/{item_id}/wants", json={"message": "想要"}, headers=hdr("dev_bob"))
    want_id = r.json()["data"]["id"]
    r = client.put(f"/api/wants/{want_id}", json={"action": "accept"}, headers=hdr("dev_alice"))
    conv_id = r.json()["data"]["conversation_id"]

    client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "你好呀"}, headers=hdr("dev_bob")
    )
    convs = client.get("/api/conversations", headers=hdr("dev_alice")).json()["data"]["list"]
    assert next(c for c in convs if c["id"] == conv_id)["unread"] == 1

    # bob 自己看自己发的消息：不计未读
    convs_b = client.get("/api/conversations", headers=hdr("dev_bob")).json()["data"]["list"]
    assert next(c for c in convs_b if c["id"] == conv_id)["unread"] == 0

    # alice 查看后归零
    client.get(f"/api/conversations/{conv_id}/messages", headers=hdr("dev_alice"))
    convs = client.get("/api/conversations", headers=hdr("dev_alice")).json()["data"]["list"]
    assert next(c for c in convs if c["id"] == conv_id)["unread"] == 0


def test_conversations_ordered_by_last_message(client, db, community, users):
    """有消息的会话排在前面（按最近消息时间），而非建会话顺序。"""
    ids = []
    for title in ("排序A", "排序B"):
        r = publish(client, "dev_alice", title=title)
        item_id = r.json()["data"]["id"]
        r = client.post(f"/api/items/{item_id}/wants", json={"message": "换"}, headers=hdr("dev_bob"))
        r = client.put(f"/api/wants/{r.json()['data']['id']}", json={"action": "accept"}, headers=hdr("dev_alice"))
        ids.append(r.json()["data"]["conversation_id"])
    # 给先建的会话（A）发消息 → A 应排最前
    client.post(
        f"/api/conversations/{ids[0]}/messages", json={"content": "顶一下"}, headers=hdr("dev_bob")
    )
    convs = client.get("/api/conversations", headers=hdr("dev_alice")).json()["data"]["list"]
    assert convs[0]["id"] == ids[0]


def test_proof_upload_admin_only_read(client, db, community, users):
    """凭证图：上传返回鉴权 URL；无会话 401；管理员会话 200。"""
    r = client.post(
        "/api/uploads?kind=proof",
        files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 200
    url = r.json()["data"]["url"]
    assert "/api/admin/proofs/" in url
    filename = url.rsplit("/", 1)[1]

    r2 = client.get(f"/api/admin/proofs/{filename}")
    assert r2.status_code == 401  # 无管理员会话

    make_admin(db)
    client.post("/api/admin/auth/login", json={"username": "admin", "password": "nswap123"})
    r3 = client.get(f"/api/admin/proofs/{filename}")
    assert r3.status_code == 200
    assert r3.headers["content-type"].startswith("image/")


def test_proof_upload_rejects_bad_kind_and_path_traversal(client, db, community, users):
    r = client.post(
        "/api/uploads?kind=evil",
        files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=hdr("dev_alice"),
    )
    assert r.status_code == 400
    # 路径穿越文件名（应被白名单拒绝）
    make_admin(db)
    client.post("/api/admin/auth/login", json={"username": "admin", "password": "nswap123"})
    r2 = client.get("/api/admin/proofs/..%2F..%2F.env")
    assert r2.status_code in (400, 404)
