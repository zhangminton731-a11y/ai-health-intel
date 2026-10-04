from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine/src'))
from sih_ref.official_metadata import FdaRelease, enrich_fda_release
from sih_ref.core import normalize_item


class OfficialMetadataTests(unittest.TestCase):
    def test_only_main_release_paragraphs_are_read(self):
        p = FdaRelease()
        p.feed('<aside><p>Navigation</p></aside><div role="main"><div><p>Official <b>approval</b>.</p></div><p>Study limitations.</p></div><footer><p>Other news</p></footer>')
        self.assertEqual(['Official approval.', 'Study limitations.'], p.paragraphs)

    def test_excerpt_provenance_and_failed_fetch_preserve_teaser(self):
        url = 'https://www.fda.gov/news-events/press-announcements/release'
        class Response(BytesIO):
            def geturl(self): return url
        item = {'url': url, 'summary': 'Source teaser'}
        body = ('<div role="main"><p>' + 'Official source evidence. ' * 12 + '</p></div>').encode()
        with patch('sih_ref.official_metadata.urlopen', return_value=Response(body)):
            self.assertEqual('ok', enrich_fda_release(item, None)['status'])
        row = normalize_item(item, {'id': 'fda', 'kind': 'rss'})
        self.assertEqual('source_excerpt', row['provenance']['summary_kind'])
        with patch('sih_ref.official_metadata.urlopen', side_effect=OSError):
            item = {'url': url, 'summary': 'Source teaser'}
            self.assertEqual('unavailable', enrich_fda_release(item, None)['status'])
            self.assertEqual('Source teaser', item['summary'])
