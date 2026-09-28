"""Build the mobile SIH site and its public feeds from one collection batch."""
from __future__ import annotations

import hashlib
import shutil
import html
from html.parser import HTMLParser
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "src"))
from sih_ref.core import freshness_gate, normalize_date
from export_feeds import export_feeds
from classify_content import classify_content
from daily_digest import build_issues, issue_text
from reader_context import reasons, update_history

OUTPUT = ROOT / "output"
CACHE_PATH = OUTPUT / ".state" / "translations.json"
SITE_NAME = "奇点医研"

SOURCE_META = {
    "ema_guidance": ("EMA 监管与程序指南", "官方机构", "官方机构", 3),
    "jmir": ("Journal of Medical Internet Research", "期刊论文", "期刊论文", 3),
    "jmir_ai": ("JMIR AI", "期刊论文", "期刊论文", 3),
    "nature_biomedical_engineering": ("Nature Biomedical Engineering", "期刊论文", "期刊论文", 3),
    "nih_funding": ("NIH 科研资助与通知", "官方机构", "官方机构", 3),
    "medtech_dive_primary": ("MedTech Dive", "专业媒体", "专业媒体", 2),
    "stat_news_feed": ("STAT News", "专业媒体", "专业媒体", 3),
    "crunchbase_news_feed": ("Crunchbase News", "专业媒体", "专业媒体", 3),
    "rock_health_feed": ("Rock Health", "企业发布", "企业发布", 2),
    "fitbit_google_blog": ("Google Blog", "企业发布", "企业发布", 2),
    "apple_newsroom": ("Apple Newsroom", "企业发布", "企业发布", 2),
    "medcity_news": ("MedCity News", "专业媒体", "专业媒体", 3),
    "npj_digital_medicine": ("npj Digital Medicine", "期刊论文", "期刊论文", 3),
    "nature_medicine": ("Nature Medicine", "期刊论文", "期刊论文", 3),
    "mit_health": ("MIT News · Health", "研究机构", "研究机构", 3),
    "oura_blog": ("Oura", "企业发布", "企业发布", 2),
    "medical_device_network": ("Medical Device Network", "专业媒体", "专业媒体", 2),
    "hn_ai_health_signals": ("Hacker News", "社区线索", "社区线索", 1),
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


def rel_time(pub: str, as_of: date) -> str:
    try:
        d = datetime.strptime(pub[:10], "%Y-%m-%d").date()
        delta = (as_of - d).days
        return {0: "今天", 1: "昨天"}.get(delta, f"{max(delta, 0)} 天前") if delta >= 0 else pub
    except Exception:
        return pub


TOPIC_TERMS = {
    "hospital": ("hospital", "clinical", "patient", "imaging", "diagnos", "surgical", "医疗", "医院", "临床", "影像"),
    "consumer": ("wearable", "fitness", "sleep", "wellness", "smart ring", "smartwatch", "glucose", "oura", "fitbit", "消费", "可穿戴", "健康", "睡眠"),
    "research": ("study", "research", "trial", "evidence", "validation", "研究", "试验", "证据"),
    "business": ("funding", "raises", "partnership", "acquis", "market", "launch", "融资", "合作", "市场", "发布"),
    "regulation": ("fda", "clearance", "cleared", "regulat", "ce mark", "监管", "审批", "获批"),
}


def item_topics(title: str, summary: str, category: str) -> list[str]:
    text = (title + " " + summary).lower()
    topics = [key for key, terms in TOPIC_TERMS.items() if any(term in text for term in terms)]
    if category == "期刊论文" and "research" not in topics:
        topics.append("research")
    return topics


class SummaryText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def reader_summary(value: str) -> str:
    parser = SummaryText()
    parser.feed(html.unescape(html.unescape(value or '')))
    value = ' '.join(parser.parts)
    value = re.sub(r'\s+', ' ', value).strip()
    value = re.sub(r'\s*The post .+? appeared first on .+?\.?$', '', value, flags=re.I)
    # Structured abstracts often put findings well beyond the RSS opening.
    parts = re.split(r'\b(Background|Objectives?|Methods|Results|Conclusions?)\s*:', value, flags=re.I)
    sections = {parts[i].lower().rstrip('s'): parts[i+1].strip() for i in range(1, len(parts)-1, 2)}
    if sections.get('result') or sections.get('conclusion'):
        value = ' '.join(label + ': ' + sections[key] for key, label in
                         [('conclusion', 'Conclusions'), ('result', 'Results')]
                         if sections.get(key))
    if len(value) > 900:
        # Do not turn a cut-off sentence into a complete finding.
        excerpt = value[:900]
        boundary = max(excerpt.rfind('. '), excerpt.rfind('。'), excerpt.rfind('; '))
        value = excerpt[:boundary+1] if boundary > 150 else excerpt.rsplit(' ', 1)[0] + '…'
    return value


def build_data(items: list[dict], tr: Translator, as_of: date) -> list[dict]:
    out = []
    for it in items:
        title_en = it.get("title", "")
        title_zh = (tr.zh(title_en) or "") if it.get("reading_tier") != "archive" else ""
        original_summary = it.get('summary', '') or ''
        summary = reader_summary(original_summary)
        summary_zh = (tr.zh(summary) or '') if it.get('reading_tier') != 'archive' else ''
        if re.search(r'\bLLMs?\b', title_en + ' ' + summary):
            summary_zh = summary_zh.replace('法学硕士', '大语言模型')
        src_id = it.get("source_id", "")
        name, role, cat, trust = SOURCE_META.get(src_id, (src_id, "", "行业媒体", 1))
        out.append({
            "id": it.get("item_id", ""),
            "t": title_zh, "te": title_en,
            "s": summary_zh, "se": summary,
            "u": it.get("url", ""),
            "src": name, "role": role, "cat": cat, "trust": trust,
            "sourceType": cat, "topics": item_topics(title_en, original_summary, cat),
            **classify_content(title_en, original_summary, cat),
            "event": it.get("event_type", "seen"), "provenance": it.get("provenance") or {},
            "tier": it.get("reading_tier", "archive"),
            "freshness": it.get("freshness_gate", "undated"),
            "rel": round((it.get("topic_relevance") or 0) * 100, 1),
            "when": rel_time(it.get("published_at", ""), as_of), "date": it.get("published_at", ""),
        })
    for item in out:
        item["reasons"] = reasons(item)
    return out


def keyword_stats(items: list[dict], profile: dict) -> list[dict]:
    text = " ".join((it.get("title", "") + " " + re.sub(r"<[^>]+>", " ", it.get("summary", ""))).lower() for it in items)
    stats = [{"term": t, "n": text.count(t.lower())} for t in profile.get("topic_terms", {})]
    stats = [s for s in stats if s["n"] >= 2]
    stats.sort(key=lambda x: -x["n"])
    return stats[:14]


def build(*, as_of: date | None = None) -> None:
    # Recheck persisted labels at build time; collection dates are not build dates.
    build_date = as_of or datetime.now(CST).date()
    items = load_items()
    health = load_health()
    tr = Translator()
    profile = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))

    history_raw = update_history(OUTPUT / 'history_items.jsonl', items, profile, build_date)
    as_of = build_date.isoformat()
    status = health.get("daily_status", "unknown")
    n_src = health.get("source_count", len(SOURCE_META))
    items = [dict(it) for it in items]
    freshness_counts = dict.fromkeys(("fresh", "stale", "future", "undated"), 0)
    for it in items:
        gate = freshness_gate(it, build_date, int(profile["freshness_days"]))
        it["freshness_gate"] = gate
        freshness_counts[gate] += 1
        if gate != "fresh":
            it["reading_tier"] = "archive"
    # Sole current recommendation set: every current view derives from this list.
    current_items = [it for it in items if it["freshness_gate"] == "fresh"
                     and it.get("reading_tier", "archive") != "archive"]
    ranked_current = sorted(current_items, key=lambda it: -(it.get("topic_relevance") or 0))
    data = build_data(items, tr, build_date)
    current_ids = {it['item_id'] for it in current_items}
    history_data = build_data([it for it in history_raw if it['item_id'] not in current_ids], tr, build_date)
    for row in history_data:
        row['historical'] = True
    history_issues = build_issues(history_data, build_date, max_age=20)
    policy = json.loads((ROOT/'config/policy_timeline.json').read_text(encoding='utf-8'))
    by_id = {d["id"]: d for d in data}
    top10 = ranked_current[:10]
    top_ids = [it.get("item_id") for it in top10]
    hot30 = [by_id[it["item_id"]] for it in ranked_current[:30]]
    kws = keyword_stats(current_items, profile)
    print(f"Freshness check ({as_of}): {freshness_counts}; current={len(current_items)}")

    src_rows = []
    for s in health.get("sources", []):
        sid = s.get("source_id", "")
        name, role, _, _ = SOURCE_META.get(sid, (sid, "", "", 1))
        dates = [normalize_date(it.get("published_at")) for it in items if it.get("source_id") == sid]
        dates = [d for d in dates if d and d <= as_of]
        low_activity = bool(dates) and (build_date - date.fromisoformat(max(dates))).days > 14
        src_rows.append({"name": name, "role": role, "status": s.get("status", ""),
                         "activity": "低活跃" if low_activity else "",
                         "n": s.get("item_count", 0),
                         "ok": s.get("status") in ("ok", "ok_no_updates")})

    daily_issues = build_issues(data, build_date)
    daily_ids = daily_issues[0]['item_ids'] if daily_issues else []
    briefing = issue_text(daily_issues[0] if daily_issues else None, by_id, as_of)

    site_data = {
        "name": SITE_NAME, "asOf": as_of,
        "generatedAt": health.get("generated_at", ""),
        "briefing": briefing, "dailyIssues": daily_issues, "dailyIds": daily_ids,
        "historyItems": history_data, "historyIssues": history_issues, "policyTimeline": policy,
        "status": STATUS_CN.get(status, status), "statusRaw": status,
        "nSrc": n_src, "nItems": len(data), "nCurrent": len(current_items),
        "freshnessCounts": freshness_counts, "top": top_ids, "hot30": hot30,
        "items": data, "kws": kws, "srcs": src_rows,
        "updated": datetime.now(CST).strftime("%Y-%m-%d %H:%M") + " CST",
    }
    payload = json.dumps(site_data, ensure_ascii=False).replace("</", "<\\/")

    page = TEMPLATE.replace("__PAYLOAD__", payload).replace("__DATE__", as_of).replace("__SITE_NAME__", SITE_NAME)
    (OUTPUT / "site").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "site" / "index.html").write_text(page, encoding="utf-8")
    print(f"✅ AI Hot 式浅色站点已生成: site/index.html（翻译 {tr.translated}，熔断={'开' if tr.circuit_open else '关'}）")
    save_cache(tr.cache)

    (OUTPUT / "daily_briefing_cn.md").write_text(briefing, encoding="utf-8")
    print("✅ 中文日报已生成: daily_briefing_cn.md")
    assets = OUTPUT/'site/assets'; assets.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'assets/community-qr.png', assets/'community-qr.png')
    export_feeds(OUTPUT / "site", site_data, health, briefing, ROOT / "skills" / "sih-intel")


TEMPLATE = (ROOT / "templates" / "site.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    build()
