# 日期时间线与健康产业扩源验收（2026-10-04）

## 交付与未完成项

- 临床科研、健康产业取消“最新推荐／近 20 天”下拉框，统一为“月日 / 星期 / 条数”的日期展开组。最新日期默认展开，其他日期默认收起；筛选后保留各日期的展开状态。
- 月度资料后台加载并复用请求；失败时保留当前内容并提供重试。当前内容覆盖同 ID 历史副本。产业栏仅显示现行双次模型确认的单一产业主板块内容，旧规则双栏缓存不再混入。
- 新纳入 CMS 官方政策事实说明栏目，最近连续 10 篇有 4 篇达到 70 分（8 篇完成、2 篇评审未完成，后者不计通过）；按近 90 天抽样，包含 7–8 月内容。这不等于 9 月有 4 篇通过。
- 回填 FDA 5 篇、CMS 1 篇：共 6 篇、覆盖 6 个日期。其中 10 月 1 日 FDA 文章原本已在当前推荐；本次增加 5 篇九月历史产业资料。
- **未达到每天至少一篇：目标 34 天，已覆盖 6 天，仍有 28 天缺口。** 本轮调查不证明这些日期全网没有高质量文章，只说明已审计渠道及已取得材料未补齐目标。未改日期、降低评分门槛或重复计数。

## 纳排结果

评估的是内容阅读价值，不是信源声望或关键词。新源必须在固定的最近连续 10 篇中至少 3 篇有效双评达到 70；单篇发布仍使用 T1=70、T1_5=72、T2=76，98 封顶。未完成、材料不足、分类分歧不算通过。

| 候选栏目 | 样本数 | 达到 70 | 完成有效双评 | 结论 |
|---|---:|---:|---:|---|
| abbott_press | 10 | 1 | 10 | excluded |
| abbvie_press | 0 | 0 | 0 | pending |
| boston_press | 2 | 0 | 2 | pending |
| cms_fact_sheets | 10 | 4 | 8 | admitted |
| cms_news | 10 | 1 | 9 | pending |
| ema_news | 10 | 1 | 7 | pending |
| healthcaremea | 10 | 2 | 10 | excluded |
| hitconsultant | 10 | 1 | 9 | pending |
| medtronic_press | 10 | 1 | 9 | pending |
| mhra_news | 10 | 0 | 8 | pending |

共取得 82 篇固定样本用于审计；部分样本因正文、调用或评审一致性问题未完成。企业公告、媒体短讯和监管日常通知不能因涉及医疗就默认高分。

[逐篇评分、原文、两次评审回执](source-admission-2026-10-04-industry.json) · [逐日覆盖明细](industry-coverage-2026-09-01-2026-10-04.json)

## 已核验回填内容

| 原文日期 | 分数 | 原文 |
|---|---:|---|
| 2026-10-01 | 74 | [FDA Approves First Heart Valve Designed to Grow with Children](http://www.fda.gov/news-events/press-announcements/fda-approves-first-heart-valve-designed-grow-children) |
| 2026-09-21 | 86 | [Preliminary Calendar Year (CY) 2027 Medicare Clinical Laboratory Fee Schedule Payment Rates](https://www.cms.gov/newsroom/fact-sheets/preliminary-calendar-year-cy-2027-medicare-clinical-laboratory-fee-schedule-payment-rates) |
| 2026-09-17 | 74 | [FDA Approves First Gene Therapy for Pediatric Patients with Sanfilippo Syndrome Type A](http://www.fda.gov/news-events/press-announcements/fda-approves-first-gene-therapy-pediatric-patients-sanfilippo-syndrome-type) |
| 2026-09-15 | 71 | [FDA Launches Expedited IND Pilot, Begins Accepting Applications](http://www.fda.gov/news-events/press-announcements/fda-launches-expedited-ind-pilot-begins-accepting-applications) |
| 2026-09-04 | 79 | [FDA Grants Accelerated Approval to a New Breast Cancer Treatment](http://www.fda.gov/news-events/press-announcements/fda-grants-accelerated-approval-new-breast-cancer-treatment) |
| 2026-09-03 | 71 | [FDA Approves First Drug to Treat Alexander Disease](http://www.fda.gov/news-events/press-announcements/fda-approves-first-drug-treat-alexander-disease) |

## 代码路径与复现

- `engine/src/sih_ref/cms_facts.py`：从发布者现有 `/newsroom/fact-sheets/` 栏目链接抓取；固定最多两页，每页 50 条官方列表，不按分数挑选最近十篇。
- `engine/src/sih_ref/public_body.py`：读取 CMS 正文和 JSON-LD `datePublished`，不拿 `dateModified` 或 RSS 的更新时间冒充发布日期；有正文和日期的缓存直接复用。
- `scripts/backfill_industry.py`：只允许启用且准入通过的信源回填，按同一 GLM 评分策略评审，保留日期与回执。环境变量沿用 GitHub Secrets 对应的 SIH_LLM_*。
- `scripts/monthly_archive.py`：保留原有档案成员，只允许校验通过的双评分记录扩展；同 URL 的有效模型记录优先于未评旧副本，新增日期重建回溯日报。
- `scripts/quality_gate.py`：月度资料也复核模型分项、总分、主板块及策略版本。回填不改变当前榜单、RSS 的 10 天窗口。

```powershell
python scripts/backfill_industry.py --snapshot <已采集的信源快照.json> --start 2026-09-01 --end 2026-10-04 --report <评审结果.json>
python scripts/build_site.py
python scripts/quality_gate.py
```

## 验证

27 项引擎测试、133 项项目测试、46 项 DOM 测试；实际浏览器检查日期点击／键盘展开、手机 390px 视口，以及旧版混栏历史被排除。CMS 新适配器实网读取成功、取得 14 篇近 90 天栏目文章。云端部署结果见本次 PR 的检查记录。
