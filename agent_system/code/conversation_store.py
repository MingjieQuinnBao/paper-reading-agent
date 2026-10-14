"""Persistent, versioned chat sessions for the paper-reading UI."""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = 1
ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_LOCK = threading.RLock()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _path(root: Path, session_id: str) -> Path:
    if not ID_PATTERN.fullmatch(session_id):
        raise ValueError("对话 ID 无效。")
    return root / "sessions" / f"{session_id}.json"


def _write(path: Path, session: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def create(root: Path, paper_source: str = "") -> dict[str, Any]:
    with _LOCK:
        session_id = secrets.token_hex(16)
        while _path(root, session_id).exists():
            session_id = secrets.token_hex(16)
        now = timestamp()
        session = {
            "version": VERSION, "session_id": session_id, "title": "新对话",
            "title_custom": False, "paper_source": paper_source,
            "created_at": now, "updated_at": now, "turns": [],
        }
        _write(_path(root, session_id), session)
        return session


def load(root: Path, session_id: str) -> dict[str, Any]:
    path = _path(root, session_id)
    if not path.is_file():
        raise FileNotFoundError("对话不存在。")
    session = json.loads(path.read_text(encoding="utf-8"))
    if session.get("version") != VERSION or session.get("session_id") != session_id or not isinstance(session.get("turns"), list):
        raise ValueError("对话文件格式无效。")
    return session


def recent(root: Path, limit: int = 30) -> list[dict[str, Any]]:
    folder = root / "sessions"
    if not folder.exists():
        return []
    sessions = []
    for path in folder.glob("*.json"):
        try:
            sessions.append(load(root, path.stem))
        except (ValueError, OSError, json.JSONDecodeError):
            continue
    return sorted(sessions, key=lambda row: row.get("updated_at", ""), reverse=True)[:limit]


def set_paper(root: Path, session_id: str, paper_source: str) -> dict[str, Any]:
    with _LOCK:
        session = load(root, session_id)
        if session["turns"] and session["paper_source"] != paper_source:
            raise ValueError("已有问答的对话不能更换论文，请新建对话。")
        session["paper_source"] = paper_source
        session["updated_at"] = timestamp()
        _write(_path(root, session_id), session)
        return session


def append(root: Path, session_id: str, turn: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        session = load(root, session_id)
        turn = {**turn, "number": len(session["turns"]) + 1, "created_at": timestamp()}
        session["turns"].append(turn)
        if len(session["turns"]) == 1 and not session.get("title_custom"):
            session["title"] = str(turn.get("question") or "论文摘要")[:48]
        session["updated_at"] = timestamp()
        _write(_path(root, session_id), session)
        return session


def rename(root: Path, session_id: str, title: str) -> dict[str, Any]:
    title = " ".join(title.split())
    if not title:
        raise ValueError("请输入对话名称。")
    if len(title) > 80:
        raise ValueError("对话名称不能超过 80 个字符。")
    with _LOCK:
        session = load(root, session_id)
        session["title"] = title
        session["title_custom"] = True
        session["updated_at"] = timestamp()
        _write(_path(root, session_id), session)
        return session


def delete(root: Path, session_id: str) -> None:
    with _LOCK:
        path = _path(root, session_id)
        if not path.is_file():
            raise FileNotFoundError("对话不存在。")
        path.unlink()


def import_record(root: Path, record: Any, paper_source: str) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("version") != VERSION or not isinstance(record.get("turns"), list):
        raise ValueError("对话文件格式无效。")
    if len(record["turns"]) > 500:
        raise ValueError("对话轮次超过 500。")
    validated = []
    for number, item in enumerate(record["turns"], 1):
        if not isinstance(item, dict) or not isinstance(item.get("question"), str) or not isinstance(item.get("answer"), str):
            raise ValueError(f"第 {number} 轮格式无效。")
        if len(item["question"]) > 20000 or len(item["answer"]) > 200000:
            raise ValueError(f"第 {number} 轮内容过长。")
        validated.append({
            "number": number, "kind": item.get("kind") if item.get("kind") in {"ask", "read", "error"} else "ask",
            "question": item["question"], "answer": item["answer"],
            "created_at": str(item.get("created_at") or timestamp())[:64],
            "run_id": str(item.get("run_id") or "")[:100],
            "model": str(item.get("model") or "")[:100],
            "config": item.get("config") if isinstance(item.get("config"), dict) else {},
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
            "annotations": [str(label)[:80] for label in item.get("annotations", [])[:10]]
            if isinstance(item.get("annotations"), list) else [],
        })
    session = create(root, paper_source)
    with _LOCK:
        session["turns"] = validated
        session["title"] = str(record.get("title") or (validated[0]["question"] if validated else "新对话"))[:48]
        session["title_custom"] = bool(record.get("title_custom", False))
        session["updated_at"] = timestamp()
        _write(_path(root, session["session_id"]), session)
    return session
