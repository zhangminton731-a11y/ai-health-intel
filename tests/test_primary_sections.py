from datetime import date
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parents[1] / 'engine/src')]
from build_site import build_data


class Translator:
    def zh(self, value): return value


class PrimarySectionTests(unittest.TestCase):
    def test_model_primary_event_overrides_cross_audience_keywords(self):
        base = {'source_id': 'medtech_dive_primary', 'title': 'FDA approves clinical AI device after trial validation',
                'summary': 'A clinical study supported the market approval.', 'published_at': '2026-10-04',
                'reading_tier': 'skim', 'freshness_gate': 'fresh'}
        rows = []
        for section, kind in [('research', 'research'), ('industry', 'product')]:
            rows.append({**base, 'item_id': section, 'editorial': {'status': 'scored', 'score': 80,
                         'audiences': [section], 'reviews': [{'kind': kind}], 'reason': section + ' specific reason'}})
        research, industry = build_data(rows, Translator(), date(2026, 10, 4))
        self.assertEqual(['research'], research['sections'])
        self.assertEqual(['industry'], industry['sections'])
        self.assertEqual({'research'}, set(research['categories']))
        self.assertEqual({'industry'}, set(industry['categories']))
        self.assertEqual({'research': 'research specific reason'}, research['reasons'])
        self.assertEqual({'industry': 'industry specific reason'}, industry['reasons'])
        self.assertEqual([], industry['stages'])
