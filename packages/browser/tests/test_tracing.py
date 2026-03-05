"""Tests for Playwright trace capture."""

from __future__ import annotations

from pathlib import Path

from forum_browser.browser import BrowserConfig, ForumBrowser
from forum_schemas.models.pipeline import StealthLevel


class TestTracing:
    async def test_trace_capture(self, tmp_path: Path) -> None:
        trace_dir = tmp_path / "traces"
        config = BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True, trace_enabled=True, trace_dir=str(trace_dir))
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<p>Trace test</p>")
            text = await page.text_content("p")
            assert text == "Trace test"

        # After teardown, trace file should exist
        trace_files = list(trace_dir.glob("*.zip"))
        assert len(trace_files) >= 1
        # Verify trace file is a valid zip
        import zipfile
        assert zipfile.is_zipfile(trace_files[0])

    async def test_no_trace_when_disabled(self, tmp_path: Path) -> None:
        trace_dir = tmp_path / "traces"
        config = BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True, trace_enabled=False, trace_dir=str(trace_dir))
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<p>No trace</p>")

        assert not trace_dir.exists() or len(list(trace_dir.glob("*.zip"))) == 0
