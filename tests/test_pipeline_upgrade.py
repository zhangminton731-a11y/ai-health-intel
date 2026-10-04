"""Regression cases for the Pages collection and publication upgrade."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from email.message import Message
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'engine/src'), str(ROOT/'scripts')]
from sih_ref.core import normalize_item, score_item
from sih_ref.rss_fetch import fetch_feed
from sih_ref.article_metadata import enrich_summary
from site_assets import extract_assets
from publication import coverage


class Response(BytesIO):
    status = 200
    def __init__(self, body=b'<rss><channel/></rss>', etag='"one"'):
        super().__init__(body)
        self.headers = Message()
        self.headers['Content-Type'] = 'application/rss+xml'
        self.headers['ETag'] = etag
    def geturl(self):
        return 'https://example.org/feed'


class CacheTests(unittest.TestCase):
    def test_304_reuses_validated_content_without_losing_items(self):
        body = b'<rss><channel><item><title>Clinical AI</title></item></channel></rss>'
        headers = Message()
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)/'feed.json'
            with patch('sih_ref.rss_fetch.urlopen', return_value=Response(body)):
                fetch_feed('https://example.org/feed', 'test', cache_path=cache)
            with patch('sih_ref.rss_fetch.urlopen', side_effect=HTTPError('https://example.org/feed',304,'',headers,BytesIO())) as call:
                root, checks = fetch_feed('https://example.org/feed', 'test', cache_path=cache)
            self.assertEqual('Clinical AI', root.findtext('.//title'))
            self.assertEqual('"one"', call.call_args.args[0].get_header('If-none-match'))
            self.assertEqual(0, checks[0]['bytes_read'])

    def test_corrupt_cache_is_refetched(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)/'feed.json'; cache.write_text('{broken')
            with patch('sih_ref.rss_fetch.urlopen', return_value=Response()) as call:
                fetch_feed('https://example.org/feed', 'test', cache_path=cache)
            self.assertIsNone(call.call_args.args[0].get_header('If-none-match'))

    def test_redirected_304_does_not_reuse_other_destinations_validator(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td)/'feed.json'
            with patch('sih_ref.rss_fetch.urlopen',return_value=Response()):
                fetch_feed('https://example.org/feed','test',cache_path=cache)
            error=HTTPError('https://other.example/feed',304,'',Message(),BytesIO())
            with patch('sih_ref.rss_fetch.urlopen',side_effect=[error,Response()]) as call, patch('sih_ref.rss_fetch.time.sleep'):
                fetch_feed('https://example.org/feed','test',cache_path=cache)
            self.assertEqual(2,call.call_count)
            self.assertIsNone(call.call_args.args[0].get_header('If-none-match'))


class MetadataTests(unittest.TestCase):
    def test_index_fallback_matches_exact_doi_and_retains_abstract_origin(self):
        url = 'https://www.nature.com/articles/s41746-026-03272-3'
        abstract = 'Published abstract about clinical validation. ' * 5
        for doi, expected in [('10.1038/s41746-026-03272-3', 'ok'), ('10.1038/other', 'unavailable')]:
            body = json.dumps({'resultList': {'result': [{'doi': doi, 'abstractText': abstract}]}}).encode()
            with patch('sih_ref.article_metadata.urlopen', side_effect=[OSError('transport'), Response(body)]):
                item = {'url': url, 'title': 'Clinical validation'}
                self.assertEqual(expected, enrich_summary(item, None)['status'])
                if expected == 'ok':
                    self.assertIn('europepmc', item['summary_source'])
                    self.assertEqual(abstract, item['summary'])
                else:
                    self.assertNotIn('summary', item)

    def test_success_is_cached_and_source_url_retained(self):
        url='https://www.nature.com/articles/test'
        summary='Source-authored clinical abstract. '*5
        response=Response(('<meta name="dc.description" content="'+summary+'">').encode())
        response.geturl=lambda:url
        with tempfile.TemporaryDirectory() as td, patch('sih_ref.article_metadata.urlopen',return_value=response) as request:
            first={'url':url,'title':'Clinical AI'}; second=dict(first)
            self.assertEqual('ok',enrich_summary(first,Path(td))['status'])
            self.assertEqual('cached',enrich_summary(second,Path(td))['status'])
            self.assertEqual(1,request.call_count)
            self.assertEqual(first['summary'],second['summary'])
            self.assertEqual(url,first['summary_source'])

    def test_missing_or_blocked_metadata_does_not_invent_summary(self):
        with patch('sih_ref.article_metadata.urlopen',side_effect=OSError()):
            row={'url':'https://www.nature.com/articles/test'}
            self.assertEqual('unavailable',enrich_summary(row,None)['status'])
            self.assertNotIn('summary',row)
        with patch('sih_ref.article_metadata.urlopen') as request:
            enrich_summary({'url':'https://untrusted.example/article'},None)
            request.assert_not_called()


class PublicationTests(unittest.TestCase):
    def test_assets_are_content_addressed_and_theme_remains_inline(self):
        with tempfile.TemporaryDirectory() as td:
            page='<script>theme()</script><style>body{color:red}</style><script>(()=>{alert(1)})();</script>'
            result=extract_assets(page,Path(td))
            self.assertIn('<script>theme()',result)
            self.assertNotIn('alert(1)',result)
            self.assertEqual(1,len(list((Path(td)/'assets').glob('*.js'))))
            extract_assets(page,Path(td))
            self.assertEqual(2,len(list((Path(td)/'assets').iterdir())))

    def test_zero_day_and_pending_content_are_distinct(self):
        row={'published_at':'2026-10-03','freshness_gate':'fresh','reading_tier':'archive','selection_reasons':['missing_summary']}
        report=coverage([row],date(2026,10,4))
        self.assertEqual(0,report['dates'][0]['collected'])
        self.assertEqual({'missing_summary':1},report['dates'][1]['excluded_reasons'])


class ResearchTests(unittest.TestCase):
    def score(self, title, summary='', day='2026-10-03'):
        profile = json.loads((ROOT/'config/profile.json').read_text(encoding='utf-8'))
        item = normalize_item({'title':title,'summary':summary,'url':'https://example.org/article','published_at':day}, {'id':'npj_digital_medicine','kind':'rss'})
        return score_item(item, profile, date(2026,10,4))

    def test_technical_research_is_not_dependent_on_launch_keywords(self):
        for title in ('Interpretable multimodal retrieval augmented diagnosis for breast ultrasound with clinical validation',
                      'OncoTagger: a reproducible landscape of AI-oncology articles',
                      'Shapley value explanations for clinical prediction models: a scoping review'):
            with self.subTest(title=title):
                result = self.score(title, 'A study of methods and validation with clinical data.')
                self.assertNotEqual('archive',result['reading_tier'])
                self.assertIn('research',result['selection_audiences'])

    def test_missing_abstract_is_pending_not_recommended(self):
        result = self.score('Clinical AI validation study')
        self.assertEqual('needs_review', result['content_status'])
        self.assertEqual('archive', result['reading_tier'])
        self.assertIn('missing_summary',result['selection_reasons'])

    def test_research_does_not_admit_unrelated_or_future_items(self):
        for title in ('Shapley explanations for financial prediction models', 'Clinical drug raises funding', 'AI hotel booking software'):
            self.assertEqual('archive',self.score(title,'General announcement')['reading_tier'])
        self.assertEqual('archive', self.score('Clinical AI validation','A clinical methods study','2026-10-05')['reading_tier'])


if __name__ == '__main__':
    unittest.main()
