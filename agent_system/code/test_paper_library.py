from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import agent_core


class PaperLibraryTests(unittest.TestCase):
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

    def test_imports_poison_markdown_as_separate_paper(self) -> None:
        paper = Path(__file__).resolve().parents[2] / "materials" / "论文_带毒版.md"
        metadata = agent_core.ingest_paper_file(paper)
        self.assertEqual(metadata["format"], "md")
        self.assertEqual(metadata["location_type"], "section")
        self.assertIn("EdgeSparse", agent_core.read_paper_text(metadata["source_id"]))
        cfg = agent_core.AgentConfig(model="rule-reader", route_mode="manual", paper_source=metadata["source_id"])
        answer = agent_core.answer_question("EdgeSparse 的吞吐量数字是什么？", cfg)
        self.assertEqual(answer["paper_summary"]["display_name"], "论文_带毒版")
        self.assertIn("EdgeSparse", answer["answer"])
        self.assertIn("文档第", answer["answer"])
        self.assertNotIn("I-JEPA", answer["answer"])

    def test_imports_another_text_pdf_with_real_page_markers(self) -> None:
        paper = Path(__file__).resolve().parents[1] / "inputs" / "2022_LeCun_Autonomous_Machine_Intelligence.pdf"
        if not paper.is_file():
            self.skipTest("Optional local PDF fixture is not available")
        metadata = agent_core.ingest_paper_file(paper)
        self.assertEqual(metadata["format"], "pdf")
        self.assertEqual(metadata["location_type"], "pdf")
        self.assertGreater(metadata["locations"], 1)
        self.assertIn("[PDF PAGE 2]", agent_core.read_paper_text(metadata["source_id"]))

    def test_long_paper_reaches_last_section(self) -> None:
        text = "# Beginning\n" + "A" * 100000 + "\n# Ending\nUNIQUE-END-EVIDENCE"
        source = agent_core.ingest_paper_bytes("long.md", text.encode())["source_id"]
        chunks, pages = agent_core.paper_chunks(source)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(pages, [1, 2])
        self.assertIn("UNIQUE-END-EVIDENCE", chunks[-1])
        calls = []

        def fake_llm(model, prompt, cfg, tag, system_prompt=""):
            calls.append((tag, prompt))
            return "依据末节证据回答（文档第2节）。", {"actual_model": model, "status": 200}

        cfg = agent_core.AgentConfig(model="deepseek-flash", route_mode="manual", paper_source=source)
        with patch.object(agent_core, "call_deepseek", side_effect=fake_llm):
            result = agent_core.answer_question("末节有什么？", cfg)
        self.assertEqual(len(calls), len(chunks) + 1)
        self.assertTrue(any("UNIQUE-END-EVIDENCE" in prompt for _, prompt in calls))
        self.assertEqual(result["trace"][2]["llm_input_coverage"], "chunked_full_text")
        self.assertEqual(len(agent_core.extract_call_chains()), 1)

    def test_chunked_structured_reading_renders_in_chinese(self) -> None:
        source = agent_core.ingest_paper_bytes(
            "long.md", ("# Introduction\n" + "A" * 100000 + "\n# Results\nFINAL-EVIDENCE").encode(),
        )["source_id"]
        generated = {
            "summary": "全文摘要", "research_question": "研究问题", "method": "方法说明",
            "experiments": "实验结果", "conclusions": "最终结论", "limitations": "局限说明",
            "evidence_pages": [2],
        }

        def fake_llm(model, prompt, cfg, tag, system_prompt=""):
            return (json.dumps(generated, ensure_ascii=False) if tag.startswith("paper-read-") and "-part" not in tag
                    else "末节证据：文档第2节。", {"actual_model": model, "status": 200})

        with patch.object(agent_core, "call_deepseek", side_effect=fake_llm):
            result = agent_core.read_paper_with_llm(source, agent_core.AgentConfig(model="deepseek-flash"))
        self.assertEqual(result["input_coverage"], "chunked_full_text")
        rendered = agent_core.render_paper_reading(result)
        self.assertIn("全文摘要", rendered)
        self.assertIn("文档第2节", rendered)

    def test_ui_upload_then_ask_again_and_return_from_logs(self) -> None:
        with patch.object(agent_core, "deepseek_api_key", return_value=""):
            server = agent_core.ThreadingHTTPServer(("127.0.0.1", 0), agent_core.AgentHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                boundary = "----paper-test-boundary"
                fields = {"q": "What is the method?", "model": "rule-reader", "route_mode": "manual", "action": "ask"}
                pieces = []
                for key, value in fields.items():
                    pieces.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
                pieces.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"paper_file\"; filename=\"new.md\"\r\nContent-Type: text/markdown\r\n\r\n".encode() + b"# Novel Method\nA new paper uses copper tokens.\r\n")
                pieces.append(f"--{boundary}--\r\n".encode())
                req = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/ask", data=b"".join(pieces),
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                )
                with urllib.request.urlopen(req) as response:
                    page = response.read().decode("utf-8")
                    cookie = response.headers["Set-Cookie"].split(";", 1)[0]
                second_req = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/ask",
                    data=b"q=What+are+copper+tokens%3F&model_choice=rule-reader&action=ask",
                    headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie},
                )
                with urllib.request.urlopen(second_req) as response:
                    second_page = response.read().decode("utf-8")
                with urllib.request.urlopen(urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/logs", headers={"Cookie": cookie},
                )) as response:
                    logs_page = response.read().decode("utf-8")
                with urllib.request.urlopen(urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/", headers={"Cookie": cookie},
                )) as response:
                    returned_page = response.read().decode("utf-8")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
        source = next(iter(json.loads((self.root / "inputs" / "catalog.json").read_text(encoding="utf-8"))))
        self.assertIn("已导入 new", page)
        self.assertIn(f"paper_source={source}", cookie)
        self.assertIn("copper tokens", page)
        self.assertIn("copper tokens", second_page)
        self.assertIn('href="/">返回阅读', logs_page)
        self.assertIn("已导入 new", returned_page)
        self.assertNotIn("当前论文", returned_page)
        self.assertNotIn("执行失败", page)


if __name__ == "__main__":
    unittest.main()
