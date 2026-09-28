"""Reader-facing daily selections grouped by the original publication date."""
from datetime import date
import re

LABELS = {'policy': '政策动态', 'papers': '论文研究', 'methods': '方法与工具',
          'business': '融资与合作', 'regulation': '市场准入',
          'products': '新品与方案', 'technology': '技术进展', 'overview': '产业动态'}


def category(item: dict) -> str:
    categories = item.get('categories', {})
    research = categories.get('research', [])
    industry = categories.get('industry', [])
    for key in LABELS:
        if key in research or key in industry:
            return key
    return 'overview'


def build_issues(items: list[dict], as_of: date) -> list[dict]:
    groups = {}
    for item in items:
        try:
            age = (as_of - date.fromisoformat(item['date'])).days
        except (KeyError, ValueError, TypeError):
            continue
        if not 0 <= age <= 10 or item.get('freshness') != 'fresh' or item.get('tier') == 'archive':
            continue
        if not (item.get('s') or item.get('se') or '').strip():
            continue
        groups.setdefault(item['date'], []).append(item)
    issues = []
    for day, rows in sorted(groups.items(), reverse=True):
        # Keep multiple subjects visible; never invent a missing policy story.
        rows.sort(key=lambda i: (-i.get('rel', 0), i['id']))
        unique, seen = [], set()
        for row in rows:
            key = re.sub(r'\W+', '', (row.get('te') or row.get('t', '')).casefold())
            if key and key not in seen:
                seen.add(key)
                unique.append(row)
        selected, categories = [], set()
        for key in LABELS:
            candidate = next((row for row in unique if category(row) == key), None)
            if candidate:
                selected.append(candidate)
                categories.add(candidate['id'])
            if len(selected) == 5:
                break
        selected += [row for row in unique if row['id'] not in categories][:5-len(selected)]
        if selected:
            chars = sum(len(row.get('t') or row.get('te', '')) + len(row.get('s') or row.get('se', '')) for row in selected)
            issues.append({'date': day, 'item_ids': [row['id'] for row in selected],
                           'minutes': max(1, (chars + 399) // 400)})
    return issues


def issue_text(issue: dict | None, by_id: dict, as_of: str) -> str:
    if not issue:
        return f'奇点医研 · AI 医疗日报 · {as_of}\n\n今日暂无新条目，请稍后再来。\n'
    lines = [f'奇点医研 · AI 医疗日报 · {issue["date"]}',
             f'这一天的 {len(issue["item_ids"])} 件 AI 医疗大事', '']
    for number, iid in enumerate(issue['item_ids'], 1):
        row = by_id[iid]
        lines += [f'{number:02d} · {LABELS[category(row)]}', row.get('t') or row.get('te', ''),
                  row.get('s') or row.get('se') or '来源未提供摘要，请阅读原文。',
                  f'{row["src"]} · {row["date"]}', row['u'], '']
    return '\n'.join(lines)
