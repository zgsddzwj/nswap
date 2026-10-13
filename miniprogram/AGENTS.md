# AGENTS.md — miniprogram（微信小程序前端）

> 接入前先读仓库根目录的 AGENTS.md（局域网地址/合规文案/验证规则）。

## 技术栈与结构

原生小程序 + TypeScript（project.config.json 的 useCompilerPlugins）+ TDesign（tdesign-miniprogram，
npm 源码在 node_modules，`npm run build:td` 产出到 miniprogram_npm/，后者被 .gitignore 排除——
新环境必须先 `npm install && npm run build:td`）。

```
config/index.ts   # 唯一环境开关：LOCAL_DEV、LAN_IP(真机)、CLOUD_ENV、订阅模板 ID、DEV_IDENTITIES
services/
├── api.ts        # 双模式请求层：dev→wx.request+X-DEV-OPENID；cloud→wx.cloud.callContainer
│                 #   （生产真实登录，openid 由微信注入）。统一拆信封、422 兜底、toastError
├── auth.ts       # ensureLogin/refreshMe/setMe + onMeChange 订阅 + 未读角标 refreshUnreadBadge
└── upload.ts     # 压缩(q70)→上传：dev 走 multipart，cloud 走 /api/uploads/base64；chooseImages
utils/
├── constants.ts  # 全部枚举字典（四形态/分类9/成色5/状态/交接方式/通知图标）——与后端枚举值强耦合
├── format.ts     # 分↔元(splitPrice/yuanToCents)、relTime、goodRate、toIso
├── navigation.ts # 通知 type→目标页映射（新通知类型必须在此登记）
└── list.ts       # createListLoader 游标分页工厂（refresh/loadMore/finished）
components/       # item-card(grid/row 双模式) filter-bar status-badge empty-state want-sheet
pages/            # 17 页，每页 ts/json/wxml/wxss 四件套
```

## 设计系统（app.wxss 的 CSS 变量，改动走变量、禁止硬编码颜色）

- 主色 `--ns-brand: #0E7A5A`（青苔深绿）；四形态色 sell绿/give橘/swap蓝/want金（`--ns-*`）；
  中性色阶 `--ns-bg/card/ink/ink-2/ink-3/line`；语义色 success/warning/danger。
- **暗色模式**：`app.json darkmode:true` + theme.json（导航/tabBar）+ 页面样式全部走变量 +
  app.wxss 末尾 `@media (prefers-color-scheme: dark)` 统一覆盖。新增颜色必须同时定义明暗两套。
- TDesign 主题经 `--td-*` 变量映射到 `--ns-*`（见 app.wxss），组件只会用到已全局注册的：
  t-icon/t-button/t-input/t-textarea/t-switch/t-popup/t-loading（app.json usingComponents）。
- 复用基类：.ns-card .ns-btn(--primary/--ghost/--soft/--plain/--sm) .ns-cell .ns-price .ns-pill
  .ns-footer-bar(底部操作栏+安全区) .ns-skeleton(骨架) .ns-list-footer。首页是**双列等高网格**
  （封面 1:1），不要改成瀑布流（设计决策）。

## 页面开发约定

- 页面 json 只写 `navigationBarTitleText`（+按需 enablePullDownRefresh/onReachBottomDistance）；
  公共组件已在 app.json 全局注册（lazyCodeLoading=requiredComponents 会摇树）。
- 列表页用 `createListLoader`：items 用字符串游标、其余接口用 int 游标、chat 用 since 轮询(5s)——
  三种游标不要混用；页脚统一「加载中/没有更多了」。
- 金额：输入用 `yuanToCents` 校验，展示用 `splitPrice` + `.ns-price`（小¥大数字）；文案「参考价」。
- 登录态：onShow 里 `refreshMe()`；需要验证资格的操作被 403 时引导去 `/pages/verify/verify`。
- 合规：全局禁止「购买/下单/订单/支付/购物车」字样（提审红线），统一「交换/赠送/约定/意向」。
- 头像昵称用微信开放能力（button open-type="chooseAvatar" + input type="nickname"），
  禁用已废弃的 wx.getUserProfile。

## 联调与真机

- 本地模式（LOCAL_DEV=true）请求 `http://{LAN_IP}:8001`；后端启动/seed 命令见根 AGENTS.md。
- 身份切换：「我的」页底部开发者身份 dev_alice/dev_bob/dev_carol（对应 seed 演示用户，
  均已验证；切身份会 reLaunch）。
- 真机：手机与电脑同 Wi-Fi + 小程序内右上角胶囊→开发调试→打开调试；LAN_IP 变了要改 config；
  游客模式（touristappid）不能真机预览，需在 project.config.json 填正式 AppID。
- 生产：`LOCAL_DEV=false` + `CLOUD_ENV`/`CLOUD_SERVICE`/`CLOUD_PUBLIC_BASE_URL` 填云托管控制台值。

## 验证

- `npm run typecheck`（tsc --noEmit）——改任何 ts 后必跑。
- 结构校验：app.json 页面 ↔ 磁盘四件套 ↔ usingComponents 路径 ↔ tabBar 图标 PNG 逐一存在
  （历史校验脚本见根 AGENTS.md「验证方式」，可让代理现写 node 脚本执行）。
- 无法 headless 运行开发者工具：视觉与交互由用户真机/模拟器验收，交付时列出待验收点。
