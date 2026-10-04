from datetime import date
from pathlib import Path
import sys
import unittest
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_sources import decision, latest_ten
from sih_ref.editorial import AXES, VERSION, WEIGHTS, combine


class AdmissionTests(unittest.TestCase):
    def test_configured_additions_have_recalculable_admission_receipts(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'config/sources.json').read_text(encoding='utf-8'))
        additions = [s for s in config['sources'] if s.get('enabled') and s.get('admission_report')]
        self.assertTrue(additions)
        for source in additions:
            report = json.loads((root / source['admission_report']).read_text(encoding='utf-8'))
            self.assertEqual(VERSION, report['policy_version'])
            audit = next(s for s in report['sources'] if s['source']['id'] == source['id'])
            self.assertEqual('admitted', decision(audit['articles'], audit.get('sampling_problems', []))['outcome'])
            for row in audit['articles']:
                judgment = row['editorial']
                if judgment['status'] not in ('scored', 'needs_review'): continue
                for review in judgment['reviews']:
                    self.assertEqual(review['total'], sum(review['axes'][a] * w for a, w in zip(AXES, WEIGHTS[review['kind']])))
                recalculated = combine(judgment['reviews'], judgment['source_tier'])
                self.assertEqual(judgment['score'], recalculated['score'])
                self.assertEqual(judgment['status'], recalculated['status'])

    def row(self, n, score=70, status='scored'):
        return {'url': f'https://journal.example/{n}', 'title': str(n), 'published_at': f'2026-09-{n:02}',
                'editorial': {'score': score, 'status': status, 'audiences': ['research']}}

    def test_latest_ten_not_best_ten_and_duplicate_urls_do_not_count(self):
        rows = [self.row(n, 98 if n < 5 else 40) for n in range(1, 16)]
        sample, problems = latest_ten(rows + [rows[-1]], date(2026, 10, 4))
        self.assertEqual([str(n) for n in range(15, 5, -1)], [r['title'] for r in sample])
        self.assertEqual([], problems)
        self.assertEqual('excluded', decision(sample)['outcome'])

    def test_exactly_three_qualify_and_tier_selection_does_not_change_admission(self):
        rows = [self.row(n, 70 if n <= 3 else 69) for n in range(1, 11)]
        self.assertEqual('admitted', decision(rows)['outcome'])
        rows[0]['editorial']['score'] = 69
        self.assertEqual('excluded', decision(rows)['outcome'])

    def test_short_failed_disputed_and_undated_samples_remain_pending(self):
        rows = [self.row(n) for n in range(1, 11)]
        self.assertEqual('pending', decision(rows[:9])['outcome'])
        for status in ('failed', 'needs_review', 'insufficient_material'):
            rows[0]['editorial']['status'] = status
            self.assertEqual('admitted', decision(rows)['outcome'])
            self.assertEqual(9, decision(rows)['qualified'])
            low_rows = [self.row(n, 40) for n in range(1, 10)] + [self.row(10, status=status)]
            self.assertEqual('pending', decision(low_rows)['outcome'])
        sample, problems = latest_ten(rows + [{**self.row(11), 'published_at': ''}], date(2026, 10, 4))
        self.assertIn('undated_article', problems)
        self.assertEqual('pending', decision(sample, problems)['outcome'])

    def test_stale_future_and_unrelated_articles_cannot_qualify(self):
        rows = [self.row(n) for n in range(1, 11)]
        sample, problems = latest_ten([{**rows[0], 'published_at': '2025-01-01'},
                                     {**rows[1], 'published_at': '2026-10-05'}], date(2026, 10, 4))
        self.assertEqual([], sample)
        self.assertIn('future_article', problems)
        for row in rows: row['editorial']['audiences'] = []
        self.assertEqual(0, decision(rows)['qualified'])
