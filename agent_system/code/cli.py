"""Command line entry point for the Paper Reading Agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(core) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["ask", "matrix", "server", "validate", "logs", "paper", "read", "import"])
    parser.add_argument("--question", default="概括这篇论文的研究问题、方法和主要结果，并给出证据位置。")
    parser.add_argument("--model", default="rule-reader")
    parser.add_argument("--route-mode", default="auto")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=2400)
    parser.add_argument("--paper-source", default="ijepa")
    parser.add_argument("--paper-file")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    if args.paper_file and args.mode in {"ask", "read", "paper", "import"}:
        args.paper_source = core.ingest_paper_file(Path(args.paper_file))["source_id"]
    if args.mode == "server":
        core.run_server(args.port)
    elif args.mode == "import":
        if not args.paper_file:
            parser.error("import 模式需要 --paper-file")
        print(json.dumps(core.paper_metadata(args.paper_source), ensure_ascii=False, indent=2))
    elif args.mode == "matrix":
        core.run_matrix()
        print("完成：results/model_parameter_matrix.json")
    elif args.mode == "validate":
        rows = core.run_acceptance_cases()
        for row in rows:
            print(f"{row['judgement']} {row['kind']} {row['case']}")
    elif args.mode == "logs":
        chains = core.extract_call_chains()
        print(f"完成：提取 {len(chains)} 条调用链路到 results/call_chains.json")
    elif args.mode in {"paper", "read"}:
        if args.mode == "read":
            result = core.read_paper_with_llm(
                args.paper_source,
                core.AgentConfig(model=args.model, temperature=args.temperature, top_p=args.top_p,
                            max_tokens=args.max_tokens, paper_source=args.paper_source),
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            summary = core.summarize_paper_input(args.paper_source)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        result = core.answer_question(
            args.question,
            core.AgentConfig(
                model=args.model,
                route_mode=args.route_mode,
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
                paper_source=args.paper_source,
            ),
        )
        print(result["answer"])

\n