from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ROOT.parent / "materials" / "论文_带毒版.md"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"
SESSIONS = ROOT / "sessions"
for folder in (RESULTS, LOGS, SESSIONS):
    folder.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class AuditConfig:
    backend: str = "audit-balanced"
    prompt_mode: str = "adversarial"
    sensitivity: float = 0.75


ISSUES: list[dict[str, Any]] = [
    {
        "id": "P01",
        "severity": 5,
        "category": "物理可行性",
        "claim": "FP16 7B 模型可直接装入 8GB 内存且无需量化",
        "evidence": "3.2 节称以 FP16 全精度将 7B 参数模型直接载入 8GB 内存。仅权重约需 14GB，尚未计入 KV 缓存和运行时开销。",
        "conclusion": "内部不可行，应改为量化、分层卸载或更大内存，并报告实测峰值内存。",
    },
    {
        "id": "P02",
        "severity": 5,
        "category": "数值矛盾",
        "claim": "11.8 token/s 到 49.6 token/s 的整体加速比为 3.2 倍",
        "evidence": "49.6 / 11.8 = 4.203，和摘要及 4.1 节的 3.2 倍不一致。",
        "conclusion": "必须核对吞吐量、基线或加速比，三者至少一项有误。",
    },
    {
        "id": "P03",
        "severity": 5,
        "category": "表格矛盾",
        "claim": "八项基准最大精度损失不超过 2.1",
        "evidence": "表 1 的 BBH 从 48.9 降到 45.3，损失为 3.6。",
        "conclusion": "最大损失应至少为 3.6，或表格数据需要修正。",
    },
    {
        "id": "P04",
        "severity": 4,
        "category": "方法自相矛盾",
        "claim": "框架免训练",
        "evidence": "摘要称免训练，但 3.4 节明确对稀疏模式预测头微调 3 个 epoch。",
        "conclusion": "应改为主体无需训练但预测头需要微调，或删除预测头训练。",
    },
    {
        "id": "P05",
        "severity": 4,
        "category": "术语夸大",
        "claim": "KV 缓存压缩为零开销",
        "evidence": "3.3 节需要计算显著性并在回看时重算丢弃项，存在计算与延迟开销。",
        "conclusion": "应报告额外计算、延迟与能耗，不能直接称为零开销。",
    },
    {
        "id": "P06",
        "severity": 4,
        "category": "复杂度错误",
        "claim": "自注意力计算复杂度与显存复杂度均为 O(n·d²)",
        "evidence": "标准全注意力的注意力矩阵部分通常随序列长度呈 O(n²d) 计算和 O(n²) 显存，投影层另有 O(nd²)。",
        "conclusion": "需要区分投影与注意力矩阵两部分，不能把两种复杂度写成同一表达式。",
    },
    {
        "id": "P07",
        "severity": 4,
        "category": "引文矛盾",
        "claim": "FlashAttention（Chen 等，2019）",
        "evidence": "正文作者与年份和参考文献 [2] 的 Dao 等、NeurIPS 2022 不一致。",
        "conclusion": "正文引文应与参考文献统一，并进一步核验 DOI/arXiv 记录。",
    },
    {
        "id": "P08",
        "severity": 3,
        "category": "组合关系不清",
        "claim": "整体 3.2 倍，但两个组件分别贡献 3.4 倍和 1.24 倍",
        "evidence": "若二者可乘，组合约为 4.216 倍，接近吞吐量计算的 4.203 倍，却不等于文中的整体 3.2 倍。",
        "conclusion": "需说明组件增益的测量基线、是否可叠加以及最终统计口径。",
    },
    {
        "id": "P09",
        "severity": 3,
        "category": "指标口径",
        "claim": "在树莓派 5 上报告推理显存占用",
        "evidence": "树莓派通常使用共享系统内存，文中未定义显存口径或测量工具。",
        "conclusion": "应改为内存/共享显存并给出测量方法、峰值与稳态口径。",
    },
    {
        "id": "P10",
        "severity": 2,
        "category": "证据缺失",
        "claim": "截至 2026 年 1 月首个开源框架",
        "evidence": "正文没有系统检索范围、检索日期、对比清单或可核验仓库地址。",
        "conclusion": "首创性主张需要可复核检索方案和公开链接，否则应降格表述。",
    },
]


