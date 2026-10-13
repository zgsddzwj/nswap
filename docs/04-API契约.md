# nswap API 契约

> 后端与小程序前端共同遵守的接口契约。基路径 `/api`，管理后台 `/admin` 见文末。

## 0. 通用约定

**鉴权**：请求头 `X-WX-OPENID`（云托管注入）/ `X-DEV-OPENID`（本地开发）。无有效身份的写操作返回 401。

**响应信封**：
```jsonc
// 成功：HTTP 200
{ "code": 0, "message": "ok", "data": { ... } }
// 失败：HTTP 4xx/5xx
{ "code": 40001, "message": "参数错误：标题不能为空" }
```

**错误码**：`400` 参数错误 ｜ `401` 未登录 ｜ `403` 无权限（未验证/封禁/非本人）｜ `404` 不存在 ｜ `409` 状态冲突（非法状态迁移）｜ `429` 频控（发布超限/续期冷却/重复意向）

**游标分页**：请求带 `cursor`（首页不传）+ `limit`（默认 20），响应 `{ "list": [...], "next_cursor": "xxx" }`，`next_cursor` 为 null 表示到底。

**金额**：一律 `price_cents` 整数（分），前端负责元↔分换算。

**时间**：ISO8601 字符串（UTC，前端本地化显示）。

**枚举**：
```
ItemType:    sell | give | swap | want
ItemStatus:  on_sale | reserved | completed | archived | sunk
Condition:   brand_new | like_new | good | used | worn      （全新未拆/99新/9成新/明显使用痕迹/功能正常有磨损）
Category:    baby | book | appliance | furniture | clothing | digital | sports | kitchen | other
WantStatus:  pending | accepted | rejected | done
TradeStatus: pending | arranged | completed | cancelled
PlaceMethod: face | porch | lobby                          （当面/放门口自取/物业前台）
SecStatus:   pass | pending | fail
Role:        member | elder | admin
```

## 1. auth 身份

### POST /api/auth/login
静默登录（启动时调用），按 openid upsert 用户。
- 请求：`{}` 
- 响应 data：`Me`

### GET /api/me
- 响应 data：`Me`

### PUT /api/me
- 请求：`{ "nickname"?, "avatar_url"?, "unit"? }`（building 属验证信息，不在此改）
- 响应 data：`Me`

```jsonc
// Me
{
  "user": {
    "id": 1, "nickname": "邻居77", "avatar_url": "https://...",
    "building": "3栋", "unit": "2单元", "role": "member",
    "verified": true, "status": "active",
    "stats": { "sell_done": 2, "give_done": 5, "swap_done": 1,
               "review_good": 8, "review_mid": 0, "review_bad": 0,
               "thanks_count": 4, "violations": 0 },
    "created_at": "2026-10-01T08:00:00Z",
    "unread_count": 3            // 未读通知数
  },
  "community": { "id": 1, "name": "阳光花园", "verified_count": 128, "item_count": 56 }
}
```

## 2. community 社区验证

### GET /api/community/info
- 响应 data：`{ "id", "name", "address", "verified_count", "item_count", "buildings": ["1栋","2栋",...] }`

### POST /api/community/join
邀请码验证（主通道）。
- 请求：`{ "code": "YQ-XXXXXX" }`
- 响应 data：`Me`（验证成功后）；错误：404 码不存在/已用/过期
- 说明：vouch 码同时生成 vouches 记录（担保关系）

### POST /api/community/vouch-invite
老住户生成担保码。前置：已验证 + trades_done ≥ 1 + 当前无未使用的担保码。
- 请求：`{}` → 响应 data：`{ "code": "DB-XXXXXX", "expires_at": "..." }`

### POST /api/community/manual-apply
人工审核申请（先 POST /api/uploads 传凭证图）。
- 请求：`{ "building": "5栋", "unit": "1单元", "proof_image": "https://.../uploads/x.jpg" }`
- 响应 data：`{ "status": "pending" }`；重复申请返回 409

## 3. items 物品

### GET /api/items
feed / 筛选 / 搜索。
- Query：`type?` `category?` `building?` `keyword?` `mine=true?`（我的发布，需登录，含全部状态）`status?`（mine 时按状态过滤）`cursor?` `limit?`
- 默认（无 mine）：返回 status ∈ {on_sale, reserved}，按 last_active_at 倒序；keyword 匹配标题+描述
- 响应 data：`{ "list": [ItemCard], "next_cursor" }`

