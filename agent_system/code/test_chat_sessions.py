from __future__ import annotations

import json
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
            "<script>alert(1)</script> [unsafe](javascript:alert(1))"
        )
        self.assertIn("<h2>Summary</h2>", rendered)
        self.assertIn("<strong>Finding</strong>", rendered)
        self.assertIn("<pre><code>", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn('href="javascript:', rendered)

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
        self.post({}, "/new")
        imported_page = self.upload({}, "chat.json", exported, "session_file", "/import")
        restored = conversation_store.recent(self.root)[0]
        self.assertNotEqual(restored["session_id"], original["session_id"])
        self.assertEqual(restored["turns"][0]["answer"], "Partial answer")
        self.assertIn("已导入 demo", imported_page)
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
        self.assertIn('class="session-menu"', first_page)
        self.assertIn('action="/rename"', first_page)
        self.assertIn('action="/delete"', first_page)

        renamed_page = self.post({"session_id": first["session_id"], "title": "  Reading notes  "}, "/rename")
        self.assertIn("Reading notes", renamed_page)
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
        self.assertEqual(len(conversation_store.recent(self.root)), 1)


if __name__ == "__main__":
    unittest.main()
