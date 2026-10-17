"""arXiv Atom API client and record normalization."""

from __future__ import annotations

import re
import threading
import time
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from .http import clean, get

ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_ID = re.compile(r"(?:(?:arxiv:)|(?:https?://)?arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(?:v\d+)?$", re.I)
_REQUEST_LOCK = threading.Lock()
_NEXT_REQUEST_AT = 0.0
_CACHE: dict[str, tuple[float, bytes]] = {}
_CACHE_SECONDS = 600
_MIN_INTERVAL_SECONDS = 3.1
_UNAVAILABLE_UNTIL = 0.0
_LAST_FAILURE = ""


class SearchRecords(list):
    def __init__(self, records: list[dict[str, Any]], retrieved_via: str, upstream_error: str):
        super().__init__(records)
        self.retrieved_via = retrieved_via
        self.upstream_error = upstream_error


class ArxivCooldownError(RuntimeError):
    pass


def _feed_bytes(url: str) -> bytes:
    """Cache identical lookups and serialize arXiv API calls in this process."""
    global _NEXT_REQUEST_AT, _UNAVAILABLE_UNTIL, _LAST_FAILURE
    with _REQUEST_LOCK:
        now = time.monotonic()
        cached = _CACHE.get(url)
        if cached and cached[0] > now:
            return cached[1]
        if _UNAVAILABLE_UNTIL > now:
            raise ArxivCooldownError(_LAST_FAILURE or "arXiv API temporarily unavailable")
        if _NEXT_REQUEST_AT > now:
            time.sleep(_NEXT_REQUEST_AT - now)
        _NEXT_REQUEST_AT = time.monotonic() + _MIN_INTERVAL_SECONDS
        try:
            payload = get(url, timeout=8)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                retry_after = error.headers.get("Retry-After") if error.headers else None
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 3
                _NEXT_REQUEST_AT = max(_NEXT_REQUEST_AT, time.monotonic() + min(delay, 30))
                _UNAVAILABLE_UNTIL = time.monotonic() + 600
                _LAST_FAILURE = "HTTP 429"
            raise
        except (urllib.error.URLError, TimeoutError) as error:
            _UNAVAILABLE_UNTIL = time.monotonic() + 120
            _LAST_FAILURE = type(error).__name__
            raise
        _CACHE[url] = (time.monotonic() + _CACHE_SECONDS, payload)
        return payload


def normalize(entry: ET.Element) -> dict[str, Any]:
    identifier_url = clean(entry.findtext("a:id", default="", namespaces=ATOM))
    identifier = ARXIV_ID.search(identifier_url.rstrip("/"))
    published = clean(entry.findtext("a:published", default="", namespaces=ATOM))
    return {
        "source": "arxiv", "title": clean(entry.findtext("a:title", default="", namespaces=ATOM)),
        "authors": [clean(author.findtext("a:name", default="", namespaces=ATOM))
                    for author in entry.findall("a:author", ATOM)],
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "doi": clean(entry.findtext("arxiv:doi", default="", namespaces=ATOM)) or None,
        "arxiv_id": identifier.group(1) if identifier else None,
        "abstract": clean(entry.findtext("a:summary", default="", namespaces=ATOM)) or None,
        "venue": clean(entry.findtext("arxiv:journal_ref", default="", namespaces=ATOM)) or None,
        "url": identifier_url or None,
    }


def search(query: str, limit: int) -> list[dict[str, Any]]:
    identifier = ARXIV_ID.fullmatch(query.strip())
    if identifier:
        params = {"id_list": identifier.group(1), "max_results": 1}
    else:
        phrase = clean(re.sub(r"[^\w\s-]", " ", query))
        params = {"search_query": f'all:"{phrase}"', "max_results": limit}
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    try:
        feed = ET.fromstring(_feed_bytes(url))
        return [normalize(entry) for entry in feed.findall("a:entry", ATOM)]
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ArxivCooldownError) as error:
        if isinstance(error, urllib.error.HTTPError) and error.code not in {429, 502, 503, 504}:
            raise
        from . import openalex_arxiv
        reason = _LAST_FAILURE or (f"HTTP {error.code}" if isinstance(error, urllib.error.HTTPError)
                                   else type(error).__name__)
        return SearchRecords(openalex_arxiv.search(query, limit), "OpenAlex", reason)
