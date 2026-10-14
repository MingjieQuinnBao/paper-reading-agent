from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import agent_core


class CallChainTests(unittest.TestCase):
    def test_extracts_question_and_paper_reading_with_actual_model(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            logs, results = root / "logs", root / "results"
            logs.mkdir()

            def save(name: str, data: dict) -> None:
                (logs / name).write_text(json.dumps(data), encoding="utf-8")

            save("run-old.trace.json", {
                "question": "What is the loss?", "selected_model": "deepseek-flash",
                "config": {"route_mode": "auto", "paper_source": "ijepa", "temperature": 0.2},
                "paper_summary": {"paper_source": "ijepa"},
                "evidence": [{"page": 4}],
                "trace": [{"step": "paper_input"}, {"step": "retrieve"}, {"step": "route"}],
                "meta": {"backend": "deepseek"},
            })
            save("run-old.meta.json", {"requested_model": "deepseek-flash", "actual_model": "deepseek-flash", "status": 200, "seconds": 1.2})
            save("run-old.request.json", {"prompt": "private paper text"})
            save("paper-read-good.trace.json", {
                "steps": ["paper_input", "full_text", "llm_call", "structured_parse"],
                "paper_source": "ijepa", "input_pages": [1, 2],
                "input_coverage": "full_text", "selected_model": "deepseek-flash",
                "actual_model": "deepseek-flash", "status": "succeeded",
            })
            save("paper-read-good.meta.json", {"requested_model": "deepseek-flash", "actual_model": "deepseek-flash", "status": 200})
            save("paper-read-incomplete.meta.json", {"requested_model": "deepseek-flash", "actual_model": "deepseek-flash", "status": 200})
            save("run-fallback.trace.json", {
                "question": "Q", "selected_model": "deepseek-v4-pro",
                "config": {"paper_source": "ijepa"}, "evidence": [],
                "trace": [{"step": "route"}, {"step": "fallback"}, {"step": "answer"}],
                "meta": {"fallback": "rule-reader", "error": "API unavailable"},
            })
            with patch.object(agent_core, "ROOT", root), patch.object(agent_core, "LOGS", logs), patch.object(agent_core, "RESULTS", results):
                chains = agent_core.extract_call_chains()
            by_id = {row["run_id"]: row for row in chains}
            self.assertEqual(len(chains), 4)
            self.assertEqual(by_id["run-old"]["actual_model"], "deepseek-flash")
            self.assertIn("llm_call", by_id["run-old"]["steps"])
            self.assertEqual(by_id["run-old"]["pages"], [4])
            self.assertEqual(by_id["paper-read-good"]["kind"], "paper_read")
            self.assertEqual(by_id["paper-read-good"]["steps"][-1], "structured_parse")
            self.assertEqual(by_id["paper-read-incomplete"]["status"], "incomplete")
            self.assertEqual(by_id["run-fallback"]["status"], "fell_back")
            self.assertEqual(by_id["run-fallback"]["actual_model"], "rule-reader")
            self.assertNotIn("private paper text", json.dumps(chains))
            self.assertTrue((results / "call_chains.json").exists())

    def test_ui_uses_simplified_chinese_and_preserves_form_state(self) -> None:
        cfg = agent_core.AgentConfig(model="rule-reader", route_mode="manual", temperature=0.8)
        page = agent_core.render_page("<p>结果</p>", cfg, "新的问题", "论文内容")
        self.assertIn("导入文件", page)
        self.assertIn("粘贴正文", page)
        self.assertIn("新的问题</textarea>", page)
        self.assertIn("论文内容</textarea>", page)
        self.assertIn('value="rule-reader" selected', page)
        self.assertIn('value="0.8"', page)
        self.assertNotIn("当前论文", page)
        self.assertNotIn("查看调用链", page)
        self.assertNotIn("自动模式会优先", page)

    def test_new_llm_answer_records_call_and_is_visible_in_chain_view(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, logs, results = (root / name for name in ("inputs", "logs", "results"))
            inputs.mkdir()
            (inputs / "sample.txt").write_text("[PDF PAGE 1]\nThe training loss is an L2 distance.", encoding="utf-8")
            cfg = agent_core.AgentConfig(model="deepseek-flash", route_mode="manual", paper_source="sample")
            with patch.object(agent_core, "ROOT", root), patch.object(agent_core, "INPUTS", inputs), \
                 patch.object(agent_core, "LOGS", logs), patch.object(agent_core, "RESULTS", results), \
                 patch.object(agent_core, "call_deepseek", return_value=("The loss is L2 (PDF page 1).", {"actual_model": "deepseek-flash", "status": 200})):
                answer = agent_core.answer_question("How is loss computed?", cfg)
                chains = agent_core.extract_call_chains()
            self.assertEqual([item["step"] for item in answer["trace"]][-2:], ["llm_call", "answer"])
            self.assertEqual(chains[0]["actual_model"], "deepseek-flash")
            self.assertIn("调用 LLM", agent_core.render_call_chain_list(chains))
            self.assertIn("运行详情", agent_core.render_result(answer))
            self.assertIn("历史记录", agent_core.render_result(answer))

    def test_logs_page_serves_simplified_chinese_chain(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            logs, results = root / "logs", root / "results"
            logs.mkdir()
            (logs / "paper-read-20261013-010000.trace.json").write_text(json.dumps({
                "steps": ["paper_input", "full_text", "llm_call", "structured_parse"],
                "paper_source": "ijepa", "input_pages": [1],
                "selected_model": "deepseek-flash", "actual_model": "deepseek-flash",
            }), encoding="utf-8")
            with patch.object(agent_core, "ROOT", root), patch.object(agent_core, "LOGS", logs), \
                 patch.object(agent_core, "RESULTS", results), patch.object(agent_core, "deepseek_api_key", return_value=""):
                server = agent_core.ThreadingHTTPServer(("127.0.0.1", 0), agent_core.AgentHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/logs") as response:
                        page = response.read().decode("utf-8")
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)
            self.assertIn("历史记录", page)
            self.assertIn('href="/">返回阅读', page)
            self.assertIn("整篇论文摘要", page)
            self.assertIn("调用 LLM", page)


if __name__ == "__main__":
    unittest.main()
