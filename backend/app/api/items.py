from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.deps import (
    count_active_items,
    count_today_items,
    get_current_user,
    get_db,
    get_verified_user,
)
from app.core.errors import bad_request, conflict, forbidden, not_found, too_many
from app.services.categorize import guess_category
from app.core.time import utcnow
from app.models import Item, ItemWant, Transaction, User
from app.schemas import ItemPayload
from app.schemas.serialize import (
    CATEGORIES,
    CONDITIONS,
    ITEM_TYPES,
    item_cards,
    item_detail,
    ok,
)
from app.services.sec_check import check_text, register_item_images

router = APIRouter(tags=["items"])

MAX_PER_DAY = 5
MAX_ACTIVE = 20
RENEW_COOLDOWN_HOURS = 72


def _encode_cursor(ts: datetime, item_id: int) -> str:
    return f"{int(ts.timestamp())}|{item_id}"


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    ts_str, id_str = cursor.split("|", 1)
    return datetime.fromtimestamp(int(ts_str)), int(id_str)


def _validate_payload(p: ItemPayload) -> None:
    if p.type not in ITEM_TYPES:
        raise bad_request("物品类型不合法")
    # 分类免选（docs/11）：None/非法值在落库前自动识别，不再强制校验
    if p.condition is not None and p.condition not in CONDITIONS:
        raise bad_request("成色不合法")
    if p.type == "sell":
        if not p.price_cents or p.price_cents <= 0:
            raise bad_request("出售物品请填写价格")
        if p.price_cents > 100_000_00:
            raise bad_request("价格超出上限（10万元）")
    if p.type in ("swap", "want") and not (p.want_desc or "").strip():
        raise bad_request("请填写想换什么/想要什么")
    if len(p.images) > 9:
        raise bad_request("图片最多 9 张")
    for url in p.images:
        if not url.startswith("http"):
            raise bad_request("图片地址不合法")


