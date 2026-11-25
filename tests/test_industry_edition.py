from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'engine/src')]
from industry_edition import overlay, public_issue, records, STAGES


class IndustryEditionTests(unittest.TestCase):
    def setUp(self):
        self.edition = json.loads((ROOT / 'config/editions/2026-11-25.json').read_text(encoding='utf-8'))

    def test_unverified_or_academic_item_cannot_enter_any_current_projection(self):
        baseline = [{'item_id': 'paper', 'reading_tier': 'must_read', 'freshness_gate': 'fresh'}]
        self.assertEqual(overlay(baseline, records(self.edition))[0]['reading_tier'], 'archive')
        for bad in ({'kind': 'research'}, {'source_type': '期刊论文'}, {'verification': 'pending'}):
            broken = deepcopy(self.edition)
            broken['events'][0].update(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                records(broken)

    def test_preorder_and_consultation_remain_distinct_from_sale_and_effect(self):
        for kind, before, after, display_before, display_after in (
            ('product', 'presale', 'on_sale', '预售', '实售'),
            ('policy', 'consultation', 'effective', '征求意见', '正式实施'),
        ):
            for code, expected in ((before, display_before), (after, display_after)):
                edition = deepcopy(self.edition)
                event = next(event for event in edition['events'] if event['kind'] == kind)
                edition['events'] = [dict(event, stage=code)]
                self.assertEqual(STAGES[kind][code], expected)
                self.assertIn(' · '+expected+'\n', public_issue(edition, records(edition))['text'])

    def test_duplicate_event_and_failed_scores_fail_closed(self):
        broken = deepcopy(self.edition)
        broken['events'].append(broken['events'][0])
        with self.assertRaisesRegex(ValueError, '重复'):
            records(broken)
        broken = deepcopy(self.edition)
        broken['events'][0]['reviews'][0]['axes'] = dict.fromkeys(broken['events'][0]['reviews'][0]['axes'], 0)
        with self.assertRaisesRegex(ValueError, '双评'):
            records(broken)

    def test_empty_edition_keeps_real_date(self):
        edition = dict(self.edition, events=[])
        value = public_issue(edition, records(edition))
        self.assertEqual(value['date'], edition['date'])
        self.assertEqual(value['item_ids'], [])
        self.assertIsNone(value['headline_id'])
        self.assertIn('暂无通过核验和评分', value['text'])

    def test_later_correction_keeps_original_issue_and_source_dates(self):
        updated = '2026-11-26T09:10:00+08:00'
        edition = dict(self.edition, updated_at=updated)
        with self.assertRaisesRegex(ValueError, '修订记录'):
            records(edition)
        edition['revisions'] = [{'date': '2026-11-26', 'note': '更正交易阶段'}]
        value = public_issue(edition, records(edition))
        self.assertEqual(value['date'], self.edition['date'])
        self.assertEqual(value['updated_at'], updated)
        self.assertEqual(value['revisions'], edition['revisions'])
        self.assertIn('2026-11-24', value['source_dates'])
