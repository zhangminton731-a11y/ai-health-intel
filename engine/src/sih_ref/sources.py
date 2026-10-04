"""Public, authenticated, snapshot, author, and legacy source adapters."""

from __future__ import annotations

import csv
import email
import email.policy
import imaplib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from .core import normalize_url, normalize_date, text
from .article_metadata import enrich_summary
from .dive_metadata import enrich_dive_brief
from .official_metadata import enrich_fda_release
from .cms_facts import collect_fact_sheets
from .rss_fetch import FeedFetchError, fetch_feed


USER_AGENT = "ScientificInformationHubReference/0.1 (+https://github.com/mengsj08/June_Public)"


@dataclass
class SourceResult:
    """One adapter result before normalization and assembly."""

    source_id: str
    status: str
    items: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


def _request(url: str, *, timeout: int = 20, retries: int = 2) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, */*"})
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL comes from explicit config
                return response.read()
        except Exception as exc:  # network failures are surfaced in SourceResult
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"request failed after {retries + 1} attempts: {type(last_error).__name__}") from None


def _request_json(url: str, *, timeout: int = 20) -> Any:
    return json.loads(_request(url, timeout=timeout).decode("utf-8"))


def _request_text(url: str, *, timeout: int = 20) -> str:
    return _request(url, timeout=timeout).decode("utf-8", errors="replace")


def _resolve_path(source: Mapping[str, Any], key: str, base_dir: Path) -> Path:
    raw = text(source.get(key))
    if not raw:
        raise ValueError(f"source {source.get('id')} requires {key}")
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (base_dir / path).resolve()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            records.append(parsed)
    return records


def _fixture_jsonl(source: Mapping[str, Any], base_dir: Path, _: date) -> SourceResult:
    path = _resolve_path(source, "path", base_dir)
    return SourceResult(text(source.get("id")), "ok", _read_jsonl(path), [{"kind": "local_fixture", "path": path.name}])


def _pubmed_query(source: Mapping[str, Any], _: Path, as_of: date) -> SourceResult:
    query = text(source.get("query"))
    if not query:
        journals = [text(value) for value in source.get("journals") or [] if text(value)]
        query = " OR ".join(f'"{journal}"[jour]' for journal in journals)
    if not query:
        raise ValueError("PubMed source requires query or journals")
    lookback = int(source.get("lookback_days") or 14)
    start = as_of - timedelta(days=lookback)
    query = f"({query}) AND ({start.isoformat()}:{as_of.isoformat()}[dp])"
    retmax = min(100, max(1, int(source.get("max_results") or 20)))
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urlencode(
        {"db": "pubmed", "retmode": "json", "retmax": retmax, "term": query, "sort": "pub date"}
    )
    search = _request_json(search_url)
    ids = [text(value) for value in ((search.get("esearchresult") or {}).get("idlist") or []) if text(value)]
    if not ids:
        return SourceResult(text(source.get("id")), "ok_no_updates", [], [{"kind": "pubmed_esearch", "count": 0}])
    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urlencode(
        {"db": "pubmed", "retmode": "json", "id": ",".join(ids)}
    )
    summary = _request_json(summary_url)
    result_map = summary.get("result") or {}
    items: list[dict[str, Any]] = []
    for pmid in ids:
        entry = result_map.get(pmid) or {}
        doi = ""
        for article_id in entry.get("articleids") or []:
            if text(article_id.get("idtype")).lower() == "doi":
                doi = text(article_id.get("value"))
                break
        items.append(
            {
                "pmid": pmid,
                "doi": doi,
                "upstream_id": pmid,
                "title": entry.get("title"),
                "authors": [author.get("name") for author in entry.get("authors") or [] if author.get("name")],
                "published_at": entry.get("pubdate"),
                "summary": entry.get("sorttitle") or "",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "tags": source.get("tags") or [],
            }
        )
    return SourceResult(text(source.get("id")), "ok", items, [{"kind": "pubmed_esearch", "count": len(items)}])


def _europe_pmc(source: Mapping[str, Any], _: Path, as_of: date) -> SourceResult:
    """A declared journal's indexed abstract channel, never a keyword-curated sample."""
    issn = text(source.get('journal_issn'))
    if not re.fullmatch(r'\d{4}-\d{3}[\dX]', issn):
        raise ValueError('Journal ISSN required')
    start = as_of - timedelta(days=int(source.get('lookback_days', 90)))
    query = f'ISSN:{issn} AND HAS_ABSTRACT:Y AND FIRST_PDATE:[{start.isoformat()} TO {as_of.isoformat()}] sort_date:y'
    url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({
        'query': query, 'format': 'json', 'resultType': 'core',
        'pageSize': min(100, max(10, int(source.get('max_results', 30))))})
    data = _request_json(url)
    rows = []
    for entry in data.get('resultList', {}).get('result', []):
        journal = entry.get('journalInfo', {}).get('journal', {})
        if issn not in (journal.get('issn'), journal.get('essn')):
            raise ValueError('Unexpected journal in indexed channel')
        doi, pmid = text(entry.get('doi')), text(entry.get('pmid'))
        rows.append({'title': entry.get('title'), 'summary': entry.get('abstractText', ''),
                     'published_at': entry.get('firstPublicationDate'), 'doi': doi, 'pmid': pmid,
                     'upstream_id': entry.get('id'), 'authors': entry.get('authorString', ''),
                     'url': 'https://doi.org/' + doi if doi else 'https://europepmc.org/article/MED/' + pmid,
                     'summary_source': 'https://europepmc.org/article/' + text(entry.get('source')) + '/' + text(entry.get('id'))})
    return SourceResult(text(source.get('id')), 'ok' if rows else 'ok_no_updates', rows,
                        [{'kind': 'europe_pmc', 'query': query, 'count': len(rows), 'hit_count': data.get('hitCount')}])


def _arxiv(source: Mapping[str, Any], _: Path, __: date) -> SourceResult:
    query = text(source.get("query") or "all:artificial intelligence")
    max_results = min(100, max(1, int(source.get("max_results") or 20)))
    url = "https://export.arxiv.org/api/query?" + urlencode(
        {"search_query": query, "start": 0, "max_results": max_results, "sortBy": "submittedDate", "sortOrder": "descending"}
    )
    root = ET.fromstring(_request_text(url))
    atom = "{http://www.w3.org/2005/Atom}"
    items: list[dict[str, Any]] = []
    for entry in root.findall(f"{atom}entry"):
        entry_id = text(entry.findtext(f"{atom}id"))
        arxiv_id = entry_id.rsplit("/", 1)[-1]
        authors = [text(author.findtext(f"{atom}name")) for author in entry.findall(f"{atom}author")]
        doi = text(entry.findtext("{http://arxiv.org/schemas/atom}doi"))
        items.append(
            {
                "arxiv_id": arxiv_id,
                "doi": doi,
                "upstream_id": arxiv_id,
                "title": entry.findtext(f"{atom}title"),
                "summary": entry.findtext(f"{atom}summary"),
                "published_at": entry.findtext(f"{atom}published"),
                "authors": authors,
                "url": entry_id,
                "tags": source.get("tags") or [],
            }
        )
    status = "ok" if items else "ok_no_updates"
    return SourceResult(text(source.get("id")), status, items, [{"kind": "arxiv_atom", "count": len(items)}])


class FeedImage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.url = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'img' and not self.url:
            self.url = dict(attrs).get('src', '')


def feed_image(entry, base):
    for node in entry.iter():
        tag = node.tag.rsplit('}', 1)[-1]
        media = node.tag.startswith('{http://search.yahoo.com/mrss/}')
        media_image = media and (tag == 'thumbnail' or (tag == 'content' and node.get('medium', 'image') == 'image' and node.get('type', 'image/').startswith('image/')))
        if media_image or (tag in ('enclosure', 'link') and node.get('type', '').startswith('image/')):
            candidate = node.get('url') or node.get('href')
            url = normalize_url(urljoin(base, candidate)) if candidate else ''
            if url: return url
    parser = FeedImage()
    for node in entry.iter():
        if node.tag.rsplit('}', 1)[-1] in ('description', 'summary', 'content', 'encoded'):
            parser.feed(node.text or '')
    return normalize_url(urljoin(base, parser.url)) if parser.url else ''


def _rss(source: Mapping[str, Any], _: Path, as_of: date) -> SourceResult:
    url = normalize_url(source.get("url"))
    if not url:
        raise ValueError("RSS source requires an http(s) url")
    cache_dir = source.get('_cache_dir')
    root, checks = fetch_feed(url, USER_AGENT, cache_path=cache_dir/'feed.json' if cache_dir else None)
    items: list[dict[str, Any]] = []
    rss_ns = "{http://purl.org/rss/1.0/}"
    rss_items = root.findall(".//item") + root.findall(f".//{rss_ns}item")
    if rss_items:
        for entry in rss_items:
            def field(name: str) -> str | None:
                node = entry.find(name)
                if node is None: node = entry.find(f"{rss_ns}{name}")
                return ''.join(node.itertext()).strip() if node is not None else None

            items.append(
                {
                    "upstream_id": field("guid") or field("link"),
                    "title": field("title"),
                    "summary": (entry.findtext('{http://purl.org/rss/1.0/modules/content/}encoded')
                                if source.get('use_feed_content') else None) or field("description"),
                    "image_url": feed_image(entry, field('link') or url),
                    "published_at": field("pubDate") or entry.findtext("{http://purl.org/dc/elements/1.1/}date"),
                    "url": field("link"),
                    "tags": source.get("tags") or [],
                }
            )
    else:
        atom = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f".//{atom}entry"):
            link_node = next((link for link in entry.findall(f"{atom}link")
                              if link.get("rel", "alternate") == "alternate"), None)
            link = link_node.get("href") if link_node is not None else ""
            items.append(
                {
                    "upstream_id": entry.findtext(f"{atom}id") or link,
                    "title": entry.findtext(f"{atom}title"),
                    "summary": entry.findtext(f"{atom}summary") or entry.findtext(f"{atom}content"),
                    "image_url": feed_image(entry, link or url),
                    "published_at": entry.findtext(f"{atom}published") or entry.findtext(f"{atom}updated"),
                    "url": link,
                    "tags": source.get("tags") or [],
                }
            )
    max_results = min(100, max(1, int(source.get("max_results") or 20)))
    items = items[:max_results]
    if source.get('article_metadata') == 'dive_brief':
        for item in items:
            published = normalize_date(item.get('published_at'))
            if published and 0 <= (as_of-date.fromisoformat(published)).days <= 90:
                checks.append(enrich_dive_brief(item, source.get('_metadata_cache_dir', cache_dir)))
    if source.get('article_metadata') == 'fda_release':
        for item in items:
            published = normalize_date(item.get('published_at'))
            if published and 0 <= (as_of-date.fromisoformat(published)).days <= 90:
                checks.append(enrich_fda_release(item, source.get('_metadata_cache_dir', cache_dir)))
    if source.get('article_metadata') == 'nature':
        attempted = 0
        for item in items:
            published = normalize_date(item.get('published_at'))
            if published and 0 <= (as_of-date.fromisoformat(published)).days <= 10 and not item.get('summary'):
                check = enrich_summary(item, source.get('_metadata_cache_dir', cache_dir), allow_fetch=attempted < 8)
                attempted += check['status'] in ('ok', 'unavailable')
                checks.append(check)
    checks.append({"kind": "rss_atom", "count": len(items)})
    return SourceResult(text(source.get("id")), "ok" if items else "ok_no_updates", items, checks)


def _hacker_news(source: Mapping[str, Any], _: Path, __: date) -> SourceResult:
    limit = min(100, max(1, int(source.get("scan_limit") or 30)))
    max_results = min(20, max(1, int(source.get("max_results") or 5)))
    keywords = [text(value).lower() for value in source.get("keywords") or [] if text(value)]
    story_ids = _request_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:limit]
    items: list[dict[str, Any]] = []
    for story_id in story_ids:
        entry = _request_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json") or {}
        title = text(entry.get("title"))
        if keywords and not any(keyword in title.lower() for keyword in keywords):
            continue
        items.append(
            {
                "upstream_id": story_id,
                "title": title,
                "summary": f"Hacker News community signal; score {entry.get('score', 0)}.",
                "published_at": datetime_from_epoch(entry.get("time")),
                "url": entry.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                "tags": ["community-signal", *(source.get("tags") or [])],
            }
        )
        if len(items) >= max_results:
            break
    return SourceResult(text(source.get("id")), "ok" if items else "ok_no_updates", items, [{"kind": "hn_firebase", "count": len(items)}])


def datetime_from_epoch(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _openalex_author(source: Mapping[str, Any], _: Path, as_of: date) -> SourceResult:
    author_ids = [text(value) for value in source.get("author_ids") or [] if text(value)]
    if not author_ids:
        raise ValueError("OpenAlex author source requires author_ids")
    lookback = int(source.get("lookback_days") or 30)
    max_results = min(100, max(1, int(source.get("max_results") or 20)))
    items: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for author_id in author_ids:
        filter_value = f"authorships.author.id:{author_id},from_publication_date:{(as_of - timedelta(days=lookback)).isoformat()}"
        url = "https://api.openalex.org/works?" + urlencode({"filter": filter_value, "per-page": max_results, "sort": "publication_date:desc"})
        payload = _request_json(url)
        results = payload.get("results") or []
        checks.append({"kind": "openalex_author", "author_id": author_id, "count": len(results)})
        for work in results:
            authors = [
                text(((authorship.get("author") or {}).get("display_name")))
                for authorship in work.get("authorships") or []
                if text(((authorship.get("author") or {}).get("display_name")))
            ]
            ids = work.get("ids") or {}
            items.append(
                {
                    "upstream_id": work.get("id"),
                    "doi": ids.get("doi") or work.get("doi"),
                    "title": work.get("display_name") or work.get("title"),
                    "summary": "",
                    "published_at": work.get("publication_date"),
                    "authors": authors,
                    "url": ids.get("doi") or work.get("id"),
                    "tags": ["author-watch", *(source.get("tags") or [])],
                }
            )
    return SourceResult(text(source.get("id")), "ok" if items else "ok_no_updates", items, checks)


def _email_directory(source: Mapping[str, Any], base_dir: Path, _: date) -> SourceResult:
    directory = _resolve_path(source, "path", base_dir)
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.eml")):
        message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
        body = message.get_body(preferencelist=("plain", "html"))
        body_text = text(body.get_content()) if body else ""
        url_match = re.search(r"https?://[^\s<>'\"]+", body_text)
        items.append(
            {
                "upstream_id": message.get("Message-ID") or path.name,
                "title": message.get("Subject") or "Untitled newsletter",
                "summary": body_text[:800],
                "published_at": message.get("Date"),
                "authors": [message.get("From") or ""],
                "url": url_match.group(0).rstrip(".,)") if url_match else "",
                "tags": ["email", *(source.get("tags") or [])],
            }
        )
    return SourceResult(text(source.get("id")), "ok" if items else "ok_no_updates", items, [{"kind": "eml_directory", "count": len(items)}])


def _imap(source: Mapping[str, Any], _: Path, __: date) -> SourceResult:
    host = text(source.get("host"))
    username_env = text(source.get("username_env"))
    password_env = text(source.get("password_env"))
    username = os.environ.get(username_env, "")
    password = os.environ.get(password_env, "")
    if not host or not username_env or not password_env:
        raise ValueError("IMAP source requires host, username_env, and password_env")
    if not username or not password:
        raise ValueError("IMAP credential environment variables are not set")
    mailbox = text(source.get("mailbox") or "INBOX")
    max_results = min(50, max(1, int(source.get("max_results") or 10)))
    items: list[dict[str, Any]] = []
    with imaplib.IMAP4_SSL(host, int(source.get("port") or 993)) as client:
        client.login(username, password)
        client.select(mailbox, readonly=True)
        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("IMAP search failed")
        ids = (data[0] or b"").split()[-max_results:]
        for message_id in reversed(ids):
            fetch_status, payload = client.fetch(message_id, "(RFC822)")
            if fetch_status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            message = email.message_from_bytes(payload[0][1], policy=email.policy.default)
            body = message.get_body(preferencelist=("plain", "html"))
            body_text = text(body.get_content()) if body else ""
            url_match = re.search(r"https?://[^\s<>'\"]+", body_text)
            items.append(
                {
                    "upstream_id": message.get("Message-ID") or message_id.decode(),
                    "title": message.get("Subject") or "Untitled newsletter",
                    "summary": body_text[:800],
                    "published_at": message.get("Date"),
                    "authors": [message.get("From") or ""],
                    "url": url_match.group(0).rstrip(".,)") if url_match else "",
                    "tags": ["email", *(source.get("tags") or [])],
                }
            )
    return SourceResult(text(source.get("id")), "ok" if items else "ok_no_updates", items, [{"kind": "imap_readonly", "count": len(items)}])


def _json_export(source: Mapping[str, Any], base_dir: Path, _: date) -> SourceResult:
    path = _resolve_path(source, "path", base_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError(f"{path} must contain a list or records list")
    mapping = source.get("field_map") or {}
    items: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        fields = record.get("fields") if isinstance(record.get("fields"), dict) else record
        items.append(_map_record(fields, mapping, fallback_id=f"{path.name}:{index}"))
    return SourceResult(text(source.get("id")), "ok" if items else "ok_no_updates", items, [{"kind": source.get("kind"), "count": len(items)}])


def _stork(source: Mapping[str, Any], base_dir: Path, _: date) -> SourceResult:
    path = _resolve_path(source, "path", base_dir)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.DictReader(stream))
    else:
        records = _read_jsonl(path)
    mapping = source.get("field_map") or {}
    items = [_map_record(record, mapping, fallback_id=f"{path.name}:{index}") for index, record in enumerate(records)]
    return SourceResult(text(source.get("id")), "ok" if items else "ok_no_updates", items, [{"kind": "stork_inbox", "count": len(items)}])


def _legacy(source: Mapping[str, Any], base_dir: Path, _: date) -> SourceResult:
    path = _resolve_path(source, "path", base_dir)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.DictReader(stream))
    else:
        records = _read_jsonl(path)
    mapping = source.get("field_map") or {}
    items = [_map_record(record, mapping, fallback_id=f"legacy:{index}") for index, record in enumerate(records)]
    for item in items:
        item["tags"] = ["legacy-compat", *(item.get("tags") or [])]
    return SourceResult(text(source.get("id")), "ok" if items else "ok_no_updates", items, [{"kind": "legacy_compat", "count": len(items)}])


def _map_record(record: Mapping[str, Any], mapping: Mapping[str, Any], *, fallback_id: str) -> dict[str, Any]:
    aliases = {
        "upstream_id": ["upstream_id", "id", "record_id"],
        "title": ["title", "name", "subject"],
        "summary": ["summary", "abstract", "description", "content"],
        "published_at": ["published_at", "published", "date", "publication_date"],
        "url": ["url", "link", "canonical_url"],
        "authors": ["authors", "author", "from"],
        "doi": ["doi"],
        "pmid": ["pmid"],
        "arxiv_id": ["arxiv_id"],
        "tags": ["tags", "topic_tags"],
    }
    result: dict[str, Any] = {}
    for target, defaults in aliases.items():
        configured = text(mapping.get(target))
        keys = [configured] if configured else defaults
        result[target] = next((record.get(key) for key in keys if key in record), "")
    result["upstream_id"] = result.get("upstream_id") or fallback_id
    return result


ADAPTERS: dict[str, Callable[[Mapping[str, Any], Path, date], SourceResult]] = {
    "cms_facts": lambda source, _, as_of: SourceResult(text(source.get('id')), 'ok', collect_fact_sheets(source, as_of), [{'kind': 'cms_facts'}]),
    "fixture_jsonl": _fixture_jsonl,
    "europe_pmc": _europe_pmc,
    "pubmed": _pubmed_query,
    "pubmed_journals": _pubmed_query,
    "arxiv": _arxiv,
    "rss": _rss,
    "hacker_news": _hacker_news,
    "openalex_author": _openalex_author,
    "email_directory": _email_directory,
    "imap": _imap,
    "feishu_export": _json_export,
    "browser_snapshot": _json_export,
    "stork_inbox": _stork,
    "legacy_jsonl": _legacy,
}


NETWORK_SOURCE_KINDS = {"cms_facts", "europe_pmc", "pubmed", "pubmed_journals", "arxiv", "rss", "hacker_news", "openalex_author", "imap"}


def collect_source(source: Mapping[str, Any], *, base_dir: Path, live: bool, as_of: date) -> SourceResult:
    """Run one explicit adapter without expanding beyond its configured boundary."""
    source_id = text(source.get("id"))
    kind = text(source.get("kind"))
    if not source.get("enabled", False):
        return SourceResult(source_id, "inactive", checks=[{"kind": kind, "reason": "disabled_by_config"}])
    if kind not in ADAPTERS:
        return SourceResult(source_id, "failed", error=f"unknown source kind: {kind}")
    if kind in NETWORK_SOURCE_KINDS and not live:
        return SourceResult(source_id, "inactive", checks=[{"kind": kind, "reason": "live_flag_required"}])
    try:
        return ADAPTERS[kind](source, base_dir, as_of)
    except FeedFetchError as exc:
        return SourceResult(source_id, "failed", checks=exc.checks, error=str(exc))
    except Exception as exc:
        return SourceResult(source_id, "failed", error=f"{type(exc).__name__}: {text(exc)}")
