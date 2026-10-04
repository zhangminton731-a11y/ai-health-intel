"""Read publishers' public Dive Brief summaries, without scraping entire articles."""
import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from .core import text, write_json_atomic

HOSTS = {'www.healthcaredive.com', 'www.biopharmadive.com', 'www.medtechdive.com'}


class DiveBrief(HTMLParser):
    def __init__(self):
        super().__init__()
        self.heading = None
        self.ready = False
        self.depth = 0
        self.parts = []
        self.done = False

    def handle_starttag(self, tag, attrs):
        if self.done: return
        if tag in ('h2', 'h3'): self.heading = []
        if tag == 'ul' and (self.ready or self.depth): self.depth += 1
        if tag == 'li' and self.depth: self.parts.append(' ')

    def handle_data(self, data):
        if self.done: return
        if self.heading is not None: self.heading.append(data)
        if self.depth: self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in ('h2', 'h3') and self.heading is not None:
            self.ready = text(''.join(self.heading)).lower() == 'dive brief:'
            self.heading = None
        if tag == 'ul' and self.depth:
            self.depth -= 1
            if self.depth == 0: self.done = True


def enrich_dive_brief(item, cache_dir):
    url = item.get('url', '')
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in HOSTS:
        return {'kind': 'dive_brief', 'status': 'skipped'}
    cache = cache_dir / ('dive-' + hashlib.sha256(url.encode()).hexdigest() + '.json') if cache_dir else None
    summary = ''
    if cache and cache.exists():
        stored = json.loads(cache.read_text(encoding='utf-8'))
        if stored.get('url') == url: summary = stored.get('summary', '')
    cached = bool(summary)
    if not summary:
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10) as response:
                if urlsplit(response.geturl()).hostname != parts.hostname:
                    raise ValueError('Unexpected article host')
                body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024: raise ValueError('Oversized page')
            parser = DiveBrief()
            parser.feed(body.decode('utf-8', errors='replace'))
            summary = text(''.join(parser.parts))
            if not parser.done or not 200 <= len(summary) <= 6000:
                return {'kind': 'dive_brief', 'status': 'unavailable'}
            if cache: write_json_atomic(cache, {'url': url, 'summary': summary})
        except (OSError, ValueError):
            return {'kind': 'dive_brief', 'status': 'unavailable'}
    item.update(summary=summary, summary_source=url)
    return {'kind': 'dive_brief', 'status': 'cached' if cached else 'ok'}
