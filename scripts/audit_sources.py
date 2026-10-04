"""Audit consecutive recent source samples using the production editorial evaluator."""
from datetime import date, timedelta
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine/src'))
from sih_ref.core import write_json_atomic
from sih_ref.editorial import VERSION, evaluate


def latest_ten(items, as_of):
    """Select before scoring; never replace low-quality articles with older ones."""
    unique, problems = {}, []
    for row in items:
        if not row.get('url') or not row.get('title'):
            problems.append('missing_identity')
            continue
        try:
            published = date.fromisoformat(row.get('published_at', ''))
        except ValueError:
            problems.append('undated_article')
            continue
        if published > as_of:
            problems.append('future_article')
            continue
        if published < as_of - timedelta(days=90):
            continue
        key = row.get('doi') or row['url']
        if key not in unique or row['published_at'] > unique[key]['published_at']:
            unique[key] = row
    # Stable sort preserves publisher order for articles on the same day.
    return sorted(unique.values(), key=lambda r: r['published_at'], reverse=True)[:10], sorted(set(problems))


def decision(rows, sampling_problems=()):
    completed = sum((r.get('editorial') or {}).get('status') == 'scored' for r in rows)
    qualified = [r for r in rows if (r.get('editorial') or {}).get('status') == 'scored'
                 and r['editorial'].get('score', 0) >= 70 and len(r['editorial'].get('audiences', [])) == 1]
    if len(rows) != 10 or sampling_problems:
        outcome, reason = 'pending', '样本不足或采样日期异常，不能确认通过。'
    elif len(qualified) >= 3:
        outcome, reason = 'admitted', '最近连续 10 篇中，至少 3 篇经有效双次评审达到 70 分；未完成项不计入达标数。'
    elif completed != 10:
        outcome, reason = 'pending', '已确认达标不足 3 篇，且存在未完成或有分歧的评审，暂不纳入。'
    else:
        outcome, reason = 'excluded', '最近连续 10 篇中，达到 70 分且面向本站读者的文章不足 3 篇。'
    return {'outcome': outcome, 'reason': reason, 'sample_size': len(rows), 'completed': completed,
            'qualified': len(qualified), 'sampling_problems': list(sampling_problems)}


def audit(snapshot, profile, provider, cache_dir, as_of):
    sample, problems = latest_ten(snapshot['items'], as_of)
    # Source admission has a 90-day sample window; publication keeps its 10-day window.
    editorial = profile.get('editorial', {})
    tiers = {**editorial.get('source_tiers', {}), snapshot['source']['id']: snapshot.get('source_tier', 'T2')}
    rows, _ = evaluate(sample, {**profile, 'freshness_days': 90, 'editorial': {**editorial, 'source_tiers': tiers}}, provider, cache_dir, as_of)
    return {'source': snapshot['source'], 'collected_status': snapshot['status'],
            'collection_checks': snapshot.get('checks', []),
            'as_of': as_of.isoformat(), 'policy_version': VERSION,
            **decision(rows, problems), 'articles': [
                {k: r[k] for k in ('item_id', 'title', 'url', 'published_at', 'editorial')} for r in rows]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshots', type=Path, required=True, help='Directory of frozen source snapshots with source/status/items')
    parser.add_argument('--as-of', type=date.fromisoformat, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    profile = json.loads((ROOT / 'config/profile.json').read_text(encoding='utf-8'))
    provider = json.loads((ROOT / 'config/sources.json').read_text(encoding='utf-8'))['llm']
    reports = []
    for path in sorted(args.snapshots.glob('*.json')):
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        report = audit(snapshot, profile, provider, ROOT / 'output/.cache/editorial', args.as_of)
        reports.append(report)
        write_json_atomic(args.output, {'as_of': args.as_of.isoformat(), 'policy_version': VERSION,
            'criteria': {'sample': 10, 'minimum_qualified': 3, 'score': 70, 'lookback_days': 90}, 'sources': reports})
        print(report['source']['id'], report['outcome'], f"{report['qualified']}/{report['sample_size']}", flush=True)


if __name__ == '__main__':
    main()
