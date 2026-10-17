"""HTTP transport for the Paper Reading Agent."""

from __future__ import annotations

import html
import json
import os
import re
import socket
import urllib.error
from dataclasses import asdict
from email import policy
from email.parser import BytesParser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from chat_stream import EventWriter


class LocalHTTPServer(ThreadingHTTPServer):
    """Reject duplicate Windows listeners instead of sharing the same local port."""

    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_handler(core):
    class AgentHandler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict[str, Any], code: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send(self, body: str, code: int = 200, paper_source: str = "", session_id: str = "") -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            if paper_source:
                self.send_header("Set-Cookie", f"paper_source={paper_source}; Path=/; SameSite=Lax; HttpOnly")
            if session_id:
                self.send_header("Set-Cookie", f"session_id={session_id}; Path=/; SameSite=Lax; HttpOnly")
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, location: str, session: dict[str, Any]) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            if session.get("paper_source"):
                self.send_header("Set-Cookie", f'paper_source={session["paper_source"]}; Path=/; SameSite=Lax; HttpOnly')
            self.send_header("Set-Cookie", f'session_id={session["session_id"]}; Path=/; SameSite=Lax; HttpOnly')
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _cookie_value(self, name: str) -> str:
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except Exception:
                return ""
            return cookie[name].value if name in cookie else ""

        def _session(self, requested_id: str = "") -> dict[str, Any]:
            for candidate in (requested_id, self._cookie_value("session_id")):
                if candidate:
                    try:
                        return core.conversations.load(core.ROOT, candidate)
                    except (ValueError, FileNotFoundError, json.JSONDecodeError):
                        pass
            return core.conversations.create(core.ROOT, self._paper_source())

        def _paper_source(self) -> str:
            source = self._cookie_value("paper_source")
            return source if source in core.load_paper_catalog() and core.paper_path(source).exists() else ""

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            static_files = {"/static/chat.css": "text/css; charset=utf-8",
                            "/static/chat.js": "application/javascript; charset=utf-8",
                            "/static/settings.js": "application/javascript; charset=utf-8",
                            "/static/markdown.js": "application/javascript; charset=utf-8"}
            katex_asset = parsed.path.removeprefix("/static/katex/") if parsed.path.startswith("/static/katex/") else ""
            katex_types = {"katex.min.js": "application/javascript; charset=utf-8",
                           "auto-render.min.js": "application/javascript; charset=utf-8",
                           "katex.min.css": "text/css; charset=utf-8"}
            if katex_asset in katex_types:
                static_files[parsed.path] = katex_types[katex_asset]
            elif re.fullmatch(r"fonts/KaTeX_[A-Za-z0-9_-]+\.(?:woff2?|ttf)", katex_asset):
                extension = katex_asset.rsplit(".", 1)[1]
                static_files[parsed.path] = {"woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf"}[extension]
            if parsed.path in static_files:
                asset = (Path(__file__).with_name("static") / "katex" / katex_asset
                         if katex_asset else Path(__file__).with_name("static") / parsed.path.rsplit("/", 1)[1])
                data = asset.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", static_files[parsed.path])
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path == "/api/academic-search":
                try:
                    query = params.get("query", [""])[0]
                    limit = int(params.get("limit", ["5"])[0])
                    source = params.get("source", ["all"])[0].lower()
                    self._send_json(core.academic_search.search_academic(query, limit, source))
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, code=400)
                return
            if parsed.path == "/api/paper-info":
                try:
                    query = params.get("query", [""])[0]
                    source = params.get("source", [""])[0]
                    if query:
                        self._send_json(core.academic_search.collect_paper_info(query))
                    elif source:
                        self._send_json(core.paper_info_for_source(self._paper_source() if source == "current" else source))
                    else:
                        raise ValueError("query or source is required")
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, code=400)
                return
            if parsed.path == "/api/multi-source-search":
                try:
                    query = params.get("query", [""])[0]
                    mode = params.get("mode", ["quick"])[0].lower()
                    limit = int(params.get("limit", ["20"])[0])
                    providers = params.get("providers", [None])[0]
                    if providers is None:
                        self._send_json(core.multi_source_search(query, mode, limit))
                    else:
                        self._send_json(core.multi_source_search(query, mode, limit, providers))
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, code=400)
                return
            cfg = core.AgentConfig(paper_source=self._paper_source())
            if parsed.path == "/export":
                try:
                    session = core.conversations.load(core.ROOT, params.get("session", [self._cookie_value("session_id")])[0])
                    data = core.export_conversation(session)
                except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                    self._send(f'<p class="error">{html.escape(str(exc))}</p>', code=404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="conversation-{session["session_id"]}.json"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path == "/logs":
                self._send(core.render_page(core.render_call_chain_list(core.extract_call_chains()), cfg, logs_view=True))
                return
            if parsed.path == "/demo-diff":
                acceptance = core.run_acceptance_cases()
                result = core.answer_question("Explain I-JEPA method with page evidence", core.AgentConfig(route_mode="auto"))
                self._send(core.render_page(core.render_diff_demo(result, acceptance), cfg))
                return
            if parsed.path == "/demo":
                result = core.answer_question("Explain I-JEPA method with page evidence", core.AgentConfig(route_mode="auto"))
                self._send(core.render_page(core.render_result(result), cfg))
                return
            session = self._session(params.get("session", [""])[0])
            self._send(core.render_chat(session, search=params.get("search", [""])[0]),
                       paper_source=session.get("paper_source", ""), session_id=session["session_id"])

        def _read_form(self) -> tuple[dict[str, list[str]], tuple[str, bytes] | None]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > core.MAX_UPLOAD_BYTES + 1024 * 1024:
                raise ValueError("请求为空或文件超过 20 MB。")
            body = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("multipart/form-data"):
                return parse_qs(body.decode("utf-8")), None
            header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            message = BytesParser(policy=policy.default).parsebytes(header + body)
            if not message.is_multipart():
                raise ValueError("上传表单格式无效。")
            form: dict[str, list[str]] = {}
            upload = None
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if not name:
                    continue
                payload = part.get_payload(decode=True) or b""
                filename = part.get_filename()
                if filename:
                    upload = (filename, payload)
                else:
                    form[name] = [payload.decode("utf-8")]
            return form, upload

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/render-markdown":
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 250_000:
                    self._send_json({"error": "Markdown 过长。"}, code=413)
                    return
                try:
                    source = self.rfile.read(length).decode("utf-8")
                except UnicodeDecodeError:
                    self._send_json({"error": "Markdown 编码无效。"}, code=400)
                    return
                self._send_json({"html": core.chat_ui.render_markdown(source)})
                return
            if path == "/new":
                core.conversations.discard_unused(core.ROOT, self._cookie_value("session_id"))
                session = core.conversations.create(core.ROOT)
                self._redirect(f'/?session={session["session_id"]}', session)
                return
            if path == "/import":
                try:
                    _, upload = self._read_form()
                    if not upload or Path(upload[0]).suffix.lower() != ".json":
                        raise ValueError("请选择导出的 JSON 对话文件。")
                    session = core.import_conversation(upload[1])
                except (ValueError, RuntimeError, FileNotFoundError, UnicodeDecodeError) as exc:
                    current = self._session()
                    self._send(core.render_chat(current, error=f"加载失败：{exc}"),
                               paper_source=current.get("paper_source", ""), session_id=current["session_id"])
                    return
                self._redirect(f'/?session={session["session_id"]}', session)
                return
            if path in {"/rename", "/delete"}:
                current = self._session()
                try:
                    form, _ = self._read_form()
                    target_id = form.get("session_id", [""])[0]
                    if path == "/rename":
                        target = core.conversations.rename(core.ROOT, target_id, form.get("title", [""])[0])
                        destination = target if current["session_id"] == target_id else current
                    else:
                        core.conversations.delete(core.ROOT, target_id)
                        if current["session_id"] == target_id:
                            others = core.conversations.recent(core.ROOT, limit=1)
                            destination = others[0] if others else core.conversations.create(core.ROOT)
                        else:
                            destination = current
                except (ValueError, FileNotFoundError, UnicodeDecodeError) as exc:
                    self._send(core.render_chat(current, error=f"操作失败：{exc}"),
                               paper_source=current.get("paper_source", ""), session_id=current["session_id"])
                    return
                self._redirect(f'/?session={destination["session_id"]}', destination)
                return
            if path not in {"/ask", "/ask/stream"}:
                self._send("未找到页面。", code=404)
                return

            stream = EventWriter(self) if path == "/ask/stream" else None

            question = ""
            paper_text = ""
            cfg = core.AgentConfig(paper_source="")
            session: dict[str, Any] | None = None
            form: dict[str, list[str]] = {}
            action = "ask"
            try:
                form, upload = self._read_form()
                session = self._session(form.get("session_id", [""])[0])
                question = form.get("q", [""])[0].strip()
                research_mode = form.get("research_mode", ["paper"])[0]
                if research_mode not in {"paper", "quick", "deep"}:
                    raise ValueError("搜索模式无效。")
                paper_text = form.get("paper_text", [""])[0].strip()
                source = session.get("paper_source", "")
                if upload and paper_text:
                    raise ValueError("请选择文件或粘贴正文，不要同时填写两项。")
                if upload:
                    source = core.ingest_paper_bytes(*upload)["source_id"]
                    paper_text = ""
                elif paper_text:
                    source = core.ingest_paper_bytes("粘贴论文.md", paper_text.encode("utf-8"))["source_id"]
                    paper_text = ""
                elif not source and research_mode == "paper":
                    raise ValueError("请导入论文文件或粘贴正文。")
                if source != session.get("paper_source", ""):
                    if session["turns"]:
                        session = core.conversations.create(core.ROOT, source)
                    else:
                        session = core.conversations.set_paper(core.ROOT, session["session_id"], source)
                choice = form.get("model_choice", [""])[0]
                if choice:
                    if choice not in {"auto", *core.LLM_MODELS, "rule-reader", "mock-fast"}:
                        raise ValueError("模型选择无效。")
                    route_mode = "auto" if choice == "auto" else "manual"
                    model = "deepseek-flash" if choice == "auto" else choice
                else:
                    model = form.get("model", ["deepseek-flash"])[0]
                    route_mode = form.get("route_mode", ["auto"])[0]
                cfg = core.AgentConfig(
                    model=model,
                    route_mode=route_mode,
                    temperature=float(form.get("temperature", ["0.2"])[0]),
                    top_p=float(form.get("top_p", ["0.9"])[0]),
                    max_tokens=int(form.get("max_tokens", ["2400"])[0]),
                    evidence_limit=int(form.get("evidence_limit", ["4"])[0]),
                    paper_source=source,
                )
                if (not 0 <= cfg.temperature <= 1.5 or not 0 < cfg.top_p <= 1
                        or not 100 <= cfg.max_tokens <= 6000 or not 1 <= cfg.evidence_limit <= 8):
                    raise ValueError("参数超出范围。")
                action = form.get("action", ["ask"])[0]
                if action == "read":
                    if cfg.route_mode == "auto":
                        cfg.model = core.route_model("", cfg)
                    result = core.read_paper_with_llm(cfg.paper_source, cfg)
                    turn = core.reading_turn(result, cfg)
                else:
                    if not question:
                        raise ValueError("请先输入问题。")
                    callbacks = ({"on_delta": lambda text: stream.send("delta", text=text),
                                  "on_status": lambda message: stream.send("status", message=message),
                                  "on_process": lambda step: stream.send("process", step=step)}
                                 if stream else {})
                    if research_mode == "paper":
                        result = core.answer_question(
                            question, cfg, session["turns"],
                            **callbacks, **({"on_reset": lambda: stream.send("reset")} if stream else {}),
                        )
                    else:
                        result = core.research_answer(question, research_mode, cfg, **callbacks)
                    turn = core.answer_turn(result)
                session = core.conversations.append(core.ROOT, session["session_id"], turn)
                error = ""
            except (ValueError, RuntimeError, FileNotFoundError, UnicodeDecodeError,
                    urllib.error.URLError, TimeoutError) as exc:
                error = f"执行失败：{exc}"
                if session is None:
                    session = self._session()
                if question or (action == "read" and session.get("paper_source")):
                    session = core.conversations.append(core.ROOT, session["session_id"], {
                        "kind": "error", "question": question or "生成论文摘要", "answer": error,
                        "run_id": "", "model": "", "config": asdict(cfg), "evidence": [],
                        "annotations": ["执行失败"],
                    })
            if stream:
                stream.send("done", session_id=session["session_id"], error=bool(error), message=error)
            else:
                self._send(core.render_chat(session, error=error, draft=question if error else "", paper_text=paper_text,
                                       cfg=cfg if not error else None),
                           paper_source=session.get("paper_source", ""), session_id=session["session_id"])

        def log_message(self, fmt: str, *args: Any) -> None:
            with (core.LOGS / "server.log").open("a", encoding="utf-8") as log_file:
                log_file.write(fmt % args + "\n")


    return AgentHandler
