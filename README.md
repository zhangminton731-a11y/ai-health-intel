# 循证奇点 · Evidence Singularity

面向临床研究者的 AI 科研信息与合作入口，医院科研为主，企业 AI 升级为辅。展示外部论文、方法工具、政策和产业信息，不公开团队自有项目案例。

[线上网站](https://zhangminton731-a11y.github.io/ai-health-intel/) · [需求讨论](https://github.com/zhangminton731-a11y/ai-health-intel/issues/1) · [版本记录](CHANGELOG.md)

> 本分支是 2026-09-27 改版，是否已上线请以 PR 合并和 Pages 部署结果为准。

## 当前功能

- 默认首页“医学科研”：论文精选、方法与工具、政策动态；支持研究设计、数据处理、AI 分析、研究验证标签。
- 第二入口“产业前沿”：新品与方案、技术进展、融资与合作、市场准入、综合动态。
- 两个入口分别提供本期重点、搜索和按原文日期分组的信息流。全站搜索、热点榜仍可使用。日报按原文日期归集，左侧选择日期，每天最多 5 件有摘要的大事，展示类别、摘要和原文。只显示有内容的日期；默认最新一期可能早于今天，不拿旧闻冒充当天事件。
- 手机底部导航、完整换行标题、摘要展开、原文跳转、日报复制与网站分享。
- June 团队介绍、个人主页、商务微信 **13028564458**，请备注公司 / 职务 / 需求。
- “更多”提供 Agent 接入、关于、反馈，不显示更新日志。
- Agent 接入提供 Skill、本地 MCP、RSS、静态 API 四种方式，附安装提示词、配置复制、llms.txt 和 OpenAPI。
- 反馈支持 2000 字内容、选填邮箱和本地截图预览；复制后由访客发送到商务微信，截图另行添加，尚未接入自动收件服务。
- 深色、跟随系统、浅色三种主题；桌面左下角和手机“更多”提供切换，记住用户选择。
- 17 个启用信源，按研究机构、期刊、官方机构、专业媒体、企业发布和社区线索分别标识。

规则分类是初步导航，不代表期刊等级或人工逐篇审核；不生成影响因子、交易概率或政策放宽结论。国内科研政策与资助的官方原文信源仍需补齐，空栏目如实显示。

产业前沿的方法参考：[Digital Oracle 核验与适用边界](docs/digital-oracle-reference.md)。已查看其市场信号、申报搜索、失败隔离与快照结构；本项目未安装运行其预测能力，未实现自动多源事件核验。

合作入口将用户引导到微信；网站没有客户资料数据库，也没有自动读取访客联系方式。内测期间由负责人记录实际新增联系和有效合作需求。

## 信源与筛选

| 类型 | 信源 |
|---|---|
| 期刊 | npj Digital Medicine、Nature Medicine、Nature Biomedical Engineering、Journal of Medical Internet Research、JMIR AI |
| 官方机构 | NIH 科研资助与通知、EMA 监管与程序指南 |
| 研究机构 | MIT News · Health |
| 专业媒体 | MedTech Dive、STAT、MedCity News、Medical Device Network、Crunchbase News |
| 企业发布 | Apple Newsroom、Google Blog、Oura |
| 社区线索 | Hacker News |

研究与企业发布分别标识；来源身份不等于每项产品主张已得到临床验证。一般科技或财经来源必须同时满足健康场景和技术线索，才能进入推荐。

北京时间 Day 0～10 为当前有效内容；未来、无日期、超过 10 天的记录归档。榜单、日报、API 与 RSS 均来自同一当前集合，不用旧条目补足数量。网页打开时再次检查日期，停更后过期条目不继续出现在推荐中。历史记录保存在 `output/`，当前页面聚焦有效内容。

[本次真实信源验收与限制](docs/sih-upgrade-acceptance.md) · [原有时效边界验收](docs/freshness-gate-acceptance.md)

## 更新与异常通知

早间目标暂定为**北京时间 09:00 前**。每天计划在 05:17、07:17、09:17、12:17、15:17、18:17、21:17 采集。GitHub Actions 可能延迟，不能承诺精确到点；页面展示真实采集时间。

采集 → 构建 → 全量质量校验 → 提交数据 → Pages 部署。质量门失败不提交新产物；少于一半信源成功、过期批次或不同接口数据不一致均阻断发布。线上检查任务计划在 09:23 与 21:23 检查已部署的数据。

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 配置：

- `FEISHU_BOT_WEBHOOK`：负责人提供的群机器人 Webhook。
- `FEISHU_BOT_SECRET`：如机器人启用了签名校验，填写对应签名密钥。

通知包括采集 / 校验失败、部署失败、当天早间内容未上线、超过 36 小时停更及部分信源失败。未配置机器人时只输出未启用提示，不能视为已经送达。不要把机器人地址或密钥写入代码或公开 Issue。

当前通知与采集都依赖 GitHub Actions。如果必须保证固定时限及调度平台故障时也能告警，需要另外确定外部调度/监控服务；本版本不预先引入付费服务。

## Agent / Skill / API

[2026-09-27 接入实测](docs/access-verification-2026-09-27.md)：本地下载与数据链路通过，公网资源仍为 404，实际客户端安装/订阅尚未验收。

部署后可匿名读取以下地址，无需 API Key：

| 相对网站根目录的路径 | 用途 |
|---|---|
| `api/v1/items.json` | 当前有效条目，含原文、日期、来源、主题和溯源 |
| `api/v1/health.json` | 批次时间与来源健康 |
| `api/v1/briefing.json` | 最新有内容日期的日报，含 edition_date 和近 10 天日期目录 editions |
| `feed.xml` | RSS 2.0 订阅 |
| `sih-intel.zip` | 可供 Agent 安装的 Skill |
| `sih-intel/SKILL.md` | 接入说明与时效要求 |
| `sih-intel/README.md` | Skill 安装与更新说明 |
| `sih-mcp.zip` | 可选的本地 stdio MCP 包 |
| `sih-mcp/README.md` | MCP 安装和客户端配置说明 |
| `llms.txt` | Agent 数据入口索引 |
| `openapi.json` | OpenAPI 3.1 静态接口定义 |

这是随采集批次更新的静态 API。搜索和多维筛选由接入方执行，不能通过 URL 查询参数调用服务端搜索。条目新增 `sections`、`categories` 和 `research_stages`，支持接入方按两个板块筛选。每次读取先检查 `generated_at`；手机端安装 Skill 取决于所使用的 Agent 客户端。本版本没有站内 AI 聊天或付费模型调用。

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
