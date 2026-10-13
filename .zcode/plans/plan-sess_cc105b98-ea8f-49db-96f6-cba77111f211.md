# nswap 小程序前端 · 设计与实施计划

## 摘要

为已完成的 FastAPI 后端补齐整个小程序前端：设计一套「青苔深绿」主题、明暗双模式的设计系统，用 **原生小程序 + TypeScript + TDesign** 实现 17 个页面 + 5 个组件 + 双模式 API 层，并补上缺失的 README。唯一后端增量是一个约 20 行的 base64 上传端点（解决云托管模式下 `wx.uploadFile` 无法携带 openid 的问题）。

---

## 一、设计系统（NS Design）

**风格定位**：多抓鱼式的克制质感——大量留白、白卡片、单一品牌色、清晰的字阶。不做花哨渐变和玻璃拟态。

### 色彩令牌（app.wxss CSS 变量，前缀 `--ns-`）

| 令牌 | 浅色值 | 暗色值 | 用途 |
|---|---|---|---|
| `--ns-brand` | `#0E7A5A` 青苔深绿 | `#3AAE8A` | 主色：主按钮、选中态、tab 高亮、sell 角标 |
| `--ns-brand-light` | `#E7F3EE` | `#17302A` | 品牌浅底：横幅、选中 chip |
| `--ns-bg` | `#F6F7F9` | `#111417` | 页面背景 |
| `--ns-card` | `#FFFFFF` | `#1C2127` | 卡片 |
| `--ns-ink / -2 / -3` | `#1B2733 / #667385 / #9AA5B1` | `#E8ECF1 / #9AA5B1 / #636E7A` | 三级文本 |
| `--ns-line` | `#EEF1F4` | `#2A2F36` | 分隔线 |
| 四形态色 | sell=`--ns-brand`、give=`#D96A3C` 陶土橘、swap=`#4C6FB1` 雾蓝、want=`#B0812E` 芥末金（暗色下各提亮一档） | | 角标、四宫格、筛选 chip |
| 状态色 | success=brand、warning=`#B0812E`、danger=`#C9453B` | | 已预约/沉底/取消等 |

### 其他令牌

- **字阶**：44/36/32/30/28/26/24/22 rpx；价格用「小 ¥ + 大数字 + 700 字重」的多抓鱼式排版；`selling` 帖价格文案统一「参考价」
- **圆角**：卡片 20rpx、按钮 16rpx、胶囊 999rpx、图片 16rpx
- **间距**：8 的倍数栅格；页面左右 24rpx、卡片内 24rpx
- **阴影**：卡片 `0 4rpx 24rpx rgba(23,35,61,.04)`；底部操作栏上浮阴影
- **触控**：主按钮高 88rpx、cell 高 104rpx，底部固定栏全部加 `env(safe-area-inset-bottom)`
- **暗色模式**：`app.json` 开 `darkmode: true` + `theme.json`（导航/tabBar 双值），页面颜色全部走变量 + `@media (prefers-color-scheme: dark)` 覆盖；TDesign 通过 `--td-brand-color` 等变量对齐到 `--ns-*`
- **加载态**：home/detail 用 WXSS 骨架屏（微光动画）；列表统一「加载中… / 没有更多了」页脚

### 首页布局决策

双列**等高网格**（1:1 封面），不用瀑布流——更整洁对称，符合「简洁高级」目标，也避免原生瀑布流的高度估算缺陷。

## 二、技术架构

```
miniprogram/
├── project.config.json      # appid=touristappid、useCompilerPlugins:["typescript"]、urlCheck:false
├── package.json / tsconfig.json / typings/
├── app.json                 # 17 页注册、4 tab、darkmode、lazyCodeLoading
├── theme.json / sitemap.json / app.ts / app.wxss
├── config/index.ts          # LOCAL_DEV 开关、本地 baseURL、云托管 env、4 个订阅模板 id
├── services/
│   ├── api.ts               # 双模式请求层：dev→wx.request+X-DEV-OPENID；cloud→wx.cloud.callContainer(注入 X-WX-OPENID)
│   │                        #   统一拆 {code,message,data} 信封、422 兜底、401/403/429 统一提示策略
│   ├── auth.ts              # 启动静默登录、me 缓存与变更订阅、未读角标轮询
│   └── upload.ts            # 压缩(wx.compressImage q70)→上传：dev 走 multipart，cloud 走 base64 端点
├── utils/
│   ├── constants.ts         # 全部枚举字典：四形态/分类9/成色5/状态/交接方式的中文与颜色映射
│   ├── format.ts            # 分↔元、ISO→相对时间、好评率
│   ├── navigation.ts        # 通知 type→目标页 的路由映射
│   └── list.ts              # 游标分页 loader 工厂（items 字符串游标 / 其余 int 游标 / chat since 三种）
├── components/              # 5 个：item-card(网格+行两种模式)、filter-bar、status-badge、empty-state、want-sheet
└── pages/                   # 17 页（home、publish、publish/edit、messages、mine、detail、profile、
                             #   wants、chat、trade、review、verify、search、my-items、favorites、my-trades、agreement）
```

