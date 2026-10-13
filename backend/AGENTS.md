# AGENTS.md — backend（FastAPI 后端）

> 接入前先读仓库根目录的 AGENTS.md（端口/合规/验证规则）。

## 技术栈与结构

FastAPI + SQLAlchemy 2.0（Mapped 风格）+ Alembic + MySQL（本地开发用 SQLite）+ APScheduler；
管理后台是 Jinja2 SSR（`/admin`，session 鉴权），与小程序无共享代码。

```
app/
├── main.py          # 入口：路由注册、APScheduler 每日沉底任务(3am)、/healthz、/uploads 静态
├── api/             # 15 个业务 router（auth/users/community/items/wants/messages/chat/trades/
│                    #   favorites/gratitudes/reports/notifications/uploads/wechat_callback）+ admin/
├── models/          # community(社区/邀请码/担保/人工审核) user item chat(会话/私信/联系交换)
│                    #   trade(交易/评价/感谢) system(举报/审核/通知/订阅/管理) —— 22 张表
├── schemas/         # Pydantic 入参（__init__.py）+ 全部响应序列化（serialize.py，改字段必看）
├── services/        # wechat(mock/cloud/token 三模式) sec_check(先检后发+降级) credit(信用)
│                    #   expiry(沉底/归档) notify(站内通知必达+订阅消息增强)
└── core/            # config(.env) deps(三级鉴权) errors(ApiError) security password/openid time(ISO UTC)
alembic/versions/    # f91b070d8b1d(初始) → b7d2e4a91c58(联系方式交换)；新迁移挂链尾
tests/               # pytest + TestClient，sqlite + mock；conftest 提供 client/db/community/users/hdr/publish
scripts/seed.py      # 建表(Base.metadata.create_all)+社区+admin+演示用户/物品/邀请码（幂等）
```

## 接口约定（前端依赖，破坏性改动需同步 docs/04-API契约.md）

- **信封**：成功 `{"code":0,"message":"ok","data":...}`（`serialize.ok`）；业务错误
  `{"code":<http状态>,"message":中文}`（core/errors.py 的 bad_request/forbidden/not_found/conflict/too_many）；
  Pydantic 422 走 FastAPI 默认 `{detail:[...]}`（前端已兜底）。
- **鉴权三级**：`get_current_user`（openid 自动建档）< `get_active_user`（未封禁）<
  `get_verified_user`（已验证=会员）。openid 来源：`X-WX-OPENID`（生产云托管注入）>
  `X-DEV-OPENID`（仅 dev）> `dev-default-openid`（dev 兜底）。
- **分页三套**：items feed 用字符串游标 `"ts|id"`；其余列表用 int id 游标；chat 用 `since` 增量。
  新列表接口默认用 int 游标并在响应里给 `next_cursor`。
- **时间**：一律 UTC ISO8601 秒级（core/time.iso）；**金额**：一律分（*_cents，int）。
- **内容安全**：用户产生的文本走 `sec_check.check_text`，图片走上传接口登记 + mediaCheckAsync
  回调（wechat_callback.py）；审核异常降级为"待审仅作者可见"，fail-closed。

## 已知怪癖（勿"修复"成不同行为，前端依赖现状）

- `GET /api/trades` 不传 `status` 返回**空列表**（实现行为），前端始终显式传
  ongoing/completed/cancelled。
- 微信 `wx.request` 无 PATCH：`/trades/{id}/arrange` 同时注册了 PUT 与 PATCH。
- 云托管下 `wx.uploadFile` 无法注入 openid：上传备有 JSON 通道 `POST /api/uploads/base64`。
- `GET /api/items/{id}` 每次浏览 `view_count+1`（无去重，产品接受）。
- `WX_CALL_MODE=mock` 只 mock 微信开放接口（审核/订阅消息/code2session），业务与数据库全真。

## 改动规则

- 新字段/新表：models → schemas/serialize（**联系方式 contact_* 三个字段禁止进入任何序列化**）→
  若影响前端，同步 miniprogram/utils/constants.ts 与 docs/04 → 写/改 pytest →
  `alembic revision` 挂到链尾（全新库可只靠 seed.py 的 create_all）。
- 通知：用 `services/notify.push_notification`，type 命名 `xxx_yyy`，payload 只放跳转所需最小 id；
  新 type 必须同步前端 `NOTIFY_META` + `navigation.ts`。
- 枚举字符串值（item type/status、place_method 等）被前端字典映射，改动 = 前后端联动改动。
- 测试命名与风格参照 tests/test_contact.py、test_trade_flow.py；跑法见根 AGENTS.md。
