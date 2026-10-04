import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_feeds import export_feeds
from quality_gate import validate
from check_published import problems
from notify_feishu import message_payload, send

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.now = datetime(2026, 9, 27, 1, 30, tzinfo=timezone.utc)
        self.health = {'as_of':'2026-09-27','generated_at':self.now.isoformat(),
                       'daily_status':'complete','sources':[{'enabled':True,'status':'ok'}]}
        self.raw = [{'item_id':str(i),'title':'Clinical AI','url':f'https://example.org/{i}',
                     'freshness_gate':'fresh','reading_tier':'skim'} for i in range(6)]
        rows = [{'id':i['item_id'],'t':'医疗 AI','te':i['title'],'s':'摘要','se':'Abstract',
                 'u':i['url'],'src':'Journal','sourceType':'期刊论文','date':'2026-09-27',
                 'topics':['hospital'],'event':'new','provenance':{},'freshness':'fresh','tier':'skim'} for i in self.raw]
        self.payload = {'name':'Test','items':rows,'top':['0','1'],'hot30':rows,
                        'generatedAt':self.now.isoformat(),'asOf':'2026-09-27','briefing':'简报'}
        (self.out/'daily_items.jsonl').write_text('\n'.join(map(json.dumps,self.raw)),encoding='utf-8')
        (self.out/'source_health.json').write_text(json.dumps(self.health),encoding='utf-8')
        for name in ('daily_briefing.md','daily_briefing_cn.md'):
            (self.out/name).write_text('简报',encoding='utf-8')
        (self.out/'site').mkdir()
        (self.out/'site/index.html').write_text('<script id="payload" type="application/json">'+json.dumps(self.payload)+'</script>',encoding='utf-8')
        export_feeds(self.out/'site',self.payload,self.health,'简报',ROOT/'skills/sih-intel')

    def issues(self):
        return validate(self.out,self.now)

    def test_valid_batch(self):
        self.assertEqual([], self.issues())

    def test_invalid_sixth_record_is_checked(self):
        path=self.out/'daily_items.jsonl'
        path.write_text('\n'.join(map(json.dumps,self.raw[:5]))+'\ninvalid',encoding='utf-8')
        self.assertTrue(any('第 6 条' in p for p in self.issues()))

    def test_missing_health_blocks(self):
        (self.out/'source_health.json').unlink()
        self.assertTrue(any('source_health.json' in p for p in self.issues()))

    def test_api_drift_blocks(self):
        path=self.out/'site/api/v1/items.json'
        data=json.loads(path.read_text(encoding='utf-8'));data['items'].pop()
        path.write_text(json.dumps(data),encoding='utf-8')
        self.assertIn('API 与网页推荐池不一致',self.issues())

    def test_page_briefing_drift_blocks(self):
        path=self.out/'site/index.html'
        html=path.read_text(encoding='utf-8').replace(json.dumps('简报'),json.dumps('旧简报'))
        path.write_text(html,encoding='utf-8')
        self.assertIn('网页与接口日报文本不一致',self.issues())

    def test_daily_edition_cannot_claim_another_publication_date(self):
        self.payload['dailyIssues']=[{'date':'2026-09-26','item_ids':['0'],'minutes':1}]
        self.payload['dailyIds']=['0']
        (self.out/'site/index.html').write_text('<script id="payload" type="application/json">'+json.dumps(self.payload)+'</script>',encoding='utf-8')
        export_feeds(self.out/'site',self.payload,self.health,'简报',ROOT/'skills/sih-intel')
        self.assertIn('日报包含非当日或不合格条目',self.issues())

    def test_daily_directory_drift_blocks(self):
        path=self.out/'site/api/v1/briefing.json'
        data=json.loads(path.read_text(encoding='utf-8'))
        data['editions']=[{'date':'2026-09-27','item_ids':['0'],'minutes':1}]
        path.write_text(json.dumps(data),encoding='utf-8')
        self.assertIn('日报日期目录与接口不一致',self.issues())

    def test_section_projection_drift_blocks(self):
        path=self.out/'site/api/v1/items.json'
        data=json.loads(path.read_text(encoding='utf-8'))
        data['items'][0]['sections']=['industry']
        path.write_text(json.dumps(data),encoding='utf-8')
        self.assertIn('API 与网页栏目分类不一致',self.issues())

    def test_old_batch_blocks(self):
        self.assertTrue(any('36 小时' in p for p in validate(self.out,self.now+timedelta(hours=37))))

    def test_old_rss_entry_blocks(self):
        path=self.out/'site/feed.xml'
        path.write_text(path.read_text(encoding='utf-8').replace('>5</guid>','>expired</guid>'),encoding='utf-8')
        self.assertIn('RSS 与网页推荐池不一致',self.issues())

    def test_failed_majority_blocks(self):
        self.health['sources']=[{'enabled':True,'status':'failed'}]*2+[{'enabled':True,'status':'ok'}]
        (self.out/'source_health.json').write_text(json.dumps(self.health),encoding='utf-8')
        self.assertIn('成功来源不足一半',self.issues())

    def test_archive_does_not_enter_public_feeds(self):
        self.payload['items'][0]['tier']='archive'
        export_feeds(self.out/'site',self.payload,self.health,'简报',ROOT/'skills/sih-intel')
        items=json.loads((self.out/'site/api/v1/items.json').read_text(encoding='utf-8'))
        self.assertNotIn('0',[i['id'] for i in items['items']])

