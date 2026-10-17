from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from contextlib import ExitStack
from http.cookiejar import CookieJar
from pathlib import Path
from unittest.mock import patch

import agent_core
import chat_ui
import conversation_store


def multipart(fields: dict[str, str], filename: str, data: bytes, name: str) -> tuple[bytes, str]:
    boundary = "----chat-session-test"
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
             for key, value in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                 'Content-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class ChatSessionTests(unittest.TestCase):
    def test_markdown_renders_without_executable_html(self) -> None:
        rendered = chat_ui.render_markdown(
            "## Summary\n\n- **Finding** with `code`\n\n```python\nprint(1)\n```\n"
            "<script>alert(1)</script> [unsafe](javascript:alert(1)) "
            r"$A^r_T$ \(x+1\) \[y^2\]"
        )
        self.assertIn("<h2>Summary</h2>", rendered)
        self.assertIn("<strong>Finding</strong>", rendered)
        self.assertIn("<pre><code>", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn('href="javascript:', rendered)
        self.assertIn(r"$A^r_T$", rendered)
        self.assertIn(r"\(x+1\)", rendered)
        self.assertIn(r"\[y^2\]", rendered)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "agent_system"
        self.root.mkdir()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in ("inputs", "logs", "results"):
            folder = self.root / name
            folder.mkdir()
            self.stack.enter_context(patch.object(agent_core, name.upper(), folder))
        self.stack.enter_context(patch.object(agent_core, "ROOT", self.root))
        self.server = agent_core.ThreadingHTTPServer(("127.0.0.1", 0), agent_core.AgentHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(lambda: self.thread.join(timeout=2))
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def get(self, path: str = "/") -> str:
        with self.opener.open(self.base + path) as response:
            return response.read().decode("utf-8")

    def test_settings_ui_and_script_are_served(self) -> None:
        page = self.get()
        self.assertIn('id="settings-trigger"', page)
        self.assertIn('id="settings-overlay"', page)
        self.assertIn('data-settings-tab="responses"', page)
        self.assertIn('id="setting-language"', page)
        self.assertIn('id="setting-send-mode"', page)
        self.assertIn('id="setting-reasoning-expanded"', page)
        self.assertIn('id="mode-slider"', page)
        self.assertNotIn('只切换界面文字，不改写论文与回答。', page)
        with self.opener.open(self.base + "/static/settings.js") as response:
            self.assertEqual(response.headers.get_content_type(), "application/javascript")
            script = response.read().decode("utf-8")
        self.assertIn("paper-agent-settings-v1", script)

    def test_quick_search_works_without_imported_paper(self) -> None:
        self.get()
        item = {"title": "Study result", "url": "https://example.org/study",
                "snippet": "A concrete search result.", "raw_content": "", "provider": "Tavily"}
        with patch.object(agent_core, "search_credential", side_effect=lambda name, root: "test" if name == "TAVILY_API_KEY" else ""), \
             patch("web_research.retrieval.tavily.search", return_value=[item]) as search, \
             patch("web_research.retrieval.academic.search_crossref", return_value=[]), \
             patch("web_research.retrieval.academic.search_arxiv", return_value=[]):
            page = self.post({"q": "concrete study", "research_mode": "quick"})
        search.assert_called_once_with("concrete study", "test", False)
        self.assertIn("Study result", page)
        session = conversation_store.recent(self.root)[0]
        self.assertEqual("search", session["turns"][0]["model"])
        self.assertEqual("", session["paper_source"])

    def test_live_markdown_route_and_local_math_assets(self) -> None:
        request = urllib.request.Request(
            self.base + "/api/render-markdown", data=b"**bold** $x^2$ <script>alert(1)</script>",
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        with self.opener.open(request) as response:
            rendered = json.load(response)["html"]
        self.assertIn("<strong>bold</strong>", rendered)
        self.assertIn("$x^2$", rendered)
        self.assertNotIn("<script>", rendered)
        for path, media_type in (("/static/katex/katex.min.js", "application/javascript"),
                                 ("/static/katex/katex.min.css", "text/css"),
                                 ("/static/katex/fonts/KaTeX_Main-Regular.woff2", "font/woff2")):
            with self.opener.open(self.base + path) as response:
                self.assertEqual(response.headers.get_content_type(), media_type)
                self.assertGreater(len(response.read()), 100)

    def test_blank_chats_stay_out_of_history_and_are_discarded_on_new(self) -> None:
        self.get()
        first_id = next((self.root / "sessions").glob("*.json")).stem
        self.assertEqual(conversation_store.recent(self.root), [])
        page = self.post({}, "/new")
        with self.assertRaises(FileNotFoundError):
            conversation_store.load(self.root, first_id)
        self.assertEqual(conversation_store.recent(self.root), [])
        self.assertNotIn('class="session-menu"', page)

    def test_stream_appends_follow_up_to_existing_chat(self) -> None:
        self.get()
        self.upload({"q": "First question", "model_choice": "rule-reader"},
                    "demo.md", b"# Method\nThe paper uses copper tokens.", "paper_file", "/ask")
        original = conversation_store.recent(self.root)[0]
        self.post({}, "/new")
        self.get(f'/?session={original["session_id"]}')

        def fake_stream(model, prompt, cfg, tag, on_delta):
            self.assertIn("First question", prompt)
            on_delta("Second ")
            on_delta("answer")
            return "Second answer", {"actual_model": model, "finish_reason": "stop", "status": 200}

        with patch.object(agent_core, "call_deepseek_stream", side_effect=fake_stream):
            stream = self.post({"q": "Follow-up question", "model_choice": "deepseek-flash",
                                "session_id": original["session_id"]}, "/ask/stream")
        events = [json.loads(line) for line in stream.splitlines()]
        self.assertEqual([event["type"] for event in events if event["type"] in {"delta", "done"}],
                         ["delta", "delta", "done"])
        self.assertTrue(any(event["type"] == "process" for event in events))
        self.assertEqual("".join(event["text"] for event in events if event["type"] == "delta"), "Second answer")
        self.assertEqual(events[-1]["session_id"], original["session_id"])
        restored = conversation_store.load(self.root, original["session_id"])
        self.assertEqual(len(restored["turns"]), 2)
        self.assertEqual(restored["turns"][1]["answer"], "Second answer")
        self.assertEqual(restored["turns"][1]["process"][-1]["key"], "processDone")
        self.assertIn('class="reasoning-process"', self.get(f'/?session={original["session_id"]}'))

    def post(self, fields: dict[str, str], path: str = "/ask") -> str:
        data = urllib.parse.urlencode(fields).encode()
        with self.opener.open(self.base + path, data=data) as response:
            return response.read().decode("utf-8")

    def upload(self, fields: dict[str, str], filename: str, data: bytes, name: str, path: str) -> str:
        payload, content_type = multipart(fields, filename, data, name)
        request = urllib.request.Request(self.base + path, data=payload, headers={"Content-Type": content_type})
        with self.opener.open(request) as response:
            return response.read().decode("utf-8")

    def test_chat_persists_turns_and_uses_history_in_next_prompt(self) -> None:
        calls = []

        def fake_call(model, prompt, cfg, tag, system_prompt=""):
            calls.append(prompt)
            return ("First answer" if len(calls) == 1 else "Second answer"), {
                "actual_model": model, "finish_reason": "stop", "status": 200,
            }

        with patch.object(agent_core, "call_deepseek", side_effect=fake_call):
            self.get()
            first = self.upload({"q": "What is the method?", "model_choice": "deepseek-flash", "action": "ask"},
                                "demo.md", b"# Method\nThe paper uses copper tokens.", "paper_file", "/ask")
            second = self.post({"q": "What about its limitation?", "model_choice": "deepseek-flash", "action": "ask"})
        self.assertIn("First answer", first)
        self.assertIn("First answer", second)
        self.assertIn("Second answer", second)
        self.assertIn("What is the method?", calls[1])
        self.assertIn("First answer", calls[1])
        self.assertIn("Second answer", self.get())
        sessions = conversation_store.recent(self.root)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0]["turns"]), 2)
        self.assertIn("First answer", self.get("/?search=%231"))
        self.assertNotIn("Second answer", self.get("/?search=%231"))

    def test_export_import_restores_paper_and_marks_truncation(self) -> None:
        def fake_call(model, prompt, cfg, tag, system_prompt=""):
            return "Partial answer", {"actual_model": model, "finish_reason": "length", "status": 200}

        with patch.object(agent_core, "call_deepseek", side_effect=fake_call):
            self.get()
            first = self.upload({"q": "Explain the method", "model_choice": "deepseek-flash", "action": "ask"},
                                "demo.md", b"# Method\nThe paper uses copper tokens.", "paper_file", "/ask")
        self.assertIn("回答截断", first)
        original = conversation_store.recent(self.root)[0]
        with self.opener.open(self.base + "/export") as response:
            exported = response.read()
            self.assertIn("attachment", response.headers["Content-Disposition"])
        record = json.loads(exported)
        self.assertIn("copper tokens", record["paper"]["text"])
        self.assertEqual(record["session"]["turns"][0]["annotations"], ["回答截断"])
        self.assertEqual(record["session"]["turns"][0]["process"][-1]["key"], "processDone")
        self.post({}, "/new")
        imported_page = self.upload({}, "chat.json", exported, "session_file", "/import")
        restored = conversation_store.recent(self.root)[0]
        self.assertNotEqual(restored["session_id"], original["session_id"])
        self.assertEqual(restored["turns"][0]["answer"], "Partial answer")
        self.assertEqual(restored["turns"][0]["process"], record["session"]["turns"][0]["process"])
        self.assertIn("已导入 demo", re.sub(r"<[^>]+>", "", imported_page))
        self.assertIn("Partial answer", imported_page)
        self.assertIn("回答截断", imported_page)
        prompts = []

        def continued(model, prompt, cfg, tag, system_prompt=""):
            prompts.append(prompt)
            return "Continued answer", {"actual_model": model, "finish_reason": "stop", "status": 200}

        with patch.object(agent_core, "call_deepseek", side_effect=continued):
            continued_page = self.post({"q": "What about its limitation?", "model_choice": "deepseek-flash"})
        self.assertIn("Continued answer", continued_page)
        self.assertIn("Explain the method", prompts[0])
        self.assertIn("Partial answer", prompts[0])

    def test_sidebar_rename_and_delete_actions(self) -> None:
        first = conversation_store.create(self.root)
        first_page = self.get(f'/?session={first["session_id"]}')
        self.assertNotIn('class="session-menu"', first_page)

        renamed_page = self.post({"session_id": first["session_id"], "title": "  Reading notes  "}, "/rename")
        self.assertIn("Reading notes", renamed_page)
        self.assertIn('action="/rename"', renamed_page)
        self.assertIn('action="/delete"', renamed_page)
        self.assertEqual(conversation_store.load(self.root, first["session_id"])["title"], "Reading notes")
        conversation_store.append(self.root, first["session_id"], {"kind": "ask", "question": "First question", "answer": "Answer"})
        self.assertEqual(conversation_store.load(self.root, first["session_id"])["title"], "Reading notes")

        second = conversation_store.create(self.root)
        self.get(f'/?session={second["session_id"]}')
        after_other_delete = self.post({"session_id": first["session_id"]}, "/delete")
        self.assertNotIn("Reading notes", after_other_delete)
        with self.assertRaises(FileNotFoundError):
            conversation_store.load(self.root, first["session_id"])
        self.assertEqual(conversation_store.load(self.root, second["session_id"])["title"], "新对话")

        after_current_delete = self.post({"session_id": second["session_id"]}, "/delete")
        self.assertIn("新对话", after_current_delete)
        with self.assertRaises(FileNotFoundError):
            conversation_store.load(self.root, second["session_id"])
        self.assertEqual(len(conversation_store.recent(self.root)), 0)


if __name__ == "__main__":
    unittest.main()
