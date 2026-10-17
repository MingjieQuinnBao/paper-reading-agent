"""Crossref REST API client and record normalization."""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from .http import clean, get

DOI = re.compile(r"(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.I)


def normalize(item: dict[str, Any]) -> dict[str, Any]:
    date = item.get("published") or item.get("issued") or {}
    parts = date.get("date-parts") or [[]]
    authors = [clean(" ".join(filter(None, (author.get("given"), author.get("family")))))
               for author in item.get("author", [])]
    doi = item.get("DOI") or ""
    return {
        "source": "crossref", "title": clean((item.get("title") or [""])[0]),
        "authors": authors, "year": parts[0][0] if parts and parts[0] else None,
        "doi": doi or None, "arxiv_id": None,
        "abstract": clean(re.sub(r"<[^>]+>", " ", item.get("abstract") or "")) or None,
        "venue": clean((item.get("container-title") or [""])[0]) or None,
        "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
    }


def search(query: str, limit: int) -> list[dict[str, Any]]:
    doi_match = DOI.fullmatch(urllib.parse.unquote(query.strip()))
    if doi_match:
        doi = doi_match.group(1).rstrip(".,;)")
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
        return [normalize(json.loads(get(url))["message"])]
    params = urllib.parse.urlencode({"query.bibliographic": query, "rows": limit})
    url = "https://api.crossref.org/works?" + params
    return [normalize(item) for item in json.loads(get(url))["message"]["items"]]


def work(doi: str) -> dict[str, Any]:
    """Return the complete deposited Crossref record for one DOI."""
    doi = doi.strip().removeprefix("https://doi.org/")
    if not DOI.fullmatch(doi):
        raise ValueError("invalid DOI")
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    return json.loads(get(url))["message"]


def search_works(title: str, limit: int = 5) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query.title": title, "rows": limit})
    url = "https://api.crossref.org/works?" + params
    return json.loads(get(url))["message"]["items"]
