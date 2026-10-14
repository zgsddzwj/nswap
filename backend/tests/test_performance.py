"""性能：feed 列表的查询数上界（N+1 回归守卫，docs/09 P1-8）。

基线（优化前）约 25 条 SQL（每行一次社区名查询）；优化后应 ≤ 8。
"""

from sqlalchemy import event

from tests.conftest import hdr, publish

QUERY_BUDGET = 8  # feed 一页（20 条）允许的最大 SQL 数


def _count_queries(db, fn):
    counter = {"n": 0}

    def _on_execute(*_args, **_kwargs):
        counter["n"] += 1

    event.listen(db.bind, "before_cursor_execute", _on_execute)
    try:
        result = fn()
    finally:
        event.remove(db.bind, "before_cursor_execute", _on_execute)
    return result, counter["n"]


def test_items_feed_query_budget(client, db, community, users):
    for i in range(5):
        assert publish(client, "dev_alice", title=f"查询预算物品{i}").status_code == 200
    _, count = _count_queries(
        db, lambda: client.get("/api/items?limit=20", headers=hdr("dev_bob"))
    )
    assert count <= QUERY_BUDGET, f"feed 查询数 {count} 超过预算 {QUERY_BUDGET}（N+1 回归）"


def test_city_feed_query_budget(client, db, community, users):
    from app.models import Community, User
    from app.core.time import utcnow

    other = Community(name="幸福里", city="测试市")
    db.add(other)
    db.commit()
    db.add(User(openid="dev_dave2", nickname="大伟", building="1栋", community_id=other.id, verified_at=utcnow()))
    db.commit()
    for i in range(5):
        assert publish(client, "dev_alice", title=f"同城预算{i}").status_code == 200
    _, count = _count_queries(
        db, lambda: client.get("/api/items?scope=city&limit=20", headers=hdr("dev_bob"))
    )
    assert count <= QUERY_BUDGET, f"同城 feed 查询数 {count} 超过预算（N+1 回归）"


def test_message_board_queries_constant(client, db, community, users):
    """留言板查询数应恒定（不随留言行数增长）——N+1 的本质守卫。"""
    assert publish(client, "dev_alice", title="留言预算物品").status_code == 200
    from app.models import Item

    item = db.query(Item).filter_by(title="留言预算物品").first()
    for i in range(5):
        client.post(
            f"/api/items/{item.id}/messages", json={"content": f"留言{i}"}, headers=hdr("dev_bob")
        )
    _, count_small = _count_queries(
        db, lambda: client.get(f"/api/items/{item.id}/messages", headers=hdr("dev_bob"))
    )
    for i in range(15):
        client.post(
            f"/api/items/{item.id}/messages", json={"content": f"追加{i}"}, headers=hdr("dev_bob")
        )
    _, count_large = _count_queries(
        db, lambda: client.get(f"/api/items/{item.id}/messages", headers=hdr("dev_bob"))
    )
    assert count_large <= count_small + 1, (
        f"留言从 5 条增到 20 条后查询数 {count_small}→{count_large}，存在 N+1"
    )
