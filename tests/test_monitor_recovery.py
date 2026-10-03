"""Only confirmed delivery suppresses alerts; unhealthy checks remain failures."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_published import alert_message, main, notify_if_needed


class MonitorRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'receipt.json'
        self.now = datetime(2026, 10, 2, 7, tzinfo=timezone.utc)
        self.issues = ['部分信源采集异常']
        self.health = {
            'generated_at': self.now.isoformat(),
            'daily_status': 'complete_with_warning',
            'sources': [{
                'source_id': 'npj_digital_medicine', 'enabled': True, 'status': 'failed',
                'consecutive_failures': 1, 'last_success_at': None,
                'checks': [{'error_code': 'invalid_xml'}],
            }],
        }

    def notify(self, issues=None, now=None):
        return notify_if_needed(
            self.issues if issues is None else issues, self.health,
            now or self.now, self.path,
        )

    def test_unconfigured_and_failed_delivery_do_not_suppress_retry(self):
        with patch('check_published.send', return_value='not_configured') as sender:
            self.assertEqual('not_configured', self.notify())
            self.assertEqual('not_configured', self.notify())
            self.assertEqual(2, sender.call_count)
        self.assertFalse(self.path.exists())
        with patch('check_published.send', side_effect=RuntimeError('delivery failed')):
            with self.assertRaises(RuntimeError):
                self.notify()
        self.assertFalse(self.path.exists())

    def test_identical_acknowledged_issue_is_suppressed_then_reminded(self):
        with patch('check_published.send', return_value='sent') as sender:
            self.assertEqual('sent', self.notify())
            self.health['sources'][0]['consecutive_failures'] = 2
            self.assertEqual('suppressed', self.notify(now=self.now + timedelta(hours=2)))
            self.assertEqual('sent', self.notify(now=self.now + timedelta(hours=24)))
            self.assertEqual(2, sender.call_count)

    def test_third_failed_batch_escalates_once(self):
        with patch('check_published.send', return_value='sent') as sender:
            self.notify()
            self.health['sources'][0]['consecutive_failures'] = 3
            self.assertEqual('sent', self.notify(now=self.now + timedelta(hours=2)))
            self.health['sources'][0]['consecutive_failures'] = 4
            self.assertEqual('suppressed', self.notify(now=self.now + timedelta(hours=3)))
            self.assertEqual(2, sender.call_count)

    def test_changed_failure_cause_notifies(self):
        with patch('check_published.send', return_value='sent') as sender:
            self.notify()
            self.health['sources'][0]['checks'][0]['error_code'] = 'rate_limited'
            self.assertEqual('sent', self.notify(now=self.now + timedelta(hours=1)))
            self.assertEqual(2, sender.call_count)

    def test_recovery_notifies_once_and_new_incident_alerts_again(self):
        with patch('check_published.send', return_value='sent') as sender:
            self.notify()
            self.assertEqual('sent', self.notify(issues=[]))
            self.assertIn('已恢复', sender.call_args.args[0])
            self.assertEqual('unchanged', self.notify(issues=[]))
            self.assertEqual('sent', self.notify())
            self.assertEqual(3, sender.call_count)

    def test_failed_recovery_delivery_does_not_clear_incident(self):
        with patch('check_published.send', return_value='sent'):
            self.notify()
        with patch('check_published.send', return_value='not_configured'):
            self.notify(issues=[])
        self.assertEqual('alert', json.loads(self.path.read_text())['status'])

    def test_unknown_history_is_explicit_in_message(self):
        del self.health['sources'][0]['consecutive_failures']
        message = alert_message(self.issues, self.health)
        self.assertIn('连续失败次数未知', message)
        self.assertIn('最后成功 未知', message)

    def test_corrupt_receipt_retries_notification(self):
        self.path.write_text('{"status":"alert"}')
        with patch('check_published.send', return_value='sent') as sender:
            self.assertEqual('sent', self.notify())
            sender.assert_called_once()

    def test_unhealthy_exit_stays_nonzero_when_notification_suppressed(self):
        with patch('check_published.urlopen') as request, \
             patch('check_published.notify_if_needed', return_value='suppressed'), \
             patch('sys.argv', ['check_published.py']):
            request.return_value.__enter__.return_value.read.return_value = json.dumps(self.health).encode()
            self.assertEqual(1, main())


if __name__ == '__main__':
    unittest.main()
