"""AI+健康产业情报站 · W2 中文站点与中文日报构建器。

输入：output/daily_items.jsonl、output/source_health.json（SIH 管线产物）
输出：output/site/index.html（中文品牌页，覆盖 SIH 默认英文壳）、output/daily_briefing_cn.md（可复制进微信群）

设计约束：
- 翻译走 Google gtx 免费接口：URL 先剥离（吸收 AI Hot 误杀教训）、哈希缓存（幂等省配额）、
  连续 5 次失败熔断降级为英文原文——无网络/无代理也能完整出站。
- 展示口径诚实：当前 V1 仅实现"相关度"单维展示（完整五维评分见《筛选方案 V1》路线），
  页面不虚构"人工审核"属性，页脚明示机器状态与免责声明。
"""
from __future__ import annotations

import hashlib
import html
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

SOURCE_NAMES = {
    "medtech_dive_primary": ("MedTech Dive", "主信源"),
    "stat_news_feed": ("STAT News", "权威媒体"),
    "crunchbase_news_feed": ("Crunchbase News", "权威媒体"),
    "rock_health_feed": ("Rock Health", "行业信源"),
    "hn_ai_health_signals": ("Hacker News", "社区信号"),
}
TIER_CN = {"must_read": "必读", "skim": "速览", "collapsed": "浏览", "archive": "归档"}
TIER_ORDER = {"must_read": 0, "skim": 1, "collapsed": 2, "archive": 3}
STATUS_CN = {"complete": "运行正常", "complete_with_warning": "运行正常（有告警）",
             "degraded": "降级运行", "failed": "采集失败"}
CST = timezone(timedelta(hours=8))


# ---------- 翻译（缓存 + 熔断 + URL 剥离） ----------

def load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")


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
        if re.fullmatch(r"[\u4e00-\u9fff\s\d\W]{2,}", clean) and not re.search(r"[A-Za-z]{3,}", clean):
            return clean  # 已是中文
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
            print("⚠️ 翻译连续失败 5 次，熔断开启，其余条目降级英文原文")
        return None


# ---------- 数据装载 ----------

