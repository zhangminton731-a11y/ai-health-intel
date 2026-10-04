"""Source-authored FDA press release excerpts for regulatory editorial judgments."""
import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from .core import text, write_json_atomic


class FdaRelease(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.paragraph = None
        self.paragraphs = []
        self.done = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.done: return
        if tag == 'div' and (self.depth or attrs.get('role') == 'main'): self.depth += 1
        if tag == 'p' and self.depth: self.paragraph = []

    def handle_data(self, data):
        if self.paragraph is not None: self.paragraph.append(data)

    def handle_endtag(self, tag):
        if tag == 'p' and self.paragraph is not None:
            value = text(''.join(self.paragraph))
            if value: self.paragraphs.append(value)
            self.paragraph = None
        if tag == 'div' and self.depth:
            self.depth -= 1
            if not self.depth: self.done = True


def enrich_fda_release(item, cache_dir):
    url = item.get('url', '')
    parts = urlsplit(url)
    if parts.hostname != 'www.fda.gov' or not parts.path.startswith('/news-events/press-announcements/'):
        return {'kind': 'fda_release', 'status': 'skipped'}
    url = 'https://www.fda.gov' + parts.path
    cache = cache_dir / ('fda-' + hashlib.sha256(url.encode()).hexdigest() + '.json') if cache_dir else None
    try:
        if cache and cache.exists():
            stored = json.loads(cache.read_text(encoding='utf-8'))
            if stored.get('url') == url and stored.get('summary'):
                item.update(summary=stored['summary'], summary_source=url, summary_kind='source_excerpt')
                return {'kind': 'fda_release', 'status': 'cached'}
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10) as response:
            if urlsplit(response.geturl()).hostname != 'www.fda.gov': raise ValueError('Unexpected host')
            body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024: raise ValueError('Oversized page')
        parser = FdaRelease(); parser.feed(body.decode('utf-8', errors='replace'))
        summary = ' '.join(parser.paragraphs)[:12000]
        if len(summary) < 200: raise ValueError('No release body')
        if cache: write_json_atomic(cache, {'url': url, 'summary': summary})
        item.update(summary=summary, summary_source=url, summary_kind='source_excerpt')
        return {'kind': 'fda_release', 'status': 'ok'}
    except (OSError, ValueError):
        return {'kind': 'fda_release', 'status': 'unavailable'}
