"""Exercise exported packages over loopback HTTP and probe the public deployment.

Run with the Python environment from integrations/mcp/requirements.txt.
This does not install a Skill in a user's client or change their MCP settings.
"""
import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import time
import argparse
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import xml.etree.ElementTree as ET
import zipfile

from jsonschema import Draft202012Validator, FormatChecker
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'output/site'
PUBLIC = 'https://zhangminton731-a11y.github.io/ai-health-intel/'
PATHS = ['api/v1/health.json', 'api/v1/items.json', 'api/v1/briefing.json',
         'feed.xml', 'sih-intel.zip', 'sih-intel/README.md', 'sih-mcp.zip',
         'sih-mcp/README.md', 'openapi.json', 'llms.txt']
RECOVERIES = []


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if not self.path.startswith('/ai-health-intel/'):
            self.send_error(404)
            return
        self.path = self.path.removeprefix('/ai-health-intel')
        super().do_GET()

    def log_message(self, *args):
        pass


def read(base, path):
    for attempt in range(2):
        try:
            with urlopen(base + path, timeout=15) as response:
                result = response.read()
            if attempt: RECOVERIES.append(base + path)
            return result
        except HTTPError:
            raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt: raise
            time.sleep(1)


async def verify_local(base):
    blobs = {path: read(base, path) for path in PATHS}
    snapshots = {name: json.loads(blobs[f'api/v1/{name}.json']) for name in ('health', 'items', 'briefing')}
    spec = json.loads(blobs['openapi.json'])
    for path, operation in spec['paths'].items():
        schema = operation['get']['responses']['200']['content']['application/json']['schema']
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(json.loads(blobs[path.lstrip('/')]))
    items = snapshots['items']['items']
    expected = {item['id'] for item in items}
    feed = ET.fromstring(blobs['feed.xml'])
    assert feed.tag == 'rss' and feed.get('version') == '2.0'
    entries = feed.findall('./channel/item')
    assert {entry.findtext('guid') for entry in entries} == expected
    for entry in entries:
        assert entry.findtext('title') and entry.findtext('link').startswith(('https://', 'http://'))
        assert parsedate_to_datetime(entry.findtext('pubDate')).tzinfo
    skill = zipfile.ZipFile(BytesIO(blobs['sih-intel.zip']))
    assert set(skill.namelist()) == {'sih-intel/SKILL.md', 'sih-intel/README.md'}
    definition = skill.read('sih-intel/SKILL.md').decode('utf-8').replace('\r\n', '\n')
    assert definition.startswith('---\nname: sih-intel\n')
    assert definition == (ROOT/'skills/sih-intel/SKILL.md').read_text(encoding='utf-8')
    assert PUBLIC in definition and all(f'api/v1/{name}.json' in definition for name in snapshots)
    package = zipfile.ZipFile(BytesIO(blobs['sih-mcp.zip']))
    assert set(package.namelist()) == {'sih-mcp/server.py', 'sih-mcp/README.md', 'sih-mcp/requirements.txt'}
    with tempfile.TemporaryDirectory() as folder:
        for name in package.namelist():
            # GitHub Linux builds use LF; Windows checkouts may use CRLF.
            assert package.read(name).decode('utf-8').replace('\r\n', '\n') == (ROOT/'integrations/mcp'/Path(name).name).read_text(encoding='utf-8')
            package.extract(name, folder)
        # Exercise the downloaded server unchanged; only route its test requests
        # to this local HTTP copy of the publication, not a stub loader.
        worker = ('import importlib.util,sys; '
                  'spec=importlib.util.spec_from_file_location("downloaded_sih",sys.argv[1]); '
                  'module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); '
                  'module.BASE=sys.argv[2]; module.create_server().run(transport="stdio")')
        params = StdioServerParameters(command=sys.executable,
                  args=['-c', worker, str(Path(folder)/'sih-mcp/server.py'), base])
        async with Client(params) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert names == {'sih_health', 'sih_items', 'sih_briefing'}
            health = await client.call_tool('sih_health')
            assert not health.is_error and health.structured_content['generated_at'] == snapshots['health']['generated_at']
            result = await client.call_tool('sih_items', {'section': 'research', 'category': 'papers', 'limit': 30})
            assert not result.is_error
            assert all('papers' in row['categories'].get('research', []) for row in result.structured_content['items'])
            assert {row['id'] for row in result.structured_content['items']}.issubset(expected)
            briefing = await client.call_tool('sih_briefing')
            assert not briefing.is_error and briefing.structured_content['text'] == snapshots['briefing']['text']
            empty = await client.call_tool('sih_items', {'keyword': 'no-match-verification-73528'})
            assert not empty.is_error and empty.structured_content['items'] == []
    return {'api': 'PASS: three HTTP GETs and OpenAPI schemas',
            'rss': f'PASS: RSS 2.0 dates, links and {len(entries)} matching items',
            'skill': 'PASS: ZIP download, exact files, metadata, instructions and data reads; client installation/trigger NOT tested',
            'mcp': f'PASS: downloaded package, real stdio discovery and all three tools reading {base}',
            'research_papers_returned': len(result.structured_content['items'])}


async def verify_public():
    results = []
    for path in PATHS:
        try:
            body = await asyncio.to_thread(read, PUBLIC, path)
            results.append({'path': path, 'status': 200, 'bytes': len(body)})
        except HTTPError as exc:
            results.append({'path': path, 'status': exc.code})
        except Exception as exc:
            results.append({'path': path, 'error': type(exc).__name__})
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT/'integrations/mcp/server.py')])
    async with Client(params) as client:
        result = await client.call_tool('sih_health')
        live_mcp = {'tool': 'sih_health', 'is_error': result.is_error}
    return results, live_mcp


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--public-only', action='store_true')
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--output', default='output/access-verification.json')
    args = parser.parse_args()
    if args.public_only:
        rounds = []
        for attempt in range(max(1, min(args.rounds, 5))):
            try:
                result = await verify_local(PUBLIC)
                rounds.append({'round': attempt+1, 'passed': True, **result})
            except Exception as exc:
                rounds.append({'round': attempt+1, 'passed': False, 'error': f'{type(exc).__name__}: {exc}'})
        report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'rounds': rounds,
                  'recovered_http_requests': RECOVERIES, 'skill_client_installation_tested': False}
        (ROOT/args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return int(not all(row['passed'] for row in rounds))
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(SITE)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        local = await verify_local(f'http://127.0.0.1:{server.server_port}/ai-health-intel/')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    public, mcp = await verify_public()
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'local': local,
              'public': public, 'public_mcp': mcp,
              'public_resources_reachable': all(row.get('status') == 200 for row in public),
              'skill_client_installation_tested': False}
    (ROOT/'output/access-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.exit(asyncio.run(main()) or 0)
