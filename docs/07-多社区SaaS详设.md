# 07 · 多社区 SaaS 详设（v2 · 已评审修订）

> 状态：**已实施**（分支 `feat/saas-multitenant`，pytest 36 项 + E2E 15 项验证通过）｜前置：v0.1.0
> 实施修订（M1-M5 中发现并回写）：
> ① `join` 原本已按 `invite.community_id` 绑定小区（v1 评审时误判为缺陷），实际需修正的只有 manual_apply；
> ② 公告不做微信 msgSecCheck——该接口要求终端用户 openid，管理员发布无 openid，改为 admin_logs 留痕问责（§4.6 已更新）；
> ③ sec_checks 表无 community_id，无法按小区隔离 → 调整为平台超管专属页（§5.2 已更新）；
> ④ 感谢帖 `GET /api/gratitudes` 补充社区隔离：仅返回本小区感谢帖（§4.9 补充）；
> ⑤ trade_dto 新增 `cross_community: bool` 字段，前端据此禁用 porch/lobby（§4.5 补充）。
> 决策记录：同城浏览=双 Tab；跨小区=可完整交易；公告触达=首页公告卡（不发全员通知）；
> 物业后台=Web /admin 分权；本期不做计费、不做小程序内物业端。
> 原则：**文档即蓝图**——本文是实施依据；实现偏差必须回写本文。

## 0. 评审修订记录（v1 → v2）

对 v1 做了代码核实与行业调研（Azure 多租户架构指南、AWS 租户隔离白皮书）后修订：

| # | 问题 | 严重度 | 处置 |
|---|---|---|---|
| R1 | **`manual_apply` 用 `get_default_community` 绑定小区**——申请人无法指定小区，多社区下必然错绑到"第一个小区" | 高（功能性缺口） | §4.2：请求体加 `community_id` 必填 + 新增公开小区查询接口供选择 |
| R2 | **举报归属错误**：`reports.community_id` 现取"举报人小区"，跨小区举报（A 小区住户举报 B 小区物品）会挂到 A 小区 → **B 小区物业永远看不到举报自己内容的记录** | 高（现有代码缺陷） | §4.4：改为按**被举报目标所属小区**归属；超管全局兜底 |
| R3 | **admin 权限只做了导航隐藏，没有路由级守卫**——物业管理员手输 URL 即可访问超管页面 | 高（越权） | §5.1：所有 admin 路由加服务端守卫，越权 403；测试断言（Azure 指南明确要求服务端强制租户上下文） |
| R4 | **跨小区交易的交接方式未校验**：`porch`(放门口自取)/`lobby`(物业前台) 对外小区住户不可行 | 中 | §4.5：后端校验——跨小区仅允许 `face`（当面），错误信息明确 |
| R5 | **自由文本泄露面未声明**：description/want_desc/nickname 可能含楼栋门牌，结构化隐藏管不到 | 中 | §7：明确为已知泄露面，靠发布表单提示 + 协议条款约束，平台不做文本清洗（说明理由） |
| R6 | **游客"全量浏览"的单城市假设未声明**：多城市后游客会看到跨城市混合内容 | 中 | §4.3 明确"单城市运营期等价同城"，预留城市选择扩展位 |
| R7 | 缺少**多租户架构选型**章节与行业依据 | 中 | §1.3 补：共享 schema + tenant_id（pool 模型）的选型理由、反模式规避、扩展路径 |
| R8 | 缺少**租户生命周期**（小区停用/下线）设计 | 中 | §3.2 增 `communities.status`（active/suspended）+ §5.3 停用/启用操作 |
| R9 | 公告未过**内容安全**；物业缺**自助改密码** | 低 | §4.6 公告走 `check_text`；§5.3 增物业自助改密码页 |
| R10 | 未说明**物业公司管多小区**的支持方式 | 低 | §5.1 明确：一期一个小区一个物业账号（行业常见按项目授权），多小区需求走多账号 |

## 1. 背景与目标

