"""Minimal pipeline runner for local testing of agent-generated extraction code.

Usage:
    python -m forum_pipeline.runner --code-dir ./output/ --stage extract
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forum_browser.browser import BrowserConfig, ForumBrowser

from forum_schemas.models.pipeline import StealthLevel

from forum_pipeline.context import RunContext
from forum_pipeline.stages.extract import run_extract, run_navigate, validate_output


async def run_pipeline(
    code_dir: Path,
    *,
    stage: str = "extract",
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run the pipeline locally against agent-generated code."""
    ctx = RunContext(code_dir=code_dir)

    # Load config
    config_path = code_dir / "config.json"
    config: dict[str, Any] = {}
    if config_path.exists():
        config = json.loads(config_path.read_text())

    url = config.get("source_url", "")
    if not url:
        raise ValueError("config.json must contain 'source_url'")

    stealth_str = config.get("stealth_level", "basic")
    try:
        stealth = StealthLevel(stealth_str)
    except ValueError:
        stealth = StealthLevel.BASIC

    # Don't use NONE for browser — use BASIC minimum
    browser_stealth = stealth if stealth != StealthLevel.NONE else StealthLevel.BASIC
    browser_config = BrowserConfig(stealth_level=browser_stealth)

    result: dict[str, Any] = {"stage": stage, "success": False, "data": [], "errors": []}

    try:
        async with ForumBrowser(browser_config) as browser:
            page = await browser.new_page()

            # Navigate
            html_pages = await run_navigate(page, ctx, url)

            # Extract from each page
            all_data: list[dict[str, Any]] = []
            for html in html_pages:
                await page.set_content(html)
                data = await run_extract(page, ctx)
                all_data.extend(data)

            result["data"] = all_data
            result["row_count"] = len(all_data)

            # Validate
            schema_path = code_dir / "schema.json"
            valid, validation_errors = validate_output(all_data, schema_path)
            result["valid"] = valid
            if validation_errors:
                result["validation_errors"] = validation_errors

            result["success"] = True

    except Exception as e:
        result["errors"].append(str(e))

    # Write output
    if output_path:
        assert ctx.output_dir is not None
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        out = output_path if output_path.suffix == ".json" else ctx.output_dir / "results.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    elif result["data"]:
        print(json.dumps(result["data"], indent=2, default=str))

    return result
