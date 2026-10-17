"""Tavily Search API adapter."""

from __future__ import annotations

from typing import Any

from .http import post_json


def search(query: str, key: str, deep: bool) -> list[dict[str, Any]]:
    data = post_json("https://api.tavily.com/search", key, {
        "query": query, "search_depth": "advanced" if deep else "basic",
        "max_results": 8 if deep else 5, "include_raw_content": deep,
        "include_answer": False, "topic": "general",
    })
    return [{
        "title": str(item.get("title") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "snippet": str(item.get("content") or "").strip(),
        "raw_content": str(item.get("raw_content") or "").strip(),
        "provider": "Tavily",
    } for item in data.get("results", []) if isinstance(item, dict)]