### 1.1 目标
1. **多小区 SaaS**：平台运营多个小区租户；住户只能经物业管理者的邀请码进入本小区。
2. **同城发现**：默认只看本小区；可切换「同城」浏览本市其他小区物品，并可完整交易。
3. **物业公告**：物业管理员发布本小区公告，业主首页见公告卡、进公告列表页——给物业持续使用的理由，助推推广。
4. **管理后台两级分权**：物业管理员只管本小区；平台超管管全局并开通小区、开设物业账号。

### 1.2 非目标（本期明确不做）
- 付费/计费/套餐（小程序碰支付有类目审核风险；开通小区走线下签约+人工操作）
- 公告全员站内通知（仅首页展示；后续可加开关）
- 小程序内嵌物业端（物业用 Web 后台）
- 区县级运营后台、地图/LBS 排序、跨城市浏览
- 用户多小区归属（一人一小区；换小区走人工客服，见 §10）

### 1.3 多租户架构选型（行业依据）

**结论：共享 schema + `community_id` 租户列（pool 模型），不引入行级安全（RLS）。**

依据与理由：
- Azure 多租户架构指南明确把"**多租户表 + 租户标识列**"列为关系库推荐做法，并把"每租户独立表"列为反模式；同时指出"避免列级租户定制""避免手工 schema 变更"。本项目现状（全表 community_id + alembic 迁移）与之完全一致，**不需要重构**。
- RLS 虽可用但"设计、实现、测试、维护复杂，多数多租户方案不用"——本项目的隔离复杂度（22 张表、单团队）不值得引入；改用**应用层强制 + 隔离测试**（§8）作为保障。
- Azure 强调共享架构下"**必须避免把一个租户的数据返回给另一个租户**，需要强的身份策略与**服务端授权**"——直接支撑 R3（路由守卫）与 §4.5 的序列化规则。
- 扩展路径（预留，不实现）：租户量/数据量增长后按 **sharding**（多库，小区哈希分片）或对 VIP 客户用**独立部署（deployment stamps）**；届时只需引入"租户→部署"映射，业务代码不变。

## 2. 角色与权限矩阵

| 角色 | 载体 | 数据范围 | 关键能力 |
|---|---|---|---|
| 游客（已登录未加入小区） | 小程序 | 同城/全量（只读） | 浏览 feed/详情/留言板；收藏；不可发布/意向/留言/交换联系方式 |
| 住户（已验证=会员） | 小程序 | 本小区 + 同城浏览 | 完整交易流；公告浏览；发起联系方式交换（额度制） |
| 楼长 elder | 小程序 | 同住户 | 同住户（既有角色，无新增） |
| 物业管理员 | Web /admin | **仅本小区**（服务端强制） | 邀请码批量生成/作废、公告发布/删除、内容巡查下架、举报处置、用户封禁、人工验证审批、自助改密 |
| 平台超管 | Web /admin | 全局 | 物业全部能力（跨小区，列表带小区列）＋「小区管理」（开通/停用小区、生成物业账号、重置密码）＋「公告管理」（选小区发布） |

**身份说明**：小程序经 `callContainer` 调用时，微信对每个用户都注入 openid，后端自动建档——即"游客"也是已注册用户（未验证），不存在真匿名访问。feed 需要 `get_current_user`，天然满足。

## 3. 数据模型变更

### 3.1 现状核实（基线 v0.1.0）
**已带 community_id**：users(可空)、items、conversations、invites、vouches、verify_requests(可空)、reports(可空，但归属语义有误见 R2)、transactions、gratitudes。
**不带但无需冗余**（经归属推导隔离）：notifications、dm_messages、item_messages、item_images、item_wants、favorites、reviews、sec_checks、msg_subscriptions、admin_logs。**本期不加冗余列**。

### 3.2 变更清单（单个迁移 `c5f8d3e27a91_multitenant_saas`）

| 表 | 变更 | 说明 |
|---|---|---|
| communities | + `city` String(50) NOT NULL default ''、+ `district` String(50) NOT NULL default ''、+ `status` String(10) NOT NULL default 'active'（active/suspended）、索引 `ix_communities_city` | city 为同城维度（创建必填）；status 支持停用（R8） |
| admin_users | + `community_id` Integer FK NULLABLE、索引 | NULL=平台超管；非 NULL=物业管理员 |
| announcements（新） | id PK、community_id FK NOT NULL 索引、title String(100) NOT NULL、content Text NOT NULL、published_by FK(admin_users.id) NULL 留痕、created_at DateTime NOT NULL | 无草稿/置顶/下架（MVP） |

