from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
from email.message import Message
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'engine/src'), str(ROOT / 'scripts')]
from sih_ref.sources import collect_source
from sih_ref.core import normalize_item, score_item
import quality_gate

class FeedResponse(BytesIO):
    status = 200

    def __init__(self, xml):
        super().__init__(xml.encode())
        self.headers = Message()
        self.headers['Content-Type'] = 'application/rss+xml'

    def geturl(self):
        return 'https://example.org/rss'


class SourceTests(unittest.TestCase):
    def test_source_images_are_preserved_and_unsafe_urls_rejected(self):
        from sih_ref.sources import feed_image
        import xml.etree.ElementTree as ET
        for xml, expected in (
            ('<item><enclosure type="image/jpeg" url="/cover.jpg"/></item>', 'https://example.org/cover.jpg'),
            ('<item><description>&lt;img src="https://example.org/pic.png"&gt;</description></item>', 'https://example.org/pic.png'),
            ('<item xmlns:m="http://search.yahoo.com/mrss/"><m:thumbnail url="https://example.org/t.jpg"/></item>', 'https://example.org/t.jpg'),
            ('<item><description>&lt;img src="javascript:alert(1)"&gt;</description></item>', ''),
            ('<item><enclosure type="image/jpeg"/></item>', ''),
            ('<item xmlns:m="http://search.yahoo.com/mrss/"><m:content type="video/mp4" url="https://example.org/movie.mp4"/></item>', ''),
        ):
            with self.subTest(xml=xml):
                image = feed_image(ET.fromstring(xml), 'https://example.org/article')
                self.assertEqual(expected, image)
                item = normalize_item({'title':'Article', 'url':'https://example.org/article', 'image_url':image}, {'id':'test','kind':'rss'})
                self.assertEqual(expected, item['provenance'].get('image_url', ''))

    def collect(self, responses):
        with patch('sih_ref.rss_fetch.urlopen', side_effect=[FeedResponse(xml) for xml in responses]) as request, \
             patch('sih_ref.rss_fetch.time.sleep'):
            result = collect_source(
                {'id': 'test', 'kind': 'rss', 'enabled': True, 'url': 'https://example.org/rss'},
                base_dir=ROOT, live=True, as_of=date(2026, 9, 28),
            )
        return result, request.call_count

    def test_rdf_nature_feed(self):
        result, _ = self.collect(['<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"><item><title>Clinical AI study</title><link>https://example.org/paper</link><description>Study abstract</description><dc:date>2026-09-26</dc:date></item></rdf:RDF>'])
        self.assertEqual(1, len(result.items))
        self.assertEqual('2026-09-26', result.items[0]['published_at'])

    def test_atom_prefers_article_over_self(self):
        result, _ = self.collect(['<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x</id><title>Health device</title><link rel="self" href="https://example.org/api/x"/><link rel="alternate" href="https://example.org/article"/><published>2026-09-26</published></entry></feed>'])
        self.assertEqual('https://example.org/article', result.items[0]['url'])

    def test_rss_retries_invalid_response_then_recovers(self):
        xml = '<rss><channel><item><title>Clinical AI</title><link>https://example.org/paper</link></item></channel></rss>'
        result, attempts = self.collect(['<rss>', '<html><body>Error</body></html>', xml])
        self.assertEqual('ok', result.status)
        self.assertEqual(1, len(result.items))
        self.assertEqual(3, attempts)
        self.assertEqual(['invalid_xml', 'non_feed', None], [check['error_code'] for check in result.checks[:-1]])

    def test_rss_repeated_html_response_is_failed_not_empty_success(self):
        result, attempts = self.collect(['<html><body>Unavailable</body></html>'] * 3)
        self.assertEqual('failed', result.status)
        self.assertEqual([], result.items)
        self.assertIn('non_feed', result.error)
        self.assertEqual(3, attempts)


class RelevanceTests(unittest.TestCase):
    def score(self, title):
        profile = json.loads((ROOT/'config/profile.json').read_text(encoding='utf-8'))
        item = normalize_item({'title':title,'url':'https://example.org/x','published_at':'2026-09-27'}, {'id':'test','kind':'rss'})
        return score_item(item, profile, date(2026,9,27))

    def test_hotel_funding_does_not_qualify(self):
        self.assertEqual('archive',self.score('Hotel AI agent raises series A funding to launch new features')['reading_tier'])

    def test_financial_identity_does_not_qualify(self):
        self.assertEqual('archive',self.score('Baselayer raises funding for financial fraud identity technology')['reading_tier'])

    def test_hospital_imaging_is_in_scope(self):
        self.assertNotEqual('archive',self.score('Hospital launches artificial intelligence for medical imaging workflow')['reading_tier'])

    def test_consumer_wearable_is_in_scope(self):
        self.assertNotEqual('archive',self.score('Wearable smart ring launches sleep monitoring feature')['reading_tier'])

    def test_drug_funding_without_technology_does_not_qualify(self):
        self.assertEqual('archive',self.score('New clinical immunology drugs raise funding in IPO')['reading_tier'])

    def test_ai_drug_discovery_is_in_scope(self):
        self.assertNotEqual('archive',self.score('Biotech raises funding for artificial intelligence drug discovery')['reading_tier'])

class GateTests(unittest.TestCase):
    def test_sixth_invalid_line_and_missing_health_fail(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); (out/'site').mkdir()
            for name in ['daily_briefing.md','daily_briefing_cn.md','site/index.html']:(out/name).write_text('test',encoding='utf-8')
            good=json.dumps({'item_id':'x','title':'x','url':'https://example.org/x'})
            (out/'daily_items.jsonl').write_text('\n'.join([good]*5+['invalid']),encoding='utf-8')
            with patch.object(quality_gate,'OUTPUT',out):
                self.assertNotEqual(0,quality_gate.main())

if __name__=='__main__':unittest.main()
