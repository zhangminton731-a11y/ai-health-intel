# SIH CEO Mobile Implementation Plan

**Goal:** 完成面向医院端与消费健康 CEO 的可内测情报站改版。
**Architecture:** 扩充并校验输入，统一推荐池生成静态页面和机器接口；采集/构建失败不发布。
**Tech Stack:** Python 3.10+ 标准库、HTML/CSS/JS、GitHub Actions / Pages。
**Spec:** ../specs/2026-09-27-sih-ceo-mobile-design.md

## Constraints
不接入付费 LLM、不创建用户数据库、不自动加微信、不提交密钥；仅用户指定的 13028564458 为商务微信。

## Task 1: 信源与场景相关性
- [x] tests/test_site_upgrade.py 先验证 RDF、Atom alternate、自定义领域必要词与医院内容正反例。
- [x] engine/src/sih_ref/sources.py 解析 RDF 命名空间与 Atom alternate；core.py 可选 required_topic_terms 与 required_technology_terms。
- [x] config/sources.json 加入 7 个经实时验证的入口；profile.json 院端+消费健康范围。
- [x] 标准库 unittest，逐源真实采集，记录来源日期和输出。

## Task 2: 手机界面、联系与机器接口
- [x] scripts/build_site.py 保留数据契约，新增场景/category 与采集时间；模板单独保存 templates/site.html。
- [x] scripts/export_feeds.py 从同一 current 集合输出 api/v1/items.json、health.json、briefing.json 和 feed.xml；禁止私有字段。
- [x] skills/sih-intel/SKILL.md 自包含接入指导，构建分发 ZIP；不依赖付费模型或账号。
- [x] 页面实现完整标题、搜索、场景/信息类型过滤、日报复制、原文跳转、合作微信复制、介绍与接入页。
- [x] 保持原有时效边界测试；新增投影一致性与输入转义测试。

## Task 3: 发布质量与异常通知
- [x] tests/test_site_upgrade.py 复现第6行损坏、缺少health、批次不一致均错误通过。
- [x] scripts/quality_gate.py 全记录与投影校验；可识别空合法池，失败关闭。
- [x] scripts/notify_feishu.py 仅环境读取 Webhook/签名，测试走 mock。
- [x] aggregate.yml 调整早间与日间调度、序列化并发、只提交 output；质量失败阻断；失败调用通知。
- [x] deploy.yml 只允许 main 聚合触发部署；发布失败通知。
- [x] 本地完整测试、构建、质量门、git diff --check；上传代码 PR，写清未接飞书和未实机验收。

实际完成情况与仍待手机/飞书验收的边界见 ../../sih-upgrade-acceptance.md。
