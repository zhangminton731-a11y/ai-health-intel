# 统一时效门 · W3-r2 验收记录

关联 [Issue #1：首版反馈与下一轮迭代：定位、内容筛选及八项问题答复](https://github.com/zhangminton731-a11y/ai-health-intel/issues/1)，需求依据为 @mengsj08 最新交接回复及冻结任务卡。

- 最新 main 基线：`46df6790690dee3292dedcb9ab156d9535393ee2`，独立分支 `codex/w3-r2-unified-freshness-gate`。
- 本地验收日期：2026-09-11。状态：实现及本地验收完成，待 Draft PR 人工审查，未合并/部署。
- 实现顺序：先复现日期/视图错误 → 修复 core 日期与归档 → 构建时重检并建立唯一 current_items → 空态/低活跃 → 全量测试、批次回归与浏览器检查。
- 改动仅六个文件：core.py、build_site.py、test_reference_pipeline.py、本文件、README.md、CHANGELOG.md。

## 冻结口径

`freshness_days=10`。北京时间构建日为 Day 0，Day 0～10（含两端）为 fresh；Day 11 起 stale；任何晚于构建日的日期均 future；缺失/无法解析为 undated。非 fresh 的 reading_tier 一律 archive。

构建时使用 core.freshness_gate 重新检查持久化条目，不信任旧 freshness 标签或 source_health.as_of。事实 JSONL 不被构建脚本覆盖；仅渲染副本更新 freshness/reading_tier，保留原评分与身份字段。

唯一集合：`current_items = fresh AND reading_tier != archive`。TOP10、TOP30 从同一集合按原 topic_relevance 排序截取；机器首推为 TOP10 第一项；热词统计整个当前集合；网页和 Markdown 日报共用 TOP10。fresh 但已归档的低相关条目仍不推荐。无任何榜单补位逻辑。

## A. 边界与窗口 — 通过

| 项目 | 证据 |
|---|---|
| A1 Day 0/10 fresh | test_day_zero、test_day_ten；35 条 Day 10 条目构建测试验证 TOP10/30 上限、排序与热词 |
| A2 Day 11 不进入五入口 | test_day_eleven、test_all_views_exclude_noncurrent_and_preserve_archive；排除条目刻意带旧 fresh 标签和高分 |
| A3 历史仍保留 | 构建测试逐字比对输入 JSONL 不变，payload items 保留全部记录，非 fresh 渲染为 archive |

## B. 异常日期 — 通过

| 项目 | 证据 |
|---|---|
| B1 缺失 → undated + archive | test_missing_date_archived |
| B2 明天和更远未来 → future | test_tomorrow、test_far_future；future/undated 独占事实池时所有入口仍为空 |
| B3 非法/无效日历日期 → undated + archive | test_invalid_date_archived（nonsense、2026-02-30），不崩溃；构建检查日志和 HTML payload freshnessCounts 留痕 |

## C. 空结果与来源 — 通过

| 项目 | 证据 |
|---|---|
| C1 全过期不回填 | test_all_stale_never_backfilled；53 条历史批次以 2030-01-01 构建：事实 53，当前 0，TOP10/30/热词均空；网页首推、TOP10、热点榜实际显示“今日暂无新条目”，网页与 Markdown 日报显示当前有效 0、推荐产出 0、零产出 |
| C1 空事实池 | test_empty_pool，不崩溃，日报零产出 |
| C2 低活跃不等于失败 | test_low_activity_is_not_collection_failure：最近有效日期距构建日 14 天不标，15 天标“低活跃”；采集 status=ok、日健康 complete 保持不变 |

低活跃为来源页面的独立 activity 提示，不修改采集状态或状态文件。只依据事实池该来源最近的有效非未来日期；没有证据时不猜测活跃度。持续零返回且没有历史日期的来源需要后续持久化活跃度追踪，本轮不新增状态架构。

## D. 五视图一致性 — 通过

| 项目 | 证据 |
|---|---|
| D1 唯一集合 | scripts/build_site.py 的 current_items；所有当前入口派生自该集合，页面不另行过滤 |
| D2 热点无过期 | 混合日期测试 + 9-07 回归，TOP30 过期记录 10→0 |
| D3 日报一致 | 网页日报与 Markdown 日报共用 top_ids；本地浏览器核对当前批次首推及十条链接，与文件一致 |
| 旧标签重建 | test_build_date_overrides_old_collection_labels：9-07 fresh 标签在 9-18 重建后过期，页面日期为构建日 |

浏览器本地检查：main 的 9-10 留存事实池以 9-11 构建，52 条事实、52 fresh、22 当前有效，TOP10=10、TOP30=22；首推为 Lyte，九组热词，日报十条。浏览器分别检查首推、热点、日报及全过期空态。使用既有翻译缓存，缓存未命中按现有熔断逻辑降级英文，未调用新增翻译服务。未重新联网采集，以上不是线上验收。

## E. 幂等与兼容 — 通过

| 项目 | 证据 |
|---|---|
| E1 重跑不复活 | test_legacy_state_seen_does_not_revive_stale_item：event_type=seen，仍 archive，item_id/fingerprint/provenance 不变 |
| E2 旧 .state 兼容 | 直接读取 a479b0a 的五份 source .state，对原始 53 条重做 normalize_item/apply_incremental：全部 seen（10/20/10/10/3），无格式变更 |

## F. 全量与历史回归 — 通过

- main 实际含 11 项测试，基线全绿；Issue 中“17 项”指未入仓的本地补丁，无法声称运行了那份测试。
- 本轮新增 16 项测试，合计 **27 项全绿**，命令：`python -m unittest discover -s engine/tests -p 'test_*.py' -v`。
- 最初红灯：明天误判 fresh、缺失/异常日期错误为 skim；随后补足构建接口和筛选，转绿。
- 本地站点结构检查：`python scripts/quality_gate.py`，通过。

### 2026-09-07 批次

使用 `a479b0a` 的原始 `output/daily_items.jsonl`（53 条），构建日期固定 2026-09-07。保留原分数/层级，使用当前配置的 10 天窗口，不做重新评分或分数拟合。

| 指标 | 修改前 main 逻辑 | 修改后 |
|---|---:|---:|
| 事实池 | 53 | 53 |
| 日期 fresh / stale / future / undated | 43 / 10 / 0 / 0 | 43 / 10 / 0 / 0 |
| 当前有效 | 9 | 9 |
| TOP10 / 其中旧闻 | 9 / 0 | 9 / 0 |
| TOP30 / 其中旧闻 | 30 / 10 | 9 / 0 |
| 中文日报推荐 | 9 | 9 |
| 热词统计输入条目 | 53 | 9 |

热词同词表比较：main 全量统计为 funding 13、fda 6、launch 5、series c 3、ipo 3、athlete 2、tactical athlete 2、fitness 2、acquires 2、valuation 2；修复后为 fda 6、launch 3。归档条目不再参与热词。a479b0a 原页面使用更早词表，不把跨词表差异当作此次修复效果。

**过期恰好 10 条，无差异**；全部为 Rock Health，item_id 为下列链接加 `url:` 前缀，与 Issue R10–R19 一致：

| Issue 编号 | 发布日期 | 原记录 |
|---|---|---|
| R10 | 2021-04-01 | [Healthcare quality](https://rockhealth.com/how-to-advance-healthcare-quality-though-digital-health/) |
| R11 | 2021-04-13 | [Nuance/platform wars](https://rockhealth.com/the-next-nuance-to-the-platform-wars/) |
| R12 | 2021-04-23 | [Go-to-market Q&A](https://rockhealth.com/building-a-coherent-go-to-market-for-digital-health-solutions-a-qa-with-zs-associates-vijesh-unnikrishnan-and-dan-macleod/) |
| R13 | 2021-05-14 | [100 digital health CEOs](https://rockhealth.com/100-digital-health-ceos-on-navigating-growth-change-and-challenges/) |
| R14 | 2021-06-11 | [Spring member retreat](https://rockhealth.com/an-inside-look-at-enterprise-digital-innovation-highlights-from-the-rock-health-spring-2021-member-retreat/) |
| R15 | 2021-06-22 | [Pear SPAC](https://rockhealth.com/pear-going-public-via-spac-take-a-bite-out-of-that/) |
| R16 | 2021-05-24 | [Ro/Modern Fertility](https://rockhealth.com/ro-acquires-modern-fertility-segment-specific-ma-another-front-in-the-platform-wars/) |
| R17 | 2021-06-17 | [Zus investment](https://rockhealth.com/zus-health-investment/) |
| R18 | 2021-07-14 | [JOON investment](https://rockhealth.com/wellbeing-benefits-for-the-modern-workforce-our-investment-in-joon/) |
| R19 | 2021-08-26 | [Sales operations role](https://rockhealth.com/were-hiring-a-sales-operations-manager/) |

### 批次复现（仓库根目录，Python 3.10+，需含 a479b0a 历史）

将以下代码保存为临时 Python 文件并从仓库根目录运行；输出留在系统临时目录，不覆盖仓库事实池：

```python
import json, re, subprocess, sys, tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, "scripts")
import build_site as b
from sih_ref.core import normalize_item, apply_incremental

def old(path):
    return subprocess.check_output(["git", "show", f"a479b0a:{path}"]).decode("utf-8")

items = [json.loads(x) for x in old("output/daily_items.jsonl").splitlines()]
health = json.loads(old("output/source_health.json"))
assert len(items) == 53
excluded = [it for it in items if b.freshness_gate(it, date(2026, 9, 7), 10) == "stale"]
assert len(excluded) == 10
print([(it["item_id"], it["published_at"]) for it in excluded])
output = Path(tempfile.mkdtemp(prefix="freshness-0907-"))
(output / "daily_items.jsonl").write_text(old("output/daily_items.jsonl"), encoding="utf-8")
(output / "source_health.json").write_text(old("output/source_health.json"), encoding="utf-8")
with patch.object(b, "OUTPUT", output), patch.object(b, "save_cache"), patch.object(b.Translator, "_gtx", return_value=None):
    b.build(as_of=date(2026, 9, 7))
page = (output / "site/index.html").read_text(encoding="utf-8")
p = json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>', page, re.S).group(1))
assert p["nItems"] == 53 and p["nCurrent"] == 9
assert len(p["top"]) == len(p["hot30"]) == 9
assert not ({x["item_id"] for x in excluded} & {x["id"] for x in p["hot30"]})
for source in health["sources"]:
    sid = source["source_id"]
    raw = [json.loads(x) for x in old(f"output/sources/{sid}/items.raw.jsonl").splitlines()]
    norm = [normalize_item(x, {"id": sid, "kind": source["source_kind"]}) for x in raw]
    state = output / f"{sid}.json"
    state.write_text(old(f"output/.state/{sid}.json"), encoding="utf-8")
    assert all(x["event_type"] == "seen" for x in apply_incremental(norm, state, persist=False))
print(output)
```

## 未解决事项与人工合并条件

- 仅修复构建时效；静态页面停止重建后的老化及刷新保障另行处理。
- 相关度误收、通讯摘要错位、翻译质量、HN 摘要、来源替代等列为后续事项；本轮没有评分重构、五维评分、LLM、分数拟合、扩源、后台、订阅或 UI 大改。
- 53 条材料是 Codex provisional editorial review，可校准，非 June 逐条批准的训练金标准，也不作为独立泛化验证。
- [x] A–F 本地验证完成
- [x] PR 交付关联 Issue #1
- [ ] 人工审查 Draft PR 并决定是否合并
- [ ] 部署后人工抽查线上热点榜/日报（本轮不部署、不自动 Merge）
