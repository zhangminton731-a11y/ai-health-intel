"""Compare anonymous Pages responses with the approved deployment checkout."""
from hashlib import sha256
from pathlib import Path
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from export_feeds import BASE_URL


def main():
    site = Path(__file__).resolve().parents[1] / 'output/site'
    required = ['index.html', 'api/v1/briefing.json', 'api/v1/health.json',
                'api/v1/items.json', 'api/v1/history.json', 'feed.xml']
    required += [path.relative_to(site).as_posix() for path in
                 sorted(site.glob('api/v1/archive/*.json')) + sorted(site.glob('reports/*/index.html'))]
    expected = {name: sha256((site / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                for name in required}
    revision = sys.argv[1]
    pending = dict(expected)
    for attempt in range(5):
        for name, digest in list(pending.items()):
            route = name.removesuffix('index.html') if name.endswith('/index.html') or name == 'index.html' else name
            request = Request(f'{BASE_URL}{route}?revision={revision}&attempt={attempt}',
                              headers={'Cache-Control': 'no-cache', 'User-Agent': 'SIH-pages-readback'})
            try:
                with urlopen(request, timeout=8) as response:
                    actual = sha256(response.read().replace(b'\r\n', b'\n')).hexdigest()
                if actual == digest:
                    del pending[name]
                    print(f'HTTP 200, matched {name}')
            except (URLError, TimeoutError):
                pass
        if not pending:
            print(f'Public Pages match checkout {revision}')
            return 0
        if attempt < 4:
            time.sleep(5)
    print('Public readback mismatch: ' + ', '.join(pending), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
