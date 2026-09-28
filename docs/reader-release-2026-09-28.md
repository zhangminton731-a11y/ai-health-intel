# 奇点医研读者功能验收 · 2026-09-28

## 内容与页面
- 17 个来源全部采集成功，243 条原始记录，28 条当前推荐；北京时间 10:48 完成，未达到 09:00 前目标。
- 当前与历史共 48 条相关内容，最早原文日期 9 月 9 日。近 20 天回顾独立筛选，当前推荐、热点和 RSS 不回填旧内容。
- 医学科研/产业前沿按目标读者展示推荐理由；产业子栏目统一四字；每日简报改为奇点日报。
- 12 个中美官方政策代表节点，含上海中试基地、广州数据标注试点；按年份、国家、试点筛选。所有节点保留原文、文件性质、编辑解读、适用边界。
- 2026-08-18 候选文件为《关于印发进一步深化“六个拓展” 做实家庭医生签约服务若干措施的通知》，8 月 18 日署期，8 月 25 日公开。与用户所指是否完全一致尚待标题确认，不作“全面放松红线”解读。
- 关于页展示用户提供的奇点医研交流群二维码原图，10 月 5 日起自动隐藏失效二维码，以微信联系作为后备。增加科研平台支持合作。

## 验证
- Python 业务测试 48 项，核心引擎 27 项，DOM 24 项，MCP 协议测试 1 项通过。
- 发布质量门检查同批次、当前推荐时效、API/RSS 一致性，以及历史日期、原文与 API 一致性。
- 本地 HTTP 下载/API/RSS/Skill 资源校验和真实 MCP stdio 调用通过。
- 浏览器连接返回 nodeRepl.fetch request failed，未获得实际桌面/安卓视觉验收；DOM 测试不能替代真实手机测试。
- Skill 客户端实际安装触发、第三方 RSS 阅读器体验尚未实测。

## 来源与复现
政策明细及每项官方链接见 config/policy_timeline.json，页面 #policy。历史补采执行 scripts/backfill_history.py，报告 output/history-backfill-report.json。欧洲 PMC 历史接口返回 503，未使用该失败请求的数据；改用 MedCity News 公开 RSS 分页，四页各 30 条成功后按日期、健康与技术相关性筛选。

## 上线与公网复验

PR #3 已合并。首轮 Pages 部署成功；随后手动触发 main 的自动采集工作流 36372433384，再由工作流触发 Pages 部署 36372458589，均成功。

最新云端批次：2026-09-28 11:07:14 北京；Nature Medicine 返回不可解析内容，16/17 来源成功，状态 complete_with_warning。页面显示部分来源不可用，当前仍有 28 条推荐（科研16、产业12），另有20条历史补充，共48条。最早原文日期9月9日。

公网的三项核心 API、RSS、Skill/MCP 下载包和说明、OpenAPI、llms.txt 均 HTTP 200。通过公网下载的 MCP 包原样启动真实 stdio，工具发现以及健康、论文筛选、日报、空结果调用成功。API 按 OpenAPI 校验，RSS 与 API 的28条内容一致。线上政策与历史 JSON 和页面一致，二维码字节与用户原图完全相同。

线上 HTML 的 DOM 执行无错误，科研16/16、产业12/12条推荐理由可见，政策地图12节点、合作3项。这里仍不是视觉或安卓真机验收。

发现并修正验证脚本对 Linux LF / Windows CRLF 的字节差异误报；比较全部文本内容，下载包仍保持原样运行。

尚未实测 Skill 在具体 Agent 客户端的安装触发、第三方 RSS 阅读器和实际扫码入群。仓库没有配置飞书 secrets，异常通知未启用。

- 网站：https://zhangminton731-a11y.github.io/ai-health-intel/
- 政策：https://zhangminton731-a11y.github.io/ai-health-intel/#policy
- 自动采集：https://github.com/zhangminton731-a11y/ai-health-intel/actions/runs/36372433384
- 发布：https://github.com/zhangminton731-a11y/ai-health-intel/actions/runs/36372458589