```jsonc
// ItemCard
{ "id": 1, "type": "sell", "title": "婴儿推车 好孩子",
  "price_cents": 15000, "negotiable": true, "category": "baby",
  "condition": "like_new", "building": "3栋", "status": "on_sale",
  "cover": "https://.../uploads/1.jpg",     // 首张可见图，无图 null
  "want_count": 2, "view_count": 35,
  "created_at": "...", "last_active_at": "...", "is_mine": false }
```

### POST /api/items
发布。前置：已验证、未封禁；频控：当日发布 < 5、在架(on_sale/reserved) < 20。
- 请求：
```jsonc
{ "type": "swap", "title": "儿童滑板车", "description": "九成新，娃大了用不上",
  "category": "sports", "condition": "good", "price_cents": null, "negotiable": false,
  "want_desc": "想换绘本或滑轮鞋", "bid_cents": null, "images": ["https://.../a.jpg"] }
```
- 校验：sell 必填 price_cents>0；swap 必填 want_desc；图片 0-9 张；标题≤30字
- 响应 data：`ItemDetail`
- 内容安全：标题/描述 msgSecCheck 不通过 → 400「内容包含敏感信息，请修改」

### GET /api/items/{id}
详情（游客可看）。view_count+1。
- 响应 data：`ItemDetail`

```jsonc
// ItemDetail = ItemCard 字段 + 以下
{
  ...,
  "description": "...", "want_desc": "...",
  "images": ["url", ...],                  // 仅 pass/pending（fail 已隐藏）
  "message_count": 3,
  "seller": { "id": 2, "nickname": "3栋-小王", "avatar_url": "...", "building": "3栋",
              "verified": true, "stats": {...}, "created_at": "..." },
  "is_favorite": false,
  "my_want": { "id": 7, "status": "pending" },   // 我提交过的意向，无则 null
  "can_want": true, "can_want_reason": "",       // false 时给原因（未验证/是自己的/已预约/已有意向）
  "active_trade_id": null                          // 与我相关的进行中交易
}
```

### PUT /api/items/{id} — 仅作者 + on_sale 状态
请求体同 POST（images 全量替换）。响应 data：`ItemDetail`

### DELETE /api/items/{id} — 仅作者，无进行中交易（reserved 拒绝）
响应 data：`{ "ok": true }`

### POST /api/items/{id}/renew — 续期（on_sale/sunk → on_sale）
冷却 72h（429「刚刚续期过，X小时后再试」）。响应 data：`ItemDetail`

### POST /api/items/{id}/off-shelf — 下架归档（on_sale/sunk → archived）
响应 data：`{ "ok": true }`

## 4. wants 意向

### POST /api/items/{id}/wants
- 前置：已验证、非本人物品、物品 on_sale、无未完结意向（pending/accepted）
- 请求：`{ "message": "我家二宝正需要，可以明天下午取", "bid_cents": 12000?, "swap_offer": "我可以用积木桌换"? }`
- 响应 data：`{ "id": 7, "status": "pending" }`；并触发：卖家站内通知 + 订阅消息

### GET /api/items/{id}/wants — 仅物品作者（或 admin）
- 响应 data：`{ "list": [ { "id", "message", "bid_cents", "swap_offer", "status",
  "created_at", "user": { ...UserSummary+stats } } ] }`

### PUT /api/wants/{id} — 作者处理
- 请求：`{ "action": "accept" | "reject" }`
- accept：创建 conversation + transaction(pending)，item→reserved，通知买家；409 若物品已 reserved
- reject：want→rejected（该用户可重新提交）
- 响应 data：accept 时 `{ "trade_id": 12, "conversation_id": 5 }`；reject 时 `{ "ok": true }`

### DELETE /api/wants/{id} — 意向方撤回（仅 pending）
响应 data：`{ "ok": true }`

## 5. item messages 留言板

### GET /api/items/{id}/messages
公开（仅 visible 留言）。响应 data：`{ "list": [ { "id", "content", "created_at",
"user": UserSummary } ], "next_cursor" }`

### POST /api/items/{id}/messages — 已验证
- 请求：`{ "content": "还在吗？" }` → 响应 data：留言对象（sec pass/pending 决定展示范围）

## 6. chat 轻会话

### GET /api/conversations
- 响应 data：`{ "list": [ { "id", "item": { "id","title","cover","type","status" },
"counterpart": UserSummary, "last_message": { "content","created_at","sender_id" },
"unread": false?, "updated_at" } ] }`

