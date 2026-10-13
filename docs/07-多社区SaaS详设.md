# 07 · 多社区 SaaS 详设

> 状态：待评审（分支 `feat/saas-multitenant`）｜前置：v0.1.0（单社区 MVP）
> 决策记录：同城浏览=双 Tab 切换；跨小区=可完整交易；公告触达=首页公告卡（不发全员通知）；
> 物业后台=沿用 Web /admin 分权；本期不做计费、不做小程序内物业端。
> 原则：**文档即蓝图**——本文是实施依据，代码严格按此生成；实现中的偏差必须回写本文。

## 1. 背景与目标

### 1.1 目标
1. **多小区 SaaS**：平台运营多个小区租户；住户只能经物业管理者的邀请码进入本小区（现有机制，本期补齐"邀请码决定小区"的正确绑定）。
2. **同城发现**：默认只看本小区；可切换「同城」浏览本市其他小区物品，并可完整交易（意向→会话→约定→确认→联系方式交换）。
3. **物业公告**：物业管理员发布本小区公告，业主在首页看到公告卡、进公告列表页——给物业一个持续使用小程序的理由，助推推广。
4. **管理后台两级分权**：物业管理员只管本小区；平台超管管全局并负责开通小区、开设物业管理员账号。

### 1.2 非目标（本期明确不做）
- 付费/计费/套餐（小程序内碰支付有类目审核风险，平台开通小区走线下签约+人工操作）
- 公告全员站内通知（仅首页展示；后续可加开关）
- 小程序内嵌物业端（物业用 Web 后台）
- 区县级运营后台、地图/LBS 排序、跨城市浏览
- 用户多小区归属（一人一小区；搬家=换小区，本期不提供换绑）

## 2. 角色与权限矩阵

| 角色 | 载体 | 数据范围 | 关键能力 |
|---|---|---|---|
| 游客（未加入小区） | 小程序 | 全部小区（仅浏览） | 看同城 feed/详情/留言板（只读）；不可发布/意向/留言/收藏？——收藏可（已登录即可）；不可交换联系方式 |
| 住户（已验证=会员） | 小程序 | 本小区 + 同城浏览 | 完整交易流；公告浏览；发起联系方式交换（额度制） |
| 楼长 elder | 小程序 | 同住户 | 同住户（既有角色，无新增） |
| 物业管理员 | Web /admin | 仅本小区 | 邀请码批量生成/作废、公告发布/删除、内容巡查下架、举报处置、用户封禁、人工验证审批 |
| 平台超管 | Web /admin | 全局 | 物业管理员全部能力（跨小区，业务页面带小区列）＋「小区管理」（开通小区、生成物业账号、重置密码）＋「公告管理」（选小区发布） |

## 3. 数据模型变更

### 3.1 现状核实（2026-10-13，分支基线 v0.1.0）

**已带 community_id 的表**：users(可空)、items、conversations、invites、vouches、verify_requests(可空)、reports(可空)、transactions、gratitudes。
**不带但无需冗余的表**（经归属推导隔离）：notifications(按用户)、dm_messages/item_messages/item_images/item_wants/favorites/reviews(挂物品)、sec_checks/msg_subscriptions(按用户)、admin_logs(按操作者)。**本期不给这些表加冗余列**，隔离一律从 item/user/conversation 推导。

### 3.2 变更清单（单个 alembic 迁移 `c5f8d3e27a91_multitenant_saas`）

| 表 | 变更 | 说明 |
|---|---|---|
| communities | + `city` String(50) NOT NULL server_default ''、+ `district` String(50) NOT NULL default ''、索引 `ix_communities_city` | city 是同城维度；**管理端创建必填**，同城查询只匹配 city 非空 |
| admin_users | + `community_id` Integer FK(communities.id) NULLABLE、索引 | NULL=平台超管；非 NULL=物业管理员 |
| announcements（新表） | id PK、`community_id` FK NOT NULL 索引、`title` String(100) NOT NULL、`content` Text NOT NULL、`published_by` Integer FK(admin_users.id) NULL（留痕）、`created_at` DateTime NOT NULL | 无草稿/置顶/下架（MVP）；删除即物理删除并记 admin_logs |

### 3.3 models 改动
- `Community`：+city/district 字段与索引。
- `AdminUser`：+community_id。
- 新 `Announcement` 放 `models/system.py`；`models/__init__.py` 导出。

