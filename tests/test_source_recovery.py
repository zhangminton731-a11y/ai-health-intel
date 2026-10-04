"""Failure recovery, diagnostic privacy and persistent source observation tests."""

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from email.message import Message
from email.utils import format_datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine/src'))
from sih_ref.rss_fetch import FeedFetchError, fetch_feed, retry_after_seconds
from sih_ref.pipeline import run_pipeline
from sih_ref.source_health import deferred_retry, load_history, update_source_health
from sih_ref.sources import SourceResult


class Response(BytesIO):
    status = 200

    def __init__(self, body=b'<rss><channel/></rss>'):
        super().__init__(body)
        self.headers = Message()
        self.headers['Content-Type'] = 'application/rss+xml; charset=utf-8'
        self.headers['Set-Cookie'] = 'private-cookie-fixture'

    def geturl(self):
        return 'https://user:password@example.org/feed?token=private-query-fixture#private-fragment-fixture'


def http_error(status, retry_after=None):
    headers = Message()
    headers['Content-Type'] = 'text/html'
    if retry_after:
        headers['Retry-After'] = retry_after
    return HTTPError('https://example.org/feed?token=private', status, 'private-message', headers, BytesIO())


class FetchTests(unittest.TestCase):
    def run_fetch(self, responses):
        with patch('sih_ref.rss_fetch.urlopen', side_effect=responses) as request, \
             patch('sih_ref.rss_fetch.time.sleep') as sleep, \
             patch('sih_ref.rss_fetch.random.uniform', return_value=0.25):
            root, checks = fetch_feed('https://example.org/feed', 'test')
        return root, checks, request, sleep

    def test_success_preserves_feed_and_allowlisted_metadata(self):
        root, checks, request, sleep = self.run_fetch([Response()])
        self.assertEqual('rss', root.tag)
        self.assertEqual(1, request.call_count)
        sleep.assert_not_called()
        self.assertEqual(200, checks[0]['http_status'])
        self.assertEqual('https://example.org/feed', checks[0]['final_url'])
        self.assertEqual('application/rss+xml', checks[0]['content_type'])
        self.assertNotIn('private', json.dumps(checks))
        self.assertNotIn('password', json.dumps(checks))

    def test_parse_failure_then_success_retains_both_attempts(self):
        _, checks, _, sleep = self.run_fetch([Response(b'<rss>&private-body-fixture;</rss>'), Response()])
        self.assertEqual('invalid_xml', checks[0]['error_code'])
        self.assertIn('parse_line', checks[0])
        self.assertIsNone(checks[1]['error_code'])
        sleep.assert_called_once_with(5.25)
        self.assertNotIn('private-body', json.dumps(checks))

    def test_timeout_then_server_error_then_success_has_single_retry_budget(self):
        _, checks, request, sleep = self.run_fetch([URLError(TimeoutError()), http_error(503), Response()])
        self.assertEqual(['timeout', 'server_error', None], [row['error_code'] for row in checks])
        self.assertEqual(3, request.call_count)
        self.assertEqual([5.25, 10.25], [call.args[0] for call in sleep.call_args_list])

    def test_rate_limit_respects_retry_after(self):
        _, checks, _, sleep = self.run_fetch([http_error(429, '30'), Response()])
        self.assertEqual('rate_limited', checks[0]['error_code'])
        sleep.assert_called_once_with(30)

    def test_long_retry_after_defers_instead_of_retrying_early(self):
        with patch('sih_ref.rss_fetch.urlopen', side_effect=http_error(503, '120')) as request, \
             patch('sih_ref.rss_fetch.time.sleep') as sleep:
            with self.assertRaises(FeedFetchError) as caught:
                fetch_feed('https://example.org/feed', 'test')
        self.assertEqual(1, request.call_count)
        sleep.assert_not_called()
        self.assertTrue(caught.exception.checks[0]['retry_deferred'])

    def test_retry_after_http_date_and_invalid_header(self):
        future = datetime.now(timezone.utc) + timedelta(seconds=40)
        delay = retry_after_seconds(format_datetime(future, usegmt=True))
        self.assertTrue(38 <= delay <= 40)
        self.assertIsNone(retry_after_seconds('invalid'))

    def test_permanent_http_error_does_not_retry_or_leak_exception(self):
        with patch('sih_ref.rss_fetch.urlopen', side_effect=http_error(404)) as request:
            with self.assertRaises(FeedFetchError) as caught:
                fetch_feed('https://example.org/feed', 'test')
        self.assertEqual(1, request.call_count)
        self.assertEqual('http_error', caught.exception.code)
        self.assertNotIn('private', json.dumps(caught.exception.checks))
        self.assertNotIn('private', str(caught.exception))

    def test_200_html_is_failure_after_three_attempts(self):
        with patch('sih_ref.rss_fetch.urlopen', side_effect=[Response(b'<!DOCTYPE html><html>private</html>') for _ in range(3)]) as request, \
             patch('sih_ref.rss_fetch.time.sleep'):
            with self.assertRaises(FeedFetchError) as caught:
                fetch_feed('https://example.org/feed', 'test')
        self.assertEqual(3, request.call_count)
        self.assertEqual('non_feed', caught.exception.code)
        self.assertNotIn('private', json.dumps(caught.exception.checks))

    def test_excessive_response_stops_without_retry(self):
        with patch('sih_ref.rss_fetch.MAX_FEED_BYTES', 4), \
             patch('sih_ref.rss_fetch.urlopen', return_value=Response()) as request:
            with self.assertRaises(FeedFetchError) as caught:
                fetch_feed('https://example.org/feed', 'test')
        self.assertEqual('response_too_large', caught.exception.code)
        self.assertEqual(1, request.call_count)


