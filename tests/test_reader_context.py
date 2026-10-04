from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'engine/src'))
from reader_context import reasons, update_history
from sih_ref.core import normalize_item


class ReaderContextTests(unittest.TestCase):
    def test_archive_keeps_original_dates_expires_and_deduplicates(self):
        profile=json.loads((ROOT/'config/profile.json').read_text(encoding='utf-8'))
        def row(key, day):
            return normalize_item({'title':'Hospital launches artificial intelligence for medical imaging workflow',
                'url':'https://example.org/'+key,'published_at':day},{'id':'test','kind':'rss'})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.jsonl'
            rows=[row('valid','2026-09-09'),row('stale','2026-09-01'),row('future','2026-09-29')]
            rows=[dict(r, reading_tier='skim') for r in rows]
            found=update_history(path,rows,profile,date(2026,9,28))
            self.assertEqual(['2026-09-09'],[r['published_at'] for r in found])
            self.assertEqual(found,update_history(path,rows[:1],profile,date(2026,9,28)))
            self.assertEqual([],update_history(path,[],profile,date(2026,10,1)))

    def test_reasons_address_the_audience_without_inventing_results(self):
        item={'te':'Systematic review of AI for sleep apnea','categories':{'research':['papers'],'industry':['products']}}
        result=reasons(item)
        self.assertIn('睡眠',result['research'])
        self.assertIn('偏倚',result['research'])
        self.assertIn('现有产品',result['industry'])
        self.assertNotIn('获批',result['research'])

    def test_policy_library_preserves_status_and_official_origins(self):
        data=json.loads((ROOT/'config/policy_timeline.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(data['items']),10)
        for row in data['items']:
            self.assertTrue(row['url'].startswith('https://'))
            self.assertTrue(row['meaning'] and row['boundary'])
            self.assertLessEqual(row['date'],'2026-09-28')
        lifecycle=next(i for i in data['items'] if i['id']=='us-lifecycle')
        self.assertIn('草案',lifecycle['kind'])
        self.assertGreaterEqual(sum(bool(i['pilot']) for i in data['items']),2)

if __name__=='__main__':unittest.main()
