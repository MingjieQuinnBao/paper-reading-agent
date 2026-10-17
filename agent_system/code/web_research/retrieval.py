"""Fan out a query to four providers and return one structured result set."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from . import academic, bocha, tavily
from .normalize import deduplicate, normalize, public_record

PROVIDERS = ("Tavily", "Bocha", "Crossref", "arXiv")


def select_providers(names: str | list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if names is None:
        return PROVIDERS
    requested = names.split(",") if isinstance(names, str) else names
    lookup = {name.lower(): name for name in PROVIDERS}
    selected = []
    for raw in requested:
        name = lookup.get(str(raw).strip().lower())
        if name is None:
            raise ValueError(f"unknown provider: {raw}; choose from {', '.join(PROVIDERS)}")
        if name not in selected:
            selected.append(name)
    if not selected:
        raise ValueError("select at least one provider")
    return tuple(selected)


def _error(error: Exception) -> str:
    code = getattr(error, "code", None)
    return f"HTTP {code}" if code else type(error).__name__


def search_sources(
    query: str, mode: str, keys: dict[str, str], limit: int = 20,
    providers: str | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError("query must contain 1 to 500 characters")
    if mode not in {"quick", "deep"}:
        raise ValueError("mode must be quick or deep")
    if not 1 <= limit <= 40:
        raise ValueError("limit must be between 1 and 40")
    selected = select_providers(providers)
    deep = mode == "deep"
    available: list[tuple[str, Callable[[], list[dict[str, Any]]] | None]] = [
        ("Tavily", (lambda: tavily.search(query, keys["TAVILY_API_KEY"], deep))
         if keys.get("TAVILY_API_KEY") else None),
        ("Bocha", (lambda: bocha.search(query, keys["BOCHA_API_KEY"], deep))
         if keys.get("BOCHA_API_KEY") else None),
        ("Crossref", lambda: academic.search_crossref(query, deep)),
        ("arXiv", lambda: academic.search_arxiv(query, deep)),
    ]
    provider_calls = [(name, call) for name, call in available if name in selected]
    found: dict[str, list[dict[str, Any]]] = {}
    status: dict[str, dict[str, Any]] = {}
    active = [(name, call) for name, call in provider_calls if call is not None]
    with ThreadPoolExecutor(max_workers=max(1, len(active))) as pool:
        futures = {pool.submit(call): name for name, call in active}
        for future in as_completed(futures):
            name = futures[future]
            try:
                found[name] = future.result()
                via = getattr(found[name], "retrieved_via", None)
                status[name] = {"status": "degraded" if via else "ok", "count": len(found[name])}
                if via:
                    status[name].update({"via": via, "upstream_error": found[name].upstream_error})
            except Exception as error:
                found[name] = []
                status[name] = {"status": "error", "count": 0, "error": _error(error)}
    for name, call in provider_calls:
        if call is None:
            status[name] = {"status": "unconfigured", "count": 0}
    ordered = [item for name, _ in provider_calls for item in found.get(name, [])]
    valid_count = sum(normalize(item) is not None for item in ordered)
    unique = deduplicate(ordered)
    returned = unique[:limit]
    source_status = {name: status[name] for name, _ in provider_calls}
    summary = {
        "raw_count": len(ordered), "valid_count": valid_count,
        "unique_count": len(unique), "duplicates_removed": valid_count - len(unique),
        "returned_count": len(returned),
        "web_count": sum(item["source_type"] == "web" for item in unique),
        "academic_count": sum(item["source_type"] == "academic" for item in unique),
        "providers_ok": [name for name, state in source_status.items() if state["status"] in {"ok", "degraded"}],
        "providers_degraded": [name for name, state in source_status.items() if state["status"] == "degraded"],
        "providers_failed": [name for name, state in source_status.items() if state["status"] == "error"],
    }
    return {
        "query": query, "mode": mode, "providers": list(selected),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary, "source_status": source_status,
        "results": returned,
    }


def public_output(result: dict[str, Any]) -> dict[str, Any]:
    return {**result, "results": [public_record(item) for item in result["results"]]}