### 3.3 models 改动
`Community` +city/district/status；`AdminUser` +community_id；新 `Announcement`（放 `models/system.py`）并导出。

### 3.4 存量回填（写入 README）
- 老库 city 为空 → 不出现在同城；超管在「小区管理」补城市，或 `UPDATE communities SET city='<城市>' WHERE city=''`。
- 老 admin_users community_id 默认 NULL=超管，无需处理；**存量 reports 的归属不回填**（历史数据，超管全局视图可见）。
- downgrade 实现为逆操作（删表/删列/删索引），供回滚。

## 4. 后端 API 详设

### 4.1 `get_default_community` 退役（4 个调用点全部替换）
| 调用点 | 替换为 |
|---|---|
| community.py `community_info` | 当前用户小区；未加入返回 §4.7 空结构 |
| community.py `join` | **`invite.community_id`**（邀请码天然属于某小区；修正现"取第一个小区"） |
| community.py `manual_apply` | **`payload.community_id`**（R1，见 §4.2） |
| items.py feed 过滤 | scope 语义（§4.3） |
| items.py `create_item` | `user.community_id` |

### 4.2 人工审核选小区（R1）
- 新增 **`GET /api/communities?keyword=`**（`get_current_user`）：公开小区查询，供申请选择。返回 `{list:[{id,name,city,district,status}]}`，**不含 address**（避免精确地址外泄）；`status=suspended` 的不返回；`keyword` 按 name 模糊；上限 20 条。
- **`POST /api/community/manual-apply`** 请求体加 `community_id`(必填 int)：校验小区存在且 active；VerifyRequest 绑定该小区（替换 get_default_community）。前端 verify 页人工审核通道加"选择小区"（输入关键词搜索选择）。
- 物业审批时只看到本小区的申请（§5.2），审批通过后用户 `community_id`/`building` 由该申请写入（现逻辑已按 verify_request 字段写入，确认不依赖默认小区）。

### 4.3 feed 双 scope（`GET /api/items` 加 `scope`）

| 场景 | scope=community（默认） | scope=city |
|---|---|---|
| 已加入小区 | `community_id == user.community_id` | `community.city == user.community.city`（含本小区，**仅 active 小区**） |
| 未加入小区（游客） | **空列表** | **全部 active 小区**（R6：单城市运营期等价"同城"；多城市后改为城市选择器，预留） |
| mine=true | 忽略 scope | 忽略 scope |
| building 筛选 | 生效 | **忽略**（前端同城模式隐藏楼栋筛选器，后端忽略为兜底） |
| 排序/游标/其余筛选 | 不变（`last_active_at` 倒序、字符串游标） | 不变 |

### 4.4 举报归属修正（R2，现有缺陷）
- `POST /api/reports` 的 `community_id` 改为**被举报目标所属小区**：item→`item.community_id`；message→所属 item 的 community_id；user→`user.community_id`。目标小区为空（如未加入小区的用户）→ `community_id=NULL`，由超管兜底。
- 语义：**谁的内容谁的小区处置**。跨小区举报由被举报方物业处理，超管全局可见全部举报。
- 前端无需改动（举报入口不变）；`reports` 列表页物业只见本小区、超管见全局。

### 4.5 跨小区交易的交接方式校验（R4）
- `PUT/PATCH /api/trades/{id}/arrange`：若交易双方 `community_id` 不同（跨小区），`place_method` 仅允许 `face`；传 `porch`/`lobby` → 400「跨小区交换请选择当面交接」。同小区不受限。
- 前端 trade 页：跨小区时禁用/隐藏 `porch`/`lobby` 选项并提示（后端校验为准）。
- 判定依据：`trade.item.community_id` 与交易对方 `user.community_id` 是否一致。

