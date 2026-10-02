"""Fetch RSS with bounded retries and public, body-free diagnostics."""

from __future__ import annotations

import random
import socket
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 20
BASE_BACKOFF_SECONDS = 5
MAX_RETRY_WAIT_SECONDS = 60
MAX_FEED_BYTES = 5 * 1024 * 1024
FEED_ROOTS = {
    "rss",
    "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF",
    "{http://www.w3.org/2005/Atom}feed",
}


class FeedFetchError(Exception):
    """Only the classified error and allowlisted diagnostics may be published."""

    def __init__(self, checks: list[dict]) -> None:
        self.checks = checks
        self.code = checks[-1]["error_code"]
        super().__init__(f"RSS {self.code} after {len(checks)} attempt(s)")


def public_url(url: str) -> str:
    """Drop credentials, queries and fragments from configured public feed URLs."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        try:
            deadline = parsedate_to_datetime(value)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            return max(0, (deadline - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def response_metadata(response: object) -> dict:
    # Never retain headers wholesale, exception messages, or response snippets.
    return {
        "http_status": response.status,
        "content_type": response.headers.get_content_type(),
        "final_url": public_url(response.geturl()),
    }


def parse_feed(body: bytes, check: dict) -> ET.Element | None:
    prefix = body.lstrip()[:256].lower()
    if prefix.startswith((b"<!doctype html", b"<html")):
        check.update(response_kind="html", error_code="non_feed")
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        check.update(
            response_kind="invalid_xml",
            error_code="invalid_xml",
            parse_line=exc.position[0],
            parse_column=exc.position[1],
        )
        return None
    if root.tag not in FEED_ROOTS:
        check.update(response_kind="non_feed", error_code="non_feed")
        return None
    check.update(response_kind="feed", error_code=None)
    return root


def fetch_feed(url: str, user_agent: str) -> tuple[ET.Element, list[dict]]:
    """One retry loop covers transport AND parsing; never multiply retries."""
    checks = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        check = {"kind": "rss_fetch", "attempt": attempt}
        start = time.monotonic()
        root = None
        retryable = True
        retry_after = None
        request = Request(url, headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        })
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                check.update(response_metadata(response))
                body = response.read(MAX_FEED_BYTES + 1)
                check["bytes_read"] = len(body)
            if len(body) > MAX_FEED_BYTES:
                check["error_code"] = "response_too_large"
                retryable = False
            else:
                root = parse_feed(body, check)
        except HTTPError as exc:
            check.update(response_metadata(exc))
            status = exc.code
            if status == 429:
                check["error_code"] = "rate_limited"
            elif status >= 500:
                check["error_code"] = "server_error"
            else:
                check["error_code"] = "http_error"
            retryable = status in (408, 429) or status >= 500
            retry_after = retry_after_seconds(exc.headers.get("Retry-After"))
            if retryable and retry_after is not None:
                check["retry_after_seconds"] = round(retry_after, 3)
                check["retry_not_before"] = (
                    datetime.now(timezone.utc) + timedelta(seconds=retry_after)
                ).isoformat()
            exc.close()
        except (TimeoutError, socket.timeout):
            check["error_code"] = "timeout"
        except URLError as exc:
            check["error_code"] = "timeout" if isinstance(exc.reason, TimeoutError) else "network_error"
        except (OSError, HTTPException):
            check["error_code"] = "network_error"
        check["elapsed_ms"] = round((time.monotonic() - start) * 1000)
        checks.append(check)
        if root is not None:
            return root, checks
        if not retryable or attempt == MAX_ATTEMPTS:
            break
        delay = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 1)
        if retry_after is not None:
            check["retry_after_seconds"] = round(retry_after, 3)
            if retry_after > MAX_RETRY_WAIT_SECONDS:
                check["retry_deferred"] = True
                break
            delay = max(delay, retry_after)
        check["retry_delay_seconds"] = round(delay, 3)
        time.sleep(delay)
    raise FeedFetchError(checks)
