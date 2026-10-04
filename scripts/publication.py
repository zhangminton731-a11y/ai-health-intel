"""One current set and explainable per-publication-date coverage."""
from collections import Counter
from datetime import timedelta


def current_items(items):
    return [i for i in items if i.get('freshness_gate') == 'fresh' and i.get('reading_tier', 'archive') != 'archive']


def coverage(items, as_of):
    days = []
    for age in range(11):
        day = (as_of-timedelta(days=age)).isoformat()
        rows = [i for i in items if i.get('published_at') == day]
        selected = current_items(rows)
        reasons = Counter(reason for i in rows if i not in selected for reason in i.get('selection_reasons', ['legacy_unclassified']))
        days.append({'date':day, 'collected':len(rows), 'selected':len(selected), 'excluded_reasons':dict(reasons)})
    return {'dates':days, 'selected':len(current_items(items)), 'collected':len(items)}
