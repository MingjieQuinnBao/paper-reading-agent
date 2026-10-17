"""Bocha Web Search API adapter."""

from __future__ import annotations

from typing import Any

from .http import post_json


def search(query: str, key: str, deep: bool) -> list[dict[str, Any]]:
    data = post_json("https://api.bochaai.com/v1/web-search", key, {
        "query": query, "summary": deep, "count": 8 if deep else 5,
    })
    if data.get("code") not in (None, 200):
        raise ValueError("Bocha search failed")
    value = ((data.get("data") or {}).get("webPages") or {}).get("value") or []
    return [{
        "title": str(item.get("name") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "snippet": str(item.get("snippet") or "").strip(),
        "raw_content": str(item.get("summary") or "").strip(),
        "provider": "Bocha",
    } for item in value if isinstance(item, dict)]
