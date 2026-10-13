# nswap · 邻里闲置交换小程序

以小区为单位的「邻里闲置交换站」：出售 / 赠送 / 换物 / 求购四形态，意向自由挑选、双向确认履约、感谢帖与信用档案。平台只做信息撮合与流程留痕，不介入资金。

```
├── backend/       FastAPI 后端（17+ 表、内容安全、交易状态机、管理后台、pytest）
├── miniprogram/   原生小程序前端（TypeScript + TDesign，17 页 + 5 组件）
├── docs/          调研 / PRD / 技术方案 / API 契约 / 上线清单 / 运营手册
└── docker-compose.yml   本地一键起 MySQL + 后端
```

## 本地跑通（三步）

```bash
# 1. 起后端（MySQL 8 + FastAPI，首次构建约 2 分钟）
docker compose up -d --build
# 后端就绪后初始化示例数据（3 个演示用户 + 5 件物品 + 5 个邀请码）
docker compose exec backend python scripts/seed.py
#    之后可访问 http://127.0.0.1:8000/admin  管理后台 admin / nswap123

# 2. 装前端依赖并构建 npm 包
cd miniprogram
npm install
npm run build:td   # 把 tdesign-miniprogram 构建到 miniprogram_npm/

# 3. 微信开发者工具导入 miniprogram/ 目录
#    测试号（touristappid）即可打开，无需 AppID
#    项目已配置「不校验合法域名」，本地直连 http://127.0.0.1:8000
```

开发者工具里点开首页即可看到示例数据。**联调双方**：进入「我的」页底部「开发者身份」切换 `dev-alice` / `dev-bob` / `dev-carol`（分别预置为已验证住户）。

> 不用 Docker 时：`cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`，
> `ENV=dev WX_CALL_MODE=mock .venv/bin/uvicorn app.main:app --port 8000`（默认 SQLite，微信接口全 mock）。

## 前端架构

- **双模式请求层** `services/api.ts`：本地开发走 `wx.request` + `X-DEV-OPENID` 模拟身份；云托管生产走 `wx.cloud.callContainer`（微信自动注入 `X-WX-OPENID`，免 token）。切换开关在 `config/index.ts` 的 `LOCAL_DEV`。
- **设计系统** `app.wxss`：青苔深绿主色（`--ns-brand: #0E7A5A`）+ 中性色阶 + 四形态色（出售绿/赠送橘/换物蓝/求购金），全部走 CSS 变量，支持**暗色模式**（`darkmode: true` + theme.json）。字阶 22–44rpx，8 的倍数间距，卡片圆角 20rpx。
- **状态与工具**：`utils/constants.ts` 全部枚举字典、`utils/list.ts` 游标分页工厂（items 字符串游标 / 其余 int 游标 / chat since 增量三种）、`utils/format.ts` 金额分↔元与相对时间。
- **页面**（17）：首页双列网格 feed、详情（轮播/留言板/按角色变化的底栏）、发布四宫格与差异化表单、意向管理、轻会话（5s 轮询）、交易约定（交接三方式+双向确认）、互评+感谢帖、小区验证（邀请码/担保码/人工审核）、我的（信用档案）等。
- **合规**：全局文案避开「购买/订单/支付」，价格展示为「参考价」；不采集定位、不强制手机号。

## 部署到微信云托管

1. 云托管创建环境与服务（服务名默认 `nswap`），后端镜像即 `backend/Dockerfile`；
2. 控制台开通「开放接口服务」与「消息推送」，回调地址 `/api/wechat/callback`；
3. 申请 4 个订阅消息模板，把模板 ID 填入后端 `.env` 的 `MSG_TPL_*` 与前端 `config/index.ts` 的 `SUBSCRIBE_TEMPLATES`；
4. 前端 `config/index.ts`：`LOCAL_DEV = false`，填 `CLOUD_ENV`（环境 ID）；开发者工具导入后上传代码。
5. 邀请码在管理后台按楼栋批量生成，交由居委会/物业/楼长发放（运营细节见 docs/06）。

## 已知事项

- **`GET /api/trades` 必须显式传 `status`**（`ongoing` / `completed` / `cancelled`）——后端不传时返回空列表（现有实现行为），前端已按此处理。
- **微信 `wx.request` 不支持 PATCH**：后端为 `arrange` 同时提供 `PUT`/`PATCH` 两个路由，小程序走 `PUT`。
- **云托管上传**：`wx.uploadFile` 直连公网域名无法注入 openid，生产环境上传走 `POST /api/uploads/base64`（callContainer 通道）；本地开发仍用 multipart `POST /api/uploads`。前端自动按模式切换。
- `GET /api/items/{id}` 每次浏览自增 view_count（无去重），详情页返回刷新属正常现象。
- 订阅消息模板 ID 未配置时，前端自动跳过授权弹窗，仅使用站内通知（不丢消息）。

## 验证情况

- 后端自带 pytest：19 项全过；`tsc --noEmit` 前端类型检查 0 错误；页面/组件/图标结构校验全绿。
- 全链路契约冒烟（登录→验证→上传→发布→意向→接受→私聊→约定→双向确认→互评→感谢→通知→收藏→编辑→下架）：41 项断言全部通过，前端依赖的字段名与后端实际响应逐项核对一致。
