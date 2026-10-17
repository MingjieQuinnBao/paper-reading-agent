"""Shared credential and JSON HTTP helpers for search providers."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any


def credential(name: str, project_root: Path) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    env_file = project_root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            key, separator, raw = line.partition("=")
            if separator and key.strip() == name:
                return raw.strip().strip('"').strip("'")
    return ""


def post_json(url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError("Search provider returned an invalid response")
    return data
