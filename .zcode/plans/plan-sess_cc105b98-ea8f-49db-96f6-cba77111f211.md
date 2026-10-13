# 里程碑固化 + SaaS 多社区详设（不含任何功能代码）

## 步骤

1. **打 tag**：`git tag -a v0.1.0 -m "单社区 MVP 完整版：后端 + 小程序前端(17页) + 联系方式交换 + 管理后台"`
2. **开分支**：`git checkout -b feat/saas-multitenant`（tag 固化在 main 的当前提交上）
3. **核实补证**（写详设前逐项确认，避免设计写偏）：
   - transactions/reports/notifications 等表现有 community_id 覆盖情况
   - `community_info` 现返回内容、`get_default_community` 全部调用点
   - admin 全部页面/模板清单（分权改造点逐一登记）
   - serialize.py 中所有输出 building 的调用点（跨小区隐藏楼栋的改造点清单）
4. **写详设 `docs/07-多社区SaaS详设.md`**（项目"文档即蓝图"原则，中文，约 10 节）：
   1. 背景与目标 / 非目标（不做计费、不做全员通知、不做小程序内物业端）
   2. 角色与权限矩阵（游客/住户/楼长/物业管理员/平台超管）
   3. 数据模型变更逐表逐字段 + 迁移与回填方案
   4. 后端 API 详设：feed 双 scope 全语义（含未加入小区游客规则）、building 隐藏统一规则与实现点清单、community/info 语义修正、公告接口
   5. 管理后台多租户：逐页面改造表、新增「小区管理」「公告管理」页、模板改动清单
   6. 小程序端逐页改动（home 双 Tab、卡片小区名适配、公告页、verify/mine 兼容）
   7. 隐私与边界规则汇总（跨小区交易、搜索 scope、留言、收藏/交易卡片）
   8. 迁移部署与 seed 更新（双演示小区、物业管理员账号）
   9. 测试计划（pytest 新增清单 + E2E 扩展 + 验收标准）
   10. 风险与开放问题
5. **提交详设到 feat/saas-multitenant 分支**，交你评审；评审通过后再按详设分 M1~M5 实施（另行确认后开工）