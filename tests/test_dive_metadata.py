from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine/src'))
from sih_ref.dive_metadata import DiveBrief, enrich_dive_brief


class DiveMetadataTests(unittest.TestCase):
    def test_only_publisher_brief_is_read(self):
        p = DiveBrief()
        p.feed('<nav><ul><li>Menu</li></ul></nav><h3>Dive Brief:</h3><ul><li>Actual <a>source</a> fact.</li><li>Second fact.</li></ul><h3>Dive Insight:</h3><p>Entire article excluded.</p>')
        self.assertEqual('Actual source fact. Second fact.', ''.join(p.parts).strip())
        self.assertTrue(p.done)

    def test_allowlist_cache_and_missing_brief_preserve_original(self):
        item = {'url': 'https://www.healthcaredive.com/news/story/1/', 'summary': 'RSS teaser'}
        class Response(BytesIO):
            def geturl(self): return item['url']
        html = ('<h3>Dive Brief:</h3><ul><li>' + 'Source authored briefing fact. ' * 12 + '</li></ul>').encode()
        with tempfile.TemporaryDirectory() as tmp, patch('sih_ref.dive_metadata.urlopen', return_value=Response(html)) as call:
            self.assertEqual('ok', enrich_dive_brief(item, Path(tmp))['status'])
            self.assertEqual('cached', enrich_dive_brief(item, Path(tmp))['status'])
            self.assertEqual(1, call.call_count)
            self.assertEqual(item['url'], item['summary_source'])
        with patch('sih_ref.dive_metadata.urlopen', return_value=Response(b'<p>No brief</p>')):
            original = {**item, 'summary': 'Original teaser'}
            self.assertEqual('unavailable', enrich_dive_brief(original, None)['status'])
            self.assertEqual('Original teaser', original['summary'])
        with patch('sih_ref.dive_metadata.urlopen') as call:
            self.assertEqual('skipped', enrich_dive_brief({'url': 'https://untrusted.example/news'}, None)['status'])
            call.assert_not_called()
