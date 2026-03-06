"""CLI entry point: python -m forum_pipeline"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from forum_pipeline.runner import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Forum E-C-T-V-L-N Pipeline Runner")
    parser.add_argument(
        "--code-dir", type=str, required=True,
        help="Path to agent-generated code artifacts",
    )
    parser.add_argument(
        "--stage", type=str, default=None,
        help="Stage(s) to run: all, extract, cleanse, transform, validate, load, notify, "
             "or comma-separated (e.g., cleanse,transform,validate). "
             "Falls back to STAGE env var, then 'all'.",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output path for results JSON",
    )

    args = parser.parse_args()
    code_dir = Path(args.code_dir)
    if not code_dir.exists():
        print(f"Error: code directory does not exist: {code_dir}", file=sys.stderr)
        sys.exit(1)

    # CLI --stage takes priority, then STAGE env var, then 'all'
    stage = args.stage or os.environ.get("STAGE", "all")
    output = Path(args.output) if args.output else None
    result = asyncio.run(run_pipeline(code_dir, stage=stage, output_path=output))

    if result.get("success"):
        print(f"Pipeline complete. Rows: {result.get('row_count', 0)}")
        if result.get("warnings"):
            for w in result["warnings"]:
                print(f"  Warning: [{w.get('code')}] {w.get('message')}", file=sys.stderr)
    else:
        print("Pipeline FAILED.", file=sys.stderr)
        for err in result.get("errors", []):
            print(f"  Error: [{err.get('code')}] {err.get('message')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
