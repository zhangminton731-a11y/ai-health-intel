import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from export_access import export_access
spec=importlib.util.spec_from_file_location('sih_mcp_server',ROOT/'integrations/mcp/server.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)

class AccessTests(unittest.TestCase):
    def test_access_artifacts_have_real_paths_and_package(self):
        with tempfile.TemporaryDirectory() as folder:
            site=Path(folder);export_access(site)
            api=json.loads((site/'openapi.json').read_text(encoding='utf-8'))
            self.assertEqual('3.1.0',api['openapi'])
            self.assertEqual({'/api/v1/items.json','/api/v1/health.json','/api/v1/briefing.json'},set(api['paths']))
            self.assertTrue(all('parameters' not in v['get'] for v in api['paths'].values()))
            with zipfile.ZipFile(site/'sih-mcp.zip') as z:
                self.assertEqual({'sih-mcp/server.py','sih-mcp/requirements.txt','sih-mcp/README.md'},set(z.namelist()))
            self.assertIn('health.json',(site/'llms.txt').read_text(encoding='utf-8'))

    def snapshot(self):
        return {'generated_at':'2026-09-27T01:00:00+00:00','as_of':'2026-09-27','items':[
            {'title':'AI 医学论文','published_at':'2026-09-27','sections':['research'],'categories':{'research':['papers']},'research_stages':['analysis']},
            {'title':'AI 医学旧论文','published_at':'2020-01-01','sections':['research'],'categories':{'research':['papers']},'research_stages':['analysis']},
            {'title':'Future','published_at':'2027-01-01','sections':['research'],'categories':{'research':['papers']}},
            {'title':'融资','published_at':'2026-09-27','sections':['industry'],'categories':{'industry':['business']}}]}

    def test_mcp_filters_section_category_stage_keyword_and_date(self):
        data=bridge.filter_items(self.snapshot(),'research','papers','analysis','医学',1,7,datetime(2026,9,27,2,tzinfo=timezone.utc))
        self.assertEqual(1,data['matched_count']);self.assertEqual('AI 医学论文',data['items'][0]['title']);self.assertFalse(data['stale'])

    def test_mcp_empty_and_invalid_queries(self):
        self.assertEqual([],bridge.filter_items(self.snapshot(),keyword='unknown')['items'])
        with self.assertRaises(ValueError):bridge.filter_items(self.snapshot(),limit=1000)
        with self.assertRaises(ValueError):bridge.filter_items(self.snapshot(),section='not-a-section')

    def test_mcp_stale_or_missing_timestamp_is_disclosed(self):
        self.assertTrue(bridge.freshness({})['stale'])
        self.assertTrue(bridge.freshness(self.snapshot(),datetime(2026,9,30,tzinfo=timezone.utc))['stale'])

    def test_mcp_fixed_endpoints_and_network_errors(self):
        with patch.object(bridge,'urlopen',side_effect=OSError('network')) as mocked:
            with self.assertRaises(ValueError):bridge.load_snapshot('https://other.example')
            mocked.assert_not_called()
            with self.assertRaisesRegex(RuntimeError,'无法读取'):bridge.load_snapshot('health')
