"""Backfill admitted sources without changing publication dates or editorial thresholds."""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine/src'))
from sih_ref.core import write_json_atomic
from sih_ref.editorial import evaluate
from monthly_archive import merge_records, verified_selection


def backfill(snapshot, start, end, root=ROOT):
    config = json.loads((root / 'config/sources.json').read_text(encoding='utf-8'))
    source_id = snapshot['source']['id']
    source = next(s for s in config['sources'] if s['id'] == source_id and s.get('enabled'))
    report = json.loads((root / source['admission_report']).read_text(encoding='utf-8'))
    admission = next(s for s in report['sources'] if s['source']['id'] == source_id)
    if admission['outcome'] != 'admitted':
        raise ValueError('Source has not passed admission')
    profile = json.loads((root / 'config/profile.json').read_text(encoding='utf-8'))
    items = [r for r in snapshot['items'] if start.isoformat() <= r.get('published_at', '') <= end.isoformat()
             and r.get('source_id') == source_id]
    rows, health = evaluate(items, {**profile, 'freshness_days': (end-start).days}, config['llm'],
                            root / 'output/.cache/editorial', end)
    selected = [r for r in rows if verified_selection(r) and r['editorial']['audiences'] == ['industry']]
    for month in sorted({r['published_at'][:7] for r in selected}):
        path = root / 'output/archives' / (month + '.json')
        archive = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
            'schema_version': '1.0', 'month': month, 'kind': 'retrospective', 'records': [],
            'recovered_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'scope': '按原始发布日期回溯，经双次模型评审入选；不代表当日实际出刊。'}
        archive['records'] = merge_records(archive['records'] + selected, month)
        write_json_atomic(path, archive)
    return {'source_id': source_id, 'start': start.isoformat(), 'end': end.isoformat(),
            'health': health, 'selected_ids': [r['item_id'] for r in selected], 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--start', type=date.fromisoformat, required=True)
    parser.add_argument('--end', type=date.fromisoformat, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.start > args.end or args.end > date.today():
        parser.error('Expected an elapsed date interval')
    result = backfill(json.loads(args.snapshot.read_text(encoding='utf-8')), args.start, args.end)
    write_json_atomic(args.report, result)
    print(result['source_id'], len(result['selected_ids']), 'industry articles selected')
