"""Collect a verified paper record and its deposited reference list."""

from __future__ import annotations

import re
import urllib.error
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from . import arxiv, crossref
from .http import clean


def _title_key(value: str) -> str:
    return re.sub(r"[^\w]+", " ", value.casefold()).strip()


def _same_title(query: str, title: str) -> bool:
    requested, found = _title_key(query), _title_key(title)
    return bool(requested and found and SequenceMatcher(None, requested, found).ratio() >= 0.86)


def _reference(item: dict[str, Any], position: int) -> dict[str, Any]:
    doi = clean(item.get("DOI")) or None
    title = clean(item.get("article-title") or item.get("volume-title")) or None
    citation = clean(item.get("unstructured"))
    if not citation:
        citation = ", ".join(filter(None, (
            clean(item.get("author")), title or "", clean(item.get("journal-title")),
            clean(item.get("year")),
        )))
    return {
        "position": position, "title": title, "citation": citation or None,
        "doi": doi, "url": f"https://doi.org/{doi}" if doi else None,
        "year": int(item["year"]) if str(item.get("year", "")).isdigit() else None,
    }


def _error(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    return f"HTTP {code}" if code else type(exc).__name__


def collect(query: str) -> dict[str, Any]:
    """Resolve a DOI, arXiv ID, or sufficiently matching paper title.

    Coverage means presence in the named metadata API only. Absent references
    mean they were not deposited there, not that the paper has no references.
    """
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError("query must contain 1 to 500 characters")
    doi_match = crossref.DOI.fullmatch(query)
    arxiv_match = arxiv.ARXIV_ID.fullmatch(query)
    status: dict[str, dict[str, str]] = {}
    candidates: list[dict[str, Any]] = []
    raw: dict[str, Any] | None = None
    arxiv_record: dict[str, Any] | None = None

    try:
        if doi_match:
            raw = crossref.work(doi_match.group(1))
        elif not arxiv_match:
            matches = crossref.search_works(query)
            candidates = [crossref.normalize(item) for item in matches]
            raw = next((item for item in matches if _same_title(query, (item.get("title") or [""])[0])), None)
            if raw and raw.get("DOI"):
                raw = crossref.work(raw["DOI"])
        status["Crossref"] = {"status": "ok" if raw else "no_verified_match"}
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError) as exc:
        status["Crossref"] = {"status": "error", "error": _error(exc)}

    if arxiv_match or (not doi_match and query):
        try:
            arxiv_results = arxiv.search(query, 5)
            for item in arxiv_results:
                if arxiv_match or _same_title(query, item.get("title") or ""):
                    arxiv_record = item
                    break
            via = getattr(arxiv_results, "retrieved_via", None)
            status["arXiv"] = {"status": "degraded" if via else ("ok" if arxiv_record else "no_verified_match")}
            if via:
                status["arXiv"].update({"via": via, "upstream_error": arxiv_results.upstream_error})
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            status["arXiv"] = {"status": "error", "error": _error(exc)}
    else:
        status["arXiv"] = {"status": "not_checked"}

    paper = crossref.normalize(raw) if raw else arxiv_record
    references = [_reference(item, index) for index, item in enumerate(raw.get("reference") or [], 1)] if raw else []
    coverage = {
        "crossref": "registered" if raw else status["Crossref"]["status"],
        "arxiv": "record_found" if arxiv_record else status["arXiv"]["status"],
        "other_indexes": "not_checked",
    }
    return {
        "query": query, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "match_status": "verified" if paper else "not_verified",
        "paper": paper, "coverage": coverage,
        "references": references,
        "references_status": "deposited" if references else ("not_available_in_crossref_record" if raw else "not_available"),
        "reference_count_reported": raw.get("reference-count") if raw else None,
        "source_status": status, "candidates": candidates if not paper else [],
    }
