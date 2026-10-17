"""Collect one paper's verified metadata and deposited references."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from academic_metadata import collect_paper_info


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Collect metadata for one paper")
    parser.add_argument("query", help="Exact title, DOI, DOI URL, or arXiv ID")
    parser.add_argument("--output", type=Path, help="Write JSON to this file")
    args = parser.parse_args()
    try:
        result = collect_paper_info(args.query)
    except ValueError as error:
        parser.error(str(error))
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
