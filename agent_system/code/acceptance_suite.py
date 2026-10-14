"""Run and record the three task 3.2 interactive acceptance categories."""

from __future__ import annotations

import difflib
import json
import threading
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

import agent_core as agent


PAPER = agent.ROOT.parent / "materials" / "论文_带毒版.md"
REPORT = agent.RESULTS / "interactive_acceptance.json"


def post(opener: urllib.request.OpenerDirector, base: str, fields: dict[str, str], upload: Path | None = None) -> str:
    boundary = "----paper-agent-acceptance"
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
        )
    if upload:
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="paper_file"; '
            f'filename="{upload.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode("utf-8")
            + upload.read_bytes() + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    request = urllib.request.Request(
        base + "/ask", data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with opener.open(request, timeout=180) as response:
        if response.status != 200:
            raise RuntimeError(f"界面返回 HTTP {response.status}")
        return response.read().decode("utf-8")


def latest_answer(question: str) -> dict[str, Any]:
    result = json.loads((agent.RESULTS / "last_answer.json").read_text(encoding="utf-8"))
    if result.get("question") != question:
        raise AssertionError("未产生与本用例对应的回答。")
    return result


def request_parameters(run_id: str) -> dict[str, Any]:
    payload = json.loads((agent.LOGS / f"{run_id}.request.json").read_text(encoding="utf-8"))
    return {name: payload[name] for name in ("model", "temperature", "top_p", "max_tokens")}


def record(
    rows: list[dict[str, Any]], case_id: str, category: str, input_description: str,
    expected: str, passed: bool, actual: str, evidence: dict[str, Any] | None = None,
    judgement: str | None = None,
) -> None:
    rows.append({
        "case": case_id,
        "category": category,
        "input": input_description,
        "expected": expected,
        "actual": actual,
        "evidence": evidence or {},
        "judgement": judgement or ("通过" if passed else "未通过"),
        "passed": passed,
    })


def run() -> dict[str, Any]:
    if not PAPER.is_file():
        raise FileNotFoundError(f"验收论文不存在：{PAPER}")
    if not agent.deepseek_api_key():
        raise RuntimeError("真实模型验收需要 DEEPSEEK_API_KEY。")

    rows: list[dict[str, Any]] = []
    previous_answers = {
        path: path.read_bytes() if path.exists() else None
        for path in (agent.RESULTS / "last_answer.json", agent.RESULTS / "last_answer.md")
    }
    server = agent.ThreadingHTTPServer(("127.0.0.1", 0), agent.AgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cookies = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    existing_sessions = {path.stem for path in (agent.ROOT / "sessions").glob("*.json")}
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        question = "EdgeSparse 的核心方法是什么？请给出文档位置。"
        page = post(opener, base, {
            "q": question, "action": "ask", "model_choice": "deepseek-flash",
            "temperature": "0.2", "top_p": "0.9",
        }, PAPER)
        answer = latest_answer(question)
        trace_steps = [item["step"] for item in answer["trace"]]
        normal_ok = all((
            "执行失败" not in page,
            answer["paper_summary"]["display_name"] == PAPER.stem,
            answer["selected_model"] == "deepseek-flash",
            answer["meta"].get("actual_model") == "deepseek-flash",
            answer["meta"].get("finish_reason") == "stop",
            not answer["meta"].get("fallback"),
            bool(answer["evidence"]),
            "EdgeSparse" in answer["answer"],
            "文档第" in answer["answer"] or "DOC SECTION" in answer["answer"],
            trace_steps[:4] == ["paper_input", "plan", "retrieve", "route"],
            "llm_call" in trace_steps and trace_steps[-1] == "answer",
        ))
        record(rows, "normal_chain", "正常链路", f"网页导入 {PAPER.name}，使用 DeepSeek 回答：{question}",
               "导入、检索、模型调用、回答和证据位置均成功，且无离线降级。", normal_ok,
               f"实际后端 {answer['meta'].get('actual_model') or answer['meta'].get('fallback')}；证据位置 "
               f"{[item['label'] for item in answer['evidence']]}；轨迹 {trace_steps}。",
               {"run_id": answer["run_id"], "trace_log": f"logs/{answer['run_id']}.trace.json",
                "model_meta": f"logs/{answer['run_id']}.meta.json"})

        tune_question = "这篇论文报告了哪些性能数字？数字之间是否一致？"
        samples = []
        for label, temperature, top_p in (("low", 0.2, 0.9), ("high", 0.9, 0.6)):
            page = post(opener, base, {
                "q": tune_question, "action": "ask", "model_choice": "deepseek-flash",
                "temperature": str(temperature), "top_p": str(top_p), "max_tokens": "2400",
            })
            result = latest_answer(tune_question)
            parameters = request_parameters(result["run_id"])
            samples.append({
                "label": label, "run_id": result["run_id"], "parameters": parameters,
                "actual_model": result["meta"].get("actual_model"),
                "fallback": result["meta"].get("fallback"),
                "finish_reason": result["meta"].get("finish_reason"),
                "answer": result["answer"], "ui_error": "执行失败" in page,
            })
        similarity = round(difflib.SequenceMatcher(None, samples[0]["answer"], samples[1]["answer"]).ratio(), 3)
        tune_transport_ok = all(
            not sample["ui_error"] and not sample["fallback"] and sample["actual_model"] == "deepseek-flash"
            for sample in samples
        ) and samples[0]["parameters"]["temperature"] == 0.2 \
            and samples[0]["parameters"]["top_p"] == 0.9 \
            and samples[1]["parameters"]["temperature"] == 0.9 \
            and samples[1]["parameters"]["top_p"] == 0.6 \
            and all(sample["parameters"]["max_tokens"] == 2400 for sample in samples)
        tune_ok = tune_transport_ok and all(sample["finish_reason"] == "stop" for sample in samples)
        tune_judgement = "通过" if tune_ok else "需优化" if tune_transport_ok else "未通过"
        record(rows, "parameter_tuning", "参数调节", f"同一问题两次调用：{tune_question}；参数分别为 "
               "temperature/top_p=0.2/0.9 与 0.9/0.6。",
               "两组参数进入真实 API 请求，均得到完整云模型回答；记录输出差异，不要求随机生成结果必然不同。",
               tune_ok,
               f"两次回答长度 {len(samples[0]['answer'])}/{len(samples[1]['answer'])} 字符；"
               f"文本相似度 {similarity}；内容{'不同' if samples[0]['answer'] != samples[1]['answer'] else '相同'}；"
               f"结束原因 {[sample['finish_reason'] for sample in samples]}。"
               + (" 输出达到 max_tokens=2400，仍需优化。" if tune_transport_ok and not tune_ok else ""),
               {"runs": [{key: value for key, value in sample.items() if key != "answer"} for sample in samples],
                "answer_excerpts": [sample["answer"][:300] for sample in samples]},
               judgement=tune_judgement)

        blank_page = post(opener, base, {"q": "", "action": "ask", "model_choice": "rule-reader"})
        blank_ok = "请先输入问题" in blank_page and "已导入" in blank_page
        record(rows, "empty_question", "边界与异常输入", "已导入论文后提交空问题。",
               "界面给出可理解的错误，论文保持已导入状态。", blank_ok,
               "显示空问题提示，论文状态保留。" if blank_ok else "提示或论文状态不符合预期。")

        bad_file = agent.RESULTS / "acceptance-invalid.exe"
        bad_file.write_bytes(b"not a paper")
        try:
            invalid_page = post(opener, base, {"q": "测试非法文件", "action": "ask", "model_choice": "rule-reader"}, bad_file)
        finally:
            bad_file.unlink(missing_ok=True)
        invalid_ok = "仅支持 .txt、.md 和可提取文字的 .pdf" in invalid_page and "已导入" in invalid_page
        record(rows, "unsupported_file", "边界与异常输入", "上传扩展名为 .exe 的非论文文件。",
               "拒绝不支持的格式，保留原论文。", invalid_ok,
               "显示格式错误，论文状态保留。" if invalid_ok else "格式错误未按预期处理。")

        no_hit_question = "zzzxxyyqq987654"
        no_hit_page = post(opener, base, {"q": no_hit_question, "action": "ask", "model_choice": "rule-reader"})
        no_hit = latest_answer(no_hit_question)
        no_hit_ok = (
            "未找到直接匹配" in no_hit_page
            and no_hit["selected_model"] == "rule-reader"
            and all(item["score"] == 0 for item in no_hit["evidence"])
            and "未找到直接匹配" in no_hit["answer"]
        )
        record(rows, "no_matching_evidence", "边界与异常输入", "提交与论文无关的随机字符串问题。",
               "离线检索明确标记无直接匹配，不伪造证据。", no_hit_ok,
               f"证据分数 {[item['score'] for item in no_hit['evidence']]}；后端 {no_hit['selected_model']}。",
               {"run_id": no_hit["run_id"], "trace_log": f"logs/{no_hit['run_id']}.trace.json"})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        for path, old_content in previous_answers.items():
            if old_content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(old_content)
        for cookie in cookies:
            if cookie.name == "session_id" and cookie.value not in existing_sessions \
                    and agent.conversations.ID_PATTERN.fullmatch(cookie.value):
                (agent.ROOT / "sessions" / f"{cookie.value}.json").unlink(missing_ok=True)

    category_results = {}
    for category in ("正常链路", "参数调节", "边界与异常输入"):
        subset = [row for row in rows if row["category"] == category]
        category_results[category] = (
            "通过" if subset and all(row["passed"] for row in subset)
            else "未通过" if any(row["judgement"] == "未通过" for row in subset)
            else "需优化"
        )
    report = {
        "paper": PAPER.name,
        "mode": "local_http_ui_with_live_deepseek",
        "criteria": "按正常链路、参数调节、边界与异常输入逐项验收；每项含预期、实际、证据和判定。",
        "cases": rows,
        "categories": category_results,
        "summary": {
            "passed": sum(row["judgement"] == "通过" for row in rows),
            "needs_optimization": sum(row["judgement"] == "需优化" for row in rows),
            "failed": sum(row["judgement"] == "未通过" for row in rows),
            "total": len(rows),
        },
    }
    agent.dump_json(REPORT, report)
    agent.extract_call_chains()
    return report


if __name__ == "__main__":
    result = run()
    for row in result["cases"]:
        print(f"{row['judgement']} {row['category']} {row['case']}")
    print(f"结果：{result['summary']['passed']} 通过，{result['summary']['needs_optimization']} 需优化，"
          f"{result['summary']['failed']} 未通过；详见 {REPORT}")
