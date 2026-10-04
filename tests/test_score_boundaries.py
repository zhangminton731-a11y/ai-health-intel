from datetime import date
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine/src'))
from sih_ref.core import score_item


class ScoreBoundaryTests(unittest.TestCase):
    def test_score_has_hard_ceiling_without_changing_lower_scores(self):
        item = {'title': 'Wearable smartwatch health app cgm glucose', 'published_at': '2026-10-04', 'source_kind': 'rss'}
        profile = {'topic_terms': {'wearable': .3, 'smartwatch': .26, 'health app': .28, 'cgm': .24, 'glucose': .22}, 'source_weights': {'rss': .05}}
        self.assertEqual(.98, score_item(item, profile, date(2026, 10, 4))['topic_relevance'])
        self.assertEqual(.35, score_item({**item, 'title': 'Wearable'}, profile, date(2026, 10, 4))['topic_relevance'])

    def test_embedded_english_terms_do_not_inflate_score(self):
        profile = {'topic_terms': {'valuation': .22, 'series a': .28}, 'freshness_days': 10}
        item = {'title': 'Evaluation of CT series analysis', 'published_at': '2026-10-04'}
        self.assertEqual(0, score_item(item, profile, date(2026, 10, 4))['topic_relevance'])
        item['title'] = 'Series A funding with a new valuation'
        self.assertEqual(.5, score_item(item, profile, date(2026, 10, 4))['topic_relevance'])

    def test_chinese_terms_and_hyphenated_english_still_match(self):
        item = {'title': '医院医疗AI升级与 AI-powered tools', 'published_at': '2026-10-04'}
        profile = {'topic_terms': {'医疗AI': .35, 'ai': .25}, 'freshness_days': 10}
        self.assertEqual(.6, score_item(item, profile, date(2026, 10, 4))['topic_relevance'])

    def test_regular_plurals_keep_relevant_wearables(self):
        item = {'title': 'Wearables and smartwatches', 'published_at': '2026-10-04'}
        profile = {'topic_terms': {'wearable': .3, 'smartwatch': .26}, 'freshness_days': 10}
        self.assertEqual(.56, score_item(item, profile, date(2026, 10, 4))['topic_relevance'])


if __name__ == '__main__': unittest.main()
