import os

# 必须在导入 app 之前设置（settings 与 engine 在导入时初始化）
os.environ["ENV"] = "dev"
os.environ["DATABASE_URL"] = "sqlite:///./test_nswap.db"
os.environ["WX_CALL_MODE"] = "mock"
os.environ["ENABLE_SCHEDULER"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminUser, Community, Invite, Item, User  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def community(db):
    c = Community(name="阳光花园", address="测试地址", city="测试市")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def make_user(db, openid, building="3栋", nickname=None):
    u = User(
        openid=openid,
        nickname=nickname or openid,
        building=building,
        community_id=1,
        verified_at=utcnow(),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def users(db, community):
    return {
        "alice": make_user(db, "dev_alice", "3栋", "3栋-小艾"),
        "bob": make_user(db, "dev_bob", "5栋", "5栋-老王"),
        "carol": make_user(db, "dev_carol", "8栋", "8栋-卡卡"),
    }


def hdr(openid: str) -> dict:
    return {"X-DEV-OPENID": openid}


def publish(client, openid, **overrides):
    payload = {
        "type": "sell",
        "title": "测试物品",
        "description": "描述",
        "category": "other",
        "condition": "good",
        "price_cents": 1000,
        "negotiable": False,
        "want_desc": None,
        "bid_cents": None,
        "images": [],
    }
    payload.update(overrides)
    return client.post("/api/items", json=payload, headers=hdr(openid))


def make_admin(db):
    admin = AdminUser(username="admin", password_hash=hash_password("nswap123"), name="管理员")
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
