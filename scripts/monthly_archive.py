"""Recover immutable monthly source records; publish explicitly retrospective digests."""
from __future__ import annotations
import argparse
import calendar
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine/src'))
from sih_ref.core import score_item
from daily_digest import build_issues, issue_text


def month_bounds(month):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise ValueError('Expected YYYY-MM')
    year, number = map(int, month.split('-'))
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


def merge_records(rows, month):
    first, last = month_bounds(month)
    unique = {}
    for row in rows:
        try:
            published = date.fromisoformat(row.get('published_at', ''))
        except (TypeError, ValueError):
            continue
        if not first <= published <= last or not row.get('url') or not row.get('item_id'):
            continue
        previous = unique.get(row['url'])
        if previous is None or len(row.get('summary') or '') > len(previous.get('summary') or ''):
            unique[row['url']] = row
    return sorted(unique.values(), key=lambda row: (row['published_at'], row['item_id']), reverse=True)


def select_records(records, profile):
    # Evaluate historical eligibility on the ORIGINAL date, without rewriting that date.
    scored = [score_item(row, profile, date.fromisoformat(row['published_at'])) for row in records]
    return [row for row in scored if row['reading_tier'] != 'archive' and (row.get('summary') or '').strip()]


def recover_month(repo, month):
    commits = subprocess.check_output(['git', 'log', '--format=%H', '--', 'output/daily_items.jsonl'], cwd=repo, text=True).splitlines()
    rows = []
    for sha in commits:
        blob = subprocess.check_output(['git', 'show', sha + ':output/daily_items.jsonl'], cwd=repo).decode('utf-8')
        rows.extend({**json.loads(line), 'archive_snapshot': sha} for line in blob.splitlines() if line.strip())
    current = repo / 'output/daily_items.jsonl'
    if current.exists():
        health = json.loads((repo / 'output/source_health.json').read_text(encoding='utf-8'))
        rows.extend({**json.loads(line), 'archive_batch': health['generated_at']}
                    for line in current.read_text(encoding='utf-8').splitlines() if line.strip())
    return {'schema_version': '1.0', 'month': month, 'kind': 'retrospective',
            'recovered_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'snapshot_count': len(commits), 'scope': '本仓库可恢复的采集快照；不代表全网完整收录。',
            'records': merge_records(rows, month)}


def export_archives(output, profile, translator, build_data):
    target = output / 'site/api/v1/archive'
    target.mkdir(parents=True, exist_ok=True)
    catalog = []
    for path in sorted((output / 'archives').glob('????-??.json'), reverse=True):
        archive = json.loads(path.read_text(encoding='utf-8'))
        month = archive['month']
        _, last = month_bounds(month)
        records = merge_records(archive['records'], month)
        rows = build_data(select_records(records, profile), translator, last)
        for row in rows:
            row.update(historical=True, archiveMonth=month)
        by_id = {row['id']: row for row in rows}
        issues = build_issues(rows, last, max_age=31)
        for issue in issues:
            issue.update(date_basis='original_publication', kind='retrospective',
                         headline=by_id[issue['item_ids'][0]]['t'] or by_id[issue['item_ids'][0]]['te'])
        public = {'schema_version': '1.0', 'month': month, 'kind': 'retrospective',
                  'description': '按原文日期回溯整理，不代表当日实际出刊。',
                  'recovered_at': archive['recovered_at'], 'record_count': len(records),
                  'item_count': len(rows), 'items': rows, 'editions': issues}
        (target / (month + '.json')).write_text(json.dumps(public, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        raw_target = output / 'site/archive' / month
        raw_target.mkdir(parents=True, exist_ok=True)
        (raw_target / 'records.json').write_text(json.dumps(archive, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        texts = ['# 奇点医研 · '+month+' 历史日报合订本', '\n按原文日期回溯整理，不代表当日实际出刊。\n']
        texts += [issue_text(issue, by_id, issue['date']) for issue in reversed(issues)]
        (raw_target / 'daily.md').write_text('\n---\n\n'.join(texts), encoding='utf-8')
        catalog.append({'month': month, 'record_count': len(records), 'item_count': len(rows),
                        'record_dates': sorted({row['published_at'] for row in records}),
                        'editions': [{key: issue[key] for key in ('date', 'headline', 'minutes', 'kind')} | {'count': len(issue['item_ids'])} for issue in issues]})
    (target / 'index.json').write_text(json.dumps({'months': catalog}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return catalog


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', required=True)
    args = parser.parse_args()
    month_bounds(args.month)
    path = ROOT / 'output/archives' / (args.month + '.json')
    archive = recover_month(ROOT, args.month)
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        archive['records'] = merge_records(previous['records'] + archive['records'], args.month)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(archive, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{args.month}: {len(archive["records"])} unique records recovered')