- **TDesign**（npm 安装，`miniprogram_npm/` 按仓库 .gitignore 约定不入库，README 写明「npm install + 构建 npm」步骤）：用于 button / icon / input / textarea / switch / tabs / popup / datetime-picker；胶囊标签、单元格、骨架屏等自绘以完全掌控视觉
- **tabBar 图标**：8 张 81×81 PNG（4 tab × 常态/选中，线性圆角笔画风格），离线用无头 Chrome 从 SVG 渲染（失败则降级 qlmanage / PIL）
- **头像昵称**：用最新的 `chooseAvatar` 开放能力 + `input type="nickname"`（wx.getUserProfile 已废弃）
- **合规文案**：全局只用「交换/赠送/约定/意向」，禁用购买/订单/支付；不调任何定位接口

## 三、页面实施（按依赖顺序分 5 组）

1. **脚手架**：工程配置、app 壳、设计令牌、config/utils/services、npm 依赖、tab 图标
2. **组件**：status-badge → empty-state → item-card → filter-bar → want-sheet
3. **浏览链**：home（搜索+筛选+感谢横滑+双列网格+下拉刷新/触底加载+未验证横幅）→ detail（轮播、参考价、卖家行、留言板、按角色/状态变化的底部操作栏、···举报菜单）→ profile（信用档案+TA的在架物品）→ search（历史关键词+结果网格）
4. **发布链**：publish 四宫格（未验证置灰引导）→ publish/edit（type 驱动的差异化表单：图片九宫格上传、分类宫格弹层、成色胶囊、价格+可小刀、想换什么/出价、编辑回填、429 频控提示）
5. **交易与个人**：wants（意向卡片、自由挑选接受/拒绝）→ chat（气泡、5s since 轮询、顶部物品卡、去约定）→ trade（状态步进条、三选一交接方式+时间选择器、双向确认、取消、完成后评价+感谢帖）→ review（1-3 星大卡片）→ verify（邀请码/担保码/人工审核三通道）→ messages（通知+会话双 tab、按 payload 路由、全部已读）→ mine（信用档案、头像昵称编辑、功能入口、管理员后台入口、LOCAL_DEV 身份切换器）→ my-items（状态 tab+管理操作）/ favorites / my-trades / agreement

## 四、后端唯一增量（约 20 行，向后兼容）

`backend/app/api/uploads.py` 增加 `POST /api/uploads/base64`（JSON `{filename, content}`，复用现有 save_upload 与校验）。原因：云托管 `callContainer` 自动注入 openid，但 `wx.uploadFile` 直连公网域名无法注入 → 401。本地开发不受影响（X-DEV-OPENID）。前端 upload.ts 按模式自动选择通道。

## 五、验证

1. `npx tsc --noEmit` 全量类型检查
2. Node 脚本校验：所有 JSON 可解析；app.json 页面↔磁盘文件↔usingComponents 路径↔tabBar 图标一一对应
3. **后端全链路冒烟**（backend/.venv + sqlite + mock，已确认被 .gitignore 覆盖）：启动 uvicorn，用两个 `X-DEV-OPENID` 身份 curl 跑通 登录→邀请码验证→发布→意向→接受→会话→约定→双方确认→互评→感谢帖，逐一核对响应字段名与游标格式（含已知的 trades status=all bug 规避）
4. 微信开发者工具的真机/模拟器视觉验收需要你本地操作（我无法运行开发者工具），README 提供三步快速开始

## 六、README 与交付

补写根目录 README.md：本地一键跑通（docker-compose + npm install + 构建 npm + 开发者工具导入）、双模式说明、身份切换器用法、云托管部署步骤、订阅模板配置、已知限制（云上传通道、trades all bug）。

完成后**不自动 git 提交**，由你 review 后自行提交。预计新增约 100 个文件。

## 七、边界与风险

- npm/pip 需要网络（pypi 此前可达；npm 必要时切 npmmirror 镜像）
- 开发者工具无法 headless 运行，视觉细节以静态检查+契约冒烟保障，最终以你本地预览为准
- 云托管真机链路（callContainer、订阅消息）在无 AppID 环境下不可验证，代码按文档实现并在 config 留配置位