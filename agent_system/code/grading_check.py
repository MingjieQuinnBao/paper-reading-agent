from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LECTURE = ROOT.parent
RESULTS = ROOT / "results"
REPORT = ROOT / "2023302111046_鲍明颉_任务3.md"


def check(name: str, ok: bool, evidence: str, points: int = 0) -> dict[str, Any]:
    return {"name": name, "passed": bool(ok), "evidence": evidence, "points": points if ok else 0}


def main() -> int:
    report_text = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    all_test = RESULTS / "all_tasks_test_report.json"
    all_passed = False
    if all_test.exists():
        test_data = json.loads(all_test.read_text(encoding="utf-8"))
        all_passed = (
            test_data.get("task3_1_and_3_2", {}).get("returncode") == 0
            and bool(test_data.get("task3_3_to_3_6", {}).get("all_passed"))
        )

    required_sections = ["任务概述", "操作记录", "产物清单", "问题与解决", "收获与反思"]
    required_outputs = [
        ROOT / "code" / "agent_core.py",
        ROOT / "code" / "poison_audit.py",
        ROOT / "screenshots" / "step3_real_ui_result.png",
        RESULTS / "acceptance_cases.json",
        RESULTS / "task3_3_poison_audit.json",
        RESULTS / "task3_4_replay_result.json",
        RESULTS / "task3_5_regression.json",
        RESULTS / "fresh_environment_test_report.json",
        ROOT / "reproduce.ps1",
    ]
    sensitive = [LECTURE / ".env", LECTURE / "api_key.txt", ROOT / ".env", ROOT / "api_key.txt"]
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", report_text))

    dimensions = [
        check("产物完整性", all(path.exists() for path in required_outputs), "源码、截图、验收、回放、回归和复现材料齐全", 5),
        check("操作可复现性", all_passed and (ROOT / "requirements.lock").exists(), "总验收与全新虚拟环境验收均通过", 2),
        check("问题解决能力", (ROOT / "问题解决记录.md").exists() and "变量隔离" in report_text, "包含问题、定位和解决方案", 1),
        check("反思与美观", all(title in report_text for title in required_sections) and (ROOT / "收获与反思.md").exists(), "结构完整、排版统一并含反思", 2),
    ]
    format_checks = [
        check("报告命名", REPORT.name == "2023302111046_鲍明颉_任务3.md", REPORT.name),
        check("约1000字", 800 <= chinese_chars <= 1500, f"中文字符数：{chinese_chars}"),
        check("关键证据", "screenshots/step3_real_ui_result.png" in report_text and "results/all_tasks_test_report.json" in report_text, "报告引用截图与机器可读验收结果"),
        check("敏感文件排除", not any(path.exists() for path in sensitive), "lecture3 范围内无 .env 或 api_key.txt"),
    ]
    bonus = [
        check("选做任务", all((RESULTS / name).exists() for name in ("task3_4_replay_result.json", "task3_5_regression.json", "fresh_environment_test_report.json")), "任务3.4、3.5、3.6均有证据", 1),
        check("创新模块", (ROOT / "code" / "grading_check.py").exists() and (RESULTS / "task3_3_variable_isolation.json").exists(), "变量隔离实验与自动评分自检", 1),
    ]
    base_score = sum(item["points"] for item in dimensions)
    bonus_score = sum(item["points"] for item in bonus)
    passed = all(item["passed"] for item in dimensions + format_checks)
    result = {
        "rubric": "课后实践记录验收标准",
        "expected_submission_name": "2023302111046_鲍明颉_任务3.zip",
        "dimensions": dimensions,
        "format_checks": format_checks,
        "bonus": bonus,
        "base_score_estimate": base_score,
        "bonus_evidence": bonus_score,
        "teacher_score_note": "以上为提交前自检，不替代教师最终评分。",
        "all_checks_passed": passed,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "grading_scorecard.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in dimensions + format_checks + bonus:
        print(f"{'PASS' if item['passed'] else 'FAIL'} {item['name']} - {item['evidence']}")
    print(f"基础分自检：{base_score}/10；加分证据：+{bonus_score}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
