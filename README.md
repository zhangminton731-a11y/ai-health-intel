<img src="assets/company-logo.png" width="197" height="85" alt="循证奇点">

# 奇点医研 · 循证奇点出品

从公开信源到可追溯的医学科研与健康产业信息。

面向临床研究者的 AI 科研信息与合作入口，医院科研为主，企业 AI 升级为辅。展示外部论文、方法工具、政策和产业信息，不公开团队自有项目案例。

[线上网站](https://zhangminton731-a11y.github.io/ai-health-intel/) · [九月档案](https://zhangminton731-a11y.github.io/ai-health-intel/#daily?date=2026-09-30) · [自动化状态](https://github.com/zhangminton731-a11y/ai-health-intel/actions) · [需求反馈](https://github.com/zhangminton731-a11y/ai-health-intel/issues) · [版本记录](CHANGELOG.md)

**2026-10-04 信源与栏目更新：** 按最近连续 10 篇中至少 3 篇达到 70 分审核新增源，接入 NEJM、The Lancet、JAMA、Annals of Internal Medicine、The BMJ 的公开摘要索引频道及 FDA 官方公告，启用源 19 → 25。当前文章只进入一个主板块，研究证据与产业事件分别呈现。[纳排标准、逐篇审计与栏目规则](docs/source-admission-and-sections.md)

**2026-10-04 编辑评分升级：** 生产筛选改为智谱 `glm-5.3-flash` 两次独立阅读价值评估，五维分项由代码验算、总分封顶 98；取消关键词累加入选。Logo 区域同步压缩。[评分机制与验收](docs/editorial-reading-value.md)

**2026-10-04 档案更新：** 医学标识、开源入口、月份目录与点阵日历；19 个启用信源；九月恢复 762 条原始资料，筛选出 120 条可读资料和 22 份回溯日报。[品牌、信源与档案验收](docs/brand-sources-archive-20261004.md)

[处理链路升级](docs/pages-upgrade-acceptance.md) · [界面与接入实测](docs/editorial-acceptance-20261004.md) · [服务器的企业价值与采购条件](docs/server-business-case.md)

## 当前功能

- **临床科研**：论文精选、方法与工具、政策动态；支持研究设计、数据处理、AI 分析、研究验证标签。
- **健康产业**：新品与方案、技术进展、融资与合作、市场准入、综合动态。
- **实时热点**：事件摘要、来源聚合与关注指数；不把单站采集量冒充全网热度。
- **奇点日报**：今日出刊、按原文日期归档、月份折叠目录和可点击日历；实心点表示有内容，灰点表示未收录日报。
- 两个入口分别提供本期重点、搜索和按原文日期分组的信息流。全站搜索、热点榜仍可使用。日报按原文日期归集，左侧选择日期，每天最多 5 件有摘要的大事，展示类别、摘要和原文。只显示有内容的日期；默认最新一期可能早于今天，不拿旧闻冒充当天事件。
- 手机底部导航、完整换行标题、摘要展开、原文跳转、日报复制与网站分享。
- June 团队介绍、个人主页、商务微信 **13028564458**，请备注公司 / 职务 / 需求。
- “更多”提供 Agent 接入、关于、反馈，不显示更新日志。
- Agent 接入提供 Skill、本地 MCP、RSS、静态 API 四种方式，附安装提示词、配置复制、llms.txt 和 OpenAPI。
- 反馈支持 2000 字内容、选填邮箱和本地截图预览；复制后由访客发送到商务微信，截图另行添加，尚未接入自动收件服务。
- 深色、跟随系统、浅色三种主题；桌面左下角和手机“更多”提供切换，记住用户选择。
- 25 个启用信源，按研究机构、期刊、官方机构、专业媒体、企业发布和社区线索分别标识；本轮 6 个新增频道有真实 3/10 准入回执，原有 19 个源不冒称已全部通过新标准。
- 桌面左下角及手机“更多”提供 GitHub 开源入口。品牌使用团队提供的循证奇点公司 Logo，站点名称仍为奇点医研；七个导航入口增加统一线稿图标。

当前文章的主板块由两次模型判断一致后确定：论文证据和方法属于临床科研；上市、采购、融资与准入等具体事件属于健康产业。关键词只用于辅助主题标签，不决定分数或主板块。分类不代表期刊等级或人工逐篇审核；国内科研政策与资助的官方原文信源仍需补齐，空栏目如实显示。

产业前沿的方法参考：[Digital Oracle 核验与适用边界](docs/digital-oracle-reference.md)。已查看其市场信号、申报搜索、失败隔离与快照结构；本项目未安装运行其预测能力，未实现自动多源事件核验。

合作入口将用户引导到微信；网站没有客户资料数据库，也没有自动读取访客联系方式。内测期间由负责人记录实际新增联系和有效合作需求。

## 信源与筛选

| 类型 | 信源 |
|---|---|
| 期刊 | npj Digital Medicine、Nature Medicine、Nature Biomedical Engineering、Journal of Medical Internet Research、JMIR AI、JMIR mHealth and uHealth、JMIR Medical Informatics |
| 公开摘要索引 | NEJM、The Lancet、JAMA、Annals of Internal Medicine、The BMJ；通过 Europe PMC 按 ISSN 获取已索引且有摘要的文章，可能存在索引延迟 |
| 官方机构 | NIH 科研资助与通知、EMA 监管与程序指南、FDA 官方公告、CMS 政策事实说明 |
| 研究机构 | MIT News · Health |
| 专业媒体 | MedTech Dive、STAT、MedCity News、Medical Device Network、Crunchbase News |
| 企业发布 | Apple Newsroom、Google Blog、Oura |
| 社区线索 | Hacker News |

研究与企业发布分别标识；来源身份不等于每项产品主张已得到临床验证。一般科技或财经报道须有明确的医疗健康阅读价值，不能因出现 AI 或健康关键词进入推荐。

北京时间 Day 0～10 为当前有效内容；未来、无日期、超过 10 天的记录归档。当前榜单、今日出刊、当前 API 与 RSS 均来自同一当前集合，不用旧条目补足数量。网页打开时再次检查日期，停更后过期条目不继续出现在推荐中。

既有[信源准入审计](docs/source-admission-2026-10-04.json)保留当时的关键词规则与原始分数，仅作为历史记录，已不用于当前入选决策。生产环境每篇文章独立接受模型双评；来源等级只调整门槛，不直接增加分数，也不让整本期刊自动入选。阅读价值不是临床证据等级或疗效评分。

新增来源使用[最近十篇模型准入审计](docs/source-admission-2026-10-04-editorial.json)。来源准入的 70 分与单篇发布的 T1/T1_5/T2 门槛分开；网络失败、材料不足和模型分歧均保留记录，不当作零分或达标。

产业扩源第二轮审计了 10 个候选栏目、取得 82 篇固定样本；CMS 政策事实说明以最近连续十篇中 4 篇达到 70 分通过准入。[纳排与逐篇回执](docs/source-admission-2026-10-04-industry.json) · [时间线及扩源验收](docs/date-timeline-industry-acceptance.md)。截至本次回填，9 月 1 日至 10 月 4 日的达标产业资料覆盖 **6 / 34 天**，每天至少一篇的目标仍未完成。

## 九月资料档案

最初从 54 个 Git 采集快照恢复 762 条去重原始记录、120 条可读资料。本次增加 5 篇经现行双次模型评审确认的九月产业资料，目前为 **767 条原始记录、125 条可读资料、22 份回溯日报**。旧版未重评记录不再混入产业时间线。日报日历仍有 8 天空缺；所有回溯日报明确标注整理方式，不宣称它们在历史当天已出刊，资料范围并非全网完整收录。

- [浏览科研资料](https://zhangminton731-a11y.github.io/ai-health-intel/#jingxuan?month=2026-09) · [浏览产业资料](https://zhangminton731-a11y.github.io/ai-health-intel/#industry?month=2026-09)
- [日报合订本](output/site/archive/2026-09/daily.md) · [原始记录及快照来源](output/archives/2026-09.json)

两栏以日期展开／收起；进入栏目后后台载入月度资料并缓存，当前内容先呈现。长期档案不受近 20 天滚动窗口影响，不混入当前推荐、热点与 RSS。后台加载失败可重试，已呈现的当前文章保留。

[本次真实信源验收与限制](docs/sih-upgrade-acceptance.md) · [原有时效边界验收](docs/freshness-gate-acceptance.md)

## 更新与异常通知

早间目标暂定为**北京时间 09:00 前**。每天计划在 05:17、07:17、09:17、12:17、15:17、18:17、21:17 采集。GitHub Actions 可能延迟，不能承诺精确到点；页面展示真实采集时间。

采集 → 构建 → 全量质量校验 → 提交数据 → Pages 部署。质量门失败不提交新产物；少于一半信源成功、过期批次或不同接口数据不一致均阻断发布。线上检查任务计划在 09:23 与 21:23 检查已部署的数据。

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 配置：

- `FEISHU_BOT_WEBHOOK`：负责人提供的群机器人 Webhook。
- `FEISHU_BOT_SECRET`：如机器人启用了签名校验，填写对应签名密钥。

通知包括采集 / 校验失败、部署失败、当天早间内容未上线、超过 36 小时停更及部分信源失败。未配置机器人时只输出未启用提示，不能视为已经送达。不要把机器人地址或密钥写入代码或公开 Issue。

当前通知与采集都依赖 GitHub Actions。如果必须保证固定时限及调度平台故障时也能告警，需要另外确定外部调度/监控服务；本版本不预先引入付费服务。

### 信源异常诊断与恢复

RSS 失败现在保留不含正文或凭据的请求诊断，区分网络、限流、HTTP、非订阅页面与 XML 解析错误。最多尝试 3 次，采用递增等待并尊重 `Retry-After`；记录最后成功时间、连续失败次数与恢复状态。公网监控只对确认送达的同类异常做 24 小时去重，连续 3 批失败升级通知，恢复后通知一次。飞书配置缺失仍明确报出，不能当作通知已送达。

状态缓存、诊断位置、权限与待验收项见 [RSS 恢复说明](docs/source-recovery-2026-10-02.md)。

## Agent / Skill / API

[2026-10-04 接入实测](docs/editorial-acceptance-20261004.md)：API、RSS 和 MCP 数据链路已有公网验收记录；客户端安装与稳定性结论以该记录的实际测试范围为准。早期 9 月 27 日记录仅供历史追溯。

部署后可匿名读取以下地址，无需 API Key：

| 相对网站根目录的路径 | 用途 |
|---|---|
| `api/v1/items.json` | 当前有效条目，含原文、日期、来源、主题和溯源 |
| `api/v1/health.json` | 批次时间与来源健康 |
| `api/v1/briefing.json` | 最新有内容日期的日报，含 edition_date 和近 10 天日期目录 editions |
| `api/v1/archive/index.json` | 长期月份目录、条目数及回溯日报目录 |
| `api/v1/archive/2026-09.json` | 九月可读资料与回溯日报，保留原文日期 |
| `archive/2026-09/records.json` | 九月原始记录及恢复来源 |
| `archive/2026-09/daily.md` | 九月日报合订本 |
| `feed.xml` | RSS 2.0 订阅 |
| `sih-intel.zip` | 可供 Agent 安装的 Skill |
| `sih-intel/SKILL.md` | 接入说明与时效要求 |
| `sih-intel/README.md` | Skill 安装与更新说明 |
| `sih-mcp.zip` | 可选的本地 stdio MCP 包 |
| `sih-mcp/README.md` | MCP 安装和客户端配置说明 |
| `llms.txt` | Agent 数据入口索引 |
| `openapi.json` | OpenAPI 3.1 静态接口定义 |

这是随采集批次更新的静态 API。搜索和多维筛选由接入方执行，不能通过 URL 查询参数调用服务端搜索。条目提供 `sections`、`categories`、`research_stages`、`reading_value_score` 和 `editorial`，支持读取栏目及双次评分回执。每次读取先检查 `generated_at`；手机端安装 Skill 取决于所使用的 Agent 客户端。模型调用发生在采集后台，浏览器不持有密钥；本版本没有站内 AI 聊天。

## 本地运行和测试

采集与构建使用 Python 3.10+ 标准库。可选 MCP 接入单独安装固定版本的官方 SDK，见 [安装说明](integrations/mcp/README.md)；没有远程托管 MCP 地址。网页无需第三方脚本或样式 CDN。Node 24.15+ 仅供 DOM 交互测试。

```bash
PYTHONPATH=engine/src python -m sih_ref.cli run \
  --config config/sources.json --profile config/profile.json \
  --output-dir output --live
python scripts/build_site.py
python scripts/quality_gate.py
python -m unittest discover -s engine/tests -p 'test_*.py'
python -m unittest discover -s tests -p 'test_*.py'
npm ci --ignore-scripts
npm test
```

PowerShell 下设置 `$env:PYTHONPATH='engine/src'` 后运行相同的 Python 命令。翻译使用缓存与失败熔断，翻译不可用时保留原文。

恢复历史月度资料时，使用包含完整 Git 历史的 checkout，执行 `python scripts/monthly_archive.py --month 2026-09`，再构建并运行质量门。正常定时采集只读取已保存档案，不反复扫描 Git 历史。

MCP 使用独立虚拟环境安装 `integrations/mcp/requirements.txt`，再用该环境执行 `python -m unittest discover -s tests_mcp -p 'test_*.py'`。此测试启动真实 stdio 服务，验证发现工具、调用、筛选、错误与恢复；测试数据来自本地夹具，部署后仍需验证线上端点。

## 10 天内测

本次代码完成后，先完成真实安卓 / 微信内置浏览器验收和飞书送达测试，再记录连续 10 天的实际结果：

- 09:00 时网站是否有当天批次，信源失败数，是否收到正确告警。
- 每天抽查 10 条（不足则全查）的相关性、重复、翻译与原文链接。
- 手机上能否完成查找、读原文、复制日报、添加商务微信。
- 有效企业联系人和具体合作需求；由负责人记录，站内尚无转化统计。

建议验收线：10/10 天早间可用、抽查相关率 ≥80%、无连续停更未发现、手机核心路径可用。引流效果目标需负责人结合渠道与访问量另定，不能用低访问量下的零线索直接判断产品价值。

## 结构与许可

`engine/` SIH 内核；`config/` 信源与规则；`scripts/` 构建、公开接口、校验和通知；`templates/` 页面；`skills/` 接入包；`output/` 实际批次；`.github/workflows/` 采集、部署、监控与 CI。

项目 MIT，上游复用见 [CREDITS](CREDITS.md)。来源文章的内容权利归各自发布方。本站内容由公开信源自动整理，译文仅供参考，请以原文为准；不构成诊疗或投资建议。
