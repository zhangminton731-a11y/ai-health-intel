"""Original CMS publication dates and source-authored policy excerpts."""
import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from .core import normalize_date, text, write_json_atomic


class PublicBody(HTMLParser):
    def __init__(self):
        super().__init__(); self.depth=0; self.parts=[]; self.script=None; self.published=''

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='script' and attrs.get('type')=='application/ld+json': self.script=[]
        classes=attrs.get('class','').split()
        if tag=='div' and ('field--name-body' in classes or self.depth): self.depth+=1
        if tag in ('p','li','br') and self.depth: self.parts.append(' ')

    def handle_data(self, data):
        if self.script is not None: self.script.append(data)
        elif self.depth: self.parts.append(data)

    def handle_endtag(self, tag):
        if tag=='div' and self.depth: self.depth-=1
        if tag=='script' and self.script is not None:
            try:
                data=json.loads(''.join(self.script))
                rows=data if isinstance(data,list) else data.get('@graph',[data])
                for row in rows:
                    if not isinstance(row,dict): continue
                    if row.get('datePublished'): self.published=normalize_date(row['datePublished'])
            except (ValueError,TypeError,AttributeError): pass
            self.script=None


def enrich_public_body(item, cache_dir):
    url=item.get('url','');host=urlsplit(url).hostname
    if host!='www.cms.gov' or urlsplit(url).scheme!='https': return {'kind':'public_body','status':'skipped'}
    cache=cache_dir/(hashlib.sha256(url.encode()).hexdigest()+'.json') if cache_dir else None
    try:
        saved=json.loads(cache.read_text(encoding='utf-8')) if cache and cache.exists() else {}
        if saved.get('url')!=url or not saved.get('summary') or not saved.get('published_at'):
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as response:
                if urlsplit(response.geturl()).hostname!=host: raise ValueError('Unexpected host')
                body=response.read(3*1024*1024+1)
            if len(body)>3*1024*1024: raise ValueError('Oversized page')
            parser=PublicBody();parser.feed(body.decode('utf-8','replace'))
            saved={'url':url,'summary':text(' '.join(parser.parts))[:12000],'published_at':parser.published}
            if len(saved['summary'])<80 or not saved['published_at']: raise ValueError('Missing original body or date')
            if cache:write_json_atomic(cache,saved)
        item.update(summary=saved['summary'],summary_source=url,summary_kind='source_excerpt')
        if saved.get('published_at'):item['published_at']=saved['published_at']
        return {'kind':'public_body','status':'ok'}
    except (OSError,ValueError):return {'kind':'public_body','status':'unavailable'}