### 4.6 公告 API
| 接口 | 说明 |
|---|---|
| `GET /api/announcements?cursor&limit(默认10,≤50)` | 本小区公告，`created_at desc`，int 游标；返回 `{list:[{id,title,content,created_at}], next_cursor}`；未加入小区 → 空列表；`get_current_user` |
- 创建走管理后台（§5.3）。**不做微信 msgSecCheck**（实施修订②：该接口要求终端用户 openid，管理员发布无 openid），问责靠 admin_logs 留痕。

### 4.7 `GET /api/community/info` 语义修正
- 已加入：现结构 + `city`/`district`；`buildings` 改为**只统计本小区**（现全表 distinct 是多社区下的 bug）。
- 未加入：`{"joined": false, "id": null, "name": "", "address": "", "city": "", "district": "", "verified_count": 0, "item_count": 0, "buildings": []}`（HTTP 200，前端兼容）。
- 停用小区（suspended）：已加入用户返回原结构（仍可看历史）；新加入被 §4.2/join 拦截。

### 4.8 跨小区隐私：building 隐藏统一规则
**唯一规则：`viewer.community_id != 目标归属.community_id` → building 输出空串 + 补 `community_name`。无例外**（含已交换联系方式者——交换解锁联系方式，不是楼栋）。

| 函数 | 改动 | 影响接口 |
|---|---|---|
| `user_summary(u)` → `user_summary(u, viewer=None)` | 跨小区→`building:""`；恒输出 `community_name` | item_detail.seller、留言、意向列表、会话/交易 counterpart、`/users/{id}`、gratitudes |
| `item_card(...)`（viewer_id 参数改传 User） | 跨小区→`building:""`；恒输出 `community_name` | feed 两模式、收藏、我的发布(mine 不隐藏)、`/users/{id}` items |
| `item_detail` | seller 用带 viewer 的 user_summary；根级 + `community_name` | 详情/创建/编辑/续期 |
| `_me_user` | **不动**（自己看自己） | /api/me 系列 |

实现：`serialize.py` 内加 `_same_community(viewer, target)` 与请求内 `community_name` 批量缓存（`item_cards` 已有批处理入口）。**不引入全局缓存**。

### 4.9 不变的接口与补充
意向/会话/私信/交易/评价/收藏/上传/联系方式交换：按参与者与物品归属运作，不感知小区（跨小区交易由此天然支持）。例外与补充：
- §4.8 的 user_summary 隐藏规则同样作用于其中；
- **感谢帖 `GET /api/gratitudes` 增加社区过滤**：仅返回本小区感谢帖（跨小区感谢对邻里氛围无意义）；
- **`trade_dto` 新增 `cross_community: bool`**：前端据此禁用 porch/lobby 交接方式（与 §4.5 后端校验双保险）。

## 5. 管理后台多租户（Web /admin）

### 5.1 权限基座（含 R3 路由守卫）
- `AdminUser.community_id`：NULL=超管，非 NULL=物业。登录不变。
- 新 helper：`scoped(admin)` → 超管 `None`（不过滤，列表显示小区列）；物业固定本小区。
- **新增守卫**：`require_super(admin)`（超管专属页面/操作，越权 403）与"目标归属校验"（写操作目标不属于本小区 → 403）。**所有 admin 路由逐一登记校验点**，不依赖导航隐藏（R3）。
- **物业公司多小区（R10）**：一期一个小区一个物业账号（行业常见按项目授权）；需要管多小区则开多账号，后续可演进为"物业公司→多小区"授权表。
- `base.html` 导航按角色显隐（仅体验优化，不作为安全边界）。

### 5.2 既有页面改造（逐条勾销）
| 页面 | 物业管理员 | 平台超管 |
|---|---|---|
| dashboard | 本小区统计 | 全局统计 + 小区概览表 |
| invites（列表/批量生成/作废） | 本小区；生成无小区选择 | 全局（+小区列）；生成必选目标小区 |
| items（巡查/强制下架） | 本小区 | 全局（+小区列） |
| reports（列表/处置） | **本小区**（按 §4.4 新归属） | 全局（+小区列） |
| users（封禁/解封/楼长） | 本小区 | 全局（+小区列） |
| verify-requests（人工审批） | 本小区 | 全局 |
| sec-checks | **不开放（表无小区维度，平台级数据）** | 全局 |
| 所有写操作 | 目标归属校验，越权 403 | 不限 |

