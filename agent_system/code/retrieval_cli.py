"""Standalone command line interface for reusable multi-source search."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from web_research.tool import search


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Search and normalize web/academic sources")
    parser.add_argument("query", help="Search text, DOI, or arXiv ID")
    parser.add_argument("--providers", default="Tavily,Bocha,Crossref,arXiv",
                        help="Comma-separated sources: Tavily, Bocha, Crossref, arXiv")
    parser.add_argument("--mode", choices=("quick", "deep"), default="quick")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", type=Path, help="Write JSON to this path (default: stdout)")
    args = parser.parse_args()
    try:
        result = search(args.query, mode=args.mode, limit=args.limit, providers=args.providers)
    except ValueError as error:
        parser.error(str(error))
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(content + "\n", encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
