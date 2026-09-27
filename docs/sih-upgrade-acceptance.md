# 2026-09-27 SIH 改版验收

## 真实采集

批次 `2026-09-27T01:09:54+00:00`（北京时间 09:09:54），启用信源 12/12 成功，共 157 条，日期在 10 天范围内的记录 112 条；再按健康场景和技术线索筛选后，当前推荐 **15 条**。这是本地手动验证批次，不能作为上午定时任务已准点执行的证明。

| 来源 ID | 返回条目 | 状态 | 入口 |
|---|---:|---|---|
| medtech_dive_primary | 10 | ok | https://www.medtechdive.com/feeds/news/ |
| stat_news_feed | 20 | ok | https://www.statnews.com/feed/ |
| crunchbase_news_feed | 10 | ok | https://news.crunchbase.com/feed/ |
| apple_newsroom | 20 | ok | https://www.apple.com/newsroom/rss-feed.rss |
| fitbit_google_blog | 10 | ok | https://blog.google/rss/ |
| hn_ai_health_signals | 4 | ok | Hacker News API |
| medcity_news | 25 | ok | https://medcitynews.com/feed/ |
| npj_digital_medicine | 8 | ok | https://www.nature.com/npjdigitalmed.rss |
| nature_medicine | 8 | ok | https://www.nature.com/nm.rss |
| mit_health | 20 | ok | https://news.mit.edu/topic/mithealth-rss.xml |
| oura_blog | 12 | ok | https://ouraring.com/blog/feed/ |
| medical_device_network | 10 | ok | https://www.medicaldevice-network.com/feed/ |

恢复 Apple 正确的 Atom 地址；Nature 两个来源为 RSS 1.0/RDF，解析已补齐。Rock Health 仍关闭。Withings 返回内容过旧，Fierce 入口返回旧且不完整内容，MobiHealthNews/Healthcare IT News/Healthcare Dive 本机访问 403，未将这些计入有效信源。

## 已完成的验证

- 原有 Python 测试 27 项通过，覆盖原时效边界等行为。
- 新增 Python 测试 24 项通过：RSS/RDF/Atom、院端与消费健康相关性、排除泛酒店/金融/纯药物融资、完整质量门、接口漂移、时间、RSS、飞书签名与失败场景。
- Node / jsdom 交互测试 7 项通过：初始化、组合筛选、合作入口与微信复制、危险链接与文本转义、静态页过期、未知路由和剪贴板拒绝处理。
- 真实采集 → 中文构建 → 严格质量门通过，网页 / 日报 / JSON / RSS 推荐集合一致。构建翻译可用、未触发熔断。
- 模拟飞书响应验证成功/拒绝处理；**没有配置真实机器人，没有发送真实通知**。

## 待验收

1. 浏览器自动化连接不可用，jsdom 不能测布局。已写响应式 CSS 和触控尺寸，但 360/390/412px 截图、Android Chrome、微信内置浏览器仍需真实验收。
2. 飞书 Webhook 和可选签名密钥待负责人配置，再演练一次真实告警。
3. 09:00 是暂定目标。GitHub 调度与监控都可能延迟；历史核验观察到延迟，本次调整不等于已经验证连续准点。
4. 需要实际企业读者抽样标注相关性；少量规则测试不能证明总体相关率达到 80%。
5. Skill/API 为外部 Agent 读取静态快照，具体手机 Agent 的安装能力需在用户选择的客户端测试。
6. 商务联系方式采用用户最后指定的微信 13028564458，未公开另一个电话号码。未增加客户数据库或自动转化统计。

## 上线顺序

先审阅 PR 与本地预览，完成手机和飞书验收；合并后手动运行一次聚合并检查 Pages 的 JSON、RSS、Skill 下载及网页。随后开始连续 10 天内测，记录实际更新时间、内容质量、手机任务完成和有效企业联系，再决定公开引流。测试期尚未开始。

## 2026-09-27 两板块更新

最新定位：默认医学科研，产业前沿为第二入口；不展示团队自有项目。栏目采用外部论文、方法工具、政策及商业信息，增加研究环节筛选与日期信息流。

本次共 70 项测试通过（原有 Python 27、新增目录 Python 33、DOM 10），真实批次重建及质量门通过。生成页面 DOM 读取科研 3 条、产业 12 条，无运行错误。此轮没有重新采集、没有增加新的信源，政策栏目本批无匹配内容。浏览器连接仍不可用，移动布局视觉验收待完成。

Digital Oracle 的实际范围与参考边界见 [核验记录](digital-oracle-reference.md)。
