"""Read source-authored Nature abstracts; never synthesize missing evidence."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from .core import write_json_atomic


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.abstract = ''
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name', '').lower() == 'dc.description':
            self.abstract = attrs.get('content', '').strip()


def enrich_summary(item: dict, cache_dir: Path | None, *, allow_fetch=True) -> dict:
    url = item.get('url') or ''
    parts = urlsplit(url)
    if item.get('summary') or parts.scheme != 'https' or parts.hostname != 'www.nature.com' or not parts.path.startswith('/articles/'):
        return {'kind':'article_metadata', 'status':'skipped'}
    cache = cache_dir / (hashlib.sha256(url.encode()).hexdigest()+'.json') if cache_dir else None
    summary = ''
    if cache and cache.exists():
        try:
            stored = json.loads(cache.read_text(encoding='utf-8'))
            if isinstance(stored, dict) and stored.get('url') == url and isinstance(stored.get('summary'), str) and len(stored['summary']) >= 80:
                summary = stored['summary']
        except (OSError, ValueError, TypeError):
            pass
    cached = bool(summary)
    if not summary and not allow_fetch:
        return {'kind':'article_metadata', 'status':'deferred'}
    if not summary:
        try:
            request = Request(url, headers={'User-Agent':'SIH-metadata/1.0'})
            with urlopen(request, timeout=10) as response:
                if urlsplit(response.geturl()).hostname != 'www.nature.com':
                    return {'kind':'article_metadata', 'status':'unavailable'}
                body = response.read(2*1024*1024+1)
            if len(body) > 2*1024*1024:
                return {'kind':'article_metadata', 'status':'unavailable'}
            parser = Metadata(); parser.feed(body.decode('utf-8', errors='replace'))
            summary = parser.abstract
            if len(summary) < 80 or summary.casefold() == str(item.get('title','')).casefold():
                return {'kind':'article_metadata', 'status':'unavailable'}
            if cache:
                write_json_atomic(cache, {'url':url, 'summary':summary})
        except (OSError, ValueError):
            return {'kind':'article_metadata', 'status':'unavailable'}
    item.update(summary=summary, summary_source=url)
    return {'kind':'article_metadata', 'status':'cached' if cached else 'ok'}
