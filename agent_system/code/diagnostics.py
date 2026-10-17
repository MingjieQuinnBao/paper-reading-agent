"""Log extraction and acceptance diagnostics."""

from __future__ import annotations

import json
import re
from typing import Any


def run_matrix(core) -> None:
    question = "I-JEPA为什么在表征空间预测而不是像素空间重建？"
    rows = []
    for model in ("mock-fast", "rule-reader", "deepseek-flash"):
        for temperature in (0.2, 0.8):
            result = core.answer_question(
                question,
                core.AgentConfig(model=model, route_mode="manual", temperature=temperature, top_p=0.9),
            )
            rows.append(
                {
                    "model": model,
                    "temperature": temperature,
                    "selected_model": result["selected_model"],
                    "answer_chars": len(result["answer"]),
                    "pages": [item["page"] for item in result["evidence"]],
                    "fallback": result["meta"].get("fallback"),
                }
            )
    core.dump_json(core.RESULTS / "model_parameter_matrix.json", rows)


def extract_call_chains(core) -> list[dict[str, Any]]:
    tags = {
        path.name.rsplit(".", 2)[0]
        for pattern in ("run-*.*.json", "paper-read-*.*.json")
        for path in core.LOGS.glob(pattern)
        if path.name.endswith((".trace.json", ".request.json", ".response.json", ".meta.json"))
        and not re.search(r"(?:-part\d+(?:-\d+)?(?:-retry)?|-retry|-repair(?:-retry)?)$", path.name.rsplit(".", 2)[0])
    }
    chains = []
    for tag in sorted(tags, key=lambda item: item.removeprefix("paper-read-").removeprefix("run-")):
        files = {kind: core.LOGS / f"{tag}.{kind}.json" for kind in ("trace", "request", "response", "meta")}
        trace = json.loads(files["trace"].read_text(encoding="utf-8")) if files["trace"].exists() else {}
        call_meta = json.loads(files["meta"].read_text(encoding="utf-8")) if files["meta"].exists() else {}
        kind = "paper_read" if tag.startswith("paper-read-") else "question_answer"
        config = trace.get("config", {})
        embedded_meta = trace.get("meta", {})
        selected_model = trace.get("selected_model") or call_meta.get("requested_model")
        actual_model = (embedded_meta.get("fallback") or call_meta.get("actual_model")
                        or trace.get("actual_model") or selected_model)
        if kind == "paper_read":
            steps = list(trace.get("steps", []))
            pages = trace.get("input_pages", [])
            paper_source = trace.get("paper_source") or config.get("paper_source")
        else:
            steps = [item.get("step") for item in trace.get("trace", []) if item.get("step")]
            pages = [item.get("page") for item in trace.get("evidence", [])]
            paper_source = config.get("paper_source") or trace.get("paper_summary", {}).get("paper_source")
            if call_meta and "llm_call" not in steps:
                steps.append("llm_call")  # 补全旧版日志中未单独记录的真实模型调用。
            if selected_model in {"rule-reader", "mock-fast"} and "offline_answer" not in steps:
                steps.append("offline_answer")
            if trace and "answer" not in steps:
                steps.append("answer")
        if not trace:
            steps = (["llm_call"] if files["request"].exists() or files["meta"].exists() else []) + ["trace_missing"]
        fallback = embedded_meta.get("fallback")
        status = ("incomplete" if not trace else "failed" if trace.get("status") == "failed"
                  else "fell_back" if fallback else "succeeded")
        chains.append({
            "run_id": tag,
            "kind": kind,
            "log_file": str(files["trace"].relative_to(core.ROOT)).replace("\\", "/") if files["trace"].exists() else None,
            "log_files": {name: str(path.relative_to(core.ROOT)).replace("\\", "/") for name, path in files.items() if path.exists()},
            "question": trace.get("question"),
            "paper_source": paper_source,
            "route_mode": config.get("route_mode"),
            "selected_model": selected_model,
            "actual_model": actual_model,
            "steps": steps,
            "pages": pages,
            "input_coverage": trace.get("input_coverage") or next((item.get("llm_input_coverage") for item in trace.get("trace", []) if item.get("llm_input_coverage")), None),
            "parameters": {name: config[name] for name in ("temperature", "top_p", "max_tokens") if name in config},
            "fallback": fallback,
            "error": trace.get("error") or embedded_meta.get("error"),
            "status": status,
            "http_status": call_meta.get("status"),
            "duration_seconds": call_meta.get("seconds"),
            "usage": call_meta.get("usage"),
        })
    core.dump_json(core.RESULTS / "call_chains.json", chains)
    return chains


def run_acceptance_cases(core) -> list[dict[str, Any]]:
    cases = [
        {
            "name": "normal_chain",
            "kind": "正常链路",
            "question": "概括I-JEPA的核心机制，并给出证据页码。",
            "config": core.AgentConfig(model="rule-reader", route_mode="manual", temperature=0.2),
            "expect": lambda r: bool(r["evidence"]) and "PDF第" in r["answer"],
        },
        {
            "name": "parameter_tuning",
            "kind": "参数调节",
            "question": "用更发散的方式解释I-JEPA为什么不重建像素。",
            "config": core.AgentConfig(model="mock-fast", route_mode="manual", temperature=0.9, top_p=0.6),
            "expect": lambda r: r["config"]["temperature"] == 0.9 and r["selected_model"] == "mock-fast",
        },
        {
            "name": "abnormal_input",
            "kind": "边界/异常输入",
            "question": "zzzz-no-hit-边界输入",
            "config": core.AgentConfig(model="rule-reader", route_mode="manual", evidence_limit=2),
            "expect": lambda r: isinstance(r["answer"], str) and len(r["answer"]) > 20,
        },
    ]
    rows = []
    for case in cases:
        result = core.answer_question(case["question"], case["config"])
        passed = bool(case["expect"](result))
        rows.append(
            {
                "case": case["name"],
                "kind": case["kind"],
                "passed": passed,
                "selected_model": result["selected_model"],
                "parameters": result["config"],
                "evidence_pages": [item["page"] for item in result["evidence"]],
                "log_steps": [item["step"] for item in result["trace"]],
                "judgement": "通过" if passed else "未通过/需优化",
            }
        )
    core.dump_json(core.RESULTS / "acceptance_cases.json", rows)
    chains = core.extract_call_chains()
    lines = [
        "# 任务3.2 交互应用验收报告",
        "",
        "## 用例判定",
        "",
    ]
    for row in rows:
        lines.append(f"- {row['kind']} `{row['case']}`：{row['judgement']}；模型 `{row['selected_model']}`；证据页码 {row['evidence_pages']}")
    lines += [
        "",
        "## 调用链路提取",
        "",
        f"已从日志中提取 {len(chains)} 条调用链路，详见 `results/call_chains.json`。",
        "",
        "## 总结",
        "",
        "系统可运行、能读取论文文本、能执行至少三类验收用例并给出判定。离线后端用于稳定验收，云模型后端在配置密钥后可接入。",
    ]
    (core.RESULTS / "acceptance_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


\n