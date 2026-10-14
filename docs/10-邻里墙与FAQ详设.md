# 10 · 邻里墙 & FAQ 详设（含合规调研）

> 状态：待评审（main）｜前置：多社区 SaaS + 生产化加固（docs/07/09）均已实施
> 诉求拆解：①邻居发表对社区的看法（UGC 交流墙）②FAQ（物业答疑）——两个独立诉求，合规属性完全不同。
> 原则：文档即蓝图；实施偏差回写本文。

## 1. 调研结论（微信官方文档）

### 1.1 类目与资质（核心变量）

| 结论 | 来源与要点 |
|---|---|
| **社交-社区/论坛类目需《非经营性互联网信息服务备案核准》** | 微信「服务类目」文档：社区/论坛、笔记、问答类目二选一提供（ICP 备案核准 / 机关信用代码证）；首次代码审核需当地互联网主管机关确认，**约 7 天** |
| **个人主体完全无法开通 UGC 类目** | 官方文档：个人主体开放类目不含社交；工具类目明确排除"用户自定义内容记录及分享" |
| **无零资质合规路径** | 文档明确：工具类若涉及"内容公开传播"即属社交范畴——即"公开的邻里墙"无法规避社交类目 |
| 个体工商户 = 非个人主体 | 可申请社交-社区/论坛类目并提交 ICP 备案材料（以微信实际提审要求为准） |

### 1.2 我们已有的合规基础（社交类目审核看重项，均为加分）

微信实名（openid）｜小区准入制（邀请码，天然限流+白名单）｜**msgSecCheck 先审后发**（fail-closed 降级待审）｜图片 mediaCheckAsync｜人工处置闭环（docs/09 P1-7）｜举报处置体系｜分钟级限流｜审计留痕。
**结论：本项目的治理能力符合"先审后发、实名、可处置"的监管方向，是类目申请的加分项。**

### 1.3 关键利好
ICP 备案（非经营性互联网信息服务备案）**本来就是上线必办项**（docs/05 第③步）——即社交类目所需的资质材料与既定上线流程重合，不是额外新增的行政成本，只是"类目选择"要在提审时变更。

## 2. 可行性分析

| 维度 | 结论 | 说明 |
|---|---|---|
| 技术可行性 | **高**（复用 ~80%） | feed 模式（物品列表）、内容安全（文本/图片）、举报处置、管理巡查、通知、限流全部现成；新增 posts/comments/likes 三张表 + 三四个页面 |
| 合规可行性 | **有条件可行** | 需社交类目 + ICP 备案（既定流程内）；**建议提审前在微信开放社区发帖确认"小区实名准入制邻里墙"的类目口径**（docs/09 风险项同款做法） |
| 产品可行性 | 中，需冷启动运营 | 空墙没人发 → 置顶公约/FAQ/活动帖铺垫（物业生产首批内容）；频控防灌水 |
| 治理成本 | 中 | UGC 增大巡查量 → 复用已有巡查/举报/人工审核闭环，新增帖子类型即可 |

## 3. 产品形态与分阶段路径

| 形态 | 发布权 | 类目风险 | 建议 |
|---|---|---|---|
| **Phase 1 · FAQ + 公告增强** | 仅物业/超管 | **零**（信息发布，不涉 UGC） | **本期实施**：物业发布「常见问题」置顶展示，住户只读+点赞；满足诉求② |
| **Phase 2 · 邻里墙** | 已验证住户（实名） | 需社交类目（§1.1） | **代码本期就绪，功能开关控制**：类目过审后 `NEIGHBOR_WALL_ENABLED=true` 开放；满足诉求① |
| （被拒备选）提议箱模式 | 住户提交→物业审核后以物业名义公示 | 零 | 若类目被拒的降级方案（发布权在物业，住户提交不公开传播）；本期不实现，仅预留设计 |

**推荐**：Phase 1 + Phase 2 一期开发（代码同批交付），运营上"物业先发内容铺垫 → 类目过审后开墙"。

## 4. 数据模型（迁移 `e1b8d2f74c63_neighbor_wall`）

```sql
posts             -- 帖子（topic=邻里话题 faq=常见问题）
  id PK、community_id FK idx、user_id FK idx、type varchar(10)   -- topic|faq
  title varchar(50) NOT NULL、content varchar(2000) NOT NULL
  images json（≤3 张 URL，走既有上传+mediaCheckAsync）
  status varchar(10) default 'published'   -- published|hidden
  sec_status varchar(10) default 'pass'    -- pass|pending|fail（复用内容安全）
  pinned bool default false、like_count int default 0、comment_count int default 0
  created_at、last_active_at
post_comments     -- 评论（仅 topic 帖可评论）
  id PK、post_id FK idx、user_id FK、content varchar(500)、
  sec_status varchar(10) default 'pending'、status varchar(10) default 'published'、created_at
post_likes        -- 点赞（幂等唯一键）
  id PK、post_id FK idx、user_id FK、created_at、UNIQUE(post_id, user_id)
reports.target_type 扩展：'post' | 'comment'
```
举报归属规则沿用 docs/07 §4.4：按被举报目标所属小区。

## 5. API 契约（新增）