### 3.4 存量数据回填（迁移说明写入 README）
- 老库 `communities.city` 为空 → 不出现在同城 Tab。上线后由超管在「小区管理」补城市；或执行
  `UPDATE communities SET city='<城市>' WHERE city=''`。
- 老的 `admin_users`（已存在超管）community_id 默认 NULL=超管，无需处理。

## 4. 后端 API 详设

### 4.1 社区绑定修正（重要 bug 级修正）
`POST /api/community/join` 现用 `get_default_community`（取第一个小区）绑定用户——**多社区下是错的**。改为：取邀请码记录 `invite.community_id` 绑定用户（邀请码天然属于某小区）。同理 `POST /api/community/vouch-invite`（担保码属本小区）无需变（担保码生成即绑定本小区）。

### 4.2 `get_default_community` 退役（4 个调用点逐一替换）
| 调用点 | 替换为 |
|---|---|
| community.py:32 `community_info` | 当前用户小区；未加入返回 §4.4 空结构 |
| community.py:140 `join` | `invite.community_id`（§4.1） |
| items.py:91 feed 过滤 | scope 语义（§4.5） |
| items.py:144 `create_item` | `user.community_id`（发布者必已验证=已加入；否则 verified 依赖已拦截） |

`get_default_community` 函数删除。

### 4.3 feed 双 scope（`GET /api/items` 新增 `scope` 参数）

| 场景 | scope=community（默认） | scope=city |
|---|---|---|
| 已加入小区 | `community_id == user.community_id` | `community.city == user.community.city`（含本小区） |
| 未加入小区（游客） | **空列表** | **全部小区**（浏览开放，冷启动转化；city 为空串的老小区除外） |
| mine=true | 忽略 scope，仍按"我的" | 忽略 scope，仍按"我的" |
| building 筛选 | 生效 | **忽略**（跨小区无楼栋概念），文档注明 |
| 排序/游标/其余筛选 | 不变 | 不变 |

### 4.4 `GET /api/community/info` 语义修正
- 已加入：现结构不变（id/name/address/verified_count/buildings），**+ `city`、`district`**。
- 未加入：`{"joined": false, "id": null, "name": "", "address": "", "city": "", "district": "", "verified_count": 0, "item_count": 0, "buildings": []}`（HTTP 200，前端兼容）。
- `buildings` 只统计本小区（现实现是全表 distinct——多社区下是 bug，改为 `filter(community_id==...)`）。

### 4.5 跨小区隐私：building 隐藏统一规则