### 5.3 新增页面/操作
| 项 | 路由 | 说明 |
|---|---|---|
| 小区管理（超管） | `GET /admin/communities` | 列表：名称/城市/区/状态/住户/物品/物业账号/开通时间 |
| 小区创建（超管） | `POST /admin/communities` | name/city(必填)/district/address + 初始物业账号 username/name/password；写 admin_logs |
| 小区停用/启用（超管） | `POST /admin/communities/{id}/toggle-status` | active↔suspended（R8）：停用后不可新加入、其物品不出现在同城；已有用户可登录查看历史 |
| 重置物业密码（超管） | `POST /admin/communities/{id}/reset-password` | 生成随机密码，页面显示一次 |
| 物业自助改密码 | `GET/POST /admin/password` | 物业与超管均可改自己密码（R9） |
| 公告管理 | `GET/POST /admin/announcements`、`POST /admin/announcements/{id}/delete` | 列表/创建/删除；物业=本小区，超管表单带小区下拉；创建过内容安全（§4.6） |
| 模板 | 新增 `communities.html`、`announcements.html`、`password.html`；改 `base.html`(导航) 与 dashboard/invites/items/reports/users.html(小区列/过滤) | 沿用现有 Bootstrap 风格 |

## 6. 小程序端改动（逐页）

| 页面/组件 | 改动 |
|---|---|
| **home** | 标题下加「本小区｜同城」分段切换（sticky，pill 风格沿用 filter-bar）；`scope` 传入 loader；**同城模式隐藏楼栋筛选器**（§4.3）；未加入小区：默认 tab=同城，本小区 Tab 空态「加入小区后查看邻里闲置」+去验证；**本小区 Tab 顶部公告卡**（`GET /api/announcements?limit=1`，标题+时间，点击进公告页；无公告不渲染） |
| **item-card** | meta 数据驱动：`building` 非空→「X栋·成色·时间」；为空→`community_name`（同城卡片自动切小区名）；grid/row 同规则 |
| **detail** | 卖家卡徽章：跨小区→「小区名·已验证」（后端已置空 building、补 community_name）；根级跨小区显示小区名标签 |
| **pages/announcements**（新，第 18 页） | 公告列表（标题/正文/日期），游标加载，空态；入口=home 公告卡 |
| **verify** | `community/info` 新语义兼容（joined:false 引导文案）；**人工审核通道加"选择小区"**（关键词搜索 → `GET /api/communities`，选定后填楼栋/单元/凭证）（R1） |
| **search** | 固定 `scope=city`（搜全城），结果卡显示小区名 |
| **trade** | 跨小区时禁用 porch/lobby 选项并提示"跨小区请当面交接"（R4） |
| **profile** | 跨小区邻居：徽章→「小区名·已验证」（后端 user_summary 已处理） |
| **mine** | 无逻辑改动（community=null 已兼容） |
| 其余页 | wants/chat/review/my-items/favorites/my-trades/agreement：仅序列化字段自动生效 |

app.json：注册 `pages/announcements/announcements`。

## 7. 隐私与边界规则汇总

1. **楼栋可见性唯一规则**：同小区才可见；跨小区一律小区名替代（§4.8，实现点清单+pytest 守卫）。
2. **自由文本泄露面（R5，已知并接受）**：description/want_desc/nickname 由用户自填，可能含楼栋门牌，平台**不做文本清洗**（成本高、误伤大、且属用户自愿披露）。缓解：发布表单提示"请勿在标题/描述中填写具体门牌号"；协议条款增加"不得公开他人隐私信息"。**这是明确的已知边界，不是遗漏。**
3. 跨小区完整交易开放；联系方式交换策略不变（会员、会话内、每日 3 次额度、双向留痕）。
4. 公告仅本小区可见；游客/外小区不可见。
5. 游客同城浏览开放（转化）；发布/意向/留言/交换仍需验证。
6. city 为空或 suspended 的小区不出现在同城；创建必填城市。
7. 管理端越权：路由守卫 + 目标归属校验（§5.1），写路径全覆盖。
8. 一人一小区；换小区本期不做（未来人工改绑，信用档案随人保留）。
9. 跨小区交接仅"当面"（§4.5）。

