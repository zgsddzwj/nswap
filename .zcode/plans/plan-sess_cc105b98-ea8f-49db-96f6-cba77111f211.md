# 管理后台 React 重构 · 技术详设编写计划（本轮只写文档，不实施）

## 调研结论（将写入详设 §2）

| 方案 | 优势 | 不选/慎选原因 |
|---|---|---|
| **React Admin (marmelab)** | dataProvider 架构成熟，CRUD 效率高 | 建模为“资源 CRUD”，我们的举报处置/人工审批/邀请码批次等是**自定义领域流程**，dataProvider 会别扭；RBAC 等关键能力在付费企业版（145€/月起）；默认 Material UI |
| **Ant Design Pro** | 国内企业级标准、脚手架全（布局/i18n/mock） | UmiJS 重度绑定、 opinionated；AntD 设计体系与 Tailwind 相斥，与用户要求的 Tailwind 方向相悷 |
| **shadcn/ui + Tailwind 自由组合（Vite+React+TS+TanStack Query+React Router+react-hook-form+zod）** | 125k stars 的现代行业标准；**代码归项目所有**（copy-paste 模式）不锁死；dashboard/表格/表单/对话框模式齐全；完全契合 Tailwind；轻量 | 需要自己搭布局与细节（用现成 dashboard blocks 弥补） |

**选型：shadcn/ui 组合方案**（用户明确要 Tailwind；我们的页面是自定义领域流程而非通用 CRUD；代码自有可控）。

## 本轮要做的事（写一份详设文档并提交，不写代码）

写 `docs/08-管理后台React重构详设.md`，约 10 节：

1. **目标/非目标**：生产级 UI；保留两级分权；本期不做图表报表/国际化/暗色
2. **调研与选型**（上表 + 理由）
3. **架构**：SPA(admin-web/) ↔ JSON API(/api/admin/*) ↔ 复用现有 session cookie；同源部署（FastAPI 挂载 dist）→ 无 CORS；dev 用 Vite proxy 到 8001
4. **后端 JSON API 契约**（逐接口）：auth(login/logout/me)、stats、invites、announcements、items、reports(含 target 解析)、users、verify-requests、communities(超管)、password；分页改 page/page_size+total（管理表格需要总数）；错误沿用 {code,message} 信封；401/403 JSON 语义；权限守卫逻辑与现 SSR 完全一致（服务端强制）
5. **前端设计**：目录结构、路由表（/admin/login + 布局内 10 页）、页面逐页规格（字段/交互/空态/确认弹窗）、shadcn 组件清单（table/dialog/form/select/badge/toast/dropdown）、品牌色 #0E7A5A 对齐
6. **安全**：session cookie 不变；守卫全部服务端；XSS 由 React 转义；操作留痕 admin_logs 不变
7. **构建与部署**：Dockerfile 多阶段（node build → python 拷贝 dist）；FastAPI 挂载 /admin 静态；docker-compose 不变；本地 npm 用 npmmirror
8. **迁移策略**：M1 后端 JSON API+pytest → M2 admin-web 脚手架+登录+布局 → M3 十个页面 → M4 构建挂载+真机验收 → M5 删除 Jinja2 模板+SSR 路由 + 文档收尾；每步回归
9. **测试计划**：pytest JSON 接口套件（沿用多租户守卫测试改 JSON 断言）+ admin-web tsc/build + 用户浏览器验收清单
10. **风险**：session 在 SPA 的 cookie 行为、构建产物体积、Tailwind 版本选择（v4）等

完成后提交到 feat/saas-multitenant 分支，交你评审；实施等你确认后按 §8 分步进行。