### 用户端（均需登录；发帖/评论需已验证住户）
| 接口 | 说明 |
|---|---|
| `GET /api/posts?cursor&limit&type?(topic\|faq)` | 本小区帖子 feed：置顶(faq/pinned)优先 → last_active_at 倒序；游客只读 |
| `POST /api/posts` | `{type: "topic", title, content, images?}`；faq 仅物业/超管经管理端发布；**频控 5 帖/天**；title+content 过 msgSecCheck（fail-closed → sec_status=pending 仅作者可见，走 P1-7 人工处置） |
| `GET /api/posts/{id}` | 详情：内容/图片/作者摘要/点赞数/是否已赞/评论分页 |
| `DELETE /api/posts/{id}` | 作者删除 |
| `GET /api/posts/{id}/comments?cursor` | 评论列表（仅 visible+pass，时间正序） |
| `POST /api/posts/{id}/comments` | `{content}`；**频控 20 评/天**；msgSecCheck 先审后发同上 |
| `POST /api/posts/{id}/like`、`DELETE .../like` | 点赞/取消（幂等） |
| faq 帖规则 | type=faq 仅 admin 端发布（免微信审核，走 admin_logs 问责）；用户端 feed 中置顶优先、不可评论、不可被举报 |

### 管理端（/api/admin/*）
| 接口 | 说明 |
|---|---|
| `GET /api/admin/posts?page&status&keyword` | 巡查：全量/本小区帖子（含 hidden） |
| `POST /api/admin/posts/{id}/off`、`/pin` | 下架隐藏 / 置顶 |
| `POST /api/admin/faq` | 物业/超管发布 FAQ 帖（pinned 可选） |
| 举报扩展 | `reports.target_type` + 'post'/'comment'；处置动作联动 hidden |
| `GET /api/admin/pending-content` | 队列扩展：含 pending 状态的帖子 |

## 6. 页面设计（小程序 3 个新页 + 2 处入口）

| 页面 | 规格 |
|---|---|
| **pages/wall/wall**（邻里墙主页） | 顶部 Tab（话题\|FAQ）；帖子卡（作者/楼栋·已验证、标题、正文截断、图 1-3、点赞/评论数）；置顶帖带角标；FAB「发帖」（未验证→验证引导）；空态引导物业发 FAQ 铺垫 |
| **pages/wall/post**（帖子详情） | 内容全文+图片轮播、点赞按钮（动效）、评论列表+评论输入框（faq 帖无评论）；作者非本人可举报 |
| **pages/wall/edit** | 发帖表单：标题(≤50)+正文(≤2000)+图片(≤3，复用上传组件)；429 频控提示 |
| **入口**（2 处） | ① home 顶部（搜索框下）加「邻里墙」入口卡（图标+最近一条帖子摘要）；② 邻里墙内 FAQ 帖与公告卡互链。**tabBar 保持 4 个不动**（理由：核心动线是交易；数据证明粘性后再评估升 tab） |
| 管理后台 | admin-web 新增「帖子巡查」页（列表/下架/置顶）+「发 FAQ」入口；举报处置页支持新 target 类型 |

## 7. 治理规则

1. **准入**：发帖/评论需已验证住户（实名+实名小区），游客只读
2. **先审后发**：title/content 过 msgSecCheck（v2），异常降级 pending → 仅作者可见 → 人工处置（复用 docs/09 P1-7，拒绝=下架+通知+信用事件）
3. **图片**：先传后审（mediaCheckAsync 回调 risk → 帖子自动 hidden）
4. **频控**：发帖 5/天/人、评论 20/天/人、点赞 30/分钟（复用限流）；在墙帖子数上限 20/人
5. **禁止**：匿名、站外引流二维码（巡查处置）、转发扩散
6. **信用联动**：帖子/评论被拒 → 用户 violations+1（复用信用体系）
7. **审计**：管理端全部操作 admin_logs

## 8. 测试计划

1. pytest 新增 `test_wall.py`：feed 置顶排序与小区隔离（跨小区不可见）、发帖频控 429、faq 仅管理端可发、评论先审后发（pending 仅作者可见→人工放行）、点赞幂等、举报联动 hidden、信用联动、游客只读
2. 举报扩展回归：`test_multitenant.py` 举报归属测试加 post/comment 用例
3. 管理端：巡查列表隔离、faq 发布权限（住户 403）
4. 前端：tsc + 结构校验；新增页面纳入 validate.mjs 自动覆盖
5. 用户验收清单：发帖（含敏感词被拒）、评论、点赞、物业发 FAQ、巡查下架后小程序消失

## 9. 风险与开放问题

| 风险 | 处置 |
|---|---|
| **社交类目审核被拒** | Phase 1 形态先跑（零风险）；提审前开放社区确认口径；备案材料提前准备 |
| 冷启动空墙 | 物业发公约/FAQ/活动帖铺垫；感谢帖文化引流；空态文案引导 |
| 灌水/广告 | 频控+每日上限+巡查下架+信用联动；情节严重走封禁 |
| 类目审核期间功能藏不住 | 功能开关 `NEIGHBOR_WALL_ENABLED`（config），默认关闭，过审即开 |
| 开放问题：帖子是否支持"求帮助"类（借工具/找失物） | 建议支持（type=topic 内自然涵盖），不加独立类型；上线看数据 |
| 开放问题：tabBar 是否升第 5 个 tab | 本期否；预留（若 open data 显示高频使用再升级） |
