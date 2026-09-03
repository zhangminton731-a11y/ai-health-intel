# CREDITS — 上游复用登记

本项目遵循"保留许可证文本与版权声明、逐项记录复用与修改"的合规原则（总控指令与设计规格 16 章要求）。

| 上游 | 许可 | 复用内容 | 上游位置 → 本项目位置 | 修改摘要 |
|---|---|---|---|---|
| [June_Public · scientific-information-hub (SIH)](https://github.com/mengsj08/June_Public) | MIT（Copyright (c) 2026 June Public contributors，见 `engine/LICENSE`） | 采集/标准化/去重/时效门/评分分层/JSONL 事实池/日报/静态页全链引擎 + doctor/tests | `workbenches/scientific-information-hub/` → `engine/` | 未修改引擎代码；仅新增本项目配置 `config/sources.json`、`config/profile.json` |
| [AI Hot](https://github.com/laolaoshiren/ai-hot) | MIT（见上游仓库 LICENSE） | GitHub Actions 双工作流编排模式（定时聚合 → 质量门 → 条件提交；workflow_run 失败隔离 + concurrency 去重 + Pages 部署） | `.github/workflows/aggregate.yml`、`deploy.yml` → 同名文件 | 按本项目改造：聚合命令换为 SIH CLI、去掉 pip 依赖安装（零依赖）、质量门宽松兜底（continue-on-error）、cron 频率改为每日 |
| [AI Hot](https://github.com/laolaoshiren/ai-hot) | MIT | 仓库布局思想（data 与站点入库、"数据即 JSON、站点只管渲染"） | 项目结构参考 | —— |

红线记录：June_Public 中 AGPL-3.0 子项目（project-canvas、scientific-pdf-bilingual-reader）与"仅限评估"子项目（comma-review-studio）代码**一律未复制**；ip-operations skills 许可未确认，未复用。
