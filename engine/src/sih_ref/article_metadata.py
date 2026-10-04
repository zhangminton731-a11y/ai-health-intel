"""Read source-authored Nature abstracts; never synthesize missing evidence."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlencode
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
    summary_source = url
    if cache and cache.exists():
        try:
            stored = json.loads(cache.read_text(encoding='utf-8'))
            if isinstance(stored, dict) and stored.get('url') == url and isinstance(stored.get('summary'), str) and len(stored['summary']) >= 80:
                summary = stored['summary']
                summary_source = stored.get('summary_source', url)
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
                    raise ValueError('Unexpected metadata host')
                body = response.read(2*1024*1024+1)
            if len(body) > 2*1024*1024:
                raise ValueError('Metadata response too large')
            parser = Metadata(); parser.feed(body.decode('utf-8', errors='replace'))
            summary = parser.abstract
            if len(summary) < 80 or summary.casefold() == str(item.get('title','')).casefold():
                raise ValueError('No source abstract')
        except (OSError, ValueError):
            # Europe's public literature index can carry the publisher's abstract
            # when the article HTML is unavailable. Never substitute another DOI.
            summary = ''
            article_id = parts.path.removeprefix('/articles/')
            if re.fullmatch(r's[0-9]+-[0-9]+-[0-9]+-[a-z0-9]+', article_id):
                doi = '10.1038/' + article_id
                fallback = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({'query':'DOI:'+doi,'format':'json','resultType':'core'})
                try:
                    with urlopen(Request(fallback, headers={'User-Agent':'SIH-metadata/1.0'}), timeout=10) as response:
                        body = response.read(2*1024*1024+1)
                    if len(body) <= 2*1024*1024:
                        data = json.loads(body)
                        for row in data.get('resultList', {}).get('result', []):
                            abstract = row.get('abstractText', '')
                            if str(row.get('doi', '')).lower() == doi.lower() and isinstance(abstract, str) and len(abstract) >= 80:
                                summary, summary_source = abstract, fallback
                                break
                except (OSError, ValueError, AttributeError, TypeError):
                    pass
            if not summary:
                return {'kind':'article_metadata', 'status':'unavailable'}
        if cache:
            write_json_atomic(cache, {'url':url, 'summary':summary, 'summary_source':summary_source})
    item.update(summary=summary, summary_source=summary_source)
    return {'kind':'article_metadata', 'status':'cached' if cached else 'ok'}
