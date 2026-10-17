"""Find arXiv-linked records in OpenAlex when the arXiv API is unavailable."""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from .http import get

ARXIV_SOURCE = "https://openalex.org/S4306400194"
ARXIV_URL = re.compile(r"^https?://(?:www\.)?arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?/?$", re.I)
ARXIV_ID = re.compile(r"(?:(?:arxiv:)|(?:https?://)?arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(?:v\d+)?$", re.I)


def _abstract(inverted: dict[str, list[int]] | None) -> str | None:
    if not inverted:
        return None
    words = [(position, word) for word, positions in inverted.items() for position in positions]
    words.sort()
    return " ".join(word for _, word in words) or None


def _normalize(item: dict[str, Any], requested_id: str | None = None) -> dict[str, Any] | None:
    locations = item.get("locations") or []
    matching = [location.get("landing_page_url") or "" for location in locations
                if (location.get("source") or {}).get("id") == ARXIV_SOURCE]
    arxiv_url = next((url for url in matching if (match := ARXIV_URL.fullmatch(url))
                      and (requested_id is None or match.group(1) == requested_id)), None)
    if not arxiv_url:
        return None
    identifier = ARXIV_URL.fullmatch(arxiv_url).group(1)
    doi = item.get("doi") or ""
    return {
        "source": "arxiv", "metadata_source": "OpenAlex",
        "title": item.get("display_name") or "",
        "authors": [(entry.get("author") or {}).get("display_name") or ""
                    for entry in item.get("authorships") or []],
        "year": item.get("publication_year"),
        "doi": doi.removeprefix("https://doi.org/") or None,
        "arxiv_id": identifier,
        "abstract": _abstract(item.get("abstract_inverted_index")),
        "venue": ((item.get("primary_location") or {}).get("source") or {}).get("display_name"),
        "url": f"https://arxiv.org/abs/{identifier}",
    }


def search(query: str, limit: int) -> list[dict[str, Any]]:
    identifier = ARXIV_ID.fullmatch(query.strip())
    if identifier:
        paper_id = identifier.group(1)
        for scheme in ("http", "https"):
            params = {"filter": f"locations.landing_page_url:{scheme}://arxiv.org/abs/{paper_id}",
                      "per-page": 2}
            url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
            works = json.loads(get(url)).get("results") or []
            found = [record for item in works if (record := _normalize(item, paper_id))]
            if found:
                return found[:1]
        return []
    params = {"search": query, "filter": "locations.source.id:S4306400194", "per-page": min(limit, 20)}
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    works = json.loads(get(url)).get("results") or []
    return [record for item in works if (record := _normalize(item))][:limit]
