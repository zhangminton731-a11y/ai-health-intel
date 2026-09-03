"""AI+健康产业情报站 · W3 浅色桌面壳（照抄 AI Hot 版式：左侧分组侧边栏 + 表格式榜单）。

版式基准（用户提供的 AI Hot 排行榜截图）：
- 左侧固定侧边栏，分组导航（内容/数据/更多），细线图标，选中项圆角高亮
- 主区：眉题 + 特大标题 + 一句话说明 + 更新时间 + 右上"榜单来源与计算方法"按钮
- 表格式榜单行：大字排名 01/02（TOP3 强调色）+ 名称（中文粗 + 英文小）+ 列数据 +
  右侧大号情报分 + "信源可信度 ●●● 高"色点
- 主题三档：明 / 暗 / 跟随系统（侧边栏底部三档切换）
- 单页多视图：精选 / 全部情报 / 热点榜 / AI 日报 / 来源健康 / 关于（hash 路由）
- 数据与翻译管线不变（gtx 缓存 + 熔断）；站名 SITE_NAME 可配置
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
CACHE_PATH = OUTPUT / ".state" / "translations.json"
SITE_NAME = "健微知著"

SOURCE_META = {
    "medtech_dive_primary": ("MedTech Dive", "主信源", "行业媒体", 2),
    "stat_news_feed": ("STAT News", "权威媒体", "行业媒体", 3),
    "crunchbase_news_feed": ("Crunchbase News", "权威媒体", "资本信息", 3),
    "rock_health_feed": ("Rock Health", "VC 官方博客", "资本信息", 2),
    "hn_ai_health_signals": ("Hacker News", "社区信号", "社区信号", 1),
}
TRUST_CN = {3: "高", 2: "中", 1: "低"}
TIER_CN = {"must_read": "必读", "skim": "速览", "collapsed": "浏览", "archive": "归档"}
TIER_ORDER = {"must_read": 0, "skim": 1, "collapsed": 2, "archive": 3}
STATUS_CN = {"complete": "运行正常", "complete_with_warning": "正常·有告警",
             "degraded": "降级运行", "failed": "采集失败"}
CST = timezone(timedelta(hours=8))


def load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


class Translator:
    def __init__(self) -> None:
        self.cache = load_cache()
        self.streak = 0
        self.circuit_open = False
        self.translated = 0

    def _gtx(self, text: str) -> str | None:
        q = urllib.parse.quote(text[:3600])
        url = ("https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl=auto&tl=zh-CN&dt=t&q={q}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return "".join(seg[0] for seg in data[0] if seg and seg[0])

    def zh(self, text: str) -> str | None:
        text = (text or "").strip()
        if len(text) < 2:
            return None
        clean = re.sub(r"https?://[^\s\u4e00-\u9fff]*", "", text).strip()
        if len(clean) < 2:
            return None
        if not re.search(r"[A-Za-z]{3,}", clean):
            return clean
        key = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]
        if key in self.cache:
            return self.cache[key]
        if self.circuit_open:
            return None
        try:
            out = self._gtx(clean)
            if out:
                self.cache[key] = out
                self.translated += 1
                self.streak = 0
                return out
        except Exception:
            pass
        self.streak += 1
        if self.streak >= 5:
            self.circuit_open = True
            print("⚠️ 翻译连续失败 5 次，熔断降级英文")
        return None


def load_items() -> list[dict]:
    return [json.loads(ln) for ln in (OUTPUT / "daily_items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_health() -> dict:
    try:
        return json.loads((OUTPUT / "source_health.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def rel_time(pub: str) -> str:
    try:
        d = datetime.strptime(pub[:10], "%Y-%m-%d").date()
        delta = (datetime.now(CST).date() - d).days
        return {0: "今天", 1: "昨天"}.get(delta, f"{max(delta, 0)} 天前") if delta >= 0 else pub
    except Exception:
        return pub


def build_data(items: list[dict], tr: Translator) -> list[dict]:
    out = []
    for it in items:
        title_en = it.get("title", "")
        title_zh = tr.zh(title_en) or ""
        summary = re.sub(r"<[^>]+>", " ", it.get("summary", "") or "")
        summary = re.sub(r"\s{2,}", " ", summary).strip()
        summary_zh = tr.zh(summary[:600]) or ""
        src_id = it.get("source_id", "")
        name, role, cat, trust = SOURCE_META.get(src_id, (src_id, "", "行业媒体", 1))
        out.append({
            "id": it.get("item_id", ""),
            "t": title_zh, "te": title_en,
            "s": summary_zh, "se": summary,
            "u": it.get("url", ""),
            "src": name, "role": role, "cat": cat, "trust": trust,
            "tier": it.get("reading_tier", "archive"),
            "rel": round((it.get("topic_relevance") or 0) * 100, 1),
            "when": rel_time(it.get("published_at", "")), "date": it.get("published_at", ""),
        })
    return out


def keyword_stats(items: list[dict], profile: dict) -> list[dict]:
    text = " ".join((it.get("title", "") + " " + re.sub(r"<[^>]+>", " ", it.get("summary", ""))).lower() for it in items)
    stats = [{"term": t, "n": text.count(t.lower())} for t in profile.get("topic_terms", {})]
    stats = [s for s in stats if s["n"] >= 2]
    stats.sort(key=lambda x: -x["n"])
    return stats[:14]


def build() -> None:
    items = load_items()
    health = load_health()
    tr = Translator()
    profile = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))

    as_of = health.get("as_of", datetime.now(CST).strftime("%Y-%m-%d"))
    status = health.get("daily_status", "unknown")
    n_src = health.get("source_count", len(SOURCE_META))
    data = build_data(items, tr)
    fresh = [it for it in items if it.get("freshness_gate") == "fresh" and it.get("reading_tier") != "archive"]
    top10 = sorted(fresh, key=lambda it: -(it.get("topic_relevance") or 0))[:10]
    top_ids = [it.get("item_id") for it in top10]
    hot30 = sorted(data, key=lambda d: -d["rel"])[:30]
    kws = keyword_stats(items, profile)

    src_rows = []
    for s in health.get("sources", []):
        sid = s.get("source_id", "")
        name, role, _, _ = SOURCE_META.get(sid, (sid, "", "", 1))
        src_rows.append({"name": name, "role": role, "status": s.get("status", ""),
                         "n": s.get("item_count", 0),
                         "ok": s.get("status") in ("ok", "ok_no_updates")})

    payload = json.dumps({
        "name": SITE_NAME, "asOf": as_of,
        "status": STATUS_CN.get(status, status), "statusRaw": status,
        "nSrc": n_src, "nItems": len(data), "top": top_ids, "hot30": hot30,
        "items": data, "kws": kws, "srcs": src_rows,
        "updated": datetime.now(CST).strftime("%Y-%m-%d %H:%M") + " CST",
    }, ensure_ascii=False).replace("</", "<\\/")

    page = TEMPLATE.replace("__PAYLOAD__", payload).replace("__DATE__", as_of).replace("__SITE_NAME__", SITE_NAME)
    (OUTPUT / "site" / "index.html").write_text(page, encoding="utf-8")
    print(f"✅ AI Hot 式浅色站点已生成: site/index.html（翻译 {tr.translated}，熔断={'开' if tr.circuit_open else '关'}）")
    save_cache(tr.cache)

    by_id = {d["id"]: d for d in data}
    lines = [f"# AI+健康情报日报 · {as_of}", "",
             f"> 信源 {n_src} · 条目 {len(data)} · 状态 {STATUS_CN.get(status, status)}", ""]
    if top_ids:
        d = by_id[top_ids[0]]
        lines += [f"**今日精选：{d.get('t') or d.get('te')}**", f"链接：{d.get('u')}", ""]
    lines.append("**今日 TOP 10**")
    for i, iid in enumerate(top_ids, 1):
        d = by_id.get(iid, {})
        lines.append(f"{i}. {d.get('t') or d.get('te') or ''}\n   {d.get('u', '')}")
    lines += ["", "（机器翻译与评分，未经人工审核；不构成医疗/投资建议）"]
    (OUTPUT / "daily_briefing_cn.md").write_text("\n".join(lines), encoding="utf-8")
    print("✅ 中文日报已生成: daily_briefing_cn.md")


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__SITE_NAME__ · AI+健康产业情报 · __DATE__</title>
<meta name="description" content="为 AI+健康赛道创业者筛选的每日产业情报：全球信源、中文速读、可溯源。">
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config={darkMode:'class',theme:{extend:{colors:{signal:'#c2410c',moss:'#0f766e',ink:'#18181b'}}}}</script>
<style>
html{scroll-behavior:smooth}
.rank{font:700 1.35rem/1 Georgia,'Times New Roman',serif;color:#a1a1aa}
.rank.top{color:#c2410c}
.dot{width:7px;height:7px;border-radius:99px;display:inline-block;margin-right:2px}
.view{display:none}.view.active{display:block}
.navitem{display:flex;align-items:center;gap:.65rem;padding:.5rem .75rem;border-radius:.6rem;font-size:14px;color:#52525b}
.navitem:hover{background:#f4f4f5}
.dark .navitem:hover{background:#1f2937}
.navitem.on{background:#f4f4f5;color:#18181b;font-weight:700}
.dark .navitem.on{background:#1f2937;color:#f9fafb}
.navitem svg{width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.row-detail{display:none}.row.open .row-detail{display:block}
</style>
</head>
<body class="bg-white dark:bg-zinc-950 text-zinc-800 dark:text-zinc-200 antialiased">

<div class="flex min-h-screen">
  <aside class="hidden lg:flex flex-col w-60 shrink-0 border-r border-zinc-200 dark:border-zinc-800 px-3 py-5 sticky top-0 h-screen overflow-y-auto">
    <div class="px-2 mb-6">
      <div class="text-2xl font-black tracking-[.18em] text-ink dark:text-white" id="brand">__SITE_NAME__</div>
    </div>
    <div class="text-xs text-zinc-400 px-2 mb-1">内容</div>
    <nav class="space-y-0.5" id="nav">
      <a href="#jingxuan" class="navitem"><svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>精选</a>
      <a href="#feed" class="navitem"><svg viewBox="0 0 24 24"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>全部情报</a>
      <a href="#hot" class="navitem"><svg viewBox="0 0 24 24"><path d="M12 2c1 4-3 5-3 9a5 5 0 0 0 10 0c0-2-1-3.5-2-5-.5 2-2 2.5-2 2.5C16 5 14 3 12 2z"/></svg>热点榜</a>
      <a href="#daily" class="navitem"><svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>AI 日报</a>
    </nav>
    <div class="text-xs text-zinc-400 px-2 mt-6 mb-1">数据</div>
    <nav class="space-y-0.5">
      <a href="#health" class="navitem"><svg viewBox="0 0 24 24"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21.2l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>来源健康</a>
    </nav>
    <div class="text-xs text-zinc-400 px-2 mt-6 mb-1">更多</div>
    <nav class="space-y-0.5">
      <a href="#about" class="navitem"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>关于与方法</a>
      <a href="https://github.com/zhangminton731-a11y/ai-health-intel/commits/main" target="_blank" rel="noopener" class="navitem"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>更新日志</a>
      <a href="https://github.com/zhangminton731-a11y/ai-health-intel/issues" target="_blank" rel="noopener" class="navitem"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>反馈</a>
    </nav>
    <div class="flex-1"></div>
    <div class="px-1 pt-4">
      <div class="inline-flex rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <button data-theme="dark" class="tbtn px-3 py-1.5 text-sm" title="暗色">🌙</button>
        <button data-theme="system" class="tbtn px-3 py-1.5 text-sm" title="跟随系统">🖥</button>
        <button data-theme="light" class="tbtn px-3 py-1.5 text-sm" title="亮色">☀️</button>
      </div>
      <div class="text-[11px] text-zinc-400 mt-3 px-1" id="sideUpd"></div>
    </div>
  </aside>

  <div class="flex-1 min-w-0">
    <div class="lg:hidden sticky top-0 z-40 bg-white/90 dark:bg-zinc-950/90 backdrop-blur border-b border-zinc-200 dark:border-zinc-800 px-4 h-12 flex items-center gap-3 overflow-x-auto">
      <span class="font-black tracking-[.15em] whitespace-nowrap" id="brandM">__SITE_NAME__</span>
      <a href="#jingxuan" class="text-xs whitespace-nowrap text-zinc-500">精选</a>
      <a href="#feed" class="text-xs whitespace-nowrap text-zinc-500">全部</a>
      <a href="#hot" class="text-xs whitespace-nowrap text-zinc-500">热点榜</a>
      <a href="#daily" class="text-xs whitespace-nowrap text-zinc-500">日报</a>
      <a href="#about" class="text-xs whitespace-nowrap text-zinc-500">关于</a>
    </div>

    <main class="max-w-5xl mx-auto px-5 md:px-10 py-8 md:py-10">

      <section id="v-jingxuan" class="view">
        <div class="text-xs font-bold tracking-[.25em] text-moss mb-2">EDITOR'S PICK · 今日精选</div>
        <h1 class="text-3xl md:text-[2.6rem] font-black leading-tight text-ink dark:text-white mb-2">今日精选</h1>
        <p class="text-zinc-500 dark:text-zinc-400 mb-1">为什么值得看：从当日全部情报中，按相关度与信源可信度选出最值得创业者关注的一条。</p>
        <p class="text-xs text-zinc-400 mb-6">更新于 <span id="upd1">—</span></p>
        <div id="spotBox" class="mb-10"></div>
        <div class="flex items-end justify-between mb-3">
          <h2 class="text-xl font-black text-ink dark:text-white">今日热点 <span class="text-zinc-400 font-bold">TOP 10</span></h2>
          <a href="#hot" class="text-sm text-moss hover:underline">查看完整热点榜 →</a>
        </div>
        <div id="topRows" class="border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden divide-y divide-zinc-100 dark:divide-zinc-800"></div>
      </section>

      <section id="v-feed" class="view">
        <div class="text-xs font-bold tracking-[.25em] text-moss mb-2">ALL INTEL · 全部情报</div>
        <h1 class="text-3xl md:text-[2.6rem] font-black text-ink dark:text-white mb-2">全部情报流</h1>
        <p class="text-zinc-500 dark:text-zinc-400 mb-4">按相关度排序的全部当日条目，可按分类与层级过滤。</p>
        <div class="flex flex-wrap gap-2 mb-3 text-sm" id="feedCats"></div>
        <div class="flex flex-wrap gap-2 mb-4 text-sm" id="feedTiers"></div>
        <div id="feedRows" class="border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden divide-y divide-zinc-100 dark:divide-zinc-800"></div>
      </section>

      <section id="v-hot" class="view">
        <div class="text-xs font-bold tracking-[.25em] text-moss mb-2">TRENDING · 热点榜</div>
        <h1 class="text-3xl md:text-[2.6rem] font-black text-ink dark:text-white mb-2">AI+健康热点榜</h1>
        <p class="text-zinc-500 dark:text-zinc-400 mb-1">按情报相关度排序的 TOP 30，相关度由主题词命中与信源权重计算。</p>
        <p class="text-xs text-zinc-400 mb-6">更新于 <span id="upd2">—</span></p>
        <div id="kws" class="flex flex-wrap gap-1.5 text-xs mb-5 items-center"></div>
        <div id="hotRows" class="border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden divide-y divide-zinc-100 dark:divide-zinc-800"></div>
      </section>

      <section id="v-daily" class="view">
        <div class="text-xs font-bold tracking-[.25em] text-moss mb-2">DAILY BRIEF · AI 日报</div>
        <h1 class="text-3xl md:text-[2.6rem] font-black text-ink dark:text-white mb-2">每日情报日报</h1>
        <p class="text-zinc-500 dark:text-zinc-400 mb-1">精选与 TOP 10 摘编，可直接复制转发到微信群。</p>
        <p class="text-xs text-zinc-400 mb-4">更新于 <span id="upd3">—</span></p>
        <button id="copyBtn" class="mb-5 text-sm px-4 py-2 rounded-lg bg-signal text-white font-bold hover:opacity-90">📋 复制日报全文</button>
        <pre id="dailyText" class="whitespace-pre-wrap text-sm bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 leading-relaxed"></pre>
      </section>

      <section id="v-health" class="view">
        <div class="text-xs font-bold tracking-[.25em] text-moss mb-2">SOURCE HEALTH · 来源健康</div>
        <h1 class="text-3xl md:text-[2.6rem] font-black text-ink dark:text-white mb-2">来源健康</h1>
        <p class="text-zinc-500 dark:text-zinc-400 mb-6">每个信源的启用状态与最近一次采集结果。连续失败会自动告警并降级。</p>
        <div id="srcRows" class="space-y-2"></div>
      </section>

      <section id="v-about" class="view">
        <div class="text-xs font-bold tracking-[.25em] text-moss mb-2">ABOUT · 关于与方法</div>
        <h1 class="text-3xl md:text-[2.6rem] font-black text-ink dark:text-white mb-6">关于与计算方法</h1>
        <div class="space-y-5 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300 max-w-3xl">
          <p><strong class="text-zinc-800 dark:text-zinc-100">这是什么：</strong>面向 AI+健康赛道创业者的每日产业情报站。全球公开信源 → 自动采集 → 清洗去重 → 主题相关度评分 → 中文呈现。</p>
          <p><strong class="text-zinc-800 dark:text-zinc-100">相关度怎么算：</strong>主题词表命中（标题加权）× 信源权重 × 时效。评分体系与词表持续迭代，试运行期每周人工抽检校准。</p>
          <p><strong class="text-zinc-800 dark:text-zinc-100">信源可信度：</strong>四级制——官方确认 / 权威媒体 / 行业信源 / 待交叉验证；"待交叉验证"内容不会出现在本站。</p>
          <p><strong class="text-zinc-800 dark:text-zinc-100">诚实声明：</strong>内容由机器翻译与规则评分生成，<strong>未经人工审核</strong>；不构成任何医疗或投资建议，请以各信源原文为准。</p>
          <p><strong class="text-zinc-800 dark:text-zinc-100">技术：</strong>引擎复用 <a class="text-moss hover:underline" href="https://github.com/mengsj08/June_Public" target="_blank" rel="noopener">June SIH</a>（MIT）· 版式参考 <a class="text-moss hover:underline" href="https://github.com/laolaoshiren/ai-hot" target="_blank" rel="noopener">AI Hot</a>（MIT）· UI <a class="text-moss hover:underline" href="https://github.com/tailwindlabs/tailwindcss" target="_blank" rel="noopener">Tailwind CSS</a>（MIT）· 每日 08:30（北京时间）自动更新 · <a class="text-moss hover:underline" href="https://github.com/zhangminton731-a11y/ai-health-intel" target="_blank" rel="noopener">GitHub 仓库</a></p>
        </div>
      </section>

    </main>
  </div>
</div>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const D = JSON.parse(document.getElementById('payload').textContent);
const tierCN={must_read:'必读',skim:'速览',collapsed:'浏览',archive:'归档'};
const $=s=>document.querySelector(s);
const esc=s=>(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.title = D.name + ' · AI+健康产业情报 · ' + D.asOf;
$('#brand').textContent=D.name; $('#brandM').textContent=D.name;
$('#upd1').textContent=D.updated; $('#upd2').textContent=D.updated; $('#upd3').textContent=D.updated; $('#sideUpd').textContent='更新于 '+D.updated;

const byId=Object.fromEntries(D.items.map(i=>[i.id,i]));
function dots(t){const c=t>=3?'#0f766e':(t===2?'#d97706':'#dc2626');let h='';for(let i=0;i<3;i++)h+=`<span class="dot" style="background:${i<t?c:'#e4e4e7'}"></span>`;return h+`<span class="ml-1 text-[11px]">${{3:'高',2:'中',1:'低'}[t]||''}</span>`;}
function row(it,rank,showSub=true){
  const rcls=rank<=3?'rank top':'rank';
  return `<div class="row bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900 cursor-pointer" data-id="${esc(it.id)}">
  <div class="flex items-center gap-3 md:gap-4 px-4 md:px-5 py-4">
    <div class="${rcls} w-9 shrink-0 text-center">${String(rank).padStart(2,'0')}</div>
    <div class="min-w-0 flex-1">
      <div class="font-bold leading-snug truncate">${esc(it.t||it.te)}</div>
      ${showSub&&it.t&&it.te?`<div class="text-[11px] text-zinc-400 truncate mt-0.5">${esc(it.te)}</div>`:''}
      <div class="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-[11px] text-zinc-400 mt-1">
        <span class="font-semibold text-zinc-500 dark:text-zinc-400">${esc(it.src)}</span>
        <span>${esc(it.when)}</span><span>· ${esc(it.cat)}</span>
        <span class="px-1.5 rounded border border-zinc-200 dark:border-zinc-700">${tierCN[it.tier]||''}</span>
      </div>
    </div>
    <div class="text-right shrink-0 w-24">
      <div class="text-2xl font-black text-ink dark:text-white">${it.rel.toFixed(1)}</div>
      <div class="text-[10px] text-zinc-400 flex items-center justify-end">${dots(it.trust)}</div>
    </div>
  </div>
  <div class="row-detail px-4 md:px-5 pb-4 pl-16 text-sm text-zinc-600 dark:text-zinc-300">
    <p class="mb-2 leading-relaxed">${esc(it.s||it.se||'（无摘要）')}</p>
    ${it.s&&it.se?`<p class="mb-2 leading-relaxed text-xs text-zinc-400">${esc(it.se)}</p>`:''}
    <a class="text-moss font-bold hover:underline" href="${esc(it.u)}" target="_blank" rel="noopener">阅读原文 →</a>
  </div></div>`;
}
function bindRows(box){box.querySelectorAll('.row').forEach(r=>r.addEventListener('click',()=>r.classList.toggle('open')));}

if(D.top.length&&byId[D.top[0]]){
  const s=byId[D.top[0]];
  $('#spotBox').innerHTML=`<div class="rounded-2xl border border-moss/30 bg-teal-50/50 dark:bg-teal-950/20 p-6">
    <a href="${esc(s.u)}" target="_blank" rel="noopener" class="block text-lg md:text-xl font-bold leading-snug hover:text-moss">${esc(s.t||s.te)}</a>
    ${s.t&&s.te?`<div class="text-xs text-zinc-400 mt-1">${esc(s.te)}</div>`:''}
    <div class="flex flex-wrap items-center gap-2 text-xs mt-3 text-zinc-500">
      <span class="font-bold text-moss">${esc(s.src)}</span><span class="px-1.5 rounded border border-zinc-200 dark:border-zinc-700">${tierCN[s.tier]}</span>
      <span>相关度 ${s.rel.toFixed(1)}</span><span>${esc(s.when)}</span></div>
    <p class="text-sm mt-3 leading-relaxed">${esc(s.s||s.se||'')}</p>
    <a class="inline-block mt-3 text-sm font-bold text-moss hover:underline" href="${esc(s.u)}" target="_blank" rel="noopener">阅读原文 →</a></div>`;
}
$('#topRows').innerHTML=D.top.map((id,ix)=>row(byId[id],ix+1)).join('');
bindRows($('#topRows'));

let fCat='全部分类',fTier='全部层级';
const cats=['全部分类',...new Set(D.items.map(i=>i.cat))],tiers=['全部层级','must_read','skim','collapsed','archive'];
function renderFeed(){
  const list=D.items.filter(i=>(fCat==='全部分类'||i.cat===fCat)&&(fTier==='全部层级'||i.tier===fTier));
  $('#feedRows').innerHTML=list.length?list.map((it,ix)=>row(it,ix+1)).join(''):'<div class="p-8 text-center text-zinc-400">没有匹配的条目</div>';
  bindRows($('#feedRows'));
}
$('#feedCats').innerHTML=cats.map(c=>`<button data-c="${esc(c)}" class="px-3 py-1.5 rounded-lg border text-xs font-bold ${c===fCat?'bg-ink text-white border-ink dark:bg-white dark:text-ink dark:border-white':'border-zinc-200 dark:border-zinc-800 text-zinc-500'}">${esc(c)}</button>`).join('');
$('#feedTiers').innerHTML=tiers.map(t=>`<button data-t="${t}" class="px-3 py-1.5 rounded-lg border text-xs ${t===fTier?'bg-moss text-white border-moss':'border-zinc-200 dark:border-zinc-800 text-zinc-500'}">${t==='全部层级'?'全部层级':tierCN[t]}</button>`).join('');
$('#feedCats').onclick=e=>{const b=e.target.closest('button');if(!b)return;fCat=b.dataset.c;$('#feedCats').querySelectorAll('button').forEach(x=>x.className=x.className.replace('bg-ink text-white border-ink dark:bg-white dark:text-ink dark:border-white','border-zinc-200 dark:border-zinc-800 text-zinc-500').replace(/border-zinc-200 dark:border-zinc-800 text-zinc-500$/,'border-zinc-200 dark:border-zinc-800 text-zinc-500'));b.className='px-3 py-1.5 rounded-lg border text-xs font-bold bg-ink text-white border-ink dark:bg-white dark:text-ink dark:border-white';renderFeed();};
$('#feedTiers').onclick=e=>{const b=e.target.closest('button');if(!b)return;fTier=b.dataset.t;$('#feedTiers').querySelectorAll('button').forEach(x=>x.className='px-3 py-1.5 rounded-lg border text-xs border-zinc-200 dark:border-zinc-800 text-zinc-500');b.className='px-3 py-1.5 rounded-lg border text-xs bg-moss text-white border-moss';renderFeed();};
renderFeed();

$('#hotRows').innerHTML=D.hot30.map((it,ix)=>row(it,ix+1)).join('');
bindRows($('#hotRows'));
$('#kws').innerHTML='<span class="text-zinc-400 mr-1">热词：</span>'+D.kws.map(k=>`<span class="px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">${esc(k.term)} <b class="text-signal">${k.n}</b></span>`).join('');

$('#srcRows').innerHTML=D.srcs.map(s=>`
  <div class="flex items-center gap-3 border border-zinc-200 dark:border-zinc-800 rounded-xl px-5 py-4">
    <span class="w-2.5 h-2.5 rounded-full ${s.ok?'bg-teal-600':'bg-signal'}"></span>
    <span class="font-bold">${esc(s.name)}</span>
    <span class="text-xs text-zinc-400">${esc(s.role)}</span>
    <span class="flex-1"></span>
    <span class="text-xs text-zinc-500">${s.n} 条</span>
    <span class="text-xs px-2 py-0.5 rounded-full ${s.ok?'bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-400':'bg-orange-50 text-signal dark:bg-orange-950'}">${esc(s.status)}</span>
  </div>`).join('');

let text=`【AI+健康情报日报 · ${D.asOf}】\n`;
if(D.top.length){const s=byId[D.top[0]];text+=`今日精选：${s.t||s.te}\n${s.u}\n\n今日 TOP10：\n`;}
D.top.forEach((id,ix)=>{const it=byId[id];text+=`${ix+1}. ${it.t||it.te}\n   ${it.u}\n`;});
text+=`\n（机器翻译与评分，未经人工审核；不构成医疗/投资建议）`;
$('#dailyText').textContent=text;
$('#copyBtn').onclick=async()=>{try{await navigator.clipboard.writeText($('#dailyText').textContent);$('#copyBtn').textContent='✅ 已复制';setTimeout(()=>$('#copyBtn').textContent='📋 复制日报全文',2000);}catch(e){$('#copyBtn').textContent='请手动全选复制';}};

function show(v){
  document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
  const el=document.getElementById('v-'+v);if(el)el.classList.add('active');
  document.querySelectorAll('#nav .navitem').forEach(a=>a.classList.toggle('on',a.getAttribute('href')==='#'+v));
  window.scrollTo(0,0);
}
function route(){show((location.hash||'#jingxuan').slice(1));}
window.addEventListener('hashchange',route);route();

const tbtns=document.querySelectorAll('.tbtn');
function applyTheme(m){const dark=m==='dark'||(m==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',dark);document.body.classList.toggle('dark:bg-zinc-950',dark);tbtns.forEach(b=>b.classList.toggle('bg-zinc-200',b.dataset.theme===m));dark?b2():b3();function b2(){document.body.style.background='';}function b3(){}}
let mode=localStorage.getItem('theme')||'light';applyTheme(mode);
tbtns.forEach(b=>b.onclick=()=>{mode=b.dataset.theme;localStorage.setItem('theme',mode);applyTheme(mode);});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{if(mode==='system')applyTheme('system')});
</script>
</body></html>
"""

if __name__ == "__main__":
    build()