class HistoryTests(unittest.TestCase):
    def test_retry_after_survives_batches_without_inflating_failure_count(self):
        source = {'id': 'feed', 'kind': 'rss', 'enabled': True}
        history = {'feed': {
            'consecutive_failures': 2, 'last_success_at': None,
            'retry_not_before': '2026-10-03T00:00:00+00:00', 'error_code': 'rate_limited',
        }}
        now = '2026-10-02T12:00:00+00:00'
        check = deferred_retry(source, history, now)
        manifest = {'source_id': 'feed', 'generated_at': now, 'status': 'failed', 'checks': [check]}
        update_source_health(manifest, history)
        self.assertEqual(2, manifest['consecutive_failures'])
        self.assertEqual('rate_limited', check['error_code'])
        self.assertIsNone(deferred_retry(source, history, '2026-10-03T00:00:00+00:00'))

    def test_inactive_source_preserves_retry_window_without_new_observation(self):
        history = {'feed': {'consecutive_failures': 2, 'retry_not_before': '2026-10-03T00:00:00+00:00'}}
        before = json.dumps(history)
        manifest = {'source_id': 'feed', 'generated_at': '2026-10-02T12:00:00+00:00', 'status': 'inactive'}
        update_source_health(manifest, history)
        self.assertEqual(before, json.dumps(history))
        self.assertEqual(2, manifest['consecutive_failures'])

    def test_pipeline_does_not_contact_rate_limited_source_before_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / '.state').mkdir()
            state = {'feed': {'consecutive_failures': 1, 'retry_not_before': '2026-10-03T00:00:00+00:00', 'error_code': 'rate_limited'}}
            (out / '.state/source_health_history.json').write_text(json.dumps(state))
            config = out / 'config.json'
            config.write_text(json.dumps({'sources': [{'id': 'feed', 'kind': 'rss', 'enabled': True}]}))
            profile = out / 'profile.json'
            profile.write_text('{}')
            with patch('sih_ref.pipeline.collect_source') as collect, \
                 patch('sih_ref.pipeline.generated_at', return_value='2026-10-02T12:00:00+00:00'):
                result = run_pipeline(config_path=config, profile_path=profile, output_dir=out, as_of=date(2026, 10, 2), live=True)
            collect.assert_not_called()
            self.assertEqual('failed', result['daily_status'])
            self.assertEqual(1, load_history(out / '.state/source_health_history.json')['feed']['consecutive_failures'])

    def test_failed_batches_persist_and_recovery_resets_without_old_items(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            config = out / 'config.json'
            config.write_text(json.dumps({'sources': [{'id': 'feed', 'kind': 'rss', 'enabled': True}]}))
            profile = out / 'profile.json'
            profile.write_text('{}')
            results = [
                SourceResult('feed', 'ok', [{'title': 'Study', 'url': 'https://example.org/paper', 'published_at': '2026-10-02'}]),
                SourceResult('feed', 'failed', error='RSS invalid_xml'),
                SourceResult('feed', 'failed', error='RSS invalid_xml'),
                SourceResult('feed', 'ok_no_updates'),
            ]
            observed = []
            with patch('sih_ref.pipeline.collect_source', side_effect=results):
                for _ in results:
                    run_pipeline(config_path=config, profile_path=profile, output_dir=out, as_of=date(2026, 10, 2))
                    health = json.loads((out / 'source_health.json').read_text())
                    observed.append(health['sources'][0])
                    if len(observed) > 1:
                        self.assertEqual('', (out / 'daily_items.jsonl').read_text())
            self.assertEqual([0, 1, 2, 0], [source['consecutive_failures'] for source in observed])
            self.assertEqual(observed[0]['last_success_at'], observed[2]['last_success_at'])
            self.assertTrue(observed[3]['recovered'])
            self.assertEqual(0, load_history(out / '.state/source_health_history.json')['feed']['consecutive_failures'])

    def test_corrupt_history_is_unknown_not_a_claim_of_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            path.write_text('{"feed": {"consecutive_failures": "bad"}}')
            self.assertEqual({}, load_history(path))


if __name__ == '__main__':
    unittest.main()
