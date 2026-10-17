"""Coordinate academic metadata providers without hiding partial failures."""

from __future__ import annotations

import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from . import arxiv, crossref


def search_academic(query: str, limit: int = 5, source: str = "all") -> dict[str, Any]:
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError("query must contain 1 to 500 characters")
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    if source not in {"all", "crossref", "arxiv"}:
        raise ValueError("source must be all, crossref, or arxiv")
    results: list[dict[str, Any]] = []
    status: dict[str, dict[str, Any]] = {}
    for name, searcher in (("crossref", crossref.search), ("arxiv", arxiv.search)):
        if source not in {"all", name}:
            continue
        try:
            found = searcher(query, limit)
            results.extend(found)
            via = getattr(found, "retrieved_via", None)
            status[name] = {"status": "degraded" if via else "ok", "count": len(found)}
            if via:
                status[name].update({"via": via, "upstream_error": found.upstream_error})
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, ET.ParseError) as exc:
            status[name] = {"status": "error", "message": str(exc)[:250]}
    return {"query": query, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_status": status, "results": results}
