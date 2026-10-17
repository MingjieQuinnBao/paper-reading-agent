"""Streaming Chat Completions transport for DeepSeek."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable


def reveal_text(answer: str, on_delta: Callable[[str], None]) -> None:
    """Pace local fallback text so the same UI can reveal it progressively."""
    size = max(8, (len(answer) + 119) // 120)
    for start in range(0, len(answer), size):
        on_delta(answer[start:start + size])
        time.sleep(0.012)


def complete(
    model: str, prompt: str, cfg: Any, tag: str, system_prompt: str,
    *, key: str, url: str, logs: Path, dump_json: Callable[[Path, Any], None],
    on_delta: Callable[[str], None],
) -> tuple[str, dict[str, Any]]:
    if not key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法调用云模型。")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        "temperature": cfg.temperature,
        "top_p": cfg.top_p,
        "max_tokens": cfg.max_tokens,
        "stream": True,
        "thinking": {"type": "disabled"},
    }
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    dump_json(logs / f"{tag}.request.json", {**payload, "api_key_logged": False})
    started = time.perf_counter()
    pieces: list[str] = []
    actual_model = model
    finish_reason = None
    usage: dict[str, Any] = {}
    done = False
    with urllib.request.urlopen(request, timeout=120) as response:
        status = response.status
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                done = True
                break
            chunk = json.loads(data)
            actual_model = chunk.get("model") or actual_model
            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                content = delta.get("content") or ""
                if content:
                    pieces.append(content)
                    on_delta(content)
                finish_reason = choice.get("finish_reason") or finish_reason
    if not done:
        raise RuntimeError("模型流式响应中断。")
    answer = "".join(pieces)
    meta = {
        "backend": "deepseek", "requested_model": model, "actual_model": actual_model,
        "status": status, "seconds": round(time.perf_counter() - started, 3),
        "usage": usage, "finish_reason": finish_reason,
    }
    dump_json(logs / f"{tag}.response.json", {
        "model": actual_model, "choices": [{"message": {"content": answer}, "finish_reason": finish_reason}],
        "usage": usage,
    })
    dump_json(logs / f"{tag}.meta.json", meta)
    return answer, meta
