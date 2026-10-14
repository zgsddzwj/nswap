# 08 · 管理后台 React 重构详设

> 状态：**已实施**（分支 `feat/saas-multitenant`，pytest 36 项 + SPA 挂载/API/越权 curl 实测全过）
> 实施修订（M1-M4 中发现并回写）：
> ① **M4/M5 合并执行**：/admin 前缀冲突——SSR 不先让位，SPA 无法挂载验收；因此 M4 即删除 SSR 路由与 templates；
> ② **组件未用 shadcn CLI**：改为其"代码归项目所有"模式的手绘实现（Radix Dialog + Tailwind，品牌色 #0E7A5A），
>    避免 CLI 交互与外部 registry 依赖；视觉与 shadcn 一致；
> ③ **dist 路径双候选探测**：本地（仓库根/admin-web/dist，三层）与容器（/app/admin-web/dist，两层）布局不同，
>    main.py 按候选列表探测；
> ④ 举报处置 Dialog 的 decision 直接作为 mutate 参数（避免 React setState 闭包旧值 bug）；
> ⑤ 依赖版本：Tailwind v4（@tailwindcss/vite）+ Vite 6 + React 18 + Radix Dialog + sonner，构建产物 gzip 101KB；
> ⑥ **路由 basename 修正**（用户验收发现）：BrowserRouter basename="/admin" 下所有 `to`/`navigate` 必须用
>    basename 内相对路径（如 `/invites` 而非 `/admin/invites`），否则跳到 /admin/admin/* 被兜底重定向回看板，
>    表现为"二级页面无法跳转"；登录成功需 qc.clear() 清理登录前的 401 错误缓存。
> 现状：管理后台为 FastAPI + Jinja2 SSR + Bootstrap（原单社区 MVP 取舍，"免前端构建链"），
> UI 非生产级、交互为整页刷新，且已暴露模板级 bug（如 Jinja2 3.x 无 `| zip` 过滤器导致的 500）。
> 原则：**文档即蓝图**；实施中的偏差必须回写本文。

## 1. 目标与非目标

### 1.1 目标
1. **生产级管理后台**：现代设计系统（Tailwind + shadcn/ui）、SPA 交互（无整页刷新）、表格/表单/弹窗/toast 完整体验。
2. **功能对等迁移**：现有 SSR 后台的全部能力不丢失——两级分权（平台超管/物业管理员）、数据隔离、路由守卫、越权 403、操作留痕（admin_logs）。
3. **架构升级**：后端 admin 从 SSR 表单改为 **JSON API**，前端独立工程（`admin-web/`），与小程序端（miniprogram/）并列。
4. **部署形态不变**：仍与后端同容器（FastAPI 挂载构建产物），同源无 CORS。

### 1.2 非目标（本期不做）
- 图表报表（看板先做统计卡片 + 小区概览表；Recharts 图表列后续）
- 国际化（纯中文）、暗色模式（shadcn 原生支持，后续一行配置）
- 移动端深度适配（管理后台以桌面为主，仅做基础响应式）
- 管理端功能新增（纯对等迁移 + 交互升级；新功能另立项）

## 2. 业内方案调研与选型

| 方案 | 定位 | 优势 | 不选原因 |
|---|---|---|---|
| **React Admin**（marmelab，MIT） | 资源 CRUD 型 admin 框架（dataProvider/authProvider 架构，50+ API 适配器） | CRUD 场景效率极高；内置 TanStack Query/React Hook Form | 建模为"资源 CRUD"，而我们的举报处置（目标解析+联动下架）、人工审批（凭证图）、邀请码批次等是**自定义领域流程**，dataProvider 模型别扭；RBAC 等关键能力在付费企业版（145€/月起）；默认 Material UI 设计体系 |
| **Ant Design Pro** | 国内企业级中后台脚手架（UmiJS + AntD） | 脚手架最全（布局/权限/i18n/mock），国内用户熟悉 | UmiJS 重度绑定、opinionated；AntD 设计体系与 Tailwind 相斥，与既定 Tailwind 方向相悖；体量大 |
| **shadcn/ui + Tailwind 自由组合**（选定 ✅） | 现代组合式方案：Vite + React 18 + TS + Tailwind + shadcn/ui（Radix 之上的 copy-paste 组件，125k stars）+ TanStack Query + React Router + react-hook-form + zod | **组件源码归项目所有**（不锁库）；dashboard/表格/表单/对话框现成模式齐全；完全契合 Tailwind；轻量可控；社区最活跃 | 布局与细节需自己搭（官方 dashboard blocks 可弥补） |

**选型结论**：`shadcn/ui 组合方案`。决定性因素：① 用户明确要求 Tailwind；② 我们的页面是自定义领域流程而非通用 CRUD；③ 代码自有，后续任意定制不付费不受制于框架升级。

## 3. 系统架构

```
┌─────────────────────────┐      同源（生产）        ┌──────────────────────────┐
│ admin-web/ (Vite+React) │ ──── /api/admin/* ────→ │ FastAPI                  │
│ SPA：React Router 页面  │      JSON + session      │  /api/admin/*  JSON API  │
│ TanStack Query 拉数据   │ ←──── cookie ────────   │  SessionMiddleware（不变）│
└─────────────────────────┘                          │  GET /admin/*  → dist 静态│
   dev：Vite server(5173) proxy /api → 127.0.0.1:8001│  （挂载 admin-web/dist）  │
   prod：vite build → FastAPI 挂载 dist（同源）        └──────────────────────────┘
```

- **同源免 CORS**：生产 SPA 由 FastAPI 在 `/admin/*` 挂载静态文件，API 在 `/api/admin/*`，cookie 天然同源；开发用 Vite proxy 转发 `/api`，同样无 CORS。
- **鉴权沿用**：现有 `SessionMiddleware`（HttpOnly signed cookie）不变，登录后发 session；SPA fetch 带 `credentials: "include"`（同源默认生效）。
- **路由前缀分离**：页面 `/admin/*`（静态），API `/api/admin/*`（JSON），互不冲突。

## 4. 后端 JSON API 契约（`/api/admin/*`）

### 4.0 通用约定
- **信封**：沿用 `{code, message, data}`；HTTP 401=未登录（SPA 收到即跳登录页）、403=越权（toast 提示）、400=参数/业务错误（toast message）。
- **鉴权依赖**：`get_current_admin(request, db)`（session → AdminUser，缺失 401 JSON）；`require_super`（community_id 非空 → 403）。**隔离与守卫逻辑与现 SSR 完全一致**（服务端强制，前端角色显隐仅为体验）。
- **分页**：管理表格需要总数 → 改用 `page`(1 起) + `page_size`(默认 20，≤100)，响应 `{list, total, page, page_size}`。
- **写操作**：全部沿用 admin_logs 留痕；目标归属校验（物业只能动本小区）逻辑不变。

### 4.1 接口清单

| 接口 | 方法 | 请求 | 响应 data | 权限 |
|---|---|---|---|---|
| `/api/admin/auth/login` | POST | `{username, password}` | admin_dto | 公开（错误 401） |
| `/api/admin/auth/logout` | POST | — | `{ok:true}` | 登录 |
| `/api/admin/auth/me` | GET | — | admin_dto | 登录 |
| `/api/admin/stats` | GET | — | `{users, verified, items, trades_done, pending_reports, pending_verify, active_invites, communities_overview?}` | 登录 |
| `/api/admin/invites` | GET | `?page&page_size&status?` | `{list:[invite_dto], total,...}` | 登录（物业限本小区） |
| `/api/admin/invites` | POST | `{building, count≤100, days≤90, batch_note?, community_id?（仅超管）}` | `{created:[codes]}` | 登录 |
| `/api/admin/invites/{id}/revoke` | POST | — | `{ok:true}` | 登录+归属 |
| `/api/admin/announcements` | GET/POST/DELETE | 见 §4.2 | 公告 dto | 登录 |
| `/api/admin/items` | GET | `?page&page_size&status?&type?&keyword?` | item 行（含 community_name）+ total | 登录 |
| `/api/admin/items/{id}/off` | POST | — | `{ok:true}` | 登录+归属 |
| `/api/admin/reports` | GET | `?status?&page...` | 行含 `target_text`（服务端解析"物品#12 标题"/"留言#3 内容…"）、`community_name`、reporter 摘要 | 登录 |
| `/api/admin/reports/{id}` | POST | `{decision: resolve\|dismiss, apply_action: bool, note?}` | `{ok:true}` | 登录+归属 |
| `/api/admin/users` | GET | `?q?&page...` | 用户行（building/community_name/role/verified/status/trades_done/violations） | 登录 |
| `/api/admin/users/{id}/ban\|unban\|elder` | POST | — | `{ok:true}` | 登录+归属 |
| `/api/admin/verify-requests` | GET | `?page...` | pending 申请（含申请人摘要、proof_image） | 登录 |
| `/api/admin/verify-requests/{id}/approve`、`/reject` | POST | approve 无体；reject `{note?}` | `{ok:true}` | 登录+归属 |
| `/api/admin/communities` | GET/POST | POST `{name, city, district?, address?, admin_username, admin_name?, admin_password}` | 列表含统计与物业账号 | **超管** |
| `/api/admin/communities/{id}/toggle-status` | POST | — | `{status}` | **超管** |
| `/api/admin/communities/{id}/reset-password` | POST | — | `{new_password}`（**仅此一次返回**） | **超管** |
| `/api/admin/sec-checks` | GET | `?page...` | 审核记录列表 | **超管** |
| `/api/admin/password` | POST | `{old_password, new_password}` | `{ok:true}` | 登录 |

`admin_dto`：`{id, username, name, role: "super"|"community", community: {id,name,city} | null}`。
`invite_dto`/公告 dto 均带 `community_id` + `community_name`；报告/用户/物品行均带 `community_name`（超管全局视图用）。

### 4.2 旧 SSR 接口处置
全部 `GET/POST /admin/*` 的 SSR 路由与 `app/admin/templates/` 在 M5 删除；`/admin` 前缀让位给 SPA 静态挂载。删除前 JSON 与 SSR 短暂并存（前缀不同，无冲突）。

## 5. 前端设计（admin-web/）

### 5.1 目录结构
```
admin-web/
├── package.json / vite.config.ts / tsconfig.json / index.html
├── src/
│   ├── main.tsx / App.tsx        # Router + QueryClientProvider + Toaster
│   ├── lib/api.ts                # fetch 封装：信封拆解、401 跳登录、403/400 toast
│   ├── lib/auth.tsx              # useAdmin()（GET /auth/me 缓存）、LoginGuard、RoleGate(super)
│   ├── components/ui/*           # shadcn 组件（button/table/dialog/form/input/select/badge/toast(sonner)/card/dropdown/tabs）
│   ├── components/layout/        # Sidebar（按角色显隐）+ Header（身份+改密+退出）
│   └── pages/                    # Login + AdminLayout 内 9 页（见 5.2）
```

### 5.2 路由与逐页规格

| 路由 | 页面 | 关键规格 |
|---|---|---|
| `/admin/login` | 登录 | 用户名/密码；401 toast「用户名或密码错误」；成功进 `/admin` |
| `/admin` | 看板 | 7 张统计卡；超管追加「小区概览」表（名称/城市/状态/住户/物品/物业账号数） |
| `/admin/invites` | 邀请码 | 生成表单（楼栋/数量/有效期/批次 + **超管带小区 Select**）；生成成功弹 Dialog 展示新码列表（一键复制全部）；列表（状态筛选 Tab、码 code 样式、作废带确认） |
| `/admin/announcements` | 公告 | 发布表单（标题≤100/正文 + 超管带小区 Select）；列表（标题/小区/正文截断/发布人/时间/删除确认） |
| `/admin/items` | 内容巡查 | 筛选（状态/类型/关键词）+ 表格 + 「强制下架」确认；超管带小区列 |
| `/admin/reports` | 举报处置 | 状态 Tabs（待处理/已处置/已驳回/全部）；卡片列表（目标类型 badge、target_text、原因红字、举报人/时间）；处置 Dialog（同时执行处置 checkbox + 备注 + 处置/驳回） |
| `/admin/users` | 用户管理 | 顶部「待审验证」卡（申请人/楼栋/凭证图点击新窗预览/通过-驳回）；搜索框；用户表（超管带小区列；封禁/解封/设楼长确认） |
| `/admin/communities` | 小区管理（超管） | 开通表单（小区信息+物业账号）；列表（状态 badge、住户/物品/账号）；停用/启用确认；重置密码 → Dialog 一次性展示新密码 |
| `/admin/sec-checks` | 内容安全（超管） | 只读表格 |
| `/admin/password` | 修改密码 | 旧密码+新密码表单 |

### 5.3 设计系统
- 品牌主色 `#0E7A5A`（对齐小程序青苔深绿）映射 shadcn `--primary`；中性灰底白卡、圆角 8px、字号 12/14/16。
- 语义色：成功=主色、危险=red-600（封禁/驳回/下架）、警示=amber（待处理 badge）。
- 空态统一「暂无数据」组件；加载态 TanStack Query `isLoading` → 骨架/行级 spinner。

## 6. 安全设计

1. **守卫全部服务端**（R3 教训）：SPA 的角色显隐只是体验；每个 JSON 接口独立做 401/403 判定与目标归属校验，pytest 守卫对齐（§8）。
2. session cookie（HttpOnly + 签名）不变；登录/登出/过期语义与现有一致。
3. React 默认转义，禁止 `dangerouslySetInnerHTML`；凭证图/头像一律 `<img src>` 新窗预览。
4. admin_logs 留痕不变（含 SPA 新交互的每个写操作）。
5. 重置密码一次性返回（JSON），不落日志；前端 Dialog 展示并提示复制。

## 7. 构建与部署

- **构建**：`cd admin-web && npm install && npm run build` → `admin-web/dist`（Vite `base: "/admin/"`）。
- **挂载**（FastAPI）：`GET /admin/assets/{path}` → StaticFiles(dist/assets)；`GET /admin` 与 `GET /admin/{path:path}`（非 /api）→ `FileResponse(dist/index.html)`，实现 SPA history 路由 fallback。
- **Dockerfile 多阶段**：`FROM node:20-alpine AS web`（build admin-web）→ `FROM python` 拷 `dist`；docker-compose 服务不变。
- **本地开发**：`npm run dev`（5173，proxy /api → 127.0.0.1:8001）；或直接 build 后访问 `http://127.0.0.1:8001/admin`。
- **npm 源**：npmmirror（本机约束，见根 AGENTS.md）。

## 8. 实施步骤（每步全量回归）

| 阶段 | 内容 | 验收 |
|---|---|---|
| M1 | 后端 JSON API（`/api/admin/*` 全量）+ pytest：把 `test_security_admin.py`/`test_multitenant.py` 的 admin 断言改为 JSON（登录/401/403/隔离/归属/一次性密码） | 36+ 项全过 |
| M2 | admin-web 脚手架（Vite+TS+Tailwind+shadcn init+Query+Router）+ 登录页 + AdminLayout（角色侧边栏）+ 看板 | 浏览器登录后看板可见 |
| M3 | 业务九页逐个实现（invites→announcements→items→reports→users→communities→sec-checks→password） | 每页对等 SSR 功能 |
| M4 | FastAPI 挂载 dist + Dockerfile 多阶段 + 用户浏览器验收（清单见 §9） | 生产形态可访问 |
| M5 | 删除 SSR 路由与 templates、修根/子 AGENTS.md 与 README、详设状态回写 | 全量回归 + 结构干净 |

## 9. 测试与验收清单

- **pytest**：M1 建立接口套件（登录/未登录 401/物业越权 403/手输超管接口 403/本小区隔离/跨小区写 403/重置密码一次性/改密后旧密码失效）；既有 36 项回归。
- **admin-web**：`tsc --noEmit` + `vite build` 通过。
- **用户验收清单**：登录；看板统计与小区概览；邀请码生成→复制→作废；发公告→小程序首页公告卡同步可见；巡查强制下架→小程序列表消失；举报处置（勾选同时执行→物品归档）；人工审批通过→住户变已验证；开通新小区→物业账号可登录且只见本小区；重置密码一次性展示；改密码。

## 10. 风险与决策点

| 风险/决策 | 处置 |
|---|---|
| Tailwind 版本（v4 新 CSS 配置）与 shadcn init 的兼容 | 优先 v4；若 init 模板有坑回退 v3.4（实施 M2 时定，回写本文） |
| session cookie 与 SPA fetch | 同源默认携带；Vite proxy 保证 dev 同源；若遇 SameSite 问题在 SessionMiddleware 配置 same_site="lax"（默认即 lax） |
| 路由冲突（/admin 页面 vs /api/admin JSON） | 前缀天然分离；M5 删 SSR 后 /admin 由静态接管 |
| 构建产物体积 | shadcn 按需拷贝组件，非整库引入；预期 <500KB gzip，不优化 |
| 工作量 | M1 ≈ 半个会话；M2-M3 ≈ 1-2 个会话；M4-M5 ≈ 半个会话 |
| 开放问题：是否要暗色/图表 | 本期不做（§1.2）；shadcn+Recharts 预留 |
