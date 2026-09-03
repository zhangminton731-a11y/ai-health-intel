# AI + 健康产业情报站（demo V1）

面向 **AI+健康赛道创业者** 的中文情报入口：持续采集全球公开信源，经可解释筛选产出每日情报流与日报。形态参考 AI Hot（数字生命卡兹克），数据处理内核复用 June_Public·SIH（均 MIT）。

> 状态：MVP W1 地基已跑通（采集 → 事实池 → 评分分层 → 日报 → 静态站，全链本地验证）
> 需求与决策档案见总控工作区；本仓库只承载可运行系统。

## 仓库结构

```
engine/        SIH 参考实现（MIT，June Public contributors）——采集/标准化/去重/评分/渲染内核
config/
  sources.json 信源配置（Atlas V1 组合：主 MedTech Dive + 辅 STAT/Crunchbase/Rock Health + HN 信号）
  profile.json 筛选方案 V1（AI+健康词表、负向降权、四层阅读队列阈值）
scripts/       质量门与辅助脚本
output/        运行产物（事实池 JSONL、日报、来源健康、自包含静态页 site/index.html）
  .state/      增量识别状态（item_id→fingerprint，保证幂等）
.github/workflows/
  aggregate.yml 每日定时采集（00:30 UTC ≈ 北京 08:30，可调）
  deploy.yml    GitHub Pages 发布（仅聚合成功后部署，失败隔离）
```

## 本地运行

```bash
# Python 3.10+，零第三方依赖
PYTHONPATH=engine/src python -m sih_ref.cli run \
  --config config/sources.json --profile config/profile.json \
  --output-dir output --live          # --live 才联网采集；不带则离线复现
```

三重安全开关互不隐含：`--live`（联网）/ `--llm`（模型分诊）/ `--publish`（外发 Sink）。V1 全部关闭后两者。

## 信源纪律

- 仅接入 Source Atlas 中 `verification=verified` 的信源；"待交叉验证"内容永不公开。
- 一主多辅：MedTech Dive 为主，STAT / Crunchbase News / Rock Health 为辅，HN Algolia 作早期信号观察位。
- 来源健康每次运行落盘 `output/source_health.json`（manifest + 四级日健康）。

## 复用与许可

见 [CREDITS.md](CREDITS.md)。上游 MIT 声明原样保留于 `engine/LICENSE`。
