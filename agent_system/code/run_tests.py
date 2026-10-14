from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code" / "agent_core.py"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CODE), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
    )


def main() -> int:
    checks = []
    ask = run(["ask", "--model", "rule-reader", "--route-mode", "manual"])
    answer_path = ROOT / "results" / "last_answer.json"
    answer = json.loads(answer_path.read_text(encoding="utf-8")) if ask.returncode == 0 and answer_path.exists() else {}
    checks.append({"name": "manual rule-reader ask", "ok": ask.returncode == 0 and answer.get("selected_model") == "rule-reader" and bool(answer.get("evidence")) and "PDF第" in ask.stdout, "stdout": ask.stdout[-500:], "stderr": ask.stderr[-500:]})
    steps = [step.get("step") for step in answer.get("trace", [])]
    checks.append({"name": "agent execution trace", "ok": steps[:4] == ["paper_input", "plan", "retrieve", "route"] and steps[-2:] == ["offline_answer", "answer"], "steps": steps})
    mock = run(["ask", "--model", "mock-fast", "--route-mode", "manual", "--temperature", "0.8"])
    mock_answer = json.loads(answer_path.read_text(encoding="utf-8")) if mock.returncode == 0 and answer_path.exists() else {}
    checks.append({"name": "manual mock-fast ask and parameter capture", "ok": mock.returncode == 0 and mock_answer.get("selected_model") == "mock-fast" and mock_answer.get("config", {}).get("temperature") == 0.8 and "mock-fast" in mock.stdout, "stdout": mock.stdout[-500:], "stderr": mock.stderr[-500:]})
    matrix = run(["matrix"])
    matrix_path = ROOT / "results" / "model_parameter_matrix.json"
    rows = json.loads(matrix_path.read_text(encoding="utf-8")) if matrix_path.exists() else []
    expected = {(model, temperature) for model in ("mock-fast", "rule-reader", "deepseek-flash") for temperature in (0.2, 0.8)}
    observed = {(row.get("model"), row.get("temperature")) for row in rows}
    checks.append({"name": "model and parameter matrix", "ok": matrix.returncode == 0 and observed == expected and all(row.get("selected_model") == row.get("model") for row in rows), "rows": len(rows), "fallbacks": [row.get("model") for row in rows if row.get("fallback")], "stderr": matrix.stderr[-500:]})
    paper = run(["paper", "--paper-source", "ijepa"])
    checks.append({"name": "paper input processing", "ok": paper.returncode == 0 and "detected_sections" in paper.stdout, "stdout": paper.stdout[-500:], "stderr": paper.stderr[-500:]})
    validate = run(["validate"])
    acceptance_path = ROOT / "results" / "acceptance_cases.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8")) if acceptance_path.exists() else []
    checks.append({"name": "three acceptance cases", "ok": validate.returncode == 0 and len(acceptance) == 3 and all(item["passed"] for item in acceptance), "stdout": validate.stdout[-500:], "stderr": validate.stderr[-500:]})
    chains_path = ROOT / "results" / "call_chains.json"
    chains = json.loads(chains_path.read_text(encoding="utf-8")) if chains_path.exists() else []
    checks.append({"name": "log call-chain extraction", "ok": len(chains) >= 3, "rows": len(chains)})
    (ROOT / "results" / "test_report.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in checks:
        print(f"{'PASS' if item['ok'] else 'FAIL'} {item['name']}")
    return 0 if all(item["ok"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
