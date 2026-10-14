from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agent_core


class PaperReadingTests(unittest.TestCase):
    def test_rejects_offline_backend_as_llm(self) -> None:
        with self.assertRaisesRegex(ValueError, "deepseek"):
            agent_core.read_paper_with_llm("ijepa", agent_core.AgentConfig(model="rule-reader"))

    def test_structured_reading_uses_paper_text_and_model_response(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, results, logs = (root / name for name in ("inputs", "results", "logs"))
            inputs.mkdir()
            (inputs / "sample.txt").write_text(
                "[PDF PAGE 1]\nAbstract: a new method.\n[PDF PAGE 2]\nExperiments show improvement.",
                encoding="utf-8",
            )
            generated = {
                "summary": "论文提出一种新方法。",
                "research_question": "如何改进方法？",
                "method": "使用新方法。",
                "experiments": "实验表明有改进。",
                "conclusions": "方法有效。",
                "limitations": "摘录未说明。",
                "evidence_pages": [1, 2],
            }
            with patch.object(agent_core, "INPUTS", inputs), \
                 patch.object(agent_core, "RESULTS", results), \
                 patch.object(agent_core, "LOGS", logs), \
                 patch.object(agent_core, "call_deepseek", return_value=(json.dumps(generated), {"actual_model": "deepseek-flash"})) as llm:
                result = agent_core.read_paper_with_llm("sample", agent_core.AgentConfig(model="deepseek-flash"))
            self.assertEqual(result["generated"], generated)
            self.assertEqual(result["generated_by"], "llm")
            self.assertEqual(result["input_pages"], [1, 2])
            self.assertEqual(result["input_coverage"], "full_text")
            self.assertIn("Experiments show improvement", llm.call_args.args[1])
            self.assertTrue((results / "paper_reading_sample.json").exists())

    def test_rejects_invalid_model_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "有效 JSON"):
            agent_core.parse_paper_reading("not JSON", [1])
        with self.assertRaisesRegex(ValueError, "证据页码"):
            agent_core.parse_paper_reading(json.dumps({
                "summary": "x", "research_question": "x", "method": "x",
                "experiments": "x", "conclusions": "x", "limitations": "x",
                "evidence_pages": [99],
            }), [1])

    def test_retries_truncated_json_without_rereading_paper(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, results, logs = (root / name for name in ("inputs", "results", "logs"))
            inputs.mkdir()
            (inputs / "sample.txt").write_text("[PDF PAGE 1]\nA concise research finding.", encoding="utf-8")
            generated = {
                "summary": "摘要", "research_question": "问题", "method": "方法",
                "experiments": "实验", "conclusions": "结论", "limitations": "局限",
                "evidence_pages": [1],
            }
            calls = []

            def fake_call(model, prompt, cfg, tag, system_prompt=""):
                calls.append((tag, cfg.max_tokens))
                if len(calls) == 1:
                    return '{"summary":', {"actual_model": model, "finish_reason": "length"}
                return json.dumps(generated, ensure_ascii=False), {"actual_model": model, "finish_reason": "stop"}

            with patch.object(agent_core, "INPUTS", inputs), patch.object(agent_core, "RESULTS", results), \
                 patch.object(agent_core, "LOGS", logs), patch.object(agent_core, "call_deepseek", side_effect=fake_call):
                result = agent_core.read_paper_with_llm("sample", agent_core.AgentConfig(model="deepseek-flash"))
            self.assertEqual(result["generated"], generated)
            self.assertEqual([limit for _, limit in calls], [2400, 4800])
            self.assertEqual(result["trace"].count("llm_call"), 2)

    def test_repairs_non_json_response_once(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, results, logs = (root / name for name in ("inputs", "results", "logs"))
            inputs.mkdir()
            (inputs / "sample.txt").write_text("[DOC SECTION 1]\nA paper.", encoding="utf-8")
            generated = {
                "summary": "摘要", "research_question": "问题", "method": "方法",
                "experiments": "实验", "conclusions": "结论", "limitations": "局限",
                "evidence_pages": [1],
            }
            responses = [
                ("Here is a summary", {"actual_model": "deepseek-flash", "finish_reason": "stop"}),
                (json.dumps(generated, ensure_ascii=False), {"actual_model": "deepseek-flash", "finish_reason": "stop"}),
            ]
            with patch.object(agent_core, "INPUTS", inputs), patch.object(agent_core, "RESULTS", results), \
                 patch.object(agent_core, "LOGS", logs), patch.object(agent_core, "call_deepseek", side_effect=responses):
                result = agent_core.read_paper_with_llm("sample", agent_core.AgentConfig(model="deepseek-flash"))
            self.assertIn("json_retry", result["trace"])
            self.assertEqual(result["generated"], generated)


if __name__ == "__main__":
    unittest.main()
