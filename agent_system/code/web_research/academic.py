"""Adapt Crossref and arXiv records to the shared search result shape."""

from __future__ import annotations

from typing import Any

from academic_metadata import arxiv, crossref


def _adapt(records: list[dict[str, Any]], provider: str) -> list[dict[str, Any]]:
    return [{
        "provider": provider,
        "title": record.get("title") or "",
        "url": record.get("url") or "",
        "snippet": record.get("abstract") or "",
        "raw_content": record.get("abstract") or "",
        "authors": record.get("authors") or [],
        "year": record.get("year"),
        "doi": record.get("doi"),
        "arxiv_id": record.get("arxiv_id"),
        "venue": record.get("venue"),
        "metadata_source": record.get("metadata_source") or provider,
    } for record in records]


def search_crossref(query: str, deep: bool) -> list[dict[str, Any]]:
    return _adapt(crossref.search(query, 8 if deep else 5), "Crossref")


def search_arxiv(query: str, deep: bool) -> list[dict[str, Any]]:
    records = arxiv.search(query, 8 if deep else 5)
    adapted = _adapt(records, "arXiv")
    if isinstance(records, arxiv.SearchRecords):
        return arxiv.SearchRecords(adapted, records.retrieved_via, records.upstream_error)
    return adapted