def load_items() -> list[dict]:
    items = []
    for line in (OUTPUT / "daily_items.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def load_health() -> dict:
    try:
        return json.loads((OUTPUT / "source_health.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------- HTML ----------

CSS = """
:root{--paper:#f7f3e8;--card:#fffdf8;--ink:#18201c;--muted:#687069;--moss:#425d4a;
--signal:#d55a2a;--gold:#b48a3c;--line:rgba(24,32,28,.14)}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:20px 16px 48px}
header h1{font-size:26px;margin:8px 0 2px;color:var(--moss);letter-spacing:.5px}
.tagline{color:var(--muted);margin:0 0 10px;font-size:14px}
.meta{display:flex;flex-wrap:wrap;gap:8px;font-size:13px;color:var(--muted);align-items:center}
.badge{display:inline-block;padding:2px 10px;border-radius:99px;background:var(--moss);color:#fff;font-size:12px}
.badge.warn{background:var(--gold)}.badge.fail{background:var(--signal)}
.spotlight{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--signal);
border-radius:10px;padding:16px 18px;margin:18px 0}
.spotlight .label{color:var(--signal);font-weight:700;font-size:13px;letter-spacing:2px}
h2{font-size:15px;color:var(--moss);border-bottom:1px solid var(--line);padding-bottom:6px;margin:26px 0 12px;letter-spacing:1px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px 16px;margin:10px 0}
.card .headline a{color:var(--ink);font-weight:600;text-decoration:none;font-size:16px}
.card .headline a:hover{color:var(--moss)}
.orig{color:var(--muted);font-size:12px;margin-top:2px;word-break:break-word}
.cmeta{display:flex;flex-wrap:wrap;gap:6px 10px;font-size:12px;color:var(--muted);margin:6px 0 4px;align-items:center}
.src{color:var(--moss);font-weight:600}
.pill{border:1px solid var(--line);border-radius:99px;padding:0 8px;font-size:11px}
.pill.must_read{color:#fff;background:var(--signal);border-color:var(--signal)}
.pill.rel{color:var(--moss);font-weight:700}
.summary{margin:6px 0 0;font-size:14px;color:#2d352f}
ul.health{list-style:none;padding:0;margin:6px 0;font-size:13px;color:var(--muted)}
ul.health li::before{content:"●";margin-right:8px;color:var(--moss);font-size:10px}
ul.health li.down::before{color:var(--signal)}
.disclaimer{font-size:12px;color:var(--muted);border-top:1px dashed var(--line);padding-top:12px;margin-top:18px}
a{color:var(--moss)}
@media(max-width:560px){.wrap{padding:14px 10px 40px}header h1{font-size:21px}.card{padding:11px 12px}}
""".strip()


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def card_html(it: dict, tr: Translator, show_orig: bool = True) -> str:
    title_en = it.get("title", "")
    title_zh = tr.zh(title_en)
    summary = re.sub(r"<[^>]+>", " ", it.get("summary", "") or "")
    summary = re.sub(r"\s{2,}", " ", summary).strip()
    summary_zh = tr.zh(summary[:600])
    src_id = it.get("source_id", "")
    src_name, _ = SOURCE_NAMES.get(src_id, (src_id, ""))
    tier = it.get("reading_tier", "archive")
    rel = int(round((it.get("topic_relevance") or 0) * 100))
    head = title_zh or title_en
    orig = f'<div class="orig">{esc(title_en)}</div>' if (show_orig and title_zh and title_zh != title_en) else ""
    pill = f'<span class="pill {esc(tier)}">{TIER_CN.get(tier, tier)}</span>' if tier != "archive" else ""
    return f"""<article class="card">
  <div class="headline"><a href="{esc(it.get('url',''))}" target="_blank" rel="noopener">{esc(head)}</a></div>
  {orig}
  <div class="cmeta"><span class="src">{esc(src_name)}</span>{pill}
    <span class="pill rel">相关度 {rel}</span><span>{esc(it.get('published_at',''))}</span></div>
  <p class="summary">{esc(summary_zh or summary)}</p>
</article>"""


def build() -> None:
    items = load_items()
    health = load_health()
    tr = Translator()
    as_of = health.get("as_of", datetime.now(CST).strftime("%Y-%m-%d"))
    status = health.get("daily_status", "unknown")
    n_src = health.get("source_count", len(SOURCE_NAMES))

    tier_order = lambda it: (TIER_ORDER.get(it.get("reading_tier"), 9), -(it.get("topic_relevance") or 0))
    items.sort(key=tier_order)
    fresh = [it for it in items if it.get("freshness_gate") == "fresh" and it.get("reading_tier") != "archive"]
    top10 = sorted(fresh, key=lambda it: -(it.get("topic_relevance") or 0))[:10]
    spot = top10[0] if top10 else None

    by_tier: dict[str, list[dict]] = {}
    for it in items:
        by_tier.setdefault(it.get("reading_tier", "archive"), []).append(it)

    badge_cls = "badge" if status in ("complete", "complete_with_warning") else "badge warn"
    if status == "failed":
        badge_cls = "badge fail"

    parts = [f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI+健康产业情报站 · {esc(as_of)}</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>AI + 健康产业情报站</h1>
<p class="tagline">为 AI+健康赛道的创业者筛选的每日产业情报 · 全球信源 · 中文速读</p>
<div class="meta"><span class="{badge_cls}">{STATUS_CN.get(status, status)}</span>
<span>{n_src} 个信源</span><span>{len(items)} 条</span><span>{esc(as_of)}</span></div></header>"""]

    if spot:
        title_en = spot.get("title", "")
        title_zh = tr.zh(title_en) or title_en
        summary = re.sub(r"<[^>]+>", " ", spot.get("summary", "") or "")
        summary = re.sub(r"\s{2,}", " ", summary).strip()
        summary_zh = tr.zh(summary[:600]) or summary
        src_name, _ = SOURCE_NAMES.get(spot.get("source_id", ""), ("", ""))
        rel = int(round((spot.get("topic_relevance") or 0) * 100))
        parts.append(f"""<section class="spotlight"><div class="label">今日精选 · 为什么值得看</div>
<div class="headline" style="font-size:18px;margin:8px 0 4px"><a href="{esc(spot.get('url',''))}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none">{esc(title_zh)}</a></div>
<div class="orig">{esc(title_en)}</div>
<div class="cmeta"><span class="src">{esc(src_name)}</span><span class="pill rel">相关度 {rel}</span><span>{esc(spot.get('published_at',''))}</span></div>
<p class="summary">{esc(summary_zh)}</p></section>""")

    parts.append('<section><h2>今日 TOP 10</h2>')
    parts.extend(card_html(it, tr) for it in top10[1:11] if len(top10) > 1)
    if len(top10) <= 1:
        parts.append(card_html(it, tr) for it in top10)
    parts.append("</section>")

    for tier in ("must_read", "skim", "collapsed"):
        group = [it for it in by_tier.get(tier, []) if it not in top10]
        if group:
            parts.append(f'<section><h2>{TIER_CN[tier]}（{len(group)}）</h2>')
            parts.extend(card_html(it, tr) for it in group)
            parts.append("</section>")

    arch = by_tier.get("archive", [])
    if arch:
        parts.append(f'<section><h2>归档（{len(arch)}）</h2><ul class="health">')
        for it in arch:
            parts.append(f'<li><a href="{esc(it.get("url",""))}" target="_blank" rel="noopener">{esc(tr.zh(it.get("title","")) or it.get("title",""))}</a> · {esc(it.get("published_at",""))}</li>')
        parts.append("</ul></section>")

    src_lines = []
    for s in health.get("sources", []):
        sid = s.get("source_id", "")
        name, role = SOURCE_NAMES.get(sid, (sid, ""))
        ok = s.get("status") in ("ok", "ok_no_updates")
        cls = "" if ok else "down"
        src_lines.append(f'<li class="{cls}">{esc(name)}（{esc(role)}）· {esc(s.get("status",""))} · {s.get("item_count",0)} 条</li>')
    parts.append(f"""<footer><h2>来源健康</h2><ul class="health">{''.join(src_lines)}</ul>
<p class="disclaimer">本页由 AI 辅助整理（机器翻译 + 规则评分），内容<strong>未经人工审核</strong>；
不构成任何医疗建议或投资建议，请以各信源原文为准。企业行为描述以官方信源表述为准。
引擎 <a href="https://github.com/mengsj08/June_Public" target="_blank" rel="noopener">June SIH</a>（MIT）· 形态参考
<a href="https://github.com/laolaoshiren/ai-hot" target="_blank" rel="noopener">AI Hot</a>（MIT）·
<a href="https://github.com/zhangminton731-a11y/ai-health-intel" target="_blank" rel="noopener">GitHub 仓库</a></p>
</footer></div></body></html>""")

    site_dir = OUTPUT / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text("\n".join(parts), encoding="utf-8")
    print(f"✅ 中文站点已生成: site/index.html（翻译 {tr.translated} 条，熔断={'开' if tr.circuit_open else '关'}）")
    save_cache(tr.cache)

    # 中文日报（可复制进微信群）
    lines = [f"# AI+健康情报日报 · {as_of}", "",
             f"> 信源 {n_src} · 条目 {len(items)} · 状态 {STATUS_CN.get(status, status)}", ""]
    if spot:
        s_title = tr.zh(spot.get("title", "")) or spot.get("title", "")
        lines += [f"**今日精选：{s_title}**", f"链接：{spot.get('url','')}", ""]
    lines.append("**今日 TOP 10**")
    for i, it in enumerate(top10, 1):
        t = tr.zh(it.get("title", "")) or it.get("title", "")
        lines.append(f"{i}. {t}\n   {it.get('url','')}")
    lines += ["", "（机器翻译与评分，未经人工审核；不构成医疗/投资建议）"]
    (OUTPUT / "daily_briefing_cn.md").write_text("\n".join(lines), encoding="utf-8")
    print("✅ 中文日报已生成: daily_briefing_cn.md")


if __name__ == "__main__":
    build()
