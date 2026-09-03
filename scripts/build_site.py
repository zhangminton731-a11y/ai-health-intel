"""AI+健康产业情报站 · W2.5 暗色信息流壳（AI Hot 风格 × Tailwind CDN）。

在 W2 中文站点基础上整体换壳：
- 技术底座：Tailwind CSS（GitHub 97.4k star，检索第一）Play CDN，零构建；暗色模式 class 切换
- 版式参考 AI Hot 信息流导航站：数据面板、今日精选、大编号 TOP10、分类浏览、关键词云
- 交互：客户端搜索 / 分类过滤 / 层级过滤 / 关键词过滤 / 暗亮切换（localStorage 记忆）
- 数据：全量条目内嵌 JSON 由前端渲染；翻译管线（缓存+熔断）与 W2 相同
- 合规：Tailwind/MIT、June SIH/MIT、AI Hot/MIT 均已在页脚与 CREDITS 署名
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

SOURCE_META = {
    "medtech_dive_primary": ("MedTech Dive", "主信源", "行业媒体"),
    "stat_news_feed": ("STAT News", "权威媒体", "行业媒体"),
    "crunchbase_news_feed": ("Crunchbase News", "权威媒体", "资本信息"),
    "rock_health_feed": ("Rock Health", "VC 官方博客", "资本信息"),
    "hn_ai_health_signals": ("Hacker News", "社区信号", "社区信号"),
}
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
    """gtx 免费翻译：URL 剥离 + 哈希缓存 + 连续 5 次失败熔断。"""

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
        name, role, cat = SOURCE_META.get(src_id, (src_id, "", "行业媒体"))
        out.append({
            "id": it.get("item_id", ""),
            "t": title_zh, "te": title_en if title_zh and title_zh != title_en else "",
            "s": summary_zh, "se": summary if summary_zh else "",
            "u": it.get("url", ""),
            "src": name, "role": role, "cat": cat,
            "tier": it.get("reading_tier", "archive"),
            "rel": int(round((it.get("topic_relevance") or 0) * 100)),
            "when": rel_time(it.get("published_at", "")),
        })
    return out


def keyword_stats(items: list[dict], profile: dict) -> list[dict]:
    text = " ".join((it.get("title", "") + " " + re.sub(r"<[^>]+>", " ", it.get("summary", ""))).lower() for it in items)
    stats = []
    for term in profile.get("topic_terms", {}):
        n = text.count(term.lower())
        if n >= 2:
            stats.append({"term": term, "n": n})
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
    tier_order = lambda it: (TIER_ORDER.get(it.get("reading_tier"), 9), -(it.get("topic_relevance") or 0))
    items.sort(key=tier_order)
    fresh = [it for it in items if it.get("freshness_gate") == "fresh" and it.get("reading_tier") != "archive"]
    top10 = sorted(fresh, key=lambda it: -(it.get("topic_relevance") or 0))[:10]
    by_id = {d["id"]: d for d in data}
    spot = by_id.get(top10[0].get("item_id")) if top10 else None
    top_ids = [it.get("item_id") for it in top10]
    kws = keyword_stats(items, profile)

    src_rows = []
    for s in health.get("sources", []):
        sid = s.get("source_id", "")
        name, role, _ = SOURCE_META.get(sid, (sid, "", ""))
        ok = s.get("status") in ("ok", "ok_no_updates")
        src_rows.append({"name": name, "role": role, "status": s.get("status", ""),
                         "n": s.get("item_count", 0), "ok": ok})

    payload = json.dumps({
        "asOf": as_of, "status": STATUS_CN.get(status, status), "statusRaw": status,
        "nSrc": n_src, "nItems": len(data), "spot": spot,
        "top": top_ids, "items": data, "kws": kws, "srcs": src_rows,
        "updated": datetime.now(CST).strftime("%m-%d %H:%M") + " CST",
    }, ensure_ascii=False).replace("</", "<\\/")

    page = TEMPLATE.replace("__PAYLOAD__", payload).replace("__DATE__", as_of)
    (OUTPUT / "site" / "index.html").write_text(page, encoding="utf-8")
    print(f"✅ 暗色信息流站点已生成: site/index.html（翻译 {tr.translated}，熔断={'开' if tr.circuit_open else '关'}）")
    save_cache(tr.cache)

    lines = [f"# AI+健康情报日报 · {as_of}", "",
             f"> 信源 {n_src} · 条目 {len(data)} · 状态 {STATUS_CN.get(status, status)}", ""]
    if spot:
        lines += [f"**今日精选：{spot['t'] or spot['te']}**", f"链接：{spot['u']}", ""]
    lines.append("**今日 TOP 10**")
    for i, iid in enumerate(top_ids, 1):
        d = by_id.get(iid, {})
        lines.append(f"{i}. {d.get('t') or d.get('te') or ''}\n   {d.get('u', '')}")
    lines += ["", "（机器翻译与评分，未经人工审核；不构成医疗/投资建议）"]
    (OUTPUT / "daily_briefing_cn.md").write_text("\n".join(lines), encoding="utf-8")
    print("✅ 中文日报已生成: daily_briefing_cn.md")


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN" class="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI+健康产业情报站 · __DATE__</title>
<meta name="description" content="为 AI+健康赛道创业者筛选的每日产业情报：全球信源、中文速读、可溯源。">
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config={darkMode:'class',theme:{extend:{colors:{signal:'#f97316',moss:'#10b981'}}}}</script>
<style>
html{scroll-behavior:smooth}
.card{transition:transform .15s ease,border-color .15s ease}
.card:hover{transform:translateY(-2px);border-color:#f97316aa}
.tnum{font:800 1.5rem/1 ui-monospace,SFMono-Regular,monospace}
::selection{background:#f9731655}
</style>
</head>
<body class="bg-paper text-slate-800 dark:bg-slate-950 dark:text-slate-200 antialiased">

<nav class="sticky top-0 z-40 backdrop-blur bg-white/80 dark:bg-slate-950/80 border-b border-slate-200 dark:border-slate-800">
  <div class="max-w-6xl mx-auto px-4 h-14 flex items-center gap-3">
    <a href="#" class="flex items-center gap-2 font-black text-lg tracking-wide">
      <span class="w-8 h-8 rounded-lg bg-signal text-white grid place-items-center text-sm">AI+</span>
      <span class="hidden sm:inline">AI+健康产业情报站</span><span class="sm:hidden">情报站</span>
    </a>
    <span class="hidden md:inline text-xs px-2 py-0.5 rounded-full border border-moss/40 text-moss" id="navStatus">—</span>
    <div class="flex-1"></div>
    <div class="relative w-36 sm:w-64">
      <input id="q" placeholder="搜索标题 / 摘要 / 信源…" autocomplete="off"
        class="w-full text-sm rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-3 py-1.5 outline-none focus:border-signal">
    </div>
    <button id="theme" title="切换明暗" class="w-9 h-9 rounded-lg border border-slate-200 dark:border-slate-700 grid place-items-center hover:border-signal">🌙</button>
  </div>
</nav>

<main class="max-w-6xl mx-auto px-4 py-6 space-y-8">

  <section class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 p-4">
      <div class="text-xs text-slate-500 dark:text-slate-400">信源</div>
      <div class="text-2xl font-black" id="statSrc">—</div></div>
    <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 p-4">
      <div class="text-xs text-slate-500 dark:text-slate-400">今日条目</div>
      <div class="text-2xl font-black" id="statItems">—</div></div>
    <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 p-4">
      <div class="text-xs text-slate-500 dark:text-slate-400">必读 + 速览</div>
      <div class="text-2xl font-black text-signal" id="statHot">—</div></div>
    <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 p-4">
      <div class="text-xs text-slate-500 dark:text-slate-400">最近更新</div>
      <div class="text-sm font-bold mt-1" id="statUpd">—</div></div>
  </section>

  <section id="spot" class="hidden rounded-2xl border border-signal/40 bg-gradient-to-br from-signal/10 to-transparent p-5 md:p-6">
    <div class="text-xs font-black tracking-[.2em] text-signal mb-2">今日精选 · 为什么值得看</div>
    <a id="spotT" target="_blank" rel="noopener" class="block text-xl md:text-2xl font-bold leading-snug hover:text-signal"></a>
    <div id="spotE" class="text-xs text-slate-500 dark:text-slate-400 mt-1 break-words"></div>
    <div class="flex flex-wrap items-center gap-2 text-xs mt-3" id="spotMeta"></div>
    <p id="spotS" class="text-sm mt-3 leading-relaxed text-slate-700 dark:text-slate-300"></p>
  </section>

  <section>
    <h2 class="text-lg font-black mb-3 flex items-center gap-2"><span class="w-1.5 h-5 bg-signal rounded"></span>今日热点 TOP 10</h2>
    <div id="topList" class="space-y-2"></div>
  </section>

  <section>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <h2 class="text-lg font-black flex items-center gap-2 mr-2"><span class="w-1.5 h-5 bg-moss rounded"></span>全部情报流</h2>
      <span id="catTabs" class="flex flex-wrap gap-1.5 text-xs"></span>
      <span class="flex-1"></span>
      <span id="tierTabs" class="flex flex-wrap gap-1.5 text-xs"></span>
    </div>
    <div id="kws" class="flex flex-wrap gap-1.5 text-xs mb-3 items-center"></div>
    <div id="feed" class="space-y-2"></div>
    <div id="empty" class="hidden text-center text-slate-500 py-10">没有匹配的条目——换个关键词试试</div>
  </section>

  <section>
    <h2 class="text-lg font-black mb-3 flex items-center gap-2"><span class="w-1.5 h-5 bg-moss rounded"></span>来源健康</h2>
    <div id="srcs" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2"></div>
  </section>

</main>

<footer class="border-t border-slate-200 dark:border-slate-800 mt-8">
  <div class="max-w-6xl mx-auto px-4 py-8 text-xs text-slate-500 dark:text-slate-400 space-y-2">
    <p>本页由 AI 辅助整理（机器翻译 + 规则评分），内容<strong>未经人工审核</strong>；不构成任何医疗或投资建议，请以各信源原文为准。</p>
    <p>引擎 <a class="text-moss" href="https://github.com/mengsj08/June_Public" target="_blank" rel="noopener">June SIH</a>（MIT）·
    版式参考 <a class="text-moss" href="https://github.com/laolaoshiren/ai-hot" target="_blank" rel="noopener">AI Hot</a>（MIT）·
    UI <a class="text-moss" href="https://github.com/tailwindlabs/tailwindcss" target="_blank" rel="noopener">Tailwind CSS</a>（MIT，97k★）·
    <a class="text-moss" href="https://github.com/zhangminton731-a11y/ai-health-intel" target="_blank" rel="noopener">GitHub 仓库</a></p>
  </div>
</footer>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const D = JSON.parse(document.getElementById('payload').textContent);
const tierCN = {must_read:'必读',skim:'速览',collapsed:'浏览',archive:'归档'};
const tierCls = {must_read:'bg-signal text-white',skim:'bg-moss/15 text-moss',collapsed:'bg-slate-500/15',archive:'bg-slate-500/10'};
let fCat='全部', fTier='全部', fKw='', fQ='';
const $ = s => document.querySelector(s);
const esc = s => (s??'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

$('#navStatus').textContent = D.status;
$('#statSrc').textContent = D.nSrc;
$('#statItems').textContent = D.nItems;
$('#statHot').textContent = D.items.filter(i=>['must_read','skim'].includes(i.tier)).length;
$('#statUpd').textContent = D.updated;

if (D.spot) {
  const s = D.spot;
  $('#spot').classList.remove('hidden');
  $('#spotT').textContent = s.t || s.te; $('#spotT').href = s.u;
  $('#spotE').textContent = s.te || '';
  $('#spotMeta').innerHTML = `<span class="px-2 py-0.5 rounded-full bg-moss/15 text-moss font-bold">${esc(s.src)}</span>`+
    `<span class="px-2 py-0.5 rounded-full bg-signal/15 text-signal font-bold">相关度 ${s.rel}</span><span>${esc(s.when)}</span>`;
  $('#spotS').textContent = s.s || s.se || '';
}

function card(it, rank) {
  const rankHtml = rank != null ? `<div class="tnum text-signal/90 w-9 shrink-0 pt-0.5">${String(rank).padStart(2,'0')}</div>` : '';
  const zh = it.t || it.te;
  return `<article class="card flex gap-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 p-3.5">
    ${rankHtml}
    <div class="min-w-0 flex-1">
      <a href="${esc(it.u)}" target="_blank" rel="noopener" class="font-semibold leading-snug hover:text-signal">${esc(zh)}</a>
      ${it.te ? `<div class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 break-words">${esc(it.te)}</div>` : ''}
      <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] mt-1.5 text-slate-500 dark:text-slate-400">
        <span class="font-bold text-moss">${esc(it.src)}</span>
        <span class="px-1.5 py-0.5 rounded-full ${tierCls[it.tier]}">${tierCN[it.tier]}</span>
        <span class="px-1.5 py-0.5 rounded-full border border-moss/40 text-moss font-bold">相关度 ${it.rel}</span>
        <span>${esc(it.when)}</span><span>· ${esc(it.cat)}</span>
      </div>
      ${(it.s||it.se) ? `<p class="text-[13px] mt-1.5 leading-relaxed text-slate-600 dark:text-slate-300">${esc(it.s||it.se)}</p>` : ''}
    </div></article>`;
}

const byId = Object.fromEntries(D.items.map(i=>[i.id,i]));
$('#topList').innerHTML = D.top.map((id,ix)=>{const it=byId[id];return it?card(it,ix+1):''}).join('');

const cats = ['全部',...new Set(D.items.map(i=>i.cat))];
$('#catTabs').innerHTML = cats.map(c=>`<button data-cat="${esc(c)}" class="tab px-2.5 py-1 rounded-full border ${c==='全部'?'bg-signal text-white border-signal':'border-slate-300 dark:border-slate-700'}">${esc(c)}</button>`).join('');
const tiers = ['全部','must_read','skim','collapsed','archive'];
$('#tierTabs').innerHTML = tiers.map(t=>`<button data-tier="${t}" class="ttab px-2.5 py-1 rounded-full border ${t==='全部'?'bg-moss text-white border-moss':'border-slate-300 dark:border-slate-700'}">${t==='全部'?'全部层级':tierCN[t]}</button>`).join('');
$('#kws').innerHTML = '<span class="text-slate-500">热词：</span>' + D.kws.map(k=>`<button data-kw="${esc(k.term)}" class="kw px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-signal">${esc(k.term)} <span class="text-slate-400">${k.n}</span></button>`).join('');

function apply(){
  const list = D.items.filter(i =>
    (fCat==='全部'||i.cat===fCat) && (fTier==='全部'||i.tier===fTier) &&
    (!fKw || ((i.t+i.te+i.s+i.se).toLowerCase().includes(fKw.toLowerCase()))) &&
    (!fQ || ((i.t+i.te+i.s+i.se+i.src).toLowerCase().includes(fQ.toLowerCase()))));
  $('#feed').innerHTML = list.map(i=>card(i,null)).join('');
  $('#empty').classList.toggle('hidden', list.length>0);
}
document.body.addEventListener('click', e=>{
  const t=e.target.closest('.tab,.ttab,.kw'); if(!t) return;
  if(t.classList.contains('tab')){fCat=t.dataset.cat;document.querySelectorAll('.tab').forEach(b=>b.className='tab px-2.5 py-1 rounded-full border '+(b===t?'bg-signal text-white border-signal':'border-slate-300 dark:border-slate-700'));}
  if(t.classList.contains('ttab')){fTier=t.dataset.tier;document.querySelectorAll('.ttab').forEach(b=>b.className='ttab px-2.5 py-1 rounded-full border '+(b===t?'bg-moss text-white border-moss':'border-slate-300 dark:border-slate-700'));}
  if(t.classList.contains('kw')){fKw=(fKw===t.dataset.kw?'':t.dataset.kw);document.querySelectorAll('.kw').forEach(b=>b.classList.toggle('border-signal', b.dataset.kw===fKw));}
  apply();
});
$('#q').addEventListener('input', e=>{fQ=e.target.value.trim(); apply();});

$('#srcs').innerHTML = D.srcs.map(s=>`
  <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 p-3 flex items-center gap-2 text-sm">
    <span class="w-2 h-2 rounded-full ${s.ok?'bg-moss':'bg-signal'}"></span>
    <span class="font-bold">${esc(s.name)}</span><span class="text-xs text-slate-500">${esc(s.role)}</span>
    <span class="flex-1"></span><span class="text-xs text-slate-500">${s.n} 条 · ${esc(s.status)}</span></div>`).join('');

const themeBtn=$('#theme');
function setTheme(dark){document.documentElement.classList.toggle('dark',dark);themeBtn.textContent=dark?'🌙':'☀️';localStorage.setItem('theme',dark?'dark':'light');}
setTheme((localStorage.getItem('theme')||'dark')==='dark');
themeBtn.onclick=()=>setTheme(!document.documentElement.classList.contains('dark'));

apply();
</script>
</body></html>
"""

if __name__ == "__main__":
    build()