## 8. 测试计划

### 8.1 pytest 新增（`tests/test_multitenant.py` 等）
1. join 绑定**邀请码所属小区**（非第一个小区）
2. manual-apply：必须传 community_id；错绑校验；公开小区接口不返回 address/suspended（R1）
3. feed：本小区只见本小区；同城只见同城 active（含本小区）；city 空/suspended 小区不出现
4. 未加入用户：community 空、city 全量
5. 跨小区序列化：同城卡片/详情/留言/意向者/会话 counterpart/`/users/{id}` 的 building 均空 + community_name；**同小区不回归**（building 正常）
6. 举报归属：跨小区举报挂**被举报目标小区**；该小区物业可见、举报人小区物业不可见、超管可见（R2）
7. 跨小区 arrange：porch/lobby → 400；face → 成功；同小区三种均可用（R4）
8. 公告：本小区可见/外小区与游客不可见/分页/内容安全拒绝
9. admin 分权：物业登录各页面仅本小区数据；**手输超管 URL → 403**；跨小区写操作 403；超管全局可见；小区创建/停用/重置密码/改密（R3/R8/R9）
10. 回归：现有 24 项全过（contact/trade 流重点）

### 8.2 E2E 冒烟（curl，双小区双用户）
seed 后：幸福里住户 carol2 发布 → 阳光花园 bob 同城 Tab 可见（building 空、小区名=幸福里）→ 提交意向 → carol2 接受 → 聊天 → **arrange 用 porch → 400，改 face → 成功** → 双向确认 → 互评 → 联系方式交换 → 公告：阳光花园公告 bob 可见、carol2 不可见 → 跨小区举报归属验证。

### 8.3 验收标准（用户侧）
开发者工具：双 Tab 流畅、同城卡片显示小区名、公告卡/公告页正常、跨小区交接仅当面、物业后台只见本小区且手输超管 URL 被拒、超管可开通/停用小区。

## 9. 迁移部署与 seed

1. 部署：`alembic upgrade head` → 重启；老库上线后超管补城市（§3.4）。
2. seed 更新：阳光花园补 `city="示例市"`/`district="高新区"`；新增「幸福里」（同城）+ 住户 `dev_dave`(6栋-大伟，已验证) + 2 件物品；新增物业账号 `wy_admin/nswap123`（阳光花园）；幸福里邀请码 2 个；公告示例 1 条。
3. 新库：seed 一次成型。

## 10. 风险与开放问题

| 风险/问题 | 处置 |
|---|---|
| admin 逐页隔离遗漏 → 跨租户泄露 | §5.2 清单勾销 + §8.1-9 测试断言 HTML 内容（Azure 指南要求必须专测隔离） |
| serialize 签名改动波及面大 | 一次性改全 + tsc/类型检查 + 既有 24 项回归；viewer=None 保持兼容 |
| 老库 city 空导致同城空转 | §3.4 回填 SQL + 管理端必填 |
| 共享库**单租户恢复困难**（Azure 指出的 pool 模型固有代价） | MVP 接受；未来 VIP 客户走独立部署（§1.3 扩展路径） |
| 租户生命周期（停用/注销/数据保留期） | 本期做 status=active/suspended（R8）；数据删除/导出策略列为后续 |
| 游客全量浏览的爬取风险 | 只读；写操作仍需验证；联系方式交换有额度制 |
| 公告被滥用（物业刷屏） | 本期无推送，影响面=首页一条卡片；后续可加频控 |
| 开放问题：同城排序是否按小区加权？ | 本期统一 `last_active_at`（与现有 feed 一致），上线看数据再定 |
| 开放问题：多城市后游客默认城市如何确定？ | 预留城市选择器（R6）；单城市运营期不阻塞 |
