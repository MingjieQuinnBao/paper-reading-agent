"""Normalize and merge search results from web and scholarly providers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

DOI = re.compile(r"10\.\d{4,9}/[^\s?#]+", re.I)
ARXIV_ID = re.compile(r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
ACADEMIC = {"Crossref", "arXiv"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _doi(value: Any) -> str:
    match = DOI.search(unquote(_clean(value)))
    return match.group(0).rstrip(".,;)").casefold() if match else ""


def _arxiv_id(value: Any) -> str:
    match = ARXIV_ID.search(_clean(value))
    return match.group(1) if match else ""


def _url(value: Any) -> str:
    try:
        parts = urlsplit(_clean(value))
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return ""
        host = parts.hostname.casefold().removeprefix("www.")
        port = f":{parts.port}" if parts.port else ""
        query = urlencode(sorted((key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                                  if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING))
        path = unquote(parts.path).rstrip("/") or "/"
        scheme = "https" if host in {"doi.org", "dx.doi.org", "arxiv.org"} else parts.scheme.casefold()
        return urlunsplit((scheme, host + port, path, query, ""))
    except ValueError:
        return ""


def normalize(item: dict[str, Any]) -> dict[str, Any] | None:
    title = _clean(item.get("title"))
    url = _url(item.get("url"))
    if not title or not url:
        return None
    provider = _clean(item.get("provider")) or "Unknown"
    authors = item.get("authors") or []
    authors = [_clean(author) for author in authors if _clean(author)] if isinstance(authors, list) else []
    year = item.get("year")
    year = int(year) if str(year).isdigit() and 1800 <= int(year) <= 2200 else None
    doi = _doi(item.get("doi") or url)
    arxiv_id = _arxiv_id(item.get("arxiv_id") or url) if provider == "arXiv" or "arxiv.org" in url else ""
    snippet = _clean(item.get("snippet") or item.get("abstract"))
    if not snippet and provider in ACADEMIC:
        snippet = (" · ".join(part for part in (", ".join(authors[:3]), str(year or ""), _clean(item.get("venue"))) if part)
                   or "Metadata record; abstract unavailable.")
    if not snippet and not item.get("raw_content"):
        return None
    return {
        "id": doi or arxiv_id or url,
        "source_type": "academic" if provider in ACADEMIC else "web",
        "provider": provider, "providers": [provider],
        "title": title, "url": url, "alternate_urls": [],
        "snippet": snippet, "raw_content": _clean(item.get("raw_content")),
        "doi": doi or None, "arxiv_id": arxiv_id or None,
        "authors": authors, "year": year, "venue": _clean(item.get("venue")) or None,
        "metadata_source": _clean(item.get("metadata_source")) or provider,
    }


def _identities(item: dict[str, Any]) -> set[str]:
    keys = {"url:" + re.sub(r"^https?://", "", url)
            for url in [item["url"], *item["alternate_urls"]]}
    if item.get("doi"):
        keys.add("doi:" + item["doi"])
    if item.get("arxiv_id"):
        keys.add("arxiv:" + item["arxiv_id"])
    title = re.sub(r"[^\w]+", "", item["title"].casefold())
    if item["source_type"] == "academic" and len(title) >= 15:
        keys.add("academic-title:" + title + ":" + str(item.get("year") or "unknown"))
    return keys


def _merge(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for provider in incoming["providers"]:
        if provider not in target["providers"]:
            target["providers"].append(provider)
    urls = set(target["alternate_urls"] + incoming["alternate_urls"] + [target["url"], incoming["url"]])
    if incoming["source_type"] == "academic" and target["source_type"] != "academic":
        target["url"] = incoming["url"]
        target["provider"] = incoming["provider"]
        target["source_type"] = "academic"
        target["metadata_source"] = incoming["metadata_source"]
    target["alternate_urls"] = sorted(urls - {target["url"]})
    for field in ("doi", "arxiv_id", "year", "venue"):
        target[field] = target.get(field) or incoming.get(field)
    if len(incoming["authors"]) > len(target["authors"]):
        target["authors"] = incoming["authors"]
    if len(incoming["snippet"]) > len(target["snippet"]):
        target["snippet"] = incoming["snippet"]
    if len(incoming["raw_content"]) > len(target["raw_content"]):
        target["raw_content"] = incoming["raw_content"]
    target["id"] = target.get("doi") or target.get("arxiv_id") or target["url"]


def deduplicate(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    for raw in results:
        item = normalize(raw)
        if item is None:
            continue
        matches = [index for index, existing in enumerate(unique)
                   if _identities(item) & _identities(existing)]
        if not matches:
            unique.append(item)
            continue
        primary = unique[matches[0]]
        _merge(primary, item)
        for index in reversed(matches[1:]):
            _merge(primary, unique.pop(index))
    return unique


def public_record(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "raw_content"}