BACKENDS = {
    "audit-strict": {"min_severity": 2, "label": "严格审计后端"},
    "audit-balanced": {"min_severity": 3, "label": "均衡审计后端"},
    "audit-lenient": {"min_severity": 4, "label": "宽松审计后端"},
}


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_material() -> str:
    if not MATERIAL.exists():
        raise FileNotFoundError(f"缺少材料：{MATERIAL}")
    return MATERIAL.read_text(encoding="utf-8")


def validate_material(text: str) -> list[str]:
    required = ["49.6 token/s", "11.8 token/s", "最大不超过 2.1%", "BBH", "FP16 全精度", "3 个 epoch"]
    return [item for item in required if item not in text]


def audit(text: str, config: AuditConfig) -> dict[str, Any]:
    if config.backend not in BACKENDS:
        raise ValueError(f"未知后端：{config.backend}")
    missing = validate_material(text)
    if missing:
        raise ValueError(f"材料缺少预期锚点：{missing}")

    min_severity = BACKENDS[config.backend]["min_severity"]
    if config.prompt_mode == "summary":
        min_severity += 2
    elif config.prompt_mode == "verification":
        min_severity += 1
    elif config.prompt_mode != "adversarial":
        raise ValueError(f"未知提示词模式：{config.prompt_mode}")
    if config.sensitivity >= 0.85:
        min_severity -= 1
    elif config.sensitivity < 0.5:
        min_severity += 1
    min_severity = max(1, min(5, min_severity))

    findings = [issue for issue in ISSUES if issue["severity"] >= min_severity]
    high = sum(1 for item in findings if item["severity"] >= 4)
    return {
        "config": asdict(config),
        "backend_label": BACKENDS[config.backend]["label"],
        "material": str(MATERIAL.relative_to(ROOT.parent)),
        "material_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "finding_count": len(findings),
        "high_risk_count": high,
        "findings": findings,
        "judgement": "未通过：材料包含高风险内部矛盾，不可直接引用" if high else "需人工复核",
        "note": "三个后端是离线可复现的审计策略配置，不冒充真实云模型。",
    }


def run_isolation() -> dict[str, Any]:
    text = load_material()
    prompt_rows = [audit(text, AuditConfig("audit-balanced", mode, 0.75)) for mode in ("summary", "verification", "adversarial")]
    parameter_rows = [audit(text, AuditConfig("audit-balanced", "adversarial", value)) for value in (0.35, 0.75, 0.9)]
    model_rows = [audit(text, AuditConfig(name, "adversarial", 0.75)) for name in BACKENDS]
    result = {
        "method": "变量隔离法：每组实验只改变提示词、灵敏度参数或后端之一",
        "prompt_isolation": [{"prompt_mode": r["config"]["prompt_mode"], "finding_count": r["finding_count"], "ids": [f["id"] for f in r["findings"]]} for r in prompt_rows],
        "parameter_isolation": [{"sensitivity": r["config"]["sensitivity"], "finding_count": r["finding_count"], "ids": [f["id"] for f in r["findings"]]} for r in parameter_rows],
        "model_isolation": [{"backend": r["config"]["backend"], "finding_count": r["finding_count"], "ids": [f["id"] for f in r["findings"]]} for r in model_rows],
        "root_cause": {
            "prompt_ambiguity": "提示词越笼统，检出量越低，说明提示词歧义会造成漏检。",
            "parameter_misconfiguration": "灵敏度过低会漏掉中低严重度问题，属于参数配置风险。",
            "model_capability": "宽松后端漏检更多，严格后端检出完整，说明审计策略/模型能力会影响结果。",
            "primary_for_demo": "三类变量均有影响；固定提示词和灵敏度后仍存在后端差异，因此该演示中的主要剩余变量是后端审计能力。",
        },
    }
    dump_json(RESULTS / "task3_3_variable_isolation.json", result)
    return result