### GET /api/conversations/{id}/messages?since={msg_id}
增量拉取（前端 5s 轮询）。since 不传返回最近 50 条。
- 响应 data：`{ "list": [ { "id", "sender_id", "content", "created_at" } ] }`

### POST /api/conversations/{id}/messages — 仅会话双方
- 请求：`{ "content": "今晚8点放门口可以吗" }` → 响应 data：消息对象

## 7. trades 交易

### GET /api/trades?status=ongoing|completed|all
- 响应 data：`{ "list": [Trade], "next_cursor" }`

### GET /api/trades/{id}
- 响应 data：`Trade`

```jsonc
// Trade
{ "id": 12, "status": "arranged", "item": { "id":1, "title":"...", "cover":"...", "type":"swap" },
  "counterpart": UserSummary,           // 对方（视角相对）
  "my_role": "owner",                   // owner=我是物品方 / other=我是意向方
  "want": { "message": "...", "bid_cents": null, "swap_offer": "..." },
  "place_method": "porch", "meet_time": "2026-10-15T12:00:00Z", "place_note": "放门口垫子上",
  "owner_confirmed": true, "other_confirmed": false, "my_confirmed": true,
  "cancel_reason": null,
  "reviews": [ { "from_user_id": 2, "rating": 3, "content": "爽快" } ],
  "my_review": { "rating": 3, "content": "..." } | null,
  "gratitude": { "content": "..." } | null,
  "created_at": "...", "completed_at": null }
```

### PATCH /api/trades/{id}/arrange — 双方均可
- 请求：`{ "place_method": "porch", "meet_time": "2026-10-15T12:00:00Z", "place_note"? }`
- 效果：transaction→arranged（首填时），item.last_active 刷新，通知对方
- 响应 data：`Trade`

### PUT /api/trades/{id}/confirm — 双方各自调用
- 我方确认置位；双方都确认 → transaction→completed、item→completed、want→done、双方 stats 更新、双方收到互评邀请通知
- 单方确认后对方收到「待确认」订阅消息
- 响应 data：`Trade`

### PUT /api/trades/{id}/cancel — completed 前任一方
- 请求：`{ "reason": "临时有事" }`
- 效果：transaction→cancelled（记取消方 violations+1）、item→on_sale、want→pending（owner取消）/rejected（意向方取消）、通知双方
- 响应 data：`Trade`

### POST /api/trades/{id}/review — completed 后，每人一次
- 请求：`{ "rating": 1|2|3, "content"? }`（3=满意 2=一般 1=不满意）
- 响应 data：`Trade`；对方收到评价通知

### POST /api/trades/{id}/gratitude — completed 后，收受方一次
- 收受方 = 意向方（sell/give/swap 物品）或求购者（want 物品），感谢物品提供方
- 请求：`{ "content": "感谢5栋邻居送的书架！", "to_building"? }`
- 响应 data：`{ "id": 3 }`（感谢帖进首页横滑区）

## 8. favorites / gratitudes / reports / notifications

### POST /api/items/{id}/favorite ｜ DELETE /api/items/{id}/favorite
响应 data：`{ "ok": true }`

### GET /api/favorites
响应 data：`{ "list": [ItemCard], "next_cursor" }`

### GET /api/gratitudes?limit=10
响应 data：`{ "list": [ { "id", "content", "to_building", "user": {"nickname","building"},
"item_id"?, "created_at" } ] }`

### POST /api/reports
- 请求：`{ "target_type": "item|message|user", "target_id": 1, "reason": "禁售品",
"detail"? }` → 响应 data：`{ "ok": true }`

### GET /api/notifications?unread_only=true&cursor=
响应 data：`{ "list": [ { "id", "type", "title", "content", "payload": {...}, "read",
"created_at" } ], "next_cursor" }`
- type/payload 跳转映射：`want_received`→{item_id} / `want_accepted`→{trade_id} /
`trade_confirmed`→{trade_id} / `trade_completed`→{trade_id} / `review_received`→{trade_id} /
`item_sunk`→{item_id} / `system`→{}

### POST /api/notifications/read ｜ POST /api/notifications/read-all
- 请求：`{ "ids": [1,2,3] }` → 响应 data：`{ "ok": true }`

