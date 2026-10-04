from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine/src'))
from sih_ref.cms_facts import FactSheetListing, collect_fact_sheets
from sih_ref.public_body import PublicBody, enrich_public_body
from sih_ref.sources import collect_source


class CmsFactsTests(unittest.TestCase):
    def test_only_publisher_fact_sheet_links_are_collected(self):
        parser = FactSheetListing()
        parser.feed('<a href="/newsroom/fact-sheets/nav">Navigation</a><h3><a href="/newsroom/press-releases/news">News</a></h3>'
                    '<h3><a href="/newsroom/fact-sheets/rule"><span>Final</span> rule</a></h3>')
        self.assertEqual([{'url': 'https://www.cms.gov/newsroom/fact-sheets/rule', 'title': 'Final rule'}], parser.items)

    def test_original_publication_not_modified_date_and_no_navigation(self):
        parser = PublicBody()
        parser.feed('<nav>Navigation</nav><script type="application/ld+json">{"@graph":[{"@type":"NewsArticle",'
                    '"datePublished":"2026-09-12T08:00:00-04:00","dateModified":"2026-10-04T08:00:00Z"}]}</script>'
                    '<div class="field--name-body"><p>Policy.</p><div><p>Payment.</p></div></div><footer>Footer</footer>')
        self.assertEqual('2026-09-12', parser.published)
        self.assertEqual('Policy. Payment.', ' '.join(''.join(parser.parts).split()))

    def test_valid_cache_avoids_request_and_other_hosts_are_not_fetched(self):
        url = 'https://www.cms.gov/newsroom/fact-sheets/rule'
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            saved = {'url': url, 'published_at': '2026-09-12', 'summary': 'Source-authored policy details. ' * 10}
            (cache / (hashlib.sha256(url.encode()).hexdigest() + '.json')).write_text(json.dumps(saved), encoding='utf-8')
            item = {'url': url}
            with patch('sih_ref.public_body.urlopen') as request:
                self.assertEqual('ok', enrich_public_body(item, cache)['status'])
                self.assertEqual('skipped', enrich_public_body({'url': 'https://example.org/a'}, cache)['status'])
                request.assert_not_called()
            self.assertEqual('2026-09-12', item['published_at'])

    def test_cms_adapter_requires_live_and_parse_failure_is_not_success(self):
        source = {'id': 'cms', 'kind': 'cms_facts', 'enabled': True}
        self.assertEqual('inactive', collect_source(source, base_dir=Path('.'), live=False, as_of=date(2026,10,4)).status)
        with patch('sih_ref.cms_facts.urlopen') as request:
            request.return_value.__enter__.return_value.read.return_value = b'<html>Changed listing</html>'
            result = collect_source(source, base_dir=Path('.'), live=True, as_of=date(2026,10,4))
        self.assertEqual('failed', result.status)


if __name__ == '__main__': unittest.main()
