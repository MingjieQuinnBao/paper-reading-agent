from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from poison_audit import run_all as run_extensions


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def run_command(args: list[str]) -> dict[str, object]:
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=child_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=240,
    )
    return {
        "command": [sys.executable, *args],
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def main() -> int:
    base = run_command(["code/run_tests.py"])
    extensions = run_extensions()
    core_passed = base["returncode"] == 0 and bool(extensions["all_passed"])
    report = {
        "task3_1_and_3_2": base,
        "task3_3_to_3_6": extensions,
        "all_passed": core_passed,
    }
    (RESULTS / "all_tasks_test_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    grading = run_command(["code/grading_check.py"])
    report["grading_rubric_check"] = grading
    report["all_passed"] = core_passed and grading["returncode"] == 0
    (RESULTS / "all_tasks_test_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("PASS 任务3.1-3.2 基础验收" if base["returncode"] == 0 else "FAIL 任务3.1-3.2 基础验收")
    print("PASS 任务3.3-3.6 扩展验收" if extensions["all_passed"] else "FAIL 任务3.3-3.6 扩展验收")
    print("PASS 评分要点自检" if grading["returncode"] == 0 else "FAIL 评分要点自检")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