**唯一规则：`viewer.community_id != 目标归属.community_id 时，building 一律输出空串**，同时相应位置给出小区名。无任何例外（含已交换联系方式者——交换解锁的是联系方式，不是楼栋）。

实现：`serialize.py` 三个 building 输出点 + 一个批量入口，统一加 viewer 上下文：

| 函数 | 改动 | 影响的接口 |
|---|---|---|
| `user_summary(u)` → `user_summary(u, viewer=None)` | viewer 非空且跨小区 → `building:""`，并恒输出 `community_name`（u.community 查名，缓存于本次请求） | item_detail.seller、物品留言、意向列表（作者看跨小区意向者）、conversations.counterpart、trades.counterpart、`/users/{id}`、gratitudes.user |
| `item_card(...)` → 增加 viewer（沿用现有 viewer_id 参数位，改为传 User） | 跨小区 → `building:""`，恒输出 `community_name` | feed（community/city 两模式）、收藏、我的发布（mine 不隐藏，is_mine）、`/users/{id}` 的 items |
| `item_detail` | seller 用带 viewer 的 user_summary；根级 + `community_name` | 详情/创建/编辑/续期响应 |
| `_me_user` | **不动**（自己看自己的楼栋天经地义） | /api/me 系列 |
| `me_payload` | + `community` 结构补 city/district/joined 语义（未加入时 community=null，现状已是 null ✓） | /api/me 系列 |

性能注记：community_name 查询按 community_id 批量缓存到请求内 dict（`item_cards` 已有批处理入口），不做全局缓存（MVP 数据量小）。

### 4.6 公告 API

| 接口 | 说明 |
|---|---|
| `GET /api/announcements?cursor&limit(默认10,≤50)` | 本小区公告，`created_at desc`，int 游标。响应 `{list:[{id,title,content,created_at}], next_cursor}`。未加入小区 → 空列表。权限 `get_current_user`（游客可见空列表） |

创建/删除只在管理后台（§5.3），小程序端只读。

### 4.7 不变的接口（明确列出，防止误改）
意向/会话/私信/交易/评价/感谢/收藏/举报/通知/上传/联系方式交换：全部按参与者与物品归属运作，**不感知小区**——跨小区交易由此天然支持。唯一例外：§4.5 的序列化隐藏规则同样作用于会话/交易/意向里的 user_summary。

## 5. 管理后台多租户（Web /admin）

### 5.1 权限基座
- `AdminUser.community_id`：NULL=平台超管，非 NULL=物业管理员。登录逻辑不变。
- 新 helper：`scoped(db, admin)` 返回数据范围——超管：`None`（不过滤，列表必须显示小区列）；物业：固定本小区。
- 模板 `base.html` 导航按角色显隐：物业见「看板/邀请码/内容巡查/举报/用户/审核/安全记录/公告」；超管另见「小区管理」+「公告管理」。

### 5.2 既有页面改造（逐一登记，实现时逐条勾销）
| 页面 | 物业管理员 | 平台超管 |
|---|---|---|
| dashboard | 本小区统计（现有查询加 community 过滤） | 全局统计 + 小区概览表（小区名/住户/物品/交易数） |
| invites（列表+批量生成+作废） | 本小区；生成表单无小区选择 | 全局列表（+小区列）；生成表单必选目标小区（下拉） |
| items（巡查+强制下架） | 本小区 | 全局（+小区列） |
| reports（列表+处置） | 本小区 | 全局（+小区列） |
| users（封禁/解封/楼长） | 本小区 | 全局（+小区列） |
| verify-requests（人工审批） | 本小区 | 全局 |
| sec-checks | 本小区 | 全局 |
| 所有写操作（下架/处置/封禁/审批） | 校验目标归属本小区，越权 403 | 不限 |

### 5.3 新增页面
| 页面 | 路由 | 说明 |
|---|---|---|
| 小区管理（超管） | `GET /admin/communities` | 列表：名称/城市/区/住户数/物品数/物业管理员/开通时间 |
| 小区创建 | `POST /admin/communities` | 表单 name/city(必填)/district/address + 初始物业管理员 username/name/password；写 admin_logs |
| 物业账号重置密码 | `POST /admin/communities/{id}/reset-password` | 生成随机密码显示一次 |
| 公告管理 | `GET/POST /admin/announcements`、`POST /admin/announcements/{id}/delete` | 列表（标题/时间/发布人/删除）；创建表单 title(必填≤100)/content(必填)；物业=本小区，super 表单带小区下拉 |
| 模板 | 新增 `communities.html`、`announcements.html`；改 `base.html`(导航)、`dashboard/invites/items/reports/users.html`(小区列+过滤) | 沿用现有 Bootstrap 风格 |

## 6. 小程序端改动（逐页）

| 页面/组件 | 改动 |
|---|---|
| **home** | 标题下方加「本小区｜同城」分段切换（sticky，样式沿用 filter-bar 的 pill 风格）；state.scope 传入 loader（`scope=community/city`）；未加入小区：默认 tab=同城，本小区 Tab 显示空态「加入小区后查看邻里闲置」+去验证按钮；**本小区 Tab 顶部公告卡**：`GET /api/announcements?limit=1` 最新一条（标题+时间，点击进公告页），无公告不渲染 |
| **item-card** | meta 行数据驱动：`building` 非空显示「X栋·成色·时间」，为空显示 `community_name`（同城模式自动切小区名）；grid/row 两模式同规则 |
| **detail** | 卖家卡徽章：`building·已验证` → 跨小区时 `community_name·已验证`（后端已置空 building、seller 带社区名）；根级显示小区名标签（跨小区时） |
| **pages/announcements**（新页，18） | 公告列表：卡片（标题/正文/日期），游标加载，空态；入口=home 公告卡 |
| **search** | 固定 `scope=city`（搜全城更符合"找东西"意图），结果卡显示小区名；首页搜索框不带 scope 直接跳转，行为不变 |
| **verify** | `community/info` 新语义兼容：`joined:false` 时小区名区域显示引导文案；邀请码验证成功后 info 才有内容 |
| **profile** | 跨小区邻居：徽章「X栋·已验证」→「小区名·已验证」（后端 user_summary 已处理） |
| **mine** | 无改动（community=null 已兼容）；AGENTS/README 文档除外 |
| 其余页 | wants/chat/trade/review/my-items/favorites/my-trades/agreement：仅序列化字段自动生效，无逻辑改动 |

app.json：pages 注册 `pages/announcements/announcements`（第 18 页）。

## 7. 隐私与边界规则汇总

1. **楼栋可见性唯一规则**：同小区才可见；同城卡片/详情/留言者/意向者/卖家/主页一律小区名替代。实现点清单见 §4.5，pytest 守卫（§8）。
2. 跨小区完整交易开放；联系方式交换策略不变（会员、会话内、每日 3 次）。
3. 公告仅本小区住户可见；游客/外小区不可见。
4. 游客同城浏览开放（转化考虑）；发布/意向/留言/交换仍需验证（既有依赖不变）。
5. city 为空的小区不出现在同城（含历史数据），管理端创建必填城市。
6. 管理端越权：物业管理员操作跨小区目标一律 403（写路径全部加归属校验）。
7. 一人一小区；换小区本期不做（未来：人工客服改绑，保留信用档案）。

## 8. 测试计划

### 8.1 pytest 新增（`tests/test_multitenant.py` + 补充既有文件）
1. join 绑定邀请码所属小区（非第一个小区）
2. feed：本小区只见本小区；同城只见同城（含本小区）；city 空串小区不出现
3. 未加入用户：community scope 空、city scope 全量
4. 跨小区序列化：同城卡片 building="" + community_name；detail seller/building 隐藏；留言/意向者/会话 counterpart user_summary 隐藏；**同小区行为不回归**（building 正常）
5. `/users/{id}` 跨小区：user.building 隐藏 + items 卡片隐藏
6. 公告：本小区可见、外小区/游客不可见、分页
7. admin：物业管理员登录后各页面仅本小区数据（断言 HTML 不含外小区内容）、越权写 403；超管全局可见；小区创建+物业账号+重置密码
8. 回归：现有 24 项全过（尤其 contact/trade 流）

### 8.2 E2E 冒烟（curl 脚本，双小区双用户）
seed 后：幸福里住户 carol2 发布 → 阳光花园 bob 同城 Tab 看到（building 空、小区名=幸福里）→ 提交意向 → carol2 接受 → 聊天 → 约定 → 双向确认 → 互评 → 联系方式交换全程可用 → 公告：阳光花园物业发公告，bob 首页可见，carol2 不可见。

### 8.3 验收标准（用户侧）
开发者工具：双 Tab 切换流畅、同城卡片显示小区名、公告卡/公告页正常、物业 Web 后台只见本小区、超管可开通小区。真机同现有流程。

## 9. 迁移部署与 seed

1. 部署：`alembic upgrade head` → 重启容器。老库上线后超管补城市（§3.4 SQL）。
2. seed.py 更新：
   - 阳光花园补 `city="示例市"`、`district="高新区"`
   - 新增小区「幸福里」（同城市）+ 演示住户 `dev_dave`（6栋-大伟，已验证）+ 2 件物品（sell/give 各一）
   - 新增物业管理员 `wy_admin / nswap123`（community=阳光花园）；admin 超管不变
   - 幸福里邀请码 2 个（`YQ-XFLE0001` 起），公告示例 1 条（阳光花园）
3. 新库：seed 一次成型（create_all 含新表新列）。

## 10. 风险与开放问题

| 风险/问题 | 处置 |
|---|---|
| admin 逐页隔离遗漏 → 跨租户泄露 | §5.2 清单逐条勾销 + §8.1 第 7 条测试断言 HTML 内容 |
| serialize 签名改动波及面大（user_summary/item_card 多处调用） | 一次性改全 + 编译期类型检查 + 既有测试回归；viewer=None 语义保持兼容 |
| 老库 city 为空导致同城空转 | §3.4 回填 SQL + 管理端必填 |
| 游客全量浏览的爬取风险 | 只读；发布/意向/交换仍需验证；联系人交换本有额度制 |
| 公告被滥用（物业刷屏） | 本期无通知推送，影响面=首页一条卡片；后续可加频控 |
| 开放问题：同城排序是否要按小区加权？ | 本期统一按 last_active_at（与现有 feed 一致），上线看数据再定 |
