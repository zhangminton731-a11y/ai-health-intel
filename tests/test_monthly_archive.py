from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'engine/src'))
from monthly_archive import merge_records, select_records, month_bounds, export_archives
from sih_ref.core import normalize_item


class MonthlyArchiveTests(unittest.TestCase):
    def row(self, day='2026-09-01', summary='Hospital artificial intelligence clinical validation healthcare medical imaging'):
        return dict(reading_tier='skim', **normalize_item({'title': 'Clinical AI study', 'url': 'https://example.org/study',
                               'published_at': day, 'summary': summary}, {'id': 'journal', 'kind': 'rss'}))

    def test_bounds_and_richest_original_record(self):
        rows = [self.row(), self.row(summary='short'), self.row('2026-08-31'), self.row('2026-10-01')]
        selected = merge_records(rows, '2026-09')
        self.assertEqual([rows[0]], selected)
        self.assertEqual(date(2024, 2, 29), month_bounds('2024-02')[1])
        for invalid in ('../2026-09', '2026-13', '2026-00'):
            with self.assertRaises(ValueError): month_bounds(invalid)

    def test_historical_eligibility_does_not_relabel_original_date(self):
        profile = json.loads((ROOT/'config/profile.json').read_text(encoding='utf-8'))
        rows = select_records([self.row(), {**self.row(), 'title': 'Election', 'summary': 'political news', 'reading_tier': 'archive'}], profile)
        self.assertEqual(1, len(rows))
        self.assertEqual('2026-09-01', rows[0]['published_at'])
        self.assertNotIn('topic_relevance', rows[0])  # No new keyword scoring of historical records.

    def test_export_preserves_all_records_but_only_selects_eligible_content(self):
        profile = json.loads((ROOT/'config/profile.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp); (output/'archives').mkdir()
            archive = {'month': '2026-09', 'recovered_at': '2026-10-04', 'records': [self.row(), {**self.row('2026-09-02'), 'url': 'https://example.org/other', 'item_id': 'other', 'title': 'Election', 'summary': 'political news', 'reading_tier': 'archive'}]}
            (output/'archives/2026-09.json').write_text(json.dumps(archive), encoding='utf-8')
            def data(rows, _, as_of):
                return [dict(id=r['item_id'], date=r['published_at'], t=r['title'], te=r['title'], s=r['summary'], se='', u=r['url'], src='Journal', rel=100, freshness='fresh', tier='skim', categories={}) for r in rows]
            index = export_archives(output, profile, None, data)
            self.assertEqual(2, index[0]['record_count'])
            self.assertEqual(1, index[0]['item_count'])
            public = json.loads((output/'site/api/v1/archive/2026-09.json').read_text(encoding='utf-8'))
            self.assertEqual('retrospective', public['editions'][0]['kind'])
            self.assertEqual('2026-09-01', public['editions'][0]['date'])
            self.assertTrue((output/'site/archive/2026-09/daily.md').exists())


if __name__ == '__main__': unittest.main()
