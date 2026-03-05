"""Record a test fixture from a live website.

Usage:
    python tests/record_fixture.py \\
        --url "https://example.com/data" \\
        --name "static_table" \\
        --description "Simple HTML table with product prices"

This script uses InteractionRecorder from forum_browser.testing to capture
all HTTP interactions and DOM snapshots, then saves to fixtures/<name>/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from forum_browser.browser import BrowserConfig, ForumBrowser
from forum_browser.testing.recorder import InteractionRecorder

from forum_schemas.models.pipeline import StealthLevel


async def record(url: str, name: str, description: str) -> None:
    fixtures_dir = Path(__file__).parent / "fixtures" / name
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    config = BrowserConfig(stealth_level=StealthLevel.BASIC)

    async with ForumBrowser(config) as browser:
        page = await browser.new_page()

        recorder = InteractionRecorder(name)
        recorder.attach(page)

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await recorder.capture_dom_snapshot(page, label="initial")

        recorder.save(fixtures_dir)

    # Save config
    fixture_config = {
        "url": url,
        "name": name,
        "description": description,
    }
    (fixtures_dir / "config.json").write_text(json.dumps(fixture_config, indent=2))

    print(f"Fixture saved to {fixtures_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a test fixture")
    parser.add_argument("--url", required=True, help="URL to record")
    parser.add_argument("--name", required=True, help="Fixture name")
    parser.add_argument("--description", required=True, help="Description of the fixture")
    args = parser.parse_args()

    asyncio.run(record(args.url, args.name, args.description))


if __name__ == "__main__":
    main()
