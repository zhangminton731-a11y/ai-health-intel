# Digital Oracle 参考评估

核验源码：komako-workshop/digital-oracle，commit `a63e4c19a2f3313d54914c44666febaf5ffb9d6f`，MIT。

## 实际范围

- README 与 SKILL 定位为基于市场数据的宏观趋势、资产和概率分析。
- `digital_oracle/providers/edgar.py` 提供 Form 4 内部人交易与 filings_search，并非现成的医疗融资并购事件库。申报搜索可以作为以后公告核查的候选能力，需验证具体文件和字段。
- `digital_oracle/concurrent.py` 汇总成功结果和错误；`snapshots.py` 记录请求/响应，支持离线重放。
- 本轮只读源码，没有运行第三方 Skill、金融预测或联网 provider，也没有证明其判断准确率。

## SIH 如何借鉴

1. 相关性：医院科研与产业问题分别筛选，泛金融信号不直接进入医疗推荐。
2. 时间：保留来源发布日期、采集时间，当前推荐维持统一时效门。
3. 证据：保留期刊/企业/媒体身份与原文。企业声明、媒体报道与监管确认不能相互替代；多个转载不等于多个独立证据。
4. 可核查：保留原始输入，分类与接口投影可离线测试；来源失败继续明确显示。

本轮实现内容分类和可核查的展示，未实现跨来源事件核验，不能在卡片上声称“多源证实”。融资与并购仍按来源报道呈现，不从证券价格推断某笔交易已发生；政策不自动生成“红线放松”的结论。

## 尚待补齐的覆盖

当前启用源主要为期刊、机构新闻、媒体和企业发布，国内科研政策/资助的机构原文覆盖不足。政策栏目可能为空或只有媒体解读，应显示实际来源；后续优先逐项验证官方入口，不能将媒体报道标为官方政策原文。

参考链接：
- https://github.com/komako-workshop/digital-oracle
- https://github.com/komako-workshop/digital-oracle/blob/a63e4c19a2f3313d54914c44666febaf5ffb9d6f/SKILL.md
- https://github.com/komako-workshop/digital-oracle/blob/a63e4c19a2f3313d54914c44666febaf5ffb9d6f/digital_oracle/providers/edgar.py

本项目未复制其代码，仅参考方法；若后续复用代码，需保留 MIT 许可证与版权声明。
