"""CLI entry point for the pipeline runner.

Usage:
    python -m forum_pipeline --code-dir ./output/ --stage extract
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from forum_pipeline.runner import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Forum Pipeline Runner")
    parser.add_argument("--code-dir", required=True, help="Directory with agent-generated code")
    parser.add_argument("--stage", default="extract", choices=["extract"], help="Pipeline stage to run")
    parser.add_argument("--output", help="Output file path for results JSON")
    args = parser.parse_args()

    code_dir = Path(args.code_dir)
    if not code_dir.exists():
        print(f"Error: code directory {code_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output) if args.output else None
    result = asyncio.run(run_pipeline(code_dir, stage=args.stage, output_path=output))

    if not result.get("success"):
        print(f"Pipeline failed: {result.get('errors', [])}", file=sys.stderr)
        sys.exit(1)

    print(f"Pipeline complete. Rows: {result.get('row_count', 0)}")


if __name__ == "__main__":
    main()
