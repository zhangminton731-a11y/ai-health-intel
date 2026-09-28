from pathlib import Path
import sys
import unittest
import anyio
from mcp import Client, StdioServerParameters

class StdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_discover_call_filter_error_and_recover(self):
        params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('fixture_server.py'))])
        with anyio.fail_after(30):
            async with Client(params) as client:
                tools=(await client.list_tools()).tools
                self.assertEqual({'sih_health','sih_items','sih_briefing'},{t.name for t in tools})
                self.assertTrue(all(t.annotations.read_only_hint for t in tools))
                health=await client.call_tool('sih_health')
                self.assertFalse(health.is_error)
                result=await client.call_tool('sih_items',{'section':'research','category':'papers','stage':'analysis','keyword':'医学'})
                self.assertEqual(1,result.structured_content['matched_count'])
                self.assertEqual('fixture',result.structured_content['items'][0]['id'])
                empty=await client.call_tool('sih_items',{'section':'industry'})
                self.assertEqual([],empty.structured_content['items'])
                invalid=await client.call_tool('sih_items',{'limit':999})
                self.assertTrue(invalid.is_error)
                failed=await client.call_tool('sih_briefing')
                self.assertTrue(failed.is_error)
                self.assertFalse((await client.call_tool('sih_health')).is_error)

if __name__=='__main__':unittest.main()