### POST /api/notifications/subscribe
记录订阅授权（wx.requestSubscribeMessage accept 后调用）。
- 请求：`{ "template_key": "want|accepted|confirm|review" }` → 响应 data：`{ "ok": true }`

## 9. uploads / wechat_callback

### POST /api/uploads （multipart/form-data，字段名 file）
- 已登录即可（游客也可，用于凭证图）。校验：jpg/png/webp，≤5MB
- 响应 data：`{ "url": "http://PUBLIC_BASE_URL/uploads/xxxx.jpg" }`

### GET /api/wechat/callback
消息推送服务器验证（echostr 透传）。

### POST /api/wechat/callback
mediaCheckAsync 结果回调：按 trace_id 更新 sec_checks 与 item_images.sec_status，risk → fail（图立即隐藏）。

## 10. /admin 管理后台（Jinja2 SSR，session 鉴权）

| 路由 | 方法 | 功能 |
|---|---|---|
| /admin/login | GET/POST | 登录（admin_users） |
| /admin/logout | POST | 登出 |
| /admin | GET | 看板（计数+最近动态） |
| /admin/invites | GET/POST | 列表 / 批量生成（building,count,days,batch_note）；?revoke={id} 作废 |
| /admin/items | GET | 内容巡查（筛选 type/status/building/keyword）；?off={id} 强制下架 |
| /admin/reports | GET | 举报列表；?resolve={id}&action=dismiss 下拉 |
| /admin/users | GET | 用户列表（含 verify_requests 待审）；?ban=/?unban=/?approve=/?reject=/?elder= 动作 |
| /admin/sec-checks | GET | 内容安全回调记录 |

动作均记录 admin_logs。默认账号 `admin / nswap123`（seed 建立，**上线必改**）。

## 3.12 联系方式交换（新增）

隐私策略：用户在「我的」主动填写并开启「允许交换」后才可被交换查看（默认不开放）；交换入口仅在轻会话内（意向被接受后），发起方须为已验证住户；每会员每日可发起 3 次（UTC 日重置），同会话幂等不重复扣费；一次交换双向解锁，双方均收到 `contact_exchanged` 通知并留有审计记录（contact_exchanges 表）。联系方式字段绝不出现在用户/物品/会话等任何既有序列化中。

- `GET /api/me/contact` → `{ "contact_enabled", "contact_wechat", "contact_phone" }`（仅本人）
- `PUT /api/me/contact` 请求 `{ "contact_enabled": bool, "contact_wechat": str≤64, "contact_phone": str≤20 }`
  - 微信号格式 `^[A-Za-z0-9_-]{6,20}$`、手机号 `^1\d{10}$`；开启时至少填一种 → 400
- `GET /api/conversations/{id}/contact` → `{ "exchanged": bool, "remaining_today": int, "counterpart": {id,nickname,building}, "contact": {wechat,phone} | null }`
  - 未交换、或对方未开放/未填写时 `contact` 恒为 `null`（不泄露）
- `POST /api/conversations/{id}/contact`（需已验证）→ 同上结构
  - 对方未开放 → 400（不扣额度）；当日额度用尽 → 429；已交换过 → 幂等返回不扣额度

## 3.13 多社区 SaaS（docs/07）

- **`GET /api/items` 新增 `scope`**：`community`(默认)｜`city`。community=本小区（未加入→空列表）；
  city=同城 active 小区（未加入→全部小区）；city 模式忽略 building 筛选。
- **序列化**：`item_card`/`user_summary` 新增 `community_name`；跨小区 viewer 时 `building` 输出空串。
- **`GET /api/community/info`**：未加入返回 `{"joined": false, ...空结构}`（HTTP 200）；已加入补 `city`/`district`；`buildings` 仅本小区。
- **`POST /api/community/manual-apply`** 请求体新增 `community_id`（必填）。
- **新增 `GET /api/communities?keyword=`**：公开小区查询（id/name/city/district，不含地址），人工审核选小区用。
- **`GET /api/announcements?cursor&limit`**：本小区公告列表（游客/外小区为空）。
- **`GET /api/trades`** 的 trade_dto 新增 `cross_community: bool`；跨小区 `arrange` 仅允许 `place_method=face`（否则 400）。
- **举报归属**：`reports.community_id` 改为被举报目标所属小区。
- **感谢帖**：仅返回本小区。
- 管理后台两级分权（平台超管/物业管理员）为 Web SSR，接口不在本契约范围，见 docs/07 §5。
