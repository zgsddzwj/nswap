# 邻里汇小区服务 · 社区闲置交换小程序

[![CI](https://github.com/zgsddzwj/nswap/actions/workflows/ci.yml/badge.svg)](https://github.com/zgsddzwj/nswap/actions/workflows/ci.yml)

以小区为单位的「邻里闲置交换站」：**出售 / 赠送 / 换物 / 求购**四形态，意向自由挑选、双向确认履约、感谢帖与信用档案。平台只做信息撮合与流程留痕，**不介入资金**——替代小区微信群刷屏卖闲置的合规解法。

## ✨ 亮点

- **准入制社区**：物业/居委会邀请码 + 老住户担保双通道，徽章「X栋·已验证」到栋不到户——没有身份验证的"附近的陌生人"社区做不起来（闲鱼鱼塘之死）。
- **商品状态机**：在售 → 已预约 → 双向确认完成 → 归档；14 天无互动自动沉底提醒、30 天自动归档——把"还在吗？"交给系统。
- **隐私优先**：上传图片统一**清除 EXIF（含 GPS）** + 平台水印 + HEIC 转 JPEG；联系方式交换默认关闭、已验证住户每日 3 次、会话内双向解锁、全程留痕；不采集定位、不强制手机号。
- **多社区 SaaS**：小区 = 租户；首页「本小区｜同城」双 Tab（跨小区隐藏楼栋、仅当面交接）；物业公告本小区可见；管理后台两级分权（平台超管 / 物业管理员）。
- **内容安全全覆盖**：文本 `msgSecCheck` 同步先检后发，图片 `mediaCheckAsync` 异步检测违规即隐藏，接口异常降级 fail-closed，举报→管理后台处置闭环。
- **合规自觉**：全局文案避开「购买/订单/支付」，价格展示为「参考价」；无支付、无抽佣、无付费推广——从竞品调研（闲鱼/转转/多抓鱼/Buy Nothing/Nextdoor）提炼的"取其精华去其糟粕"清单见 [docs/01](docs/01-调研报告.md)。

## 🏗️ 架构

```
├── backend/       FastAPI（SQLAlchemy 2.0 + Alembic · MySQL · 20+ 表 · 70 项 pytest · CI）
│   └── 镜像内置 admin-web/  React 管理后台（Vite+TS+Tailwind），由 FastAPI 同源挂载 /admin
├── miniprogram/   原生微信小程序（TypeScript + TDesign · 19 页 · 自建设计系统 · 暗色模式）
├── docs/          13 份文档：调研 / PRD / 技术方案 / API 契约 / 上线清单 / 运营手册
│                  / 多社区SaaS / 后台重构 / 生产化加固 / FAQ墙 / 图片安全 / 审查报告 / 部署指南
└── docker-compose.yml   本地一键 MySQL + 后端（管理后台随镜像构建）
```

鉴权设计：本地开发走 `wx.request` + `X-DEV-OPENID` 模拟身份；生产走 `wx.cloud.callContainer`——**云托管自动注入 `X-WX-OPENID`，全程免 token**。`wx.request` 不支持 PATCH，后端为交易约定同时提供 `PUT`/`PATCH` 双路由。

## 🚀 本地跑通（三步）

```bash
# 1. 起后端（MySQL 8 + FastAPI，管理后台随镜像构建，首次约 2 分钟）
docker compose up -d --build
docker compose exec backend python scripts/seed.py   # 3 个演示用户 + 5 件物品 + 邀请码
#    管理后台 http://127.0.0.1:8000/admin  admin / nswap123（仅本地演示）

# 2. 前端构建 npm 包（TDesign）
cd miniprogram && npm install && npm run build:td

# 3. 微信开发者工具导入 miniprogram/ 目录
#    测试号（touristappid）即可打开，无需 AppID；已配置「不校验合法域名」
```

开发者工具里首页即可看到示例数据。「我的」页底部可切换 **开发者身份** `dev_alice / dev_bob / dev_carol`（已预置为已验证住户），双开即可模拟买卖双方全流程。

> **不用 Docker 时**：`cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt`，
> `ENV=dev WX_CALL_MODE=mock .venv/Scripts/uvicorn app.main:app --port 8001`（默认 SQLite、微信接口全 mock；
> 小程序本地模式默认连 **8001**，与 docker 路线的 8000 不同——见 `miniprogram/config/index.ts`）。
> 此路线管理后台需先手动构建：`cd admin-web && npm install && npm run build`。

## 📚 文档（docs/）

| # | 文档 | 内容 |
|---|---|---|
| 01 | [调研报告](docs/01-调研报告.md) | 闲鱼/转转/多抓鱼/Buy Nothing/Nextdoor 取精去糟 |
| 02 | [PRD](docs/02-PRD.md) | 功能架构、7 大模块、17+2 页清单与跳转地图 |
| 03 | [技术方案](docs/03-技术方案.md) | 架构、数据模型、鉴权与内容安全设计 |
| 04 | [API 契约](docs/04-API契约.md) | 前后端接口契约（含枚举与错误码） |
| 05 | [上线 Checklist](docs/05-上线Checklist.md) | 个体户/备案/类目/隐私/提审全流程 |
| 06 | [运营手册](docs/06-运营手册.md) | 邀请码发放、楼长制度、冷启动 |
| 07-11 | SaaS / 后台重构 / 生产化加固 / FAQ 墙 / 图片安全 | 五份详设 |
| 12 | [代码审查报告](docs/12-代码审查报告.md) | P0×2 / P1×9 / P2×20 问题清单与修复状态 |
| 13 | [部署指南](docs/13-部署指南.md) | **微信云托管生产 runbook**（环境变量表/微信侧配置/发布步骤） |

## ☁️ 部署上线

生产路线为**微信云托管**（免域名/备案证书/运维）：Git 关联仓库直接部署 `backend/Dockerfile`，MySQL + COS + 开放接口服务一体；小程序改 `config/index.ts` 切云托管模式后上传提审。完整步骤、环境变量表与上线检查清单见 **[docs/13-部署指南](docs/13-部署指南.md)**。

生产化配置速查（细节见 docs/09 与 README 下表）：

| 能力 | 配置 | 说明 |
|---|---|---|
| **图片存储** | `STORAGE_BACKEND=cos` + `COS_*` | **生产必须**：云托管容器无状态，`local` 重启即丢图 |
| 登录防爆破 | `RATE_LIMIT_ENABLED=true` | 登录 IP 10次/5分钟、账号失败锁定；写接口分钟级限流 |
| 错误监控 | `SENTRY_DSN=`（留空不启用） | 5xx 自动上报，请求带 `X-Request-Id` |
| 备份 | `backend/scripts/backup.sh` | 另在云托管控制台开启 MySQL 每日自动备份 |
| 图片安全 | 自动 | EXIF（含 GPS）清除 + 水印 + HEIC 转码，fail-closed |
| 智能分类 | 自动 | 发布免选分类，词表在 `services/categorize.py` |

## ⚠️ 已知事项

- **存量 MySQL 升级**：自 v0.1.0 起新增联系方式交换与多社区表，需执行 `alembic upgrade head`（CI 已有空库全链迁移守卫）；全新部署直接跑通。
- **上线后立即改默认密码**（管理后台右上角）；`ADMIN_SESSION_SECRET` 必须配强随机串（docs/12 P0-2）。
- `GET /api/trades` 须显式传 `status`（`ongoing/completed/cancelled`）。
- 云托管生产上传走 `POST /api/uploads/base64`（callContainer 通道，自动注入身份）；本地用 multipart，前端自动切换。
- 订阅消息模板未配置时自动降级为站内通知，不丢消息。

## ✅ 验证情况

- 后端 **pytest 70 项全过**；CI 含**数据库迁移链守卫**（MySQL 8 + SQLite 双环境空库全链 `alembic upgrade head`）、admin-web 构建、小程序 tsc + 结构校验。
- 全链路契约冒烟 41 项断言通过（登录→验证→上传→发布→意向→接受→私聊→约定→双向确认→互评→感谢→通知）。

## 🗺️ Roadmap

- [ ] docs/12 审查清单修复（P0-1 迁移链已完成 ✅，剩余：会话密钥 fail-fast、凭证图私有读、chat 空会话轮询、会话未读等）
- [ ] 邻里墙 Phase 2（UGC 动态，开关已预留、详设见 docs/10）
- [ ] AI 辅助发布（拍照识别品类 + 建议描述 + 参考价）
- [ ] 交换积分（限定品类）

---

> **免责声明**：本项目为社区公益性质的闲置物品信息撮合工具，不介入任何资金往来；用户协议要求当面验货、钱货两清。上线运营请遵守微信小程序平台规范与当地法规（备案、类目、内容安全义务）。

觉得有帮助请点个 ⭐
