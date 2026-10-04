# CREDITS — 上游复用登记

本项目遵循"保留许可证文本与版权声明、逐项记录复用与修改"的合规原则（总控指令与设计规格 16 章要求）。

| 上游 | 许可 | 复用内容 | 上游位置 → 本项目位置 | 修改摘要 |
|---|---|---|---|---|
| [AIHOT](https://github.com/KKKKhazix/AIHOT/tree/9848e936106db037d99a304887c36aad3fd0fad4) | MIT（Copyright (c) 2026 数字生命卡兹克，完整许可见 `assets/AIHOT-LICENSE.txt`，随站点发布） | 关于页 SignalRiver Canvas 流程动画；关于与反馈页面布局参考 | `apps/web/app/features/about/SignalRiver.tsx` → `assets/signal-river.js` | 保留曲线布局、脉冲、离屏缓存、主题适配；移除 React 依赖，按路由懒加载与销毁，支持动态减少动画偏好；提示文案改为本站实际筛选流程。曲线是示意，不表示实测流量或事件聚类。未复用品牌、作者资料及内容数据。 |
| [June_Public · scientific-information-hub (SIH)](https://github.com/mengsj08/June_Public) | MIT（Copyright (c) 2026 June Public contributors，见 `engine/LICENSE`） | 采集/标准化/去重/时效门/评分分层/JSONL 事实池/日报/静态页全链引擎 + doctor/tests | `workbenches/scientific-information-hub/` → `engine/` | 本项目新增配置与时效规则，并补充 RSS 1.0、Atom 原文链接及健康技术场景筛选 |
| [AI Hot](https://github.com/laolaoshiren/ai-hot) | MIT（见上游仓库 LICENSE） | GitHub Actions 双工作流编排模式（定时聚合 → 质量门 → 条件提交；workflow_run 失败隔离 + concurrency 去重 + Pages 部署） | `.github/workflows/aggregate.yml`、`deploy.yml` → 同名文件 | 按本项目改造：聚合命令换为 SIH CLI、去掉 pip 依赖安装（零依赖）、本次升级改为严格质量门与早间/日间滚动调度 |
| [AI Hot](https://github.com/laolaoshiren/ai-hot) | MIT | 仓库布局思想（data 与站点入库、"数据即 JSON、站点只管渲染"） | 项目结构参考 | —— |

红线记录：June_Public 中 AGPL-3.0 子项目（project-canvas、scientific-pdf-bilingual-reader）与"仅限评估"子项目（comma-review-studio）代码**一律未复制**；ip-operations skills 许可未确认，未复用。
