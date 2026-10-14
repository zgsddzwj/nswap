# AGENTS.md — nswap 项目总览（给 AI 编码代理的接入指南）

> 邻里闲置交换小程序：以小区为单位的闲置物品交换平台（出售/赠送/换物/求购），
> 平台只做信息撮合与流程留痕，不介入资金。
> 本文件是代理的"地图"——先读这里，再按需深入子目录的同名 AGENTS.md 和 docs/。

## 仓库结构

```
backend/        FastAPI 后端（已完成，见 backend/AGENTS.md）
miniprogram/    微信原生小程序前端 + TypeScript + TDesign（见 miniprogram/AGENTS.md）
admin-web/      管理后台 SPA（Vite+React+TS+Tailwind，见 docs/08；dist 由 FastAPI 挂载到 /admin）
docs/           01调研 02PRD 03技术方案 04API契约 05上线Checklist 06运营手册 —— 文档即蓝图
.zcode/plans/   历史开发会话的实施方案（只读参考，勿改）
```

**开发顺序原则**：改接口先改 `docs/04-API契约.md`，改页面先对照 `docs/02-PRD.md` 的页面清单与流转图。

## 常用命令

```bash
# 后端（venv 已建在 backend/.venv）
cd backend && ENV=dev DATABASE_URL="sqlite:///./nswap.db" WX_CALL_MODE=mock \
  ENABLE_SCHEDULER=false PUBLIC_BASE_URL=http://192.168.0.230:8001 \
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
cd backend && ENV=dev DATABASE_URL="sqlite:///./nswap.db" WX_CALL_MODE=mock \
  ENABLE_SCHEDULER=false .venv/bin/python scripts/seed.py   # 建表+演示数据（可重复执行）
cd backend && ENV=dev DATABASE_URL="sqlite:///./test_pytest.db" WX_CALL_MODE=mock \
  ENABLE_SCHEDULER=false .venv/bin/python -m pytest tests/ -q

# 前端
cd miniprogram && npm install && npm run build:td   # 构建 TDesign 到 miniprogram_npm/
cd miniprogram && npm run typecheck                 # tsc --noEmit，改代码后必跑
```

## 本机环境事实（重要）

- **8000 端口被另一个应用占用（收粮收购平台），nswap 后端固定用 8001**。杀进程要按端口精确杀
  （`lsof -ti :8001`），不要 pkill 泛匹配，避免误伤用户其他服务。
- 前端本地模式地址 = 局域网 IP（`miniprogram/config/index.ts` 的 `LAN_IP`，当前 192.168.0.230）。
  本机 IP 变了要同步改。真机调试需手机与电脑同 Wi-Fi 且手机端打开"开发调试"。
- 本机 pip 装包必须加 `--only-binary :all:`（否则 cryptography 会走源码编译并卡死）；
  npm 用 `--registry=https://registry.npmmirror.com`；GitHub 直连常超时，克隆用 SSH。
- 演示身份与 `backend/scripts/seed.py` 一致：`dev_alice` / `dev_bob` / `dev_carol`（下划线）。
- 管理后台：React SPA 源码在 `admin-web/`（构建 `npm run build`，产物 dist 由 FastAPI 挂载 /admin）；
  JSON API 在 `/api/admin/*`（见 backend/AGENTS.md）；dev 用 `npm run dev`（5173，proxy 已配）。
  物业账号 `wy_admin`、超管 `admin`（演示密码 nswap123）。

## 多社区 SaaS 要点（feat/saas-multitenant 起）

- 小区 = 租户：`communities.status`(active/suspended)、`city` 为同城维度（空值不出现在同城）。
- feed 双 scope：`/api/items?scope=community|city`；未加入小区用户 community=空、city=全量。
- **跨小区隐私唯一规则**：viewer 与目标不同小区 → 所有序列化 building 输出空串 + community_name
  （serialize.py 的 `_same_community/_building_for/_community_name`）。新增带 user_summary/item_card
  的接口必须传 viewer，否则楼栋泄露。
- 跨小区交易仅允许 `place_method=face`（trades.py 校验）；举报归属=被举报目标小区。
- admin 两级分权：AdminUser.community_id（NULL=超管）。物业路由守卫 403；写操作校验目标归属。
- 新页面加 user_summary 时若忘记传 viewer，跑 `pytest tests/test_multitenant.py` 会失败。

## 硬性规则

1. **合规文案**：全局禁止出现「购买/下单/订单/支付/购物车」，统一用「交换/赠送/约定/意向」；
   价格一律展示为「参考价」；不调用任何定位接口、不强制手机号。
2. **隐私底线**：用户联系方式（contact_wechat/contact_phone/contact_enabled）绝不允许加入任何
   列表/详情/会话序列化，只能通过会话内交换接口返回（backend/tests/test_contact.py 有守卫测试）。
3. **微信平台限制**：`wx.request` 不支持 PATCH——后端新增有副作用的接口时同时提供 PUT 路由。
4. **枚举同步**：后端 models 的枚举字符串值改动必须同步 `miniprogram/utils/constants.ts`。
5. **验证后交付**：后端改动跑 pytest（24 项），前端改动跑 tsc + 页面结构校验；不提交未验证的代码。
6. 提交信息用中文、Conventional 风格（`feat:` / `fix:` / `chore:`）；仅在用户明确要求时 commit。
7. 面向用户的代码注释、错误提示、文档一律中文。

## 验证方式（无法跑微信开发者工具 GUI）

- 后端契约：pytest + 手写 curl/python 脚本对 8001 端口跑全链路（登录→验证→发布→意向→接受→
  聊天→约定→确认→互评→感谢→通知→收藏→联系方式交换）。
- 前端：tsc 类型检查 + 结构校验（app.json 页面↔磁盘四件套↔usingComponents↔tabBar 图标）。
- 视觉/交互：只有用户能在开发者工具里看，交付时明确告知用户需要本地预览的改动点。

## 联系方式交换策略（已实现，改动需谨慎）

默认不开放 → 用户在「我的」主动填写+开启 → 仅会话内（意向被接受后）交换 → 会员=已验证住户 →
发起方每日 3 次额度（UTC 日重置，对方未开放不扣费，同会话幂等）→ 一次交换双向解锁+双向通知
（contact_exchanges 表留痕）。详情见 docs/04-API契约.md §3.12。