class AlertTests(unittest.TestCase):
    def test_signed_payload(self):
        expected=base64.b64encode(hmac.new(b'123\nsecret',b'',hashlib.sha256).digest()).decode()
        self.assertEqual(expected,message_payload('test','secret',123)['sign'])

    def test_no_bot_does_not_send(self):
        with patch.dict(os.environ,{},clear=True),patch('notify_feishu.urlopen') as network:
            self.assertEqual('not_configured',send('test'))
            network.assert_not_called()

    def test_wrong_endpoint_does_not_send(self):
        with patch.dict(os.environ,{'FEISHU_BOT_WEBHOOK':'https://example.org/secret'}),patch('notify_feishu.urlopen') as network:
            with self.assertRaises(ValueError):send('test')
            network.assert_not_called()

    def test_feishu_acknowledgement(self):
        with patch.dict(os.environ,{'FEISHU_BOT_WEBHOOK':'https://open.feishu.cn/open-apis/bot/v2/hook/test'}),patch('notify_feishu.urlopen') as network:
            network.return_value.__enter__.return_value.read.return_value=b'{"code":0}'
            self.assertEqual('sent',send('test'))
            network.return_value.__enter__.return_value.read.return_value=b'{"code":19021}'
            with self.assertRaises(RuntimeError):send('test')

    def test_morning_deadline_and_staleness(self):
        health={'generated_at':'2026-09-26T13:00:00+00:00','daily_status':'complete'}
        self.assertEqual([],problems(health,datetime(2026,9,27,0,59,tzinfo=timezone.utc)))
        self.assertIn('今天的早间更新尚未上线',problems(health,datetime(2026,9,27,1,0,tzinfo=timezone.utc)))
        self.assertTrue(any('36 小时' in p for p in problems(health,datetime(2026,9,28,2,tzinfo=timezone.utc))))

    def test_partial_sources_alert(self):
        health={'generated_at':'2026-09-27T01:00:00+00:00','daily_status':'complete_with_warning'}
        self.assertIn('部分信源采集异常',problems(health,datetime(2026,9,27,2,tzinfo=timezone.utc)))

    def test_editorial_review_queue_is_not_a_source_outage(self):
        now=datetime(2026,9,27,2,tzinfo=timezone.utc)
        health={'generated_at':now.isoformat(),'daily_status':'complete_with_warning',
                'sources':[{'enabled':True,'status':'ok'}],
                'editorial':{'counts':{'scored':138,'needs_review':32}}}
        self.assertEqual([],problems(health,now))
        health['sources'][0]['status']='failed'
        self.assertIn('部分信源采集异常',problems(health,now))

    def test_model_failure_still_alerts_with_healthy_sources(self):
        now=datetime(2026,9,27,2,tzinfo=timezone.utc)
        health={'generated_at':now.isoformat(),'daily_status':'complete_with_warning',
                'sources':[{'enabled':True,'status':'ok_no_updates'}],
                'editorial':{'counts':{'failed':1,'needs_review':32}}}
        self.assertEqual(['部分内容模型评分失败或未配置'],problems(health,now))
        health['editorial']['counts']={'unconfigured':10}
        self.assertEqual(['部分内容模型评分失败或未配置'],problems(health,now))
