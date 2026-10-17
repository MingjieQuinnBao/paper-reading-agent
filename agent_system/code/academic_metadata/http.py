"""Shared HTTP and text helpers for metadata providers."""

from __future__ import annotations

import urllib.request

USER_AGENT = "Paper-Reading-Agent/1.0 (academic metadata lookup)"


def get(url: str, timeout: float = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def clean(value: str | None) -> str:
    return " ".join((value or "").split())