@router.get("/items")
def list_items(
    type: str | None = None,
    category: str | None = None,
    building: str | None = None,
    keyword: str | None = None,
    status: str | None = None,
    mine: bool = Query(default=False),
    scope: str = Query(default="community"),  # community|city（docs/07 §4.3）
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if type is not None and type not in ITEM_TYPES:
        raise bad_request("类型筛选不合法")

    q = db.query(Item)
    if mine:
        q = q.filter(Item.user_id == user.id)
        if status:
            q = q.filter(Item.status == status)
        q = q.order_by(Item.created_at.desc(), Item.id.desc())
        order_ts_col, order_id_col = Item.created_at, Item.id
    else:
        q = q.filter(Item.status.in_(["on_sale", "reserved"]))
        # 文本审核降级（pending）内容：仅作者本人与管理员可见
        q = q.filter(
            or_(Item.sec_status == "pass", Item.user_id == user.id, user.role == "admin")
        )
        if scope == "city":
            # 同城：本小区所在城市的全部 active 小区（docs/09 修订：准入制，
            # 未加入小区的游客返回空列表并引导验证，不再开放浏览）
            from app.models import Community

            if not user.community_id:
                return ok({"list": [], "next_cursor": None})
            own = db.get(Community, user.community_id)
            city_q = db.query(Community.id).filter(
                Community.status == "active", Community.city != ""
            )
            if own and own.city:
                city_q = city_q.filter(Community.city == own.city)
            q = q.filter(Item.community_id.in_(city_q))
        elif user.community_id:
            # 本小区（默认）
            q = q.filter(Item.community_id == user.community_id)
        else:
            # 未加入小区：本小区 Tab 返回空
            return ok({"list": [], "next_cursor": None})
        if type:
            q = q.filter(Item.type == type)
        if category:
            q = q.filter(Item.category == category)
        if building and scope == "community":
            # 同城模式无楼栋概念，忽略该筛选（docs/07 §4.3）
            q = q.filter(Item.building == building)
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.filter(or_(Item.title.like(like), Item.description.like(like)))
        q = q.order_by(Item.last_active_at.desc(), Item.id.desc())
        order_ts_col, order_id_col = Item.last_active_at, Item.id

    if cursor:
        try:
            ts, last_id = _decode_cursor(cursor)
        except (ValueError, IndexError):
            raise bad_request("分页参数错误")
        q = q.filter(or_(order_ts_col < ts, and_(order_ts_col == ts, order_id_col < last_id)))

    items = q.limit(limit + 1).all()
    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        last = items[-1]
        ts = last.created_at if mine else last.last_active_at
        next_cursor = _encode_cursor(ts, last.id)

    return ok({"list": item_cards(db, items, user), "next_cursor": next_cursor})


@router.post("/items")
def create_item(
    payload: ItemPayload,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    _validate_payload(payload)
    if count_today_items(db, user) >= MAX_PER_DAY:
        raise too_many(f"今日发布已达上限（{MAX_PER_DAY} 件），明天再来吧")
    if count_active_items(db, user) >= MAX_ACTIVE:
        raise too_many(f"在架物品已达上限（{MAX_ACTIVE} 件），请先下架一些")

    if not user.community_id:
        raise forbidden("请先完成小区验证")
    sec_status = check_text(db, f"{payload.title}\n{payload.description}", user, "text", None)
    # 分类免选（docs/11）：未传/非法 → 按标题与描述自动识别
    category = payload.category if payload.category in CATEGORIES else guess_category(
        payload.title, payload.description
    )
    item = Item(
        community_id=user.community_id,
        user_id=user.id,
        type=payload.type,
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=category,
        condition=payload.condition,
        price_cents=payload.price_cents if payload.type == "sell" else None,
        negotiable=payload.negotiable and payload.type == "sell",
        want_desc=payload.want_desc,
        bid_cents=payload.bid_cents if payload.type == "want" else None,
        building=user.building,
        sec_status=sec_status,
    )
    db.add(item)
    db.flush()
    register_item_images(db, item, payload.images, user)
    db.commit()
    db.refresh(item)
    return ok(item_detail(db, item, user))


def _get_item_or_404(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise not_found()
    return item


@router.get("/items/{item_id}")
def get_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.community_id:
        raise forbidden("完成小区验证后查看内容")
    item = _get_item_or_404(db, item_id)
    item.view_count += 1
    db.commit()
    return ok(item_detail(db, item, user))


@router.put("/items/{item_id}")
def update_item(
    item_id: int,
    payload: ItemPayload,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    item = _get_item_or_404(db, item_id)
    if item.user_id != user.id:
        raise forbidden("只能编辑自己发布的物品")
    if item.status not in ("on_sale", "sunk"):
        raise conflict("当前状态不可编辑")
    _validate_payload(payload)
    sec_status = check_text(db, f"{payload.title}\n{payload.description}", user, "text", item.id)
    item.type = payload.type
    item.title = payload.title.strip()
    item.description = payload.description.strip()
    item.category = payload.category if payload.category in CATEGORIES else guess_category(
        payload.title, payload.description
    )
    item.condition = payload.condition
    item.price_cents = payload.price_cents if payload.type == "sell" else None
    item.negotiable = payload.negotiable and payload.type == "sell"
    item.want_desc = payload.want_desc
    item.bid_cents = payload.bid_cents if payload.type == "want" else None
    item.sec_status = sec_status

    # 全量替换图片
    from app.models import ItemImage

    db.query(ItemImage).filter(ItemImage.item_id == item.id).delete()
    db.flush()
    register_item_images(db, item, payload.images, user)
    db.commit()
    return ok(item_detail(db, item, user))


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    item = _get_item_or_404(db, item_id)
    if item.user_id != user.id and user.role != "admin":
        raise forbidden("只能删除自己发布的物品")
    if item.status == "reserved":
        raise conflict("物品正在交换约定中，请先处理交易")
    active_want = (
        db.query(ItemWant)
        .filter(ItemWant.item_id == item.id, ItemWant.status == "accepted")
        .first()
    )
    if active_want:
        raise conflict("已有接受的意向，请先处理")
    db.delete(item)
    db.commit()
    return ok({"ok": True})


@router.post("/items/{item_id}/renew")
def renew_item(
    item_id: int,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    item = _get_item_or_404(db, item_id)
    if item.user_id != user.id:
        raise forbidden("只能续期自己发布的物品")
    if item.status not in ("on_sale", "sunk"):
        raise conflict("当前状态不可续期")
    now = utcnow()
    if item.last_renewed_at:
        from datetime import timedelta

        cooldown_end = item.last_renewed_at + timedelta(hours=RENEW_COOLDOWN_HOURS)
        if now < cooldown_end:
            hours = int((cooldown_end - now).total_seconds() // 3600) + 1
            raise too_many(f"刚刚续期过，{hours} 小时后再试")
    item.status = "on_sale"
    item.last_active_at = now
    item.last_renewed_at = now
    db.commit()
    return ok(item_detail(db, item, user))


@router.post("/items/{item_id}/off-shelf")
def off_shelf_item(
    item_id: int,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    item = _get_item_or_404(db, item_id)
    if item.user_id != user.id and user.role != "admin":
        raise forbidden("只能下架自己发布的物品")
    if item.status not in ("on_sale", "sunk"):
        raise conflict("当前状态不可下架")
    item.status = "archived"
    db.commit()
    return ok({"ok": True})
