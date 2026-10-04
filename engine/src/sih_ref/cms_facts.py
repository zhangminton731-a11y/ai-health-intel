"""CMS's publisher-defined fact-sheet channel, with original article dates."""
from datetime import timedelta
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from .public_body import enrich_public_body


class FactSheetListing(HTMLParser):
    def __init__(self):
        super().__init__()
        self.heading = False
        self.link = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h3':
            self.heading = True
        if tag == 'a' and self.heading and attrs.get('href', '').startswith('/newsroom/fact-sheets/'):
            self.link = {'url': 'https://www.cms.gov' + attrs['href'], 'title': ''}

    def handle_data(self, value):
        if self.link is not None:
            self.link['title'] += value

    def handle_endtag(self, tag):
        if tag == 'a' and self.link is not None:
            self.items.append(self.link)
            self.link = None
        if tag == 'h3':
            self.heading = False


def collect_fact_sheets(source, as_of):
    items, seen = [], set()
    cutoff = (as_of - timedelta(days=90)).isoformat()
    # Two official listing pages cover the channel's latest consecutive sample.
    for page in range(2):
        url = 'https://www.cms.gov/newsroom/articles?items_per_page=50&page=' + str(page)
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
            body = response.read(3 * 1024 * 1024 + 1)
        if len(body) > 3 * 1024 * 1024:
            raise ValueError('Oversized CMS listing')
        parser = FactSheetListing()
        parser.feed(body.decode('utf-8', 'replace'))
        for row in parser.items:
            if row['url'] in seen:
                continue
            seen.add(row['url'])
            enrich_public_body(row, source.get('_metadata_cache_dir'))
            if not row.get('published_at') or row['published_at'] >= cutoff:
                items.append(row)
    if not seen:
        raise ValueError('CMS listing did not contain fact sheets')
    return items[:int(source.get('max_results', 30))]