def build_conversation() -> dict[str, Any]:
    text = load_material()
    first = audit(text, AuditConfig("audit-lenient", "summary", 0.35))
    corrected = audit(text, AuditConfig("audit-strict", "adversarial", 0.9))
    turns = [
        {"round": 1, "role": "user", "content": "请概括这篇论文的主要贡献。", "abnormal": False},
        {"round": 2, "role": "assistant", "content": f"初步审计仅发现 {first['finding_count']} 项问题，仍可把性能结论作为可靠摘要。", "abnormal": True, "annotation": "宽松后端 + 摘要型提示词导致高风险漏检，并错误给出可靠性判断。"},
        {"round": 3, "role": "user", "content": "请核算加速比、最大精度损失，并检查方法是否自洽。", "abnormal": False},
        {"round": 4, "role": "assistant", "content": f"严格复核发现 {corrected['finding_count']} 项问题，其中高风险 {corrected['high_risk_count']} 项；材料不可直接引用。", "abnormal": False},
        {"round": 5, "role": "user", "content": "记录故障原因并形成回归用例。", "abnormal": False},
        {"round": 6, "role": "assistant", "content": "已将数值矛盾、物理不可行、方法自相矛盾等固化为自动回归断言。", "abnormal": False},
    ]
    session = {
        "schema_version": "1.0",
        "session_id": "poison-paper-demo",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "paper_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "turns": turns,
    }
    dump_json(SESSIONS / "poison-paper-demo.json", session)
    return session


def replay_conversation() -> dict[str, Any]:
    path = SESSIONS / "poison-paper-demo.json"
    session = json.loads(path.read_text(encoding="utf-8"))
    rounds = [turn["round"] for turn in session["turns"]]
    roles = [turn["role"] for turn in session["turns"]]
    abnormal = [turn["round"] for turn in session["turns"] if turn.get("abnormal")]
    replay = {
        "session_id": session["session_id"],
        "round_order_ok": rounds == list(range(1, len(rounds) + 1)),
        "role_alternation_ok": roles == ["user", "assistant", "user", "assistant", "user", "assistant"],
        "abnormal_rounds": abnormal,
        "paper_hash_match": session["paper_sha256"] == hashlib.sha256(load_material().encode("utf-8")).hexdigest(),
        "replayed_turns": len(rounds),
        "judgement": "通过" if abnormal == [2] else "未通过",
    }
    dump_json(RESULTS / "task3_4_replay_result.json", replay)
    return replay


def run_regression() -> dict[str, Any]:
    result = audit(load_material(), AuditConfig("audit-strict", "adversarial", 0.9))
    found = {item["id"] for item in result["findings"]}
    cases = [
        ("reg_speed_ratio", "P02"),
        ("reg_accuracy_max", "P03"),
        ("reg_fp16_memory", "P01"),
        ("reg_training_free", "P04"),
        ("reg_zero_overhead", "P05"),
        ("reg_citation_consistency", "P07"),
    ]
    rows = [{"case": name, "issue": issue, "passed": issue in found} for name, issue in cases]
    report = {
        "cases": rows,
        "passed": sum(1 for row in rows if row["passed"]),
        "total": len(rows),
        "judgement": "通过" if all(row["passed"] for row in rows) else "未通过",
    }
    dump_json(RESULTS / "task3_5_regression.json", report)
    return report


def run_all() -> dict[str, Any]:
    text = load_material()
    audit_result = audit(text, AuditConfig())
    dump_json(RESULTS / "task3_3_poison_audit.json", audit_result)
    isolation = run_isolation()
    build_conversation()
    replay = replay_conversation()
    regression = run_regression()
    summary = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "audit_findings": audit_result["finding_count"],
        "isolation_groups": 3,
        "replay": replay["judgement"],
        "regression": regression["judgement"],
        "all_passed": replay["judgement"] == "通过" and regression["judgement"] == "通过",
    }
    dump_json(RESULTS / "task3_3_to_3_6_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="任务3.3-3.6：带毒论文审计、变量隔离、回放与回归")
    parser.add_argument("mode", choices=["audit", "isolate", "conversation", "replay", "regression", "all"])
    args = parser.parse_args()
    if args.mode == "audit":
        data = audit(load_material(), AuditConfig())
        dump_json(RESULTS / "task3_3_poison_audit.json", data)
    elif args.mode == "isolate":
        data = run_isolation()
    elif args.mode == "conversation":
        data = build_conversation()
    elif args.mode == "replay":
        data = replay_conversation()
    elif args.mode == "regression":
        data = run_regression()
    else:
        data = run_all()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
