"""Reusable retrieval interface, independent of chat sessions and language models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .http import credential
from .retrieval import public_output, search_sources


def search(
    query: str, *, mode: str = "quick", limit: int = 20,
    providers: str | list[str] | tuple[str, ...] | None = None,
    keys: dict[str, str] | None = None, project_root: Path | None = None,
    include_raw_content: bool = False,
) -> dict[str, Any]:
    """Search selected sources and return normalized, deduplicated records.

    Explicit ``keys`` take precedence. If omitted, web keys are read from the
    environment or ``project_root/.env``; Crossref and arXiv need no API key.
    """
    if keys is None:
        root = project_root or Path(__file__).resolve().parents[3]
        keys = {name: credential(name, root) for name in ("TAVILY_API_KEY", "BOCHA_API_KEY")}
    result = search_sources(query, mode, keys, limit, providers)
    return result if include_raw_content else public_output(result)
