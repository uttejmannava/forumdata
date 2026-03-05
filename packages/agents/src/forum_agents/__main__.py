"""CLI entry point for the orchestrator.

Usage:
    python -m forum_agents --url <url> --description <desc> [--output <dir>]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from forum_agents.orchestrator import run_setup


def main() -> None:
    parser = argparse.ArgumentParser(description="Forum Agent — pipeline setup")
    parser.add_argument("--url", required=True, help="Source URL to extract from")
    parser.add_argument("--description", required=True, help="What data to extract")
    parser.add_argument("--output", default="./output", help="Output directory for artifacts")
    parser.add_argument("--schema", help="Path to existing schema JSON file")
    args = parser.parse_args()

    result = asyncio.run(run_setup(args.url, args.description, args.output, args.schema))

    status = result.get("status", "unknown")
    errors = result.get("errors", [])

    if status == "complete":
        print(f"Setup complete. Artifacts written to {args.output}/")
        ext = result.get("extraction_result") or {}
        print(f"  Rows extracted: {ext.get('row_count', 0)}")
        print(f"  Navigation mode: {result.get('navigation_mode', 'unknown')}")
        print(f"  Stealth level: {result.get('stealth_level', 'unknown')}")
    else:
        print(f"Setup failed with status: {status}", file=sys.stderr)
        for err in errors:
            print(f"  Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
