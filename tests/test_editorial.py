import copy
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine/src'))
from sih_ref.core import score_item
from sih_ref.editorial import AXES, VERSION, combine, evaluate, material, validate_review, restore_receipts, retain_recent_sources


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.item = {'item_id': 'x', 'source_id': 'journal', 'title': 'A controlled clinical study',
                     'summary': 'A multicentre trial compared a new method with standard care. The study reports its outcomes and limitations.',
                     'published_at': '2026-10-04'}
        self.profile = {'editorial': {'enabled': True, 'source_tiers': {'journal': 'T1'}}, 'freshness_days': 10}
        self.provider = {'enabled': True, 'endpoint': 'https://example.org/v1', 'model': 'test-model', 'max_workers': 1}
        self.raw = {'kind': 'research', 'axes': dict.fromkeys(AXES, 8), 'audiences': ['research'],
                    'reason': '比较了新方法与标准诊疗路径，但仍需核对研究局限。',
                    'support': 'A multicentre trial compared a new method with standard care.'}
        self.review = {**validate_review(self.raw, material(self.item)), 'receipt': {'model': 'test-model'}}

    def test_keyword_stuffing_cannot_assign_a_production_score(self):
        p = {**self.profile, 'topic_terms': {'glucose': 9999}}
        row = score_item({**self.item, 'title': 'glucose ' * 100}, p, date(2026, 10, 4))
        self.assertEqual(0, row['topic_relevance'])
        self.assertEqual('archive', row['reading_tier'])
        self.assertEqual('pending', row['editorial']['status'])

    def test_backend_ignores_model_total_and_recalculates_weights(self):
        raw = {**self.raw, 'total': 100, 'axes': dict(zip(AXES, [5, 6, 7, 8, 9]))}
        self.assertEqual(65, validate_review(raw, material(self.item))['total'])

    def test_invalid_axes_are_rejected(self):
        for value in [11, -1, True, 5.5, '8', float('nan')]:
            raw = copy.deepcopy(self.raw)
            raw['axes']['evidence'] = value
            with self.assertRaises(ValueError): validate_review(raw, material(self.item))

    def test_invented_support_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_review({**self.raw, 'support': 'The study proved universal clinical efficacy.'}, material(self.item))

    def test_long_verbatim_support_is_trimmed_without_rejecting_valid_content(self):
        content = {'title': 'Clinical study', 'summary': 'Original clinical evidence. ' * 15}
        result = validate_review({**self.raw, 'support': content['summary']}, content)
        self.assertEqual(200, len(result['support']))
        self.assertIn(result['support'], content['summary'])

    def test_two_scores_average_floor_and_ceiling(self):
        result = combine([{**self.review, 'total': 99}, {**self.review, 'total': 100}], 'T1')
        self.assertEqual(98, result['score'])
        self.assertEqual(79, combine([{**self.review, 'total': 79}, self.review], 'T1')['score'])
        with self.assertRaises(ValueError): combine([self.review], 'T1')

    def test_source_threshold_and_out_of_scope(self):
        reviews = [{**self.review, 'total': 72}] * 2
        self.assertTrue(combine(reviews, 'T1')['selected'])
        self.assertFalse(combine(reviews, 'T2')['selected'])
        self.assertFalse(combine(reviews, 'EXCLUDE_MP')['selected'])
        self.assertFalse(combine([{**self.review, 'audiences': []}, self.review], 'T1')['selected'])

    def test_disagreement_cannot_enter_recommendations(self):
        result = combine([{**self.review, 'total': 50}, self.review], 'T1')
        self.assertEqual('needs_review', result['status'])
        self.assertFalse(result['selected'])

    def test_two_independent_requests_cache_and_content_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SIH_LLM_API_KEY': 'test-only'}), patch('sih_ref.editorial.request_review', return_value=self.review) as call:
            rows, _ = evaluate([self.item], self.profile, self.provider, Path(tmp), date(2026, 10, 4))
            self.assertEqual(2, call.call_count)
            self.assertEqual(.8, rows[0]['topic_relevance'])
            self.assertEqual('skim', rows[0]['reading_tier'])
            evaluate([self.item], self.profile, self.provider, Path(tmp), date(2026, 10, 4))
            self.assertEqual(2, call.call_count)
            evaluate([{**self.item, 'title': 'Changed result'}], self.profile, self.provider, Path(tmp), date(2026, 10, 4))
            self.assertEqual(4, call.call_count)

    def test_second_request_failure_does_not_publish_single_score(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SIH_LLM_API_KEY': 'test-only'}), patch('sih_ref.editorial.request_review', side_effect=[self.review, RuntimeError('private diagnostic')]):
            rows, status = evaluate([self.item], self.profile, self.provider, Path(tmp), date(2026, 10, 4))
            self.assertEqual('failed', rows[0]['editorial']['status'])
            self.assertNotIn('private diagnostic', json.dumps(rows))
            self.assertEqual('archive', rows[0]['reading_tier'])
            self.assertEqual('warning', status['status'])

    def test_no_credentials_and_stale_or_short_material(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True), patch('sih_ref.editorial.request_review') as call:
            rows, _ = evaluate([self.item, {**self.item, 'summary': 'Short'}, {**self.item, 'published_at': '2026-11-01'}], self.profile, self.provider, Path(tmp), date(2026, 10, 4))
            self.assertEqual(['unconfigured', 'insufficient_material', 'ineligible'], [r['editorial']['status'] for r in rows])
            self.assertFalse(call.called)

    def test_pending_projection_never_reuses_legacy_score(self):
        row = score_item({**self.item, 'topic_relevance': .98, 'reading_tier': 'must_read'}, self.profile, date(2026, 10, 4))
        self.assertEqual(0, row['topic_relevance'])
        self.assertEqual('archive', row['reading_tier'])

    def test_new_runner_reuses_published_receipts_but_not_a_changed_model(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SIH_LLM_API_KEY': 'test-only'}), patch('sih_ref.editorial.request_review', return_value=self.review) as call:
            root = Path(tmp)
            rows, _ = evaluate([self.item], self.profile, self.provider, root/'first', date(2026, 10, 4))
            (root/'items.jsonl').write_text(json.dumps(rows[0])+'\n', encoding='utf-8')
            restore_receipts(root/'items.jsonl', root/'runner')
            evaluate([self.item], self.profile, self.provider, root/'runner', date(2026, 10, 4))
            self.assertEqual(2, call.call_count)
            evaluate([self.item], self.profile, {**self.provider, 'model':'changed'}, root/'runner', date(2026, 10, 4))
            self.assertEqual(4, call.call_count)

    def test_old_archive_membership_survives_new_rejection(self):
        sys.path.insert(0, str(ROOT/'scripts'))
        from reader_context import update_history
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'history.jsonl'
            old = {**self.item, 'url':'https://example.org/original', 'reading_tier':'skim'}
            path.write_text(json.dumps(old)+'\n', encoding='utf-8')
            rejected = {**old, 'reading_tier':'archive', 'editorial':{'status':'scored','selected':False,'score':40}}
            rows = update_history(path, [rejected], self.profile, date(2026,10,4))
            self.assertEqual([old['url']], [r['url'] for r in rows])
            self.assertNotIn('editorial', rows[0])

    def test_feed_outage_retains_only_recent_verified_records_without_refreshing_age(self):
        now = datetime(2026,10,4,8,tzinfo=timezone.utc)
        health = [{'source_id':'journal','enabled':True,'status':'failed'}]
        rows, count = retain_recent_sources([], [self.item], health, '2026-10-04T06:00:00+00:00', now.date(), now)
        self.assertEqual(1, count)
        self.assertEqual(self.item['published_at'], rows[0]['published_at'])
        later = datetime(2026,10,6,8,tzinfo=timezone.utc)
        _, count = retain_recent_sources([], rows, health, later.isoformat(), later.date(), later)
        self.assertEqual(0, count)  # Repeated failures cannot reset the observed timestamp.
        for changed in [dict(self.item,published_at='2026-09-01'),dict(self.item,published_at='2026-11-01')]:
            self.assertEqual(0,retain_recent_sources([], [changed],health,now.isoformat(),now.date(),now)[1])
        health[0]['enabled'] = False
        self.assertEqual(0,retain_recent_sources([], [self.item],health,now.isoformat(),now.date(),now)[1])


if __name__ == '__main__': unittest.main()
