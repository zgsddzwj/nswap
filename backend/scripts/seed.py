"""初始化脚本：建表 + 社区 + 管理员 + 示例数据。

用法（在 backend/ 目录下）：
    python scripts/seed.py                      # 完整初始化（含示例数据）
    python scripts/seed.py --skip-demo          # 只建表+社区+管理员（生产用）
    python scripts/seed.py --admin-openid oXXXX # 把指定 openid 的用户提为小程序端管理员
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import AdminUser, Community, Invite, Item, User  # noqa: E402


def ensure_community(db) -> Community:
    c = db.query(Community).order_by(Community.id).first()
    if c is None:
        c = Community(name="阳光花园", address="示例地址 88 号")
        db.add(c)
        db.commit()
        db.refresh(c)
        print(f"[OK] 创建社区: {c.name} (id={c.id})")
    return c


def ensure_admin(db) -> None:
    if db.query(AdminUser).filter(AdminUser.username == "admin").first() is None:
        db.add(AdminUser(username="admin", password_hash=hash_password("nswap123"), name="超级管理员"))
        db.commit()
        print("[OK] 创建管理后台账号: admin / nswap123（上线后请立即修改！）")


def promote_openid(db, openid: str) -> None:
    u = db.query(User).filter(User.openid == openid).first()
    if u is None:
        u = User(openid=openid, nickname="管理员")
        db.add(u)
    u.role = "admin"
    db.commit()
    print(f"[OK] openid={openid} 已设为小程序端管理员")


DEMO_USERS = [
    # openid, 昵称, 楼栋
    ("dev_alice", "3栋-小艾", "3栋"),
    ("dev_bob", "5栋-老王", "5栋"),
    ("dev_carol", "8栋-卡卡", "8栋"),
]

DEMO_ITEMS = [
    # type, title, category, condition, price_cents, negotiable, want_desc, owner_openid
    ("sell", "好孩子婴儿推车 九成新", "baby", "like_new", 15000, True, None, "dev_alice"),
    ("give", "儿童绘本 20 册免费送", "book", None, None, False, None, "dev_alice"),
    ("swap", "儿童滑板车 想换绘本或滑轮鞋", "sports", "good", None, False, "绘本或滑轮鞋", "dev_bob"),
    ("want", "求购二手儿童书架", "furniture", None, None, False, "结实耐用的儿童书架", "dev_carol"),
    ("sell", "小米空气净化器 3", "appliance", "used", 12000, False, None, "dev_bob"),
]


def seed_demo(db, community: Community) -> None:
    users = {}
    for openid, nickname, building in DEMO_USERS:
        u = db.query(User).filter(User.openid == openid).first()
        if u is None:
            u = User(
                openid=openid,
                nickname=nickname,
                building=building,
                community_id=community.id,
                verified_at=utcnow(),
            )
            db.add(u)
            db.flush()
            print(f"[OK] 示例用户: {nickname} (dev openid={openid})")
        users[openid] = u
    db.commit()

    if db.query(Item).count() > 0:
        return
    for type_, title, category, condition, price, negotiable, want_desc, owner in DEMO_ITEMS:
        db.add(
            Item(
                community_id=community.id,
                user_id=users[owner].id,
                type=type_,
                title=title,
                description="示例数据：方便本地联调与小程序端演示",
                category=category,
                condition=condition,
                price_cents=price,
                negotiable=negotiable,
                want_desc=want_desc,
                building=users[owner].building,
                status="on_sale",
            )
        )
    db.commit()
    print(f"[OK] 创建 {len(DEMO_ITEMS)} 条示例物品")

    if db.query(Invite).count() == 0:
        for i in range(5):
            db.add(
                Invite(
                    community_id=community.id,
                    code=f"YQ-DEMO{i:04d}",
                    kind="normal",
                    building="1栋",
                    batch_note="seed 示例",
                )
            )
        db.commit()
        print("[OK] 创建 5 个示例邀请码（YQ-DEMO0000 起）")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-demo", action="store_true", help="不创建示例数据（生产环境）")
    parser.add_argument("--admin-openid", default="", help="提升为小程序端管理员的 openid")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    print("[OK] 数据表已就绪")
    db = SessionLocal()
    try:
        community = ensure_community(db)
        ensure_admin(db)
        if args.admin_openid:
            promote_openid(db, args.admin_openid)
        if not args.skip_demo:
            seed_demo(db, community)
    finally:
        db.close()


if __name__ == "__main__":
    main()
