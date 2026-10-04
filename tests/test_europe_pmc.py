from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine/src'))
from sih_ref.sources import collect_source


class JournalChannelTests(unittest.TestCase):
    def test_abstract_channel_preserves_source_dates_and_doi_and_is_not_keyword_filtered(self):
        src = {'id': 'journal', 'kind': 'europe_pmc', 'enabled': True, 'journal_issn': '0028-4793'}
        entry = {'id': '123', 'source': 'MED', 'pmid': '123', 'title': 'A negative trial',
                 'doi': '10.1/trial', 'abstractText': 'The treatment did not improve outcomes.',
                 'firstPublicationDate': '2026-09-28', 'journalInfo': {'journal': {'issn': '0028-4793'}}}
        with patch('sih_ref.sources._request_json', return_value={'resultList': {'result': [entry]}, 'hitCount': 1}) as request:
            result = collect_source(src, base_dir=Path('.'), live=True, as_of=date(2026, 10, 4))
            self.assertEqual('ok', result.status)
            self.assertEqual(entry['abstractText'], result.items[0]['summary'])
            self.assertEqual('2026-09-28', result.items[0]['published_at'])
            self.assertEqual('https://doi.org/10.1/trial', result.items[0]['url'])
            query = parse_qs(urlsplit(request.call_args.args[0]).query)['query'][0]
            self.assertIn('sort_date:y', query)
            self.assertIn('FIRST_PDATE:[2026-07-06 TO 2026-10-04]', query)
            self.assertNotIn('glucose', query)

    def test_wrong_journal_and_invalid_issn_cannot_enter_channel(self):
        src = {'id': 'journal', 'kind': 'europe_pmc', 'enabled': True, 'journal_issn': '0028-4793'}
        with patch('sih_ref.sources._request_json', return_value={'resultList': {'result': [{'journalInfo': {'journal': {'issn': '0000-0000'}}}]}}):
            self.assertEqual('failed', collect_source(src, base_dir=Path('.'), live=True, as_of=date(2026, 10, 4)).status)
        with patch('sih_ref.sources._request_json') as request:
            self.assertEqual('failed', collect_source({**src, 'journal_issn': 'anything OR anything'}, base_dir=Path('.'), live=True, as_of=date(2026, 10, 4)).status)
            request.assert_not_called()
